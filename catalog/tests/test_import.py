"""真实文件流水线及 PostgreSQL 集成；只有 HTTP 边界用 MockTransport。"""

import base64
from contextlib import contextmanager, nullcontext
from copy import deepcopy
from datetime import UTC, datetime, timedelta
import gc
import json
import os
from pathlib import Path, PurePosixPath
import re
import struct
import subprocess
import sys
import tempfile
from uuid import uuid4
import weakref

import httpx
import psycopg
import pytest
from psycopg.pq import TransactionStatus
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from dh_catalog import importer, rules
from dh_catalog._compact import CompactMap
from dh_catalog.config import load_settings
from dh_catalog.db import ImportBusy, create_pool
from dh_catalog.derivation import CACHE_FILES
from dh_catalog.importer import (
    CatalogState, _BasisPool, _basis, _json_value, build_report, compute_import, latest_valid_snapshot,
    load_catalog_state, prepare_import,
    read_report, value_at_run,
)
from dh_catalog.v0 import IndexFetch, V0Client


@pytest.fixture
def cache(tmp_path):
    path = tmp_path / "v0cache"
    path.mkdir()
    for name in CACHE_FILES:
        key = {"seg_move_plan.json": "plan", "samefolder_plan.json": "has_merged", "validated_moves.json": "moves"}.get(name)
        (path / name).write_text(json.dumps({key: []}) if key else "", encoding="utf-8")
    return path


@pytest.fixture
def host_records(roots, cache, make_image):
    """Synthetic legacy paths are record text only, distinct from the temporary scan roots."""
    directory = "敦煌003/P2002"
    make_image(roots["data"] / directory / "合并长卷.tif")
    make_image(roots["backup"] / directory / "分段/native.tif")
    make_image(roots["backup"] / directory / "分段/processed.tif", software="Photoshop synthetic")
    (cache / "merge_all.log").write_text(
        f"===== 10:00:00 开始: /srv/legacy/segments/{directory}/分段 =====\n"
        "分片 2 个\nnative.tif x0= 0 w= 7\nprocessed.tif x0= 0 w= 7\n"
        f"完成: /srv/legacy/images/{directory}/合并长卷.tif  14 x 5\n退出码: 0\n",
        encoding="utf-8",
    )
    return {"DH_RECORD_DATA_ROOT": " /srv/legacy/images ",
            "DH_RECORD_BACKUP_ROOT": "/srv/legacy/segments/",
            "DH_V0_ENV_FILE": str(cache / "absent.env")}


def _manifest(number="BD12345", entry="synthetic-entry"):
    return json.dumps({
        "id": f"https://example.invalid/manifest/{entry}",
        "metadata": [{"label": {"en": ["Pressmark"]}, "value": {"en": [number]}}],
        "requiredStatement": {"value": {"en": ["Synthetic Library"]}},
        "items": [{"id": "https://example.invalid/canvas/0"}],
    }, ensure_ascii=False).encode()


def _compute(roots, cache, *, previous=None, run=1, sink=None):
    # sink 只消费文件读取结果；不实现数据库或身份算法。
    return compute_import(roots, cache, run_id=run, previous=previous,
                          attachment_sink=sink or (lambda file, raw: uuid4()))


def _state(result):
    # 将真实计算产物作为下一轮的 S0，不模拟 SQL 或业务算法。
    return CatalogState(result.images, result.items, result.identifiers, result.links,
                        result.derivations, result.item_attachments)


def _report(result, previous=None, fetch=None):
    return build_report(result, previous or CatalogState(), fetch or IndexFetch(None, "synthetic unavailable"))


def _fetch(directories=(), *, ready=True):
    def handler(request):
        assert request.headers["cookie"] == "dh_session=caller-cookie"
        ids = [base64.urlsafe_b64encode(path.encode()).decode().rstrip("=") for path in directories]
        return httpx.Response(200, json={"status": "ready" if ready else "building", "items": [{"id": value} for value in ids]})
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        with V0Client("http://v0.test", "caller-cookie", http) as client:
            return client.fetch_index()


def test_nlc_authority_precedes_identity_and_no_stale_no_number_issue(roots, cache, make_image):
    directory = roots["data"] / "中国国博馆藏/无目录编号"
    make_image(directory / "BD12345_0000_0.tif")
    (directory / "manifest.json").write_bytes(_manifest())
    result = _compute(roots, cache)
    item, = result.items.values()
    assert item["grouping_key"] == "nlc:BD12345"
    assert "无馆藏号的写卷单元" not in {a["category"] for a in result.anomalies}
    image, = result.images.values()
    assert image["canvas_number"] == 0 and image["attribution"] == "Synthetic Library"
    assert image["license"] == rules.IDP_LICENSE
    assert image["field_basis"]["attribution"]["source"] == "外部清单"


def test_nlc_preserves_both_origins_but_only_one_primary(roots, cache, make_image):
    directory = roots["data"] / "中国国博馆藏/bd12345"
    make_image(directory / "BD12345_0000_0.tif")
    (directory / "manifest.json").write_bytes(_manifest())
    result = _compute(roots, cache)
    identifiers, = result.identifiers.values()
    assert len(identifiers) == 3
    primary, = [i for i in identifiers if i["is_primary"]]
    assert primary["source"] == "外部清单"
    assert {i["raw"] for i in identifiers} == {"bd12345", "BD12345", "synthetic-entry"}
    assert "编号存疑" not in {a["category"] for a in result.anomalies}


def test_nlc_authority_does_not_override_outside_vocabulary_child(roots, cache, make_image):
    directory = roots["data"] / "中国国博馆藏/BD12345"
    child = directory / "P2003"
    make_image(directory / "BD12345_0000_0.tif")
    make_image(child / "native.tif")
    (directory / "manifest.json").write_bytes(_manifest())
    (child / "说明.txt").write_bytes(b"child original attachment")
    consumed = {}
    def consume(file, raw):
        consumed[file] = raw
        return uuid4()
    result = _compute(roots, cache, sink=consume)
    assert {row["grouping_key"] for row in result.items.values()} == {"nlc:BD12345", "pelliot:2003"}
    owner = next(row["id"] for row in result.items.values() if row["grouping_key"] == "pelliot:2003")
    image = next(row for row in result.images.values() if row["relative_path"].endswith("P2003/native.tif"))
    assert (owner, image["id"]) in result.links
    assert set(result.nlc) == {"data:中国国博馆藏/BD12345"}
    attachment = next(file for file in result.attachments if file.kind == "text")
    assert result.item_attachments[owner] == {result.attachments[attachment]}
    assert consumed[attachment] == b"child original attachment"
    assert any(a["category"] == "词表外子目录" and a["relative_path"] == "中国国博馆藏/BD12345/P2003"
               for a in result.anomalies)
    assert not any(a["category"] == "编号存疑" and a["raw"] == "P2003" for a in result.anomalies)


def test_identifier_read_order_does_not_report_item_change(roots, cache, make_image):
    directory = roots["data"] / "中国国博馆藏/bd12345"
    make_image(directory / "BD12345_0000_0.tif")
    (directory / "manifest.json").write_bytes(_manifest())
    first = _compute(roots, cache)
    previous = _state(first)
    owner, = previous.items
    assert len(previous.identifiers[owner]) == 3
    assert {row["source"] for row in previous.identifiers[owner]} == {"文件名解析", "外部清单"}
    previous.identifiers = {owner: list(reversed(previous.identifiers[owner]))}
    second = _compute(roots, cache, previous=previous, run=2, sink=lambda file, raw: first.attachments[file])
    assert second.identifiers[owner] == first.identifiers[owner]
    assert second.identifiers[owner] != previous.identifiers[owner]
    assert second.items == previous.items
    assert _report(second, previous)["counts"]["changes"]["items"] == {"new": 0, "changed": 0}


def test_derivation_license_and_unknown_source_not_inherited_from_old_state(roots, cache, make_image):
    directory = roots["data"] / "敦煌003/P2002"
    make_image(directory / "native.tif")
    make_image(directory / "合并长卷.tif")
    (cache / "merge_all.log").write_text(
        "===== 10:00:00 开始: 敦煌003/P2002 =====\n分片 1 个\nnative.tif x0= 0 w= 7\n"
        "完成: /data/敦煌003/P2002/合并长卷.tif  7 x 5\n退出码: 0\n", encoding="utf-8")
    first = _compute(roots, cache)
    output = next(row for row in first.images.values() if row["lineage"] == "本地合成")
    assert output["license"] == rules.GALLICA_LICENSE
    assert len(first.derivations) == 1
    (directory / "native.tif").unlink()
    second = _compute(roots, cache, previous=_state(first), run=2)
    assert second.images[output["id"]]["license"] == "未知"
    assert not second.derivations
    assert "派生来源不明" in {a["category"] for a in second.anomalies}


def test_configured_record_roots_reach_computation_and_strictest_license(roots, cache, host_records):
    settings = load_settings(host_records)
    unknown = _compute(roots, cache)
    output = next(row for row in unknown.images.values() if row["lineage"] == "本地合成")
    assert output["license"] == rules.UNKNOWN_LICENSE and not unknown.derivations
    assert any("不是 data / backup" in issue.reason for issue in unknown.derivation.issues)
    known = compute_import(roots, cache, run_id=2, previous=_state(unknown),
                           attachment_sink=lambda file, raw: uuid4(), record_roots=settings.record_roots)
    assert set(known.images) == set(unknown.images) and set(known.items) == set(unknown.items)
    after = known.images[output["id"]]
    assert len(known.derivations) == 2 and not known.derivation.issues
    sources = [row for row in known.images.values() if row["root"] == "backup"]
    assert {row["license"] for row in sources} == {rules.GALLICA_LICENSE, rules.PROCESSED_LICENSE}
    assert after["license"] == rules.PROCESSED_LICENSE and after["display_policy"] == "仅供研究使用"
    assert after["external_policy"] == "不对外" and after["collection"] == "法国国家图书馆"
    assert after["attribution"] == "Source gallica.bnf.fr / BnF"
    assert after["acquisition"] == rules.LOCAL_EVENT
    assert {row["acquisition"] for row in sources} == {"第三方资料接收（接收事件 A）"}
    assert after["field_basis"]["license"]["source_images"] == sorted(str(row["id"]) for row in sources)
    assert {edge["source_image_id"] for edge in known.derivations.values()} == {row["id"] for row in sources}
    assert all(edge["image_id"] == output["id"] and edge["method"] == "拼接"
               and edge["evidence_file"] == "merge_all.log" and edge["evidence_line"] == 5
               for edge in known.derivations.values())
    assert output["license"] == rules.UNKNOWN_LICENSE  # Previous computation remains unchanged.


@contextmanager
def _observe_image_policy():
    """只留弱引用/标量；真实帧与 f_locals 不跨 profile 回调保存。"""
    observed = {"refs": [], "image_returns": [], "item_calls": [], "calls": [], "resolved": []}
    init_code = importer._ImagePolicyResolver.__init__.__code__
    call_code = importer._ImagePolicyResolver.__call__.__code__

    def profile(frame, event, arg):
        if event == "return" and frame.f_code is init_code:
            observed["refs"].append(weakref.ref(frame.f_locals["self"]))
        elif event == "call" and frame.f_code is call_code:
            observed["calls"].append(str(frame.f_locals["file"].relative_path))
        elif event == "return" and frame.f_code is rules.source_policy.__code__:
            observed["resolved"].append(str(frame.f_locals["file"].relative_path))
        elif event == "return" and frame.f_code is importer._image_rows.__code__:
            # return 事件时帧仍活；正常返回不能误要求解析器此刻已死。
            observed["image_returns"].append(observed["refs"][-1]() is not None)
        elif event == "call" and frame.f_code is importer._item_rows.__code__:
            observed["item_calls"].append(all(ref() is None for ref in observed["refs"]))

    previous_profile, gc_enabled = sys.getprofile(), gc.isenabled()
    try:
        gc.disable()  # 只限小型真实 compute，旧自环不能靠自动 GC 假绿。
        sys.setprofile(profile)
        yield observed
    finally:
        sys.setprofile(previous_profile)
        if gc_enabled:
            gc.enable()
        else:
            gc.disable()


def _write_policy_stitches(cache, directory, steps):
    # 合成同形执行记录，仍由生产 derivation 解析，不直接构造派生边。
    (cache / "merge_all.log").write_text("".join(
        f"===== 10:00:00 开始: {directory} =====\n分片 {len(sources)} 个\n"
        + "".join(f"{source} x0= 0 w= 7\n" for source in sources)
        + f"完成: /data/{directory}/{output}  7 x 5\n退出码: 0\n"
        for output, sources in steps
    ), encoding="utf-8")


@pytest.mark.parametrize("case", ["nlc", "nlc-default", "bnf", "derived", "unreadable"])
def test_image_policy_lifetime_without_gc(roots, cache, make_image, case):
    directory = "中国国博馆藏/BD12345" if case.startswith("nlc") else "敦煌003/P2002"
    name = "BD12345_0000_0.tif" if case.startswith("nlc") else "native.tif"
    path = make_image(roots["data"] / directory / name)
    if case == "nlc":
        (path.parent / "manifest.json").write_bytes(_manifest())
    elif case == "derived":
        for filename in ("a-final.tif", "b-middle.tif", "processed.tif"):
            make_image(path.parent / filename, software="Photoshop synthetic")
        _write_policy_stitches(cache, directory, [
            ("b-middle.tif", ["native.tif"]),
            ("a-final.tif", ["b-middle.tif", "native.tif", "processed.tif"]),
        ])
    elif case == "unreadable":
        path.write_bytes(b"broken TIFF")

    previous_profile, gc_enabled = sys.getprofile(), gc.isenabled()
    with _observe_image_policy() as observed:
        result = _compute(roots, cache)
        assert len(observed["refs"]) == 1
        assert observed["image_returns"] == [True]
        assert observed["item_calls"] == [True]
        assert observed["refs"][0]() is None  # result 仍活，普通字段不能钉住解析器。
    assert sys.getprofile() is previous_profile and gc.isenabled() == gc_enabled
    rows = {PurePosixPath(row["relative_path"]).name: row for row in result.images.values()}
    assert sorted(observed["resolved"]) == sorted(row["relative_path"] for row in rows.values())
    image = rows[name]
    item, = result.items.values()
    if case.startswith("nlc"):
        assert image["lineage"] == "国图 IDP 下载" and image["license"] == rules.IDP_LICENSE
        assert image["attribution"] == ("Synthetic Library" if case == "nlc" else "The National Library of China")
        assert image["field_basis"]["attribution"]["source"] == ("外部清单" if case == "nlc" else "默认规则")
        assert image["collection"] == "中国国家图书馆" and image["acquisition"] == rules.DOWNLOAD_EVENT
    elif case == "unreadable":
        assert not image["read_ok"] and image["lineage"] == "未判定"
        assert image["license"] == rules.UNKNOWN_LICENSE and image["display_policy"] == "仅供研究使用"
        assert any(a["category"] == "读不了的文件" for a in result.anomalies)
    else:
        assert image["lineage"] == "BnF 原图" and image["license"] == rules.GALLICA_LICENSE
        assert image["attribution"] == "Source gallica.bnf.fr / BnF"
        assert image["acquisition"] == rules.TRANSFER_EVENT
    assert item["display_policy"] == ("仅供研究使用" if case in {"derived", "unreadable"} else "登录墙内可展示")
    if case == "derived":
        final, middle, processed = (rows[name] for name in ("a-final.tif", "b-middle.tif", "processed.tif"))
        assert observed["calls"][0] == final["relative_path"]  # 输出先扫描，确实走多层递归。
        assert observed["calls"].count(image["relative_path"]) == 3  # 递归与外层再次调用命中 memo。
        assert observed["resolved"] == [image["relative_path"], middle["relative_path"],
                                         processed["relative_path"], final["relative_path"]]
        assert not result.derivation.issues and len(result.derivations) == 4
        assert middle["license"] == rules.GALLICA_LICENSE and middle["display_policy"] == "登录墙内可展示"
        assert final["license"] == processed["license"] == rules.PROCESSED_LICENSE
        assert final["display_policy"] == "仅供研究使用" and final["external_policy"] == "不对外"
        assert final["attribution"] == middle["attribution"] == image["attribution"]
        assert final["collection"] == processed["collection"] == "法国国家图书馆"
        assert processed["field_basis"]["collection"]["confidence"] == "推断"
        for output, sources in ((middle, [image]), (final, [middle, image, processed])):
            assert output["lineage"] == "本地合成" and output["acquisition"] == rules.LOCAL_EVENT
            assert output["field_basis"]["lineage"]["source"] == "执行记录"
            assert output["field_basis"]["license"]["source_images"] == sorted(str(row["id"]) for row in sources)
            assert output["field_basis"]["license"]["author"] == "rule:license-local-inherit@" + rules.RULE_VERSION


def test_image_policy_exception_releases_after_traceback(roots, cache, make_image):
    directory = "敦煌003/P2002"
    for name in ("a.tif", "b.tif"):
        make_image(roots["data"] / directory / name)
    # 真实记录形成互相依赖，原递归异常必须传播；不增加生产循环恢复规则。
    _write_policy_stitches(cache, directory, [("a.tif", ["b.tif"]), ("b.tif", ["a.tif"])])
    previous_profile, gc_enabled = sys.getprofile(), gc.isenabled()
    with _observe_image_policy() as observed:
        with pytest.raises(RecursionError) as failure:
            _compute(roots, cache)
        assert len(observed["refs"]) == 1 and not observed["item_calls"]
        assert failure.value.__traceback__ is not None
        assert observed["refs"][0]() is not None  # traceback 合法持帧，不误判泄漏。
        del failure  # 释放测试持有的异常/帧，不用 gc.collect 制造通过。
        assert observed["refs"][0]() is None
    assert sys.getprofile() is previous_profile and gc.isenabled() == gc_enabled


def test_attachments(roots, cache, make_image):
    directory = roots["data"] / "敦煌003/P2002+2003"
    make_image(directory / "native.tif")
    locations = [directory / "HD/说明.txt", roots["data"] / "敦煌003/只有附件/说明.txt",
                 roots["data"] / "敦煌003/分类说明.txt"]
    for path in locations:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"\xff raw\r\n")
    consumed = []
    result = _compute(roots, cache, sink=lambda file, raw: consumed.append((file, raw)) or uuid4())
    assert len(result.items) == 2
    assert len(consumed) == 3 and all(raw == b"\xff raw\r\n" for _, raw in consumed)
    assert all(len(ids) == 1 for ids in result.item_attachments.values())
    report = _report(result)
    assert len(report["unassigned_attachments"]) == 2
    assert report["counts"]["attachments_by_kind"] == {"text": 3}
    assert "缺少影像" in {a["category"] for a in result.anomalies}


def test_attachment_read_failure_is_not_empty_original(roots, cache, make_image):
    directory = roots["data"] / "敦煌003/P2002"
    make_image(directory / "native.tif")
    first, second = directory / "a.txt", directory / "b.txt"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    consumed = []
    def consume(file, raw):
        consumed.append(raw)
        second.unlink()  # 真实的扫描后读取失败，不 mock 文件操作。
        return uuid4()
    with pytest.raises(FileNotFoundError):
        _compute(roots, cache, sink=consume)
    assert consumed == [b"first"]


def test_unreadable_file_retried_and_recovers(roots, cache, make_image):
    path = roots["data"] / "敦煌003/P2002/native.tif"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"broken")
    first = _compute(roots, cache)
    second = _compute(roots, cache, previous=_state(first), run=2)
    assert all(not reading.reused and reading.error for reading in second.readings.values())
    make_image(path)
    third = _compute(roots, cache, previous=_state(second), run=3)
    assert set(first.images) == set(third.images)
    assert all(not reading.error for reading in third.readings.values())
    assert "读不了的文件" not in {a["category"] for a in third.anomalies}
    fourth = _compute(roots, cache, previous=_state(third), run=4)
    assert all(reading.reused for reading in fourth.readings.values())


def test_jpeg_decompression_bomb_does_not_abort_import_and_recovers(roots, cache, make_image):
    relative = "中国国博馆藏/BD12345/BD12345_preview.jpg"
    path = make_image(roots["data"] / relative, dpi=(180, 180))
    valid = path.read_bytes()
    header = bytearray(valid)
    sof = header.index(b"\xff\xc0")
    # 合成文件仍只有几百字节；只让文件头触发真实 Pillow 安全异常。
    header[sof + 5:sof + 9] = struct.pack(">HH", 20000, 20000)
    path.write_bytes(header)
    make_image(roots["data"] / "敦煌003/P2002/native.tif")
    first = _compute(roots, cache)
    image = next(row for row in first.images.values() if row["relative_path"] == relative)
    healthy = next(row for row in first.images.values() if row["kind"] == "tiff")
    assert not image["read_ok"] and image["read_error"].startswith("DecompressionBombError:")
    assert image["lineage"] == "国图 IDP 下载" and image["state"] == "present"
    assert {name: fact["status"] for name, fact in image["facts"].items()} == {
        "pixel_size": "missing", "channels": "missing", "color_mode": "missing",
        "bit_depth": "missing", "resolution": "missing",
        "compression": "not_applicable", "software": "not_applicable",
    }
    assert healthy["read_ok"] and healthy["lineage"] == "BnF 原图"
    assert {row["grouping_key"] for row in first.items.values()} == {"nlc:BD12345", "pelliot:2002"}
    report = _report(first)
    assert report["counts"]["present_images"] == report["counts"]["items"] == 2
    issue, = [a for a in report["anomalies"] if a["category"] == "读不了的文件"]
    assert issue == {
        "category": "读不了的文件", "object_kind": "image", "object_key": f"data:{relative}",
        "root": "data", "relative_path": relative, "raw": path.name,
        "description": image["read_error"],
    }
    assert report["counts"]["anomalies_by_category"]["读不了的文件"] == 1

    second = _compute(roots, cache, previous=_state(first), run=2)
    failed_reading = next(r for f, r in second.readings.items() if str(f.relative_path) == relative)
    assert failed_reading.error == image["read_error"] and not failed_reading.reused
    assert _report(second, _state(first))["counts"]["facts_reused"] == 1
    assert [a for a in _report(second, _state(first))["anomalies"] if a["category"] == "读不了的文件"] == [issue]

    path.write_bytes(valid)
    third = _compute(roots, cache, previous=_state(second), run=3)
    repaired = third.images[image["id"]]
    assert repaired["read_ok"] and repaired["read_error"] is None
    assert repaired["facts"]["pixel_size"] == {"status": "value", "value": [7, 5]}
    assert repaired["facts"]["resolution"] == {"status": "value", "value": [180.0, 180.0, "INCH"]}
    assert all(not r.error for r in third.readings.values())
    assert not next(r for f, r in third.readings.items() if str(f.relative_path) == relative).reused
    recovered_report = _report(third, _state(second))
    assert "读不了的文件" not in {a["category"] for a in recovered_report["anomalies"]}
    assert recovered_report["counts"]["facts_reused"] == 1
    for result in (second, third):
        assert set(result.images) == set(first.images)
        assert set(result.items) == set(first.items)
        assert set(result.links) == set(first.links)
        assert result.identifiers == first.identifiers
        assert result.images[image["id"]]["lineage"] == "国图 IDP 下载"
        assert result.images[healthy["id"]]["read_ok"]
    fourth = _compute(roots, cache, previous=_state(third), run=4)
    assert all(r.reused and not r.error for r in fourth.readings.values())


def test_raw_names_verbatim(roots, cache, make_image):
    relative = "敦煌003/P.2002 Plainte judiciaire ＋---/.原图.tif"
    make_image(roots["data"] / relative)
    result = _compute(roots, cache)
    row, = result.images.values()
    assert row["original_path"] == row["relative_path"] == relative
    assert row["original_name"] == ".原图.tif" and row["hidden"]
    item, = result.items.values()
    assert item["original_positions"][0]["name"] == "P.2002 Plainte judiciaire ＋---"


def test_field_basis_and_author(roots, cache, make_image):
    make_image(roots["data"] / "敦煌003/P2002/native.tif")
    first = _compute(roots, cache)
    image, = first.images.values()
    assert image["field_basis"]["facts"]["pixel_size"]["confidence"] == "确定"
    assert image["field_basis"]["lineage"]["confidence"] == "推断"
    assert image["field_basis"]["lineage"]["author"].endswith("@" + rules.RULE_VERSION)
    second = _compute(roots, cache, previous=_state(first), run=2)
    assert image["field_basis"] == second.images[image["id"]]["field_basis"]
    item, = first.items.values()
    assert item == second.items[item["id"]]
    assert all(b["run"] == 1 for b in second.links[next(iter(second.links))]["field_basis"].values())


def test_basis_and_fact_leaves_shared_but_field_maps_independent(roots, cache, make_image):
    paths = [make_image(roots["data"] / f"敦煌003/P2002/native({n}).tif") for n in range(2)]
    at = datetime(2026, 10, 29, tzinfo=UTC)
    first = compute_import(roots, cache, run_id=1, at=at, attachment_sink=lambda file, raw: uuid4())
    left, right = first.images.values()
    assert type(first.images) is dict
    for row in (left, right):
        for mapping in (row, row["facts"], row["field_basis"], row["field_basis"]["facts"]):
            assert isinstance(mapping, CompactMap)
            with pytest.raises(TypeError):
                mapping["unexpected"] = None
    assert left._shape is right._shape
    assert left["field_basis"]._shape is right["field_basis"]._shape
    assert all(type(row) is dict for rows in (first.items, first.links, first.derivations) for row in rows.values())
    assert all(type(row) is dict for rows in first.identifiers.values() for row in rows)
    expected = {"source": "文件头", "author": "rule:file-header@" + rules.RULE_VERSION,
                "confidence": "确定", "run": 1, "at": at.isoformat()}
    assert json.loads(json.dumps(left["field_basis"]["facts"]["pixel_size"])) == expected
    assert left["field_basis"]["facts"]["pixel_size"] is right["field_basis"]["facts"]["channels"]
    assert left["facts"]["pixel_size"] is right["facts"]["pixel_size"]
    assert type(left["facts"]["pixel_size"]["value"]) is list
    assert left["field_basis"] is not right["field_basis"]
    assert left["field_basis"]["facts"] is not right["field_basis"]["facts"]
    assert left["facts"] is not right["facts"]
    before = {
        key: json.dumps(_json_value(row), sort_keys=True) for key, row in first.images.items()
    }
    unchanged = _compute(roots, cache, previous=_state(first), run=2)
    assert _report(unchanged, _state(first))["counts"]["changes"]["images"]["metadata_changed"] == 0
    # 真实改一个文件；未变字段仍用原依据，变化不得污染另一影像或 S0。
    replacement = make_image(paths[0].parent / "replacement.tif", software="Photoshop synthetic")
    os.replace(replacement, paths[0])
    changed = _compute(roots, cache, previous=_state(first), run=3)
    row = next(r for r in changed.images.values() if r["relative_path"].endswith(paths[0].name))
    assert row["field_basis"]["facts"]["software"]["run"] == 3
    assert row["field_basis"]["facts"]["channels"]["run"] == 1
    assert row["facts"]["channels"] == first.images[row["id"]]["facts"]["channels"]
    assert {key: json.dumps(_json_value(value), sort_keys=True) for key, value in first.images.items()} == before
    other = next(r for r in changed.images.values() if r["id"] != row["id"])
    assert other["facts"]["software"]["status"] == "missing"
    with pytest.raises(TypeError):
        row["field_basis"]["facts"]["channels"] = dict(expected, author="user:synthetic")
    with pytest.raises(TypeError):
        row["facts"]["channels"] = {"status": "value", "value": 99}
    copied_basis = dict(row["field_basis"]["facts"])
    copied_facts = dict(row["facts"])
    copied_basis["channels"] = dict(expected, author="user:synthetic")
    copied_facts["channels"] = {"status": "value", "value": 99}
    assert copied_basis["channels"]["author"] == "user:synthetic"
    assert copied_facts["channels"]["value"] == 99
    assert row["field_basis"]["facts"]["channels"] == expected
    assert row["facts"]["channels"]["value"] == 3
    assert other["field_basis"]["facts"]["channels"] == expected
    assert first.images[row["id"]]["field_basis"]["facts"]["channels"] == expected
    assert other["facts"]["channels"]["value"] == 3
    assert first.images[row["id"]]["facts"]["channels"]["value"] == 3


def test_basis_run_time_and_rule_version_isolation(roots, cache, make_image):
    make_image(roots["data"] / "敦煌003/P2002/native.tif")
    at = datetime(2026, 10, 29, tzinfo=UTC)
    def compute(run, time, previous=None):
        return compute_import(roots, cache, run_id=run, at=time, previous=previous,
                              attachment_sink=lambda file, raw: uuid4())
    first = compute(1, at)
    original, = first.images.values()
    for run, time in ((2, at), (1, at + timedelta(seconds=1))):
        fresh, = compute(run, time).images.values()
        assert fresh["field_basis"]["lineage"]["run"] == run
        assert fresh["field_basis"]["lineage"]["at"] == time.isoformat()
        assert fresh["field_basis"]["lineage"] != original["field_basis"]["lineage"]
    version = rules.RULE_VERSION
    try:
        # 改真实规则配置而非替换规则算法；缓存必须读取当前版本。
        rules.RULE_VERSION = version + ".test"
        changed = compute(3, at + timedelta(seconds=2), _state(first))
        row = changed.images[original["id"]]
        for leaf in (row["field_basis"]["lineage"], row["field_basis"]["facts"]["channels"],
                     row["field_basis"]["collection"]):
            assert leaf["author"].endswith("@" + rules.RULE_VERSION)
            assert leaf["run"] == 3 and leaf["at"] == (at + timedelta(seconds=2)).isoformat()
        assert original["field_basis"]["lineage"]["author"].endswith("@" + version)
    finally:
        rules.RULE_VERSION = version
    restored, = compute(4, at).images.values()
    assert restored["field_basis"]["lineage"]["author"].endswith("@" + version)


def test_basis_pool_full_semantics_and_bounded_lifetime():
    at = datetime(2026, 10, 29, tzinfo=UTC)
    pool = _BasisPool(1, at)
    meaning = {"source": "执行记录", "author": "rule:synthetic@v1", "confidence": "确定",
               "unit_key": "data:甲", "location": "log:1", "location_field": "name",
               "source_images": ["image-a", "image-b"], "identifier_sources": ["data:甲"]}
    leaf = _basis({"value": 1}, {"value": meaning}, {}, pool)["value"]
    assert leaf == dict(meaning, run=1, at=at.isoformat())
    assert leaf is pool.share(json.loads(json.dumps(leaf)))
    for name, value in {"author": "rule:synthetic@v2", "run": 2, "at": "another-time",
                        "unit_key": "data:乙", "location": "log:2", "location_field": "Pressmark",
                        "source_images": ["image-b", "image-a"], "identifier_sources": ["data:乙"],
                        "source": "人工", "confidence": "推断"}.items():
        changed = dict(leaf, **{name: value})
        assert pool.share(changed) == changed and pool.share(changed) is not leaf
    assert type(leaf["source_images"]) is type(leaf["identifier_sources"]) is list
    assert type(pool.share({"status": "value", "value": 1})["value"]) is int
    assert type(pool.share({"status": "value", "value": 1.0})["value"]) is float
    # 连续加载不同位置不会把任意历史依据永久积存在缓存中。
    for n in range(4200):
        pool.share(dict(leaf, location=f"log:{n}"))
    assert pool._leaf.cache_info().currsize == 4096
    assert pool.text.cache_info().currsize <= 512
    assert _BasisPool().share(leaf) is not leaf
    assert leaf == dict(meaning, run=1, at=at.isoformat())


def test_rule_version_change_is_field_history_not_forced_value_change(roots, cache, make_image):
    make_image(roots["data"] / "敦煌003/P2002/native.tif")
    first = _compute(roots, cache)
    image, = first.images.values()
    old_basis = image["field_basis"]["facts"]["pixel_size"]
    previous = _state(first)
    builder = dict(image)
    builder["field_basis"] = dict(image["field_basis"])
    builder["field_basis"]["facts"] = dict(image["field_basis"]["facts"])
    builder["field_basis"]["facts"]["pixel_size"] = dict(old_basis, author="rule:file-header@previous-version")
    previous.images = dict(previous.images)
    previous.images[image["id"]] = builder
    second = _compute(roots, cache, previous=previous, run=2)
    after = second.images[image["id"]]
    assert after["facts"] == image["facts"]
    assert after["field_basis"]["facts"]["pixel_size"]["author"] == "rule:file-header@" + rules.RULE_VERSION
    assert after["field_basis"]["facts"]["pixel_size"]["run"] == 2
    assert after["field_basis"]["facts"]["channels"]["run"] == 1
    assert _report(second, previous)["counts"]["changes"]["images"]["metadata_changed"] == 1
    assert image["field_basis"]["facts"]["pixel_size"] is old_basis
    assert old_basis["author"] == "rule:file-header@" + rules.RULE_VERSION


def _previous_identifier_basis(row):
    # 合成旧部署输入；逐层新建，不改真实规则配置或共享的依据叶。
    return {name: dict(leaf, author="rule:identifier@previous-version")
            for name, leaf in row["field_basis"].items()}


@pytest.mark.parametrize("with_id", [False, True], ids=["compute-s0", "persisted-s0"])
def test_identifier_basis_upgrade_preserves_tenure_and_s0(roots, cache, make_image, with_id):
    base = roots["data"] / "敦煌003"
    for name in ("P2002", "P2003"):
        make_image(base / name / "native.tif")
    directory = roots["data"] / "中国国博馆藏/bd12345a"
    make_image(directory / "BD12345a_0000_0.tif")
    (directory / "manifest.json").write_bytes(_manifest("BD12345a"))
    first = _compute(roots, cache)
    sink = lambda file, raw: first.attachments[file]
    (base / "P2002").rename(base / "副本 P2003")
    pending = _compute(roots, cache, previous=_state(first), run=2, sink=sink)
    owner = next(key for key, row in pending.items.items() if row["grouping_key"] == "pelliot:2002")
    nlc_owner = next(key for key, row in pending.items.items() if row["grouping_key"] == "nlc:BD12345a")
    assert {(r["normalized"], r["state"], r["since_run"]) for r in pending.identifiers[owner]} == {
        ("P.2002", "current", 1), ("P.2003", "pending", 2),
    }
    nlc_rows = pending.identifiers[nlc_owner]
    assert {(r["system"], r["raw"], r["normalized"], r["source"], r["is_primary"]) for r in nlc_rows} == {
        ("nlc", "bd12345a", "BD12345a", "文件名解析", False),
        ("nlc", "BD12345a", "BD12345a", "外部清单", True),
        ("idp", "synthetic-entry", "synthetic-entry", "外部清单", False),
    }
    assert all(r["parent_number"] == "BD12345" and r["part"] == "a" for r in nlc_rows if r["system"] == "nlc")
    previous = _state(pending)
    previous.identifiers = {
        key: [dict(row, field_basis=_previous_identifier_basis(row)) if key in {owner, nlc_owner}
              else dict(row) for row in rows]
        for key, rows in previous.identifiers.items()
    }
    if with_id:
        for number, row in enumerate((r for rows in previous.identifiers.values() for r in rows), 1):
            row["id"] = number  # 合成已持久化 S0 的元数据，不模拟 SQL。
    before = deepcopy(previous)
    original = deepcopy(pending.identifiers)
    references = [(key, index, row, row["field_basis"], dict(row["field_basis"]))
                  for key, rows in previous.identifiers.items() for index, row in enumerate(rows)]
    at = datetime(2026, 10, 30, tzinfo=UTC)
    upgraded = compute_import(roots, cache, previous=previous, run_id=3, at=at, attachment_sink=sink)
    assert previous == before and pending.identifiers == original
    for key, index, row, fields, leaves in references:
        assert previous.identifiers[key][index] is row
        assert row["field_basis"] is fields
        assert all(fields[name] is leaf for name, leaf in leaves.items())
    for key, old_rows in previous.identifiers.items():
        for old, new in zip(old_rows, upgraded.identifiers[key], strict=True):
            assert new == dict(old, field_basis=new["field_basis"])
            if key in {owner, nlc_owner}:
                assert new is not old and new["field_basis"] is not old["field_basis"]
                for name, leaf in new["field_basis"].items():
                    assert leaf is not old["field_basis"][name]
                    assert leaf == dict(old["field_basis"][name], author="rule:identifier@" + rules.RULE_VERSION,
                                        run=3, at=at.isoformat())
            else:
                assert new is old  # 完全未变编号仍复用，不为每行制造更新。
    assert _report(upgraded, previous)["counts"]["changes"]["items"] == {"new": 0, "changed": 2}
    repeated = _compute(roots, cache, previous=_state(upgraded), run=4, sink=sink)
    assert repeated.identifiers == upgraded.identifiers
    assert all(new is old for key, rows in upgraded.identifiers.items()
               for old, new in zip(rows, repeated.identifiers[key], strict=True))
    assert _report(repeated, _state(upgraded))["counts"]["changes"]["items"] == {"new": 0, "changed": 0}

    # 真正路径/来源/主号变化不是 basis-only；撤销 pending 与真实改号仍走旧语义。
    moved = directory.with_name("BD12345a")
    directory.rename(moved)
    (base / "副本 P2003").rename(base / "P2002")
    attachment_id, = first.attachments.values()
    relocated = _compute(roots, cache, previous=_state(repeated), run=5, sink=lambda file, raw: attachment_id)
    assert all(r["since_run"] == 5 and "id" not in r for r in relocated.identifiers[nlc_owner])
    assert {r["source_path"] for r in relocated.identifiers[nlc_owner]} == {
        "data:中国国博馆藏/BD12345a", "data:中国国博馆藏/BD12345a/manifest.json",
    }
    held, = relocated.identifiers[owner]
    assert held is next(r for r in repeated.identifiers[owner] if r["state"] == "current")
    (moved / "manifest.json").unlink()
    (base / "P2002").rename(base / "P2004")
    changed = _compute(roots, cache, previous=_state(relocated), run=6)
    directory_number, = changed.identifiers[nlc_owner]
    assert directory_number["source"] == "文件名解析" and directory_number["is_primary"]
    assert directory_number["since_run"] == 6 and "id" not in directory_number
    new_number, = changed.identifiers[owner]
    assert new_number["normalized"] == "P.2004" and new_number["state"] == "current"
    assert new_number["since_run"] == 6 and "id" not in new_number
    assert previous == before and pending.identifiers == original


def test_share_numbers_and_zhihao_are_not_doubtful_collection_numbers(roots, cache, make_image):
    for name in ("WB29", "WA9", "敦煌藏經洞 1 令字"):
        make_image(roots["data"] / "敦煌003" / name / "native.tif")
    result = _compute(roots, cache)
    assert "编号存疑" not in {a["category"] for a in result.anomalies}
    assert all(not row["is_primary"] for rows in result.identifiers.values() for row in rows)
    counts = _report(result)["counts"]
    assert counts["items_by_primary_number"] == {"无主编号": 3}
    assert counts["kaibao_suggestion_units"] == 1
    assert counts["title_clue_suggestion_units"] == 0


def test_merge_suggestion_anomalies_bind_both_endpoints(roots, cache, make_image):
    for name in ("WB29 甲", "WB29 乙"):
        make_image(roots["data"] / "敦煌003" / name / "native.tif")
    result = _compute(roots, cache)
    suggestion, = result.units.suggestions
    anomalies = [a for a in result.anomalies if a["category"] == "合并建议"]
    assert len(result.items) == 2  # 仅补关联，不自动合并。
    assert len(anomalies) == 2
    assert {a["object_key"] for a in anomalies} == {suggestion.left, suggestion.right}
    assert {a["object_kind"] for a in anomalies} == {"unit"}
    assert all(a["raw"] == suggestion.left + "；" + suggestion.right for a in anomalies)
    assert _report(result)["counts"]["anomalies_by_category"]["合并建议"] == 2


def test_basic_report_counts_do_not_double_count_shared_images(roots, cache, make_image):
    for path in ("敦煌003/P2002+2003/native.tif", "敦煌003/P2504-1/native.tif",
                 "敦煌003/P2504-2/native.tif", "敦煌003/WB29/.hidden.psb"):
        make_image(roots["data"] / path)
    result = _compute(roots, cache)
    report = _report(result)
    counts = report["counts"]
    assert counts["items"] == 5 and counts["present_images"] == 4
    assert sum(counts["images_by_role"].values()) == 4
    assert counts["parts_by_parent"] == {"P.2504": 2}
    assert counts["data_tiff"] == 3 and counts["psb"] == 1
    assert counts["hidden_files"] == 1 and counts["wb_units"] == 1
    assert counts["multi_number_units"] == 1
    assert sum(counts["anomalies_by_category"].values()) == len(report["anomalies"])


def test_entirely_missing_item_preserves_metadata(roots, cache, make_image):
    directory = roots["data"] / "敦煌003/P2002+2003 WB29"
    make_image(directory / "native.tif")
    first = _compute(roots, cache)
    recycle = roots["data"] / "#recycle"
    directory.rename(recycle)
    second = _compute(roots, cache, previous=_state(first), run=2)
    assert first.items == second.items
    assert first.identifiers == second.identifiers
    assert first.links == second.links
    assert all(row["state"] == "missing" for row in second.images.values())
    for key, row in second.images.items():
        assert isinstance(row, CompactMap) and isinstance(row["field_basis"], CompactMap)
        assert row["facts"] is first.images[key]["facts"]
        assert row["field_basis"]["facts"] is first.images[key]["field_basis"]["facts"]
    assert _report(second, _state(first))["counts"]["changes"]["images"]["missing"] == 1


def test_preserved_item_accepts_new_image_metadata_and_attachments(roots, cache, make_image):
    directory = roots["data"] / "敦煌003/P2002 原图"
    make_image(directory / "native.tif")
    (directory / "旧说明.txt").write_bytes(b"old original note")
    first = _compute(roots, cache)
    item, = first.items.values()
    old_image, = first.images.values()
    assert item["display_policy"] == "登录墙内可展示"
    directory.rename(roots["data"] / "#recycle")
    new_directory = directory.with_name("P2002 加工图")
    make_image(new_directory / "processed.tif", software="Adobe Photoshop synthetic")
    (new_directory / "新说明.txt").write_bytes(b"new original note")
    consumed = {}
    def consume(file, raw):
        consumed[file] = raw
        return uuid4()
    second = _compute(roots, cache, previous=_state(first), run=2, sink=consume)
    assert second.item_resolution.preserved_items == {item["id"]}
    assert set(second.items) == {item["id"]}
    after = second.items[item["id"]]
    assert second.images[old_image["id"]]["state"] == "missing"
    new_image, = [row for row in second.images.values() if row["state"] == "present"]
    assert new_image["lineage"] == "第三方加工图"
    assert (item["id"], new_image["id"]) in second.links
    assert after["display_policy"] == "仅供研究使用"
    for name in ("grouping_key", "clues", "provenance"):
        assert after[name] == item[name]
        assert after["field_basis"][name] == item["field_basis"][name]
    assert second.identifiers == first.identifiers
    assert after["original_positions"] == item["original_positions"] + [
        {"root": "data", "relative_path": "敦煌003/P2002 加工图", "name": "P2002 加工图"},
    ]
    assert after["field_basis"]["display_policy"]["run"] == 2
    assert after["field_basis"]["original_positions"]["run"] == 2
    assert after["updated_run"] == 2
    assert list(consumed.values()) == [b"new original note"]
    assert second.item_attachments[item["id"]] == first.item_attachments[item["id"]] | set(second.attachments.values())
    assert len(second.item_attachments[item["id"]]) == 2
    assert second.images[old_image["id"]]["original_path"] == old_image["original_path"]


def test_processed_collection_uses_retained_item_number_after_rename(roots, cache, make_image):
    directory = roots["data"] / "敦煌003/P2002 加工图"
    make_image(directory / "processed.tif", software="Adobe Photoshop synthetic")
    first = _compute(roots, cache)
    item, = first.items.values()
    image, = first.images.values()
    assert image["collection"] == "法国国家图书馆"
    directory.rename(directory.with_name("加工图无编号"))
    second = _compute(roots, cache, previous=_state(first), run=2)
    assert set(second.items) == {item["id"]}
    assert set(second.images) == {image["id"]}
    assert second.items[item["id"]]["grouping_key"] == "pelliot:2002"
    primary, = [row for row in second.identifiers[item["id"]] if row["is_primary"]]
    assert primary["normalized"] == "P.2002" and primary["state"] == "current"
    assert item["id"] in second.item_resolution.pending
    assert any(a["category"] == "身份待确认" and a["object_key"] == str(item["id"]) for a in second.anomalies)
    assert second.images[image["id"]]["collection"] == "法国国家图书馆"
    assert second.images[image["id"]]["field_basis"]["collection"]["confidence"] == "推断"
    assert second.images[image["id"]]["field_basis"]["collection"] == image["field_basis"]["collection"]


def test_human_conclusion_computation(roots, cache, make_image):
    make_image(roots["data"] / "敦煌003/P2002/native.tif")
    first = _compute(roots, cache)
    item, = first.items.values()
    item["provenance"] = dict(item["provenance"], status="非敦煌", judge="user:scholar", evidence=["合成文献核对"])
    item["field_basis"]["provenance"] = dict(item["field_basis"]["provenance"], source="人工", author="user:scholar", confidence="确定")
    second = _compute(roots, cache, previous=_state(first), run=2)
    assert second.items[item["id"]]["provenance"] == item["provenance"]
    assert second.items[item["id"]]["field_basis"]["provenance"] == item["field_basis"]["provenance"]


def test_v0_index_coverage(roots, cache, make_image):
    make_image(roots["data"] / "敦煌003/P2002/native.tif")
    make_image(roots["data"] / "敦煌003/P2003/native.tif")
    result = _compute(roots, cache)
    report = _report(result, fetch=_fetch(["敦煌003/P2002", "敦煌003/已删除"]))
    assert report["coverage"] == {"status": "valid", "reason": None, "unmapped_existing": [], "unmapped_existing_count": 0,
                                  "disk_not_indexed": ["敦煌003/P2003"], "index_directory_absent": ["敦煌003/已删除"]}
    unavailable = _report(result, fetch=_fetch(ready=False))
    assert unavailable["coverage"]["status"] == "unavailable"
    assert unavailable["coverage"]["unmapped_existing"] is None
    assert "v0 索引不可用" in {a["category"] for a in unavailable["anomalies"]}


def test_v0_cache_access(roots, cache, make_image):
    make_image(roots["data"] / "敦煌003/P2002/native.tif")
    (cache / "users.json").write_bytes(b"must not read")
    events, active = [], True
    def audit(event, args):
        if active and event in {"open", "os.listdir", "os.scandir"} and isinstance(args[0], (str, bytes)):
            if Path(os.fsdecode(args[0])).is_relative_to(cache):
                events.append((event, args))
    sys.addaudithook(audit)
    try:
        result = _compute(roots, cache)
    finally:
        active = False
    assert {event for event, _ in events} == {"open"}
    assert [Path(args[0]).name for _, args in events] == list(CACHE_FILES)
    assert all(args[1] == "r" for _, args in events)
    assert _report(result)["cache_access"] == [str(cache / name) for name in CACHE_FILES]


@pytest.mark.parametrize("category", [
    "编号存疑", "疑似编号", "编号与清单不一致", "缺少清单", "缺少影像", "无馆藏号的写卷单元",
    "词表外子目录", "合并建议", "隐藏文件与非隐藏影像同目录（待确认）", "读不了的文件", "谱系未判定",
    "派生来源不明", "备份分片对不上", "画布对不上", "身份待确认", "出处证据冲突", "v0 索引不可用", "未导入的文件",
])
def test_anomaly_categories(roots, cache, make_image, category):
    directory = roots["data"] / "敦煌003/P2002"
    previous = None
    if category in {"编号与清单不一致", "缺少清单", "画布对不上"}:
        directory = roots["data"] / "中国国博馆藏/BD12345"
        make_image(directory / "unmapped.tif")
        if category != "缺少清单":
            (directory / "manifest.json").write_bytes(_manifest("BD12346"))
    elif category == "缺少影像":
        directory.mkdir(parents=True)
        (directory / "note.txt").write_bytes(b"only attachment")
    elif category == "备份分片对不上":
        make_image(roots["backup"] / "敦煌003/P2002/1.tif")
    else:
        name = {"编号存疑": "P0901", "疑似编号": "4518(35)", "无馆藏号的写卷单元": "无号",
                "合并建议": "WB29 上部", "出处证据冲突": "P2002 室町写"}.get(category, "P2002")
        directory = directory.with_name(name)
        filename = {"谱系未判定": "1.tif", "派生来源不明": "合并长卷.tif"}.get(category, "native.tif")
        path = make_image(directory / filename)
        if category == "词表外子目录":
            make_image(directory / "独立子目录/native.tif")
        elif category == "合并建议":
            make_image(directory.with_name("WB29 下部") / "native.tif")
        elif category == "隐藏文件与非隐藏影像同目录（待确认）":
            make_image(directory / ".hidden.tif")
        elif category == "读不了的文件":
            path.write_bytes(b"broken")
        elif category == "未导入的文件":
            (directory / "excluded.pdf").write_bytes(b"synthetic")
        elif category == "身份待确认":
            previous = _state(_compute(roots, cache))
            directory.rename(directory.with_name("无号"))
    result = _compute(roots, cache, previous=previous, run=2)
    anomalies = _report(result, previous)["anomalies"]
    found = [a for a in anomalies if a["category"] == category]
    assert found
    assert all({"category", "object_kind", "object_key", "raw", "description"} <= a.keys() and a["description"] for a in found)


@pytest.fixture
def import_runner(connection, test_database_url, roots, cache):
    def handler(request):
        assert request.headers["cookie"] == "dh_session=caller-cookie"
        if request.url.path == "/api/health":
            return httpx.Response(200, json={"ok": True})
        return httpx.Response(200, json=payload)
    payload = {"status": "ready", "items": []}
    with create_pool(test_database_url) as pool, httpx.Client(transport=httpx.MockTransport(handler)) as http:
        pool.wait(10)
        def prepare():
            return prepare_import(pool, triggered_by="import-admin", code_version="synthetic-code",
                                  session_cookie="caller-cookie", v0_url="http://v0.test", http_client=http)
        def run():
            prepared = prepare()
            return prepared.run_id, prepared.execute(roots, cache)
        yield run, prepare, payload


@pytest.mark.db
def test_prepared_import_passes_record_roots_and_preserves_history(connection, import_runner, roots, cache, host_records):
    run, prepare, _ = import_runner
    first, _ = run()  # Omitted parameter remains compatible; no implicit host prefix.
    output = connection.execute("SELECT * FROM image WHERE lineage='本地合成'").fetchone()
    past = value_at_run(connection, "image", output["id"], first)
    assert output["license"] == rules.UNKNOWN_LICENSE
    assert connection.execute("SELECT count(*) AS n FROM derivation").fetchone()["n"] == 0
    settings = load_settings(host_records)
    prepared = prepare()
    report = prepared.execute(roots, cache, record_roots=settings.record_roots)
    assert read_report(connection, prepared.run_id)["status"] == "succeeded"
    assert report["counts"]["outputs_with_derivation"] == 1
    after = connection.execute("SELECT * FROM image WHERE id=%s", (output["id"],)).fetchone()
    assert after["license"] == rules.PROCESSED_LICENSE
    assert after["display_policy"] == "仅供研究使用" and after["external_policy"] == "不对外"
    edges = list(connection.execute("SELECT * FROM derivation"))
    assert len(edges) == 2 and all(edge["image_id"] == output["id"] for edge in edges)
    assert {row["id"] for row in connection.execute("SELECT id FROM image WHERE root='backup'")} == {
        edge["source_image_id"] for edge in edges}
    current = value_at_run(connection, "image", output["id"], prepared.run_id)
    assert current["snapshot"]["license"] == rules.PROCESSED_LICENSE
    assert current["run_id"] == prepared.run_id
    assert value_at_run(connection, "image", output["id"], first) == past
    third, _ = run()
    assert connection.execute("SELECT count(*) AS n FROM derivation").fetchone()["n"] == 0
    assert value_at_run(connection, "image", output["id"], third)["snapshot"]["license"] == rules.UNKNOWN_LICENSE
    assert value_at_run(connection, "image", output["id"], prepared.run_id) == current
    assert value_at_run(connection, "image", output["id"], first) == past


@pytest.mark.db
def test_public_event_upgrade_appends_history_without_changing_identifier_tenure(
    connection, import_runner, roots, make_image,
):
    run, _, _ = import_runner
    make_image(roots["data"] / "敦煌003/P2002/native.tif")
    version, event = rules.RULE_VERSION, rules.TRANSFER_EVENT
    try:
        # Synthetic prior deployment configuration, never the private historical label.
        rules.RULE_VERSION = "synthetic-previous-version"
        rules.TRANSFER_EVENT = "第三方资料接收（合成旧事件）"
        first, _ = run()
    finally:
        rules.RULE_VERSION, rules.TRANSFER_EVENT = version, event
    old_run = read_report(connection, first)
    image = connection.execute("SELECT * FROM image").fetchone()
    item = connection.execute("SELECT * FROM item").fetchone()
    identifier = connection.execute("SELECT * FROM identifier").fetchone()
    history = list(connection.execute("SELECT * FROM history ORDER BY object_kind, object_id, run_id"))
    second, _ = run()
    assert read_report(connection, first) == old_run
    assert old_run["rule_version"] == "synthetic-previous-version"
    assert read_report(connection, second)["rule_version"] == "2026-10-30.1"
    after = connection.execute("SELECT * FROM image").fetchone()
    assert after["id"] == image["id"] and after["acquisition"] == "第三方资料接收（接收事件 A）"
    for name in ("facts", "lineage", "collection", "license", "attribution", "display_policy", "external_policy"):
        assert after[name] == image[name]
    assert after["field_basis"]["acquisition"]["author"].endswith("@2026-10-30.1")
    assert after["field_basis"]["acquisition"]["run"] == second
    assert connection.execute("SELECT id FROM item").fetchone()["id"] == item["id"]
    current_identifier = connection.execute("SELECT * FROM identifier").fetchone()
    assert current_identifier == dict(identifier, field_basis=current_identifier["field_basis"])
    assert list(connection.execute("SELECT * FROM history WHERE run_id=%s ORDER BY object_kind, object_id, run_id",
                                   (first,))) == history
    old_image = value_at_run(connection, "image", image["id"], first)
    assert old_image["snapshot"]["acquisition"] == "第三方资料接收（合成旧事件）"
    assert old_image["field_basis"]["acquisition"]["author"].endswith("@synthetic-previous-version")
    new_history = list(connection.execute("SELECT * FROM history ORDER BY object_kind, object_id, run_id"))
    assert len(new_history) == len(history) + 2
    third, report = run()
    assert not any(report["counts"]["changes"]["images"].values())
    assert report["counts"]["changes"]["items"] == {"new": 0, "changed": 0}
    assert list(connection.execute("SELECT * FROM history ORDER BY object_kind, object_id, run_id")) == new_history
    assert value_at_run(connection, "image", image["id"], third)["run_id"] == second


@pytest.mark.db
def test_full_repeat_import_and_new_files_appear(connection, import_runner, roots, make_image):
    run, _, _ = import_runner
    directory = roots["data"] / "敦煌003/P2002"
    make_image(directory / "native.tif")
    first, report = run()
    ids = list(connection.execute("SELECT id FROM image"))
    items = list(connection.execute("SELECT id, field_basis FROM item"))
    history_count = connection.execute("SELECT count(*) AS n FROM history").fetchone()["n"]
    second, report2 = run()
    assert list(connection.execute("SELECT id FROM image")) == ids
    assert list(connection.execute("SELECT id, field_basis FROM item")) == items
    assert connection.execute("SELECT count(*) AS n FROM history").fetchone()["n"] == history_count
    assert report2["counts"]["facts_reused"] == 1
    assert not any(report2["counts"]["changes"]["images"].values())
    make_image(directory / "native(1).tif")
    third, report3 = run()
    assert report3["counts"]["changes"]["images"]["new"] == 1
    assert connection.execute("SELECT count(*) AS n FROM item").fetchone()["n"] == 1
    assert first < second < third
    record = read_report(connection, third)
    assert record["status"] == "succeeded" and record["ended_at"]
    assert record["triggered_by"] == "import-admin" and record["code_version"] == "synthetic-code"
    assert record["health_summary"]["count"] >= 1
    assert record["counts"] == report3


@pytest.mark.db
def test_loaded_basis_sharing_json_and_history_unchanged(connection, import_runner, roots, cache, make_image):
    run, _, _ = import_runner
    for number in (2002, 2003):
        directory = roots["data"] / f"敦煌003/P{number}"
        make_image(directory / "source.psb")
        make_image(directory / "合并长卷.tif")
    (cache / "psb_convert.log").write_text("".join(
        f"===== 11:00:00 转换: 敦煌003/P{number} =====\nPSBNAME: source.psb\n"
        f"TIFF 完成: /data/敦煌003/P{number}/合并长卷_psb.tif  7 x 5\n已替换合并长卷.tif\n退出码: 0\n"
        for number in (2002, 2003)), encoding="utf-8")
    first, _ = run()
    loaded = load_catalog_state(connection)
    raw_images = {r["id"]: r for r in connection.execute("SELECT * FROM image")}
    assert loaded.images == raw_images
    assert loaded.items == {r["id"]: r for r in connection.execute("SELECT * FROM item")}
    assert loaded.links == {(r["item_id"], r["image_id"]): r for r in connection.execute("SELECT * FROM item_image")}
    assert len(loaded.derivations) == 2
    assert loaded.derivations == {(r["image_id"], r["source_image_id"]): r
                                  for r in connection.execute("SELECT * FROM derivation")}
    for row in connection.execute("SELECT * FROM identifier WHERE state='current'"):
        assert row in loaded.identifiers[row["item_id"]]
    images = list(loaded.images.values())
    assert len({id(r["field_basis"]) for r in images}) == 4
    assert len({id(r["field_basis"]["facts"]) for r in images}) == 4
    assert len({id(r["facts"]) for r in images}) == 4
    assert len({id(r["field_basis"]["facts"]["channels"]) for r in images}) == 1
    assert len({id(r["field_basis"]["root"]) for r in images}) == 1
    psbs = [r for r in images if r["kind"] == "psb"]
    assert psbs[0]["facts"]["pixel_size"] is psbs[1]["facts"]["pixel_size"]
    for edge in loaded.derivations.values():
        output = loaded.images[edge["image_id"]]
        assert output["field_basis"]["license"]["source_images"] == [str(edge["source_image_id"])]
        assert edge["field_basis"]["method"]["location"] == f"psb_convert.log:{edge['evidence_line']}"
    for owner, identifiers in loaded.identifiers.items():
        for ident in identifiers:
            assert ident["field_basis"]["raw"]["unit_key"] == ident["source_path"]
        assert loaded.items[owner]["field_basis"]["grouping_key"]["identifier_sources"] == [identifiers[0]["source_path"]]
    # 新加载使用新池；不让上次返回的只读叶被本次加载修改。
    reloaded = load_catalog_state(connection)
    assert reloaded == loaded
    assert reloaded.images[images[0]["id"]]["field_basis"]["root"] is not images[0]["field_basis"]["root"]
    history = list(connection.execute("SELECT * FROM history ORDER BY object_kind, object_id, run_id"))
    second, report = run()
    assert list(connection.execute("SELECT * FROM history ORDER BY object_kind, object_id, run_id")) == history
    assert report["counts"]["changes"]["items"] == {"new": 0, "changed": 0}
    assert report["counts"]["changes"]["images"]["metadata_changed"] == 0
    for image in images:
        assert value_at_run(connection, "image", image["id"], second)["run_id"] == first
        assert value_at_run(connection, "image", image["id"], first)["field_basis"] == image["field_basis"]


@pytest.mark.db
def test_compact_images_keep_history_and_json(connection, import_runner, roots, cache, make_image):
    run, _, _ = import_runner
    relative = "敦煌003/P2002 Plainte ＋---"
    directory = roots["data"] / relative
    source = make_image(directory / "source.psb")
    make_image(directory / "合并长卷.tif")
    raw = b"\xff\x00 original\r\n"
    (directory / "原文.txt").write_bytes(raw)
    nlc = roots["data"] / "中国国博馆藏/bd12345"
    path = make_image(nlc / "BD12345_0000_0.tif", dpi=(180, 180))
    (nlc / "manifest.json").write_bytes(_manifest())
    (cache / "psb_convert.log").write_text(
        f"===== 11:00:00 转换: {relative} =====\nPSBNAME: source.psb\n"
        f"TIFF 完成: /data/{relative}/合并长卷_psb.tif  7 x 5\n已替换合并长卷.tif\n退出码: 0\n",
        encoding="utf-8",
    )
    past = {}

    def check(run_id):
        loaded = load_catalog_state(connection)
        # 六集合完整 SQL 对照；包括非影像行的可写契约与 JSON 数值类型。
        images = {r["id"]: r for r in connection.execute("SELECT * FROM image")}
        items = {r["id"]: r for r in connection.execute("SELECT * FROM item")}
        identifiers, attachments = {}, {}
        for row in connection.execute("SELECT * FROM identifier WHERE state IN ('current', 'pending') ORDER BY id"):
            identifiers.setdefault(row["item_id"], []).append(row)
        for row in connection.execute("SELECT * FROM item_attachment"):
            attachments.setdefault(row["item_id"], set()).add(row["attachment_id"])
        links = {(r["item_id"], r["image_id"]): r for r in connection.execute("SELECT * FROM item_image")}
        edges = {(r["image_id"], r["source_image_id"]): r for r in connection.execute("SELECT * FROM derivation")}
        assert loaded == CatalogState(images, items, identifiers, links, edges, attachments)
        assert all((images, items, identifiers, links, edges, attachments))
        for actual, expected in ((loaded.images, images), (loaded.items, items),
                                 (loaded.identifiers, identifiers), (loaded.links, links),
                                 (loaded.derivations, edges)):
            assert type(actual) is dict and actual.keys() == expected.keys()
            for key in actual:
                assert json.dumps(_json_value(actual[key]), sort_keys=True) == json.dumps(_json_value(expected[key]), sort_keys=True)
        for row in loaded.images.values():
            for mapping in (row, row["facts"], row["field_basis"], row["field_basis"]["facts"]):
                assert isinstance(mapping, CompactMap)
            assert type(row["facts"]["pixel_size"]) is dict
            assert type(row["facts"]["pixel_size"]["value"]) is list
        assert all(type(row) is dict for rows in (loaded.items, loaded.links, loaded.derivations) for row in rows.values())
        assert all(type(row) is dict for rows in loaded.identifiers.values() for row in rows)
        output, = [r for r in loaded.images.values() if r["lineage"] == "本地合成"]
        assert type(output["field_basis"]["license"]["source_images"]) is list
        assert output["original_path"] == relative + "/合并长卷.tif"
        assert output["original_name"] == "合并长卷.tif"
        assert bytes(connection.execute("SELECT raw FROM attachment WHERE kind='text'").fetchone()["raw"]) == raw
        # 按任意批次读到的完整 JSON 与当时当前行逐字段相符，独立依据列也相符。
        for kind, rows in (("image", loaded.images), ("item", loaded.items)):
            for object_id, row in rows.items():
                history = value_at_run(connection, kind, object_id, run_id)
                assert history["field_basis"] == history["snapshot"]["field_basis"] == row["field_basis"]
                for name, value in row.items():
                    if name != ("last_seen" if kind == "image" else "updated_run"):
                        assert json.dumps(history["snapshot"][name], sort_keys=True) == json.dumps(_json_value(value), sort_keys=True)
                past[kind, object_id, run_id] = history
        for (kind, object_id, requested), expected in past.items():
            assert value_at_run(connection, kind, object_id, requested) == expected
        return loaded

    first, _ = run()
    initial = check(first)
    nlc_image = next(r for r in initial.images.values() if r["kind"] == "tiff" and r["lineage"] == "国图 IDP 下载")
    assert type(nlc_image["hidden"]) is bool and type(nlc_image["canvas_number"]) is int
    assert type(nlc_image["facts"]["resolution"]["value"][0]) is float
    history_count = connection.execute("SELECT count(*) AS n FROM history").fetchone()["n"]
    second, report = run()
    repeated = check(second)
    assert repeated.images.keys() == initial.images.keys()
    assert repeated.images[nlc_image["id"]]._shape is not nlc_image._shape
    assert report["counts"]["facts_reused"] == len(initial.images)
    assert not any(report["counts"]["changes"]["images"].values())
    assert connection.execute("SELECT count(*) AS n FROM history").fetchone()["n"] == history_count

    version = rules.RULE_VERSION
    try:
        rules.RULE_VERSION = version + ".compact-test"
        changed_rule, _ = run()
        revised = check(changed_rule)
        assert revised.images[nlc_image["id"]]["facts"] == nlc_image["facts"]
        leaf = revised.images[nlc_image["id"]]["field_basis"]["facts"]["pixel_size"]
        assert leaf["author"].endswith("@" + rules.RULE_VERSION) and leaf["run"] == changed_rule
        replacement = make_image(nlc / "replacement.tif", software="Photoshop changed", dpi=(300, 300))
        os.replace(replacement, path)
        make_image(directory / ".新增.tif")
        changed_file, report = run()
        changed = check(changed_file)
        assert set(initial.images) < set(changed.images) and set(initial.items) == set(changed.items)
        assert report["counts"]["changes"]["images"]["changed"] == 1
        assert report["counts"]["changes"]["images"]["new"] == 1
        assert changed.images[nlc_image["id"]]["facts"]["software"]["value"] == "Photoshop changed"
        assert changed.images[nlc_image["id"]]["field_basis"]["facts"]["software"]["run"] == changed_file
        path.unlink()
        missing_run, _ = run()
        missing = check(missing_run)
        assert missing.images[nlc_image["id"]]["state"] == "missing"
        assert missing.images[nlc_image["id"]]["facts"] == changed.images[nlc_image["id"]]["facts"]
        assert missing.images[nlc_image["id"]]["missing_since"] is not None
        unchanged_missing, report = run()
        check(unchanged_missing)
        assert not any(report["counts"]["changes"]["images"].values())
        assert value_at_run(connection, "image", nlc_image["id"], unchanged_missing)["run_id"] == missing_run
        assert source.exists()
    finally:
        rules.RULE_VERSION = version


@contextmanager
def _state_load_protocol(connection, enabled):
    """只留下协议命令摘要；原始行数据仅在临时文件中，失败也 untrace / 关闭。"""
    commands = []
    if not enabled:
        yield commands
        return
    with tempfile.TemporaryFile(mode="w+b") as trace:
        connection.pgconn.trace(trace.fileno())
        try:
            yield commands
        finally:
            connection.pgconn.untrace()
        trace.seek(0)
        for line in trace.read().decode("utf-8").splitlines():
            if "\tF\t" in line:
                command = re.search(
                    r"\b(DECLARE|FETCH FORWARD (?:ALL|\d+)|CLOSE|BEGIN|COMMIT|ROLLBACK|RELEASE)\b", line,
                )
                if command:
                    commands.append(command[1])


_PROTOCOL_CASES = [
    False,
    pytest.param(True, marks=pytest.mark.skipif(
        sys.platform != "linux", reason="真实 libpq 协议 trace 仅在 Linux 目标环境验证",
    ), id="linux-protocol-trace"),
]


@pytest.mark.db
@pytest.mark.parametrize("protocol", _PROTOCOL_CASES)
def test_state_load_batches_match_all_rows_and_json(connection, import_runner, roots, cache, make_image, protocol):
    run, _, _ = import_runner
    base = roots["data"] / "敦煌003"
    for n in range(253):
        make_image(base / "P2002" / f"native({n}).tif")
    make_image(base / "P2003/source.psb")
    make_image(base / "P2003/合并长卷.tif")
    (base / "P2003/原文.txt").write_bytes(b"\xff\x00 original\r\n")
    make_image(base / "P2004/native.tif")
    nlc = roots["data"] / "中国国博馆藏/bd12345"
    make_image(nlc / "BD12345_0000_0.tif", dpi=(180, 180))
    (nlc / "manifest.json").write_bytes(_manifest())
    (cache / "psb_convert.log").write_text(
        "===== 11:00:00 转换: 敦煌003/P2003 =====\nPSBNAME: source.psb\n"
        "TIFF 完成: /data/敦煌003/P2003/合并长卷_psb.tif  7 x 5\n已替换合并长卷.tif\n退出码: 0\n",
        encoding="utf-8",
    )
    run()
    # 由真实归并/持久化产生 current、pending、historical，不在测试中复制编号算法。
    (base / "P2002").rename(base / "副本 P2003")
    (base / "P2004").rename(base / "P2005")
    run()
    assert {r["state"] for r in connection.execute("SELECT DISTINCT state FROM identifier")} == {
        "current", "pending", "historical",
    }
    with _state_load_protocol(connection, protocol) as commands:
        loaded = load_catalog_state(connection)
    assert connection.info.transaction_status == TransactionStatus.IDLE
    assert list(connection.execute("SELECT name FROM pg_cursors")) == []
    assert len(loaded.images) == 257
    # 普通只读 SQL 逐字段对照；这些容器仅用于测试期望，不模拟读取实现。
    assert loaded.images == {r["id"]: r for r in connection.execute("SELECT * FROM image")}
    assert loaded.items == {r["id"]: r for r in connection.execute("SELECT * FROM item")}
    identifiers = {}
    for row in connection.execute("SELECT * FROM identifier WHERE state IN ('current', 'pending') ORDER BY id"):
        identifiers.setdefault(row["item_id"], []).append(row)
    assert loaded.identifiers == identifiers  # 包括每件的数据库 id 顺序。
    assert loaded.links == {(r["item_id"], r["image_id"]): r for r in connection.execute("SELECT * FROM item_image")}
    assert loaded.derivations == {(r["image_id"], r["source_image_id"]): r for r in connection.execute("SELECT * FROM derivation")}
    attachments = {}
    for row in connection.execute("SELECT * FROM item_attachment"):
        attachments.setdefault(row["item_id"], set()).add(row["attachment_id"])
    assert loaded.attachments == attachments
    assert all((loaded.items, loaded.identifiers, loaded.links, loaded.derivations, loaded.attachments))
    # JSON 序列化还区分 Python 相等比较会混同的 bool/int/float；嵌套列表不转 tuple。
    for table, rows, json_fields in (
        ("image", loaded.images.values(), ("facts", "field_basis")),
        ("item", loaded.items.values(), ("original_positions", "provenance", "clues", "field_basis")),
        ("identifier", [r for group in loaded.identifiers.values() for r in group], ("field_basis",)),
        ("item_image", loaded.links.values(), ("field_basis",)),
        ("derivation", loaded.derivations.values(), ("field_basis",)),
    ):
        stored = list(connection.execute(f"SELECT * FROM {table}"))
        for row in rows:
            raw = next(r for r in stored if all(r[key] == row[key] for key in (
                ("id",) if "id" in row else ("item_id", "image_id") if table == "item_image"
                else ("image_id", "source_image_id")
            )))
            for name in json_fields:
                assert json.dumps(_json_value(row[name]), sort_keys=True) == json.dumps(raw[name], sort_keys=True)
    for image in loaded.images.values():
        assert type(image["facts"]["pixel_size"]["value"]) is list
    for item in loaded.items.values():
        assert type(item["original_positions"]) is type(item["clues"]) is list
        assert type(item["provenance"]["evidence"]) is list
        assert type(item["field_basis"]["grouping_key"]["identifier_sources"]) is list
    output, = [r for r in loaded.images.values() if r["lineage"] == "本地合成"]
    assert type(output["field_basis"]["license"]["source_images"]) is list
    if protocol:
        # 六个显式 DECLARE/FETCH/CLOSE 顺序；容许整批后的空 FETCH，不凑总次数。
        assert commands[0] == "BEGIN" and commands[-1] == "COMMIT"
        cursor_commands = commands[1:-1]
        counts = (len(loaded.images), len(loaded.items), sum(map(len, loaded.identifiers.values())),
                  len(loaded.links), len(loaded.derivations), sum(map(len, loaded.attachments.values())))
        for count in counts:
            assert cursor_commands[0] == "DECLARE"
            end = cursor_commands.index("CLOSE")
            fetches = cursor_commands[1:end]
            assert len(fetches) >= max(1, (count + 127) // 128)
            assert set(fetches) == {"FETCH FORWARD 128"}
            cursor_commands = cursor_commands[end + 1:]
        assert cursor_commands == []


@pytest.mark.db
@pytest.mark.parametrize("outer_transaction", [False, True])
@pytest.mark.parametrize("populated", [False, True])
def test_state_load_preserves_caller_transaction_and_cursors(
    connection, test_database_url, import_runner, roots, make_image, outer_transaction, populated,
):
    run, _, _ = import_runner
    if populated:
        make_image(roots["data"] / "敦煌003/P2002/native.tif")
    run_id, _ = run()
    with psycopg.connect(test_database_url, autocommit=True, row_factory=dict_row) as observer:
        with connection.transaction(force_rollback=True) if outer_transaction else nullcontext():
            if outer_transaction:
                connection.execute("UPDATE import_run SET code_version='uncommitted-marker' WHERE id=%s", (run_id,))
            state = load_catalog_state(connection)
            assert len(state.images) == int(populated)
            assert connection.info.transaction_status == (
                TransactionStatus.INTRANS if outer_transaction else TransactionStatus.IDLE
            )
            assert list(connection.execute("SELECT name FROM pg_cursors")) == []
            assert connection.execute("SELECT 1 AS n").fetchone()["n"] == 1
            assert connection.execute("SELECT code_version FROM import_run WHERE id=%s", (run_id,)).fetchone()["code_version"] == (
                "uncommitted-marker" if outer_transaction else "synthetic-code"
            )
            assert observer.execute("SELECT code_version FROM import_run WHERE id=%s", (run_id,)).fetchone()["code_version"] == "synthetic-code"
        assert connection.info.transaction_status == TransactionStatus.IDLE
        assert connection.execute("SELECT code_version FROM import_run WHERE id=%s", (run_id,)).fetchone()["code_version"] == "synthetic-code"
        assert observer.execute("SELECT code_version FROM import_run WHERE id=%s", (run_id,)).fetchone()["code_version"] == "synthetic-code"
    assert list(connection.execute("SELECT name FROM pg_cursors")) == []


@pytest.mark.db
def test_state_load_sql_failure_rolls_back_savepoint(connection, test_database_url, import_runner, roots, make_image):
    run, _, _ = import_runner
    make_image(roots["data"] / "敦煌003/P2002/native.tif")
    run_id, _ = run()
    with psycopg.connect(test_database_url, autocommit=True, row_factory=dict_row) as observer:
        with connection.transaction(force_rollback=True):
            connection.execute("UPDATE import_run SET code_version='uncommitted-marker' WHERE id=%s", (run_id,))
            connection.execute("ALTER TABLE derivation RENAME TO synthetic_renamed_derivation")
            with pytest.raises(psycopg.errors.UndefinedTable) as failure:
                load_catalog_state(connection)
            # 保持真实异常及 traceback 存活，不能靠生成器 GC 关闭游标。
            assert failure.value.sqlstate == "42P01" and failure.value.__traceback__ is not None
            assert connection.info.transaction_status == TransactionStatus.INTRANS
            assert list(connection.execute("SELECT name FROM pg_cursors")) == []
            assert connection.execute("SELECT 1 AS n").fetchone()["n"] == 1
            assert connection.execute("SELECT code_version FROM import_run WHERE id=%s", (run_id,)).fetchone()["code_version"] == "uncommitted-marker"
            # 不在第二连接读被 DDL 持有 ACCESS EXCLUSIVE 锁的表。
            assert observer.execute("SELECT code_version FROM import_run WHERE id=%s", (run_id,)).fetchone()["code_version"] == "synthetic-code"
        assert connection.info.transaction_status == TransactionStatus.IDLE
        assert observer.execute("SELECT code_version FROM import_run WHERE id=%s", (run_id,)).fetchone()["code_version"] == "synthetic-code"
    assert connection.execute("SELECT count(*) AS n FROM derivation").fetchone()["n"] == 0
    assert len(load_catalog_state(connection).images) == 1
    assert list(connection.execute("SELECT name FROM pg_cursors")) == []


@pytest.mark.db
@pytest.mark.parametrize("outer_transaction", [False, True])
@pytest.mark.parametrize("protocol", _PROTOCOL_CASES)
def test_state_load_row_failure_closes_cursor(
    connection, test_database_url, import_runner, roots, make_image, outer_transaction, protocol,
):
    run, _, _ = import_runner
    make_image(roots["data"] / "敦煌003/P2002/native.tif")
    run_id, _ = run()
    image = connection.execute("SELECT id, field_basis FROM image").fetchone()
    with psycopg.connect(test_database_url, autocommit=True, row_factory=dict_row) as observer:
        try:
            with connection.transaction(force_rollback=True) if outer_transaction else nullcontext():
                connection.execute("UPDATE image SET field_basis='null'::jsonb WHERE id=%s", (image["id"],))
                if outer_transaction:
                    connection.execute("UPDATE import_run SET code_version='uncommitted-marker' WHERE id=%s", (run_id,))
                with _state_load_protocol(connection, protocol) as commands:
                    with pytest.raises(AttributeError, match="items") as failure:
                        load_catalog_state(connection)
                assert failure.value.__traceback__ is not None
                assert connection.info.transaction_status == (
                    TransactionStatus.INTRANS if outer_transaction else TransactionStatus.IDLE
                )
                assert list(connection.execute("SELECT name FROM pg_cursors")) == []
                assert connection.execute("SELECT 1 AS n").fetchone()["n"] == 1
                assert connection.execute("SELECT code_version FROM import_run WHERE id=%s", (run_id,)).fetchone()["code_version"] == (
                    "uncommitted-marker" if outer_transaction else "synthetic-code"
                )
                assert observer.execute("SELECT code_version FROM import_run WHERE id=%s", (run_id,)).fetchone()["code_version"] == "synthetic-code"
                if protocol:
                    assert commands.count("DECLARE") == commands.count("CLOSE") == 1
                    assert "FETCH FORWARD 128" in commands
                    assert commands.index("CLOSE") < commands.index("ROLLBACK")
                    assert "COMMIT" not in commands
        finally:
            # autocommit 分支的合成坏行已经提交，显式还原；外事务分支已回滚。
            connection.execute("UPDATE image SET field_basis=%s WHERE id=%s", (Jsonb(image["field_basis"]), image["id"]))
        assert connection.info.transaction_status == TransactionStatus.IDLE
        assert observer.execute("SELECT code_version FROM import_run WHERE id=%s", (run_id,)).fetchone()["code_version"] == "synthetic-code"
    assert len(load_catalog_state(connection).images) == 1
    assert list(connection.execute("SELECT name FROM pg_cursors")) == []


@pytest.mark.db
@pytest.mark.parametrize("count", [2, 3])
def test_number_swap_end_to_end(connection, import_runner, roots, make_image, count):
    run, _, _ = import_runner
    base = roots["data"] / "敦煌003"
    names = [f"P{2002 + i}" for i in range(count)]
    for name in names:
        make_image(base / name / "native.tif")
    run()
    before = {row["grouping_key"]: row["id"] for row in connection.execute("SELECT * FROM item")}
    images = {row["inode"]: row["id"] for row in connection.execute("SELECT * FROM image")}
    for i, name in enumerate(names):
        (base / name).rename(base / f"temporary{i}")
    for i in range(count):
        (base / f"temporary{i}").rename(base / names[(i + 1) % count])
    run()
    after = {row["grouping_key"]: row["id"] for row in connection.execute("SELECT * FROM item")}
    assert {row["inode"]: row["id"] for row in connection.execute("SELECT * FROM image")} == images
    for i in range(count):
        assert after[f"pelliot:{2002 + (i + 1) % count}"] == before[f"pelliot:{2002 + i}"]
    assert connection.execute("SELECT count(*) AS n FROM identifier WHERE state = 'historical'").fetchone()["n"] == count
    assert connection.execute("SELECT count(*) AS n FROM image_path_history").fetchone()["n"] == count * 2


@pytest.mark.db
def test_attachment_raw_roundtrip(connection, import_runner, roots, make_image):
    run, _, _ = import_runner
    directory = roots["data"] / "中国国博馆藏/BD12345"
    make_image(directory / "BD12345_0000_0.tif")
    originals = {"manifest.json": _manifest(), "report.json": b'{"strips":0}\r\n',
                 "index.json": b'[1,2,3]', "原文.txt": b'\xff\x00\r\nexact'}
    for name, raw in originals.items():
        (directory / name).write_bytes(raw)
    run()
    assert {PurePosixPath(row["relative_path"]).name: bytes(row["raw"]) for row in connection.execute("SELECT * FROM attachment")} == originals
    assert connection.execute("SELECT count(*) AS n FROM item_attachment").fetchone()["n"] == 4
    rows = list(connection.execute("SELECT * FROM identifier WHERE is_primary AND state = 'current'"))
    assert len(rows) == 1 and rows[0]["source"] == "外部清单"
    (directory / "原文.txt").write_bytes(b"new exact bytes")
    run()
    assert bytes(connection.execute("SELECT raw FROM attachment WHERE kind='text'").fetchone()["raw"]) == b"new exact bytes"


@pytest.mark.db
def test_failed_transaction_rolls_back_and_keeps_snapshot(connection, import_runner, roots, cache, make_image):
    _, prepare, payload = import_runner
    make_image(roots["data"] / "敦煌003/P2002/native.tif")
    (roots["data"] / "敦煌003/P2002/note.txt").write_bytes(b"rollback this")
    volume = base64.urlsafe_b64encode("敦煌003/P2002".encode()).decode().rstrip("=")
    payload["items"] = [{"id": volume}]
    # 真正的 PostgreSQL 写入错误：附件和 item 已写入，image 写入失败。
    connection.execute("""CREATE FUNCTION synthetic_import_failure() RETURNS trigger LANGUAGE plpgsql AS $$
                          BEGIN RAISE EXCEPTION 'synthetic failure'; END; $$""")
    connection.execute("CREATE TRIGGER synthetic_failure BEFORE INSERT ON image FOR EACH ROW EXECUTE FUNCTION synthetic_import_failure()")
    prepared = prepare()
    try:
        with pytest.raises(Exception, match="synthetic failure"):
            prepared.execute(roots, cache)
    finally:
        connection.execute("DROP TRIGGER synthetic_failure ON image")
        connection.execute("DROP FUNCTION synthetic_import_failure()")
    for table in ("item", "image", "attachment", "identifier", "history", "anomaly", "excluded"):
        assert connection.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"] == 0
    record = read_report(connection, prepared.run_id)
    assert record["status"] == "failed" and record["v0_snapshot_status"] == "valid"
    assert list(latest_valid_snapshot(connection).volumes) == [PurePosixPath("敦煌003/P2002")]
    assert "caller-cookie" not in json.dumps(record)
    next_prepared = prepare()
    next_prepared.cancel()


@pytest.mark.db
def test_prepare_holds_lock_and_cancel_releases(connection, import_runner):
    _, prepare, _ = import_runner
    first = prepare()
    try:
        assert read_report(connection, first.run_id)["status"] == "running"
        with pytest.raises(ImportBusy):
            prepare()
    finally:
        first.cancel()
    assert read_report(connection, first.run_id)["status"] == "failed"
    second = prepare()
    second.cancel()
    second.cancel()  # 派发异常清理可重复调用。


@pytest.mark.db
def test_latest_valid_empty_snapshot_not_older_nonempty(connection, import_runner):
    run, _, payload = import_runner
    payload["items"] = [{"id": base64.urlsafe_b64encode(b"synthetic/old").decode().rstrip("=")}]
    run()
    assert latest_valid_snapshot(connection).volumes
    payload["items"] = []
    empty_run, _ = run()
    assert latest_valid_snapshot(connection) is not None
    assert latest_valid_snapshot(connection).volumes == {}
    payload["status"] = "building"
    unavailable_run, report = run()
    assert latest_valid_snapshot(connection).volumes == {}
    assert report["coverage"]["status"] == "unavailable"
    assert empty_run < unavailable_run


@pytest.mark.db
def test_human_conclusion_survives_reimport(connection, import_runner, roots, make_image):
    run, _, _ = import_runner
    make_image(roots["data"] / "敦煌003/P2002/native.tif")
    run()
    item = connection.execute("SELECT * FROM item").fetchone()
    provenance = dict(item["provenance"], status="非敦煌", judge="user:scholar", evidence=["人工核对文献"])
    basis = dict(item["field_basis"])
    basis["provenance"] = dict(basis["provenance"], source="人工", author="user:scholar", confidence="确定")
    connection.execute("UPDATE item SET provenance=%s, field_basis=%s WHERE id=%s", (Jsonb(provenance), Jsonb(basis), item["id"]))
    run()
    after = connection.execute("SELECT * FROM item").fetchone()
    assert after["provenance"] == provenance and after["field_basis"]["provenance"] == basis["provenance"]


@pytest.mark.db
@pytest.mark.parametrize("new_location", [False, True])
def test_missing_marked_not_deleted_and_reappearance(connection, import_runner, roots, make_image, new_location):
    run, _, _ = import_runner
    directory = roots["data"] / "敦煌003/P2002+2003 WB29"
    make_image(directory / "native.tif")
    first, _ = run()
    items = list(connection.execute("SELECT * FROM item ORDER BY serial"))
    image = connection.execute("SELECT * FROM image").fetchone()
    links = list(connection.execute("SELECT * FROM item_image ORDER BY item_id"))
    recycled = roots["data"] / "#recycle"
    directory.rename(recycled)
    missing, report = run()
    assert list(connection.execute("SELECT * FROM item ORDER BY serial")) == items
    assert list(connection.execute("SELECT * FROM item_image ORDER BY item_id")) == links
    row = connection.execute("SELECT * FROM image").fetchone()
    assert row["id"] == image["id"] and row["state"] == "missing" and row["missing_since"]
    assert row["facts"] == image["facts"]
    assert value_at_run(connection, "image", image["id"], first)["snapshot"]["state"] == "present"
    missing_snapshot = value_at_run(connection, "image", image["id"], missing)["snapshot"]
    assert missing_snapshot["state"] == "missing"
    assert [event["kind"] for event in missing_snapshot["events"]] == ["missing"]
    restored = directory.with_name("新位置 P2002+2003 WB29") if new_location else directory
    recycled.rename(restored)
    _, report = run()
    assert report["counts"]["changes"]["images"]["reappeared"] == 1
    row = connection.execute("SELECT * FROM image").fetchone()
    assert row["id"] == image["id"] and row["state"] == "present" and row["missing_since"] is None


@pytest.mark.db
def test_changed_file_history_and_value_at_any_run(connection, import_runner, roots, make_image):
    run, _, _ = import_runner
    path = make_image(roots["data"] / "敦煌003/P2002/native.tif")
    first, _ = run()
    image = connection.execute("SELECT * FROM image").fetchone()
    replacement = make_image(path.parent / "replacement.tif", software="Photoshop synthetic changed content")
    os.replace(replacement, path)
    second, report = run()
    assert report["counts"]["changes"]["images"]["changed"] == 1
    assert report["counts"]["changes"]["images"]["moved"] == 0
    before = value_at_run(connection, "image", image["id"], first)
    after = value_at_run(connection, "image", image["id"], second)
    assert before["snapshot"]["lineage"] == "BnF 原图"
    assert after["snapshot"]["lineage"] == "第三方加工图"
    assert before["snapshot"]["facts"]["software"]["status"] == "missing"
    assert after["snapshot"]["facts"]["software"]["value"] == "Photoshop synthetic changed content"
    assert after["field_basis"]["facts"]["software"]["run"] == second
    assert after["field_basis"]["facts"]["pixel_size"]["run"] == first
    assert all("import-admin" not in json.dumps(row["field_basis"]) for row in connection.execute("SELECT field_basis FROM history"))
    third, _ = run()
    assert value_at_run(connection, "image", image["id"], third)["run_id"] == second


@pytest.mark.db
def test_pending_numbers_and_original_primary_remain_current(connection, import_runner, roots, make_image):
    run, _, _ = import_runner
    base = roots["data"] / "敦煌003"
    for name in ("P2002", "P2003"):
        make_image(base / name / "native.tif")
    run()
    owner = connection.execute("SELECT id FROM item WHERE grouping_key='pelliot:2002'").fetchone()["id"]
    original = connection.execute("SELECT * FROM identifier WHERE item_id=%s", (owner,)).fetchone()
    (base / "P2002").rename(base / "副本 P2003")
    pending_run, _ = run()
    rows = list(connection.execute("SELECT * FROM identifier WHERE item_id=%s AND state != 'historical'", (owner,)))
    assert {(r["normalized"], r["state"], r["is_primary"]) for r in rows} == {("P.2002", "current", True), ("P.2003", "pending", False)}
    pending, = [r for r in rows if r["state"] == "pending"]
    past = value_at_run(connection, "item", owner, pending_run)
    past_pending, = [r for r in past["snapshot"]["identifiers"] if r["state"] == "pending"]
    assert past_pending["normalized"] == "P.2003" and past_pending["raw"] == "P2003"
    assert past_pending["source"] == "文件名解析"
    assert past_pending["source_path"] == "data:敦煌003/副本 P2003"
    assert past_pending["since_run"] == pending_run
    assert past_pending["field_basis"] == pending["field_basis"]
    assert all(b["run"] == pending_run and b["at"] for b in past_pending["field_basis"].values())
    (base / "副本 P2003").rename(base / "P2002")
    run_id, _ = run()
    assert connection.execute("SELECT count(*) AS n FROM identifier WHERE state='pending'").fetchone()["n"] == 0
    assert connection.execute("SELECT count(*) AS n FROM anomaly WHERE run_id=%s AND category='身份待确认'", (run_id,)).fetchone()["n"] == 0
    assert list(connection.execute("SELECT * FROM identifier WHERE item_id=%s", (owner,))) == [original]
    assert connection.execute("SELECT * FROM identifier WHERE id=%s", (pending["id"],)).fetchone() is None
    assert value_at_run(connection, "item", owner, pending_run) == past
    assert not any(r["state"] == "pending" for r in value_at_run(connection, "item", owner, run_id)["snapshot"]["identifiers"])
    # 真正改号仍历史化，而不是跟撤销候选一起删除。
    (base / "P2002").rename(base / "P2004")
    changed_run, _ = run()
    rows = list(connection.execute("SELECT * FROM identifier WHERE item_id=%s", (owner,)))
    assert {(r["normalized"], r["state"]) for r in rows} == {("P.2002", "historical"), ("P.2004", "current")}
    historical, = [r for r in rows if r["state"] == "historical"]
    assert historical == dict(original, state="historical", until_run=changed_run)
    assert value_at_run(connection, "item", owner, pending_run) == past


def _seed_previous_identifier_basis(connection, owners):
    """仅构造合成旧部署编号及配套历史；真实 SQL，不替换导入/规则函数。"""
    with connection.transaction():
        for row in connection.execute("SELECT * FROM identifier WHERE item_id = ANY(%s)", (owners,)):
            connection.execute("UPDATE identifier SET field_basis=%s WHERE id=%s",
                               (Jsonb(_previous_identifier_basis(row)), row["id"]))
        for row in connection.execute(
            "SELECT * FROM history WHERE object_kind='item' AND object_id = ANY(%s)", (owners,),
        ):
            snapshot = row["snapshot"]
            snapshot["identifiers"] = [dict(ident, field_basis=_previous_identifier_basis(ident))
                                       for ident in snapshot["identifiers"]]
            connection.execute("UPDATE history SET snapshot=%s WHERE object_kind='item' AND object_id=%s AND run_id=%s",
                               (Jsonb(snapshot), row["object_id"], row["run_id"]))


@pytest.mark.db
def test_identifier_basis_upgrade_keeps_database_rows_and_history(connection, import_runner, roots, make_image):
    run, _, _ = import_runner
    base = roots["data"] / "敦煌003"
    for name in ("P2001", "P2003"):
        make_image(base / name / "native.tif")
    directory = roots["data"] / "中国国博馆藏/bd12345a"
    make_image(directory / "BD12345a_0000_0.tif")
    (directory / "manifest.json").write_bytes(_manifest("BD12345a"))
    first, _ = run()
    (base / "P2001").rename(base / "P2002")
    changed_run, _ = run()  # 留下真正曾用号，升级不得碰这条 historical。
    (base / "P2002").rename(base / "副本 P2003")
    pending_run, _ = run()
    owners = {row["grouping_key"]: row["id"] for row in connection.execute("SELECT * FROM item")}
    upgraded_owners = [owners["pelliot:2002"], owners["nlc:BD12345a"]]
    _seed_previous_identifier_basis(connection, upgraded_owners)
    query = "SELECT *, xmin::text AS row_version FROM identifier ORDER BY id"
    before = list(connection.execute(query))
    history_query = "SELECT * FROM history ORDER BY object_kind, object_id, run_id"
    past = list(connection.execute(history_query))
    assert {(r["normalized"], r["state"], r["since_run"], r["until_run"])
            for r in before if r["item_id"] == owners["pelliot:2002"]} == {
        ("P.2001", "historical", first, changed_run),
        ("P.2002", "current", changed_run, None), ("P.2003", "pending", pending_run, None),
    }
    nlc_rows = [r for r in before if r["item_id"] == owners["nlc:BD12345a"]]
    assert {(r["system"], r["raw"], r["normalized"], r["source"], r["source_path"], r["is_primary"])
            for r in nlc_rows} == {
        ("nlc", "bd12345a", "BD12345a", "文件名解析", "data:中国国博馆藏/bd12345a", False),
        ("nlc", "BD12345a", "BD12345a", "外部清单", "data:中国国博馆藏/bd12345a/manifest.json", True),
        ("idp", "synthetic-entry", "synthetic-entry", "外部清单", "data:中国国博馆藏/bd12345a/manifest.json", False),
    }
    assert all(r["parent_number"] == "BD12345" and r["part"] == "a" for r in nlc_rows if r["system"] == "nlc")
    upgraded_run, report = run()
    after = list(connection.execute(query))
    record = read_report(connection, upgraded_run)
    started_at, ended_at = (datetime.fromisoformat(record[name]) for name in ("started_at", "ended_at"))
    assert len(after) == len(before)
    for old, new in zip(before, after, strict=True):
        if old["item_id"] in upgraded_owners and old["state"] != "historical":
            assert new == dict(old, field_basis=new["field_basis"], row_version=new["row_version"])
            assert new["row_version"] != old["row_version"]
            for name, leaf in new["field_basis"].items():
                assert leaf == dict(old["field_basis"][name], author="rule:identifier@" + rules.RULE_VERSION,
                                    run=upgraded_run, at=leaf["at"])
                assert started_at <= datetime.fromisoformat(leaf["at"]) <= ended_at
                assert old["field_basis"][name]["author"] == "rule:identifier@previous-version"
                assert leaf["at"] != old["field_basis"][name]["at"]
        else:
            assert new == old  # xmin 也不变：历史行/未变编号没有无条件 UPDATE。
    assert report["counts"]["changes"]["items"] == {"new": 0, "changed": 2}
    history = list(connection.execute(history_query))
    assert [h for h in history if h["run_id"] < upgraded_run] == past
    assert len(history) == len(past) + 2
    for owner in upgraded_owners:
        latest = value_at_run(connection, "item", owner, upgraded_run)
        assert latest["run_id"] == upgraded_run
        expected = [{key: value for key, value in row.items() if key not in {"id", "until_run", "row_version"}}
                    for row in after if row["item_id"] == owner and row["state"] != "historical"]
        assert sorted(latest["snapshot"]["identifiers"], key=lambda r: r["raw"]) == sorted(_json_value(expected), key=lambda r: r["raw"])
    repeated_run, report = run()
    assert list(connection.execute(query)) == after  # 包括完整字段及 xmin；不是只有行数没变。
    assert list(connection.execute(history_query)) == history
    assert report["counts"]["changes"]["items"] == {"new": 0, "changed": 0}
    for owner in upgraded_owners:
        assert value_at_run(connection, "item", owner, repeated_run)["run_id"] == upgraded_run


@pytest.mark.db
def test_rule_version_change_recorded_at_batch(connection, import_runner, roots, make_image):
    run, _, _ = import_runner
    make_image(roots["data"] / "敦煌003/P2002/native.tif")
    first, _ = run()
    image = connection.execute("SELECT * FROM image").fetchone()
    # 将已存数据设为旧部署规则版本，下一轮运行真实当前规则；不 mock 规则函数。
    basis = image["field_basis"]
    basis["facts"]["pixel_size"]["author"] = "rule:file-header@previous-version"
    snapshot = value_at_run(connection, "image", image["id"], first)["snapshot"]
    snapshot["field_basis"] = basis
    connection.execute("UPDATE image SET field_basis=%s WHERE id=%s", (Jsonb(basis), image["id"]))
    connection.execute("UPDATE history SET snapshot=%s, field_basis=%s WHERE object_kind='image' AND object_id=%s AND run_id=%s",
                       (Jsonb(snapshot), Jsonb(basis), image["id"], first))
    second, report = run()
    old = value_at_run(connection, "image", image["id"], first)
    new = value_at_run(connection, "image", image["id"], second)
    assert old["field_basis"]["facts"]["pixel_size"]["author"].endswith("@previous-version")
    assert new["field_basis"]["facts"]["pixel_size"]["author"].endswith("@" + rules.RULE_VERSION)
    assert new["field_basis"]["facts"]["pixel_size"]["run"] == second
    assert old["snapshot"]["facts"] == new["snapshot"]["facts"]
    assert report["counts"]["changes"]["images"]["metadata_changed"] == 1


@pytest.mark.db
def test_failed_current_empty_snapshot_is_retained(connection, import_runner, roots, cache, make_image):
    run, prepare, payload = import_runner
    payload["items"] = [{"id": base64.urlsafe_b64encode(b"synthetic/old").decode().rstrip("=")}]
    run()
    payload["items"] = []
    # 无扫描根是真实文件系统异常；不启动数据库或伪造失败返回。
    absent_roots = dict(roots, data=roots["data"] / "absent")
    prepared = prepare()
    with pytest.raises(FileNotFoundError):
        prepared.execute(absent_roots, cache)
    assert read_report(connection, prepared.run_id)["status"] == "failed"
    assert read_report(connection, prepared.run_id)["v0_snapshot_status"] == "valid"
    assert latest_valid_snapshot(connection).volumes == {}


@pytest.mark.db
def test_report_cli_readonly_without_auth_files(connection, import_runner, test_database_url, tmp_path):
    run, _, _ = import_runner
    run_id, _ = run()
    count = connection.execute("SELECT count(*) AS n FROM import_run").fetchone()["n"]
    env = dict(os.environ, DH_DATABASE_URL=test_database_url,
               DH_V0_ENV_FILE=str(tmp_path / "must-not-read.env"), DH_V0_URL="must-not-load-http-settings",
               PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"))
    result = subprocess.run([sys.executable, "-X", "utf8", "-m", "dh_catalog", "report", "--run", str(run_id)],
                            env=env, capture_output=True, encoding="utf-8", check=False)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["id"] == run_id
    assert "caller-cookie" not in result.stdout
    assert connection.execute("SELECT count(*) AS n FROM import_run").fetchone()["n"] == count
