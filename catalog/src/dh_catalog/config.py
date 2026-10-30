"""运行配置入口；不在导入模块时读取环境或文件。"""

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import dotenv_values


@dataclass(frozen=True, slots=True)
class Settings:
    data_dir: Path
    backup_dir: Path
    v0_cache_dir: Path
    v0_env_file: Path
    v0_url: str
    v0_public_url: str
    database_url: str | None = field(repr=False)
    auth_secret: str | None = field(repr=False)
    code_version: str = "development"
    record_roots: Mapping[str, str] = field(default_factory=dict)


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    """只在启动入口调用；缺 secret 保持 None，由 HTTP 入口拒绝全部请求。"""
    values = os.environ if env is None else env
    # 仅供本机开发的后备值；生产 Compose 要求显式 DH_V0_URL。
    v0_url = _http_url(values.get("DH_V0_URL", "http://localhost:8503"))
    public_url = _http_url(values.get("DH_V0_PUBLIC_URL", "").strip() or v0_url)
    env_file = Path(values.get("DH_V0_ENV_FILE", "/run/v0.env"))
    return Settings(
        data_dir=Path(values.get("DH_DATA_DIR", "/data")),
        backup_dir=Path(values.get("DH_BACKUP_DIR", "/backup")),
        v0_cache_dir=Path(values.get("DH_V0_CACHE_DIR", "/v0cache")),
        v0_env_file=env_file,
        v0_url=v0_url,
        v0_public_url=public_url,
        database_url=values.get("DH_DATABASE_URL") or None,
        auth_secret=_read_auth_secret(env_file),
        code_version=values.get("DH_CODE_VERSION") or "development",
        record_roots=_record_roots(values),
    )


def _record_roots(values: Mapping[str, str]) -> dict[str, str]:
    """旧记录的宿主前缀，与容器扫描根无关；保持 POSIX 字符串。"""
    roots = {}
    for role, name in (("data", "DH_RECORD_DATA_ROOT"), ("backup", "DH_RECORD_BACKUP_ROOT")):
        value = values.get(name, "").strip()
        if not value:
            continue
        if not value.startswith("/") or not value.strip("/") or "\\" in value:
            raise ValueError(f"{name} 须为绝对 POSIX 路径且不能仅为根目录")
        roots[role] = value.rstrip("/") + "/"
    return roots


def _http_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("v0 地址须为完整的 HTTP(S) URL")
    return value.rstrip("/")


def _read_auth_secret(path: Path) -> str | None:
    try:
        values = dotenv_values(path, encoding="utf-8-sig", interpolate=False)
    except (OSError, UnicodeError):
        return None
    return values.get("AUTH_SECRET") or None
