"""Where an export goes (REQ-14).

One sink exists today: a recording sink that writes a row per call, so "was the third party called
twice?" is answered by the database instead of by inspection. An HTTP sink belongs to whichever
deployment needs one; it is deliberately absent rather than half-written, because an untested
outbound call is exactly the thing this chapter claims to have under control.
"""

from .store import connection


class RecordingSink:
    """Counts its calls. Stands in for a third party in tests and local runs."""

    name = "test"

    def deliver(self, idempotency_key: str, payload: dict) -> dict:
        with connection() as cur:
            cur.execute("INSERT INTO sink_calls (idempotency_key) VALUES (%s)", (idempotency_key,))
        return {"delivered": True, "rows": payload.get("row_count", 0)}


SINKS = {RecordingSink.name: RecordingSink()}


def get(name: str):
    sink = SINKS.get(name)
    if sink is None:
        raise KeyError(name)
    return sink


def call_count(idempotency_key: str) -> int:
    with connection() as cur:
        row = cur.fetchone("SELECT COUNT(*) FROM sink_calls WHERE idempotency_key = %s",
                           (idempotency_key,))
    return int(row[0]) if row else 0
