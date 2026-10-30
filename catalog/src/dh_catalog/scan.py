"""只读文件系统入口：清单与文件头事实，不访问 v0 cache，不解码像素。"""

import os
import struct
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path, PurePosixPath
from typing import Literal

import tifffile
from PIL import Image

from .rules import NLC_ATTACHMENTS, NLC_CATEGORY, PSB_COLOR_MODES, TIFF_EXTENSIONS

RootName = Literal["data", "backup"]
FileKind = Literal["tiff", "psb", "jpg", "text", "manifest", "report", "index"]
FactValue = int | float | str | tuple[int, ...] | tuple[float, float, str] | None
FACT_NAMES = ("pixel_size", "channels", "color_mode", "bit_depth", "resolution", "compression", "software")


@dataclass(frozen=True, slots=True)
class FileEntry:
    root: RootName
    relative_path: PurePosixPath
    kind: FileKind
    size: int
    mtime_ns: int
    inode: int

    @property
    def hidden(self) -> bool:
        return self.relative_path.name.startswith(".")


@dataclass(frozen=True, slots=True)
class Excluded:
    root: RootName
    relative_path: PurePosixPath
    reason: str


@dataclass(slots=True)
class Inventory:
    images: list[FileEntry] = field(default_factory=list)
    attachments: list[FileEntry] = field(default_factory=list)
    directories: dict[RootName, set[PurePosixPath]] = field(default_factory=dict)
    excluded: list[Excluded] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class Fact:
    status: Literal["value", "missing", "not_applicable"]
    value: FactValue = None


@dataclass(frozen=True, slots=True)
class ReadResult:
    file: FileEntry
    facts: dict[str, Fact]
    error: str | None = None
    reused: bool = False


def scan(roots: Mapping[RootName, Path]) -> Inventory:
    """返回全部可见目录、影像、附件和排除项；扫描失败不伪装成空目录。"""
    result = Inventory()
    for name, directory in roots.items():
        _scan_root(name, directory, result)
    return result


def _scan_root(name: RootName, directory: Path, result: Inventory) -> None:
    if not directory.is_dir():
        raise FileNotFoundError(f"扫描根目录不存在：{directory}")
    result.directories[name] = set()
    for current, dirs, files in os.walk(directory, onerror=_scan_error):
        relative = PurePosixPath(Path(current).relative_to(directory).as_posix())
        result.directories[name].add(relative)
        visible = []
        for child in sorted(dirs):
            if child.startswith(("@", "#", ".")):
                result.excluded.append(Excluded(name, relative / child, "隐藏或系统目录（不遍历）"))
            else:
                visible.append(child)
        dirs[:] = visible
        for filename in sorted(files):
            path = relative / filename
            kind, reason = _classify(path)
            if kind is None:
                result.excluded.append(Excluded(name, path, reason))
                continue
            stat = (directory / path).stat()
            entry = FileEntry(name, path, kind, stat.st_size, stat.st_mtime_ns, stat.st_ino)
            if kind in {"tiff", "psb", "jpg"}:
                result.images.append(entry)
            else:
                result.attachments.append(entry)


def _scan_error(error: OSError) -> None:
    raise error


def _classify(path: PurePosixPath) -> tuple[FileKind | None, str]:
    if len(path.parts) < 2:
        return None, "文件直接位于根目录，不在分类中"
    suffix = path.suffix.lower()
    if suffix in TIFF_EXTENSIONS:
        return "tiff", ""
    if suffix == ".psb":
        return "psb", ""
    if suffix == ".txt":
        return "text", ""
    if path.parts[0] == NLC_CATEGORY:
        if path.name in NLC_ATTACHMENTS:
            return NLC_ATTACHMENTS[path.name], ""
        if suffix == ".jpg" and ("pages" in path.parts[2:-1] or path.name.endswith("_preview.jpg")):
            return "jpg", ""
        if "tiles" in path.parts[2:-1]:
            return None, "下载器图块缓存"
    return None, "不在本版导入范围的文件类型或位置"


def read_facts(file: FileEntry, root_dir: Path, previous: ReadResult | None = None) -> ReadResult:
    """复用成功且未变化的事实；读取失败返回显式缺失，下次必须重读。"""
    if previous is not None and previous.error is None and previous.file == file:
        return ReadResult(file, previous.facts, reused=True)
    facts = _empty_facts(file.kind)
    try:
        values = _read_header(root_dir / file.relative_path, file.kind)
    except (OSError, ValueError, SyntaxError, struct.error, Image.DecompressionBombError) as error:
        return ReadResult(file, facts, error=f"{type(error).__name__}: {error}")
    for name, value in values.items():
        if value is not None:
            facts[name] = Fact("value", value)
    return ReadResult(file, facts)


def _empty_facts(kind: FileKind) -> dict[str, Fact]:
    fields = {name: Fact("missing") for name in FACT_NAMES}
    not_applicable = {"resolution", "compression", "software"} if kind == "psb" else set()
    if kind == "jpg":
        not_applicable = {"compression", "software"}
    for name in not_applicable:
        fields[name] = Fact("not_applicable")
    return fields


def _read_header(path: Path, kind: FileKind) -> dict[str, FactValue]:
    if kind == "tiff":
        return _tiff_facts(path)
    if kind == "psb":
        return _psb_facts(path)
    if kind == "jpg":
        return _jpg_facts(path)
    raise ValueError("附件不读取影像事实")


def _tiff_facts(path: Path) -> dict[str, FactValue]:
    with tifffile.TiffFile(path) as image:
        if not image.pages:
            raise ValueError("TIFF 没有影像页")
        tags = image.pages[0].tags
        width, height = _tag(tags, 256), _tag(tags, 257)
        x, y, unit = _tag(tags, 282), _tag(tags, 283), _tag(tags, 296)
        resolution = None
        if x is not None and y is not None and unit in {"INCH", "CENTIMETER"}:
            resolution = (_rational(x), _rational(y), unit)
        return {
            "pixel_size": (int(width), int(height)) if width and height else None,
            "channels": _tag(tags, 277),
            "color_mode": _tag(tags, 262),
            "bit_depth": _tag(tags, 258),
            "resolution": resolution,
            "compression": _tag(tags, 259),
            "software": _tag(tags, 305),
        }


def _tag(tags, code: int):
    tag = tags.get(code)
    if tag is None:
        return None
    value = tag.value
    if isinstance(value, IntEnum):
        return value.name
    return value


def _rational(value) -> float:
    if isinstance(value, tuple):
        if value[1] == 0:
            raise ValueError("分辨率分母为零")
        return value[0] / value[1]
    return float(value)


def _psb_facts(path: Path) -> dict[str, FactValue]:
    with path.open("rb") as stream:
        signature, version, _, channels, height, width, depth, mode = struct.unpack(
            ">4sH6sHIIHH", stream.read(26),
        )
    if signature != b"8BPS" or version != 2 or not (width and height) or not 1 <= channels <= 56:
        raise ValueError("无效的 PSB 文件头")
    if depth not in {1, 8, 16, 32}:
        raise ValueError("无效的 PSB 位深")
    return {
        "pixel_size": (width, height), "channels": channels, "bit_depth": depth,
        "color_mode": PSB_COLOR_MODES.get(mode, f"UNKNOWN({mode})"),
    }


def _jpg_facts(path: Path) -> dict[str, FactValue]:
    with Image.open(path) as image:
        if image.format != "JPEG":
            raise ValueError("文件不是 JPEG")
        return {
            "pixel_size": image.size, "channels": image.layers,
            "color_mode": image.mode, "bit_depth": image.bits,
            "resolution": _jpg_resolution(image),
        }


def _jpg_resolution(image) -> tuple[float, float, str] | None:
    # 不用 info['dpi']：Pillow 会在 EXIF 缺字段时猜 72 dpi，不是文件中的事实。
    unit = image.info.get("jfif_unit")
    if unit in {1, 2}:
        x, y = image.info["jfif_density"]
        return float(x), float(y), "INCH" if unit == 1 else "CENTIMETER"
    exif = image.getexif()
    x, y, unit = exif.get(282), exif.get(283), exif.get(296)
    if x is not None and y is not None and unit in {2, 3}:
        return float(x), float(y), "INCH" if unit == 2 else "CENTIMETER"
    return None
