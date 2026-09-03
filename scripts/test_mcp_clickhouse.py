"""Gate-0 smoke test: talk to the official mcp-clickhouse server over stdio
using the raw `mcp` SDK client (no ADK yet) and run a real query against
ClickHouse Cloud. Run: python scripts/test_mcp_clickhouse.py
"""
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parent.parent


async def main() -> None:
    load_dotenv(ROOT / ".env")
    env = {
        **os.environ,
        "CLICKHOUSE_HOST": os.environ["CLICKHOUSE_HOST"],
        "CLICKHOUSE_PORT": os.environ["CLICKHOUSE_PORT"],
        "CLICKHOUSE_USER": os.environ["CLICKHOUSE_USER"],
        "CLICKHOUSE_PASSWORD": os.environ["CLICKHOUSE_PASSWORD"],
        "CLICKHOUSE_SECURE": "true",
        "CLICKHOUSE_DATABASE": "cinesignal",
    }
    mcp_clickhouse_bin = str(Path(sys.executable).parent / "mcp-clickhouse")
    params = StdioServerParameters(command=mcp_clickhouse_bin, args=[], env=env)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print("Tools exposed:", [t.name for t in tools.tools])
            result = await session.call_tool("run_query", {"query": "SELECT 1 AS ok, version() AS v"})
            for block in result.content:
                print("run_query ->", getattr(block, "text", block))
            result2 = await session.call_tool("list_tables", {"database": "cinesignal"})
            for block in result2.content:
                text = getattr(block, "text", str(block))
                print("list_tables ->", text[:500])


if __name__ == "__main__":
    asyncio.run(main())
