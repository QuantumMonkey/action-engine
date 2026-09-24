"""Environment for the acceptance suite: a real database file and a signing secret.

This sets up what a deployment would provide. It does not stub anything the tests assert on.
"""

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)


@pytest.fixture(scope="session", autouse=True)
def service_environment(tmp_path_factory):
    from scripts.make_fixture import build

    root = tmp_path_factory.mktemp("acceptance")
    db = root / "sample.db"
    build(str(db))
    os.environ["ACTION_ENGINE_DB"] = str(db)
    os.environ["ACTION_ENGINE_AUDIT_LOG"] = str(root / "audit.jsonl")
    # A short window keeps the suite fast; the limiter logic is identical at sixty seconds, and
    # /healthz reports the rate normalised per minute either way.
    os.environ["ACTION_ENGINE_RATE_LIMIT"] = "10"
    os.environ["ACTION_ENGINE_RATE_WINDOW"] = "5"
    # State for REQ-14. SQLite here proves the idempotency logic; REQ-15's own test still demands a
    # real Postgres (ACTION_ENGINE_TEST_DATABASE_URL), which is why it stays red until CI has one.
    os.environ["ACTION_ENGINE_DATABASE_URL"] = "sqlite:///" + str(root / "state.db").replace("\\", "/")
    from action_engine_api.migrations import upgrade

    upgrade()
    os.environ.setdefault("ACTION_ENGINE_JWT_SECRET", "acceptance-only-secret-not-for-any-deployment")
    yield

