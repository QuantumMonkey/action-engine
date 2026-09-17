"""MCP server exposing one local SQLite db, read-only (REQ-01, REQ-02).

Usage:
    py -m sqlite_mcp_server.server path\\to\\sample.db        (Windows)
    python3 -m sqlite_mcp_server.server path/to/sample.db    (macOS/Linux)

Tools: list_tables, table_schema, run_readonly_query.
All refusals are typed dicts, never exceptions (FLOW-03 demo).

Runs on the official MCP Python SDK, either major version: 1.x exposes
the server class as FastMCP, 2.x renamed it to MCPServer. Same decorator
API for the three tools used here.
"""

import functools
import sys

try:  # mcp >= 2.0
    from mcp.server.mcpserver import MCPServer as _Server
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Server

from .guards import PathLock, RefusalError, open_readonly, run_query

mcp = _Server("sqlite-readonly")

_lock: "PathLock | None" = None  # set in main()


def _refusal_safe(fn):
    """Turn a RefusalError into its typed payload. functools.wraps keeps the
    real signature visible, which is what the SDK builds the tool's JSON
    schema from; without it every tool would advertise (*args, **kwargs)."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except RefusalError as exc:
            return exc.payload

    return wrapper


@mcp.tool()
@_refusal_safe
def list_tables() -> dict:
    """List all user tables in the locked database."""
    conn = open_readonly(_lock)
    try:
        cur = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
        return {"tables": [r[0] for r in cur.fetchall()]}
    finally:
        conn.close()


@mcp.tool()
@_refusal_safe
def table_schema(table: str) -> dict:
    """Return the CREATE TABLE statement and column names for one table."""
    conn = open_readonly(_lock)
    try:
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
        if row is None:
            return {"error": "unknown_table", "table": table}
        # Column names come from a zero-row SELECT. PRAGMA table_info (and
        # the pragma_table_info() table-valued function) is denied by the
        # authorizer, and that deny list is deliberately not widened for the
        # server's own convenience. The name was matched exactly against
        # sqlite_master above, so quoting it as an identifier is safe.
        quoted = '"' + table.replace('"', '""') + '"'
        cur = conn.execute(f"SELECT * FROM {quoted} LIMIT 0")
        return {
            "table": table,
            "columns": [d[0] for d in cur.description],
            "create_sql": row[0],
        }
    finally:
        conn.close()


@mcp.tool()
@_refusal_safe
def run_readonly_query(sql: str) -> dict:
    """Run a single SELECT query against the locked database.
    Any write/DDL attempt returns {"error": "read_only_violation", ...}."""
    return run_query(_lock, sql)


def main() -> None:
    global _lock
    if len(sys.argv) != 2:
        print("usage: python -m sqlite_mcp_server.server <path-to-db>",
              file=sys.stderr)
        sys.exit(2)
    try:
        _lock = PathLock(sys.argv[1])
    except FileNotFoundError as exc:
        print(f"sqlite-readonly: {exc}", file=sys.stderr)
        print("hint: the sample fixture is generated, not committed -- run "
              "scripts/make_fixture.py first", file=sys.stderr)
        sys.exit(2)
    # stderr only: stdout is the MCP transport.
    print(f"sqlite-readonly: locked to {_lock.locked_realpath}", file=sys.stderr)
    mcp.run()


if __name__ == "__main__":
    main()
