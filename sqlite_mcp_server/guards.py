"""Security guards for the SQLite MCP server (REQ-01, REQ-02, D-08).

Two guarantees, both enforced at the server, never at the prompt:
1. Path lock: the server serves exactly ONE .db file, resolved via
   os.path.realpath at startup AND re-checked on every connection
   (symlink swap defense, D-08).
2. Read-only: SELECT-only statement screen + sqlite3 authorizer +
   mode=ro URI connection. Any write/DDL attempt returns a typed
   refusal, never an exception (FLOW-03).
"""

import os
import re
import sqlite3


class RefusalError(Exception):
    """Carries the typed refusal payload for a blocked operation."""

    def __init__(self, error: str, detail: str = "", attempted_sql: str = ""):
        super().__init__(error)
        self.payload = {"error": error}
        if detail:
            self.payload["detail"] = detail
        if attempted_sql:
            self.payload["attempted_sql"] = attempted_sql


class PathLock:
    """Locks the server to a single database file resolved at startup."""

    def __init__(self, db_path: str):
        real = os.path.realpath(db_path)
        if not os.path.isfile(real):
            raise FileNotFoundError(f"database file not found: {db_path}")
        self.locked_realpath = real
        self.declared_path = db_path

    def check(self) -> str:
        """Re-resolve the declared path; refuse if it no longer resolves
        to the path locked at startup (e.g. swapped for a symlink)."""
        current = os.path.realpath(self.declared_path)
        if current != self.locked_realpath:
            raise RefusalError(
                "path_lock_violation",
                detail="declared db path no longer resolves to the file "
                       "locked at startup",
            )
        return self.locked_realpath


_COMMENT_RE = re.compile(r"(--[^\n]*|/\*.*?\*/)", re.DOTALL)

# sqlite3 authorizer opcodes that a read-only query may use.
_ALLOWED_OPS = {
    sqlite3.SQLITE_SELECT,
    sqlite3.SQLITE_READ,
    sqlite3.SQLITE_FUNCTION,
    # sqlite runs these internally for some SELECTs
    31,  # SQLITE_RECURSIVE
}


def _strip_comments(sql: str) -> str:
    return _COMMENT_RE.sub(" ", sql)


def screen_select_only(sql: str) -> str:
    """Statement-level screen: single statement, must begin with SELECT
    or WITH after comment stripping. Returns normalized sql or raises
    RefusalError."""
    stripped = _strip_comments(sql).strip().rstrip(";").strip()
    if not stripped:
        raise RefusalError("empty_query", attempted_sql=sql)
    if ";" in stripped:
        raise RefusalError(
            "read_only_violation",
            detail="multiple statements are not allowed",
            attempted_sql=sql,
        )
    head = stripped.split(None, 1)[0].upper()
    if head not in ("SELECT", "WITH"):
        raise RefusalError(
            "read_only_violation",
            detail=f"only SELECT queries are allowed, got '{head}'",
            attempted_sql=sql,
        )
    return stripped


def _authorizer(action, arg1, arg2, dbname, source):
    if action in _ALLOWED_OPS:
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


def open_readonly(lock: PathLock) -> sqlite3.Connection:
    """Open the locked db in read-only mode with a deny-by-default
    authorizer. Belt (mode=ro), suspenders (authorizer), and the
    statement screen runs before either."""
    path = lock.check()
    uri = "file:{}?mode=ro".format(path.replace("\\", "/"))
    conn = sqlite3.connect(uri, uri=True)
    conn.set_authorizer(_authorizer)
    return conn


def run_query(lock: PathLock, sql: str, max_rows: int = 200) -> dict:
    """Screen, execute, and shape a read-only query result."""
    normalized = screen_select_only(sql)
    conn = open_readonly(lock)
    try:
        try:
            cur = conn.execute(normalized)
        except sqlite3.DatabaseError as exc:
            # authorizer denials surface here too
            msg = str(exc)
            if "not authorized" in msg or "prohibited" in msg:
                raise RefusalError(
                    "read_only_violation", detail=msg, attempted_sql=sql
                )
            raise RefusalError("sql_error", detail=msg, attempted_sql=sql)
        columns = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchmany(max_rows)
        truncated = cur.fetchone() is not None
        return {
            "columns": columns,
            "rows": [list(r) for r in rows],
            "row_count": len(rows),
            "truncated": truncated,
        }
    finally:
        conn.close()
