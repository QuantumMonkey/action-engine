"""Per-subject rate limiting (REQ-12).

Limits are per SUBJECT, not per agent and not per IP: the subject is whose permissions are being
spent, so it is the thing worth protecting. An agent that holds three tokens for three subjects gets
three budgets, which is correct -- the budget belongs to the account, not to the software.

Sliding window, held in memory. That is honest for a single instance and wrong the moment a second
one starts serving the same subject, because each process would grant a full budget. The scaling
path is a shared counter (the Postgres of REQ-15, or a cache), and the deploy stays single-instance
until that exists rather than pretending the limit holds.
"""

import math
import os
import threading
import time
from collections import defaultdict, deque

LIMIT_ENV = "ACTION_ENGINE_RATE_LIMIT"      # requests allowed per window
WINDOW_ENV = "ACTION_ENGINE_RATE_WINDOW"    # window length in seconds
DEFAULT_LIMIT = 60
DEFAULT_WINDOW = 60.0


def limit() -> int:
    return int(os.environ.get(LIMIT_ENV, DEFAULT_LIMIT))


def window() -> float:
    return float(os.environ.get(WINDOW_ENV, DEFAULT_WINDOW))


def per_minute() -> int:
    """What the limit works out to per minute, which is what /healthz advertises. Reporting the
    window's raw count would mislead whenever the window is not sixty seconds."""
    return int(round(limit() * 60.0 / window()))


class SlidingWindow:
    def __init__(self):
        self._hits = defaultdict(deque)
        self._announced = {}
        self._lock = threading.Lock()

    def check(self, subject: str):
        """Return (allowed, retry_after_seconds, first_refusal_in_this_window).

        The third value exists so the caller can audit the first refusal per subject per window and
        stay quiet for the rest: a client in a retry loop must not be able to turn its own excess
        into unbounded writes on our side.
        """
        now = time.monotonic()
        span = window()
        with self._lock:
            hits = self._hits[subject]
            while hits and now - hits[0] >= span:
                hits.popleft()
            if len(hits) < limit():
                hits.append(now)
                self._announced.pop(subject, None)
                return True, 0, False
            retry_after = max(1, math.ceil(span - (now - hits[0])))
            first = self._announced.get(subject) != len(hits)
            self._announced[subject] = len(hits)
            return False, retry_after, first

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
            self._announced.clear()


limiter = SlidingWindow()
