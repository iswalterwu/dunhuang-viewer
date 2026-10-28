import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import replace

import pytest
from fastapi import Depends, HTTPException
from fastapi.testclient import TestClient

from dh_catalog.api import Principal, authenticate_cookie, create_app, require_admin
from dh_catalog.config import load_settings


def _cookie(user, secret, expiry):
    """按 v0 app.py 的线协议生成外部输入，不调用或复制被测的会话校验器。"""
    message = f"{user}|{expiry}"
    signature = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{message}|{signature}".encode()).decode().rstrip("=")


@pytest.fixture
def auth_files(tmp_path):
    secret = secrets.token_urlsafe(32)
    config = tmp_path / "v0.env"
    config.write_text(f"AUTH_SECRET = '{secret}'\n", encoding="utf-8")
    cache = tmp_path / "cache"
    cache.mkdir()
    users = cache / "users.json"
    users.write_text(json.dumps({"owner": {"admin": True}, "reader": {"admin": False}}), encoding="utf-8")
    settings = load_settings({"DH_V0_ENV_FILE": str(config), "DH_V0_CACHE_DIR": str(cache)})
    return settings, users, secret


@pytest.mark.parametrize("username,admin", [("owner", True), ("reader", False)])
def test_valid_v0_cookie_and_admin_flag(auth_files, username, admin):
    settings, users, secret = auth_files
    before = users.read_bytes(), users.stat().st_mtime_ns
    token = _cookie(username, secret, 2_000_000_000)
    assert authenticate_cookie(token, settings, 1_999_999_999) == Principal(username, admin)
    assert (users.read_bytes(), users.stat().st_mtime_ns) == before


@pytest.mark.parametrize("case", ["empty", "malformed", "expired", "bad_signature", "non_ascii_signature", "deleted_user"])
def test_invalid_cookie_rejected_at_boundary(auth_files, case):
    settings, users, secret = auth_files
    token = _cookie("owner", secret, 2_000_000_000)
    if case == "empty":
        token = ""
    elif case == "malformed":
        token = "%%%not base64"
    elif case == "expired":
        token = _cookie("owner", secret, 1_999_999_000)
    elif case == "bad_signature":
        token = _cookie("owner", "different signing key", 2_000_000_000)
    elif case == "non_ascii_signature":
        token = base64.urlsafe_b64encode("owner|2000000000|非签名".encode()).decode().rstrip("=")
    else:
        users.write_text("{}", encoding="utf-8")
    with pytest.raises(HTTPException) as error:
        authenticate_cookie(token, settings, 1_999_999_999)
    assert error.value.status_code == 401


@pytest.mark.parametrize("content", ["not json", "[]", '{"owner": []}', '{"owner": {"admin": "true"}}'])
def test_unavailable_user_table_rejects_instead_of_falling_back(auth_files, content):
    settings, users, secret = auth_files
    users.write_text(content, encoding="utf-8")
    with pytest.raises(HTTPException) as error:
        authenticate_cookie(_cookie("owner", secret, 2_000_000_000), settings, 1_999_999_999)
    assert error.value.status_code == 503


def test_missing_secret_rejects_all_http_requests(auth_files):
    settings, _, _ = auth_files
    with TestClient(create_app(replace(settings, auth_secret=None))) as client:
        for path in ("/api/v1/docs", "/api/v1/openapi.json", "/not-a-route"):
            assert client.get(path).status_code == 503


def test_login_wall_docs_admin_and_user_deletion(auth_files):
    settings, users, secret = auth_files
    app = create_app(settings)

    @app.post("/test-admin", dependencies=[Depends(require_admin)])
    def admin_probe():
        return {"ok": True}

    with TestClient(app) as client:
        assert client.get("/api/v1/docs").status_code == 401
        assert client.get("/api/v1/openapi.json").status_code == 401
        client.cookies.set("dh_session", _cookie("reader", secret, int(time.time()) + 3600))
        assert client.get("/api/v1/openapi.json").status_code == 200
        assert client.post("/test-admin").status_code == 403
        client.cookies.set("dh_session", _cookie("owner", secret, int(time.time()) + 3600))
        assert client.post("/test-admin").json() == {"ok": True}
        assert client.get("/api/v1/docs").status_code == 200
        users.write_text('{"reader": {"admin": false}}', encoding="utf-8")
        assert client.get("/api/v1/docs").status_code == 401
