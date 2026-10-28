"""仅生成合成材料；不读取 NAS，也不在 fixture 中复制业务规则。"""

import os
import struct
from pathlib import Path

import numpy as np
from psycopg.conninfo import conninfo_to_dict
import pytest
import tifffile
from PIL import Image


@pytest.fixture
def roots(tmp_path):
    paths = {name: tmp_path / name for name in ("data", "backup")}
    for path in paths.values():
        path.mkdir()
    return paths


@pytest.fixture
def make_image():
    def make(path: Path, *, software: str = "", dpi=None, mode: str = "RGB") -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        suffix = path.suffix.lower()
        if suffix in {".tif", ".tiff", ".btf"}:
            tifffile.imwrite(
                path, np.zeros((5, 7, 3), dtype=np.uint8),
                photometric="rgb", software=software, metadata=None,
                resolution=dpi, resolutionunit="INCH" if dpi else None,
            )
        elif suffix == ".psb":
            path.write_bytes(struct.pack(">4sH6sHIIHH", b"8BPS", 2, b"\0" * 6, 4, 5, 7, 16, 4))
        elif suffix in {".jpg", ".jpeg"}:
            kwargs = {"dpi": dpi} if dpi else {}
            Image.new(mode, (7, 5)).save(path, **kwargs)
        else:
            raise ValueError(f"测试夹具不支持此文件类型：{suffix}")
        return path
    return make


@pytest.fixture(scope="session")
def test_database_url():
    """仅在显式指定的一次性测试库上执行数据库测试；不借用正式配置。"""
    url = os.environ.get("DH_TEST_DATABASE_URL")
    if not url:
        pytest.skip("未配置 DH_TEST_DATABASE_URL；真实 PostgreSQL 测试尚未执行")
    database = conninfo_to_dict(url).get("dbname", "")
    if not database.startswith("dh_catalog_test_"):
        raise pytest.UsageError("测试库名必须以 dh_catalog_test_ 开头，拒绝改动其他数据库")
    return url
