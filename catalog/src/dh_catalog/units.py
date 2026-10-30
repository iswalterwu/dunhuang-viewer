"""从扫描清单划分写卷单元；只建议合并，不分配写卷 ID、不修改文件。"""

import re
from collections import defaultdict
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import PurePosixPath

from .identifiers import ParsedIdentifiers, parse_identifiers
from .rules import (
    BATCH_CATEGORIES, CONTEXT_PRIORITY, KNOWN_CATEGORIES, NLC_CATEGORY, SEGMENT_NAMES, image_role,
)
from .scan import Excluded, FileEntry, Inventory, RootName

PAIR_MARKER = re.compile(r"上部|下部|上卷|下卷|紙背")


@dataclass(slots=True)
class UnitImage:
    file: FileEntry
    context: str = "regular"
    role: str = ""


@dataclass(slots=True)
class Unit:
    root: RootName
    relative_path: PurePosixPath
    name: str
    images: list[UnitImage] = field(default_factory=list)
    attachments: list[FileEntry] = field(default_factory=list)
    parsed: ParsedIdentifiers = field(default_factory=lambda: ParsedIdentifiers((), ()))

    @property
    def key(self) -> str:
        # 这是本批次的单元位置键，不是写卷 / 影像的内部 ID。
        return f"{self.root}:{self.relative_path}"


@dataclass(frozen=True, slots=True)
class UnitIssue:
    category: str
    root: RootName
    relative_path: PurePosixPath
    reason: str


@dataclass(frozen=True, slots=True)
class MergeSuggestion:
    left: str
    right: str
    reason: str


@dataclass(slots=True)
class UnitsResult:
    units: list[Unit] = field(default_factory=list)
    unassigned_attachments: list[FileEntry] = field(default_factory=list)
    excluded: list[Excluded] = field(default_factory=list)
    issues: list[UnitIssue] = field(default_factory=list)
    new_categories: list[str] = field(default_factory=list)
    suggestions: list[MergeSuggestion] = field(default_factory=list)


def build_units(inventory: Inventory) -> UnitsResult:
    """编号只取单元名；国图 Pressmark 的覆盖由 nlc / importer 阶段完成。"""
    result = UnitsResult(excluded=list(inventory.excluded))
    files, children, has_images = _directory_index(inventory)
    candidates: dict[tuple[RootName, PurePosixPath], Unit] = {}
    for root in inventory.directories:
        for category in children[root, PurePosixPath(".")]:
            if category.name not in KNOWN_CATEGORIES and category.name not in result.new_categories:
                result.new_categories.append(category.name)
            containers = [category]
            if category.name in BATCH_CATEGORIES:
                containers += children[root, category]
            for container in containers:
                _loose_files(root, container, files, candidates, result)
                if container == category and category.name in BATCH_CATEGORIES:
                    continue
                for directory in children[root, container]:
                    logical_root: RootName = root
                    if root == "backup":
                        if directory in inventory.directories.get("data", set()):
                            logical_root = "data"
                        elif directory in has_images[root]:
                            result.issues.append(UnitIssue(
                                "备份分片对不上", root, directory, "原图目录中没有对应的写卷目录",
                            ))
                    unit = _unit(candidates, logical_root, directory, directory.name)
                    _walk_unit(root, directory, unit, "regular", files, children, has_images, candidates, result)
    _finish_units(candidates, result)
    _hidden_issues(inventory.images, result)
    result.suggestions = _merge_suggestions(result.units)
    return result


def _directory_index(inventory: Inventory):
    files = defaultdict(list)
    children = defaultdict(list)
    has_images = defaultdict(set)
    for file in (*inventory.images, *inventory.attachments):
        files[file.root, file.relative_path.parent].append(file)
    for root, directories in inventory.directories.items():
        for directory in sorted(directories):
            if directory.parts:
                children[root, directory.parent].append(directory)
    for file in inventory.images:
        has_images[file.root].update(file.relative_path.parents)
    return files, children, has_images


def _unit(candidates, root: RootName, path: PurePosixPath, name: str) -> Unit:
    key = root, path
    if key not in candidates:
        candidates[key] = Unit(root, path, name, parsed=parse_identifiers(name))
    return candidates[key]


def _loose_files(root, directory, files, candidates, result) -> None:
    for file in files[root, directory]:
        if file.kind in {"tiff", "psb", "jpg"}:
            unit = _unit(candidates, root, file.relative_path, file.relative_path.name)
            unit.images.append(UnitImage(file))
        else:
            result.unassigned_attachments.append(file)


def _walk_unit(root, directory, unit, context, files, children, has_images, candidates, result) -> None:
    for file in files[root, directory]:
        if file.kind in {"tiff", "psb", "jpg"}:
            unit.images.append(UnitImage(file, context))
        else:
            unit.attachments.append(file)
    for child in children[root, directory]:
        if child not in has_images[root]:
            result.excluded.append(Excluded(root, child, "不含可导入影像的子目录（附件仍保留）"))
            _walk_unit(root, child, unit, context, files, children, has_images, candidates, result)
            continue
        child_context = _subdir_context(child.name, unit.parsed, child.parts[0] == NLC_CATEGORY)
        if child_context is None:
            target = _unit(candidates, unit.root, child, child.name)
            result.issues.append(UnitIssue("词表外子目录", root, child, "自成写卷单元，不继承父编号"))
            _walk_unit(root, child, target, "regular", files, children, has_images, candidates, result)
        else:
            combined = max((context, child_context), key=CONTEXT_PRIORITY.__getitem__)
            _walk_unit(root, child, unit, combined, files, children, has_images, candidates, result)


def _subdir_context(name: str, parsed: ParsedIdentifiers, is_nlc: bool) -> str | None:
    if name in SEGMENT_NAMES or name.endswith(("分段", "裁")):
        return "segment"
    if name == "HD":
        return "version"
    if name.endswith("HD"):
        if any(i.compliant and name in {i.normalized + "HD", i.raw + "HD"} for i in parsed.identifiers):
            return "version"
    if is_nlc and name == "pages":
        return "page"
    return None


def _finish_units(candidates, result: UnitsResult) -> None:
    for unit in sorted(candidates.values(), key=lambda u: u.key):
        if not unit.images:
            if unit.attachments:
                result.issues.append(UnitIssue("缺少影像", unit.root, unit.relative_path, "仅附件，不建写卷"))
                result.unassigned_attachments.extend(unit.attachments)
            continue
        psb_names = [
            image.file.relative_path.name for image in unit.images
            if image.file.kind == "psb" and image.file.relative_path.parent == unit.relative_path
        ]
        if psb_names:
            unit.parsed = parse_identifiers(unit.name, psb_names)
        if not unit.parsed.keys:
            result.issues.append(UnitIssue("无馆藏号的写卷单元", unit.root, unit.relative_path, "不自动合并"))
        count = sum(
            image.file.kind == "tiff" and image.file.root == "data" and image.context == "regular"
            and not image.file.relative_path.name.lstrip(".").startswith("合并长卷")
            for image in unit.images
        )
        for image in unit.images:
            image.role = image_role(image.file.kind, image.file.relative_path.name, image.file.root, image.context, count)
        result.units.append(unit)


def _hidden_issues(images: list[FileEntry], result: UnitsResult) -> None:
    groups = defaultdict(list)
    for image in images:
        groups[image.root, image.relative_path.parent].append(image)
    for group in groups.values():
        if any(not image.hidden for image in group):
            for image in group:
                if image.hidden:
                    result.issues.append(UnitIssue(
                        "隐藏文件与非隐藏影像同目录（待确认）", image.root, image.relative_path, "逐个确认，不丢弃",
                    ))


def _merge_suggestions(units: list[Unit]) -> list[MergeSuggestion]:
    groups = defaultdict(list)
    for unit in units:
        if unit.parsed.keys:
            continue
        base = PAIR_MARKER.sub("", unit.name).strip()
        groups["name", base].append(unit)
        for ident in unit.parsed.identifiers:
            if ident.system in {"sharer", "zhihao"}:
                groups[ident.system, ident.normalized].append(unit)
    suggestions = set()
    for (system, value), group in groups.items():
        for left, right in combinations(group, 2):
            if left.key == right.key:
                continue
            if system == "name" and (left.name == right.name or not (PAIR_MARKER.search(left.name) or PAIR_MARKER.search(right.name))):
                continue
            a, b = sorted((left.key, right.key))
            suggestions.add((a, b, f"名称对应：{value}" if system == "name" else f"同一 {system}：{value}"))
    return [MergeSuggestion(*s) for s in sorted(suggestions)]
