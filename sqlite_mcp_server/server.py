"""FastMCP server exposing one local SQLite db, read-only (REQ-01, REQ-02).

Usage:
    py -m sqlite_mcp_server.server path\\to\\sample.db

Tools: list_tables, table_schema, run_readonly_query.
All refusals are typed dicts, never exceptions (FLOW-03 demo).
"""

import sys

from mcp.server.fastmcp import FastMCP

from .guards import PathLock, RefusalError, open_readonly, run_query

mcp = FastMCP("sqlite-readonly")

_lock: PathLock = None  # set in main()


def _refusal_safe(fn):
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except RefusalError as exc:
            return exc.payload
    wrapper.__name__ = fn.__name__
    wrapper.__doc__ = fn.__doc__
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
    """Return column names, types, and constraints for one table."""
    conn = open_readonly(_lock)
    try:
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        )
        if cur.fetchone() is None:
            return {"error": "unknown_table", "table": table}
        cols = conn.execute(
            "SELECT name, type, [notnull], pk FROM pragma_table_info(?)",
            (table,),
        ).fetchall()
        return {
            "table": table,
            "columns": [
                {"name": c[0], "type": c[1], "notnull": bool(c[2]),
                 "primary_key": bool(c[3])}
                for c in cols
            ],
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
        print("usage: py -m sqlite_mcp_server.server <path-to-db>",
              file=sys.stderr)
        sys.exit(2)
    _lock = PathLock(sys.argv[1])
    mcp.run()


if __name__ == "__main__":
    main()
