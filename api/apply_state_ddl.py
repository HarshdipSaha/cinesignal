"""Apply api/app_state_ddl.sql (query_log, memos tables). Idempotent.

Usage: python api/apply_state_ddl.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ingest.apply_ddl import get_client, split_statements  # noqa: E402


def main() -> None:
    client = get_client()
    ddl_path = ROOT / "api" / "app_state_ddl.sql"
    statements = split_statements(ddl_path.read_text(encoding="utf-8"))
    print(f"Applying {len(statements)} DDL statements from {ddl_path}")
    for i, stmt in enumerate(statements, 1):
        first_line = stmt.strip().splitlines()[0][:80]
        client.command(stmt)
        print(f"  [{i}/{len(statements)}] OK   {first_line}")
    tables = client.query("SHOW TABLES FROM cinesignal").result_rows
    print("Tables in cinesignal:", [t[0] for t in tables])


if __name__ == "__main__":
    main()
