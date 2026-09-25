# Chapter B - The remote surface: an HTTP API with an attributable audit trail

Status: spec, written 2026-09-24. Nothing here is built yet.
Due: 2026-10-06 (box 1 in money-map/sends/POSITIONING-AND-90-DAY-MAP.md).

## Why this chapter exists, and why it jumps the queue

The planning pack runs chapters 1 -> 2 (local model loop, sandboxed executor)
-> 3 (flagship offline workflow). This chapter is pulled ahead of chapter 2 for
a reason outside the product: the profile claims API Development, Systems
Integration, PostgreSQL and Docker, and those claims need a public artifact by
2026-11-20 or they come off. Recorded in DEVIATIONS.md; chapters 2 and 3 are
not cancelled, only resequenced.

The second reason is that the market moved. MCP added OAuth 2.1 on its HTTP
transport in January 2026, and enterprise-managed authorization arrived in
August 2026. The open question in practice is not "can you log a tool call" --
several gateways do that already -- it is **whether the identity on the log
entry can be trusted**: who initiated the task, which agent acted, and under
whose permissions. That is what this chapter builds.

## One-liner

A small HTTP surface in front of the read-only SQLite MCP server, where every
answer carries an attributable record of who asked, what ran, and what was
refused.

## Requirements (continuing the pack's numbering)

| REQ | Statement | Chapter |
|---|---|---|
| REQ-10 | HTTP API serves the three existing tools as routes, documented by an OpenAPI document generated from the code, not hand-written | B |
| REQ-11 | Every route except /healthz requires a bearer token; a missing, malformed or expired token returns 401 with a typed refusal body, never a 500 | B |
| REQ-12 | Every request is rate limited per subject; over the limit returns 429 with a Retry-After header and the counter resets on its own | B |
| REQ-13 | Each accepted request writes one audit row binding three identities: the agent (client id), the subject whose permissions were used, and the human initiator recorded at token-issue time, plus tool, args-hash, outcome and duration. Extends REQ-07's run-log rather than replacing it | B |
| REQ-14 | One outbound third-party call is made with retries and an idempotency key; a replayed request with the same key returns the first result and does not act twice | B |
| REQ-15 | State lives in PostgreSQL with migrations that run from empty to current in one command; SQLite stays the served database, Postgres holds audit rows and idempotency keys | B |
| REQ-16 | The service ships as a published container image and runs on one cloud at a URL a stranger can open, with CI blocking a red build | B |

Non-functional, carried from the pack: NFR-01 (a refusal is typed, never an
exception on the wire) applies to every route added here.

## API surface (v0)

| Method | Route | Purpose | Auth |
|---|---|---|---|
| GET | /healthz | liveness; no auth, no audit row | none |
| GET | /openapi.json | the generated document (REQ-10) | none |
| GET | /v1/tables | list_tables | bearer |
| GET | /v1/tables/{name}/schema | table_schema | bearer |
| POST | /v1/query | run_readonly_query, body {sql, params} | bearer |
| POST | /v1/export | the one side-effectful route: hands a result set to a third-party sink, requires Idempotency-Key (REQ-14) | bearer |
| GET | /v1/audit/{request_id} | the audit row for one request, for the caller's own subject only | bearer |

Refusal body, identical in shape to the MCP tools' typed refusals:
`{"refused": true, "reason": "<machine-readable>", "detail": "<human>"}`.

## The three identities (REQ-13)

Every audit row carries all three, because an entry naming only the agent is
not attributable to anyone who can be asked about it:

| Field | Meaning | Source |
|---|---|---|
| agent_id | the client software making the call | token claim `azp` |
| subject_id | the account whose permissions authorised it | token claim `sub` |
| initiator_id | the human who decided this should happen | token claim `act.sub` when the token is delegated; equal to subject_id for a direct human call; explicitly `"unattended"` for a service token |

A service token with no initiator is allowed, but it is recorded as
`"unattended"` rather than left blank, so an auditor can count how much of the
traffic had nobody behind it. Client-declared identity headers are ignored:
if it is not in the signed token, it does not reach the audit row.

## Audit row (extends the REQ-07 JSONL run-log)

request_id, ts, agent_id, subject_id, initiator_id, route, tool, args_hash
(sha256 of the canonicalised args, never the args), outcome
(ok | refused | error), refusal_reason, duration_ms, rows_returned,
idempotency_key.
Rows are append-only. Hash chaining is out of scope here and belongs to the
compliance-rag audit store; this chapter must not grow that far.

Two decisions REQ-13 forces, recorded here before the code (2026-09-24):

1. **A rejected request writes no audit row.** The row's fields are the three
   identities, and a request that failed authentication has none that can be
   trusted. Writing "unknown did something" would make the trail longer and
   less true. Failed auth belongs in an access log, which is a different
   artifact with a different retention rule and is not part of this chapter.
2. **Audit reads are not themselves audited.** /v1/audit/* touches the log,
   not the served database, so a read of one's own trail is not an action the
   trail exists to record. Self-referential rows also make any count
   untestable. If read-access logging is ever required, it goes to the same
   separate access log as decision 1.

Storage in this chapter is an append-only JSONL file, which is REQ-07's
run-log extended with the identity fields rather than a second subsystem.
REQ-15 moves it to Postgres; the reader is deliberately a small interface so
that move is a backend swap, not a rewrite.

## Acceptance criteria -> tests

Every line below is one test in tests/acceptance/test_http_api.py. The box is
done when all of them pass, not when the code looks finished.

| # | Criterion | Test |
|---|---|---|
| 1 | The OpenAPI document lists exactly the routes that exist, and every route has a summary | test_openapi_matches_routes |
| 2 | No token, bad signature, and expired token each return 401 with a typed refusal body | test_auth_rejects_missing_bad_and_expired |
| 3 | /healthz answers without auth and writes no audit row | test_healthz_is_open_and_unaudited |
| 4 | Over the limit returns 429 with Retry-After, and the window resets | test_rate_limit_returns_429_then_recovers |
| 5 | A write attempt through /v1/query is refused by the existing guards, with the refusal recorded | test_write_attempt_is_refused_and_audited |
| 6 | An accepted call writes exactly one audit row carrying all three identities | test_audit_row_binds_three_identities |
| 7 | A delegated token records the human initiator; a service token records "unattended"; a spoofed header is ignored | test_initiator_from_token_not_from_header |
| 8 | A replayed Idempotency-Key returns the first result and performs no second side effect | test_replay_with_same_key_does_not_act_twice |
| 9 | Migrations run from an empty database to current in one command, twice in a row, without error | test_migrations_are_idempotent |

Criteria 10 and 11 are checked by CI and by hand, not by pytest: the published
image serves /openapi.json on a clean machine, and the deployed URL answers
/healthz from outside the network it was built on.

## Definition of done (completion-gate applies)

- [ ] All nine acceptance tests pass; `pytest` and `pytest -m acceptance` are
      both green.
- [ ] CI runs both on every push; a red build blocks the merge.
- [ ] Image published; `docker run` on a clean machine serves /openapi.json.
- [ ] Deployed to ONE cloud (decide AWS or Azure, ADR-0003); the URL answers
      /healthz for a stranger.
- [ ] README states measured median latency and the test count, as measured.
- [ ] ADR-0001 and ADR-0002 merged; DEVIATIONS.md records the resequencing.
- [ ] The Tuesday and Friday posts of that fortnight carry the URL and the two
      numbers.

## Out of scope (binding)

Write access of any kind to the served SQLite database. Multi-tenant
onboarding. A UI. Hash-chained or tamper-evident audit storage (that is
compliance-rag's job). Agent-to-agent delegation chains beyond one hop.
