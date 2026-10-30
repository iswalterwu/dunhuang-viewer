"""国图 JSON 边界：提取编号、署名与零起始画布，不保留原始附件。"""

import json
import re
from dataclasses import dataclass, replace
from pathlib import PurePosixPath

from .identifiers import BD, Identifier, ParsedIdentifiers, parse_identifiers
from .rules import SourceKind
from .scan import RootName
from .units import Unit

TIFF_NUMBER = re.compile(r"BD\d{5}[a-z]?_(\d{4})_\d+\.(?:tif|tiff|btf)", re.IGNORECASE)
PAGE_NUMBER = re.compile(r"(\d{4})_\d+x\d+\.jpg", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class IdentifierOrigin:
    source: SourceKind
    root: RootName
    relative_path: PurePosixPath
    field: str


@dataclass(frozen=True, slots=True)
class CanvasRef:
    number: int
    id: str


@dataclass(frozen=True, slots=True)
class NlcIssue:
    category: str
    root: RootName
    relative_path: PurePosixPath
    raw: str
    reason: str
    field: str = ""


@dataclass(frozen=True, slots=True)
class NlcResult:
    parsed: ParsedIdentifiers
    attribution: str | None
    canvases: dict[PurePosixPath, CanvasRef]
    issues: tuple[NlcIssue, ...]
    # 与 parsed.identifiers 同序；同号的目录写法和清单写法各自保留出处。
    identifier_origins: tuple[IdentifierOrigin, ...]


@dataclass(frozen=True, slots=True)
class _Manifest:
    pressmark: str | None
    pressmark_field: str
    entry_id: str | None
    attribution: str | None
    canvases: dict[int, str]


def parse_nlc(unit: Unit, manifest: bytes | None, report: bytes | None) -> NlcResult:
    """调用方在身份计算前以 result.parsed 覆盖 unit.parsed；本函数不修改单元。

    None 表示附件不可用；读取失败由调用方另记。JSON / 字段格式错误在此
    记为 issues，不中断导入。有清单但 Pressmark 不可用时不信任目录号。
    report 的 strips 非列表（含没有 report）时使用文件名序号。
    三种附件的原始字节由调用方存储，index.json 不参与业务解析。
    """
    issues: list[NlcIssue] = []
    parsed_manifest = _read_manifest(unit, manifest, issues)
    strips = _read_strips(unit, report, issues)
    parsed, origins = _resolve_identifiers(unit, parsed_manifest, manifest is None, issues)
    canvases = _map_canvases(unit, parsed_manifest.canvases, strips, issues)
    return NlcResult(parsed, parsed_manifest.attribution, canvases, tuple(issues), origins)


def _json_object(raw: bytes | None, origin: IdentifierOrigin, issues: list[NlcIssue]) -> dict | None:
    if raw is None:
        return None
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        # 只留定位用片段；大附件原文由 importer 保存，不复制进异常结果。
        _format_issue(origin, "", raw[:160].decode("utf-8", errors="replace"), str(error), issues)
        return None
    if not isinstance(value, dict):
        _format_issue(origin, "", value, "JSON 顶层应为对象", issues)
        return None
    return value


def _format_issue(origin: IdentifierOrigin, field: str, raw, reason: str, issues: list[NlcIssue]) -> None:
    excerpt = raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False)
    issues.append(NlcIssue("读不了的文件", origin.root, origin.relative_path, excerpt[:160], reason, field))


def _language_values(value, origin: IdentifierOrigin, field: str, issues: list[NlcIssue]) -> tuple[str, ...]:
    if not isinstance(value, dict) or not all(
        isinstance(texts, list) and all(isinstance(text, str) for text in texts)
        for texts in value.values()
    ):
        _format_issue(origin, field, value, "应为 IIIF 语言映射（语言 → 字符串列表）", issues)
        return ()
    return tuple(text for texts in value.values() for text in texts)


def _read_manifest(unit: Unit, raw: bytes | None, issues: list[NlcIssue]) -> _Manifest:
    origin = IdentifierOrigin("外部清单", unit.root, unit.relative_path / "manifest.json", "")
    data = _json_object(raw, origin, issues)
    if data is None:
        return _Manifest(None, "metadata", None, None, {})
    pressmark = None
    pressmark_field = "metadata"
    metadata = data.get("metadata")
    if not isinstance(metadata, list):
        _format_issue(origin, "metadata", metadata, "metadata 应为列表", issues)
    else:
        for index, entry in enumerate(metadata):
            field = f"metadata[{index}]"
            if not isinstance(entry, dict):
                _format_issue(origin, field, entry, "metadata 条目应为对象", issues)
                continue
            labels = _language_values(entry.get("label"), origin, field + ".label", issues)
            if "Pressmark" in labels:
                values = _language_values(entry.get("value"), origin, field + ".value", issues)
                pressmark_field = field + ".value"
                if len(values) == 1:
                    pressmark = values[0]
                else:
                    _format_issue(origin, pressmark_field, values, "Pressmark 应有一个编号值", issues)
                break
    identifier = data.get("id")
    entry_id = None
    if isinstance(identifier, str) and identifier.rsplit("/", 1)[-1]:
        entry_id = identifier.rsplit("/", 1)[-1]
    else:
        _format_issue(origin, "id", identifier, "清单 id 应为末段非空的字符串", issues)
    attribution = None
    statement = data.get("requiredStatement")
    if statement is not None:
        if isinstance(statement, dict):
            values = _language_values(statement.get("value"), origin, "requiredStatement.value", issues)
            attribution = "\n".join(values) or None
        else:
            _format_issue(origin, "requiredStatement", statement, "requiredStatement 应为对象", issues)
    canvases = {}
    items = data.get("items")
    if not isinstance(items, list):
        _format_issue(origin, "items", items, "items 应为画布列表", issues)
    else:
        for number, item in enumerate(items):
            if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"]:
                canvases[number] = item["id"]
            else:
                _format_issue(origin, f"items[{number}].id", item, "画布应有非空字符串 id", issues)
    return _Manifest(pressmark, pressmark_field, entry_id, attribution, canvases)


def _read_strips(unit: Unit, raw: bytes | None, issues: list[NlcIssue]) -> dict[PurePosixPath, int] | None:
    origin = IdentifierOrigin("外部清单", unit.root, unit.relative_path / "report.json", "strips")
    data = _json_object(raw, origin, issues)
    if data is None or not isinstance(data.get("strips"), list):
        return None
    strips = {}
    for index, entry in enumerate(data["strips"]):
        if not (
            isinstance(entry, dict) and isinstance(entry.get("file"), str) and entry["file"]
            and type(entry.get("index")) is int and entry["index"] >= 0
        ):
            _format_issue(origin, f"strips[{index}]", entry, "分片应有 file 字符串与从 0 起的整数 index", issues)
            continue
        strips[unit.relative_path / entry["file"]] = entry["index"]
    return strips


def _resolve_identifiers(
    unit: Unit, manifest: _Manifest, missing: bool, issues: list[NlcIssue],
) -> tuple[ParsedIdentifiers, tuple[IdentifierOrigin, ...]]:
    directory_origin = IdentifierOrigin("文件名解析", unit.root, unit.relative_path, "name")
    manifest_origin = IdentifierOrigin(
        "外部清单", unit.root, unit.relative_path / "manifest.json", manifest.pressmark_field,
    )
    authority = None
    if manifest.pressmark is not None:
        candidates = parse_identifiers(manifest.pressmark).identifiers if BD.fullmatch(manifest.pressmark) else ()
        if candidates:
            authority = replace(candidates[0], normalized=manifest.pressmark)
        else:
            authority = Identifier("nlc", manifest.pressmark, manifest.pressmark)
    if missing:
        issues.append(NlcIssue("缺少清单", unit.root, manifest_origin.relative_path, unit.name,
                               "没有可用 manifest.json，按目录 BD 写法判定"))
    elif authority is None or not authority.compliant:
        issues.append(NlcIssue("编号存疑", unit.root, manifest_origin.relative_path, manifest.pressmark or "",
                               "Pressmark 缺失或写法不合规；清单号与目录号均不作为归并依据", manifest.pressmark_field))
    identifiers = []
    origins = []
    for ident in unit.parsed.identifiers:
        resolved = replace(ident, key=None)
        if ident.system == "nlc":
            if missing:
                resolved = ident
                if not ident.compliant:
                    issues.append(NlcIssue("编号存疑", unit.root, unit.relative_path, ident.raw,
                                           "目录 BD 写法不合规", "name"))
            elif authority is not None and authority.compliant and ident.raw.casefold() == authority.raw.casefold():
                resolved = replace(ident, normalized=authority.normalized, key=authority.key)
            else:
                issues.append(NlcIssue("编号与清单不一致", unit.root, unit.relative_path, ident.raw,
                                       f"目录号存疑；清单 Pressmark 为 {manifest.pressmark!r}", "name"))
        identifiers.append(resolved)
        origins.append(directory_origin)
    if authority is not None:
        identifiers.append(authority)
        origins.append(manifest_origin)
    if manifest.entry_id is not None:
        identifiers.append(Identifier("idp", manifest.entry_id, manifest.entry_id))
        origins.append(replace(manifest_origin, field="id"))
    return ParsedIdentifiers(tuple(identifiers), unit.parsed.suspected), tuple(origins)


def _map_canvases(
    unit: Unit, canvas_ids: dict[int, str], strips: dict[PurePosixPath, int] | None,
    issues: list[NlcIssue],
) -> dict[PurePosixPath, CanvasRef]:
    canvases = {}
    for image in unit.images:
        file = image.file
        path = file.relative_path
        if file.kind == "jpg" and path.name.endswith("_preview.jpg"):
            continue  # 整卷另一版本，不是单一画布，也不报对应异常。
        number = None
        if file.kind == "tiff":
            if strips is not None:
                number = strips.get(path)
            elif match := TIFF_NUMBER.fullmatch(path.name):
                number = int(match[1])
        elif file.kind == "jpg" and image.context == "page":
            if match := PAGE_NUMBER.fullmatch(path.name):
                number = int(match[1])
        else:
            continue
        if number is not None and number in canvas_ids:
            canvases[path] = CanvasRef(number, canvas_ids[number])
        else:
            reason = "未取得画布序号" if number is None else f"清单中没有可用的 items[{number}].id"
            issues.append(NlcIssue("画布对不上", file.root, path, path.name, reason))
    return canvases
