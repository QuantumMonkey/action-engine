# TRD - Action Engine (absorbs appflow FLOW-nn and schema ENT-nn)

## Stack (pinned; deviate only via ADR)
| Layer | Choice | D-nn |
|---|---|---|
| Language | Python 3.12 (py launcher; NEVER bare python -- Store stub) | D-01 |
| MCP | FastMCP (official python SDK server helper) | D-02 |
| Local LLM | Ollama; default model qwen2.5:7b-instruct (ASSUMED, OPEN-01) | D-03 |
| Sandbox | Docker Desktop (Windows), python:3.12-slim, --network none | D-04 |
| Excel | openpyxl (read-only mode) | D-05 |
| Tests | pytest; egress proof via psutil connection snapshot + Sysmon note | D-06 |

Decision log:
- D-02: FastMCP | Because: least boilerplate, spec-current | Rejected: raw
  JSON-RPC -- teaches plumbing, wastes chapters.
- D-03: Ollama | Because: one-command local serving, OpenAI-compat endpoint |
  Rejected: llama.cpp direct -- more control, more yak.
- D-04: --network none container | Because: egress-by-construction beats
  egress-by-promise; it IS the content | Rejected: firewall rules -- fragile,
  not portable to a reader's machine.
- D-07: client harness is OUR minimal loop (~150 lines) | Because: the loop is
  the teachable artifact | Rejected: LangChain agent -- hides exactly what the
  posts must show.

## NFRs
- NFR-01 Offline: zero non-localhost sockets during workflow execution
  (verified by REQ-06 harness, run in CI-style script).
- NFR-02 Windows-native: PS 5.1-safe scripts, ASCII-only, py launcher.
- NFR-03 Reproducible: fresh clone -> README steps -> demo in <=15 min.
- NFR-04 Honest logging: run-log records failures verbatim (REQ-07).

## Flows
- FLOW-01 Tool loop: user goal -> harness builds prompt w/ tool schemas ->
  Ollama /api/chat -> tool_call parsed -> MCP server invoked -> result
  appended -> loop until final answer or max 8 turns -> run-log entry.
  Failure arms: malformed tool call (1 retry w/ error echo), tool refusal
  (surfaced, not retried), turn cap (abort, log PARTIAL).
- FLOW-02 Excel-to-email: load .xlsx (openpyxl RO) -> validate expected
  columns (fail fast, named error) -> transform rules from a .yaml config ->
  render Jinja2 email template -> write draft.eml + summary.md -> egress
  assert -> run-log.
- FLOW-03 Refusal demo: UPDATE attempt -> server returns
  {error: "read_only_violation", attempted_sql} -> shown in post.

## Data (ENT)
- ENT-01 runlog.jsonl: {ts, workflow, tool, args_sha256, duration_ms,
  outcome: ok|refused|error|partial, detail}. Append-only, gitignored.
- ENT-02 sample.db (committed fixture): tables customers, orders -- small,
  fake, regenerable by scripts/make_fixture.py.
- ENT-03 workflow config .yaml: {input_glob, required_columns[], transforms[],
  template}. Schema documented in README; additive-only evolution.

## Security
Server path-lock resolved via os.path.realpath prefix check (D-08: symlink
traversal is the classic hole; test for it). No secrets exist in this project.
