"""PostgreSQL 连接、按序迁移与单批导入锁；不引入 ORM 或迁移框架。"""

from contextlib import contextmanager
from pathlib import Path

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations"
IMPORT_LOCK_KEY = 2026102801


class ImportBusy(Exception):
    """已有导入持有数据库会话锁；HTTP 入口将其转为 409。"""


def create_pool(database_url: str) -> ConnectionPool:
    """显式打开才连接；运行中导入占一个连接，其余供只读查询。"""
    return ConnectionPool(
        database_url, min_size=1, max_size=4, open=False,
        kwargs={"autocommit": True, "row_factory": dict_row},
    )


def migrate(connection: Connection, directory: Path = MIGRATIONS) -> tuple[str, ...]:
    """迁移与版本登记同事务；重复运行跳过已登记文件。"""
    applied = []
    with connection.transaction():
        connection.execute("""
            CREATE TABLE IF NOT EXISTS schema_migration (
                name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now()
            )
        """)
        done = {row["name"] for row in connection.execute("SELECT name FROM schema_migration")}
        for path in sorted(directory.glob("*.sql")):
            if path.name not in done:
                connection.execute(path.read_text(encoding="utf-8"))
                connection.execute("INSERT INTO schema_migration(name) VALUES (%s)", (path.name,))
                applied.append(path.name)
    return tuple(applied)


@contextmanager
def import_lock(connection: Connection):
    """会话锁跨越快照提交和目录事务，回滚不提前释放，不另建进程锁。"""
    row = connection.execute("SELECT pg_try_advisory_lock(%s) AS locked", (IMPORT_LOCK_KEY,)).fetchone()
    if not row["locked"]:
        raise ImportBusy("已有导入在跑")
    try:
        yield
    finally:
        connection.execute("SELECT pg_advisory_unlock(%s)", (IMPORT_LOCK_KEY,))
