# ARC-1: Action Engine - Scope, Chapters, Measurement

Forward-looking approximation (2026-07-12). Direction-setter, not law; chapters
are theses to prove or amend. Deviations -> DEVIATIONS.md. Ledger: LED-003.

## One-liner
An AI with hands: local-first assistant that reasons with local models and
executes real actions on your machine through MCP - no cloud, no data egress.

## GTM tie (LED-004 compliance/consulting wedge)
Demo sentence for a buyer: "It removed the human copy-paster between your
tools, and your data never left the building."

## Architecture (approximate)
Ollama (local SLM, e.g. Llama-3-8B class) -> MCP client loop -> FastMCP
servers (filesystem, SQLite, email-draft) -> Docker-sandboxed execution.
Windows-native first (it is the machine we own); Linux notes as content bonus.

## Chapters (strictly serialized; artifact = tagged release + post)
| Ch | Build | Done-when (measurement) |
|---|---|---|
| 1 | No new build: architecture write-up of the existing Depthworks MCP/skill ecosystem + minimal local-SQLite MCP server as the demo | Post published; SQLite MCP server runs against a sample DB from Claude Code; repo tagged v0.1 |
| 2 | Sandboxed execution: Docker-contained tool runner + Ollama backend wired via MCP | A destructive-looking action is provably contained; local model completes a 3-step tool chain; v0.2 |
| 3 | Real workflow: read local Excel -> transform -> draft email, fully offline | Workflow runs end-to-end with wifi disabled (the money demo/GIF); v0.3 |
| A | Assembly/birth post: what the three chapters add up to; extract + ARCHIVE the SQLite MCP server as a standalone frozen utility | Utility repo archived "stable, done"; assembly post published; v1.0 |

## System done-criteria
3 distinct real workflows end-to-end on local hardware, zero network calls
during execution (verified, not claimed), each documented with a demo GIF.

## Out of scope (binding)
Multi-user, cloud deploy, product packaging, any monetization feature.
This is a portfolio system (LED-003), not a product (that would be LED-004+).

## Blog theses (per chapter)
1. "Your AI does not need the cloud to have hands." (ch1)
2. "MCP is AI's USB moment - one protocol, every tool." (ch1)
3. "I have run my entire dev environment through MCP for months - what breaks and what holds." (ch1, zero-build)
4. "Sandbox first: letting an LLM touch your filesystem without trusting it." (ch2)
5. "An 8B local model beats a cloud giant at YOUR workflow - when the tools do the heavy lifting." (ch2/3)
6. "Airplane-mode automation: the Excel-to-email pipeline that never phones home." (ch3)
