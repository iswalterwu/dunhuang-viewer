"""稳定身份计算；影像按标识认领，再按未被认领的位置延续。"""

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from .scan import FileEntry


@dataclass(frozen=True, slots=True)
class ImageState:
    id: UUID
    file: FileEntry
    first_seen: int
    last_seen: int
    missing_since: datetime | None = None


@dataclass(frozen=True, slots=True)
class ImageEvent:
    image_id: UUID
    kind: Literal["new", "moved", "changed", "missing", "reappeared"]
    at: datetime
    previous: FileEntry | None
    current: FileEntry | None


@dataclass(slots=True)
class ImageResolution:
    images: list[ImageState] = field(default_factory=list)
    events: list[ImageEvent] = field(default_factory=list)


def resolve_images(
    previous: Sequence[ImageState], files: Sequence[FileEntry], run: int, at: datetime | None = None,
) -> ImageResolution:
    """只算结果，不修改导入前状态；历史持久化与事实更新由 importer 完成。"""
    now = datetime.now(UTC) if at is None else at
    matches = _match_images(previous, files)
    result = ImageResolution()
    for file in files:
        old = matches.get(file)
        if old is None:
            current = ImageState(uuid4(), file, run, run)
            result.events.append(ImageEvent(current.id, "new", now, None, file))
        else:
            current = replace(old, file=file, last_seen=run, missing_since=None)
            result.events.extend(_image_changes(old, file, now))
        result.images.append(current)
    found = {image.id for image in result.images}
    for old in previous:
        if old.id not in found:
            if old.missing_since is None:
                result.images.append(replace(old, missing_since=now))
                result.events.append(ImageEvent(old.id, "missing", now, old.file, None))
            else:
                result.images.append(old)
    return result


def _match_images(previous: Sequence[ImageState], files: Sequence[FileEntry]) -> dict[FileEntry, ImageState]:
    by_signature = {_file_signature(image.file): image for image in previous}
    by_position = {}
    for image in sorted(previous, key=lambda image: image.last_seen):
        by_position[image.file.root, image.file.relative_path] = image
    matches = {}
    claimed = set()
    # 第一轮全部完成，才允许位置回退；目录 / 文件互换不会被先处理者抢走。
    for file in files:
        old = by_signature.get(_file_signature(file))
        if old is not None and old.id not in claimed:
            matches[file] = old
            claimed.add(old.id)
    for file in files:
        if file in matches:
            continue
        old = by_position.get((file.root, file.relative_path))
        if old is not None and old.id not in claimed:
            matches[file] = old
            claimed.add(old.id)
    return matches


def _file_signature(file: FileEntry) -> tuple[str, int, int, int]:
    return file.root, file.inode, file.size, file.mtime_ns


def _image_changes(old: ImageState, file: FileEntry, now: datetime) -> list[ImageEvent]:
    events = []
    if old.missing_since is not None:
        events.append(ImageEvent(old.id, "reappeared", now, old.file, file))
    if old.file.relative_path != file.relative_path:
        events.append(ImageEvent(old.id, "moved", now, old.file, file))
    if _file_signature(old.file) != _file_signature(file):
        events.append(ImageEvent(old.id, "changed", now, old.file, file))
    return events
