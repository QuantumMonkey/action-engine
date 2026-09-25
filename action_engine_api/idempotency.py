"""Idempotency for the one side-effectful route (REQ-14, ADR-0002).

The ambiguity this exists for: a timeout is indistinguishable from a success whose response was
lost, and a retry on that ambiguity is how one export becomes two. So the key is claimed BEFORE the
outbound call and completed after it. A crash in between leaves an in_flight row, which is a fact
worth having rather than a gap to guess about.

Reuse of a key with a different body is a conflict, never a second export: the caller has a bug, and
the safe reading of a caller bug is that somebody is about to act twice by accident.
"""

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone

from .store import connection

TTL_HOURS = 24


class Conflict(Exception):
    def __init__(self, reason: str, detail: str, retry_after: int = 0):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail
        self.retry_after = retry_after


class Replay(Exception):
    """Not an error: the same key and the same body, so the stored response is the right answer."""

    def __init__(self, response: dict):
        super().__init__("replay")
        self.response = response


def fingerprint(body) -> str:
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _now():
    return datetime.now(timezone.utc)


def claim(key: str, subject_id: str, body) -> str:
    """Claim the key, or raise Replay/Conflict. Returns the export id to use."""
    fp = fingerprint(body)
    export_id = uuid.uuid4().hex
    now = _now()
    with connection() as cur:
        cur.execute("DELETE FROM idempotency_keys WHERE expires_at < %s", (now.isoformat(),))
        row = cur.fetchone(
            "SELECT fingerprint, state, response, subject_id FROM idempotency_keys WHERE key = %s", (key,))
        if row is not None:
            stored_fp, state, response, owner = row[0], row[1], row[2], row[3]
            if owner != subject_id:
                # Another subject's key. Say "reused" rather than "belongs to someone else": who
                # else holds a key is not this caller's business.
                raise Conflict("idempotency_key_reused", "this key was used for a different request")
            if stored_fp != fp:
                raise Conflict("idempotency_key_reused",
                               "this key was used for a different request body")
            if state == "in_flight":
                raise Conflict("in_flight", "the first request with this key has not finished", retry_after=2)
            raise Replay(json.loads(response) if isinstance(response, str) else response)
        cur.execute(
            "INSERT INTO idempotency_keys (key, subject_id, fingerprint, state, export_id, expires_at) "
            "VALUES (%s, %s, %s, 'in_flight', %s, %s)",
            (key, subject_id, fp, export_id, (now + timedelta(hours=TTL_HOURS)).isoformat()))
    return export_id


def complete(key: str, response: dict) -> None:
    with connection() as cur:
        cur.execute("UPDATE idempotency_keys SET state = 'done', response = %s WHERE key = %s",
                    (json.dumps(response), key))


def release(key: str) -> None:
    """Drop a claim whose work failed, so an honest retry is not blocked by our own bookkeeping."""
    with connection() as cur:
        cur.execute("DELETE FROM idempotency_keys WHERE key = %s AND state = 'in_flight'", (key,))
