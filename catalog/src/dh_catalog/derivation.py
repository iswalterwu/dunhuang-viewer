"""10-21 执行记录入口：只读固定白名单，不访问日志指向的文件。

时间只取日志的操作时间；同一日志按行序。跨日志缺时间或同一时刻时
不以白名单顺序、文件 mtime 猜测最后操作。移动计划不是生成成功的证据。
"""

import json
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Literal, TextIO

from .rules import SEGMENT_NAMES
from .scan import FileEntry, RootName

CACHE_FILES = (
    "merge_all.log", "merge_smart_all.log", "merge_extra.log",
    "psb_convert.log", "psb_convert_all.log", "psb_convert_7.log", "psb_conv_wb5back.log",
    "seg_move_log.txt", "samefolder_move_log.txt", "extra_move_log.txt",
    "seg_move_plan.json", "samefolder_plan.json", "validated_moves.json",
)
Method = Literal["拼接", "PSB 转换"]
Location = tuple[RootName, PurePosixPath]
HEADER = re.compile(r"^=+\s+(?:(\d{2}:\d{2}:\d{2})\s+)?(开始|转换):\s*(.*?)\s+=+$")
COMPLETION = re.compile(r"^(完成|TIFF 完成):\s*(.+?\.(?:tif|tiff|btf))(?=\s{2,}|\s+\d|$)", re.I)
PIECE = re.compile(r"^\s*(.+?\.(?:tif|tiff|btf))\s+x0=", re.I)
COUNT = re.compile(r"(?:分片\s*(\d+)\s*个|拼接[：:]\s*(\d+)\s*片)")


@dataclass(frozen=True, slots=True)
class DerivationEdge:
    output: FileEntry
    source: FileEntry
    method: Method
    evidence_file: str
    evidence_line: int


@dataclass(frozen=True, slots=True)
class DerivationIssue:
    root: RootName | None
    relative_path: PurePosixPath | None
    reason: str
    evidence_file: str | None = None
    evidence_line: int | None = None
    raw: str = ""
    category: str = "派生来源不明"


@dataclass(slots=True)
class DerivationResult:
    edges: list[DerivationEdge] = field(default_factory=list)
    outputs: frozenset[Location] = frozenset()
    issues: list[DerivationIssue] = field(default_factory=list)
    opened_paths: list[Path] = field(default_factory=list)


@dataclass(slots=True)
class _Block:
    method: Method
    line: int
    raw: str
    clock: str | None = None
    directory: PurePosixPath | None = None
    psb_name: str | None = None
    names: list[str] = field(default_factory=list)
    count: int | None = None
    output: Location | None = None
    completion_line: int | None = None
    completion_raw: str = ""
    replaced: bool = False
    exited: bool = False
    error: str | None = None


@dataclass(frozen=True, slots=True)
class _Operation:
    output: Location
    method: Method
    directory: PurePosixPath | None
    psb_name: str | None
    names: tuple[str, ...]
    count: int | None
    clock: str | None
    evidence_file: str
    evidence_line: int
    raw: str


def resolve_derivations(
    cache_dir: Path, images: Sequence[FileEntry], *, record_roots: Mapping[str, str] | None = None,
) -> DerivationResult:
    """images 来自 scan；返回最终来源、成功输出位置、异常与所有打开尝试。

    outputs 包含成功生成的已扫描文件，即使其来源无法确定；不包含已被替换、
    不在清单中的中间文件。edges 对每个输出只采用最后一次成功操作，且来源
    必须全部可确定（不返回会误导许可继承的部分来源）。
    """
    result = DerivationResult()
    operations = _read_records(cache_dir.absolute(), result, record_roots=record_roots)
    _resolve_operations(operations, images, result)
    return result


def open_cache_record(cache_dir: Path, name: str, opened_paths: list[Path]) -> TextIO:
    """cache 统一只读打开入口；拒绝白名单外名称，失败尝试也进入报告。"""
    if name not in CACHE_FILES:
        raise ValueError(f"不在执行记录白名单：{name}")
    path = cache_dir.absolute() / name
    opened_paths.append(path)
    return path.open("r", encoding="utf-8-sig")


def _read_records(
    cache_dir: Path, result: DerivationResult, *, record_roots: Mapping[str, str] | None = None,
) -> list[_Operation]:
    operations = []
    for name in CACHE_FILES:
        try:
            with open_cache_record(cache_dir, name, result.opened_paths) as stream:
                if name.endswith(".json"):
                    _validate_plan(json.load(stream), name)
                elif name.endswith(".log"):
                    # 每个文件解析完再加入，解码 / 读取失败不留下半份证据。
                    parsed, issues = _parse_log(stream, name, record_roots=record_roots)
                    operations.extend(parsed)
                    result.issues.extend(issues)
                else:
                    # 移动日志只说明搬运，不能证明拼接或转换；不保留巨量原文。
                    for _ in stream:
                        pass
        except (OSError, UnicodeError, ValueError) as error:
            result.issues.append(DerivationIssue(
                None, None, f"执行记录缺失、读不了或格式错误：{type(error).__name__}: {error}", name,
                error.lineno if isinstance(error, json.JSONDecodeError) else None,
            ))
    return operations


def _validate_plan(value: object, name: str) -> None:
    """核查已知 JSON 外形；计划即使合法也不产生派生边或输出。"""
    key = {"seg_move_plan.json": "plan", "samefolder_plan.json": "has_merged", "validated_moves.json": "moves"}[name]
    if not isinstance(value, dict) or not isinstance(value.get(key), list):
        raise ValueError(f"应为含 {key} 列表的对象")
    fields = {
        "plan": ("src", "dst", "rel"),
        "has_merged": ("rel",),
        "moves": ("rel", "file", "src", "dst_dir", "keep"),
    }[key]
    for index, row in enumerate(value[key]):
        if not isinstance(row, dict) or any(not isinstance(row.get(f), str) for f in fields):
            raise ValueError(f"{key}[{index}] 缺少字符串字段 {fields}")
        if key == "has_merged":
            merged, move = row.get("merged"), row.get("move")
            if (not isinstance(merged, dict) or not isinstance(merged.get("name"), str)
                    or not isinstance(move, list)
                    or any(not isinstance(p, dict) or not isinstance(p.get("name"), str) for p in move)):
                raise ValueError(f"{key}[{index}] 的 merged / move 格式错误")


def _record_path(text: str, *, record_roots: Mapping[str, str] | None = None) -> Location:
    """日志路径仅转为清单键，不交给文件系统。"""
    root: RootName = "data"
    for label, prefix in (("data", "/data/"), ("backup", "/backup/"), *(record_roots or {}).items()):
        if text.startswith(prefix):
            text, root = text[len(prefix):], label
            break
    path = PurePosixPath(text)
    if not path.parts or path.is_absolute() or ".." in path.parts or "\\" in text:
        raise ValueError(f"不是 data / backup 下的记录路径：{text}")
    return root, path


def _parse_log(
    stream: TextIO, name: str, *, record_roots: Mapping[str, str] | None = None,
) -> tuple[list[_Operation], list[DerivationIssue]]:
    operations, issues = [], []
    method: Method = "拼接" if name.startswith("merge_") else "PSB 转换"
    block = None
    for number, raw in enumerate(stream, 1):
        text = raw.strip()
        header = HEADER.fullmatch(text)
        count = COUNT.search(text)
        # merge_all 的最后一块没有开始行：退出后的新计数行必须另起块。
        boundary = text.startswith("=====") or (block is not None and block.exited and count)
        if boundary or (text.startswith("PSBNAME:") and block is not None and (block.exited or block.output is not None)):
            if block is not None:
                _finish_block(block, name, operations, issues)
            block = None
        if header:
            clock, action, location = header.groups()
            block = _Block("拼接" if action == "开始" else "PSB 转换", number, text, clock)
            try:
                if clock is not None and any(int(v) >= bound for v, bound in zip(clock.split(":"), (24, 60, 60))):
                    raise ValueError("无效操作时间")
                if action == "转换" and " / " in location:
                    location, block.psb_name = location.rsplit(" / ", 1)
                block.directory = _record_path(location, record_roots=record_roots)[1]
            except ValueError as error:
                block.error = str(error)
            continue
        if text.startswith("=====") or not text:
            continue
        if block is None:
            block = _Block(method, number, text)
        try:
            if text.startswith("PSBNAME:"):
                block.psb_name = text.removeprefix("PSBNAME:").strip()
                if len(_record_path(block.psb_name, record_roots=record_roots)[1].parts) != 1:
                    raise ValueError("PSBNAME 应为文件名")
            if count:
                block.count = int(count.group(1) or count.group(2))
            piece = PIECE.match(text)
            if piece:
                piece_name = piece.group(1)
                if len(_record_path(piece_name, record_roots=record_roots)[1].parts) != 1:
                    raise ValueError("分片应为文件名")
                block.names.append(piece_name)
            complete = COMPLETION.match(text)
            if complete and ((block.method == "拼接") == (complete.group(1) == "完成")):
                block.output = _record_path(complete.group(2), record_roots=record_roots)
                block.completion_line, block.completion_raw = number, text
            if text == "已替换合并长卷.tif":
                if block.method != "PSB 转换" or block.output is None:
                    raise ValueError("替换记录之前没有 TIFF 完成证据")
                if block.directory is not None and block.output[1].parent != block.directory:
                    raise ValueError("转换目录与 TIFF 输出目录不一致")
                block.output = block.output[0], block.output[1].with_name("合并长卷.tif")
                block.replaced = True
                block.completion_line, block.completion_raw = number, text
            if text.startswith("Traceback"):
                block.error = "操作含 Traceback，不能证明生成成功"
            if text.startswith("退出码:"):
                block.exited = True
                if text.removeprefix("退出码:").strip() != "0":
                    block.error = f"操作失败（{text}）"
        except ValueError as error:
            block.error = str(error)
    if block is not None:
        _finish_block(block, name, operations, issues)
    return operations, issues


def _finish_block(block: _Block, name: str, operations: list[_Operation], issues: list[DerivationIssue]) -> None:
    if block.error or block.output is None:
        issues.append(DerivationIssue(
            block.output[0] if block.output else None,
            block.output[1] if block.output else block.directory,
            block.error or "操作没有最终 TIFF 完成证据；raw 完成或退出码 0 不代表成功",
            name, block.line, block.raw,
        ))
        return
    operations.append(_Operation(
        block.output, block.method, block.directory, block.psb_name, tuple(block.names), block.count,
        block.clock, name, block.completion_line, block.completion_raw,
    ))
    if block.method == "PSB 转换" and block.output[1].name == "合并长卷_psb.tif" and not block.replaced:
        issues.append(DerivationIssue(
            block.output[0], block.output[1].with_name("合并长卷.tif"),
            "只证明生成合并长卷_psb.tif，没有替换最终合并长卷.tif的证据",
            name, block.completion_line, block.completion_raw,
        ))


def _resolve_operations(operations: list[_Operation], images: Sequence[FileEntry], result: DerivationResult) -> None:
    by_location = {(file.root, file.relative_path): file for file in images}
    by_path = defaultdict(list)
    by_directory = defaultdict(list)
    for file in images:
        by_path[file.relative_path].append(file)
        by_directory[file.relative_path.parent].append(file)
    candidates = defaultdict(list)
    outputs = set()
    for operation in operations:
        output = by_location.get(operation.output)
        if output is None and operation.output[0] == "data":
            output = by_location.get(("backup", operation.output[1]))
        if output is None or output.kind != "tiff":
            result.issues.append(DerivationIssue(
                *operation.output, "执行记录中的输出不在已扫描 TIFF 清单中（不猜测改名或搬到父目录）",
                operation.evidence_file, operation.evidence_line, operation.raw,
            ))
            continue
        location = output.root, output.relative_path
        outputs.add(location)
        candidates[location].append(operation)
    for location, group in candidates.items():
        latest = _last_operation(group)
        if latest is None:
            result.issues.append(DerivationIssue(
                *location, "跨日志缺少操作时间或时间相同，不能确定最后成功操作",
                raw="；".join(f"{op.evidence_file}:{op.evidence_line}" for op in group),
            ))
            continue
        output = by_location[location]
        sources, reason = _sources(latest, by_path, by_directory)
        if reason:
            result.issues.append(DerivationIssue(
                *location, reason, latest.evidence_file, latest.evidence_line, latest.raw,
            ))
        else:
            result.edges.extend(DerivationEdge(
                output, source, latest.method, latest.evidence_file, latest.evidence_line,
            ) for source in sources)
    result.outputs = frozenset(outputs)
    for file in images:
        if (file.kind == "tiff" and file.relative_path.name.lstrip(".").startswith("合并长卷")
                and (file.root, file.relative_path) not in outputs):
            result.issues.append(DerivationIssue(
                file.root, file.relative_path, "不在 2026-10-21 执行记录中（无可确认的成功输出记录）",
            ))


def _last_operation(group: list[_Operation]) -> _Operation | None:
    # 同文件先取最后成功行；再比较不同文件中明确记下的操作时间。
    last_by_file = {}
    for operation in group:
        previous = last_by_file.get(operation.evidence_file)
        if previous is None or operation.evidence_line > previous.evidence_line:
            last_by_file[operation.evidence_file] = operation
    remaining = list(last_by_file.values())
    if len(remaining) == 1:
        return remaining[0]
    if any(op.clock is None for op in remaining):
        return None
    remaining.sort(key=lambda op: op.clock)
    return remaining[-1] if remaining[-1].clock != remaining[-2].clock else None


def _sources(operation: _Operation, by_path, by_directory) -> tuple[list[FileEntry], str]:
    directory = operation.directory or operation.output[1].parent
    if operation.method == "PSB 转换":
        if directory != operation.output[1].parent:
            return [], "转换目录与输出目录不一致"
        sources = [file for file in by_directory[directory] if file.kind == "psb"
                   and (operation.psb_name is None or file.relative_path.name == operation.psb_name)]
        if len(sources) != 1:
            return [], f"PSB 源文件不能唯一确定：匹配 {len(sources)} 个"
        return sources, ""
    if operation.directory is not None and operation.output[1].parent not in {directory, directory.parent}:
        return [], "拼接起始目录与输出位置不对应，不能套用这一块的源分片"
    if operation.names and operation.directory is not None:
        paths = [directory / name for name in operation.names]
        sources = [file for path in paths for file in by_path[path] if file.kind == "tiff"]
        if len(set(paths)) != len(paths) or any(len(by_path[path]) != 1 for path in paths):
            return [], "记录的源分片缺失、重复或在 data / backup 中有多个候选"
        if operation.count is not None and len(sources) != operation.count:
            return [], "分片名清单与记录的分片数不一致"
        if any(file.relative_path == operation.output[1] for file in sources):
            return [], "源分片清单包含输出自身"
        return sources, ""
    # 未列片名时，只接受起始目录或其一个直接分段子目录中的唯一完整集合。
    # 段号仅是位置编号，不能直接拼成 1.tif 等文件名。
    if operation.count is None or operation.count <= 0:
        return [], "未列源分片名且没有有效分片数，不能确定源文件集合"
    groups = []
    for path, files in by_directory.items():
        if path != directory and not (path.parent == directory and (
                path.name in SEGMENT_NAMES or path.name.endswith(("分段", "裁")))):
            continue
        sources = [file for file in files if file.kind == "tiff"
                   and file.relative_path != operation.output[1]
                   and not file.relative_path.name.lstrip(".").startswith("合并长卷")]
        if operation.names:
            sources = [file for file in sources if file.relative_path.name in operation.names]
        if len(sources) == operation.count and len({file.relative_path for file in sources}) == len(sources):
            groups.append(sources)
    if len(groups) != 1:
        return [], f"源分片集合不能唯一确定：{operation.count} 片，匹配 {len(groups)} 个目录集合"
    return sorted(groups[0], key=lambda file: (file.root, file.relative_path)), ""
