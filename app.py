# -*- coding: utf-8 -*-
"""敦煌画卷 · NAS 高清图查看服务

设计目标：
- 直接读取 NAS 本机磁盘上的 TIFF 扫描件（不做任何拷贝/转码全量）
- 首次打开某卷时在 NAS 本地生成 DZI 缩放图块（进度可查），之后秒开
- 浏览器（电脑/手机/平板）通过网页缩放浏览，只下载小图块
- 提供元数据、说明.txt、原图下载、按卷分段浏览

接口：
  GET  /                         画廊页
  GET  /view/{item_id}           查看器页
  GET  /api/index                索引（分类、卷列表）
  GET  /api/item/{item_id}       单卷详情（每段的尺寸/DPI/压缩、说明文字）
  GET  /thumb/{file_id}          缩略图（磁盘缓存）
  POST /api/pyramid/{file_id}    触发生成缩放图块（幂等）
  GET  /api/pyramid/{file_id}/status  生成进度
  GET  /tiles/...                图块静态文件（DZI）
  GET  /file/{file_id}           下载原图
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import html as _html
import re
import io
import json
import math
import os
import shutil
import threading
import time
import traceback
from contextlib import asynccontextmanager
from pathlib import Path

import numpy as np
import tifffile
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from urllib.parse import parse_qs, quote
from fastapi.staticfiles import StaticFiles
from PIL import Image

try:  # libvips 优先：流式解码，降低超大扫描件的内存占用
    import pyvips

    HAS_VIPS = True
except Exception:  # 没装 libvips 时退回 Pillow（小图够用，超大图可能吃内存）
    pyvips = None
    HAS_VIPS = False

Image.MAX_IMAGE_PIXELS = None

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
CACHE_DIR = Path(os.environ.get("CACHE_DIR", "/cache"))
STATIC_DIR = BASE_DIR / "static"

TIFF_EXTS = {".tif", ".tiff", ".btf"}
PYRAMIDS_DIR = CACHE_DIR / "pyramids"
THUMBS_DIR = CACHE_DIR / "thumbs"

TILE_SIZE = int(os.environ.get("TILE_SIZE", "512"))
TILE_QUALITY = int(os.environ.get("TILE_QUALITY", "82"))
THUMB_SIZE = int(os.environ.get("THUMB_SIZE", "480"))
CACHE_MAX_GB = float(os.environ.get("CACHE_MAX_GB", "50"))
THUMB_WORKERS = int(os.environ.get("THUMB_WORKERS", "2"))

# —— 登录墙（公网部署用）——
AUTH_USER = os.environ.get("AUTH_USER", "").strip()
AUTH_PASS = os.environ.get("AUTH_PASS", "").strip()
AUTH_SECRET = os.environ.get("AUTH_SECRET", "").strip()
AUTH_SESSION_HOURS = int(os.environ.get("AUTH_SESSION_HOURS", "168"))
AUTH_ENABLED = bool(AUTH_USER and AUTH_PASS and AUTH_SECRET)
SESSION_COOKIE = "dh_session"
USERS_FILE = Path(os.environ.get("USERS_FILE", "/cache/users.json"))
USERS_LOCK = threading.Lock()

# —— 内存安全红线：查看器不能耗尽宿主机内存 ——
MEM_GUARD_MB = int(os.environ.get("MEM_GUARD_MB", "900"))  # 可用内存低于此值就拒绝解码
FULL_DZI_MAX_PIXELS = int(os.environ.get("FULL_DZI_MAX_PIXELS", "350000000"))  # 超过此像素量只做预览
PREVIEW_LONG_EDGE = int(os.environ.get("PREVIEW_LONG_EDGE", "10000"))  # 预览图长边像素
PREVIEW_MAX_PIXELS = int(os.environ.get("PREVIEW_MAX_PIXELS", "20000000"))  # 预览图总像素上限
THUMB_VIPS_MAX_PIXELS = int(os.environ.get("THUMB_VIPS_MAX_PIXELS", "30000000"))  # 缩略图允许整卷解码的上限
PREVIEW_VIPS_MAX_PIXELS = int(os.environ.get("PREVIEW_VIPS_MAX_PIXELS", "30000000"))  # 预览允许整卷解码的上限

PYRAMIDS_DIR.mkdir(parents=True, exist_ok=True)
THUMBS_DIR.mkdir(parents=True, exist_ok=True)


# ------------------------------------------------------------------ 基础工具

def encode_id(rel: str) -> str:
    return base64.urlsafe_b64encode(rel.encode("utf-8")).decode("ascii").rstrip("=")


def decode_id(value: str) -> str:
    padding = "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode(value + padding).decode("utf-8")
    except Exception:
        raise HTTPException(status_code=400, detail="无效的编号")


def order_key(name: str):
    """数字文件名（1.tif, 2.tif...）按数字排前面，其余按名称排。"""
    stem = Path(name).stem.strip()
    if stem.isdigit():
        return (0, int(stem), "")
    return (1, 0, stem.lower())


def file_hash(fid: str) -> str:
    return hashlib.sha1(fid.encode("utf-8")).hexdigest()[:16]


def human_size(n: float) -> str:
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{int(n)} B" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def mem_available_mb() -> float | None:
    """读取当前可用内存（MB），读不到返回 None。"""
    try:
        with open("/proc/meminfo", "r", encoding="ascii") as fh:
            for line in fh:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) / 1024.0
    except Exception:
        pass
    return None


# ------------------------------------------------------------------ 图像解码

def load_page_array(path: Path, page: int = 0) -> np.ndarray:
    with tifffile.TiffFile(path) as tif:
        if len(tif.pages) == 0:
            raise ValueError("文件里没有图像页")
        pg = tif.pages[min(page, len(tif.pages) - 1)]
        name = str(getattr(pg.photometric, "name", "")).upper()
        if name in ("SEPARATED", "YCBCR", "PALETTE", "CIELAB", "CMYK"):
            try:
                return pg.asarray(photometric="rgb")
            except Exception:
                pass
        return pg.asarray()


def _to_8bit(arr: np.ndarray) -> np.ndarray:
    """把非 8 位图像线性拉伸到 0-255。"""
    if arr.dtype == np.uint8:
        return arr
    x = arr.astype(np.float32)
    if x.ndim == 2:
        lo, hi = np.percentile(x[::4, ::4], [0.5, 99.5])
        if hi <= lo:
            lo, hi = float(x.min()), float(x.max())
        if hi <= lo:
            hi = lo + 1.0
        return np.clip((x - lo) / (hi - lo) * 255.0, 0, 255).astype(np.uint8)
    out = np.empty_like(x)
    for c in range(x.shape[2]):
        lo, hi = np.percentile(x[::4, ::4, c], [0.5, 99.5])
        if hi <= lo:
            lo, hi = float(x[..., c].min()), float(x[..., c].max())
        if hi <= lo:
            hi = lo + 1.0
        out[..., c] = (x[..., c] - lo) / (hi - lo) * 255.0
    return np.clip(out, 0, 255).astype(np.uint8)


def array_to_pil(arr: np.ndarray) -> Image.Image:
    arr = _to_8bit(arr)
    if arr.ndim == 2:
        return Image.fromarray(np.ascontiguousarray(arr), "L")
    if arr.ndim != 3:
        raise ValueError(f"不支持的数据形状: {arr.shape}")
    channels = arr.shape[2]
    if channels == 1:
        return Image.fromarray(np.ascontiguousarray(arr[..., 0]), "L")
    if channels == 2:
        return Image.fromarray(np.ascontiguousarray(arr[..., 0]), "L")
    if channels == 3:
        return Image.fromarray(np.ascontiguousarray(arr), "RGB")
    return Image.fromarray(np.ascontiguousarray(arr[..., :4]), "RGBA")


def read_meta(path: Path) -> dict:
    meta: dict = {"size": path.stat().st_size}
    try:
        with tifffile.TiffFile(path) as tif:
            pg = tif.pages[0]
            meta["width"] = int(pg.imagewidth)
            meta["height"] = int(pg.imagelength)
            meta["pages"] = len(tif.pages)
            meta["compression"] = str(getattr(pg.compression, "name", pg.compression))
            meta["dtype"] = str(np.dtype(pg.dtype))
            meta["bigtiff"] = bool(tif.is_bigtiff)
            xr = pg.tags.get("XResolution")
            yr = pg.tags.get("YResolution")
            try:
                if xr is not None and yr is not None:
                    xv = xr.value[0] / xr.value[1] if isinstance(xr.value, tuple) else float(xr.value)
                    meta["dpi"] = round(float(xv))
            except Exception:
                pass
            software = pg.tags.get("Software")
            if software is not None:
                meta["software"] = str(software.value)[:80]
    except Exception as exc:  # 单个文件读失败不影响整卷
        meta["error"] = str(exc)
    return meta


# ------------------------------------------------------------------ 索引

INDEX_LOCK = threading.Lock()
INDEX: dict = {
    "status": "empty", "error": None, "scan_seconds": None,
    "items": [], "categories": [], "total_files": 0, "total_bytes": 0,
}
ITEM_BY_ID: dict[str, dict] = {}
FILE_BY_ID: dict[str, dict] = {}


def scan_index() -> None:
    INDEX["status"] = "scanning"
    started = time.time()
    items: list[dict] = []
    file_map: dict[str, dict] = {}
    categories: list[str] = []
    total_files = 0
    total_bytes = 0
    try:
        if not DATA_DIR.exists():
            raise FileNotFoundError(f"数据目录不存在: {DATA_DIR}")
        for cat_dir in sorted(DATA_DIR.iterdir(), key=lambda p: order_key(p.name)):
            if not cat_dir.is_dir() or cat_dir.name.startswith(("@", "#", ".")):
                continue
            categories.append(cat_dir.name)
            for root, dirs, files in os.walk(cat_dir):
                dirs[:] = sorted((d for d in dirs if not d.startswith(("@", "#", "."))), key=order_key)
                tiffs = sorted((f for f in files if Path(f).suffix.lower() in TIFF_EXTS), key=order_key)
                if not tiffs:
                    continue
                root_path = Path(root)
                entries = []
                for name in tiffs:
                    fp = root_path / name
                    try:
                        size = fp.stat().st_size
                    except OSError:
                        size = 0
                    rel = fp.relative_to(DATA_DIR).as_posix()
                    fid = encode_id(rel)
                    entry = {"id": fid, "name": name, "size": size, "rel": rel}
                    entries.append(entry)
                    file_map[fid] = entry
                    total_files += 1
                    total_bytes += size
                rel_dir = root_path.relative_to(DATA_DIR).as_posix()
                items.append({
                    "id": encode_id(rel_dir),
                    "title": root_path.name,
                    "category": cat_dir.name,
                    "files": entries,
                    "file_count": len(entries),
                    "bytes": sum(e["size"] for e in entries),
                    "cover": min(entries, key=lambda e: e["size"])["id"],
                })
        with INDEX_LOCK:
            INDEX.update(
                status="ready", error=None, items=items, categories=categories,
                total_files=total_files, total_bytes=total_bytes,
                scan_seconds=round(time.time() - started, 1),
            )
            ITEM_BY_ID.clear()
            ITEM_BY_ID.update({it["id"]: it for it in items})
            FILE_BY_ID.clear()
            FILE_BY_ID.update(file_map)
    except Exception as exc:
        INDEX.update(status="error", error=str(exc))


def to_json_index() -> dict:
    with INDEX_LOCK:
        return {
            "status": INDEX["status"],
            "error": INDEX["error"],
            "scan_seconds": INDEX["scan_seconds"],
            "categories": list(INDEX["categories"]),
            "total_files": INDEX["total_files"],
            "total_bytes": INDEX["total_bytes"],
            "total_size": human_size(INDEX["total_bytes"]),
            "items": [
                {
                    "id": it["id"], "title": it["title"], "category": it["category"],
                    "file_count": it["file_count"], "bytes": it["bytes"],
                    "size": human_size(it["bytes"]), "cover": it["cover"],
                }
                for it in INDEX["items"]
            ],
        }


# ------------------------------------------------------------------ 缩放图块（DZI）

PYR_STATE: dict[str, dict] = {}
PYR_STATE_LOCK = threading.Lock()
PYR_GENERATE_LOCK = threading.Semaphore(1)


def set_pyr_state(fid: str, state: str, percent: int = 0, error: str | None = None,
                  preview_only: bool = False) -> None:
    with PYR_STATE_LOCK:
        PYR_STATE[fid] = {
            "state": state, "percent": percent, "error": error,
            "hash": file_hash(fid), "preview_only": bool(preview_only),
        }


def get_pyr_state(fid: str) -> dict:
    with PYR_STATE_LOCK:
        return dict(PYR_STATE.get(fid) or {
            "state": "missing", "percent": 0, "error": None,
            "hash": file_hash(fid), "preview_only": False,
        })


def pyramid_files(fid: str) -> tuple[Path, Path]:
    h = file_hash(fid)
    folder = PYRAMIDS_DIR / h
    return folder / f"{h}.dzi", folder / f"{h}_files"


def dzi_preview_flag(dzi_path: Path, source: Path) -> bool:
    """已生成的 DZI 是否为预览分辨率（图块宽度小于原图宽度即为预览）。"""
    try:
        import re as _re

        text = dzi_path.read_text(encoding="utf-8", errors="replace")
        match = _re.search(r'Width="(\d+)"', text)
        if not match:
            return False
        dzi_w = int(match.group(1))
        with tifffile.TiffFile(source) as tif:
            orig_w = int(tif.pages[0].imagewidth)
        return dzi_w < orig_w
    except Exception:
        return False


def evict_cache() -> None:
    if CACHE_MAX_GB <= 0:
        return
    try:
        folders = []
        for d in PYRAMIDS_DIR.iterdir():
            if not d.is_dir():
                continue
            size = sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
            folders.append((d.stat().st_mtime, size, d))
        total = sum(x[1] for x in folders)
        limit = int(CACHE_MAX_GB * 1024**3)
        if total <= limit:
            return
        folders.sort()
        for _, size, d in folders:
            if total <= limit * 0.8:
                break
            shutil.rmtree(d, ignore_errors=True)
            total -= size
    except Exception:
        pass


def build_pyramid(path: Path, fid: str, progress=None) -> bool:
    """生成 DZI 缩放图块。返回 True 表示只生成了预览分辨率。"""
    if HAS_VIPS:
        return _build_pyramid_vips(path, fid, progress)
    return _build_pyramid_pillow(path, fid, progress)


def _assert_memory_ok() -> None:
    avail = mem_available_mb()
    if avail is not None and avail < MEM_GUARD_MB:
        raise RuntimeError(
            f"NAS 可用内存仅 {avail:.0f} MB（低于安全阈值 {MEM_GUARD_MB} MB），已拒绝解码，请稍后再试"
        )


def _stream_preview_plain_tiff(path: Path, long_edge: int, max_pixels: int = 20_000_000):
    """把未压缩 8 位 TIFF 流式缩小成预览图，内存占用只与输出图大小有关。

    做法：按整数倍 factor 分块读取源行，块内做行/列平均，逐输出行填充。
    适合"单条带、未压缩"的大扫描件（这批敦煌 TIFF 基本都是）。
    不满足条件或出错时返回 None，由调用方回退到 libvips。
    """
    try:
        import numpy as _np

        with tifffile.TiffFile(path) as tif:
            page = tif.pages[0]
            if int(page.compression) != 1:          # 只处理未压缩
                return None
            if str(getattr(page.planarconfig, "name", "")) != "CONTIG":
                return None
            page_dtype = _np.dtype(page.dtype)
            if page_dtype not in (_np.dtype(_np.uint8), _np.dtype(_np.uint16)):
                return None
            width = int(page.imagewidth)
            height = int(page.imagelength)
            samples = int(page.samplesperpixel or 1)
            if samples not in (1, 3, 4):
                return None
            photo = str(getattr(page.photometric, "name", "")).upper()
            if photo in ("YCBCR", "PALETTE", "CIELAB", "LAB"):
                return None
            rowsperstrip = int(page.rowsperstrip or height)
            offsets = tuple(int(v) for v in page.dataoffsets)
            counts = tuple(int(v) for v in page.databytecounts)
            expected = (height + rowsperstrip - 1) // rowsperstrip
            if len(offsets) != expected:
                return None
            row_bytes = width * samples * page_dtype.itemsize
            for i, (off, cnt) in enumerate(zip(offsets, counts)):
                rows = min(rowsperstrip, height - i * rowsperstrip)
                if cnt < rows * row_bytes:
                    return None

            factor = max(1, math.ceil(max(width, height) / max(1, long_edge)))
            # 同时限制总像素，避免近方形超大卷把内存撑爆
            if width * height > max_pixels * factor * factor:
                factor = max(factor, math.ceil(math.sqrt(width * height / max_pixels)))
            out_w = max(1, width // factor)
            out_h = max(1, height // factor)
            out = _np.empty((out_h, out_w, samples), dtype=_np.uint8)
            row_stride = max(1, factor // 2)   # 每 band 只抽读一半行，再对列取平均
            with open(path, "rb") as fh:
                for oy in range(out_h):
                    y0 = oy * factor
                    y1 = min(y0 + factor, height)
                    sampled = list(range(y0, y1, row_stride))[:6] or [y0]
                    acc = None
                    for j in sampled:
                        strip = j // rowsperstrip
                        off = offsets[strip] + (j - strip * rowsperstrip) * row_bytes
                        fh.seek(off)
                        buf = fh.read(row_bytes)
                        if len(buf) != row_bytes:
                            return None
                        row = _np.frombuffer(buf, dtype=page_dtype).reshape(width, samples)
                        acc = row.astype(_np.float32) if acc is None else acc + row
                    rows_mean = acc / len(sampled)
                    cols = rows_mean[: out_w * factor].reshape(out_w, factor, samples)
                    col_mean = cols.mean(axis=1)
                    if page_dtype.itemsize == 2:   # 16 位 → 8 位显示
                        out[oy] = _np.clip(col_mean / 257.0, 0, 255).astype(_np.uint8)
                    else:
                        out[oy] = col_mean.astype(_np.uint8)
        if samples == 1:
            return Image.fromarray(out[..., 0], "L")
        if samples == 4 and photo in ("SEPARATED", "CMYK"):
            return Image.fromarray(out, "CMYK").convert("RGB")
        # 4 通道按 RGBA 处理；JPEG 不支持透明通道，取前三通道
        return Image.fromarray(_np.ascontiguousarray(out[..., :3]), "RGB")
    except Exception:
        return None


def _build_pyramid_vips(path: Path, fid: str, progress=None) -> bool:
    dzi_path, files_dir = pyramid_files(fid)
    dzi_path.parent.mkdir(parents=True, exist_ok=True)
    if files_dir.exists():
        shutil.rmtree(files_dir, ignore_errors=True)
    if dzi_path.exists():
        dzi_path.unlink()
    if progress:
        progress(5)

    _assert_memory_ok()
    with tifffile.TiffFile(path) as tif:
        page = tif.pages[0]
        photo = str(getattr(page.photometric, "name", "")).upper()
        page_dtype = str(np.dtype(page.dtype))
        orig_w = int(page.imagewidth)
        orig_h = int(page.imagelength)
    pixels = orig_w * orig_h
    # 超大卷、CMYK 等特殊色彩、16 位图（libvips 整卷转换会吃爆内存）→ 走流式预览
    need_preview = (
        pixels > FULL_DZI_MAX_PIXELS
        or photo not in ("RGB", "MINISBLACK", "MINISWHITE")
        or page_dtype != "uint8"
    )
    base = str(dzi_path.with_suffix(""))
    preview_only = False

    if need_preview:
        tmp_jpg = dzi_path.parent / f"{file_hash(fid)}_preview.jpg"
        preview_img = _stream_preview_plain_tiff(path, PREVIEW_LONG_EDGE, PREVIEW_MAX_PIXELS)
        if preview_img is not None:
            preview_only = max(preview_img.size) < max(orig_w, orig_h)
            preview_img.save(tmp_jpg, "JPEG", quality=85)
            del preview_img
        elif pixels > PREVIEW_VIPS_MAX_PIXELS:
            raise RuntimeError(
                "该卷为压缩格式的超大图，暂不支持在线预览（整卷解码会超出内存上限）；"
                "可下载原图查看，或告诉我文件名，我加专门的流式解码支持"
            )
        else:
            small = pyvips.Image.thumbnail(
                str(path), PREVIEW_LONG_EDGE, height=PREVIEW_LONG_EDGE, size="down"
            )
            small.jpegsave(str(tmp_jpg), Q=85)
        _assert_memory_ok()
        image = pyvips.Image.new_from_file(str(tmp_jpg), access="sequential")
        image.dzsave(
            base, tile_size=TILE_SIZE, overlap=0,
            suffix=f".jpg[Q={TILE_QUALITY}]", layout="dz",
        )
        # 预览 JPEG 保留在缓存里，后续缩略图直接用它，避免再次跳读原图
    else:
        image = pyvips.Image.new_from_file(str(path), access="sequential")
        image.dzsave(
            base, tile_size=TILE_SIZE, overlap=0,
            suffix=f".jpg[Q={TILE_QUALITY}]", layout="dz",
        )

    if progress:
        progress(100)
    return preview_only


def _build_pyramid_pillow(path: Path, fid: str, progress=None) -> bool:
    # 没有 libvips 时只允许处理中小图，超大图直接拒绝，防止整卷像素进内存
    with tifffile.TiffFile(path) as tif:
        page0 = tif.pages[0]
        pixels = int(page0.imagewidth) * int(page0.imagelength)
    if pixels > 150_000_000:
        raise RuntimeError(
            f"该卷 {pixels / 1e6:.0f} 百万像素，当前环境缺少 libvips，为安全起见拒绝整卷解码"
        )
    arr = load_page_array(path)
    img = array_to_pil(arr)
    del arr
    width, height = img.size
    max_level = max(0, math.ceil(math.log2(max(width, height))))
    dzi_path, files_dir = pyramid_files(fid)
    dzi_path.parent.mkdir(parents=True, exist_ok=True)
    if files_dir.exists():
        shutil.rmtree(files_dir, ignore_errors=True)
    files_dir.mkdir(parents=True, exist_ok=True)

    cur = img
    level = max_level
    levels_total = max_level + 1
    while level >= 0:
        lw, lh = cur.size
        cols = math.ceil(lw / TILE_SIZE)
        rows = math.ceil(lh / TILE_SIZE)
        level_dir = files_dir / str(level)
        level_dir.mkdir(parents=True, exist_ok=True)
        for r in range(rows):
            for c in range(cols):
                box = (
                    c * TILE_SIZE, r * TILE_SIZE,
                    min((c + 1) * TILE_SIZE, lw), min((r + 1) * TILE_SIZE, lh),
                )
                cur.crop(box).save(
                    level_dir / f"{c}_{r}.jpg", "JPEG",
                    quality=TILE_QUALITY, subsampling=2,
                )
        if progress:
            progress(int((max_level - level + 1) / levels_total * 100))
        if level > 0:
            nxt = cur.resize((max(1, (lw + 1) // 2), max(1, (lh + 1) // 2)), Image.LANCZOS)
            if cur is not img:
                cur.close()
            cur = nxt
        level -= 1

    dzi_path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<Image TileSize="{TILE_SIZE}" Overlap="0" Format="jpg" '
        'xmlns="http://schemas.microsoft.com/deepzoom/2008">\n'
        f'<Size Width="{width}" Height="{height}"/>\n</Image>\n',
        encoding="utf-8",
    )


def generate_worker(fid: str, entry: dict) -> None:
    stop = threading.Event()

    def ramp() -> None:
        """libvips 不回报百分比，用一个平滑的假进度让前端不显得卡死。"""
        percent = 5
        while not stop.wait(0.7):
            percent = min(90, percent + max(1, int((92 - percent) * 0.18)))
            set_pyr_state(fid, "generating", percent)

    ramp_thread = threading.Thread(target=ramp, daemon=True)
    try:
        _assert_memory_ok()
        with PYR_GENERATE_LOCK:
            set_pyr_state(fid, "generating", 2)
            ramp_thread.start()
            preview_only = build_pyramid(DATA_DIR / entry["rel"], fid)
            stop.set()
        set_pyr_state(fid, "ready", 100, preview_only=preview_only)
        evict_cache()
    except Exception as exc:
        stop.set()
        set_pyr_state(fid, "error", 0, str(exc))


# ------------------------------------------------------------------ 缩略图

THUMB_SEMAPHORE = threading.Semaphore(THUMB_WORKERS)


def thumb_file(fid: str) -> Path:
    return THUMBS_DIR / f"v3_{file_hash(fid)}.jpg"


def _save_center_thumb(img, tmp: Path) -> None:
    """把整幅缩略图裁成中心 4:3 局部再保存（长卷在画廊里才看得清）。"""
    width, height = img.size
    ratio = 4.0 / 3.0
    if width / max(1, height) > ratio:
        cw, ch = int(height * ratio), height
    else:
        cw, ch = width, int(width / ratio)
    cw = max(1, cw)
    ch = max(1, ch)
    x0 = max(0, (width - cw) // 2)
    y0 = max(0, (height - ch) // 2)
    crop = img.crop((x0, y0, x0 + cw, y0 + ch))
    crop.thumbnail((THUMB_SIZE, int(THUMB_SIZE * 3 / 4)), Image.LANCZOS)
    crop.save(tmp, "JPEG", quality=80)


def _fast_thumb_plain_tiff(path: Path, size: int):
    """超大/CMYK 的未压缩 TIFF：按行、列抽样读取生成缩略图，不整卷解码。"""
    try:
        import numpy as _np

        with tifffile.TiffFile(path) as tif:
            page = tif.pages[0]
            if int(page.compression) != 1:
                return None
            if str(getattr(page.planarconfig, "name", "")) != "CONTIG":
                return None
            dtype = _np.dtype(page.dtype)
            if dtype not in (_np.dtype(_np.uint8), _np.dtype(_np.uint16)):
                return None
            width = int(page.imagewidth)
            height = int(page.imagelength)
            samples = int(page.samplesperpixel or 1)
            if samples not in (1, 3, 4):
                return None
            rowsperstrip = int(page.rowsperstrip or height)
            offsets = tuple(int(v) for v in page.dataoffsets)
            row_bytes = width * samples * dtype.itemsize
            step_y = max(1, height // max(1, size))
            step_x = max(1, width // max(1, size))
            out_w = len(range(0, width, step_x))
            out_h = len(range(0, height, step_y))
            small = _np.empty((out_h, out_w, samples), dtype=dtype)
            with open(path, "rb") as fh:
                oy = 0
                for y in range(0, height, step_y):
                    strip = y // rowsperstrip
                    off = offsets[strip] + (y - strip * rowsperstrip) * row_bytes
                    fh.seek(off)
                    buf = fh.read(row_bytes)
                    if len(buf) != row_bytes:
                        return None
                    row = _np.frombuffer(buf, dtype=dtype).reshape(width, samples)[::step_x]
                    small[oy, : row.shape[0]] = row
                    oy += 1
            photo = str(getattr(page.photometric, "name", "")).upper()
        if dtype.itemsize == 2:   # 16 位 → 8 位
            small = _np.clip(small.astype(_np.float32) / 257.0, 0, 255).astype(_np.uint8)
        if samples == 1:
            return Image.fromarray(small[..., 0], "L")
        if samples == 4 and photo in ("SEPARATED", "CMYK"):
            return Image.fromarray(small, "CMYK").convert("RGB")
        return Image.fromarray(_np.ascontiguousarray(small[..., :3]), "RGB")
    except Exception:
        return None


def _thumb_from_pyramid(fid: str, size: int):
    """从已生成的 DZI 图块里取中间一块当缩略图（避免重新解码原图）。"""
    try:
        import re as _re

        dzi_path, files_dir = pyramid_files(fid)
        if not dzi_path.exists():
            return None
        text = dzi_path.read_text(encoding="utf-8", errors="replace")
        width = int(_re.search(r'Width="(\d+)"', text).group(1))
        height = int(_re.search(r'Height="(\d+)"', text).group(1))
        match_tile = _re.search(r'TileSize="(\d+)"', text)
        tile_size = int(match_tile.group(1)) if match_tile else TILE_SIZE
        max_level = max(0, math.ceil(math.log2(max(width, height))))
        level = max_level
        for lv in range(max_level, -1, -1):
            lw = max(1, math.ceil(width / (2 ** (max_level - lv))))
            lh = max(1, math.ceil(height / (2 ** (max_level - lv))))
            if max(lw, lh) <= 1400:
                level = lv
                break
        scale = 2 ** (max_level - level)
        lw = max(1, math.ceil(width / scale))
        lh = max(1, math.ceil(height / scale))
        cols = math.ceil(lw / tile_size)
        rows = math.ceil(lh / tile_size)
        tile = files_dir / str(level) / f"{cols // 2}_{rows // 2}.jpg"
        if not tile.exists():
            return None
        with Image.open(tile) as im:
            return im.convert("RGB").copy()
    except Exception:
        return None


def ensure_thumb(fid: str, entry: dict) -> Path:
    target = thumb_file(fid)
    if target.exists() and target.stat().st_size > 0:
        return target
    with THUMB_SEMAPHORE:
        if target.exists() and target.stat().st_size > 0:
            return target
        source = DATA_DIR / entry["rel"]
        avail = mem_available_mb()
        if avail is not None and avail < MEM_GUARD_MB:
            raise HTTPException(status_code=503, detail="NAS 内存紧张，暂不生成缩略图")
        tmp = target.parent / (target.stem + "_tmp.jpg")
        try:
            with tifffile.TiffFile(source) as tif:
                _page = tif.pages[0]
                _pixels = int(_page.imagewidth) * int(_page.imagelength)
                _photo = str(getattr(_page.photometric, "name", "")).upper()
        except Exception:
            _pixels, _photo = 0, "RGB"
        preview_jpg = PYRAMIDS_DIR / file_hash(fid) / f"{file_hash(fid)}_preview.jpg"
        if preview_jpg.exists():
            try:
                with Image.open(preview_jpg) as im:
                    _save_center_thumb(im.convert("RGB"), tmp)
                tmp.replace(target)
                return target
            except Exception:
                pass
        pyramid_img = _thumb_from_pyramid(fid, THUMB_SIZE)
        if pyramid_img is not None:
            _save_center_thumb(pyramid_img, tmp)
            tmp.replace(target)
            return target
        if _pixels > THUMB_VIPS_MAX_PIXELS:
            # 中/超大卷：直接从原图读中心一块（低内存、无需整卷解码）
            try:
                with tifffile.TiffFile(source) as tif:
                    _p = tif.pages[0]
                    _w, _h = int(_p.imagewidth), int(_p.imagelength)
            except Exception:
                _w, _h = 0, 0
            if _w and _h:
                reg_w = min(2400, _w)
                reg_h = min(1800, _h)
                x0 = max(0, (_w - reg_w) // 2)
                y0 = max(0, (_h - reg_h) // 2)
                region_img = read_region_plain_tiff(source, x0, y0, reg_w, reg_h)
                if region_img is not None:
                    region_img.thumbnail(
                        (THUMB_SIZE, int(THUMB_SIZE * 3 / 4)), Image.LANCZOS
                    )
                    region_img.save(tmp, "JPEG", quality=80)
                    tmp.replace(target)
                    return target
            raise HTTPException(
                status_code=503,
                detail="该卷为压缩格式，暂无法生成缩略图；点开可查看（或下载原图）",
            )
        if HAS_VIPS:
            image = pyvips.Image.new_from_file(str(source))
            w, h = image.width, image.height
            if w / max(1, h) > 4.0 / 3.0:
                cw, ch = int(h * 4.0 / 3.0), h
            else:
                cw, ch = w, int(w / (4.0 / 3.0))
            image = image.crop((w - cw) // 2, (h - ch) // 2, cw, ch)
            image = image.thumbnail_image(THUMB_SIZE, height=int(THUMB_SIZE * 3 / 4), size="down")
            image.jpegsave(str(tmp), Q=80)
        else:
            arr = load_page_array(source)
            img = array_to_pil(arr)
            del arr
            _save_center_thumb(img, tmp)
        tmp.replace(target)
        return target


def read_region_plain_tiff(path: Path, x: int, y: int, w: int, h: int):
    """从未压缩 TIFF 中直接读一个矩形区域（只读需要的字节），返回 PIL 图。

    适用于 uint8/uint16、CONTIG、未压缩 的扫描件；其他格式返回 None。
    """
    try:
        import numpy as _np

        with tifffile.TiffFile(path) as tif:
            page = tif.pages[0]
            if int(page.compression) != 1:
                return None
            if str(getattr(page.planarconfig, "name", "")) != "CONTIG":
                return None
            dtype = _np.dtype(page.dtype)
            if dtype not in (_np.dtype(_np.uint8), _np.dtype(_np.uint16)):
                return None
            samples = int(page.samplesperpixel or 1)
            if samples not in (1, 3, 4):
                return None
            photo = str(getattr(page.photometric, "name", "")).upper()
            if photo in ("YCBCR", "PALETTE", "CIELAB", "LAB"):
                return None
            width = int(page.imagewidth)
            height = int(page.imagelength)
            rowsperstrip = int(page.rowsperstrip or height)
            offsets = tuple(int(v) for v in page.dataoffsets)
            row_bytes = width * samples * dtype.itemsize

            x0 = max(0, min(int(x), width - 1))
            y0 = max(0, min(int(y), height - 1))
            x1 = max(x0 + 1, min(width, x0 + int(w)))
            y1 = max(y0 + 1, min(height, y0 + int(h)))
            item = dtype.itemsize
            read_bytes = (x1 - x0) * samples * item
            row_offset = x0 * samples * item
            out = _np.empty((y1 - y0, x1 - x0, samples), dtype=dtype)
            with open(path, "rb") as fh:
                for j in range(y0, y1):
                    strip = j // rowsperstrip
                    off = offsets[strip] + (j - strip * rowsperstrip) * row_bytes + row_offset
                    fh.seek(off)
                    buf = fh.read(read_bytes)
                    if len(buf) != read_bytes:
                        return None
                    out[j - y0] = _np.frombuffer(buf, dtype=dtype).reshape(x1 - x0, samples)

        if dtype.itemsize == 2:
            arr = _np.clip(out.astype(_np.float32) / 257.0, 0, 255).astype(_np.uint8)
        else:
            arr = out
        if samples == 1:
            return Image.fromarray(arr[..., 0], "L")
        if samples == 4 and photo in ("SEPARATED", "CMYK"):
            return Image.fromarray(arr, "CMYK").convert("RGB")
        return Image.fromarray(_np.ascontiguousarray(arr[..., :3]), "RGB")
    except Exception:
        return None


# ------------------------------------------------------------------ 应用

@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_bootstrap_admin()
    threading.Thread(target=scan_index, daemon=True).start()
    yield


app = FastAPI(title="敦煌画卷 · 高清查看", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/tiles", StaticFiles(directory=str(PYRAMIDS_DIR)), name="tiles")


# ------------------------------------------------------------------ 登录墙

def _session_sign(user: str, expire: int) -> str:
    message = f"{user}|{expire}".encode("utf-8")
    return hmac.new(AUTH_SECRET.encode("utf-8"), message, hashlib.sha256).hexdigest()


def make_session(user: str) -> str:
    expire = int(time.time()) + AUTH_SESSION_HOURS * 3600
    raw = f"{user}|{expire}|{_session_sign(user, expire)}".encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def load_users() -> dict:
    with USERS_LOCK:
        try:
            data = json.loads(USERS_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}


def save_users(users: dict) -> None:
    with USERS_LOCK:
        USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = USERS_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")
        os.chmod(tmp, 0o600)
        os.replace(tmp, USERS_FILE)


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return f"pbkdf2_sha256$200000${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt_hex, hash_hex = stored.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)
        )
        return hmac.compare_digest(digest.hex(), hash_hex)
    except Exception:
        return False


def ensure_bootstrap_admin() -> None:
    """用环境变量账号做初始管理员：仅当用户表里没有该账号时创建/补回。"""
    if not (AUTH_USER and AUTH_PASS and AUTH_SECRET):
        return
    users = load_users()
    if AUTH_USER not in users:
        users[AUTH_USER] = {
            "hash": hash_password(AUTH_PASS),
            "created": time.strftime("%Y-%m-%d %H:%M"),
            "admin": True,
            "bootstrap": True,
        }
        save_users(users)
        print(f"[auth] 已用环境变量初始化管理员账号 {AUTH_USER}", flush=True)


def authenticate(username: str, password: str) -> bool:
    record = load_users().get(username)
    if not record:
        # 用户名不存在时也做一次等价的哈希运算，避免通过响应时间枚举用户名
        verify_password(password, "pbkdf2_sha256$200000$00$00")
        return False
    return verify_password(password, str(record.get("hash", "")))


def is_admin(username: str) -> bool:
    if not username:
        return False
    return bool(load_users().get(username, {}).get("admin"))


def session_user(token: str) -> str:
    if not token:
        return ""
    try:
        padding = "=" * (-len(token) % 4)
        raw = base64.urlsafe_b64decode(token + padding).decode("utf-8")
        user, expire, signature = raw.rsplit("|", 2)
        if int(expire) < time.time():
            return ""
        if not hmac.compare_digest(signature, _session_sign(user, int(expire))):
            return ""
        if not is_admin(user) and user not in load_users():
            return ""
        return user
    except Exception:
        return ""


def check_session(token: str) -> bool:
    return bool(session_user(token))


def _csrf_token(token: str) -> str:
    return hmac.new(
        AUTH_SECRET.encode("utf-8"), ("csrf|" + token).encode("utf-8"), hashlib.sha256
    ).hexdigest()[:32]


LOGIN_ATTEMPTS: dict = {}
LOGIN_LOCK = threading.Lock()


def _client_ip(request: Request) -> str:
    """反向代理后面取真实客户端 IP：优先 X-Real-IP，其次 X-Forwarded-For 的最后一段。"""
    real = (request.headers.get("x-real-ip") or "").strip()
    if real:
        return real
    forwarded = request.headers.get("x-forwarded-for") or ""
    parts = [p.strip() for p in forwarded.split(",") if p.strip()]
    if parts:
        return parts[-1]
    return request.client.host if request.client else "unknown"


def _login_rate_ok(ip: str) -> bool:
    now = time.time()
    with LOGIN_LOCK:
        attempts = [t for t in LOGIN_ATTEMPTS.get(ip, []) if now - t < 600]
        LOGIN_ATTEMPTS[ip] = attempts
        return len(attempts) < 10


def _login_rate_record(ip: str) -> None:
    with LOGIN_LOCK:
        LOGIN_ATTEMPTS.setdefault(ip, []).append(time.time())


def _login_page(error: str = "", next_url: str = "/") -> str:
    safe_next = quote(next_url or "/", safe="")
    error_html = f'<div class="err">{error}</div>' if error else ""
    return """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>登录 · 敦煌画卷</title>
<style>
  body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
       background:#f5efe3;color:#2f2a24;font-family:"Noto Serif SC","Songti SC",serif}
  .box{width:min(92vw,360px);background:#fffdf8;border:1px solid #ddd2bf;border-radius:12px;
       box-shadow:0 4px 20px rgba(80,60,30,.12);padding:26px 24px}
  h1{font-size:20px;margin:0 0 4px;letter-spacing:2px}
  .sub{font-size:12px;color:#6b6154;margin-bottom:18px}
  label{display:block;font-size:13px;color:#6b6154;margin:12px 0 6px}
  input{width:100%;box-sizing:border-box;padding:9px 11px;border:1px solid #ddd2bf;border-radius:8px;
        background:#fffdf8;font-size:14px;font-family:inherit;color:#2f2a24;outline:none}
  input:focus{border-color:#b07a42}
  button{width:100%;margin-top:20px;padding:10px;border:0;border-radius:8px;background:#8a5a2b;
         color:#fff;font-size:15px;letter-spacing:2px;font-family:inherit;cursor:pointer}
  button:hover{background:#a06a35}
  .err{margin-top:14px;color:#b03a2e;font-size:13px;text-align:center}
  .foot{margin-top:16px;font-size:11px;color:#a2937f;text-align:center;line-height:1.6}
</style></head>
<body><div class="box">
  <h1>敦煌画卷</h1>
  <div class="sub">请登录后查看高清图像</div>
  <form method="post" action="/login">
    <input type="hidden" name="next" value="__NEXT__">
    <label>用户名</label><input name="username" autocomplete="username" autofocus>
    <label>密码</label><input name="password" type="password" autocomplete="current-password">
    <button type="submit">登 录</button>
  </form>
  __ERROR__
  <div class="foot">本服务仅授权用户可访问</div>
</div></body></html>""".replace("__NEXT__", safe_next).replace("__ERROR__", error_html)


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    if not AUTH_ENABLED:
        return await call_next(request)
    if path in ("/login", "/logout", "/favicon.ico") or path.startswith("/static/"):
        return await call_next(request)
    if check_session(request.cookies.get(SESSION_COOKIE, "")):
        return await call_next(request)
    if path.startswith(("/api/", "/tiles/", "/thumb/", "/file/", "/region/")):
        return JSONResponse({"detail": "未登录或会话已过期"}, status_code=401)
    next_url = path + (("?" + request.url.query) if request.url.query else "")
    return RedirectResponse("/login?next=" + quote(next_url, safe=""), status_code=303)


@app.get("/login")
def login_get(request: Request, next: str = "/"):
    if not AUTH_ENABLED:
        return RedirectResponse("/", status_code=303)
    if check_session(request.cookies.get(SESSION_COOKIE, "")):
        return RedirectResponse(next if next.startswith("/") else "/", status_code=303)
    return HTMLResponse(_login_page("", next), headers={"Cache-Control": "no-store"})


@app.post("/login")
async def login_post(request: Request):
    if not AUTH_ENABLED:
        return RedirectResponse("/", status_code=303)
    ip = _client_ip(request)
    raw = await request.body()
    try:
        values = parse_qs(raw.decode("utf-8", "replace"))
    except Exception:
        values = {}
    username = (values.get("username") or [""])[0]
    password = (values.get("password") or [""])[0]
    next_url = (values.get("next") or ["/"])[0] or "/"
    if not next_url.startswith("/"):
        next_url = "/"
    if not _login_rate_ok(ip):
        return HTMLResponse(_login_page("尝试次数过多，请 10 分钟后再试", next_url),
                            status_code=429, headers={"Cache-Control": "no-store"})
    if authenticate(username, password):
        response = RedirectResponse(next_url, status_code=303)
        secure = request.headers.get("x-forwarded-proto", request.url.scheme) == "https"
        response.set_cookie(
            SESSION_COOKIE, make_session(username),
            max_age=AUTH_SESSION_HOURS * 3600, httponly=True, samesite="lax",
            secure=secure, path="/",
        )
        return response
    _login_rate_record(ip)
    return HTMLResponse(_login_page("用户名或密码错误", next_url),
                        status_code=401, headers={"Cache-Control": "no-store"})


@app.get("/logout")
def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


# ------------------------------------------------------------------ 用户管理后台

def _admin_count(users: dict) -> int:
    return sum(1 for record in users.values() if record.get("admin"))


def _admin_page(token: str, current_user: str, message: str = "", error: str = "") -> str:
    csrf = _csrf_token(token)
    users = load_users()
    rows = []
    for name in sorted(users.keys(), key=lambda x: (not users[x].get("admin"), x.lower())):
        record = users[name]
        safe_name = _html.escape(name)
        created = _html.escape(str(record.get("created", "")))
        badge = ' <span class="badge">管理员</span>' if record.get("admin") else ""
        if record.get("admin"):
            toggle_label = "取消管理员"
        else:
            toggle_label = "设为管理员"
        ops = [
            f'<form method="post" action="/admin/toggle_admin">'
            f'<input type="hidden" name="csrf" value="{csrf}">'
            f'<input type="hidden" name="username" value="{safe_name}">'
            f'<button class="mini ghost" type="submit">{toggle_label}</button></form>',
            f'<form method="post" action="/admin/reset" onsubmit="return confirm(\'确定重置 {safe_name} 的密码？\')">'
            f'<input type="hidden" name="csrf" value="{csrf}">'
            f'<input type="hidden" name="username" value="{safe_name}">'
            f'<input type="password" name="password" placeholder="新密码（≥8位）" required>'
            f'<button class="mini" type="submit">重置密码</button></form>',
            f'<form method="post" action="/admin/delete" onsubmit="return confirm(\'确定删除用户 {safe_name}？\')">'
            f'<input type="hidden" name="csrf" value="{csrf}">'
            f'<input type="hidden" name="username" value="{safe_name}">'
            f'<button class="mini danger" type="submit">删除</button></form>',
        ]
        rows.append(
            f'<tr><td><b>{safe_name}</b>{badge}</td>'
            f'<td class="muted">{created} 创建</td>'
            f'<td class="ops">{"".join(ops)}</td></tr>'
        )
    msg_html = f'<div class="msg ok">{_html.escape(message)}</div>' if message else ""
    err_html = f'<div class="msg err">{_html.escape(error)}</div>' if error else ""
    return """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>用户管理 · 敦煌画卷</title>
<style>
  body{margin:0;background:#f5efe3;color:#2f2a24;font-family:"Noto Serif SC","Songti SC",serif;padding:24px 16px 60px}
  .wrap{max-width:900px;margin:0 auto}
  h1{font-size:20px;letter-spacing:2px;margin:0 0 4px}
  .sub{font-size:13px;color:#6b6154;margin-bottom:18px}
  .sub a{color:#8a5a2b;text-decoration:none}
  .card{background:#fffdf8;border:1px solid #ddd2bf;border-radius:12px;box-shadow:0 2px 10px rgba(80,60,30,.08);padding:16px 18px;margin-bottom:18px}
  table{width:100%;border-collapse:collapse;font-size:14px}
  th,td{text-align:left;padding:10px 6px;border-bottom:1px solid #eee4d3;vertical-align:middle}
  th{font-size:12px;color:#6b6154;font-weight:normal}
  .muted{color:#6b6154;font-size:12px}
  .badge{font-size:11px;background:#8a5a2b;color:#fff;border-radius:999px;padding:1px 8px;margin-left:6px}
  .ops form{display:inline-flex;gap:6px;margin:3px 6px 3px 0;align-items:center;flex-wrap:wrap}
  input[type=text],input[type=password]{padding:7px 9px;border:1px solid #ddd2bf;border-radius:7px;background:#fffdf8;font-family:inherit;font-size:13px;color:#2f2a24;outline:none}
  input[type=text]:focus,input[type=password]:focus{border-color:#b07a42}
  button{padding:7px 12px;border:0;border-radius:7px;background:#8a5a2b;color:#fff;font-family:inherit;font-size:13px;cursor:pointer}
  button:hover{background:#a06a35}
  button.mini{padding:5px 10px;font-size:12px}
  button.ghost{background:#fffdf8;color:#8a5a2b;border:1px solid #ddd2bf}
  button.ghost:hover{background:#f8f0e2}
  button.danger{background:#b03a2e}
  button.danger:hover{background:#c94a3d}
  .msg{padding:9px 12px;border-radius:8px;font-size:13px;margin-bottom:14px}
  .msg.ok{background:#eef6ea;color:#3d6b2f;border:1px solid #cfe3c4}
  .msg.err{background:#fbeeec;color:#b03a2e;border:1px solid #f0cfc9}
  .addform{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
  .check{font-size:13px;color:#6b6154;display:inline-flex;align-items:center;gap:4px}
  .foot{font-size:12px;color:#6b6154;margin-top:10px;line-height:1.7}
</style></head>
<body><div class="wrap">
  <h1>用户管理</h1>
  <div class="sub"><a href="/">← 返回画卷</a> · 当前账号：__CURRENT__</div>
  __MSG____ERR__
  <div class="card">
    <table>
      <tr><th>用户名</th><th>备注</th><th>操作（管理员/密码/删除）</th></tr>
      __ROWS__
    </table>
    <div class="foot">至少保留一个管理员；删除用户后其已登录会话立即失效。</div>
  </div>
  <div class="card">
    <h2 style="font-size:15px;margin:0 0 12px;color:#8a5a2b">新增用户</h2>
    <form class="addform" method="post" action="/admin/add">
      <input type="hidden" name="csrf" value="__CSRF__">
      <input type="text" name="username" placeholder="用户名（字母/数字/_-，2-32位）" required>
      <input type="password" name="password" placeholder="密码（至少 8 位）" required>
      <input type="password" name="confirm" placeholder="再输一次密码" required>
      <label class="check"><input type="checkbox" name="admin" value="1"> 设为管理员</label>
      <button type="submit">添加用户</button>
    </form>
  </div>
</div></body></html>""".replace("__CURRENT__", _html.escape(current_user)).replace(
        "__MSG__", msg_html
    ).replace("__ERR__", err_html).replace("__ROWS__", "".join(rows)).replace("__CSRF__", csrf)


def _admin_guard(request: Request):
    user = session_user(request.cookies.get(SESSION_COOKIE, ""))
    if not user:
        return None, RedirectResponse("/login?next=%2Fadmin", status_code=303)
    if not is_admin(user):
        return None, HTMLResponse(
            "<html><body style='background:#f5efe3;font-family:serif;padding:40px'>"
            "<h2>403 · 仅管理员可访问</h2><p><a href='/'>返回画卷</a></p></body></html>",
            status_code=403,
        )
    return user, None


@app.get("/admin")
def admin_page(request: Request, msg: str = "", err: str = ""):
    user, denial = _admin_guard(request)
    if denial is not None:
        return denial
    token = request.cookies.get(SESSION_COOKIE, "")
    return HTMLResponse(_admin_page(token, user, msg, err), headers={"Cache-Control": "no-store"})


def _admin_csrf_ok(request: Request, values: dict) -> bool:
    token = request.cookies.get(SESSION_COOKIE, "")
    supplied = (values.get("csrf") or [""])[0]
    return hmac.compare_digest(supplied, _csrf_token(token))


def _read_form(raw: bytes) -> dict:
    try:
        return parse_qs(raw.decode("utf-8", "replace"))
    except Exception:
        return {}


@app.post("/admin/add")
async def admin_add(request: Request):
    user, denial = _admin_guard(request)
    if denial is not None:
        return denial
    values = _read_form(await request.body())
    if not _admin_csrf_ok(request, values):
        return RedirectResponse("/admin?err=CSRF%20%E6%A0%A1%E9%AA%8C%E5%A4%B1%E8%B4%A5", status_code=303)
    name = (values.get("username") or [""])[0].strip()
    password = (values.get("password") or [""])[0]
    confirm = (values.get("confirm") or [""])[0]
    as_admin = (values.get("admin") or [""])[0] == "1"
    if not re.fullmatch(r"[A-Za-z0-9_.-]{2,32}", name):
        return RedirectResponse("/admin?err=" + quote("用户名只能包含字母/数字/_-.，2-32 位"), status_code=303)
    if len(password) < 8:
        return RedirectResponse("/admin?err=" + quote("密码至少 8 位"), status_code=303)
    if password != confirm:
        return RedirectResponse("/admin?err=" + quote("两次输入的密码不一致"), status_code=303)
    users = load_users()
    if name in users:
        return RedirectResponse("/admin?err=" + quote("用户已存在，可在列表里重置密码"), status_code=303)
    users[name] = {
        "hash": hash_password(password),
        "created": time.strftime("%Y-%m-%d %H:%M"),
        "admin": as_admin,
    }
    save_users(users)
    print(f"[admin] {user} 新增用户 {name}（admin={as_admin}）", flush=True)
    return RedirectResponse("/admin?msg=" + quote(f"已添加用户 {name}"), status_code=303)


@app.post("/admin/toggle_admin")
async def admin_toggle(request: Request):
    user, denial = _admin_guard(request)
    if denial is not None:
        return denial
    values = _read_form(await request.body())
    if not _admin_csrf_ok(request, values):
        return RedirectResponse("/admin?err=CSRF%20%E6%A0%A1%E9%AA%8C%E5%A4%B1%E8%B4%A5", status_code=303)
    name = (values.get("username") or [""])[0]
    users = load_users()
    if name not in users:
        return RedirectResponse("/admin?err=" + quote("用户不存在"), status_code=303)
    becoming_admin = not bool(users[name].get("admin"))
    if not becoming_admin and _admin_count(users) <= 1:
        return RedirectResponse("/admin?err=" + quote("必须至少保留一个管理员"), status_code=303)
    users[name]["admin"] = becoming_admin
    save_users(users)
    print(f"[admin] {user} 将 {name} 设为管理员={becoming_admin}", flush=True)
    action = "设为管理员" if becoming_admin else "取消管理员"
    return RedirectResponse("/admin?msg=" + quote(f"已把 {name} {action}"), status_code=303)


@app.post("/admin/delete")
async def admin_delete(request: Request):
    user, denial = _admin_guard(request)
    if denial is not None:
        return denial
    values = _read_form(await request.body())
    if not _admin_csrf_ok(request, values):
        return RedirectResponse("/admin?err=CSRF%20%E6%A0%A1%E9%AA%8C%E5%A4%B1%E8%B4%A5", status_code=303)
    name = (values.get("username") or [""])[0]
    users = load_users()
    if name not in users:
        return RedirectResponse("/admin?err=" + quote("用户不存在"), status_code=303)
    if users[name].get("admin") and _admin_count(users) <= 1:
        return RedirectResponse("/admin?err=" + quote("必须至少保留一个管理员"), status_code=303)
    del users[name]
    save_users(users)
    print(f"[admin] {user} 删除用户 {name}", flush=True)
    return RedirectResponse("/admin?msg=" + quote(f"已删除用户 {name}"), status_code=303)


@app.post("/admin/reset")
async def admin_reset(request: Request):
    user, denial = _admin_guard(request)
    if denial is not None:
        return denial
    values = _read_form(await request.body())
    if not _admin_csrf_ok(request, values):
        return RedirectResponse("/admin?err=CSRF%20%E6%A0%A1%E9%AA%8C%E5%A4%B1%E8%B4%A5", status_code=303)
    name = (values.get("username") or [""])[0]
    password = (values.get("password") or [""])[0]
    if len(password) < 8:
        return RedirectResponse("/admin?err=" + quote("密码至少 8 位"), status_code=303)
    users = load_users()
    if name not in users:
        return RedirectResponse("/admin?err=" + quote("用户不存在"), status_code=303)
    users[name]["hash"] = hash_password(password)
    save_users(users)
    print(f"[admin] {user} 重置用户 {name} 的密码", flush=True)
    return RedirectResponse("/admin?msg=" + quote(f"已重置 {name} 的密码"), status_code=303)


@app.get("/")
def page_gallery():
    return FileResponse(STATIC_DIR / "gallery.html", media_type="text/html; charset=utf-8")


@app.get("/view/{item_id}")
def page_viewer(item_id: str):
    return FileResponse(STATIC_DIR / "viewer.html", media_type="text/html; charset=utf-8")


@app.get("/api/health")
def api_health():
    return JSONResponse(
        {
            "ok": True,
            "data_dir": str(DATA_DIR),
            "data_exists": DATA_DIR.exists(),
            "vips": HAS_VIPS,
            "pyvips": (pyvips.__version__ if HAS_VIPS else None),
            "mem_available_mb": round(mem_available_mb() or 0, 1),
            "mem_guard_mb": MEM_GUARD_MB,
            "full_dzi_max_pixels": FULL_DZI_MAX_PIXELS,
            "preview_long_edge": PREVIEW_LONG_EDGE,
        }
    )


@app.get("/api/me")
def api_me(request: Request):
    user = session_user(request.cookies.get(SESSION_COOKIE, ""))
    return JSONResponse({"user": user, "is_admin": is_admin(user)})


@app.get("/api/index")
def api_index():
    return JSONResponse(to_json_index())


@app.post("/api/rescan")
def api_rescan():
    if INDEX["status"] == "scanning":
        return {"ok": False, "message": "正在扫描中"}
    threading.Thread(target=scan_index, daemon=True).start()
    return {"ok": True}


# 放大镜小地图：整卷总览小图缓存（每张几十 KB）
OVERVIEW_CACHE: dict = {}
OVERVIEW_ORDER: list = []
OVERVIEW_MAX = 20
OVERVIEW_LOCK = threading.Lock()


def _overview_from_dzi(fid: str):
    """从 DZI 里挑一个合适的小层级拼出整卷总览（几张小图块，很快）。"""
    try:
        import re as _re

        dzi_path, files_dir = pyramid_files(fid)
        if not dzi_path.exists():
            return None
        xml_text = dzi_path.read_text(encoding="utf-8", errors="replace")
        match_w = _re.search(r'Width="(\d+)"', xml_text)
        match_h = _re.search(r'Height="(\d+)"', xml_text)
        if not match_w or not match_h:
            return None
        width = int(match_w.group(1))
        height = int(match_h.group(1))
        max_level = max(0, math.ceil(math.log2(max(width, height))))
        target = 900
        level = max_level
        while level > 0:
            lw = math.ceil(width / 2 ** (max_level - level))
            if lw <= target:
                break
            level -= 1
        lw = math.ceil(width / 2 ** (max_level - level))
        lh = math.ceil(height / 2 ** (max_level - level))
        cols = math.ceil(lw / TILE_SIZE)
        rows = math.ceil(lh / TILE_SIZE)
        level_dir = files_dir / str(level)
        if not level_dir.exists():
            return None
        canvas = Image.new("RGB", (cols * TILE_SIZE, rows * TILE_SIZE), (27, 26, 24))
        for row in range(rows):
            for col in range(cols):
                tile_path = level_dir / f"{col}_{row}.jpg"
                if not tile_path.exists():
                    return None
                with Image.open(tile_path) as tile:
                    canvas.paste(tile.convert("RGB"), (col * TILE_SIZE, row * TILE_SIZE))
        return canvas.crop((0, 0, lw, lh))
    except Exception:
        return None


@app.get("/api/overview/{fid}")
def api_overview(fid: str):
    """整卷总览小图（放大镜右下角参照图用）。"""
    entry = FILE_BY_ID.get(fid)
    if entry is None:
        raise HTTPException(status_code=404, detail="找不到文件")
    with OVERVIEW_LOCK:
        cached = OVERVIEW_CACHE.get(fid)
        if cached is not None:
            return Response(content=cached, media_type="image/jpeg",
                            headers={"Cache-Control": "private, max-age=3600"})
    img = None
    preview_jpg = PYRAMIDS_DIR / file_hash(fid) / f"{file_hash(fid)}_preview.jpg"
    if preview_jpg.exists():
        try:
            with Image.open(preview_jpg) as im:
                img = im.convert("RGB").copy()
        except Exception:
            img = None
    if img is None:
        img = _overview_from_dzi(fid)
    if img is None:
        try:
            img = _fast_thumb_plain_tiff(DATA_DIR / entry["rel"], 600)
        except Exception:
            img = None
    if img is None:
        raise HTTPException(status_code=415, detail="该卷暂无法生成总览图")
    img.thumbnail((640, 640), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=80)
    data = buf.getvalue()
    with OVERVIEW_LOCK:
        if fid not in OVERVIEW_CACHE:
            OVERVIEW_CACHE[fid] = data
            OVERVIEW_ORDER.append(fid)
            while len(OVERVIEW_ORDER) > OVERVIEW_MAX:
                old_fid = OVERVIEW_ORDER.pop(0)
                OVERVIEW_CACHE.pop(old_fid, None)
    return Response(content=data, media_type="image/jpeg",
                    headers={"Cache-Control": "private, max-age=3600"})


# 放大镜：优先用已生成的 DZI 图块拼区域；记录每卷 DZI 是否全分辨率
DZI_FULL_CACHE: dict = {}
DZI_FULL_LOCK = threading.Lock()


def _dzi_full_res(fid: str, source: Path) -> bool:
    """该卷已生成的 DZI 是否为原分辨率（否则为预览分辨率）。"""
    with DZI_FULL_LOCK:
        cached = DZI_FULL_CACHE.get(fid)
    if cached is not None:
        return cached
    result = False
    try:
        dzi_path, _files_dir = pyramid_files(fid)
        if dzi_path.exists():
            result = not dzi_preview_flag(dzi_path, source)
    except Exception:
        result = False
    with DZI_FULL_LOCK:
        if len(DZI_FULL_CACHE) > 512:
            DZI_FULL_CACHE.clear()
        DZI_FULL_CACHE[fid] = result
    return result


def _region_from_dzi(fid: str, x: int, y: int, w: int, h: int):
    """用 DZI 最高层级（原分辨率）的 512px 图块拼出请求区域，返回 PIL 图或 None。"""
    try:
        import re as _re

        dzi_path, files_dir = pyramid_files(fid)
        if not dzi_path.exists() or not files_dir.exists():
            return None
        xml_text = dzi_path.read_text(encoding="utf-8", errors="replace")
        match_w = _re.search(r'Width="(\d+)"', xml_text)
        match_h = _re.search(r'Height="(\d+)"', xml_text)
        if not match_w or not match_h:
            return None
        width = int(match_w.group(1))
        height = int(match_h.group(1))
        if x + w > width or y + h > height:
            return None
        match_tile = _re.search(r'TileSize="(\d+)"', xml_text)
        tile_size = int(match_tile.group(1)) if match_tile else TILE_SIZE
        max_level = max(0, math.ceil(math.log2(max(width, height))))
        level_dir = files_dir / str(max_level)
        if not level_dir.exists():
            return None
        col0 = x // tile_size
        col1 = (x + w - 1) // tile_size
        row0 = y // tile_size
        row1 = (y + h - 1) // tile_size
        canvas = Image.new(
            "RGB",
            ((col1 - col0 + 1) * tile_size, (row1 - row0 + 1) * tile_size),
            (27, 26, 24),
        )
        for row in range(row0, row1 + 1):
            for col in range(col0, col1 + 1):
                tile_path = level_dir / f"{col}_{row}.jpg"
                if not tile_path.exists():
                    return None
                with Image.open(tile_path) as tile:
                    canvas.paste(tile.convert("RGB"), ((col - col0) * tile_size, (row - row0) * tile_size))
        left = x - col0 * tile_size
        top = y - row0 * tile_size
        return canvas.crop((left, top, left + w, top + h))
    except Exception:
        return None


# 放大镜区域缓存（只存小 JPEG，最多 24 张 / 24MB，不占整卷内存）
REGION_CACHE: dict = {}
REGION_CACHE_ORDER: list = []
REGION_CACHE_BYTES = [0]
REGION_CACHE_MAX_ITEMS = 24
REGION_CACHE_MAX_BYTES = 24 * 1024 * 1024
REGION_CACHE_LOCK = threading.Lock()
REGION_SEM = threading.BoundedSemaphore(2)


@app.get("/api/region/{fid}")
def api_region(fid: str, x: int, y: int, w: int = 2400, h: int = 1600):
    """局部放大镜：直接从原图读取一块高清区域（每次只读几 MB，可拖动平移）。"""
    entry = FILE_BY_ID.get(fid)
    if entry is None:
        raise HTTPException(status_code=404, detail="找不到文件")
    avail = mem_available_mb()
    if avail is not None and avail < MEM_GUARD_MB:
        raise HTTPException(status_code=503, detail="NAS 内存紧张，稍后再试")
    w = max(64, min(int(w), 4000))
    h = max(64, min(int(h), 4000))
    if w * h > 12_000_000:
        raise HTTPException(status_code=400, detail="取图范围太大，请缩小")
    key = (fid, int(x), int(y), w, h)
    with REGION_CACHE_LOCK:
        cached = REGION_CACHE.get(key)
        if cached is not None:
            REGION_CACHE_ORDER.remove(key)
            REGION_CACHE_ORDER.append(key)
            return Response(content=cached, media_type="image/jpeg",
                            headers={"Cache-Control": "private, max-age=3600"})
    if not REGION_SEM.acquire(timeout=20):
        raise HTTPException(status_code=503, detail="取图繁忙，请稍后再试")
    try:
        source = DATA_DIR / entry["rel"]
        img = None
        if _dzi_full_res(fid, source):
            img = _region_from_dzi(fid, int(x), int(y), w, h)
        if img is None:
            img = read_region_plain_tiff(source, int(x), int(y), w, h)
    finally:
        REGION_SEM.release()
    if img is None:
        raise HTTPException(status_code=415, detail="该卷为压缩/特殊格式，暂不支持局部高清读取")
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=88, subsampling=2)
    data = buf.getvalue()
    with REGION_CACHE_LOCK:
        if key not in REGION_CACHE:
            REGION_CACHE[key] = data
            REGION_CACHE_ORDER.append(key)
            REGION_CACHE_BYTES[0] += len(data)
            while REGION_CACHE_ORDER and (
                len(REGION_CACHE_ORDER) > REGION_CACHE_MAX_ITEMS
                or REGION_CACHE_BYTES[0] > REGION_CACHE_MAX_BYTES
            ):
                old_key = REGION_CACHE_ORDER.pop(0)
                old_data = REGION_CACHE.pop(old_key, None)
                if old_data:
                    REGION_CACHE_BYTES[0] -= len(old_data)
    return Response(
        content=data,
        media_type="image/jpeg",
        headers={"Cache-Control": "private, max-age=3600"},
    )


@app.get("/api/item/{item_id}")
def api_item(item_id: str):
    item = ITEM_BY_ID.get(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="找不到这一卷（索引可能尚未完成）")
    item_dir = DATA_DIR / decode_id(item_id)
    files = []
    for entry in item["files"]:
        path = DATA_DIR / entry["rel"]
        meta = {"id": entry["id"], "name": entry["name"], "size": entry["size"],
                "size_text": human_size(entry["size"])}
        meta.update(read_meta(path))
        files.append(meta)
    notes = []
    try:
        for txt in sorted(item_dir.glob("*.txt"), key=lambda p: order_key(p.name)):
            raw = txt.read_bytes()
            text = None
            for enc in ("utf-8-sig", "gb18030", "utf-16", "latin-1"):
                try:
                    text = raw.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
            notes.append({"name": txt.name, "text": (text or raw.decode("utf-8", "replace"))[:8000]})
    except Exception:
        pass
    return {
        "id": item_id, "title": item["title"], "category": item["category"],
        "files": files, "notes": notes,
    }


@app.get("/thumb/{fid}")
def api_thumb(fid: str):
    entry = FILE_BY_ID.get(fid)
    if entry is None:
        raise HTTPException(status_code=404, detail="找不到文件")
    try:
        target = ensure_thumb(fid, entry)
    except HTTPException:
        raise
    except Exception as exc:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"缩略图生成失败: {exc}")
    return FileResponse(target, media_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=604800"})


@app.post("/api/pyramid/{fid}")
def api_start_pyramid(fid: str):
    entry = FILE_BY_ID.get(fid)
    if entry is None:
        raise HTTPException(status_code=404, detail="找不到文件")
    dzi_path, _ = pyramid_files(fid)
    if dzi_path.exists():
        set_pyr_state(fid, "ready", 100,
                      preview_only=dzi_preview_flag(dzi_path, DATA_DIR / entry["rel"]))
        return get_pyr_state(fid)
    state = get_pyr_state(fid)
    if state["state"] != "generating":
        threading.Thread(target=generate_worker, args=(fid, entry), daemon=True).start()
        set_pyr_state(fid, "queued", 0)
    return get_pyr_state(fid)


@app.get("/api/pyramid/{fid}/status")
def api_pyramid_status(fid: str):
    if fid not in FILE_BY_ID:
        raise HTTPException(status_code=404, detail="找不到文件")
    dzi_path, _ = pyramid_files(fid)
    if dzi_path.exists():
        entry = FILE_BY_ID[fid]
        set_pyr_state(fid, "ready", 100,
                      preview_only=dzi_preview_flag(dzi_path, DATA_DIR / entry["rel"]))
    return get_pyr_state(fid)


@app.get("/file/{fid}")
def api_file(fid: str):
    entry = FILE_BY_ID.get(fid)
    if entry is None:
        raise HTTPException(status_code=404, detail="找不到文件")
    path = DATA_DIR / entry["rel"]
    if not path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(path, filename=path.name, media_type="image/tiff")


# ==================================================================== 手动拼接工作台
STITCH_PLANS_DIR = CACHE_DIR / "stitch_plans"
STITCH_PREVIEW_DIR = CACHE_DIR / "stitch_previews"
STITCH_OUT_DIR = CACHE_DIR / "stitch_out"
STITCH_PLANS_DIR.mkdir(parents=True, exist_ok=True)
STITCH_PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
STITCH_OUT_DIR.mkdir(parents=True, exist_ok=True)
STITCH_BUILDS: dict = {}
STITCH_BUILDS_LOCK = threading.Lock()
STITCH_SEMAPHORE = threading.Semaphore(1)


def _stitch_item_or_404(item_id: str) -> dict:
    item = ITEM_BY_ID.get(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="找不到这一卷（索引可能尚未完成）")
    return item


def _stitch_plan_path(item_id: str) -> Path:
    return STITCH_PLANS_DIR / (hashlib.sha1(("stitch:" + item_id).encode()).hexdigest()[:16] + ".json")


def _stitch_load_plan(item_id: str):
    path = _stitch_plan_path(item_id)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def _stitch_save_plan(item_id: str, plan: dict) -> None:
    path = _stitch_plan_path(item_id)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def _hex_to_rgb(value: str):
    value = (value or "#ffffff").strip().lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    try:
        return [int(value[i:i + 2], 16) for i in (0, 2, 4)]
    except Exception:
        return [255, 255, 255]


@app.get("/stitch/{item_id}")
def page_stitch(item_id: str):
    return FileResponse(STATIC_DIR / "stitch.html", media_type="text/html; charset=utf-8")


@app.get("/api/stitch/{item_id}/info")
def api_stitch_info(item_id: str):
    item = _stitch_item_or_404(item_id)
    files = []
    for entry in item["files"]:
        path = DATA_DIR / entry["rel"]
        if not path.exists():
            continue
        meta = read_meta(path)
        files.append({
            "id": entry["id"], "name": entry["name"], "size": entry["size"],
            "width": int(meta.get("width") or 0), "height": int(meta.get("height") or 0),
            "preview": "/api/stitch/piece/" + entry["id"],
        })
    return {"id": item_id, "title": item["title"], "category": item["category"],
            "files": files, "plan": _stitch_load_plan(item_id)}


@app.get("/api/stitch/piece/{fid}")
def api_stitch_piece(fid: str, w: int = 1600):
    entry = FILE_BY_ID.get(fid)
    if entry is None:
        raise HTTPException(status_code=404, detail="找不到文件")
    w = max(200, min(2600, int(w)))
    key = hashlib.sha1(("piece:" + fid + ":" + str(w)).encode()).hexdigest()[:16]
    target = STITCH_PREVIEW_DIR / f"{key}_{w}.jpg"
    if target.exists() and target.stat().st_size > 0:
        return FileResponse(target, media_type="image/jpeg",
                            headers={"Cache-Control": "private, max-age=86400"})
    source = DATA_DIR / entry["rel"]
    if not source.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    avail = mem_available_mb()
    if avail is not None and avail < MEM_GUARD_MB:
        raise HTTPException(status_code=503, detail="NAS 内存紧张，稍后再试")
    tmp = target.with_suffix(".tmp.jpg")
    try:
        if HAS_VIPS:
            im = pyvips.Image.new_from_file(str(source), access="sequential")
            th = im.thumbnail_image(w)
            th.jpegsave(str(tmp), Q=86)
        else:
            with Image.open(source) as im:
                im = im.convert("RGB")
                im.thumbnail((w, max(1, int(w * 4))))
                im.save(tmp, "JPEG", quality=86)
        tmp.replace(target)
    except Exception as exc:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise HTTPException(status_code=500, detail=f"预览生成失败: {exc}")
    return FileResponse(target, media_type="image/jpeg",
                        headers={"Cache-Control": "private, max-age=86400"})


@app.post("/api/stitch/{item_id}/plan")
async def api_stitch_plan(item_id: str, request: Request):
    item = _stitch_item_or_404(item_id)
    raw = await request.body()
    try:
        plan = json.loads(raw.decode("utf-8", "replace"))
    except Exception:
        raise HTTPException(status_code=400, detail="方案格式错误")
    ids = {entry["id"] for entry in item["files"]}
    pieces = plan.get("pieces") or []
    if not pieces:
        raise HTTPException(status_code=400, detail="方案为空")
    for piece in pieces:
        if piece.get("id") not in ids:
            raise HTTPException(status_code=400, detail="方案里包含不属于这一卷的文件")
    _stitch_save_plan(item_id, plan)
    return {"ok": True}


def _pyramid_state_path() -> Path:
    return CACHE_DIR / "pyramid_build_state.json"


def _stitch_remove_tiles(rel: str) -> None:
    try:
        fid = encode_id(rel)
        h = file_hash(fid)
        folder = PYRAMIDS_DIR / h
        if folder.exists():
            import shutil
            shutil.rmtree(folder, ignore_errors=True)
        thumb = THUMBS_DIR / (h + ".jpg")
        if thumb.exists():
            try:
                thumb.unlink()
            except OSError:
                pass
        set_pyr_state(fid, "missing", 0)
    except Exception:
        traceback.print_exc()


def _stitch_queue_pyramid(rel: str) -> None:
    try:
        path = _pyramid_state_path()
        state = {}
        if path.exists():
            try:
                state = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                state = {}
        state.setdefault("done", {})
        state.setdefault("failed", {})
        state.setdefault("attempts", {})
        state.setdefault("deferred", {})
        state["done"].pop(rel, None)
        state["failed"].pop(rel, None)
        state["attempts"].pop(rel, None)
        state["deferred"][rel] = {"ts": 0}
        path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    except Exception:
        traceback.print_exc()


def _stitch_build_worker(item_id: str, item: dict, plan: dict) -> None:
    with STITCH_SEMAPHORE:
        with STITCH_BUILDS_LOCK:
            STITCH_BUILDS[item_id] = {"state": "building", "percent": 0,
                                      "message": "准备中…", "output": None, "error": None}
        try:
            if not HAS_VIPS:
                raise RuntimeError("服务未启用 pyvips，无法拼接")
            pieces = [p for p in (plan.get("pieces") or []) if p.get("enabled", True)]
            if not pieces:
                raise RuntimeError("没有勾选任何参与拼接的分片")
            bg_rgb = _hex_to_rgb(plan.get("bg") or "#ffffff")
            geo = []
            prev_end = 0
            x = 0
            max_bottom = 0
            min_top = 0
            for i, piece in enumerate(pieces):
                entry = FILE_BY_ID.get(piece["id"])
                if entry is None:
                    raise RuntimeError(f"文件不在索引中: {piece['id'][:16]}")
                src_path = DATA_DIR / entry["rel"]
                if not src_path.exists():
                    raise RuntimeError(f"文件不存在（索引可能过期，请重新扫描）: {entry['name']}")
                meta = read_meta(src_path)
                w = int(meta.get("width") or 0)
                h = int(meta.get("height") or 0)
                if w <= 0 or h <= 0:
                    raise RuntimeError(f"无法读取尺寸: {entry['name']}")
                angle = float(piece.get("angle") or 0)
                if angle < -45 or angle > 45:
                    angle = max(-45.0, min(45.0, angle))
                if abs(angle) > 1e-6:
                    rad = math.radians(angle)
                    ca, sa = abs(math.cos(rad)), abs(math.sin(rad))
                    rw = int(math.ceil(w * ca + h * sa))
                    rh = int(math.ceil(w * sa + h * ca))
                else:
                    rw, rh = w, h
                want_x = int(piece.get("x") or 0)
                trim = 0
                gap = 0
                if i == 0:
                    place = 0
                elif want_x < prev_end:
                    trim = min(rw - 1, prev_end - want_x)
                    place = prev_end
                else:
                    gap = want_x - prev_end
                    place = want_x
                trimr = max(0, min(rw - trim - 1, int(piece.get("trimr") or 0)))
                y = int(piece.get("y") or 0)
                tw = rw - trim - trimr
                if tw <= 0:
                    raise RuntimeError(f"裁剪过多: {entry['name']}")
                geo.append({"entry": entry, "w": w, "h": h, "angle": angle, "rw": rw, "rh": rh,
                            "trim": trim, "trimr": trimr, "tw": tw, "x": place, "y": y, "gap": gap})
                prev_end = place + tw
                x = prev_end
                max_bottom = max(max_bottom, y + rh)
                min_top = min(min_top, y)
                with STITCH_BUILDS_LOCK:
                    STITCH_BUILDS[item_id]["percent"] = int(10 * (i + 1) / len(pieces))
            shift = -min_top if min_top < 0 else 0
            canvas_h = max_bottom + shift
            canvas_w = x
            if canvas_h <= 0 or canvas_w <= 0:
                raise RuntimeError("画布尺寸无效")
            parts = []
            prev_end = 0
            for i, g in enumerate(geo):
                im = pyvips.Image.new_from_file(str(DATA_DIR / g["entry"]["rel"]), access=("random" if abs(g["angle"]) > 1e-6 else "sequential"))
                if abs(g["angle"]) > 1e-6:
                    rad = math.radians(abs(g["angle"]))
                    pad = int(math.ceil(max(g["w"], g["h"]) * math.sin(rad) * math.cos(rad))) + 8
                    padded = im.embed(pad, pad, g["w"] + 2 * pad, g["h"] + 2 * pad, extend="copy")
                    rot = padded.rotate(g["angle"], background=bg_rgb)
                    # 裁回原图的旋转包围盒（以中心对齐），保证不裁掉原图内容
                    x0 = max(0, (rot.width - g["rw"]) // 2)
                    y0 = max(0, (rot.height - g["rh"]) // 2)
                    im = rot.crop(x0, y0, min(g["rw"], rot.width - x0), min(g["rh"], rot.height - y0))
                    g["rw"], g["rh"] = im.width, im.height
                    max_keep = max(1, g["rw"] - min(g["trim"], g["rw"] - 1))
                    g["trimr"] = min(g["trimr"], max_keep - 1) if max_keep > 1 else 0
                    g["tw"] = max(1, g["rw"] - min(g["trim"], g["rw"] - 1) - g["trimr"])
                if g["trim"] or g["trimr"]:
                    im = im.crop(min(g["trim"], im.width - 1), 0, g["tw"], im.height)
                piece_h = im.height
                top = g["y"] + shift
                bottom = canvas_h - top - piece_h
                if top < 0:
                    cut = -top
                    im = im.crop(0, cut, im.width, im.height - cut)
                    top = 0
                if bottom < 0:
                    cut = -bottom
                    im = im.crop(0, 0, im.width, im.height - cut)
                    bottom = 0
                if top > 0 or bottom > 0:
                    im = im.embed(0, top, im.width, canvas_h, extend="copy")
                if g["gap"] > 0:
                    gap_img = pyvips.Image.black(g["gap"], canvas_h, bands=3)
                    gap_img = gap_img.linear(1, 255).colourspace("srgb")
                    parts.append(gap_img)
                parts.append(im)
                with STITCH_BUILDS_LOCK:
                    STITCH_BUILDS[item_id]["percent"] = 10 + int(55 * (i + 1) / len(geo))
            canvas = parts[0]
            for part in parts[1:]:
                canvas = canvas.join(part, "horizontal")
            rel = (decode_id(item_id).rstrip("/") + "/合并长卷.tif")
            out_path = DATA_DIR / rel
            tmp_out = out_path.parent / (".合并长卷_building_" + str(int(time.time())) + ".tif")
            canvas.tiffsave(str(tmp_out), compression="none", bigtiff=True, strip=True)
            if tmp_out.stat().st_size <= 0:
                raise RuntimeError("输出文件为空")
            tmp_out.replace(out_path)
            with STITCH_BUILDS_LOCK:
                STITCH_BUILDS[item_id]["percent"] = 75
                STITCH_BUILDS[item_id]["message"] = "整卷已生成，正在重建图块…"
            _stitch_remove_tiles(rel)
            _stitch_queue_pyramid(rel)
            # 等待图块重建完成（最多 40 分钟）
            deadline = time.time() + 2400
            while time.time() < deadline:
                try:
                    st_path = _pyramid_state_path()
                    st = json.loads(st_path.read_text(encoding="utf-8")) if st_path.exists() else {}
                except Exception:
                    st = {}
                if rel in st.get("done", {}):
                    break
                time.sleep(6)
            while INDEX.get("status") == "scanning":
                time.sleep(2)
            scan_index()
            with STITCH_BUILDS_LOCK:
                STITCH_BUILDS[item_id] = {"state": "done", "percent": 100,
                                          "message": "已生成，卷目录与图块已更新",
                                          "output": rel, "error": None}
        except Exception as exc:
            traceback.print_exc()
            with STITCH_BUILDS_LOCK:
                STITCH_BUILDS[item_id] = {"state": "error", "percent": 0,
                                          "message": "生成失败", "output": None, "error": str(exc)}


@app.post("/api/stitch/{item_id}/build")
async def api_stitch_build(item_id: str, request: Request):
    item = _stitch_item_or_404(item_id)
    raw = await request.body()
    try:
        plan = json.loads(raw.decode("utf-8", "replace"))
    except Exception:
        raise HTTPException(status_code=400, detail="方案格式错误")
    if not (plan.get("pieces") or []):
        raise HTTPException(status_code=400, detail="方案为空")
    ids = {entry["id"] for entry in item["files"]}
    for piece in plan["pieces"]:
        if piece.get("id") not in ids:
            raise HTTPException(status_code=400, detail="方案里包含不属于这一卷的文件")
    _stitch_save_plan(item_id, plan)
    with STITCH_BUILDS_LOCK:
        current = STITCH_BUILDS.get(item_id)
    if current and current.get("state") == "building":
        return {"ok": False, "message": "正在生成中，请稍候"}
    threading.Thread(target=_stitch_build_worker, args=(item_id, item, plan), daemon=True).start()
    return {"ok": True}


@app.get("/api/stitch/{item_id}/build/status")
def api_stitch_build_status(item_id: str):
    with STITCH_BUILDS_LOCK:
        return dict(STITCH_BUILDS.get(item_id) or {"state": "idle", "percent": 0,
                                                   "message": "", "output": None, "error": None})
