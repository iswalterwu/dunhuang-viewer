"""稳定身份计算；影像两阶段认领，写卷按 S0 同时改号，不自动合并或拆分。"""

from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from .identifiers import Identifier
from .scan import FileEntry
from .units import Unit


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


@dataclass(frozen=True, slots=True)
class SourcedIdentifier:
    value: Identifier
    unit_key: str


@dataclass(frozen=True, slots=True)
class ItemState:
    id: UUID
    serial: int
    grouping_key: str | None
    image_ids: frozenset[UUID]
    parent_id: UUID | None = None
    identifiers: tuple[SourcedIdentifier, ...] = ()
    clues: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class NumberChange:
    item_id: UUID
    before: str | None
    after: str | None


@dataclass(slots=True)
class ItemResolution:
    items: list[ItemState]
    unit_items: dict[str, frozenset[UUID]]
    pending: dict[UUID, tuple[str, ...]]
    pending_identifiers: dict[UUID, tuple[SourcedIdentifier, ...]]
    number_changes: list[NumberChange]
    # B 中没有仍在的已有影像：不重算其编号、线索、出处。importer 据此保留出处等字段。
    preserved_items: frozenset[UUID]


@dataclass(slots=True)
class _UnitDecision:
    unit: Unit
    image_ids: frozenset[UUID]
    counts: Counter[UUID]
    added_keys: frozenset[str]
    proposals: dict[UUID, str | None]
    pending: dict[UUID, str]


def resolve_items(
    previous: Sequence[ItemState], units: Sequence[Unit], images: Sequence[ImageState],
) -> ItemResolution:
    """plan §4.2.3 A～E；输入已由 scan / units / identifiers 确定，不访问外部数据。"""
    prior = {item.id: item for item in previous}
    decisions = _unit_decisions(prior, units, images)
    keys, pending, preserved = _item_decisions(prior, decisions)
    _rollback_collisions(prior, keys, pending)
    items, unit_items = _assign_item_images(prior, decisions, keys, pending)
    return _finish_items(prior, items, unit_items, decisions, pending, preserved)


def _unit_decisions(prior, units, images) -> list[_UnitDecision]:
    by_file = {image.file: image.id for image in images if image.missing_since is None}
    old_owners = defaultdict(set)
    for item in prior.values():
        for image_id in item.image_ids:
            old_owners[image_id].add(item.id)
    decisions = []
    for unit in units:
        image_ids = frozenset(by_file[image.file] for image in unit.images)
        counts = Counter(owner for image_id in image_ids for owner in old_owners[image_id])
        keys = unit.parsed.keys
        held = {prior[owner].grouping_key for owner in counts}
        added = keys - held
        unmatched = {owner for owner in counts if prior[owner].grouping_key not in keys}
        proposals = {owner: prior[owner].grouping_key for owner in counts}
        pending = {}
        if len(added) == len(unmatched) == 1:
            proposals[next(iter(unmatched))] = next(iter(added))
        elif unmatched:
            if not keys:
                pending = {
                    owner: f"{unit.key} 已没有馆藏号，保留原主编号"
                    for owner in unmatched if prior[owner].grouping_key is not None
                }
            else:
                pending = {
                    owner: f"{unit.key} 的 {len(added)} 个未持有编号与 {len(unmatched)} 件已有写卷无法一一对应"
                    for owner in unmatched
                }
        decisions.append(_UnitDecision(unit, image_ids, counts, added, proposals, pending))
    return decisions


def _item_decisions(prior, decisions):
    proposals = defaultdict(set)
    pending = defaultdict(set)
    for decision in decisions:
        for owner, key in decision.proposals.items():
            proposals[owner].add(key)
        for owner, reason in decision.pending.items():
            pending[owner].add(reason)
    keys = {}
    preserved = set()
    for item in prior.values():
        choices = proposals[item.id]
        if not choices:
            preserved.add(item.id)
        elif len(choices) > 1:
            pending[item.id].add("所在多个单元给出的编号结果不一致，保留原主编号")
        keys[item.id] = next(iter(choices)) if len(choices) == 1 and not pending[item.id] else item.grouping_key
    return keys, {owner: reasons for owner, reasons in pending.items() if reasons}, frozenset(preserved)


def _rollback_collisions(prior, keys, pending) -> None:
    # 只回退改号者；每次至少退回一件，最终 key0 互异，故不需要重试上限或兜底合并。
    while True:
        groups = defaultdict(list)
        for owner, key in keys.items():
            if key is not None:
                groups[key].append(owner)
        conflicts = [owners for owners in groups.values() if len(owners) > 1]
        if not conflicts:
            return
        for owners in conflicts:
            participant_ids = ", ".join(sorted(str(owner) for owner in owners))
            for owner in owners:
                if keys[owner] != prior[owner].grouping_key:
                    reason = (
                        f"拟用编号 {keys[owner]} 与其他写卷同号，退回原主编号"
                        f"（本轮同号写卷 ID：{participant_ids}）"
                    )
                    keys[owner] = prior[owner].grouping_key
                    pending.setdefault(owner, set()).add(reason)


def _assign_item_images(prior, decisions, keys, pending):
    items = {owner: replace(item, grouping_key=keys[owner]) for owner, item in prior.items()}
    owners = {item.grouping_key: item.id for item in items.values() if item.grouping_key is not None}
    next_serial = max((item.serial for item in prior.values()), default=0) + 1
    wanted = sorted({
        key for d in decisions if not (d.counts.keys() & pending.keys()) for key in d.unit.parsed.keys
    })
    for key in wanted:
        if key not in owners:
            item = ItemState(uuid4(), next_serial, key, frozenset())
            items[item.id] = item
            owners[key] = item.id
            next_serial += 1
    unkeyed = {}
    for d in sorted(decisions, key=lambda d: (str(d.unit.relative_path), d.unit.root)):
        if not d.counts and not d.unit.parsed.keys:
            item = ItemState(uuid4(), next_serial, None, frozenset())
            items[item.id] = item
            unkeyed[d.unit.key] = item.id
            next_serial += 1
    assigned = {owner: set(item.image_ids) for owner, item in items.items()}
    previously_owned = {image_id for item in prior.values() for image_id in item.image_ids}
    for d in decisions:
        keys_in_unit = d.unit.parsed.keys
        new_images = d.image_ids - previously_owned
        if not d.counts:
            targets = {owners[key] for key in keys_in_unit} if keys_in_unit else {unkeyed[d.unit.key]}
            for owner in targets:
                assigned[owner].update(d.image_ids)
        elif not keys_in_unit or (d.counts.keys() & pending.keys()):
            winner = min(d.counts, key=lambda owner: (-d.counts[owner], prior[owner].serial))
            assigned[winner].update(new_images)
        else:
            for key in keys_in_unit:
                assigned[owners[key]].update(d.image_ids if key in d.added_keys else new_images)
    by_image = defaultdict(set)
    for owner, image_ids in assigned.items():
        items[owner] = replace(items[owner], image_ids=frozenset(image_ids))
        for image_id in image_ids:
            by_image[image_id].add(owner)
    unit_items = {
        d.unit.key: frozenset(owner for image_id in d.image_ids for owner in by_image[image_id])
        for d in decisions
    }
    return items, unit_items


def _finish_items(prior, items, unit_items, decisions, pending, preserved) -> ItemResolution:
    units_by_item = defaultdict(list)
    for d in sorted(decisions, key=lambda d: d.unit.key):
        for owner in unit_items[d.unit.key]:
            units_by_item[owner].append(d.unit)
    owners = {item.grouping_key: item.id for item in items.values() if item.grouping_key is not None}
    pending_identifiers = {}
    changes = []
    for owner, item in items.items():
        if owner not in preserved:
            identifiers = []
            candidates = []
            clues = set()
            for unit in units_by_item[owner]:
                if len(unit.parsed.keys) > 1:
                    clues.add("名称所示的合装或缀合")
                for ident in unit.parsed.identifiers:
                    sourced = SourcedIdentifier(ident, unit.key)
                    if ident.key is None or ident.key == item.grouping_key:
                        identifiers.append(sourced)
                    elif owner in pending:
                        candidates.append(sourced)
            if owner in pending and item.grouping_key is not None and not any(
                sourced.value.key == item.grouping_key for sourced in identifiers
            ):
                # 待确认只重算其余编号；原主编号即使已不在当前目录名中也必须保留。
                identifiers.extend(
                    sourced for sourced in prior[owner].identifiers if sourced.value.key == item.grouping_key
                )
            item = replace(item, identifiers=tuple(identifiers), clues=tuple(sorted(clues)))
            if candidates:
                pending_identifiers[owner] = tuple(candidates)
        parent_id = owners.get(_parent_key(item.grouping_key))
        items[owner] = replace(item, parent_id=parent_id)
        if owner in prior and prior[owner].grouping_key != item.grouping_key:
            changes.append(NumberChange(owner, prior[owner].grouping_key, item.grouping_key))
    return ItemResolution(
        sorted(items.values(), key=lambda item: item.serial), unit_items,
        {owner: tuple(sorted(reasons)) for owner, reasons in pending.items()}, pending_identifiers,
        sorted(changes, key=lambda change: items[change.item_id].serial), preserved,
    )


def _parent_key(key: str | None) -> str | None:
    if key is None:
        return None
    system, number = key.split(":", 1)
    if system == "pelliot" and ":" in number:
        return "pelliot:" + number.split(":", 1)[0]
    if system == "nlc" and number[-1].isalpha():
        return "nlc:" + number[:-1]
    return None
