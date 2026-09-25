"""The audit trail (REQ-13, ADR-0001). Extends REQ-07's JSONL run-log with the three identities.

The single rule that shapes this module: the row records WHAT was done and WHO decided it, never the
data itself. Arguments are hashed, never stored, so an audit file is safe to hand to an auditor who
is not cleared to read the database it describes. The guards' refusal payloads carry attempted_sql;
that field is deliberately dropped here, because a refused query is exactly the case where the
argument is most likely to contain something sensitive.

Storage is an append-only JSONL file. REQ-15 replaces it with Postgres; everything outside this
module talks to AuditLog, so that is a backend swap rather than a rewrite.
"""

import hashlib
import json
import os
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field

LOG_ENV = "ACTION_ENGINE_AUDIT_LOG"
DEFAULT_LOG = "action-engine-audit.jsonl"


def new_request_id() -> str:
    return uuid.uuid4().hex


def args_hash(args) -> str:
    """sha256 over the canonicalised arguments. Stable across key order and whitespace so two
    identical calls hash alike, and one-way so the row never carries the argument itself."""
    canonical = json.dumps(args or {}, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass
class AuditRow:
    request_id: str
    ts: float
    agent_id: str
    subject_id: str
    initiator_id: str
    route: str
    tool: str = ""
    args_hash: str = ""
    outcome: str = "ok"               # ok | refused | error
    refusal_reason: str = ""
    duration_ms: float = 0.0
    rows_returned: int = 0
    idempotency_key: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


class AuditLog:
    """Append-only JSONL, one row per line, opened per write so a crash cannot lose a buffered row."""

    def __init__(self, path: str = None):
        self.path = path or os.environ.get(LOG_ENV) or DEFAULT_LOG
        self._lock = threading.Lock()

    def append(self, row: AuditRow) -> None:
        line = json.dumps(row.as_dict(), sort_keys=True) + "\n"
        with self._lock:
            with open(self.path, "a", encoding="ascii") as fh:
                fh.write(line)
                fh.flush()
                os.fsync(fh.fileno())

    def _rows(self):
        if not os.path.exists(self.path):
            return
        with open(self.path, "r", encoding="ascii") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    yield json.loads(line)

    def get(self, request_id: str, subject_id: str):
        """One row, and only if it belongs to the caller. A row for another subject reads as absent
        rather than forbidden: whether a request id exists is itself information."""
        for row in self._rows():
            if row["request_id"] == request_id:
                return row if row["subject_id"] == subject_id else None
        return None

    def count(self, subject_id: str) -> int:
        return sum(1 for row in self._rows() if row["subject_id"] == subject_id)


@dataclass
class AuditContext:
    """Carried on request.state. Handlers describe what they did; the middleware times it and writes
    exactly one row, so no handler can forget to log and none can log twice."""

    request_id: str
    identities: object
    route: str
    started: float = field(default_factory=time.perf_counter)
    tool: str = ""
    args: dict = None
    outcome: str = ""
    refusal_reason: str = ""
    rows_returned: int = 0
    idempotency_key: str = ""
    suppressed: bool = False

    def note(self, tool: str, args=None, rows_returned: int = 0) -> None:
        self.tool = tool
        self.args = args or {}
        self.rows_returned = rows_returned

    def refuse(self, reason: str) -> None:
        """Reason only. The refusal's detail and attempted_sql never reach the trail."""
        self.outcome = "refused"
        self.refusal_reason = reason

    def suppress(self) -> None:
        self.suppressed = True

    def to_row(self, status_code: int) -> AuditRow:
        outcome = self.outcome or ("ok" if status_code < 400 else
                                   "refused" if status_code < 500 else "error")
        elapsed = (time.perf_counter() - self.started) * 1000.0
        return AuditRow(
            request_id=self.request_id,
            ts=time.time(),
            agent_id=self.identities.agent_id,
            subject_id=self.identities.subject_id,
            initiator_id=self.identities.initiator_id,
            route=self.route,
            tool=self.tool or self.route,
            args_hash=args_hash(self.args),
            outcome=outcome,
            refusal_reason=self.refusal_reason,
            duration_ms=round(elapsed, 3) or 0.001,
            rows_returned=self.rows_returned,
            idempotency_key=self.idempotency_key,
        )
