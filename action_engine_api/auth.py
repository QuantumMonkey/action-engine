"""Bearer-token verification and the three identities (REQ-11, REQ-13, ADR-0001).

The rule this module exists to enforce: an identity that did not arrive inside a signed token does
not exist. Headers are never consulted. A caller can send X-Initiator-Id: ceo@example.com and it
changes nothing, which is the point -- the audit row's whole value is that it cannot be authored by
the party it describes.

Signing: HS256 against a shared secret is the development and test path. Production verifies against
a published key set (JWKS), cached, with the last known good set as the fallback. That path is not
built yet; ACTION_ENGINE_JWT_JWKS_URL is read here so the switch is one deploy, not one refactor.
"""

import os
import time
from dataclasses import dataclass

import jwt

DEV_SECRET_ENV = "ACTION_ENGINE_JWT_SECRET"
JWKS_ENV = "ACTION_ENGINE_JWT_JWKS_URL"
AUDIENCE = "action-engine"
UNATTENDED = "unattended"


class AuthRefusal(Exception):
    """A typed refusal, never an exception on the wire (NFR-01).

    reason is machine-readable and stable; detail is for a human reading a log and never echoes the
    token or any part of it.
    """

    def __init__(self, reason: str, detail: str):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail

    @property
    def payload(self) -> dict:
        return {"refused": True, "reason": self.reason, "detail": self.detail}


@dataclass(frozen=True)
class Identities:
    """Who acted, whose permissions applied, and who decided (ADR-0001).

    initiator_id is never blank: a token with no human behind it records UNATTENDED, so an auditor
    can count unattended traffic instead of guessing whether a blank field is a bug.
    """

    agent_id: str
    subject_id: str
    initiator_id: str

    @property
    def is_unattended(self) -> bool:
        return self.initiator_id == UNATTENDED


def _secret() -> str:
    secret = os.environ.get(DEV_SECRET_ENV)
    if not secret:
        if os.environ.get(JWKS_ENV):
            raise AuthRefusal("auth_not_configured", "JWKS verification is not implemented yet")
        raise AuthRefusal("auth_not_configured", "no signing key configured for this deployment")
    return secret


def bearer_from_header(header_value) -> str:
    """Pull the token out of an Authorization header, refusing anything that is not a bearer."""
    if not header_value:
        raise AuthRefusal("missing_token", "Authorization header absent")
    parts = header_value.split()
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise AuthRefusal("malformed_authorization", "expected 'Authorization: Bearer <token>'")
    return parts[1]


def verify(token: str) -> dict:
    """Verify signature, expiry and audience. Every failure mode lands as a typed refusal."""
    try:
        return jwt.decode(token, _secret(), algorithms=["HS256"], audience=AUDIENCE)
    except jwt.ExpiredSignatureError:
        raise AuthRefusal("expired_token", "the token's exp has passed")
    except jwt.InvalidAudienceError:
        raise AuthRefusal("wrong_audience", "token was not issued for this service")
    except jwt.InvalidSignatureError:
        raise AuthRefusal("bad_signature", "token signature does not verify")
    except jwt.DecodeError:
        raise AuthRefusal("malformed_token", "token is not a well-formed JWT")
    except jwt.InvalidTokenError as exc:  # anything PyJWT adds later still lands typed
        raise AuthRefusal("invalid_token", type(exc).__name__)


def identities(claims: dict) -> Identities:
    """Map verified claims onto the three identities. Claims only; headers are not an input here."""
    subject = claims.get("sub")
    agent = claims.get("azp") or subject
    if not subject or not agent:
        raise AuthRefusal("incomplete_token", "token carries no subject")

    delegation = claims.get("act") or {}
    delegated_human = delegation.get("sub") if isinstance(delegation, dict) else None
    if delegated_human:
        initiator = delegated_human           # a human delegated this to an agent
    elif claims.get("typ") == "service":
        initiator = UNATTENDED                # nobody is behind it, and the row says so
    else:
        initiator = subject                   # a person calling directly is their own initiator
    return Identities(agent_id=agent, subject_id=subject, initiator_id=initiator)


def authenticate(header_value) -> Identities:
    """Header in, three identities out, or a typed refusal. The only entry point callers need."""
    return identities(verify(bearer_from_header(header_value)))


def mint(subject: str, agent: str = None, initiator: str = None, service: bool = False,
         ttl_seconds: int = 900, secret: str = None, audience: str = AUDIENCE) -> str:
    """Issue a token. Used by the test helper and by local development; a real deployment gets its
    tokens from an identity provider, and this function is not a substitute for one."""
    now = int(time.time())
    claims = {"sub": subject, "azp": agent or subject, "aud": audience, "iat": now,
              "exp": now + ttl_seconds}
    if service:
        claims["typ"] = "service"
    if initiator:
        claims["act"] = {"sub": initiator}
    return jwt.encode(claims, secret or _secret(), algorithm="HS256")
