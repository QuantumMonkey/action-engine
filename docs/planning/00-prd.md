# PRD - Action Engine (ARC-1)

Pack deviation (recorded): condensed 6-doc pack -> 4 files. 02-uiux.md WAIVED
(surface is CLI + Claude Code MCP client + demo GIFs; no SCR ids). 03-appflow
and 04-schema absorbed into 01-trd.md (FLOW-nn, ENT-nn live there).
Because: portfolio/learning system, token budget; quality kept via full ID
traceability. Rejected: full 6 docs -- ceremony exceeds surface area.

## Problem
Knowledge workers are the glue between local tools (spreadsheets, DBs, email),
doing manual copy-paste that cloud assistants cannot take over because the
data may not leave the machine. Nothing on this machine can read a local file,
reason about it, and act -- without egress.

## Users
- U1 (primary): the operator (portfolio author). Success = chapters shipped.
- U2 (audience): LED-004 buyer/hiring evaluator viewing demos and posts.
  Success = "I understood it, I believe it ran, I can imagine it on my data."

## Requirements
| ID | Requirement | mvp | Chapter |
|---|---|---|---|
| REQ-01 | Local-SQLite MCP server: list_tables, table_schema, run_readonly_query; SELECT-only enforced at the server, not the prompt | mvp | 1 |
| REQ-02 | Server is path-locked to one .db passed at startup; any write/DDL attempt returns a typed refusal (demoable) | mvp | 1 |
| REQ-03 | Local model loop: Ollama-served SLM plans and calls MCP tools through a minimal client harness (no cloud LLM in the loop) | mvp | 2 |
| REQ-04 | Sandboxed executor: side-effectful tools run in a Docker container with an explicit allowlist mount; container has no network | mvp | 2 |
| REQ-05 | Flagship workflow: read local .xlsx -> transform per rules -> write .eml/.md email draft, end-to-end offline | mvp | 3 |
| REQ-06 | Egress proof: harness that runs any workflow while capturing network activity and asserts zero non-localhost connections | mvp | 3 |
| REQ-07 | Every action appended to a local JSONL run-log (tool, args-hash, duration, outcome) | mvp | 2 |
| REQ-08 | Each chapter ships: tagged release, README a stranger can run, demo GIF, published post | mvp | all |
| REQ-09 | Extract SQLite MCP server as standalone repo, archived on completion | -- | A |

## Non-goals (binding, from 00-scope)
Multi-user, cloud deploy, packaging/monetization, Linux parity (notes only),
more than 3 workflows, GUI.

## Success metrics
3 workflows pass REQ-06 egress proof; 4 posts published; v1.0 tagged;
outreach clock started (chapter-1-plan.md DoD).

## OPEN items
- OPEN-01 RESOLVED 2026-07-12: GPU = RTX 3080 Laptop, 8GB VRAM.
  Model tier CONFIRMED: qwen2.5:7b-instruct Q4_K_M (~4.7GB weights) fully
  GPU-offloaded with room for KV cache. Constraints now binding in TRD:
  num_ctx <= 8192 (KV cache eats the remaining VRAM); ONE model resident at
  a time (Ollama swaps embed/gen models -- fine, do not fight it); llama3.1:8b
  Q4 is the approved fallback if qwen tool-calling disappoints in TASK-03.
