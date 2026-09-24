# ADR-0002: The one side-effectful route is idempotent by key, and the key is the record

- Status: accepted
- Date: 2026-09-24
- Requirements: REQ-14, REQ-15
- Relates to: ADR-0001 (the same row carries who asked)

## Context

Everything in chapter 1 is a read. Chapter B adds exactly one route that acts
on the outside world, /v1/export, which hands a result set to a third-party
sink. The moment a call leaves the process, the network can lie about what
happened: a timeout is indistinguishable from a success whose response was
lost. A retry on that ambiguity is how one export becomes two.

This project's whole claim is that an agent's write access is safe to hand
over. An export that silently double-fires would contradict the claim more
loudly than any README supports it.

## Decision

1. /v1/export requires an `Idempotency-Key` header. No key, no side effect:
   the request is refused with a typed body, not accepted-and-hoped.
2. The key, the request fingerprint (sha256 of the canonicalised body), the
   outcome and the response are stored in Postgres before the outbound call is
   attempted, and the row is completed after it returns.
3. A replay of the same key with the same fingerprint returns the stored
   response, with `Idempotent-Replay: true` on the way out so the caller can
   tell the difference.
4. The same key with a *different* fingerprint is a conflict (409), never a
   second export. Reusing a key for a different request is a caller bug and the
   safe reading is that somebody is about to act twice by accident.
5. Outbound retries use bounded exponential backoff with jitter, and the retry
   budget is per key, not per attempt, so a retry storm cannot outlive the
   request that started it.
6. A key whose row is still in-flight when a replay arrives returns 409 with
   Retry-After rather than waiting: holding a connection open to preserve an
   illusion of synchronicity is how one stuck sink becomes an outage.

Keys expire after 24 hours. Long enough for any honest client retry, short
enough that the table does not become a second database.

## Consequences

Good: one export per decision, provably, with a test that asserts the sink saw
exactly one call for a replayed key. The stored row is also the audit answer to
"did this actually happen", which means REQ-13 and REQ-14 share one write
rather than two subsystems that can disagree.

Costs: Postgres is now on the request path for the export route, so its
availability is the route's availability. Accepted: the alternative is an
in-memory key store that forgets everything on deploy, which would make the
guarantee false exactly when a deploy is rolling.

Rejected alternatives: dedupe by request fingerprint alone (two legitimate
identical exports would be silently collapsed into one, which is a different
kind of wrong); at-least-once with reconciliation afterwards (correct, and it
needs a reconciler nobody is going to write for a portfolio service); trusting
the sink to dedupe (this one cannot, and the claim being made is about what
this service guarantees, not what a vendor might).
