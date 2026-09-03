"""Apply ingest/ddl.sql to the ClickHouse Cloud cluster. Idempotent.

Usage: python ingest/apply_ddl.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
import clickhouse_connect

ROOT = Path(__file__).resolve().parent.parent


def get_client():
    load_dotenv(ROOT / ".env")
    return clickhouse_connect.get_client(
        host=os.environ["CLICKHOUSE_HOST"],
        port=int(os.environ["CLICKHOUSE_PORT"]),
        username=os.environ["CLICKHOUSE_USER"],
        password=os.environ["CLICKHOUSE_PASSWORD"],
        secure=True,
    )


def split_statements(sql: str) -> list[str]:
    statements, buf = [], []
    for line in sql.splitlines():
        stripped = line.strip()
        if stripped.startswith("--") or not stripped:
            continue
        buf.append(line)
        if stripped.endswith(";"):
            statements.append("\n".join(buf).rstrip(";\n") + "")
            buf = []
    if buf:
        statements.append("\n".join(buf))
    return [s for s in statements if s.strip()]


def main() -> None:
    client = get_client()
    ddl_path = ROOT / "ingest" / "ddl.sql"
    statements = split_statements(ddl_path.read_text(encoding="utf-8"))
    print(f"Applying {len(statements)} DDL statements from {ddl_path}")
    for i, stmt in enumerate(statements, 1):
        first_line = stmt.strip().splitlines()[0][:80]
        try:
            client.command(stmt)
            print(f"  [{i}/{len(statements)}] OK   {first_line}")
        except Exception as exc:  # noqa: BLE001
            print(f"  [{i}/{len(statements)}] FAIL {first_line}\n    {exc}", file=sys.stderr)
            raise

    tables = client.query("SHOW TABLES FROM cinesignal").result_rows
    print("Tables in cinesignal:", [t[0] for t in tables])


if __name__ == "__main__":
    main()
