"""Database access for the state chapter B keeps (REQ-15).

Two dialects, one interface. Postgres is the deployment target; SQLite exists so local development
and the idempotency tests can run without a server. The difference is confined to this module and to
the DDL in migrations.py: nothing above here knows which one it is talking to.

The honest boundary: running the migrations on SQLite proves the RUNNER is correct and idempotent.
It does not prove the Postgres DDL, which is why temp_database() refuses to invent a URL and
REQ-15's acceptance test stays red until a real Postgres is configured.
"""

import os
import sqlite3
from contextlib import contextmanager
from urllib.parse import urlparse

URL_ENV = "ACTION_ENGINE_DATABASE_URL"
TEST_URL_ENV = "ACTION_ENGINE_TEST_DATABASE_URL"


def database_url() -> str:
    url = os.environ.get(URL_ENV)
    if not url:
        raise RuntimeError("%s is not set; chapter B keeps its state in a database" % URL_ENV)
    return url


def dialect(url: str) -> str:
    scheme = urlparse(url).scheme.split("+")[0]
    if scheme in ("postgres", "postgresql"):
        return "postgres"
    if scheme == "sqlite":
        return "sqlite"
    raise RuntimeError("unsupported database URL scheme %r" % scheme)


def sqlite_path(url: str) -> str:
    # sqlite:///relative/path  or  sqlite:////absolute/path
    return url[len("sqlite:///"):]


@contextmanager
def connection(url: str = None):
    """A connection with a transaction, committed on success and rolled back on any exception."""
    url = url or database_url()
    kind = dialect(url)
    if kind == "sqlite":
        conn = sqlite3.connect(sqlite_path(url), isolation_level=None, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("BEGIN IMMEDIATE")
    else:
        try:
            import psycopg
        except ImportError as exc:  # pragma: no cover - exercised only where postgres is configured
            raise RuntimeError("postgres URL configured but psycopg is not installed") from exc
        conn = psycopg.connect(url)
    try:
        yield Cursor(conn, kind)
        conn.commit() if kind == "postgres" else conn.execute("COMMIT")
    except Exception:
        conn.rollback() if kind == "postgres" else conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


class Cursor:
    """Thin shim so callers write one SQL string with %s placeholders for both dialects."""

    def __init__(self, conn, kind: str):
        self._conn = conn
        self.kind = kind

    def _sql(self, sql: str) -> str:
        return sql.replace("%s", "?") if self.kind == "sqlite" else sql

    def execute(self, sql: str, params=()):
        if self.kind == "sqlite":
            return self._conn.execute(self._sql(sql), params)
        cur = self._conn.cursor()
        cur.execute(sql, params)
        return cur

    def fetchone(self, sql: str, params=()):
        cur = self.execute(sql, params)
        row = cur.fetchone()
        return row

    def fetchall(self, sql: str, params=()):
        return self.execute(sql, params).fetchall()
