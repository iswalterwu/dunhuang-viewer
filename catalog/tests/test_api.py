"""真实 HTTP 路由 + 临时 PostgreSQL；只在 v0 HTTP 边界使用替身。"""

import base64
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
from threading import Event
import time
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from dh_catalog import rules
from dh_catalog.api import create_app
from dh_catalog.config import load_settings
from dh_catalog.importer import prepare_import
from test_auth import _cookie, auth_files  # 共用合成认证输入，不替换认证实现。
from test_import import _manifest, _seed_previous_identifier_basis, cache, host_records  # 共用合成白名单与旧部署输入。


def _login(client, secret, username="owner"):
    token = _cookie(username, secret, int(time.time()) + 3600)
    client.cookies.set("dh_session", token)
    return token


def _join(app):
    for thread in app.state.import_threads:
        thread.join(10)
        assert not thread.is_alive(), "真实后台导入未在测试时限内结束"


@pytest.fixture
def api_db(connection, test_database_url, roots, cache, auth_files):
    settings, _, secret = auth_files
    # 认证与导入共用这个临时 cache；其余白名单全是合成材料。
    (cache / "users.json").write_bytes((settings.v0_cache_dir / "users.json").read_bytes())
    settings = replace(settings, data_dir=roots["data"], backup_dir=roots["backup"], v0_cache_dir=cache,
                       database_url=test_database_url, code_version="api-synthetic-code")
    payload = {"status": "ready", "items": []}
    requests = []
    entered, release = Event(), Event()
    control = {"block": False}

    def handler(request):
        requests.append((request.url.path, request.headers["cookie"]))
        if request.url.path == "/api/index":
            if control["block"]:
                entered.set()
                assert release.wait(10), "测试没有释放 v0 HTTP 边界"
            return httpx.Response(200, json=payload)
        assert request.url.path == "/api/health"
        return httpx.Response(200, json={"ok": True})

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        app = create_app(settings, http_client=http)
        with TestClient(app) as client:
            pool = app.state.pool
            assert not pool.closed
            token = _login(client, secret)

            def run():
                prepared = prepare_import(app.state.pool, triggered_by="owner", code_version=settings.code_version,
                                          session_cookie=token, v0_url=settings.v0_url, http_client=http)
                return prepared.run_id, prepared.execute(roots, cache)

            try:
                yield SimpleNamespace(client=client, app=app, run=run, payload=payload, requests=requests,
                                      settings=settings, token=token, http=http, secret=secret,
                                      control=control, entered=entered, release=release)
            finally:
                release.set()
                _join(app)
        assert app.state.pool is None and pool.closed


def _resolve(api, q):
    response = api.client.get("/api/v1/resolve", params={"q": q})
    assert response.status_code == 200, response.text
    return response.json()["items"]


def _item(api, q):
    row, = _resolve(api, q)
    response = api.client.get(f"/api/v1/items/{row['id']}")
    assert response.status_code == 200, response.text
    return response.json()


def _list(api, **params):
    response = api.client.get("/api/v1/items", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_no_mutating_routes(auth_files):
    settings, _, secret = auth_files
    app = create_app(settings)
    writes = {(method, route.path) for route in app.routes for method in route.methods
              if method not in {"GET", "HEAD"}}
    assert writes == {("POST", "/api/v1/imports")}
    expected = {"/api/v1/items", "/api/v1/items/{id}", "/api/v1/items/{id}/history", "/api/v1/resolve",
                "/api/v1/images/{id}", "/api/v1/images/{id}/history", "/api/v1/attachments/{id}",
                "/api/v1/anomalies", "/api/v1/imports", "/api/v1/imports/{id}"}
    assert expected <= {route.path for route in app.routes}
    with TestClient(app) as client:
        for path in ("/api/v1/docs", "/api/v1/openapi.json", "/api/v1/items", "/api/v1/imports"):
            assert client.get(path).status_code == 401
        assert client.post("/api/v1/imports").status_code == 401
        _login(client, secret, "reader")
        assert client.get("/api/v1/docs").status_code == 200
        schema = client.get("/api/v1/openapi.json").json()
        assert expected <= schema["paths"].keys()
        assert client.post("/api/v1/imports").status_code == 403
        assert client.delete("/api/v1/items/" + str(uuid4())).status_code == 405


def test_no_database_explicitly_unavailable(auth_files):
    settings, _, secret = auth_files
    assert settings.database_url is None
    app = create_app(settings)
    with TestClient(app) as client:
        _login(client, secret)
        for path in ("/api/v1/items", "/api/v1/resolve?q=P2002", "/api/v1/anomalies", "/api/v1/imports",
                     f"/api/v1/items/{uuid4()}", f"/api/v1/images/{uuid4()}", f"/api/v1/attachments/{uuid4()}"):
            assert client.get(path).status_code == 503
        assert client.post("/api/v1/imports").status_code == 503
        assert app.state.pool is None
        assert not app.state.import_threads


def test_secret_missing_rejects_data_and_trigger(auth_files):
    settings, _, secret = auth_files
    with TestClient(create_app(replace(settings, auth_secret=None))) as client:
        _login(client, secret)
        for path in ("/api/v1/items", "/api/v1/imports", "/api/v1/docs", "/api/v1/openapi.json"):
            assert client.get(path).status_code == 503
        assert client.post("/api/v1/imports").status_code == 503


@pytest.mark.db
def test_auth_and_admin_import(api_db, connection, roots, make_image):
    api = api_db
    make_image(roots["data"] / "敦煌003/P2002/native.tif")
    api.client.cookies.clear()
    assert api.client.get("/api/v1/items").status_code == 401
    assert api.client.post("/api/v1/imports").status_code == 401
    _login(api.client, api.secret, "reader")
    assert api.client.get("/api/v1/items").json()["total"] == 0
    assert api.client.post("/api/v1/imports").status_code == 403
    token = _login(api.client, api.secret)
    held = prepare_import(api.app.state.pool, triggered_by="owner", code_version="held-lock",
                          session_cookie=token, v0_url=api.settings.v0_url, http_client=api.http)
    try:
        assert api.client.post("/api/v1/imports").status_code == 409
        assert not api.app.state.import_threads
        assert connection.execute("SELECT count(*) AS n FROM import_run").fetchone()["n"] == 1
    finally:
        held.cancel()
    api.control["block"] = True
    response = api.client.post("/api/v1/imports")
    assert response.status_code == 202
    run = response.json()["id"]
    assert api.entered.wait(5)
    try:
        record = api.client.get(f"/api/v1/imports/{run}").json()
        assert record["status"] == "running" and record["triggered_by"] == "owner"
        assert record["code_version"] == "api-synthetic-code"
        assert api.client.post("/api/v1/imports").status_code == 409
    finally:
        api.release.set()
    _join(api.app)
    record = api.client.get(f"/api/v1/imports/{run}").json()
    assert record["status"] == "succeeded"
    assert record["report"]["counts"]["items"] == 1
    assert record["report"]["health"]["count"] >= 1
    assert all(cookie == f"dh_session={token}" for _, cookie in api.requests)
    assert token not in json.dumps(record)
    assert api.settings.auth_secret not in json.dumps(record)
    _login(api.client, api.secret, "reader")
    assert api.client.get(f"/api/v1/imports/{run}").status_code == 200
    assert api.client.get("/api/v1/items").json()["total"] == 1


@pytest.mark.db
@pytest.mark.parametrize("configured", [False, True])
def test_background_import_uses_configured_record_roots(api_db, host_records, configured):
    api = api_db
    settings = load_settings(host_records)
    if configured:
        api.app.state.settings = replace(api.settings, record_roots=settings.record_roots)
    else:
        assert api.app.state.settings.record_roots == {}
    response = api.client.post("/api/v1/imports")
    assert response.status_code == 202
    _join(api.app)
    record = api.client.get(f"/api/v1/imports/{response.json()['id']}").json()
    assert record["status"] == "succeeded"
    assert record["rule_version"] == "2026-10-30.1"
    assert record["report"]["counts"]["outputs_with_derivation"] == int(configured)
    item = _item(api, "P2002")
    output, = [row for row in item["images"] if row["lineage"] == "本地合成"]
    sources = [row for row in item["images"] if row["root"] == "backup"]
    assert len(sources) == 2 and item["display_policy"] == "仅供研究使用"
    assert {row["acquisition"] for row in sources} == {"第三方资料接收（接收事件 A）"}
    assert output["display_policy"] == "仅供研究使用" and output["external_policy"] == "不对外"
    if configured:
        assert output["license"] == rules.PROCESSED_LICENSE
        assert {edge["source_image_id"] for edge in output["derivations"]} == {row["id"] for row in sources}
        assert len(output["derivations"]) == 2
        assert output["field_basis"]["license"]["source_images"] == sorted(row["id"] for row in sources)
        assert all(edge["method"] == "拼接" and edge["evidence_file"] == "merge_all.log"
                   and edge["evidence_line"] == 5 for edge in output["derivations"])
    else:
        assert output["license"] == rules.UNKNOWN_LICENSE and not output["derivations"]
        assert any("不是 data / backup" in anomaly["description"] for anomaly in record["report"]["anomalies"])
    history = api.client.get(f"/api/v1/images/{output['id']}/history", params={"run": record["id"]})
    assert history.status_code == 200
    assert history.json()["snapshot"]["license"] == output["license"]
    assert history.json()["snapshot"]["derivations"] == output["derivations"]


@pytest.mark.db
def test_background_failure_recorded_and_lock_released(api_db, roots, make_image, caplog):
    api = api_db
    make_image(roots["data"] / "敦煌003/P2002/native.tif")
    roots["data"].rename(roots["data"].with_name("temporarily-absent"))
    response = api.client.post("/api/v1/imports")
    assert response.status_code == 202
    _join(api.app)
    failed = api.client.get(f"/api/v1/imports/{response.json()['id']}").json()
    assert failed["status"] == "failed" and failed["error"] == "FileNotFoundError"
    assert api.token not in caplog.text and api.settings.auth_secret not in caplog.text
    roots["data"].with_name("temporarily-absent").rename(roots["data"])
    response = api.client.post("/api/v1/imports")
    assert response.status_code == 202
    _join(api.app)
    assert api.client.get(f"/api/v1/imports/{response.json()['id']}").json()["status"] == "succeeded"


@pytest.mark.db
def test_resolve(api_db, roots, make_image):
    api = api_db
    for name in ("P2002", "WB29 甲", "WB 29 乙", "P2504", "P2504-1Pièce", "P2504-2", "P2504-3", "P2504-4",
                 "P.0901 甲", "P.0901 乙", "P.0901 丙", "敦煌藏經洞 1 令字", "P2006", "P2007"):
        make_image(roots["data"] / "敦煌003" / name / "native.tif")
    directory = roots["data"] / "中国国博馆藏/BD00001"
    make_image(directory / "BD00001_0000_0.tif")
    (directory / "manifest.json").write_bytes(_manifest("BD00001", "EXTERNAL-IDP"))
    api.run()
    expected = _resolve(api, "P.2002")
    assert len(expected) == 1
    for q in ("P2002", "pelliot chinois 2002", "p.2002"):
        assert _resolve(api, q) == expected
    assert len(_resolve(api, "wb29")) == 2
    assert len(_resolve(api, "P.2504")) == 5
    assert len(_resolve(api, "p2504-1")) == 1
    assert len(_resolve(api, "p0901")) == 3
    assert len(_resolve(api, "令字")) == 1
    assert _resolve(api, "bd00001") == _resolve(api, "external-idp")
    nlc = _item(api, "bd00001")
    assert not any(i["is_primary"] for i in nlc["identifiers"] if i["system"] == "idp")
    assert nlc["images"][0]["canvas_number"] == 0
    assert nlc["images"][0]["canvas_id"] == "https://example.invalid/canvas/0"
    assert nlc["images"][0]["field_basis"]["attribution"]["source"] == "外部清单"
    (roots["data"] / "敦煌003/P2006").rename(roots["data"] / "敦煌003/P2008")
    (roots["data"] / "敦煌003/P2007").rename(roots["data"] / "敦煌003/副本 P2002")
    pending_run, _ = api.run()
    assert not _resolve(api, "P2006")
    assert len(_resolve(api, "P2008")) == 1
    assert _resolve(api, "P2002")[0]["id"] == expected[0]["id"]
    assert len(_resolve(api, "P2002")) == 1  # 待确认号不是额外命中。
    pending = _item(api, "P2007")
    assert any(i["normalized"] == "P.2002" and i["state"] == "pending" for i in pending["identifiers"])
    changed = _item(api, "P2008")
    assert any(i["normalized"] == "P.2006" and i["state"] == "historical" for i in changed["identifiers"])
    assert _resolve(api, "not-a-number") == []
    assert _resolve(api, "' OR TRUE --") == []
    history_url = f"/api/v1/items/{pending['id']}/history"
    response = api.client.get(history_url, params={"run": pending_run})
    assert response.status_code == 200
    past = response.json()
    past_pending, = [i for i in past["snapshot"]["identifiers"] if i["state"] == "pending"]
    current_pending, = [i for i in pending["identifiers"] if i["state"] == "pending"]
    assert past_pending["normalized"] == "P.2002"
    assert past_pending["source_path"] == "data:敦煌003/副本 P2002"
    assert past_pending["source"] == "文件名解析"
    assert past_pending["field_basis"] == current_pending["field_basis"]
    assert past_pending["since_run"] == pending_run
    (roots["data"] / "敦煌003/副本 P2002").rename(roots["data"] / "敦煌003/P2007")
    restored_run, _ = api.run()
    restored = _item(api, "P2007")
    assert restored["id"] == pending["id"]
    assert {(i["normalized"], i["state"]) for i in restored["identifiers"]} == {("P.2007", "current")}
    assert api.client.get(history_url, params={"run": pending_run}).json() == past
    latest = api.client.get(history_url, params={"run": restored_run})
    assert latest.status_code == 200
    assert not any(i["state"] == "pending" for i in latest.json()["snapshot"]["identifiers"])
    assert _resolve(api, "P2002")[0]["id"] == expected[0]["id"]
    assert len(_resolve(api, "P2002")) == 1
    assert not _resolve(api, "P2006")
    assert any(i["normalized"] == "P.2006" and i["state"] == "historical"
               for i in _item(api, "P2008")["identifiers"])


@pytest.mark.db
def test_identifier_basis_upgrade_detail_resolve_and_history(api_db, connection, roots, make_image):
    api = api_db
    base = roots["data"] / "敦煌003"
    for name in ("P2002", "P2003"):
        make_image(base / name / "native.tif")
    directory = roots["data"] / "中国国博馆藏/bd12345a"
    make_image(directory / "BD12345a_0000_0.tif")
    (directory / "manifest.json").write_bytes(_manifest("BD12345a"))
    api.run()
    (base / "P2002").rename(base / "副本 P2003")
    pending_run, _ = api.run()
    owners = [row["id"] for row in connection.execute(
        "SELECT id FROM item WHERE grouping_key IN ('pelliot:2002', 'nlc:BD12345a')")]
    _seed_previous_identifier_basis(connection, owners)
    queries = ("P2002", "bd12345a")
    before = {q: _item(api, q) for q in queries}
    past = {}
    for q, detail in before.items():
        response = api.client.get(f"/api/v1/items/{detail['id']}/history", params={"run": pending_run})
        assert response.status_code == 200
        past[q] = response.json()
        assert all(leaf["author"] == "rule:identifier@previous-version"
                   for row in past[q]["snapshot"]["identifiers"] for leaf in row["field_basis"].values())
    current_holder = _resolve(api, "P2003")
    assert len(current_holder) == 1 and current_holder[0]["id"] != before["P2002"]["id"]
    upgraded_run, _ = api.run()
    new_history = {}
    for q in queries:
        detail = _item(api, q)
        assert detail["id"] == before[q]["id"]
        assert not any(r["state"] == "historical" for r in detail["identifiers"])
        old_rows = {r["id"]: r for r in before[q]["identifiers"]}
        assert {r["id"] for r in detail["identifiers"]} == set(old_rows)
        for row in detail["identifiers"]:
            old = old_rows[row["id"]]
            assert row == dict(old, field_basis=row["field_basis"])
            for name, leaf in row["field_basis"].items():
                assert leaf == dict(old["field_basis"][name], author="rule:identifier@" + rules.RULE_VERSION,
                                    run=upgraded_run, at=leaf["at"])
                assert leaf["at"] != old["field_basis"][name]["at"]
        history_url = f"/api/v1/items/{detail['id']}/history"
        assert api.client.get(history_url, params={"run": pending_run}).json() == past[q]
        response = api.client.get(history_url, params={"run": upgraded_run})
        assert response.status_code == 200
        new_history[q] = response.json()
        assert new_history[q]["run_id"] == upgraded_run
        expected = [{k: v for k, v in row.items() if k not in {"id", "until_run"}}
                    for row in detail["identifiers"]]
        assert sorted(new_history[q]["snapshot"]["identifiers"], key=lambda r: r["raw"]) == sorted(expected, key=lambda r: r["raw"])
    pending = _item(api, "P2002")
    assert {(r["normalized"], r["state"], r["is_primary"]) for r in pending["identifiers"]} == {
        ("P.2002", "current", True), ("P.2003", "pending", False),
    }
    nlc = _item(api, "bd12345a")
    assert {(r["raw"], r["source"], r["is_primary"]) for r in nlc["identifiers"]} == {
        ("bd12345a", "文件名解析", False), ("BD12345a", "外部清单", True),
        ("synthetic-entry", "外部清单", False),
    }
    assert _resolve(api, "P2003") == current_holder
    assert _resolve(api, "bd12345a") == _resolve(api, "synthetic-entry")
    repeated_run, _ = api.run()
    for q, detail in (("P2002", pending), ("bd12345a", nlc)):
        assert _item(api, q)["identifiers"] == detail["identifiers"]
        history_url = f"/api/v1/items/{detail['id']}/history"
        assert api.client.get(history_url, params={"run": repeated_run}).json() == dict(new_history[q], requested_run=repeated_run)
        assert api.client.get(history_url, params={"run": pending_run}).json() == past[q]


@pytest.mark.db
def test_filters_and_pagination(api_db, roots, make_image):
    api = api_db
    paths = ["188敦煌001/2018年/P2002+2003/native.tif", "188敦煌001/2018年/P2002+2003/native(1).tif",
             "敦煌003/P2002/native.tif", "敦煌003/P2004/native.tif", "敦煌003/WB29 甲/native.tif",
             "敦煌003/WB29 乙/native.tif", "敦煌003/P2005/processed.tif"]
    for path in paths:
        make_image(roots["data"] / path, software="Photoshop" if "processed" in path else "")
    api.run()
    all_rows = _list(api)
    assert all_rows["total"] == 6
    pages = [_list(api, page=n, page_size=2) for n in range(1, 5)]
    assert all(p["total"] == 6 for p in pages)
    assert [i["id"] for p in pages for i in p["items"]] == [i["id"] for i in all_rows["items"]]
    assert _list(api, system="pelliot")["total"] == 4
    assert _list(api, system="sharer", provenance="待核")["total"] == 2
    assert _list(api, lineage="第三方加工图")["total"] == 1
    assert _list(api, category="188敦煌001", batch="2018年")["total"] == 2
    assert _list(api, category="敦煌003", batch="P2004")["total"] == 0
    assert _list(api, has_anomaly=True)["total"] == 2
    assert _list(api, has_anomaly=False)["total"] == 4
    assert _list(api, category="' OR TRUE --")["total"] == 0
    # 当前位置筛选：移走后旧分类不命中；缺失影像仍用末见位置。
    (roots["data"] / "188敦煌001/2018年/P2002+2003").rename(roots["data"] / "敦煌003/P2002+2003")
    (roots["data"] / "敦煌003/P2004/native.tif").unlink()
    api.run()
    assert _list(api, category="188敦煌001")["total"] == 0
    assert _list(api, category="敦煌003")["total"] == 6


@pytest.mark.db
def test_anomaly_associations_and_latest_success(api_db, connection, roots, make_image):
    api = api_db
    # 分别真实产生 image、unit、file(附件)、file(输出)、item 异常。
    for name in ("P2002", "P2003", "P2004", "P2005", "P2006 室町", "P2007"):
        make_image(roots["data"] / "敦煌003" / name / "native.tif")
    (roots["data"] / "敦煌003/P2002/native.tif").write_bytes(b"broken header")
    make_image(roots["data"] / "敦煌003/P2003/.hidden.tif")
    make_image(roots["data"] / "敦煌003/P2004/合并长卷.tif")
    directory = roots["data"] / "中国国博馆藏/BD00001"
    make_image(directory / "BD00001_0000_0.tif")
    (directory / "manifest.json").write_bytes(_manifest("BD00001"))
    (directory / "report.json").write_bytes(b"invalid json")
    run, _ = api.run()
    anomalous = {i["grouping_key"] for i in _list(api, has_anomaly=True)["items"]}
    assert anomalous == {"pelliot:2002", "pelliot:2003", "pelliot:2004", "pelliot:2006", "nlc:BD00001"}
    # 全局白名单缺失异常不会关联到正常写卷；失败批次也不会取代成功批次。
    (api.settings.v0_cache_dir / "merge_all.log").unlink()
    (roots["data"] / "敦煌003/P2002/native.tif").unlink()
    make_image(roots["data"] / "敦煌003/P2002/native.tif")
    api.run()
    anomalous.remove("pelliot:2002")
    assert {i["grouping_key"] for i in _list(api, has_anomaly=True)["items"]} == anomalous
    prepared = prepare_import(api.app.state.pool, triggered_by="owner", code_version="failed",
                              session_cookie=api.token, v0_url=api.settings.v0_url, http_client=api.http)
    prepared.cancel()
    assert {i["grouping_key"] for i in _list(api, has_anomaly=True)["items"]} == anomalous
    assert connection.execute("SELECT status FROM import_run WHERE id=%s", (run,)).fetchone()["status"] == "succeeded"


@pytest.mark.db
def test_merge_suggestion_filter_both_ends_without_other_anomalies(api_db, connection, roots, make_image):
    api = api_db
    for name in ("WB29 甲", "WB29 乙", "P2002"):
        make_image(roots["data"] / "敦煌003" / name / "native.tif")
    run, _ = api.run()
    # 真实库隔离夹具：保留真实 compute 生成的建议，只移除会掩盖关联缺口的无号异常。
    connection.execute("DELETE FROM anomaly WHERE category <> %s", ("合并建议",))
    suggestions = api.client.get("/api/v1/anomalies", params={"run": run, "category": "合并建议"}).json()
    assert suggestions["total"] == 2
    assert {a["object_key"] for a in suggestions["items"]} == {"data:敦煌003/WB29 甲", "data:敦煌003/WB29 乙"}
    assert {i["id"] for i in _list(api, has_anomaly=True)["items"]} == {i["id"] for i in _resolve(api, "WB29")}
    assert _list(api, has_anomaly=False)["total"] == 1


@pytest.mark.db
def test_derivation_details(api_db, roots, make_image):
    api = api_db
    directory = roots["data"] / "敦煌003/P2002"
    make_image(directory / "source.psb")
    make_image(directory / "合并长卷.tif")
    (api.settings.v0_cache_dir / "psb_convert.log").write_text(
        "===== 11:00:00 转换: 敦煌003/P2002 =====\nPSBNAME: source.psb\n"
        "TIFF 完成: /data/敦煌003/P2002/合并长卷_psb.tif  7 x 5\n已替换合并长卷.tif\n退出码: 0\n",
        encoding="utf-8")
    api.run()
    item = _item(api, "P2002")
    output = next(i for i in item["images"] if i["kind"] == "tiff")
    source = next(i for i in item["images"] if i["kind"] == "psb")
    edge, = output["derivations"]
    assert edge["source_image_id"] == source["id"] and edge["method"] == "PSB 转换"
    assert edge["evidence_file"] == "psb_convert.log" and edge["evidence_line"] == 4
    assert edge["field_basis"]["method"]["source"] == "执行记录"
    assert output["license"] == source["license"]
    assert api.client.get(f"/api/v1/images/{output['id']}").json()["derivations"] == output["derivations"]


@pytest.mark.db
def test_details_attachments_history_and_reports(api_db, roots, make_image):
    api = api_db
    parent = roots["data"] / "敦煌003/P2504"
    directory = roots["data"] / "敦煌003/P2504-1"
    make_image(parent / "native.tif")
    image_path = make_image(directory / "native.tif")
    raw = b"\xff\x00original\r\n\xef\xbb\xbf"
    (directory / "原文.txt").write_bytes(raw)
    (directory.parent / "分类说明.txt").write_bytes(b"unassigned")
    (directory / "excluded.pdf").write_bytes(b"excluded")
    first, report = api.run()
    part = _item(api, "P2504-1")
    assert part["parent"]["grouping_key"] == "pelliot:2504"
    parent_row = _resolve(api, "P2504")[0]
    parent_detail = api.client.get(f"/api/v1/items/{parent_row['id']}").json()
    assert [i["id"] for i in parent_detail["parts"]] == [part["id"]]
    assert part["original_positions"][0]["name"] == "P2504-1"
    assert part["field_basis"] and part["provenance_history"]
    image, = part["images"]
    assert image["relationship"]["role"] == "单幅整卷"
    assert image["facts"]["software"]["status"] == "missing"
    assert image["license"] and image["acquisition"] and image["field_basis"]
    attachment, = part["attachments"]
    (directory / "原文.txt").unlink()  # API 必须从数据库取回，不再读取文件。
    response = api.client.get(f"/api/v1/attachments/{attachment['id']}")
    assert response.content == raw and response.headers["content-type"] == "application/octet-stream"
    replacement = make_image(directory / "replacement.tif", software="Photoshop synthetic")
    os.replace(replacement, image_path)
    second, _ = api.run()
    directory.rename(directory.with_name("P2504-1 新位置"))
    third, _ = api.run()
    for kind, id in (("items", part["id"]), ("images", image["id"])):
        before = api.client.get(f"/api/v1/{kind}/{id}/history", params={"run": first})
        assert before.status_code == 200
        assert before.json()["field_basis"]
        assert before.json()["requested_run"] == first
    old = api.client.get(f"/api/v1/images/{image['id']}/history?run={first}").json()
    new = api.client.get(f"/api/v1/images/{image['id']}/history?run={second}").json()
    assert old["snapshot"]["lineage"] == "BnF 原图"
    assert new["snapshot"]["lineage"] == "第三方加工图"
    assert new["field_basis"]["facts"]["software"]["author"].startswith("rule:")
    latest = api.client.get(f"/api/v1/images/{image['id']}").json()
    assert len(latest["path_history"]) == 2 and len(latest["history"]) == 3
    assert latest["original_path"] == "敦煌003/P2504-1/native.tif"
    anomalies = api.client.get("/api/v1/anomalies", params={"run": first, "category": "未导入的文件", "page_size": 1}).json()
    assert anomalies["total"] == 1 and len(anomalies["items"]) == 1  # excluded 已汇入，不 UNION 两次。
    imports = api.client.get("/api/v1/imports", params={"page_size": 1}).json()
    assert imports["total"] == 3 and imports["items"][0]["id"] == third
    record = api.client.get(f"/api/v1/imports/{first}").json()
    assert record["report"] == report and "counts" not in record
    assert record["report"]["unassigned_attachments"]
    assert len(record["report"]["cache_access"]) == 13
    assert record["v0_snapshot_status"] == "valid"


@pytest.mark.db
def test_v0_links(api_db, roots, make_image):
    api = api_db
    relative = "敦煌003/P2002"
    for path in (f"{relative}/native.tif", f"{relative}/work.psb", "敦煌003/P2003/native.tif",
                 "188敦煌001/2018年/P4508 散放.tif", "中国国博馆藏/BD00001/pages/0000_7x5.jpg"):
        make_image(roots["data"] / path)
    make_image(roots["backup"] / f"{relative}/分段/1.tif")
    indexed = [relative, "188敦煌001/2018年"]
    api.payload["items"] = [{"id": base64.urlsafe_b64encode(path.encode()).decode().rstrip("=")} for path in indexed]
    api.run()
    item = _item(api, "P2002")
    links = {(i["root"], i["kind"]): i["v0_link"] for i in item["images"]}
    assert links["data", "tiff"]["url"].endswith("/view/" + api.payload["items"][0]["id"])
    assert links["data", "psb"]["url"] is None and "PSB" in links["data", "psb"]["reason"]
    assert "备份" in links["backup", "tiff"]["reason"]
    assert "索引" in _item(api, "P2003")["images"][0]["v0_link"]["reason"]
    assert "JPG" in _item(api, "BD00001")["images"][0]["v0_link"]["reason"]
    loose = _item(api, "P4508")["images"][0]["v0_link"]["url"]
    assert "?file=" in loose  # 附文件名，不保证 v0 定位到这个文件。
    directory = roots["data"] / relative
    directory.rename(directory.with_name("临时移走"))
    assert "目录已不存在" in next(i for i in _item(api, "P2002")["images"] if i["root"] == "data" and i["kind"] == "tiff")["v0_link"]["reason"]
    directory.with_name("临时移走").rename(directory)
    (directory / "native.tif").unlink()
    api.run()
    assert "影像缺失" in next(i for i in _item(api, "P2002")["images"] if i["root"] == "data" and i["kind"] == "tiff")["v0_link"]["reason"]


@pytest.mark.db
def test_v0_empty_failed_snapshot_and_never_valid(api_db, roots, make_image):
    api = api_db
    path = make_image(roots["data"] / "敦煌003/P2002/native.tif")
    api.payload["status"] = "building"
    api.run()
    assert "从未" in _item(api, "P2002")["images"][0]["v0_link"]["reason"]
    api.payload.update(status="ready", items=[{"id": base64.urlsafe_b64encode("敦煌003/P2002".encode()).decode().rstrip("=")}])
    api.run()
    assert _item(api, "P2002")["images"][0]["v0_link"]["url"]
    api.payload["items"] = []
    prepared = prepare_import(api.app.state.pool, triggered_by="owner", code_version="failed-empty",
                              session_cookie=api.token, v0_url=api.settings.v0_url, http_client=api.http)
    with pytest.raises(FileNotFoundError):
        prepared.execute(dict(roots, backup=roots["backup"] / "absent"), api.settings.v0_cache_dir)
    assert path.exists()
    link = _item(api, "P2002")["images"][0]["v0_link"]
    assert link["url"] is None and "不在" in link["reason"]
    api.payload["status"] = "building"
    api.run()
    assert _item(api, "P2002")["images"][0]["v0_link"]["url"] is None


@pytest.mark.db
def test_http_parameter_validation_and_not_found(api_db, roots, make_image):
    api = api_db
    before, _ = api.run()
    make_image(roots["data"] / "敦煌003/P2002/native.tif")
    run, _ = api.run()
    item = _item(api, "P2002")
    image = item["images"][0]
    for path in ("/api/v1/items?page=0", "/api/v1/items?page_size=201", "/api/v1/items?page_size=0",
                 "/api/v1/items?has_anomaly=maybe", "/api/v1/items?system=unknown", "/api/v1/items/not-uuid",
                 "/api/v1/images/not-uuid", "/api/v1/resolve?q=", "/api/v1/resolve", "/api/v1/anomalies?run=0",
                 "/api/v1/anomalies?page=-1", "/api/v1/imports?page_size=201", "/api/v1/imports/not-integer",
                 f"/api/v1/items/{item['id']}/history", f"/api/v1/images/{image['id']}/history?run=no"):
        assert api.client.get(path).status_code == 422, path
    for path in (f"/api/v1/items/{uuid4()}", f"/api/v1/images/{uuid4()}", f"/api/v1/attachments/{uuid4()}",
                 f"/api/v1/imports/{run + 100}", f"/api/v1/anomalies?run={run + 100}",
                 f"/api/v1/items/{item['id']}/history?run={run + 100}",
                 f"/api/v1/items/{item['id']}/history?run={before}",
                 f"/api/v1/images/{image['id']}/history?run={before}"):
        assert api.client.get(path).status_code == 404, path


@pytest.mark.db
def test_health_cli_readonly_and_migration_check(api_db, connection, test_database_url, tmp_path):
    api = api_db
    env = dict(os.environ, DH_DATABASE_URL=test_database_url, DH_V0_ENV_FILE=str(api.settings.v0_env_file),
               DH_DATA_DIR=str(tmp_path / "must-not-read"), DH_BACKUP_DIR=str(tmp_path / "must-not-read"),
               DH_V0_CACHE_DIR=str(tmp_path / "must-not-read"),
               PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"))
    command = [sys.executable, "-X", "utf8", "-m", "dh_catalog", "health"]
    result = subprocess.run(command, env=env, capture_output=True, encoding="utf-8", check=False)
    assert result.returncode == 0, result.stderr
    assert "健康检查通过" in result.stdout
    assert connection.execute("SELECT count(*) AS n FROM import_run").fetchone()["n"] == 0
    connection.execute("UPDATE schema_migration SET name='synthetic-unapplied' WHERE name='0001_init.sql'")
    try:
        result = subprocess.run(command, env=env, capture_output=True, encoding="utf-8", check=False)
        assert result.returncode == 1 and "迁移未就绪" in result.stderr
    finally:
        connection.execute("UPDATE schema_migration SET name='0001_init.sql' WHERE name='synthetic-unapplied'")
