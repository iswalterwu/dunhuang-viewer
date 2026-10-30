"""合成 IDP v3 格式；从真实小影像扫描、划分单元后调用国图解析器。"""

import json
from pathlib import PurePosixPath

import pytest

from dh_catalog.identity import resolve_images, resolve_items
from dh_catalog.nlc import CanvasRef, parse_nlc
from dh_catalog.rules import NLC_CATEGORY, source_policy
from dh_catalog.scan import scan
from dh_catalog.units import build_units

MANIFEST_ID = "https://example.invalid/iiif/3/manifest/SYNTHETIC-ENTRY"


def manifest_data(pressmark="BD61234a"):
    return {
        "@context": "http://iiif.io/api/presentation/3/context.json",
        "id": MANIFEST_ID,
        "type": "Manifest",
        "metadata": [
            {"label": {"en": ["Reading Direction"]}, "value": {"en": ["Right to left"]}},
            {"label": {"en": ["Pressmark"]}, "value": {"en": [pressmark]}},
        ],
        "requiredStatement": {
            "label": {"en": ["Attribution"]},
            "value": {"en": ["Synthetic Library — test attribution"]},
        },
        "items": [
            {"id": MANIFEST_ID + "/items/0", "label": {"en": ["0"]}, "type": "Canvas"},
            {"id": MANIFEST_ID + "/items/1", "label": {"en": ["1"]}, "type": "Canvas"},
        ],
    }


@pytest.fixture
def nlc_case(roots, make_image):
    def make(*, directory="BD61234a", files=("BD61234a_0000_9.tif",), manifest=None, report=None, index=None):
        relative = PurePosixPath(NLC_CATEGORY) / directory
        path = roots["data"] / relative
        for filename in files:
            make_image(path / filename)
        attachments = {}
        for name, data in (("manifest", manifest), ("report", report), ("index", index)):
            if data is not None:
                raw = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False).encode("utf-8")
                (path / f"{name}.json").write_bytes(raw)
                attachments[name] = (path / f"{name}.json").read_bytes()
        units = build_units(scan(roots)).units
        assert len(units) == 1
        unit = units[0]
        result = parse_nlc(unit, attachments.get("manifest"), attachments.get("report"))
        return unit, result
    return make


@pytest.mark.parametrize(
    "directory,pressmark,key,category",
    [
        ("BD61234a", "BD61234a", "nlc:BD61234a", None),
        ("bd61234a", "BD61234A", "nlc:BD61234a", None),
        ("BD61234a", "BD61235b", "nlc:BD61235b", "编号与清单不一致"),
        ("BD1234", "BD61235b", "nlc:BD61235b", "编号与清单不一致"),
        ("BD61234a", "BD1234", None, "编号存疑"),
        ("BD61234a", "BD61234ab", None, "编号存疑"),
        ("BD61234a", "P.2345", None, "编号存疑"),
        ("BD61234a", "BD61234a extra", None, "编号存疑"),
        ("BD61234a", None, "nlc:BD61234a", "缺少清单"),
        ("BD1234", None, None, "缺少清单"),
    ],
)
def test_pressmark_authority(nlc_case, directory, pressmark, key, category):
    manifest = manifest_data(pressmark) if pressmark is not None else None
    unit, result = nlc_case(directory=directory, manifest=manifest, report={"strips": 2})
    assert result.parsed.keys == (frozenset({key}) if key else frozenset())
    identifiers = result.parsed.identifiers
    assert identifiers[0].raw == directory
    assert result.identifier_origins[0].source == "文件名解析"
    assert result.identifier_origins[0].relative_path == unit.relative_path
    assert result.identifier_origins[0].field == "name"
    if pressmark is not None:
        assert identifiers[1].raw == pressmark
        assert identifiers[1].normalized == pressmark
        assert result.identifier_origins[1].source == "外部清单"
        assert result.identifier_origins[1].relative_path == unit.relative_path / "manifest.json"
        assert result.identifier_origins[1].field == "metadata[1].value"
        assert identifiers[2].system == "idp"
        assert identifiers[2].raw == identifiers[2].normalized == "SYNTHETIC-ENTRY"
        assert identifiers[2].key is None  # 外部条目 ID 不能作为归并依据。
        assert result.identifier_origins[2].field == "id"
        if directory.casefold() != pressmark.casefold() or key is None:
            assert identifiers[0].key is None
            conflict = next(i for i in result.issues if i.category == "编号与清单不一致")
            assert conflict.relative_path == unit.relative_path
            assert conflict.raw == directory
        else:
            assert identifiers[0].key == key
            assert identifiers[0].normalized == pressmark
    if category is None:
        assert not result.issues
    else:
        assert category in {i.category for i in result.issues}
    assert len(identifiers) == len(result.identifier_origins)
    assert unit.parsed.identifiers[0].raw == directory  # 不原地修改单元。
    if pressmark is not None and key is None:
        issue = next(i for i in result.issues if i.category == "编号存疑")
        assert issue.raw == pressmark
        assert issue.relative_path == unit.relative_path / "manifest.json"


@pytest.mark.parametrize("strips", [2, 0, None])
def test_canvas_mapping(nlc_case, strips):
    unit, result = nlc_case(
        files=("BD61234a_0000_9.tif", "BD61234a_0001_8.tif"),
        manifest=manifest_data(), report={"strips": strips} if strips is not None else None,
    )
    assert result.canvases == {
        unit.relative_path / "BD61234a_0000_9.tif": CanvasRef(0, MANIFEST_ID + "/items/0"),
        unit.relative_path / "BD61234a_0001_8.tif": CanvasRef(1, MANIFEST_ID + "/items/1"),
    }
    assert not result.issues


def test_canvas_mapping_list_uses_file_and_index_not_order_or_filename(nlc_case):
    unit, result = nlc_case(
        files=("BD61234a_0000_9.tif", "BD61234a_0001_8.tif"), manifest=manifest_data(),
        report={"strips": [
            {"file": "BD61234a_0001_8.tif", "index": 0, "label": "other", "width": 7, "height": 5},
            {"file": "BD61234a_0000_9.tif", "index": 1, "label": "0", "width": 7, "height": 5},
            {"file": "BD61234a_0000_9.tif", "index": 1, "label": "0", "width": 7, "height": 5},
        ]},
    )
    assert result.canvases == {
        unit.relative_path / "BD61234a_0000_9.tif": CanvasRef(1, MANIFEST_ID + "/items/1"),
        unit.relative_path / "BD61234a_0001_8.tif": CanvasRef(0, MANIFEST_ID + "/items/0"),
    }
    assert not result.issues


@pytest.mark.parametrize("strips", [[], [{"file": "absent.tif", "index": 0}], [{"file": "BD61234a_0000_9.tif", "index": 2}]])
def test_canvas_mapping_list_does_not_fall_back(nlc_case, strips):
    unit, result = nlc_case(manifest=manifest_data(), report={"strips": strips})
    assert not result.canvases
    issue, = result.issues
    assert issue.category == "画布对不上"
    assert issue.relative_path == unit.images[0].file.relative_path
    assert issue.raw == "BD61234a_0000_9.tif"
    assert issue.reason


@pytest.mark.parametrize("filename", ["BD61234a_0002_0.tif", "whole.tif", "pages/0002_7x5.jpg", "pages/unknown.jpg"])
def test_canvas_mapping_unmatched_files(nlc_case, filename):
    unit, result = nlc_case(files=(filename,), manifest=manifest_data(), report={"strips": 0})
    assert not result.canvases
    issue, = result.issues
    assert issue.category == "画布对不上"
    assert issue.relative_path == unit.relative_path / filename


def test_canvas_mapping_pages_and_preview(nlc_case):
    unit, result = nlc_case(
        files=("pages/0000_7x5.jpg", "pages/0001_7x5.jpg", "BD61234a_preview.jpg"),
        manifest=manifest_data(), report={"strips": 0, "pages": 2},
        index=[{"index": 0, "label": "0", "url": "https://example.invalid/test.jpg"}],
    )
    assert result.canvases == {
        unit.relative_path / "pages/0000_7x5.jpg": CanvasRef(0, MANIFEST_ID + "/items/0"),
        unit.relative_path / "pages/0001_7x5.jpg": CanvasRef(1, MANIFEST_ID + "/items/1"),
    }
    assert {image.file.relative_path.name: image.role for image in unit.images} == {
        "0000_7x5.jpg": "页图", "0001_7x5.jpg": "页图", "BD61234a_preview.jpg": "另一版本",
    }
    assert {file.kind for file in unit.attachments} == {"manifest", "report", "index"}
    assert not result.issues


def test_attribution_is_passed_to_real_source_policy(nlc_case):
    data = manifest_data()
    data["requiredStatement"]["value"] = {"en": ["Synthetic Library", "Credit the photographer"], "zh": ["合成署名"]}
    data["structures"] = [{"label": {"en": ["UNUSED-LARGE-JSON-CONTENT" * 1000]}}]
    unit, result = nlc_case(manifest=data, report={"strips": 2})
    assert result.attribution == "Synthetic Library\nCredit the photographer\n合成署名"
    policy = source_policy(unit.images[0].file, "国图 IDP 下载", attribution=result.attribution)
    assert policy.attribution == result.attribution
    assert policy.basis["attribution"].source == "外部清单"
    assert "UNUSED-LARGE-JSON-CONTENT" not in repr(result)


def test_missing_manifest_has_no_attribution_or_canvas(nlc_case):
    unit, result = nlc_case(files=("pages/0000_7x5.jpg", "BD61234a_preview.jpg"))
    assert result.attribution is None
    assert not result.canvases
    assert result.parsed.keys == {"nlc:BD61234a"}
    assert {issue.category for issue in result.issues} == {"缺少清单", "画布对不上"}
    canvas_issue = next(i for i in result.issues if i.category == "画布对不上")
    assert canvas_issue.relative_path == unit.relative_path / "pages/0000_7x5.jpg"
    policy = source_policy(unit.images[0].file, "国图 IDP 下载", attribution=result.attribution)
    assert policy.basis["attribution"].source == "默认规则"


@pytest.mark.parametrize("raw", [b'{"metadata":', b'[]', b'\xff'])
def test_invalid_manifest_json_is_reported_not_trusted_as_missing(nlc_case, raw):
    unit, result = nlc_case(manifest=raw, report={"strips": 2})
    assert not result.parsed.keys
    assert not result.canvases
    categories = {issue.category for issue in result.issues}
    assert {"读不了的文件", "编号存疑", "编号与清单不一致", "画布对不上"} <= categories
    assert "缺少清单" not in categories
    issue = next(i for i in result.issues if i.category == "读不了的文件")
    assert issue.relative_path == unit.relative_path / "manifest.json"
    assert issue.root == "data"
    assert issue.reason


def test_missing_pressmark_keeps_directory_doubtful(nlc_case):
    data = manifest_data()
    data["metadata"] = data["metadata"][:1]
    _, result = nlc_case(manifest=data, report={"strips": 2})
    assert not result.parsed.keys
    assert result.parsed.identifiers[0].raw == "BD61234a"
    assert "编号存疑" in {issue.category for issue in result.issues}
    assert result.canvases  # 编号问题不妨碍独立的画布对应。


def test_manifest_field_types_and_canvas_positions(nlc_case):
    data = manifest_data()
    data["metadata"][1]["value"] = {"en": "BD61234a"}
    data["requiredStatement"]["value"] = "not a language map"
    data["id"] = 123
    data["items"][0]["id"] = None
    unit, result = nlc_case(
        files=("BD61234a_0000_9.tif", "BD61234a_0001_8.tif"), manifest=data, report={"strips": 2},
    )
    assert not result.parsed.keys
    assert result.attribution is None
    assert all(ident.system != "idp" for ident in result.parsed.identifiers)
    assert result.canvases == {unit.relative_path / "BD61234a_0001_8.tif": CanvasRef(1, MANIFEST_ID + "/items/1")}
    assert {issue.field for issue in result.issues if issue.category == "读不了的文件"} == {
        "metadata[1].value", "requiredStatement.value", "id", "items[0].id",
    }


@pytest.mark.parametrize("report", [b'{', [{"file": "irrelevant.tif", "index": 0}]])
def test_invalid_report_json_is_reported_and_filename_fallback_used(nlc_case, report):
    unit, result = nlc_case(manifest=manifest_data(), report=report)
    issue, = result.issues
    assert issue.category == "读不了的文件"
    assert issue.relative_path == unit.relative_path / "report.json"
    assert result.canvases[unit.images[0].file.relative_path].number == 0


@pytest.mark.parametrize("index", ["0", -1, True])
def test_invalid_strip_index_is_reported_without_filename_fallback(nlc_case, index):
    unit, result = nlc_case(
        manifest=manifest_data(), report={"strips": [{"file": "BD61234a_0000_9.tif", "index": index}]},
    )
    assert not result.canvases
    assert {issue.category for issue in result.issues} == {"读不了的文件", "画布对不上"}
    issue = next(i for i in result.issues if i.category == "读不了的文件")
    assert issue.relative_path == unit.relative_path / "report.json"
    assert issue.field == "strips[0]"


@pytest.mark.parametrize("pressmark,key", [("BD61235B", "nlc:BD61235b"), ("BD1234", None)])
def test_parsed_override_before_identity_calculation(nlc_case, pressmark, key):
    unit, result = nlc_case(manifest=manifest_data(pressmark), report={"strips": 2})
    assert unit.parsed.keys == {"nlc:BD61234a"}
    unit.parsed = result.parsed
    images = resolve_images([], [image.file for image in unit.images], run=1)
    items = resolve_items([], [unit], images.images)
    item, = items.items
    assert item.grouping_key == key
    assert len(item.image_ids) == 1
    assert any(sourced.value.system == "idp" for sourced in item.identifiers)
    assert len(item.identifiers) == len(result.parsed.identifiers)
    assert not items.pending
