"""v0 HTTP 边界与只读链接计算；不签发会话，不扫描 v0 cache。"""

from __future__ import annotations

import base64
import binascii
import re
import threading
import time
from collections.abc import Collection
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import TYPE_CHECKING
from urllib.parse import urlencode

import httpx

if TYPE_CHECKING:
    from .identity import ImageState

VOLUME_ID = re.compile(r"[A-Za-z0-9_-]+")


@dataclass(frozen=True, slots=True)
class V0Volume:
    id: str
    directory: PurePosixPath


@dataclass(frozen=True, slots=True)
class IndexSnapshot:
    fetched_at: datetime
    volumes: dict[PurePosixPath, V0Volume]


@dataclass(frozen=True, slots=True)
class IndexFetch:
    snapshot: IndexSnapshot | None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class HealthSample:
    at: datetime
    seconds: float
    ok: bool
    error: str | None = None


@dataclass(frozen=True, slots=True)
class HealthSummary:
    count: int
    failures: int
    max_seconds: float


@dataclass(frozen=True, slots=True)
class V0Link:
    url: str | None
    reason: str | None = None


class V0Client:
    """一次导入的外部连接；借用触发者原 cookie，仅在这个实例的内存中持有。"""

    def __init__(self, base_url: str, session_cookie: str, client: httpx.Client | None = None):
        self._base_url = base_url
        self._session_cookie = session_cookie
        self._owns_client = client is None
        self._client = httpx.Client(timeout=2.0, trust_env=False) if client is None else client

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self) -> None:
        self._session_cookie = ""
        if self._owns_client:
            self._client.close()

    def fetch_index(self) -> IndexFetch:
        try:
            response = self._get("/api/index")
            if response.status_code != 200:
                return IndexFetch(None, f"v0 索引 HTTP {response.status_code}")
            snapshot = _parse_index(response.json())
        except httpx.RequestError as error:
            return IndexFetch(None, f"v0 索引请求失败：{type(error).__name__}")
        except ValueError as error:
            return IndexFetch(None, f"v0 索引不可用：{error}")
        return IndexFetch(snapshot)

    def sample_health(self) -> HealthSample:
        started = time.perf_counter()
        at = datetime.now(UTC)
        error = None
        try:
            response = self._get("/api/health")
            if response.status_code != 200:
                error = f"HTTP {response.status_code}"
            else:
                data = response.json()
                if not isinstance(data, dict) or data.get("ok") is not True:
                    error = "v0 健康响应不正常"
        except httpx.RequestError as exc:
            error = f"v0 健康请求失败：{type(exc).__name__}"
        except ValueError:
            error = "v0 健康响应格式无效"
        seconds = time.perf_counter() - started
        if seconds > 2.0:
            error = error or "v0 健康响应超过 2 秒"
        return HealthSample(at, seconds, error is None, error)

    def _get(self, path: str) -> httpx.Response:
        return self._client.get(
            self._base_url + path, headers={"Cookie": f"dh_session={self._session_cookie}"}, timeout=2.0,
            follow_redirects=False,
        )


class HealthMonitor:
    """导入期间每 5 秒采样，退出时等待正在进行的请求结束，再读取汇总。"""

    def __init__(self, client: V0Client, interval: float = 5.0):
        self._client = client
        self._interval = interval
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self.samples: list[HealthSample] = []

    def __enter__(self):
        self.samples.append(self._client.sample_health())
        self._thread.start()
        return self

    def __exit__(self, *_):
        self._stop.set()
        self._thread.join()

    def summary(self) -> HealthSummary:
        return HealthSummary(
            len(self.samples), sum(not sample.ok for sample in self.samples),
            max((sample.seconds for sample in self.samples), default=0.0),
        )

    def _run(self) -> None:
        tick = time.monotonic() + self._interval
        while not self._stop.wait(max(0.0, tick - time.monotonic())):
            self.samples.append(self._client.sample_health())
            tick += self._interval


def _parse_index(data) -> IndexSnapshot:
    if not isinstance(data, dict) or data.get("status") != "ready":
        raise ValueError("v0 索引尚未就绪")
    entries = data.get("items")
    if not isinstance(entries, list):
        raise ValueError("v0 索引缺少卷列表")
    volumes = {}
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
            raise ValueError("v0 卷条目缺少 ID")
        volume_id = entry["id"]
        if not VOLUME_ID.fullmatch(volume_id):
            raise ValueError("v0 卷 ID 不是 base64url")
        try:
            relative = base64.b64decode(volume_id + "=" * (-len(volume_id) % 4), altchars=b"-_", validate=True).decode("utf-8")
        except (binascii.Error, UnicodeError) as error:
            raise ValueError("v0 卷 ID 无法解码") from error
        directory = PurePosixPath(relative)
        if not directory.parts or directory.is_absolute() or ".." in directory.parts:
            raise ValueError("v0 卷不是有效的相对目录")
        volumes[directory] = V0Volume(volume_id, directory)
    return IndexSnapshot(datetime.now(UTC), volumes)


def viewer_link(
    image: ImageState, snapshot: IndexSnapshot | None, present_directories: Collection[PurePosixPath],
    public_url: str, *, loose: bool = False,
) -> V0Link:
    """使用最近有效快照与本次扫描目录集合；不在内部重复读磁盘。"""
    file = image.file
    if file.root == "backup":
        return V0Link(None, "备份分片不在 v0 中展示")
    if file.kind != "tiff":
        return V0Link(None, "v0 不展示 JPG 或 PSB")
    if image.missing_since is not None:
        return V0Link(None, "影像缺失")
    if snapshot is None:
        return V0Link(None, "从未取得有效 v0 索引")
    directory = file.relative_path.parent
    if directory not in present_directories:
        return V0Link(None, "影像目录已不存在")
    volume = snapshot.volumes.get(directory)
    if volume is None:
        return V0Link(None, "影像目录不在 v0 索引中")
    url = f"{public_url}/view/{volume.id}"
    if loose:
        url += "?" + urlencode({"file": file.relative_path.name})
    return V0Link(url)
