# Traceability - Action Engine

| REQ | FLOW/ENT | TASK | Status |
|---|---|---|---|
| REQ-01 | FLOW-03, ENT-02 | TASK-01 | open |
| REQ-02 | FLOW-03 | TASK-01 | open |
| REQ-03 | FLOW-01 | TASK-03 | open |
| REQ-04 | FLOW-01 | TASK-04 | open |
| REQ-05 | FLOW-02, ENT-03 | TASK-05 | open |
| REQ-06 | NFR-01 | TASK-06 | open |
| REQ-07 | ENT-01 | TASK-03 | open |
| REQ-08 | -- | TASK-02,04,06,07 | open |
| REQ-09 | -- | TASK-07 | open |
| REQ-10 | chapter B | TASK-B1 | DONE 2026-09-24: generated OpenAPI served at /openapi.json, every route summarised; test_openapi_matches_routes green |
| REQ-11 | chapter B, ADR-0001 | TASK-B2 | DONE 2026-09-24: bearer auth in middleware, typed 401s, three identities from claims only; test_auth_rejects_missing_bad_and_expired green |
| REQ-12 | chapter B | TASK-B3 | DONE 2026-09-24: per-subject sliding window, 429 with Retry-After, first refusal per window audited; acceptance green |
| REQ-13 | chapter B, ADR-0001, extends REQ-07 | TASK-B4 | DONE 2026-09-24: one row per accepted request, three identities from claims, args hashed not stored, append-only JSONL; 4 acceptance tests + 6 unit tests green |
| REQ-14 | chapter B, ADR-0002 | TASK-B5 | DONE 2026-09-24: key claimed before the outbound call, replay returns the stored response, reuse with a different body is 409; 7 unit tests + acceptance green |
| REQ-15 | chapter B, ADR-0002 | TASK-B6 | PARTIAL 2026-09-24: runner + dialect-aware DDL written and proven idempotent on SQLite; the Postgres path is UNVERIFIED (no server available) and its acceptance test stays RED until CI supplies ACTION_ENGINE_TEST_DATABASE_URL |
| REQ-16 | chapter B | TASK-B7 | spec, CI and deploy checked by hand |

No orphan REQs; no TASK without an upstream cite. SCR- unused (uiux waived,
see 00-prd deviation note). OPEN-01 blocks TASK-03 only.
