"""Unit tests for the audit trail (REQ-13, ADR-0001).

Two properties carry the whole claim and are tested here rather than only in the acceptance suite,
because they are the ones that would fail silently: arguments are never stored, and a row belongs to
exactly one subject.
"""

import json
import os

import pytest

pytest.importorskip("fastapi", reason="install the api extra: pip install -e .[api]")
starlette_test = pytest.importorskip("starlette.testclient", reason="install the api extra")

import action_engine_api.service as app_module  # noqa: E402
from action_engine_api.audit import AuditLog, args_hash  # noqa: E402
from action_engine_api.testing import issue_test_tokens  # noqa: E402
from scripts.make_fixture import build  # noqa: E402

SECRET = "unit-test-secret-long-enough-for-hmac-sha256"
SECRET_SQL = "SELECT name FROM sqlite_master WHERE name = 'patients_confidential'"


@pytest.fixture
def service(tmp_path, monkeypatch):
    db = tmp_path / "sample.db"
    build(str(db))
    monkeypatch.setenv("ACTION_ENGINE_DB", str(db))
    monkeypatch.setenv("ACTION_ENGINE_AUDIT_LOG", str(tmp_path / "audit.jsonl"))
    monkeypatch.setenv("ACTION_ENGINE_JWT_SECRET", SECRET)
    monkeypatch.setattr(app_module, "_lock", None)
    monkeypatch.setattr(app_module, "_audit", AuditLog(str(tmp_path / "audit.jsonl")))
    tokens = issue_test_tokens()
    client = starlette_test.TestClient(app_module.app)
    return client, tokens, tmp_path / "audit.jsonl"


def auth(token):
    return {"Authorization": "Bearer %s" % token}


def test_arguments_are_hashed_never_stored(service):
    client, tokens, log_path = service
    r = client.post("/v1/query", json={"sql": SECRET_SQL}, headers=auth(tokens["delegated"]))
    assert r.status_code == 200

    raw = log_path.read_text(encoding="ascii")
    assert SECRET_SQL not in raw, "the query text reached the audit file"
    assert "patients_confidential" not in raw, "an argument value reached the audit file"

    row = json.loads(raw.strip().splitlines()[-1])
    assert row["args_hash"] == args_hash({"sql": SECRET_SQL})
    assert len(row["args_hash"]) == 64


def test_refusal_records_the_reason_without_the_attempted_sql(service):
    client, tokens, log_path = service
    attempted = "UPDATE secrets SET value = 'x'"
    r = client.post("/v1/query", json={"sql": attempted}, headers=auth(tokens["delegated"]))
    assert r.status_code == 400 and r.json()["refused"] is True

    row = json.loads(log_path.read_text(encoding="ascii").strip().splitlines()[-1])
    assert row["outcome"] == "refused"
    assert row["refusal_reason"] == "read_only_violation"
    assert attempted not in log_path.read_text(encoding="ascii")


def test_a_row_belongs_to_one_subject_and_reads_as_absent_to_others(service):
    client, tokens, _ = service
    r = client.get("/v1/tables", headers=auth(tokens["delegated"]))
    request_id = r.headers["X-Request-Id"]

    mine = client.get("/v1/audit/%s" % request_id, headers=auth(tokens["delegated"]))
    assert mine.status_code == 200 and mine.json()["request_id"] == request_id

    theirs = client.get("/v1/audit/%s" % request_id, headers=auth(tokens["service"]))
    assert theirs.status_code == 404, "another subject could read the row"
    assert "refused" in theirs.json(), "the refusal must stay typed"


def test_open_and_audit_routes_write_no_rows(service):
    client, tokens, log_path = service
    client.get("/healthz")
    client.get("/v1/audit/_count", headers=auth(tokens["delegated"]))
    assert not os.path.exists(log_path) or log_path.read_text(encoding="ascii").strip() == ""


def test_failed_auth_writes_no_row(service):
    client, tokens, log_path = service
    assert client.get("/v1/tables", headers=auth(tokens["bad_signature"])).status_code == 401
    assert client.get("/v1/tables").status_code == 401
    assert not os.path.exists(log_path) or log_path.read_text(encoding="ascii").strip() == ""


def test_every_response_carries_a_request_id(service):
    client, tokens, _ = service
    for response in (client.get("/healthz"),
                     client.get("/v1/tables", headers=auth(tokens["delegated"])),
                     client.get("/v1/tables", headers=auth(tokens["expired"]))):
        assert response.headers.get("X-Request-Id"), "a caller cannot quote what they were not given"
