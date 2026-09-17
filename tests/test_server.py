"""End-to-end over MCP stdio with the official client, the way a host
(Claude Desktop, Claude Code, any MCP client) talks to the server: the tool
schemas a host sees, the three tools, typed refusals on the wire, and the
symlink swap under a live session.

Needs the mcp package (1.x or 2.x). tests/test_guards.py covers the guards
without it.
"""

import json
import os
import sqlite3
import subprocess
import sys

import pytest

anyio = pytest.importorskip("anyio")
mcp_pkg = pytest.importorskip("mcp")
from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from scripts.make_fixture import build  # noqa: E402


def _attr(obj, *names, default=None):
    """mcp 2.x snake_cases the protocol types (input_schema, is_error,
    structured_content); 1.x keeps the wire names (inputSchema, ...)."""
    for name in names:
        value = getattr(obj, name, None)
        if value is not None:
            return value
    return default


def _payload(result):
    """Tool output as a dict, whether the SDK sent structured content or
    JSON text."""
    sc = _attr(result, "structured_content", "structuredContent")
    if sc is not None:
        return sc
    return json.loads(result.content[0].text)


def _is_error(result):
    return bool(_attr(result, "is_error", "isError", default=False))


def _schema(tool):
    return _attr(tool, "input_schema", "inputSchema")


async def _with_session(db_path, fn):
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "sqlite_mcp_server.server", db_path],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": ROOT},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await fn(session)


def run(db_path, fn):
    return anyio.run(_with_session, db_path, fn)


@pytest.fixture()
def db(tmp_path):
    path = str(tmp_path / "sample.db")
    build(path)
    return path


def test_tools_advertise_real_parameters(db):
    async def fn(s):
        return (await s.list_tools()).tools

    tools = {t.name: t for t in run(db, fn)}
    assert set(tools) == {"list_tables", "table_schema", "run_readonly_query"}
    q = _schema(tools["run_readonly_query"])
    assert "sql" in q["properties"] and "sql" in q.get("required", [])
    t = _schema(tools["table_schema"])
    assert "table" in t["properties"] and "table" in t.get("required", [])
    assert "args" not in q["properties"] and "kwargs" not in q["properties"]


def test_list_tables_and_table_schema(db):
    async def fn(s):
        return (
            _payload(await s.call_tool("list_tables", {})),
            _payload(await s.call_tool("table_schema", {"table": "orders"})),
            _payload(await s.call_tool("table_schema", {"table": "nope"})),
        )

    tables, orders, nope = run(db, fn)
    assert tables == {"tables": ["customers", "orders"]}
    assert orders["table"] == "orders"
    assert orders["columns"] == ["id", "customer_id", "order_date", "amount", "status"]
    assert orders["create_sql"].lstrip().upper().startswith("CREATE TABLE ORDERS")
    assert nope == {"error": "unknown_table", "table": "nope"}


def test_select_over_the_wire(db):
    async def fn(s):
        r = await s.call_tool(
            "run_readonly_query",
            {"sql": "SELECT name FROM customers ORDER BY id LIMIT 2"},
        )
        return _is_error(r), _payload(r)

    is_error, out = run(db, fn)
    assert is_error is False
    assert out["columns"] == ["name"]
    assert out["rows"] == [["Meridian Textiles"], ["BlueFin Logistics"]]


@pytest.mark.parametrize("sql", [
    "UPDATE customers SET name = 'x'",
    "DELETE FROM orders",
    "DROP TABLE customers",
    "ATTACH DATABASE 'evil.db' AS e",
    "SELECT 1; DELETE FROM orders",
    "WITH x AS (SELECT 1) DELETE FROM orders",
])
def test_writes_come_back_as_typed_refusals(db, sql):
    async def fn(s):
        r = await s.call_tool("run_readonly_query", {"sql": sql})
        return _is_error(r), _payload(r)

    is_error, out = run(db, fn)
    assert is_error is False, "a refusal is a result, not a protocol error"
    assert out["error"] == "read_only_violation"
    assert out["attempted_sql"] == sql
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 8
    assert conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0] == 5
    conn.close()
    assert not os.path.exists(os.path.join(ROOT, "evil.db"))


def test_symlink_swap_refused_under_live_session(tmp_path):
    served = str(tmp_path / "served.db")
    decoy = str(tmp_path / "decoy.db")
    build(served)
    build(decoy)
    sql = {"sql": "SELECT COUNT(*) FROM customers"}

    async def fn(s):
        before = _payload(await s.call_tool("run_readonly_query", sql))
        os.remove(served)
        try:
            os.symlink(decoy, served)
        except OSError:
            pytest.skip("symlink creation not permitted (Windows: enable "
                        "Developer Mode or run as admin)")
        after = _payload(await s.call_tool("run_readonly_query", sql))
        listing = _payload(await s.call_tool("list_tables", {}))
        return before, after, listing

    before, after, listing = run(served, fn)
    assert before["rows"] == [[5]]
    assert after["error"] == "path_lock_violation"
    assert listing["error"] == "path_lock_violation"


def test_missing_db_exits_with_a_message(tmp_path):
    proc = subprocess.run(
        [sys.executable, "-m", "sqlite_mcp_server.server", str(tmp_path / "nope.db")],
        cwd=ROOT, capture_output=True, text=True, timeout=60,
        env={**os.environ, "PYTHONPATH": ROOT},
    )
    assert proc.returncode == 2
    assert "database file not found" in proc.stderr
    assert "make_fixture" in proc.stderr
