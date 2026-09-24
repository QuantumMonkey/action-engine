"""Test-token issuance for the acceptance suite (ADR-0001 names this as part of the spec).

It lives in the package rather than in tests/ because the acceptance suite is meant to run against a
DEPLOYED service too, where the test tree is not present. Nothing here is imported by app.py.
"""

import os
import time

import jwt

from .auth import AUDIENCE, DEV_SECRET_ENV, mint

# 32+ bytes: shorter HMAC keys are legal but PyJWT warns, and a warning in a green run is noise
# that trains people to ignore warnings.
TEST_SECRET = "acceptance-only-secret-not-for-any-deployment"
DELEGATED_INITIATOR = "anand@anubislab.test"


def ensure_secret() -> str:
    """Use the configured secret if there is one, otherwise install the test secret. Keeps a local
    `pytest -m acceptance` runnable with no setup while never overriding a real deployment."""
    secret = os.environ.get(DEV_SECRET_ENV)
    if not secret:
        secret = TEST_SECRET
        os.environ[DEV_SECRET_ENV] = secret
    return secret


def issue_test_tokens() -> dict:
    """The four tokens the auth model must tell apart, plus the initiator the delegated one carries.

    delegated: an agent acting for a named human -> initiator is that human
    service:   an unattended agent acting for itself -> initiator is "unattended"
    expired:   valid signature, exp in the past
    bad_signature: well-formed, signed with the wrong key
    """
    secret = ensure_secret()
    now = int(time.time())
    expired = jwt.encode(
        {"sub": "svc:reporting", "azp": "agent:nightly", "aud": AUDIENCE,
         "iat": now - 7200, "exp": now - 3600}, secret, algorithm="HS256")
    return {
        "delegated": mint("svc:desk", agent="agent:claude-desktop",
                          initiator=DELEGATED_INITIATOR, secret=secret),
        "delegated_initiator": DELEGATED_INITIATOR,
        "service": mint("svc:nightly", agent="agent:nightly", service=True, secret=secret),
        "expired": expired,
        "bad_signature": mint("svc:desk", agent="agent:claude-desktop",
                              initiator=DELEGATED_INITIATOR, secret=secret + "-wrong"),
    }


def sink_calls(idempotency_key: str) -> int:
    """How many times the third-party sink was called for one key (REQ-14). Raises until the export
    route exists, which keeps test_replay_with_same_key_does_not_act_twice honestly red."""
    raise NotImplementedError("REQ-14 (idempotent export) is not built yet")
