"""Unit tests for the chapter B auth layer (REQ-11, ADR-0001).

These run in the default suite, unlike the acceptance gate, because they test code that exists.
They skip when the optional api extra is not installed: the MCP server does not need it.
"""

import time

import pytest

jwt = pytest.importorskip("jwt", reason="install the api extra: pip install -e .[api]")
auth = pytest.importorskip("action_engine_api.auth", reason="install the api extra")

SECRET = "unit-test-secret-long-enough-for-hmac-sha256"


@pytest.fixture(autouse=True)
def secret(monkeypatch):
    monkeypatch.setenv(auth.DEV_SECRET_ENV, SECRET)


def test_delegated_token_records_the_human_initiator():
    token = auth.mint("svc:desk", agent="agent:desktop", initiator="anand@example.test", secret=SECRET)
    ids = auth.authenticate("Bearer %s" % token)
    assert (ids.agent_id, ids.subject_id, ids.initiator_id) == (
        "agent:desktop", "svc:desk", "anand@example.test")
    assert not ids.is_unattended
    assert ids.agent_id != ids.initiator_id, "agent and initiator must stay distinguishable"


def test_service_token_records_unattended_never_blank():
    token = auth.mint("svc:nightly", agent="agent:nightly", service=True, secret=SECRET)
    ids = auth.authenticate("Bearer %s" % token)
    assert ids.initiator_id == auth.UNATTENDED
    assert ids.is_unattended


def test_direct_human_token_is_its_own_initiator():
    token = auth.mint("anand@example.test", secret=SECRET)
    ids = auth.authenticate("Bearer %s" % token)
    assert ids.initiator_id == ids.subject_id == "anand@example.test"


def test_claims_only_headers_are_not_an_input():
    """The spoof case ADR-0001 exists for: identity comes from the token or not at all."""
    token = auth.mint("svc:nightly", agent="agent:nightly", service=True, secret=SECRET)
    claims = auth.verify(token)
    claims_with_spoof = dict(claims, initiator_id="ceo@example.test", act=None)
    assert auth.identities(claims_with_spoof).initiator_id == auth.UNATTENDED


@pytest.mark.parametrize("header,reason", [
    (None, "missing_token"),
    ("", "missing_token"),
    ("Token abc", "malformed_authorization"),
    ("Bearer", "malformed_authorization"),
    ("Bearer not-a-jwt", "malformed_token"),
])
def test_bad_headers_are_typed_refusals(header, reason):
    with pytest.raises(auth.AuthRefusal) as exc:
        auth.authenticate(header)
    assert exc.value.reason == reason
    assert exc.value.payload["refused"] is True


def test_expired_and_wrongly_signed_tokens_are_refused():
    now = int(time.time())
    expired = jwt.encode({"sub": "a", "azp": "a", "aud": auth.AUDIENCE, "iat": now - 60,
                          "exp": now - 1}, SECRET, algorithm="HS256")
    with pytest.raises(auth.AuthRefusal) as exc:
        auth.authenticate("Bearer %s" % expired)
    assert exc.value.reason == "expired_token"

    wrong = auth.mint("svc:desk", secret=SECRET + "-other")
    with pytest.raises(auth.AuthRefusal) as exc:
        auth.authenticate("Bearer %s" % wrong)
    assert exc.value.reason == "bad_signature"


def test_refusal_detail_never_echoes_the_token():
    token = auth.mint("svc:desk", secret=SECRET + "-other")
    with pytest.raises(auth.AuthRefusal) as exc:
        auth.authenticate("Bearer %s" % token)
    assert token not in exc.value.detail and token not in str(exc.value.payload)

