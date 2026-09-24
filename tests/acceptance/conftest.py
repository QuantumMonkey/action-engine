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

    db = tmp_path_factory.mktemp("acceptance") / "sample.db"
    build(str(db))
    os.environ["ACTION_ENGINE_DB"] = str(db)
    os.environ.setdefault("ACTION_ENGINE_JWT_SECRET", "acceptance-only-secret-not-for-any-deployment")
    yield

