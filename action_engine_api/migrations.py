"""Schema migrations (REQ-15). One command, empty to current, safe to run twice.

Deliberately small: a numbered list of statements, a table recording what has been applied, and a
runner that skips what is already there. No migration framework, because the schema is two tables
and a framework would be the largest dependency in the project.

Postgres is the target; SQLite is supported so local runs and the idempotency tests work without a
server. temp_database() does NOT invent a SQLite URL: REQ-15 says Postgres, so its acceptance test
stays red until ACTION_ENGINE_TEST_DATABASE_URL points at a real one (CI provides it in REQ-16).
"""

import os

from .store import TEST_URL_ENV, connection, database_url, dialect

MIGRATIONS = [
    ("0001_schema_migrations", {
        "postgres": """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                revision   TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )""",
        "sqlite": """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                revision   TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT (datetime('now'))
            )""",
    }),
    ("0002_idempotency_keys", {
        # response and expires_at are TEXT in both dialects on purpose. The response is stored
        # verbatim to be replayed, never queried by field, so JSONB would buy nothing and would
        # force a cast on every bind; expires_at holds an ISO-8601 UTC string, which sorts
        # correctly as text and compares the same way in both dialects. One shape, no casts, no
        # class of bug that only appears against Postgres.
        "postgres": """
            CREATE TABLE IF NOT EXISTS idempotency_keys (
                key           TEXT PRIMARY KEY,
                subject_id    TEXT NOT NULL,
                fingerprint   TEXT NOT NULL,
                state         TEXT NOT NULL CHECK (state IN ('in_flight', 'done')),
                export_id     TEXT,
                response      TEXT,
                created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
                expires_at    TEXT NOT NULL
            )""",
        "sqlite": """
            CREATE TABLE IF NOT EXISTS idempotency_keys (
                key           TEXT PRIMARY KEY,
                subject_id    TEXT NOT NULL,
                fingerprint   TEXT NOT NULL,
                state         TEXT NOT NULL CHECK (state IN ('in_flight', 'done')),
                export_id     TEXT,
                response      TEXT,
                created_at    TEXT NOT NULL DEFAULT (datetime('now')),
                expires_at    TEXT NOT NULL
            )""",
    }),
    ("0003_sink_calls", {
        # The recording sink used by tests and local runs counts its calls here, so
        # "was the third party called twice?" is answered by the database rather than by a log line.
        "postgres": """
            CREATE TABLE IF NOT EXISTS sink_calls (
                idempotency_key TEXT NOT NULL,
                called_at       TIMESTAMPTZ NOT NULL DEFAULT now()
            )""",
        "sqlite": """
            CREATE TABLE IF NOT EXISTS sink_calls (
                idempotency_key TEXT NOT NULL,
                called_at       TEXT NOT NULL DEFAULT (datetime('now'))
            )""",
    }),
]


def upgrade(url: str = None) -> int:
    """Apply every migration not yet recorded. Returns how many were applied this call; running it a
    second time returns 0, which is the whole point."""
    url = url or database_url()
    kind = dialect(url)
    applied = 0
    with connection(url) as cur:
        cur.execute(MIGRATIONS[0][1][kind])
        cur.execute("INSERT INTO schema_migrations (revision) VALUES (%s) "
                    + ("ON CONFLICT DO NOTHING" if kind == "postgres" else "ON CONFLICT DO NOTHING"),
                    (MIGRATIONS[0][0],))
        done = {r[0] for r in cur.fetchall("SELECT revision FROM schema_migrations")}
        for revision, sql in MIGRATIONS[1:]:
            if revision in done:
                continue
            cur.execute(sql[kind])
            cur.execute("INSERT INTO schema_migrations (revision) VALUES (%s)", (revision,))
            applied += 1
    return applied


def current_revision(url: str = None):
    url = url or database_url()
    with connection(url) as cur:
        row = cur.fetchone("SELECT revision FROM schema_migrations ORDER BY revision DESC LIMIT 1")
    return row[0] if row else None


def temp_database() -> str:
    """A database the acceptance suite may migrate from empty.

    No fallback on purpose. REQ-15 is about Postgres, and a SQLite substitute would turn this gate
    green while the Postgres DDL stayed unexercised -- the exact shape of false confidence this
    suite exists to prevent.
    """
    url = os.environ.get(TEST_URL_ENV)
    if not url:
        raise RuntimeError(
            "REQ-15 needs a real database: set %s to a Postgres URL the suite may create tables in "
            "(CI provides one as a service container)." % TEST_URL_ENV)
    return url


def main() -> None:
    applied = upgrade()
    print("migrations applied: %d; at revision %s" % (applied, current_revision()))


if __name__ == "__main__":
    main()
