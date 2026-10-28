"""命名规则与数据登记的唯一源头；随导入批次记录规则版本。"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from .scan import FileEntry, ReadResult, RootName
    from .units import Unit

RULE_VERSION = "2026-10-28.1"

NLC_CATEGORY = "中国国博馆藏"
BATCH_CATEGORIES = {
    "188敦煌001": ("2018年", "2019年新增1", "2019年新增2", "2019年新增3", "2501-2600"),
    "188 敦煌002": ("202106新增",),
}
KNOWN_CATEGORIES = frozenset((*BATCH_CATEGORIES, "敦煌003", "敦煌004", NLC_CATEGORY))
PELLIOT_RANGES = ((2001, 4099), (4500, 5043), (5522, 6038))
TIFF_EXTENSIONS = frozenset({".tif", ".tiff", ".btf"})
NLC_ATTACHMENTS = {"manifest.json": "manifest", "report.json": "report", "index.json": "index"}

SEGMENT_NAMES = frozenset({
    "分段", "分", "切片", "片", "斷巻分段", "全巻分段", "全巻分", "全卷分", "寫 1巻分段",
})
CONTEXT_PRIORITY = {"regular": 0, "segment": 1, "version": 2, "page": 3}
KAIBAO_DIRECTORY = re.compile(r"^敦煌藏經洞\s*\d+")
KAIBAO_WORDS = ("開寶藏", "开宝藏")
NON_DUNHUANG_MARKERS = (
    ("《开宝藏》", KAIBAO_WORDS),
    ("清光绪写本", ("清光绪", "清光緒")),
    ("尖山刻经", ("尖山刻经", "尖山刻經")),
    ("室町写", ("室町",)),
    ("竹生島経", ("竹生島経", "竹生岛经")),
    ("紫紙金字", ("紫紙金字", "紫纸金字")),
    ("大橋家来翰集", ("大橋家来翰集",)),
)
NATIVE_TIFF = re.compile(r"native(?:\(\d+\))?\.(?:tif|tiff|btf)", re.IGNORECASE)

Lineage = Literal["BnF 原图", "第三方加工图", "本地合成", "国图 IDP 下载", "未判定"]
Confidence = Literal["确定", "推断"]
SourceKind = Literal["文件名解析", "文件头", "外部清单", "执行记录", "默认规则", "人工"]
IDP_LICENSE = "IDP：个人或非商业复用"
GALLICA_LICENSE = "Gallica：非商业免费复用，注明出处"
UNKNOWN_LICENSE = "未知"
PROCESSED_LICENSE = "未知（第三方衍生）"
LICENSE_RANK = {GALLICA_LICENSE: 0, IDP_LICENSE: 1, UNKNOWN_LICENSE: 2, PROCESSED_LICENSE: 2}
DISPLAY_RANK = {"登录墙内可展示": 0, "仅供研究使用": 1}
TRANSFER_EVENT = "第三方资料接收（接收事件 A）"
DOWNLOAD_EVENT = "IDP IIIF 下载（2026-10-21 起）"
LOCAL_EVENT = "本地生成（2026-10-21 脚本或拼接工作台）"


def image_role(kind: str, filename: str, root: str, context: str, ordinary_tiffs: int) -> str:
    """plan §4.4 的角色优先级；参数均已由扫描与单元入口确定。"""
    if kind == "psb":
        return "PSB 源文件"
    if kind == "tiff" and filename.lstrip(".").startswith("合并长卷"):
        return "合并长卷"
    if root == "backup":
        return "已迁出的分片"
    if context == "page":
        return "页图"
    if context == "version" or (kind == "jpg" and filename.endswith("_preview.jpg")):
        return "另一版本"
    if context == "segment":
        return "分段"
    return "单幅整卷" if ordinary_tiffs == 1 else "分段"


PSB_COLOR_MODES = {
    0: "BITMAP", 1: "GRAYSCALE", 2: "INDEXED", 3: "RGB", 4: "CMYK",
    7: "MULTICHANNEL", 8: "DUOTONE", 9: "LAB",
}


@dataclass(frozen=True, slots=True)
class RuleBasis:
    source: SourceKind
    author: str
    confidence: Confidence


@dataclass(frozen=True, slots=True)
class LineageDecision:
    value: Lineage
    basis: RuleBasis
    unresolved: bool = False


@dataclass(frozen=True, slots=True)
class SourcePolicy:
    collection: str
    acquisition: str
    license: str
    attribution: str
    display: str
    external: str
    basis: dict[str, RuleBasis]


@dataclass(frozen=True, slots=True)
class Provenance:
    status: Literal["已确认", "待核", "非敦煌"]
    evidence: tuple[str, ...]
    judge: str
    at: datetime
    suggestion: str | None = None
    suggestion_evidence: tuple[str, ...] = ()
    evidence_conflict: bool = False


def detect_lineage(
    reading: ReadResult, derived_outputs: frozenset[tuple[RootName, PurePosixPath]] = frozenset(),
) -> LineageDecision:
    """按 plan §4.4 的顺序逐文件判定；读失败的普通 TIFF 不误套 Gallica 许可。"""
    file = reading.file
    name = file.relative_path.name.lstrip(".")
    if file.relative_path.parts[0] == NLC_CATEGORY:
        return LineageDecision("国图 IDP 下载", _basis("lineage-nlc", "默认规则"))
    if file.kind == "psb":
        return LineageDecision("第三方加工图", _basis("lineage-psb", "默认规则"))
    if file.kind == "tiff" and name.startswith("合并长卷"):
        return LineageDecision("本地合成", _basis("lineage-local-name", "文件名解析"))
    if file.kind == "tiff" and (file.root, file.relative_path) in derived_outputs:
        return LineageDecision("本地合成", _basis("lineage-local-record", "执行记录"))
    if reading.error is not None:
        return LineageDecision("未判定", _basis("lineage-unreadable", "文件头"))
    software = reading.facts["software"]
    if file.kind == "tiff" and NATIVE_TIFF.fullmatch(name) and software.status == "missing":
        return LineageDecision("BnF 原图", _basis("lineage-bnf-native", "文件头"))
    if file.kind == "tiff" and software.status == "value":
        return LineageDecision("第三方加工图", _basis("lineage-software", "文件头"))
    return LineageDecision("未判定", _basis("lineage-unresolved", "默认规则"), unresolved=True)


def summarize_lineages(
    entries: Sequence[tuple[FileEntry, LineageDecision]],
) -> dict[tuple[RootName, PurePosixPath], str]:
    """影像目录只汇总直接包含的 TIFF / BTF；不把子目录、PSB 或 JPG 混进数量。"""
    groups = defaultdict(set)
    for file, lineage in entries:
        if file.kind == "tiff":
            groups[file.root, file.relative_path.parent].add(lineage.value)
    return {directory: next(iter(values)) if len(values) == 1 else "混合" for directory, values in groups.items()}


def source_policy(
    file: FileEntry, lineage: Lineage, *, has_pelliot: bool = False, attribution: str | None = None,
    sources: Sequence[SourcePolicy] = (),
) -> SourcePolicy:
    """D-012 的六项默认字段；只消费已判定的谱系、馆藏号和外部清单署名。"""
    if lineage == "本地合成":
        return _inherited_policy(sources)
    channel = _acquisition(file)
    if lineage == "国图 IDP 下载":
        result = _policy("license-nlc", "中国国家图书馆", channel, IDP_LICENSE,
                         attribution or "The National Library of China", "登录墙内可展示", "链接 IDP")
        if attribution:
            result.basis["attribution"] = _basis("license-nlc-attribution", "外部清单", "确定")
        return result
    if lineage == "BnF 原图":
        return _policy("license-bnf", "法国国家图书馆", channel, GALLICA_LICENSE,
                       "Source gallica.bnf.fr / BnF", "登录墙内可展示", "链接 Gallica / IDP")
    if lineage == "第三方加工图":
        return _policy("license-processed", "法国国家图书馆" if has_pelliot else "未知", channel,
                       PROCESSED_LICENSE, "无", "仅供研究使用", "不对外")
    return _policy("license-unknown", "未知", channel, UNKNOWN_LICENSE, "无", "仅供研究使用", "不对外")


def item_display_policy(policies: Sequence[SourcePolicy]) -> str:
    return max((policy.display for policy in policies), key=DISPLAY_RANK.__getitem__)


def _basis(rule: str, source: SourceKind, confidence: Confidence = "推断") -> RuleBasis:
    return RuleBasis(source, f"rule:{rule}@{RULE_VERSION}", confidence)


def _acquisition(file: FileEntry) -> str:
    category = file.relative_path.parts[0]
    if category == NLC_CATEGORY:
        return DOWNLOAD_EVENT
    return TRANSFER_EVENT if category in KNOWN_CATEGORIES else "未知"


def _policy(rule, collection, acquisition, license, attribution, display, external) -> SourcePolicy:
    basis = {name: _basis(rule, "默认规则") for name in ("collection", "acquisition", "license", "attribution", "display", "external")}
    return SourcePolicy(collection, acquisition, license, attribution, display, external, basis)


def _inherited_policy(sources: Sequence[SourcePolicy]) -> SourcePolicy:
    if not sources:
        return _policy("license-local-unknown", "未知", LOCAL_EVENT, UNKNOWN_LICENSE, "无", "仅供研究使用", "不对外")
    strictest = max(sources, key=lambda policy: (LICENSE_RANK[policy.license], DISPLAY_RANK[policy.display]))
    collection = "；".join(sorted({policy.collection for policy in sources}))
    attribution = "；".join(sorted({policy.attribution for policy in sources if policy.attribution != "无"})) or "无"
    return _policy("license-local-inherit", collection, LOCAL_EVENT, strictest.license,
                   attribution, item_display_policy(sources), strictest.external)


def initial_provenance(
    grouping_key: str | None, units: Sequence[Unit], previous: Provenance | None = None, at: datetime | None = None,
) -> Provenance:
    """规则只给已确认 / 待核，非敦煌仅建议；人工结论原样保留。"""
    if previous is not None and previous.judge.startswith("user:"):
        return previous
    counter_evidence = _non_dunhuang_evidence(units)
    evidence = ([f"合规馆藏号：{grouping_key}"] if grouping_key else []) + list(counter_evidence)
    value = Provenance(
        "已确认" if grouping_key and not counter_evidence else "待核",
        tuple(evidence) or ("未发现合规馆藏号及明确的非敦煌线索",),
        f"rule:provenance-initial@{RULE_VERSION}", datetime.now(UTC) if at is None else at,
        "非敦煌" if counter_evidence else None, counter_evidence, bool(grouping_key and counter_evidence),
    )
    if previous is not None and replace(value, at=previous.at) == previous:
        return previous
    return value


def _non_dunhuang_evidence(units: Sequence[Unit]) -> tuple[str, ...]:
    evidence = set()
    for unit in units:
        texts = [unit.name] + [
            image.file.relative_path.name for image in unit.images
            if image.file.kind == "psb" and image.file.relative_path.parent == unit.relative_path
        ]
        if KAIBAO_DIRECTORY.match(unit.name):
            evidence.add(f"{unit.key}：敦煌藏經洞序号目录，疑为《开宝藏》刻本")
        for ident in unit.parsed.identifiers:
            if ident.system == "zhihao":
                evidence.add(f"{unit.key}：开宝藏帙号 {ident.raw}")
        for label, markers in NON_DUNHUANG_MARKERS:
            names = texts if markers == KAIBAO_WORDS else [unit.name]
            if any(marker in text for text in names for marker in markers):
                evidence.add(f"{unit.key}：{label}")
    return tuple(sorted(evidence))
