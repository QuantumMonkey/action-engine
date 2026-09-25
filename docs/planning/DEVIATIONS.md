# Deviations log

| Date | Task | Doc amended | Why |
|---|---|---|---|
| 2026-07-17 | TASK-01 | 01-trd.md D-01 (Python 3.12 pinned) | py launcher resolves to 3.13.0 on this machine; stdlib-only server, no 3.12-specific dependency. Pin updated in spirit to "3.12+ via py". |
| 2026-09-24 | chapter order | new docs/planning/chapter-B-http-api.md; REQ-10..REQ-16 added; ADR-0001, ADR-0002 | Chapter B (HTTP surface, delegated identity, idempotent export, Postgres, container, one cloud) is pulled ahead of chapters 2 and 3. Reason is outside the product: four profile claims (API Development, Systems Integration, PostgreSQL, Docker) need a public artifact by 2026-11-20 or they are removed. Chapters 2 and 3 are resequenced, not cancelled; REQ-03..REQ-06 stand unchanged. Acceptance suite written first and left red (tests/acceptance/, marker `acceptance`, deselected by default). |
