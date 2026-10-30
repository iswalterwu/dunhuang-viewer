"""HTTP 边界：共用 v0 登录、只读目录查询及管理员导入。"""

import base64
import binascii
import hashlib
import hmac
import json
import time
import logging
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from threading import Thread
from typing import Annotated, Literal
from uuid import UUID

import httpx
import psycopg
from psycopg import sql
from psycopg_pool import PoolTimeout
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response

from .config import Settings, load_settings
from .db import ImportBusy, create_pool
from .identifiers import parse_identifiers
from .identity import ImageState
from .importer import latest_valid_snapshot, prepare_import, value_at_run
from .rules import BATCH_CATEGORIES
from .scan import FileEntry
from .v0 import viewer_link

logger = logging.getLogger(__name__)
Page = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=200)]
Run = Annotated[int, Query(ge=1)]


@dataclass(frozen=True, slots=True)
class Principal:
    username: str
    admin: bool


def create_app(settings: Settings | None = None, *, http_client: httpx.Client | None = None) -> FastAPI:
    """uvicorn --factory 入口；http_client 只注入 v0 HTTP 边界。"""
    settings = load_settings() if settings is None else settings

    @asynccontextmanager
    async def lifespan(app):
        pool = create_pool(settings.database_url) if settings.database_url else None
        app.state.pool = pool
        try:
            if pool is not None:
                pool.open(wait=True)
            yield
        finally:
            # 导入持有连接和会话锁；先等真实线程结束，再关闭运行池。
            for thread in app.state.import_threads:
                thread.join()
            if pool is not None:
                pool.close()
            app.state.pool = None

    app = FastAPI(
        title="敦煌目录服务", docs_url="/api/v1/docs", openapi_url="/api/v1/openapi.json", redoc_url=None,
        swagger_ui_oauth2_redirect_url=None, lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.pool = None
    app.state.import_threads = []

    @app.middleware("http")
    async def login_wall(request: Request, call_next):
        try:
            request.state.principal = authenticate_cookie(
                request.cookies.get("dh_session", ""), app.state.settings,
            )
        except HTTPException as error:
            return JSONResponse({"detail": error.detail}, status_code=error.status_code)
        return await call_next(request)

    _read_routes(app)
    _import_route(app, http_client)
    return app


def _pool(request: Request):
    if request.app.state.pool is None:
        raise HTTPException(503, "未配置或尚未打开目录数据库")
    return request.app.state.pool


def _read_connection(request: Request):
    try:
        with _pool(request).connection() as connection, connection.transaction():
            connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            yield connection
    except (psycopg.Error, PoolTimeout) as error:
        logger.error("目录查询失败：%s", type(error).__name__)
        raise HTTPException(503, "目录数据库不可用") from None


ReadConnection = Annotated[psycopg.Connection, Depends(_read_connection)]

# 每条异常用结构化对象 / 路径关联，不解析说明原文，不把全局导入异常分给所有写卷。
# 先求关联 ID 集合，避免逐写卷重复遍历整批异常；IN 不会因多影像关联膨胀计数。
_ITEM_ANOMALY = """
    i.id::text IN (
        WITH recent AS MATERIALIZED (
            SELECT * FROM anomaly
            WHERE run_id = (SELECT max(id) FROM import_run WHERE status = 'succeeded')
        )
        SELECT object_key FROM recent WHERE object_kind = 'item'
        UNION
        SELECT ii.item_id::text FROM recent a
        JOIN item_image ii ON ii.unit_key = a.object_key
        WHERE a.object_kind = 'unit'
        UNION
        SELECT ii.item_id::text FROM recent a
        JOIN image im ON im.root = a.root AND im.relative_path = a.relative_path
        JOIN item_image ii ON ii.image_id = im.id
        WHERE a.object_kind IN ('unit', 'image', 'file')
        UNION
        SELECT ii.item_id::text FROM recent a
        JOIN item_image ii ON ii.unit_key = a.root || ':' || a.relative_path
        WHERE a.object_kind = 'file'
        UNION
        SELECT ii.item_id::text FROM recent a
        JOIN item_image ii ON ii.source_directory = regexp_replace(a.relative_path, '/[^/]+$', '')
        JOIN image im ON im.id = ii.image_id AND im.root = a.root
        WHERE a.object_kind = 'file' AND ii.unit_key <> im.root || ':' || im.relative_path
        UNION
        SELECT ia.item_id::text FROM recent a
        JOIN attachment at ON at.root = a.root AND at.relative_path = a.relative_path
        JOIN item_attachment ia ON ia.attachment_id = at.id
        WHERE a.object_kind = 'file'
    )
"""


def _read_routes(app):
    @app.get("/api/v1/items")
    def items(
        connection: ReadConnection, system: Literal["pelliot", "nlc", "sharer", "zhihao", "idp"] | None = None,
        lineage: str | None = None, provenance: Literal["已确认", "待核", "非敦煌"] | None = None,
        has_anomaly: bool | None = None, category: str | None = None, batch: str | None = None,
        page: Page = 1, page_size: PageSize = 50,
    ):
        where, params = _item_filters(system, lineage, provenance, has_anomaly, category, batch)
        return _page(connection, "item i", "i.*", where, params, "i.serial, i.id", page, page_size)

    @app.get("/api/v1/resolve")
    def resolve(connection: ReadConnection, q: Annotated[str, Query(min_length=1)]):
        # 编号解析仅在查询入口；无 key 的分享者号 / 帙号 / IDP 并不是存疑馆藏号。
        values = {q.strip().lower()}
        values.update(ident.normalized.lower() for ident in parse_identifiers(q).identifiers)
        rows = connection.execute("""
            SELECT i.* FROM item i WHERE EXISTS (
                SELECT 1 FROM identifier n WHERE n.item_id = i.id AND n.state = 'current'
                AND (lower(n.raw) = ANY(%s) OR lower(n.normalized) = ANY(%s)
                     OR lower(n.parent_number) = ANY(%s))
            ) ORDER BY i.serial, i.id
        """, (list(values), list(values), list(values))).fetchall()
        return {"items": rows, "total": len(rows)}

    @app.get("/api/v1/items/{id}")
    def item_detail(id: UUID, request: Request, connection: ReadConnection):
        item = _resource(connection, "item", id)
        item["identifiers"] = connection.execute(
            "SELECT * FROM identifier WHERE item_id = %s ORDER BY id", (id,)).fetchall()
        item["images"] = connection.execute("""
            SELECT im.*, to_jsonb(ii) AS relationship FROM item_image ii
            JOIN image im ON im.id = ii.image_id WHERE ii.item_id = %s ORDER BY im.root, im.relative_path, im.id
        """, (id,)).fetchall()
        _image_details(connection, item["images"], request.app.state.settings)
        item["attachments"] = connection.execute("""
            SELECT at.id, at.root, at.relative_path, at.kind, at.encoding, at.created_run, at.updated_run
            FROM item_attachment ia JOIN attachment at ON at.id = ia.attachment_id
            WHERE ia.item_id = %s ORDER BY at.root, at.relative_path, at.id
        """, (id,)).fetchall()
        item["provenance_history"] = connection.execute(
            "SELECT * FROM provenance_history WHERE item_id = %s ORDER BY run_id, id", (id,)).fetchall()
        item["parent"] = _resource(connection, "item", item["parent_id"]) if item["parent_id"] else None
        item["parts"] = connection.execute(
            "SELECT * FROM item WHERE parent_id = %s ORDER BY serial, id", (id,)).fetchall()
        return item

    @app.get("/api/v1/items/{id}/history")
    def item_history(id: UUID, run: Run, connection: ReadConnection):
        return _history_at(connection, "item", id, run)

    @app.get("/api/v1/images/{id}")
    def image_detail(id: UUID, request: Request, connection: ReadConnection):
        image = _resource(connection, "image", id)
        _image_details(connection, [image], request.app.state.settings)
        return image

    @app.get("/api/v1/images/{id}/history")
    def image_history(id: UUID, run: Run, connection: ReadConnection):
        return _history_at(connection, "image", id, run)

    @app.get("/api/v1/attachments/{id}")
    def attachment(id: UUID, connection: ReadConnection):
        row = _resource(connection, "attachment", id)
        return Response(content=bytes(row["raw"]), media_type="application/octet-stream")

    @app.get("/api/v1/anomalies")
    def anomalies(connection: ReadConnection, run: Run | None = None, category: str | None = None,
                  page: Page = 1, page_size: PageSize = 50):
        clauses, params = [], []
        if run is not None:
            _resource(connection, "import_run", run)
            clauses.append("run_id = %s")
            params.append(run)
        if category is not None:
            clauses.append("category = %s")
            params.append(category)
        return _page(connection, "anomaly", "*", " AND ".join(clauses) or "TRUE", params,
                     "run_id DESC, id", page, page_size)

    @app.get("/api/v1/imports")
    def imports(connection: ReadConnection, page: Page = 1, page_size: PageSize = 50):
        result = _page(connection, "import_run", "*", "TRUE", [], "id DESC", page, page_size)
        for row in result["items"]:
            row["report"] = row.pop("counts")
        return result

    @app.get("/api/v1/imports/{id}")
    def import_detail(id: int, connection: ReadConnection):
        row = _resource(connection, "import_run", id)
        row["report"] = row.pop("counts")
        return row


def _item_filters(system, lineage, provenance, has_anomaly, category, batch):
    clauses, params = [], []
    if system is not None:
        clauses.append("EXISTS (SELECT 1 FROM identifier n WHERE n.item_id = i.id AND n.state = 'current' AND n.system = %s)")
        params.append(system)
    if provenance is not None:
        clauses.append("i.provenance->>'status' = %s")
        params.append(provenance)
    if has_anomaly is not None:
        clauses.append(_ITEM_ANOMALY if has_anomaly else "NOT " + _ITEM_ANOMALY)
    # 分类和批次须由同一影像当前位置命中；缺失影像仍保留最后位置。
    image_clauses = []
    if lineage is not None:
        image_clauses.append("im.lineage = %s")
        params.append(lineage)
    if category is not None:
        image_clauses.append("split_part(im.relative_path, '/', 1) = %s")
        params.append(category)
    if batch is not None:
        image_clauses.append("split_part(im.relative_path, '/', 1) = ANY(%s) AND split_part(im.relative_path, '/', 2) = %s")
        params.extend([list(BATCH_CATEGORIES), batch])
    if image_clauses:
        clauses.append("EXISTS (SELECT 1 FROM item_image ii JOIN image im ON im.id = ii.image_id "
                       "WHERE ii.item_id = i.id AND " + " AND ".join(image_clauses) + ")")
    return " AND ".join(clauses) or "TRUE", params


def _page(connection, table, columns, where, params, order, page, page_size):
    # SQL 片段仅由本模块常量构成，所有外部值用绑定参数。
    total = connection.execute(f"SELECT count(*) AS n FROM {table} WHERE {where}", params).fetchone()["n"]
    rows = connection.execute(f"SELECT {columns} FROM {table} WHERE {where} ORDER BY {order} LIMIT %s OFFSET %s",
                              [*params, page_size, (page - 1) * page_size]).fetchall()
    return {"items": rows, "total": total, "page": page, "page_size": page_size}


def _resource(connection, table, id):
    row = connection.execute(sql.SQL("SELECT * FROM {} WHERE id = %s").format(sql.Identifier(table)), (id,)).fetchone()
    if row is None:
        raise HTTPException(404, "资源不存在")
    return row


def _history_at(connection, kind, id, run):
    _resource(connection, kind, id)
    _resource(connection, "import_run", run)
    row = value_at_run(connection, kind, id, run)
    if row is None:
        raise HTTPException(404, "该批次时尚无此对象记录")
    return dict(row, requested_run=run)


def _image_details(connection, images, settings):
    if not images:
        return
    by_id = {image["id"]: image for image in images}
    ids = list(by_id)
    for image in images:
        image.update(path_history=[], history=[], derivations=[], items=[])
    for row in connection.execute("SELECT * FROM image_path_history WHERE image_id = ANY(%s) ORDER BY since_run", (ids,)):
        by_id[row["image_id"]]["path_history"].append(row)
    for row in connection.execute("SELECT * FROM history WHERE object_kind = 'image' AND object_id = ANY(%s) ORDER BY run_id", (ids,)):
        by_id[row["object_id"]]["history"].append(row)
    for row in connection.execute("SELECT * FROM derivation WHERE image_id = ANY(%s) ORDER BY source_image_id", (ids,)):
        by_id[row["image_id"]]["derivations"].append(row)
    for row in connection.execute("SELECT * FROM item_image WHERE image_id = ANY(%s) ORDER BY item_id", (ids,)):
        by_id[row["image_id"]]["items"].append(row)
    snapshot = latest_valid_snapshot(connection)
    # 当前 HTTP 文件系统入口：每个相关目录只精确检查一次，不列目录或递归扫描。
    directories = {PurePosixPath(row["relative_path"]).parent for row in images
                   if row["root"] == "data" and row["kind"] == "tiff" and row["state"] == "present"}
    present = {path for path in directories if (settings.data_dir / path).is_dir()}
    for row in images:
        file = FileEntry(row["root"], PurePosixPath(row["relative_path"]), row["kind"], row["size"], row["mtime_ns"], row["inode"])
        state = ImageState(row["id"], file, row["first_seen"], row["last_seen"], row["missing_since"])
        loose = any(link["unit_key"] == f"{file.root}:{file.relative_path}" for link in row["items"])
        row["v0_link"] = asdict(viewer_link(state, snapshot, present, settings.v0_public_url, loose=loose))


def _import_route(app, http_client):
    @app.post("/api/v1/imports", status_code=202)
    def trigger_import(request: Request, principal: Annotated[Principal, Depends(require_admin)]):
        settings = request.app.state.settings
        try:
            prepared = prepare_import(
                _pool(request), triggered_by=principal.username, code_version=settings.code_version,
                session_cookie=request.cookies["dh_session"], v0_url=settings.v0_url, http_client=http_client,
            )
        except ImportBusy:
            raise HTTPException(409, "已有导入在跑") from None
        except (psycopg.Error, PoolTimeout) as error:
            logger.error("导入准备失败：%s", type(error).__name__)
            raise HTTPException(503, "目录数据库不可用") from None
        try:
            thread = Thread(target=_execute_import, args=(prepared, settings), name=f"catalog-import-{prepared.run_id}")
            thread.start()
        except Exception as error:
            prepared.cancel()
            logger.error("导入派发失败：run=%s type=%s", prepared.run_id, type(error).__name__)
            raise HTTPException(503, "导入未派发") from None
        app.state.import_threads.append(thread)
        return {"id": prepared.run_id}


def _execute_import(prepared, settings):
    try:
        prepared.execute(
            {"data": settings.data_dir, "backup": settings.backup_dir}, settings.v0_cache_dir,
            record_roots=settings.record_roots,
        )
    except BaseException as error:
        # 不打印 traceback / 消息：外部异常可能含 cookie、secret 或连接串。
        logger.error("导入失败：run=%s type=%s", prepared.run_id, type(error).__name__)


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
