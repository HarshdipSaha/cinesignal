"""Shared direct ClickHouse client for app-state reads (memos, query_log,
fan-explorer). NOT used for playbook analytical queries — those go through
mcp-clickhouse exclusively (agent/mcp_client.py). This module is for the
API layer's own persistence/read-back, which the spec doesn't require to be
MCP-mediated, and where a fast, connection-pooled client matters for a
public-facing endpoint (Fan Explorer)."""
from __future__ import annotations

import os
from pathlib import Path

import clickhouse_connect
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

_client = None


def get_client():
    global _client
    if _client is None:
        _client = clickhouse_connect.get_client(
            host=os.environ["CLICKHOUSE_HOST"],
            port=int(os.environ["CLICKHOUSE_PORT"]),
            username=os.environ["CLICKHOUSE_USER"],
            password=os.environ["CLICKHOUSE_PASSWORD"],
            secure=True,
            database="cinesignal",
        )
    return _client
