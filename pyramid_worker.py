#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""敦煌画卷 · 全量 DZI 图块生成器（后台任务）

特点：
  - libvips 流式读取（access="sequential"），内存只与"宽度 × 一个 tile 行"相关；
  - 单进程、单文件串行；容器内存硬上限（compose 里 640m），超限只会杀本容器；
  - 断点续跑：状态写入 /cache/pyramid_build_state.json，重启后跳过已完成文件；
  - 已存在全分辨率 DZI 的文件自动跳过（不重复生成）；
  - 可随时暂停：创建 /cache/pyramid_build.stop 后，当前文件完成即退出；
  - 全程日志：/cache/pyramid_build.log（docker logs 也能看进度）。
"""
import base64
import hashlib
import json
import math
import os
import re
import shutil
import time
from pathlib import Path

import pyvips

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
CACHE_DIR = Path(os.environ.get("CACHE_DIR", "/cache"))
PYRAMIDS_DIR = CACHE_DIR / "pyramids"
STATE_FILE = CACHE_DIR / "pyramid_build_state.json"
LOG_FILE = CACHE_DIR / "pyramid_build.log"
STOP_FILE = CACHE_DIR / "pyramid_build.stop"

TIFF_EXTS = {".tif", ".tiff", ".btf"}
TILE_QUALITY = int(os.environ.get("TILE_QUALITY", "82"))
MEM_FLOOR_MB = float(os.environ.get("BUILD_MEM_FLOOR_MB", "1200"))
# 单个 tile 行的目标内存（字节）：宽度 × 3 通道 × tile 高
TARGET_STRIP_MB = float(os.environ.get("BUILD_STRIP_MB", "96"))
RETRY_TIMES = 2
MAX_ATTEMPTS_DEFERRED = 3
# 超巨卷阈值：先跳过（后续单独用低内存方式处理），避免反复 OOM
HUGE_PIXELS = int(os.environ.get("HUGE_PIXELS", "400000000"))
HUGE_WIDTH = int(os.environ.get("HUGE_WIDTH", "100000"))

try:
    pyvips.cache_set_max_mem(16 * 1024 * 1024)
    pyvips.cache_set_max_files(16)
except Exception:
    pass


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


# ---------------------------------------------------------------- 与 app 保持一致的映射
def encode_id(rel: str) -> str:
    return base64.urlsafe_b64encode(rel.encode("utf-8")).decode("ascii").rstrip("=")


def file_hash(fid: str) -> str:
    return hashlib.sha1(fid.encode("utf-8")).hexdigest()[:16]


def pyramid_paths(rel: str):
    h = file_hash(encode_id(rel))
    folder = PYRAMIDS_DIR / h
    return folder / f"{h}.dzi", folder / f"{h}_files"


def order_key(name: str):
    stem = Path(name).stem.strip()
    if stem.isdigit():
        return (0, int(stem), "")
    return (1, 0, stem.lower())


def mem_available_mb():
    try:
        with open("/proc/meminfo", "r", encoding="ascii") as fh:
            for line in fh:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) / 1024.0
    except Exception:
        return None
    return None


# ---------------------------------------------------------------- 状态
def load_state() -> dict:
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data.setdefault("done", {})
            data.setdefault("failed", {})
            return data
    except Exception:
        pass
    return {"done": {}, "failed": {}, "current": "", "updated": 0,
            "started": int(time.time()), "total_done_bytes": 0, "total_done_sec": 0.0}


def save_state(state: dict) -> None:
    state["updated"] = int(time.time())
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, STATE_FILE)


# ---------------------------------------------------------------- 扫描
def scan_files():
    found = []
    for root, dirs, files in os.walk(DATA_DIR):
        dirs.sort(key=order_key)
        tiffs = [f for f in files if Path(f).suffix.lower() in TIFF_EXTS]
        if not tiffs:
            continue
        root_path = Path(root)
        for name in sorted(tiffs, key=order_key):
            full = root_path / name
            try:
                if not full.is_file():
                    continue
            except OSError:
                continue
            rel = str(full.relative_to(DATA_DIR)).replace("\\", "/")
            found.append((rel, full))
    return found


# ---------------------------------------------------------------- DZI 检查
def dzi_meta(dzi_path: Path):
    try:
        text = dzi_path.read_text(encoding="utf-8", errors="replace")
        mw = re.search(r'Width="(\d+)"', text)
        mh = re.search(r'Height="(\d+)"', text)
        mt = re.search(r'TileSize="(\d+)"', text)
        if not mw or not mh:
            return None
        return {
            "width": int(mw.group(1)),
            "height": int(mh.group(1)),
            "tile": int(mt.group(1)) if mt else 512,
        }
    except Exception:
        return None


def tiff_size(path: Path):
    import tifffile

    try:
        with tifffile.TiffFile(path) as tif:
            page = tif.pages[0]
            return int(page.imagewidth), int(page.imagelength), int(page.samplesperpixel or 1)
    except Exception:
        return None


def already_full(rel: str):
    dzi_path, files_dir = pyramid_paths(rel)
    if not dzi_path.exists() or not files_dir.exists():
        return False
    meta = dzi_meta(dzi_path)
    dims = tiff_size(DATA_DIR / rel)
    if not meta or not dims:
        return False
    return meta["width"] == dims[0] and meta["height"] == dims[1]


# ---------------------------------------------------------------- 生成
def choose_tile_size(width: int, bands: int) -> int:
    target = TARGET_STRIP_MB * 1024 * 1024
    bands = max(1, min(bands, 4))
    for tile in (512, 256, 128, 64, 32):
        if width * bands * tile <= target:
            return tile
    return 32


def prepare_image(path: Path) -> pyvips.Image:
    """打开 TIFF 并转成 8 位、3/1 通道（交给 libvips 流式处理，不整卷进内存）。"""
    image = pyvips.Image.new_from_file(str(path), access="sequential")
    interp = str(image.interpretation)
    fmt = str(image.format)
    bands = image.bands
    # 位深转换（16 位 → 8 位，和查看器预览的 /257 保持一致）
    if fmt in ("ushort", "short"):
        image = (image / 257.0).cast("uchar")
    elif fmt not in ("uchar",):
        # 其它位深（uint/int/float 等）：尽量线性压到 0-255
        if fmt in ("uint", "int"):
            maxval = float(2 ** 16 - 1)
            image = (image * (255.0 / maxval)).cast("uchar")
        else:
            image = image.cast("uchar")
    # 色彩空间
    if interp in ("cmyk", "cmyk16") or bands == 4:
        try:
            if interp in ("cmyk", "cmyk16"):
                image = image.colourspace("srgb")
            else:
                image = image.extract_band(0, n=3)
        except Exception:
            image = image.extract_band(0, n=min(3, bands))
    elif bands == 2:
        image = image.extract_band(0)
    elif bands > 4:
        image = image.extract_band(0, n=3 if interp in ("rgb", "srgb") else 1)
    return image


def build_one(rel: str, path: Path) -> dict:
    dzi_path, files_dir = pyramid_paths(rel)
    dzi_path.parent.mkdir(parents=True, exist_ok=True)
    if files_dir.exists():
        shutil.rmtree(files_dir, ignore_errors=True)
    if dzi_path.exists():
        dzi_path.unlink()
    dims = tiff_size(path)
    if not dims:
        raise RuntimeError("无法读取 TIFF 元数据")
    width, _height, samples = dims
    image = prepare_image(path)
    tile = choose_tile_size(width, image.bands)
    base = str(dzi_path.with_suffix(""))
    image.dzsave(base, tile_size=tile, overlap=0,
                 suffix=f".jpg[Q={TILE_QUALITY}]", layout="dz")
    meta = dzi_meta(dzi_path)
    if not meta or meta["width"] != width:
        raise RuntimeError(f"生成校验失败：DZI 宽度 {meta and meta['width']} != 原图 {width}")
    out_bytes = sum(f.stat().st_size for f in files_dir.rglob("*") if f.is_file())
    tiles = sum(1 for f in files_dir.rglob("*.jpg"))
    return {"width": width, "height": dims[1], "tile": tile, "tiles": tiles,
            "out_bytes": out_bytes, "src_bytes": path.stat().st_size}


# ---------------------------------------------------------------- 超巨卷专用模式
def run_deferred_mode() -> int:
    """只处理主任务里被延后的超巨卷；独立容器、更高内存上限。"""
    log("=" * 60)
    log("超巨卷生成模式启动（PROCESS_DEFERRED=1）")
    state = load_state()
    state.setdefault("attempts", {})
    deferred = state.setdefault("deferred", {})
    pending = list(deferred.keys())
    log(f"待处理超巨卷 {len(pending)} 个")
    ok = fail = 0
    t_start = time.time()
    for idx, rel in enumerate(pending, 1):
        if STOP_FILE.exists():
            log("收到暂停信号（/cache/pyramid_build.stop），退出")
            save_state(state)
            return 0
        path = DATA_DIR / rel
        if not path.exists():
            state["failed"][rel] = {"error": "源文件不存在", "ts": int(time.time())}
            deferred.pop(rel, None)
            save_state(state)
            fail += 1
            continue
        attempts = int(state["attempts"].get(rel, 0))
        if attempts >= MAX_ATTEMPTS_DEFERRED:
            state["failed"][rel] = {"error": f"连续 {attempts} 次未完成（可能内存不足），已跳过",
                                    "ts": int(time.time())}
            state["attempts"].pop(rel, None)
            deferred.pop(rel, None)
            save_state(state)
            fail += 1
            log(f"跳过反复失败的超巨卷：{rel}")
            continue
        avail = mem_available_mb()
        while avail is not None and avail < MEM_FLOOR_MB:
            log(f"可用内存 {avail:.0f}MB < {MEM_FLOOR_MB:.0f}MB，等待 60 秒…")
            time.sleep(60)
            if STOP_FILE.exists():
                log("收到暂停信号，退出")
                save_state(state)
                return 0
            avail = mem_available_mb()
        state["attempts"][rel] = attempts + 1
        state["current"] = rel
        save_state(state)
        t0 = time.time()
        try:
            info = build_one(rel, path)
            elapsed = time.time() - t0
            state["done"][rel] = {
                "ts": int(time.time()), "tiles": info["tiles"], "tile": info["tile"],
                "out_bytes": info["out_bytes"], "src_bytes": info["src_bytes"],
            }
            state["failed"].pop(rel, None)
            state["attempts"].pop(rel, None)
            deferred.pop(rel, None)
            save_state(state)
            ok += 1
            log(f"[{idx}/{len(pending)}] ✓ {rel}  {info['width']}×{info['height']}  "
                f"tile={info['tile']}  {info['tiles']}块/{info['out_bytes']/1e6:.1f}MB  "
                f"{elapsed:.1f}s  剩余 {len(pending)-idx} 个")
        except Exception as exc:
            fail += 1
            err = f"{type(exc).__name__}: {exc}"
            state["failed"][rel] = {"error": err, "ts": int(time.time())}
            save_state(state)
            log(f"[{idx}/{len(pending)}] ✗ {rel} 失败：{err}")
    log(f"超巨卷处理结束：成功 {ok}，失败 {fail}，耗时 {(time.time()-t_start)/3600:.2f} 小时")
    save_state(state)
    return 0


# ---------------------------------------------------------------- 主流程
def main() -> int:
    if os.environ.get("PROCESS_DEFERRED") == "1":
        return run_deferred_mode()
    log("=" * 60)
    log("DZI 全量生成器启动：DATA_DIR=%s CACHE=%s" % (DATA_DIR, CACHE_DIR))
    if STOP_FILE.exists():
        STOP_FILE.unlink()
    state = load_state()
    log(f"历史状态：已完成 {len(state['done'])}，失败 {len(state['failed'])}")

    files = scan_files()
    total = len(files)
    pending = [(rel, p) for rel, p in files if not already_full(rel)]
    log(f"共扫描到 {total} 个 TIFF，需要生成全分辨率图块 {len(pending)} 个")
    pending_bytes = sum(p.stat().st_size for _, p in pending)
    log(f"待处理源文件总量 {pending_bytes / 1e9:.1f} GB")

    state.setdefault("attempts", {})
    MAX_ATTEMPTS = 3
    ok = fail = skip = 0
    t_start = time.time()
    processed_bytes = 0
    out_total = 0
    for idx, (rel, path) in enumerate(pending, 1):
        if STOP_FILE.exists():
            log("收到暂停信号（/cache/pyramid_build.stop），退出")
            save_state(state)
            return 0
        if rel in state["done"]:
            skip += 1
            continue
        dims = tiff_size(path)
        if dims and (dims[0] * dims[1] > HUGE_PIXELS or dims[0] > HUGE_WIDTH or dims[1] > HUGE_WIDTH):
            deferred = state.setdefault("deferred", {})
            if rel not in deferred:
                deferred[rel] = {"width": dims[0], "height": dims[1],
                                 "pixels": dims[0] * dims[1], "ts": int(time.time())}
                save_state(state)
            continue
        attempts = int(state["attempts"].get(rel, 0))
        if attempts >= MAX_ATTEMPTS:
            fail += 1
            state["failed"][rel] = {"error": f"连续 {attempts} 次未完成（可能内存不足），已跳过",
                                    "ts": int(time.time())}
            state["attempts"].pop(rel, None)
            save_state(state)
            log(f"跳过反复失败的文件：{rel}")
            continue
        state["attempts"][rel] = attempts + 1
        save_state(state)
        avail = mem_available_mb()
        while avail is not None and avail < MEM_FLOOR_MB:
            log(f"可用内存 {avail:.0f}MB < {MEM_FLOOR_MB:.0f}MB，等待 60 秒…")
            time.sleep(60)
            if STOP_FILE.exists():
                log("收到暂停信号，退出")
                save_state(state)
                return 0
            avail = mem_available_mb()
        try:
            src_bytes = path.stat().st_size
        except OSError:
            fail += 1
            state["failed"][rel] = {"error": "源文件不可读", "ts": int(time.time())}
            save_state(state)
            continue
        state["current"] = rel
        save_state(state)
        t0 = time.time()
        err = None
        info = None
        for attempt in range(1, RETRY_TIMES + 1):
            try:
                info = build_one(rel, path)
                err = None
                break
            except MemoryError:
                err = "内存不足"
            except Exception as exc:
                err = f"{type(exc).__name__}: {exc}"
            log(f"  第 {attempt} 次失败：{rel} → {err}")
            time.sleep(5)
        elapsed = time.time() - t0
        if info is None:
            fail += 1
            state["failed"][rel] = {"error": err, "ts": int(time.time())}
            save_state(state)
            log(f"[{idx}/{len(pending)}] ✗ {rel} 失败：{err}（{elapsed:.0f}s）")
            continue
        ok += 1
        processed_bytes += src_bytes
        out_total += info["out_bytes"]
        state["done"][rel] = {
            "ts": int(time.time()), "tiles": info["tiles"], "tile": info["tile"],
            "out_bytes": info["out_bytes"], "src_bytes": src_bytes,
        }
        state["failed"].pop(rel, None)
        state["attempts"].pop(rel, None)
        save_state(state)
        speed = src_bytes / 1e6 / max(0.1, elapsed)
        progressed = idx
        remain = len(pending) - progressed
        avg_speed = processed_bytes / 1e6 / max(0.1, time.time() - t_start)
        eta_h = (pending_bytes - processed_bytes) / 1e6 / max(0.1, avg_speed) / 3600.0
        log(f"[{idx}/{len(pending)}] ✓ {rel}  {info['width']}×{info['height']}  "
            f"tile={info['tile']}  {info['tiles']}块/{info['out_bytes']/1e6:.1f}MB  "
            f"源{src_bytes/1e6:.0f}MB  {elapsed:.1f}s ({speed:.1f}MB/s)  "
            f"剩余 {remain} 个 / 预计还需 {eta_h:.1f} 小时  输出累计 {out_total/1e9:.2f}GB")
    deferred = state.setdefault("deferred", {})
    log(f"本轮结束：成功 {ok}，失败 {fail}，跳过 {skip}，待单独处理超巨卷 {len(deferred)} 个；"
        f"输出 {out_total/1e9:.2f}GB；总耗时 {(time.time()-t_start)/3600:.2f} 小时")
    save_state(state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
