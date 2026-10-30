import base64
import threading
import time
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from dh_catalog.identity import resolve_images
from dh_catalog.scan import scan
from dh_catalog.v0 import HealthMonitor, V0Client, viewer_link


def _volume_id(relative):
    return base64.urlsafe_b64encode(relative.encode()).decode().rstrip("=")


def test_index_protocol_uses_original_cookie_and_validates_at_boundary():
    seen = []
    directory = "敦煌003/P.2002 著录"

    def respond(request):
        seen.append(request)
        return httpx.Response(200, json={"status": "ready", "items": [{"id": _volume_id(directory)}]})

    with httpx.Client(transport=httpx.MockTransport(respond)) as backend:
        service = V0Client("http://v0.test:8503", "original-cookie", backend)
        with service:
            fetch = service.fetch_index()
        assert service._session_cookie == ""
        assert "Cookie" not in backend.headers
    assert fetch.error is None
    assert [str(path) for path in fetch.snapshot.volumes] == [directory]
    volume = next(iter(fetch.snapshot.volumes.values()))
    assert volume.id == _volume_id(directory)
    assert seen[0].method == "GET" and seen[0].url.path == "/api/index"
    assert seen[0].headers["Cookie"] == "dh_session=original-cookie"
    assert seen[0].extensions["timeout"]["read"] == 2.0


@pytest.mark.parametrize("body", [
    {"status": "scanning", "items": []},
    {"status": "ready", "items": 0},
    {"status": "ready", "items": [{}]},
    {"status": "ready", "items": [{"id": "not valid base64"}]},
    {"status": "ready", "items": [{"id": _volume_id("../outside")}]},
])
def test_unready_or_invalid_index_not_a_valid_snapshot(body):
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body))) as backend:
        result = V0Client("http://v0.test", "cookie", backend).fetch_index()
    assert result.snapshot is None and result.error
    if body.get("status") == "scanning":
        assert "尚未就绪" in result.error


@pytest.mark.parametrize("case", ["http", "timeout", "not_json"])
def test_index_failure_returns_reportable_reason_not_exception(case):
    def respond(request):
        if case == "timeout":
            raise httpx.ReadTimeout("simulated network boundary failure", request=request)
        if case == "not_json":
            return httpx.Response(200, text="not json")
        return httpx.Response(503)

    with httpx.Client(transport=httpx.MockTransport(respond)) as backend:
        result = V0Client("http://v0.test", "cookie", backend).fetch_index()
    assert result.snapshot is None and result.error
    assert "cookie" not in result.error


def test_valid_empty_index_is_distinct_from_no_valid_index(roots, make_image):
    make_image(roots["data"] / "敦煌003/P2002/1.tif")
    inventory = scan(roots)
    image = resolve_images([], inventory.images, 1).images[0]
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"status": "ready", "items": []}))) as backend:
        fetch = V0Client("http://v0.test", "cookie", backend).fetch_index()
    assert fetch.snapshot is not None and fetch.snapshot.volumes == {} and fetch.error is None
    link = viewer_link(image, fetch.snapshot, inventory.directories["data"], "http://viewer.test")
    assert link.url is None and "不在 v0 索引" in link.reason
    missing_snapshot = viewer_link(image, None, inventory.directories["data"], "http://viewer.test")
    assert "从未取得" in missing_snapshot.reason


@pytest.mark.parametrize("case", ["ok", "bad_flag", "string_flag", "http", "timeout", "not_json"])
def test_health_protocol_and_failures(case):
    def respond(request):
        assert request.url.path == "/api/health"
        assert request.headers["Cookie"] == "dh_session=original-cookie"
        if case == "timeout":
            raise httpx.ReadTimeout("simulated timeout", request=request)
        if case == "not_json":
            return httpx.Response(200, text="not json")
        if case == "http":
            return httpx.Response(401)
        return httpx.Response(200, json={"ok": True if case == "ok" else "true" if case == "string_flag" else False})

    with httpx.Client(transport=httpx.MockTransport(respond)) as backend:
        sample = V0Client("http://v0.test", "original-cookie", backend).sample_health()
    assert sample.ok is (case == "ok")
    assert (sample.error is None) is sample.ok
    assert sample.seconds >= 0


def test_health_late_success_still_fails_two_second_requirement():
    def respond(request):
        time.sleep(2.05)
        return httpx.Response(200, json={"ok": True})

    with httpx.Client(transport=httpx.MockTransport(respond)) as backend:
        sample = V0Client("http://v0.test", "cookie", backend).sample_health()
    assert sample.seconds > 2 and not sample.ok and "超过 2 秒" in sample.error


def test_health_monitor_stops_and_summarizes_without_polling_sleeps():
    sampled_twice = threading.Event()
    calls = []

    def respond(request):
        calls.append(request.url.path)
        if len(calls) >= 2:
            sampled_twice.set()
        return httpx.Response(200, json={"ok": len(calls) == 1})

    with httpx.Client(transport=httpx.MockTransport(respond)) as backend:
        with V0Client("http://v0.test", "cookie", backend) as service:
            with HealthMonitor(service, interval=0.01) as monitor:
                assert sampled_twice.wait(2), "后台采样没有运行"
            summary = monitor.summary()
            assert not monitor._thread.is_alive()
    assert summary.count == len(calls) >= 2
    assert summary.failures == len(calls) - 1 and summary.max_seconds >= 0


def test_viewer_links_use_snapshot_and_current_scan(roots, make_image):
    paths = [
        "敦煌003/P2002/1.tif", "敦煌003/未收录/2.tif", "敦煌003/P2002/source.psb",
        "中国国博馆藏/BD00001/pages/0001_7x5.jpg", "188敦煌001/2018年/散放 P4508.tif",
    ]
    for path in paths:
        make_image(roots["data"] / path)
    make_image(roots["backup"] / "敦煌003/P2002/old.tif")
    inventory = scan(roots)
    images = resolve_images([], inventory.images, 1)
    body = {"status": "ready", "items": [
        {"id": _volume_id("敦煌003/P2002")}, {"id": _volume_id("188敦煌001/2018年")},
        {"id": _volume_id("敦煌003/已不存在")},
    ]}
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body))) as backend:
        snapshot = V0Client("http://v0.test", "cookie", backend).fetch_index().snapshot
    by_path = {(image.file.root, str(image.file.relative_path)): image for image in images.images}
    good = viewer_link(by_path["data", paths[0]], snapshot, inventory.directories["data"], "http://viewer.test")
    assert good.url == "http://viewer.test/view/" + _volume_id("敦煌003/P2002")
    assert good.reason is None
    for path in paths[1:4]:
        link = viewer_link(by_path["data", path], snapshot, inventory.directories["data"], "http://viewer.test")
        assert link.url is None and link.reason
    backup = viewer_link(by_path["backup", "敦煌003/P2002/old.tif"], snapshot, inventory.directories["data"], "http://viewer.test")
    assert backup.url is None and "备份" in backup.reason
    loose = viewer_link(by_path["data", paths[4]], snapshot, inventory.directories["data"], "http://viewer.test", loose=True)
    assert urlsplit(loose.url).path == "/view/" + _volume_id("188敦煌001/2018年")
    assert parse_qs(urlsplit(loose.url).query) == {"file": ["散放 P4508.tif"]}
    (roots["data"] / paths[0]).unlink()
    reimported = resolve_images(images.images, scan(roots).images, 2)
    missing = next(image for image in reimported.images if image.id == by_path["data", paths[0]].id)
    assert viewer_link(missing, snapshot, inventory.directories["data"], "http://viewer.test").reason == "影像缺失"
