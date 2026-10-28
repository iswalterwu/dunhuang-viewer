"""仅提供已实现的运维命令；没有命令行导入入口。"""

import argparse
import json
import os

import psycopg
from psycopg.rows import dict_row

from .db import migrate
from .importer import read_report


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m dh_catalog")
    parser.add_argument("command", choices=["migrate", "report"])
    parser.add_argument("--run", type=int, help="report 的批次 ID；省略时读取最新批次")
    args = parser.parse_args()
    if args.run is not None and (args.command != "report" or args.run < 1):
        parser.error("--run 仅用于 report，且必须为正整数")
    database_url = os.environ.get("DH_DATABASE_URL")
    if not database_url:
        parser.error("需要配置 DH_DATABASE_URL")
    try:
        with psycopg.connect(database_url, autocommit=True, row_factory=dict_row) as connection:
            if args.command == "migrate":
                applied = migrate(connection)
                print("迁移完成：" + (", ".join(applied) if applied else "已是最新版本"))
            else:
                with connection.transaction():
                    connection.execute("SET TRANSACTION READ ONLY")
                    report = read_report(connection, args.run)
                if report is None:
                    parser.exit(1, "未找到导入批次\n")
                print(json.dumps(report, ensure_ascii=False, indent=2))
    except psycopg.Error as error:
        # 连接异常文本可能包含口令；不把连接串或驱动原始消息打印到终端。
        parser.exit(1, f"数据库操作失败：{type(error).__name__}\n")


if __name__ == "__main__":
    main()
