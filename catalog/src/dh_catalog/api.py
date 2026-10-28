"""HTTP 入口：共用 v0 登录；目录查询与导入路由在后续任务加入。"""

import base64
import binascii
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from .config import Settings, load_settings


@dataclass(frozen=True, slots=True)
class Principal:
    username: str
    admin: bool


def create_app(settings: Settings | None = None) -> FastAPI:
    """供 uvicorn --factory 调用；导入模块本身不读文件、不连接数据库。"""
    app = FastAPI(
        title="敦煌目录服务", docs_url="/api/v1/docs", openapi_url="/api/v1/openapi.json", redoc_url=None,
        swagger_ui_oauth2_redirect_url=None,
    )
    app.state.settings = load_settings() if settings is None else settings

    @app.middleware("http")
    async def login_wall(request: Request, call_next):
        try:
            request.state.principal = authenticate_cookie(
                request.cookies.get("dh_session", ""), app.state.settings,
            )
        except HTTPException as error:
            return JSONResponse({"detail": error.detail}, status_code=error.status_code)
        return await call_next(request)

    return app


def current_user(request: Request) -> Principal:
    # login_wall 已在唯一的 HTTP 边界验证；路由不再解析 cookie 或重读用户表。
    return request.state.principal


def require_admin(user: Annotated[Principal, Depends(current_user)]) -> Principal:
    if not user.admin:
        raise HTTPException(403, "只有管理员能触发导入")
    return user


def authenticate_cookie(token: str, settings: Settings, now: float | None = None) -> Principal:
    if not settings.auth_secret:
        raise HTTPException(503, "v0 AUTH_SECRET 不可用，目录服务拒绝请求")
    username = _signed_user(token, settings.auth_secret, time.time() if now is None else now)
    admin = _user_admin(settings.v0_cache_dir / "users.json", username)
    return Principal(username, admin)


def _signed_user(token: str, secret: str, now: float) -> str:
    try:
        raw = base64.b64decode(token + "=" * (-len(token) % 4), altchars=b"-_", validate=True).decode("utf-8")
        username, expiry, signature = raw.rsplit("|", 2)
        expires = int(expiry)
        expected = hmac.new(secret.encode("utf-8"), f"{username}|{expires}".encode("utf-8"), hashlib.sha256).hexdigest()
        valid = hmac.compare_digest(signature.encode("ascii"), expected.encode("ascii"))
    except (binascii.Error, UnicodeError, ValueError):
        raise HTTPException(401, "未登录或登录状态无效") from None
    if expires < now or not valid:
        raise HTTPException(401, "未登录或登录状态无效")
    return username


def _user_admin(path: Path, username: str) -> bool:
    try:
        users = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        raise HTTPException(503, "v0 用户表不可用") from None
    if not isinstance(users, dict):
        raise HTTPException(503, "v0 用户表格式无效")
    if username not in users:
        raise HTTPException(401, "未登录或登录状态无效")
    record = users[username]
    if not isinstance(record, dict) or not isinstance(record.get("admin", False), bool):
        raise HTTPException(503, "v0 用户记录格式无效")
    return record.get("admin", False)
