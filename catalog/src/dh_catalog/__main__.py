"""仅提供已实现的运维命令；没有命令行导入入口。"""

import argparse

import psycopg
from psycopg.rows import dict_row

from .config import load_settings
from .db import migrate


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m dh_catalog")
    parser.add_argument("command", choices=["migrate"])
    parser.parse_args()
    settings = load_settings()
    if settings.database_url is None:
        parser.error("需要配置 DH_DATABASE_URL")
    with psycopg.connect(settings.database_url, autocommit=True, row_factory=dict_row) as connection:
        applied = migrate(connection)
    print("迁移完成：" + (", ".join(applied) if applied else "已是最新版本"))


if __name__ == "__main__":
    main()
