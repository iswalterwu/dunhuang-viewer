from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from pathlib import PurePosixPath

import pytest

from dh_catalog import rules
from dh_catalog.rules import (
    GALLICA_LICENSE, IDP_LICENSE, RULE_VERSION, Provenance, detect_lineage, initial_provenance,
    item_display_policy, source_policy, summarize_lineages,
)
from dh_catalog.scan import read_facts, scan
from dh_catalog.units import build_units

NOW = datetime(2026, 10, 28, 13, 0, tzinfo=UTC)


@pytest.mark.parametrize("name,software,expected", [
    ("敦煌003/P2002/native.tif", "", "BnF 原图"),
    ("敦煌003/P2002/native(2).tif", "", "BnF 原图"),
    ("敦煌003/P2002/native.tif", "Photoshop CS6", "第三方加工图"),
    ("敦煌003/P2002/1.tif", "Photoshop CS6", "第三方加工图"),
    ("敦煌003/P2002/1.tif", "", "未判定"),
    ("敦煌003/P2002/合并长卷.tif", "Photoshop", "本地合成"),
    ("敦煌003/P2002/.合并长卷.tif", "", "本地合成"),
    ("敦煌003/P2002/合并长卷.psb", "", "第三方加工图"),
    ("中国国博馆藏/BD00001/1.tif", "Photoshop", "国图 IDP 下载"),
    ("中国国博馆藏/BD00001/pages/0001_7x5.jpg", "", "国图 IDP 下载"),
    ("中国国博馆藏/BD00001/BD00001_preview.jpg", "", "国图 IDP 下载"),
])
def test_lineage(roots, make_image, name, software, expected):
    make_image(roots["data"] / name, software=software)
    file = scan(roots).images[0]
    result = detect_lineage(read_facts(file, roots["data"]))
    assert result.value == expected
    assert result.unresolved is (expected == "未判定")
    assert result.basis.author.startswith("rule:lineage-")
    assert result.basis.author.endswith("@" + RULE_VERSION)
    assert result.basis.confidence == "推断"


def test_unreadable_native_tiff_not_assumed_bnf_and_recovery_rejudged(roots, make_image):
    path = roots["data"] / "敦煌003/P2002/native(1).tif"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"not a TIFF")
    file = scan(roots).images[0]
    reading = read_facts(file, roots["data"])
    result = detect_lineage(reading)
    assert reading.error
    assert result.value == "未判定" and not result.unresolved  # 已有读取异常，不重复报谱系异常。
    assert source_policy(file, result.value).license == "未知"
    make_image(path)
    recovered = read_facts(scan(roots).images[0], roots["data"], reading)
    assert recovered.error is None
    assert detect_lineage(recovered).value == "BnF 原图"


def test_recorded_output_lineage_uses_execution_record_basis(roots, make_image):
    make_image(roots["data"] / "敦煌003/P2002/recorded_output.tif")
    file = scan(roots).images[0]
    decision = detect_lineage(read_facts(file, roots["data"]), frozenset({(file.root, file.relative_path)}))
    assert decision.value == "本地合成"
    assert decision.basis.source == "执行记录"


def test_directory_summary_only_direct_tiffs(roots, make_image):
    for name, software in [
        ("敦煌003/P2002/native.tif", ""), ("敦煌003/P2002/processed.tif", "Photoshop"),
        ("敦煌003/P2002/HD/native.tif", ""), ("敦煌003/P2003/native.tif", ""),
        ("敦煌003/P2003/source.psb", ""), ("中国国博馆藏/BD00001/pages/0001_7x5.jpg", ""),
    ]:
        make_image(roots["data"] / name, software=software)
    entries = [(file, detect_lineage(read_facts(file, roots["data"]))) for file in scan(roots).images]
    assert summarize_lineages(entries) == {
        ("data", PurePosixPath("敦煌003/P2002")): "混合",
        ("data", PurePosixPath("敦煌003/P2002/HD")): "BnF 原图",
        ("data", PurePosixPath("敦煌003/P2003")): "BnF 原图",
    }


@pytest.mark.parametrize("lineage,pelliot,collection,license,display,external", [
    ("BnF 原图", True, "法国国家图书馆", GALLICA_LICENSE, "登录墙内可展示", "链接 Gallica / IDP"),
    ("第三方加工图", True, "法国国家图书馆", "未知（第三方衍生）", "仅供研究使用", "不对外"),
    ("第三方加工图", False, "未知", "未知（第三方衍生）", "仅供研究使用", "不对外"),
    ("未判定", False, "未知", "未知", "仅供研究使用", "不对外"),
])
def test_license_defaults(roots, make_image, lineage, pelliot, collection, license, display, external):
    make_image(roots["data"] / "敦煌003/P2002/1.tif")
    policy = source_policy(scan(roots).images[0], lineage, has_pelliot=pelliot)
    assert (policy.collection, policy.license, policy.display, policy.external) == (collection, license, display, external)
    assert all((policy.collection, policy.acquisition, policy.license, policy.attribution, policy.display, policy.external))
    assert set(policy.basis) == {"collection", "acquisition", "license", "attribution", "display", "external"}
    assert all(b.author.endswith("@" + RULE_VERSION) for b in policy.basis.values())
    if pelliot and lineage == "第三方加工图":
        assert policy.basis["collection"].confidence == "推断"


def test_nlc_attribution_from_manifest_or_explicit_default(roots, make_image):
    make_image(roots["data"] / "中国国博馆藏/BD00001/1.tif")
    file = scan(roots).images[0]
    policy = source_policy(file, "国图 IDP 下载", attribution="The National Library of China")
    assert policy.collection == "中国国家图书馆" and policy.license == IDP_LICENSE
    assert policy.attribution == "The National Library of China"
    assert policy.basis["attribution"].source == "外部清单"
    assert policy.basis["attribution"].confidence == "确定"
    fallback = source_policy(file, "国图 IDP 下载")
    assert fallback.attribution == "The National Library of China"
    assert fallback.basis["attribution"].source == "默认规则"


def test_shared_rule_basis_is_frozen_but_policy_maps_are_independent(roots, make_image):
    make_image(roots["data"] / "中国国博馆藏/BD00001/1.tif")
    file = scan(roots).images[0]
    first = source_policy(file, "国图 IDP 下载")
    second = source_policy(file, "国图 IDP 下载", attribution="Synthetic Library")
    assert first.basis is not second.basis
    assert first.basis["collection"] is second.basis["collection"]
    assert first.basis["attribution"].source == "默认规则"
    assert second.basis["attribution"].source == "外部清单"
    with pytest.raises(FrozenInstanceError):
        first.basis["collection"].author = "user:must-not-mutate"
    version = rules.RULE_VERSION
    try:
        rules.RULE_VERSION = version + ".test"
        changed = source_policy(file, "国图 IDP 下载")
        assert changed.basis["collection"].author.endswith("@" + rules.RULE_VERSION)
        assert changed.basis["collection"] is not first.basis["collection"]
    finally:
        rules.RULE_VERSION = version
    assert source_policy(file, "国图 IDP 下载").basis["collection"] is first.basis["collection"]
    assert rules._versioned_basis.cache_info().maxsize == 128


def test_item_policy_most_restrictive(roots, make_image):
    make_image(roots["data"] / "敦煌003/P2002/1.tif")
    file = scan(roots).images[0]
    bnf = source_policy(file, "BnF 原图")
    processed = source_policy(file, "第三方加工图", has_pelliot=True)
    assert item_display_policy([bnf]) == "登录墙内可展示"
    assert item_display_policy([bnf, processed]) == "仅供研究使用"
    local = source_policy(file, "本地合成", sources=[bnf, processed])
    assert local.license == "未知（第三方衍生）" and local.display == "仅供研究使用"
    assert local.external == "不对外" and local.collection == "法国国家图书馆"
    assert "gallica" in local.attribution
    nlc = source_policy(file, "国图 IDP 下载")
    mixed = source_policy(file, "本地合成", sources=[bnf, nlc])
    assert mixed.license == IDP_LICENSE and mixed.external == "链接 IDP"
    unknown = source_policy(file, "本地合成")
    assert unknown.license == "未知" and unknown.display == "仅供研究使用"


def test_channel_is_specific_event(roots, make_image):
    make_image(roots["data"] / "敦煌003/P2002/1.tif")
    make_image(roots["data"] / "中国国博馆藏/BD00001/1.tif")
    files = {file.relative_path.parts[0]: file for file in scan(roots).images}
    assert source_policy(files["敦煌003"], "BnF 原图").acquisition == "第三方资料接收（接收事件 A）"
    assert source_policy(files["中国国博馆藏"], "国图 IDP 下载").acquisition == "IDP IIIF 下载（2026-10-21 起）"
    assert "本地生成" in source_policy(files["敦煌003"], "本地合成").acquisition


def test_every_item_has_provenance():
    result = initial_provenance(None, [], at=NOW)
    assert result.status == "待核" and result.evidence
    assert result.judge == "rule:provenance-initial@" + RULE_VERSION
    assert result.at == NOW
    assert result.suggestion is None


def test_confirmed_only_without_counter_evidence(roots, make_image):
    make_image(roots["data"] / "敦煌003/P2002 敦煌遗书/1.tif")
    units = build_units(scan(roots)).units
    result = initial_provenance("pelliot:2002", units, at=NOW)
    assert result.status == "已确认" and not result.evidence_conflict
    assert initial_provenance(None, units, at=NOW).status == "待核"
    assert initial_provenance("pelliot:2002", units, result, NOW + timedelta(hours=1)) is result
    old_rule = replace(result, judge="rule:provenance-initial@previous-version")
    updated = initial_provenance("pelliot:2002", units, old_rule, NOW + timedelta(hours=1))
    assert updated.judge != old_rule.judge and updated.at > old_rule.at


@pytest.mark.parametrize("name", [
    "敦煌藏經洞 1 令字", "開寶藏零本", "清光绪18年 經", "北齐 尖山刻经", "室町写",
    "竹生島経", "紫紙金字金光明最勝王経", "大橋家来翰集",
])
def test_non_dunhuang_suggestions_and_conflicts(roots, make_image, name):
    make_image(roots["data"] / "188敦煌001/2018年" / name / "1.tif")
    units = build_units(scan(roots)).units
    result = initial_provenance(None, units, at=NOW)
    assert result.status == "待核" and result.suggestion == "非敦煌"
    assert result.suggestion_evidence and not result.evidence_conflict
    conflict = initial_provenance("pelliot:2002", units, at=NOW)
    assert conflict.status == "待核" and conflict.evidence_conflict
    assert any("pelliot:2002" in evidence for evidence in conflict.evidence)


def test_psb_kaibao_evidence_and_human_conclusion_preserved(roots, make_image):
    directory = roots["data"] / "188敦煌001/2018年/待核"
    make_image(directory / "開寶藏零件.psb")
    units = build_units(scan(roots)).units
    initial = initial_provenance(None, units, at=NOW)
    assert initial.suggestion == "非敦煌"
    human = Provenance("非敦煌", ("人工核对文献",), "user:owner", NOW)
    assert initial_provenance("pelliot:2002", units, human, NOW + timedelta(hours=1)) is human
