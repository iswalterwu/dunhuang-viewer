"""只对真实 PostgreSQL 测试库运行，不用 SQLite / mock 模拟数据库行为。"""

import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import errors
from psycopg.rows import dict_row

from dh_catalog.db import ImportBusy, create_pool, import_lock, migrate

pytestmark = pytest.mark.db


def _run(conn):
    return conn.execute("""
        INSERT INTO import_run(status, triggered_by, rule_version, code_version)
        VALUES ('running', 'test-admin', 'test-rules', 'test-code') RETURNING id
    """).fetchone()["id"]


def _item(conn, run, key=None):
    item_id = uuid4()
    serial = conn.execute("SELECT coalesce(max(serial), 0) + 1 AS serial FROM item").fetchone()["serial"]
    conn.execute("""
        INSERT INTO item(id, serial, grouping_key, original_positions, display_policy, provenance,
                         clues, field_basis, created_run, updated_run)
        VALUES (%s, %s, %s, '[]', '仅供研究使用', '{}', '[]', '{}', %s, %s)
    """, (item_id, serial, key, run, run))
    return item_id


def _image(conn, run, path="敦煌003/P2002/1.tif", state="present"):
    image_id = uuid4()
    conn.execute("""
        INSERT INTO image(id, root, relative_path, original_name, original_path, hidden, kind,
                          size, mtime_ns, inode, read_ok, facts, lineage, collection, acquisition,
                          license, attribution, display_policy, external_policy, state,
                          first_seen, last_seen, field_basis)
        VALUES (%s, 'data', %s, '1.tif', %s, false, 'tiff', 100, 1, 1, false, '{}', '未判定',
                '未知', '未知', '未知', '无', '仅供研究使用', '不对外', %s, %s, %s, '{}')
    """, (image_id, path, path, state, run, run))
    return image_id


def test_migration_repeatable(connection):
    assert migrate(connection) == ()
    assert migrate(connection) == ()
    assert connection.execute("SELECT count(*) AS n FROM schema_migration").fetchone()["n"] == 1
    tables = {row["tablename"] for row in connection.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")}
    assert {
        "import_run", "item", "identifier", "image", "image_path_history", "item_image", "attachment",
        "item_attachment", "derivation", "provenance_history", "history", "anomaly", "excluded", "v0_volume",
    } <= tables


def test_failed_migration_and_registration_rolled_back(connection, tmp_path):
    (tmp_path / "0002_failure.sql").write_text("CREATE TABLE migration_rollback(x integer); SELECT 1/0;", encoding="utf-8")
    with pytest.raises(errors.DivisionByZero):
        migrate(connection, tmp_path)
    assert connection.execute("SELECT to_regclass('migration_rollback') AS name").fetchone()["name"] is None
    assert connection.execute("SELECT count(*) AS n FROM schema_migration WHERE name = '0002_failure.sql'").fetchone()["n"] == 0


def test_item_unique_key_and_unkeyed_items(connection):
    run = _run(connection)
    _item(connection, run, "pelliot:2002")
    _item(connection, run)
    _item(connection, run)
    with pytest.raises(errors.UniqueViolation):
        _item(connection, run, "pelliot:2002")
    assert connection.execute("SELECT count(*) AS n FROM item").fetchone()["n"] == 3


def test_number_swap_using_temporary_keys(connection):
    run = _run(connection)
    a = _item(connection, run, "pelliot:2002")
    b = _item(connection, run, "pelliot:2003")
    with pytest.raises(errors.UniqueViolation), connection.transaction():
        connection.execute("UPDATE item SET grouping_key = 'pelliot:2003' WHERE id = %s", (a,))
    with connection.transaction():
        connection.execute("UPDATE item SET grouping_key = 'temporary:' || id::text WHERE id = ANY(%s)", ([a, b],))
        connection.execute("UPDATE item SET grouping_key = 'pelliot:2003' WHERE id = %s", (a,))
        connection.execute("UPDATE item SET grouping_key = 'pelliot:2002' WHERE id = %s", (b,))
    assert {row["id"]: row["grouping_key"] for row in connection.execute("SELECT id, grouping_key FROM item")} == {
        a: "pelliot:2003", b: "pelliot:2002",
    }


@pytest.mark.parametrize("system,compliant", [("sharer", False), ("sharer", True), ("pelliot", False)])
def test_primary_requires_compliant_collection_number(connection, system, compliant):
    run = _run(connection)
    item = _item(connection, run)
    with pytest.raises(errors.CheckViolation):
        connection.execute("""
            INSERT INTO identifier(item_id, system, raw, normalized, source, source_path,
                                   is_primary, compliant, state, since_run, field_basis)
            VALUES (%s, %s, 'test', 'test', '目录名', 'synthetic', true, %s, 'current', %s, '{}')
        """, (item, system, compliant, run))


def test_one_current_primary_but_history_kept(connection):
    run = _run(connection)
    item = _item(connection, run, "pelliot:2002")
    sql = """
        INSERT INTO identifier(item_id, system, raw, normalized, source, source_path,
                               is_primary, compliant, state, since_run, field_basis)
        VALUES (%s, 'pelliot', %s, %s, '目录名', 'synthetic', true, true, %s, %s, '{}')
    """
    connection.execute(sql, (item, "P2002", "P.2002", "current", run))
    connection.execute(sql, (item, "P2001", "P.2001", "historical", run))
    with pytest.raises(errors.UniqueViolation):
        connection.execute(sql, (item, "P2003", "P.2003", "current", run))
    assert connection.execute("SELECT count(*) AS n FROM identifier").fetchone()["n"] == 2


def test_missing_position_can_have_new_present_image(connection):
    run = _run(connection)
    _image(connection, run, state="missing")
    _image(connection, run)
    with pytest.raises(errors.UniqueViolation):
        _image(connection, run)
    assert connection.execute("SELECT count(*) AS n FROM image").fetchone()["n"] == 2


def test_multi_item_image_relation(connection):
    run = _run(connection)
    a, b = _item(connection, run), _item(connection, run)
    image = _image(connection, run)
    for item in (a, b):
        connection.execute("""
            INSERT INTO item_image(item_id, image_id, role, source_directory, unit_key, field_basis)
            VALUES (%s, %s, '分段', 'synthetic', 'data:synthetic', '{}')
        """, (item, image))
    assert connection.execute("SELECT count(*) AS n FROM item_image WHERE image_id = %s", (image,)).fetchone()["n"] == 2


def test_run_and_snapshot_survive_formal_transaction_rollback(connection):
    run = _run(connection)
    connection.execute("UPDATE import_run SET v0_snapshot_status = 'valid' WHERE id = %s", (run,))
    connection.execute("INSERT INTO v0_volume VALUES (%s, 'encoded', 'synthetic')", (run,))
    with pytest.raises(RuntimeError), connection.transaction():
        _item(connection, run, "pelliot:2002")
        raise RuntimeError("synthetic import failure")
    connection.execute("UPDATE import_run SET status = 'failed' WHERE id = %s", (run,))
    assert connection.execute("SELECT count(*) AS n FROM item").fetchone()["n"] == 0
    assert connection.execute("SELECT status FROM import_run WHERE id = %s", (run,)).fetchone()["status"] == "failed"
    assert connection.execute("SELECT count(*) AS n FROM v0_volume WHERE run_id = %s", (run,)).fetchone()["n"] == 1


def test_import_lock_blocks_other_connection_and_survives_rollback(connection, test_database_url):
    with psycopg.connect(test_database_url, autocommit=True, row_factory=dict_row) as other:
        with import_lock(connection):
            with pytest.raises(ImportBusy), import_lock(other):
                pass
            with pytest.raises(RuntimeError), connection.transaction():
                raise RuntimeError("rollback must not release session lock")
            with pytest.raises(ImportBusy), import_lock(other):
                pass
        with import_lock(other):
            pass


def test_import_lock_released_after_exception(connection, test_database_url):
    with pytest.raises(RuntimeError), import_lock(connection):
        raise RuntimeError("synthetic failure")
    with psycopg.connect(test_database_url, autocommit=True, row_factory=dict_row) as other:
        with import_lock(other):
            pass


def test_pool_is_explicitly_opened_and_closed(connection, test_database_url):
    pool = create_pool(test_database_url)
    assert pool.closed
    with pool:
        pool.wait(10)
        with pool.connection() as conn:
            assert conn.autocommit
            assert conn.execute("SELECT 1 AS value").fetchone()["value"] == 1
    assert pool.closed


def test_migrate_cli(connection, test_database_url):
    env = dict(os.environ, DH_DATABASE_URL=test_database_url, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"))
    result = subprocess.run(
        [sys.executable, "-X", "utf8", "-m", "dh_catalog", "migrate"], env=env,
        capture_output=True, encoding="utf-8", check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "已是最新版本" in result.stdout
