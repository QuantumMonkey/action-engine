"""Unit tests for the idempotent export (REQ-14, ADR-0002).

The property that matters: one decision, one side effect, provably. Everything else here exists to
stop that property being true only on the happy path.
"""

import pytest

pytest.importorskip("fastapi", reason="install the api extra: pip install -e .[api]")
starlette_test = pytest.importorskip("starlette.testclient", reason="install the api extra")

import action_engine_api.service as app_module  # noqa: E402
from action_engine_api.audit import AuditLog  # noqa: E402
from action_engine_api.migrations import current_revision, upgrade  # noqa: E402
from action_engine_api.sinks import call_count  # noqa: E402
from action_engine_api.testing import issue_test_tokens  # noqa: E402
from scripts.make_fixture import build  # noqa: E402

SECRET = "unit-test-secret-long-enough-for-hmac-sha256"


@pytest.fixture
def service(tmp_path, monkeypatch):
    db = tmp_path / "sample.db"
    build(str(db))
    monkeypatch.setenv("ACTION_ENGINE_DB", str(db))
    monkeypatch.setenv("ACTION_ENGINE_AUDIT_LOG", str(tmp_path / "audit.jsonl"))
    monkeypatch.setenv("ACTION_ENGINE_JWT_SECRET", SECRET)
    monkeypatch.setenv("ACTION_ENGINE_DATABASE_URL",
                       "sqlite:///" + str(tmp_path / "state.db").replace("\\", "/"))
    monkeypatch.setenv("ACTION_ENGINE_RATE_LIMIT", "500")
    monkeypatch.setattr(app_module, "_lock", None)
    monkeypatch.setattr(app_module, "_audit", AuditLog(str(tmp_path / "audit.jsonl")))
    app_module.limiter.reset()
    upgrade()
    return starlette_test.TestClient(app_module.app), issue_test_tokens()


def headers(token, key=None):
    h = {"Authorization": "Bearer %s" % token}
    if key:
        h["Idempotency-Key"] = key
    return h


BODY = {"sql": "SELECT 1", "sink": "test"}


def test_migrations_are_idempotent_on_this_dialect(service):
    """REQ-15's own gate demands Postgres; this proves the runner does not re-apply work."""
    first = current_revision()
    assert upgrade() == 0, "a second upgrade applied migrations again"
    assert current_revision() == first


def test_export_requires_a_key(service):
    client, tokens = service
    r = client.post("/v1/export", json=BODY, headers=headers(tokens["delegated"]))
    assert r.status_code == 400 and r.json()["reason"] == "idempotency_key_required"
    assert call_count("") == 0


def test_replay_returns_the_first_result_and_calls_the_sink_once(service):
    client, tokens = service
    h = headers(tokens["delegated"], "key-1")
    first = client.post("/v1/export", json=BODY, headers=h)
    second = client.post("/v1/export", json=BODY, headers=h)
    assert first.status_code == second.status_code == 200
    assert first.json()["export_id"] == second.json()["export_id"]
    assert second.headers.get("Idempotent-Replay") == "true"
    assert first.headers.get("Idempotent-Replay") is None, "the first call is not a replay"
    assert call_count("key-1") == 1


def test_same_key_different_body_is_a_conflict_not_a_second_export(service):
    client, tokens = service
    h = headers(tokens["delegated"], "key-2")
    assert client.post("/v1/export", json=BODY, headers=h).status_code == 200
    other = client.post("/v1/export", json={"sql": "SELECT 2", "sink": "test"}, headers=h)
    assert other.status_code == 409 and other.json()["reason"] == "idempotency_key_reused"
    assert call_count("key-2") == 1, "the conflicting request exported anyway"


def test_another_subject_cannot_reuse_a_key(service):
    client, tokens = service
    assert client.post("/v1/export", json=BODY,
                       headers=headers(tokens["delegated"], "key-3")).status_code == 200
    theirs = client.post("/v1/export", json=BODY, headers=headers(tokens["service"], "key-3"))
    assert theirs.status_code == 409
    assert "different request" in theirs.json()["detail"], "the detail should not reveal the owner"
    assert call_count("key-3") == 1


def test_a_refused_query_releases_the_key_so_an_honest_retry_works(service):
    client, tokens = service
    h = headers(tokens["delegated"], "key-4")
    bad = client.post("/v1/export", json={"sql": "UPDATE t SET a = 1", "sink": "test"}, headers=h)
    assert bad.status_code == 400 and call_count("key-4") == 0

    good = client.post("/v1/export", json=BODY, headers=h)
    assert good.status_code == 200, "our own bookkeeping blocked a retry of work that never happened"
    assert call_count("key-4") == 1


def test_unknown_sink_is_refused_and_leaves_no_claim(service):
    client, tokens = service
    h = headers(tokens["delegated"], "key-5")
    r = client.post("/v1/export", json={"sql": "SELECT 1", "sink": "nowhere"}, headers=h)
    assert r.status_code == 400 and r.json()["reason"] == "no_such_sink"
    assert client.post("/v1/export", json=BODY, headers=h).status_code == 200
