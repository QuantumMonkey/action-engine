# Implementation Plan - Action Engine

Executor contract (Sonnet/Gemini): docs are the constitution; deviation ->
amend doc first, log in DEVIATIONS.md. One TASK per session. Claim/close in bd.
Context manifest = the ONLY files to read before starting (token discipline).

| ID | Task (chapter) | Cites | Context manifest | Done-criteria / verify |
|---|---|---|---|---|
| TASK-01 | SQLite MCP server + fixture + refusal tests (ch1) [bd action-engine-am8] | REQ-01,02 ENT-02 D-02,08 | this file, 01-trd.md S-Security, chapter-1-plan.md | pytest green incl. symlink + UPDATE refusal; wired into Claude Code .mcp.json and queried live; v0.1 |
| TASK-02 | Chapter-1 post: MCP ecosystem write-up + server demo (ch1) | REQ-08 | chapter-1-plan.md only | Post published (LinkedIn primary); GIF; 10 outreaches started |
| TASK-03 | Ollama client harness: FLOW-01 loop, run-log (ch2) | REQ-03,07 FLOW-01 ENT-01 D-03,07 OPEN-01 | 01-trd.md FLOW-01+ENT, TASK-01 server README | 3-step tool chain completes on local model; malformed-call retry test; runlog entries verified |
| TASK-04 | Docker sandbox executor (ch2) | REQ-04 D-04 | 01-trd.md D-04, harness entrypoint | destructive command inside container provably cannot touch host or net (test + filmed); v0.2 + ch2 post |
| TASK-05 | Excel-to-email workflow: FLOW-02 (ch3) | REQ-05 FLOW-02 ENT-03 D-05 | 01-trd.md FLOW-02, config schema | wifi-off end-to-end run; bad-input fail-fast test |
| TASK-06 | Egress-proof harness (ch3) | REQ-06 NFR-01 D-06 | 01-trd.md NFR-01 | asserts zero non-localhost conns during TASK-05 run; becomes standard check; v0.3 + ch3 post |
| TASK-07 | Assembly: v1.0, extract+archive sqlite-mcp-server repo, birth post (A) | REQ-08,09 | 00-prd.md metrics, BUILD-ARCS.md | standalone repo archived "stable, done"; assembly post; LED-003 chapter marks updated in ledger |

Sequencing: strict order. TASK-02 may run parallel to TASK-03 only if TASK-01
is closed (W2: artifact before next chapter's build).
Verification standard: completion-gate checklist before any "done"; /verify
on TASK-04/05 (runtime surfaces).
