"""Acceptance gate for chapter B (docs/planning/chapter-B-http-api.md).

These tests are the definition of done for the HTTP surface, written before the code exists. They are
RED on purpose: until `action_engine_api` is importable and satisfies them, running

    pytest -m acceptance

fails, and that failure is the gate. The default `pytest` run deselects this directory (see
pyproject.toml addopts) so the existing chapter-1 suite stays green while chapter B is built.

Each test names the REQ it enforces. Do not soften a test to make it pass; amend the spec first, the
way DEVIATIONS.md requires, and then change the test.
"""

import json
import time

import pytest

pytestmark = pytest.mark.acceptance

MISSING = "chapter B is not built yet: expose an ASGI app as action_engine_api.app (REQ-10)"


def require(name, why=MISSING):
    """Import or FAIL. Deliberately not importorskip: a skipped gate reads as green in CI, and this
    suite exists to be red until the chapter is built."""
    import importlib

    try:
        return importlib.import_module(name)
    except ImportError as exc:
        pytest.fail("%s [%s: %s]" % (why, name, exc))


@pytest.fixture(scope="module")
def client():
    """The app under test, over a real ASGI transport."""
    app_mod = require("action_engine_api")
    starlette_test = require("starlette.testclient", "install the api extra: pip install -e .[api]")
    return starlette_test.TestClient(app_mod.app)


@pytest.fixture
def tokens():
    """Three tokens the auth model must tell apart (ADR-0001): a delegated human token, a service
    token with no initiator, and one whose signature does not verify."""
    return require("action_engine_api.testing").issue_test_tokens()


def audit_rows(client, request_id, token):
    r = client.get("/v1/audit/%s" % request_id, headers={"Authorization": "Bearer %s" % token})
    return r.json() if r.status_code == 200 else None


# REQ-10 -----------------------------------------------------------------------------------------
def test_openapi_matches_routes(client):
    doc = client.get("/openapi.json").json()
    documented = {(p, m.lower()) for p, item in doc["paths"].items() for m in item}
    live = {(r.path, m.lower()) for r in client.app.routes for m in getattr(r, "methods", [])
            if m.lower() not in ("head", "options")}
    assert documented == live, "OpenAPI and the router disagree: %s" % (documented ^ live)
    for path, item in doc["paths"].items():
        for method, op in item.items():
            assert op.get("summary"), "%s %s has no summary" % (method.upper(), path)


# REQ-11 -----------------------------------------------------------------------------------------
def test_auth_rejects_missing_bad_and_expired(client, tokens):
    cases = {
        "missing": {},
        "malformed": {"Authorization": "Bearer not-a-token"},
        "bad-signature": {"Authorization": "Bearer %s" % tokens["bad_signature"]},
        "expired": {"Authorization": "Bearer %s" % tokens["expired"]},
    }
    for name, headers in cases.items():
        r = client.get("/v1/tables", headers=headers)
        assert r.status_code == 401, "%s got %s" % (name, r.status_code)
        body = r.json()
        assert body.get("refused") is True and body.get("reason"), "%s: untyped refusal %s" % (name, body)


def test_healthz_is_open_and_unaudited(client, tokens):
    h = {"Authorization": "Bearer %s" % tokens["delegated"]}
    counted = client.get("/v1/audit/_count", headers=h)
    assert counted.status_code == 200, "no audit counter to check against (REQ-13 not built)"
    before = counted.json()
    assert client.get("/healthz").status_code == 200
    after = client.get("/v1/audit/_count", headers=h).json()
    assert before == after, "health checks must not write audit rows"


# REQ-12 -----------------------------------------------------------------------------------------
def test_rate_limit_returns_429_then_recovers(client, tokens):
    h = {"Authorization": "Bearer %s" % tokens["delegated"]}
    limit = client.get("/healthz").json()["rate_limit_per_minute"]
    codes = [client.get("/v1/tables", headers=h).status_code for _ in range(limit + 5)]
    assert 429 in codes, "no request was limited after %d calls" % (limit + 5)
    limited = client.get("/v1/tables", headers=h)
    assert limited.headers.get("Retry-After"), "429 without Retry-After"
    time.sleep(int(limited.headers["Retry-After"]) + 1)
    assert client.get("/v1/tables", headers=h).status_code == 200, "window never reset"


# REQ-01/REQ-02 carried onto the wire -------------------------------------------------------------
def test_write_attempt_is_refused_and_audited(client, tokens):
    h = {"Authorization": "Bearer %s" % tokens["delegated"]}
    r = client.post("/v1/query", json={"sql": "UPDATE t SET a = 1"}, headers=h)
    assert r.status_code == 400 and r.json()["refused"] is True
    row = audit_rows(client, r.headers["X-Request-Id"], tokens["delegated"])
    assert row["outcome"] == "refused" and row["refusal_reason"], "a refusal must be recorded, not dropped"


# REQ-13 -----------------------------------------------------------------------------------------
def test_audit_row_binds_three_identities(client, tokens):
    h = {"Authorization": "Bearer %s" % tokens["delegated"]}
    r = client.get("/v1/tables", headers=h)
    assert r.status_code == 200
    row = audit_rows(client, r.headers["X-Request-Id"], tokens["delegated"])
    for field in ("agent_id", "subject_id", "initiator_id", "route", "args_hash", "outcome", "duration_ms"):
        assert row.get(field), "audit row missing %s" % field
    assert len(row["args_hash"]) == 64, "args_hash must be a sha256 digest, never the args themselves"
    assert "sql" not in json.dumps(row).lower() or row["route"] != "/v1/query", "raw args leaked into the audit row"


def test_initiator_from_token_not_from_header(client, tokens):
    spoof = {"Authorization": "Bearer %s" % tokens["service"], "X-Initiator-Id": "ceo@example.com"}
    r = client.get("/v1/tables", headers=spoof)
    row = audit_rows(client, r.headers["X-Request-Id"], tokens["service"])
    assert row["initiator_id"] == "unattended", "a service token must record 'unattended', got %r" % row["initiator_id"]

    r2 = client.get("/v1/tables", headers={"Authorization": "Bearer %s" % tokens["delegated"]})
    row2 = audit_rows(client, r2.headers["X-Request-Id"], tokens["delegated"])
    assert row2["initiator_id"] == tokens["delegated_initiator"], "delegated token must carry the human initiator"
    assert row2["initiator_id"] != row2["agent_id"], "agent and initiator must be distinguishable"


# REQ-14 -----------------------------------------------------------------------------------------
def test_replay_with_same_key_does_not_act_twice(client, tokens):
    h = {"Authorization": "Bearer %s" % tokens["delegated"], "Idempotency-Key": "acc-test-key-1"}
    body = {"sql": "SELECT 1", "sink": "test"}
    first = client.post("/v1/export", json=body, headers=h)
    second = client.post("/v1/export", json=body, headers=h)
    assert first.status_code == second.status_code == 200
    assert first.json()["export_id"] == second.json()["export_id"], "replay produced a second export"
    assert second.headers.get("Idempotent-Replay") == "true", "replay not flagged to the caller"
    sink = require("action_engine_api.testing").sink_calls("acc-test-key-1")
    assert sink == 1, "the third-party sink was called %d times for one key" % sink


# REQ-15 -----------------------------------------------------------------------------------------
def test_migrations_are_idempotent():
    mig = require("action_engine_api.migrations")
    url = mig.temp_database()
    mig.upgrade(url)
    first = mig.current_revision(url)
    mig.upgrade(url)
    assert mig.current_revision(url) == first, "running migrations twice changed the revision"
    assert first, "no revision recorded after upgrade"
