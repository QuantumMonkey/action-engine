# ARC-1 Chapter 1 - Execution Plan (the first artifact of the whole arc)

Goal: ship the first portfolio unit within one week of starting. Two halves:
a zero-build story asset and a small real build proving the story.

## Half 1 - The write-up (no code)
"I run my dev environment through MCP" - architecture post on the existing
Depthworks setup: Claude Code + skills + MCP servers + beads + graphify as a
lived MCP ecosystem. Include: one architecture diagram (excalidraw-style, this
is the SUMMON trigger case for internal use - mermaid is fine for v1), the
token-tax lesson (single skills not packs), the Zero-Trust skill-audit rules
(from the insights doc S8 - green/red flags), one real gotcha story (the
mojibake incident is genuinely good content).

## Half 2 - The build (small, real, extractable)
Minimal local-SQLite MCP server (FastMCP, Python):
- Tools: list_tables, table_schema, run_readonly_query (SELECT-only guard).
- Sandbox: rejects non-SELECT, path-locked to one .db file passed at startup.
- Test: wire into Claude Code via .mcp.json, query a sample DB live.
- This is the GTM map's own suggested open-source artifact, and the first
  archive-on-completion utility (breadth valve from LED-003 amendment).

## Definition of done (completion-gate applies)
- [ ] SQLite MCP server runs; SELECT-only guard demonstrated (attempt an
      UPDATE, show the refusal in the post - security IS the content)
- [ ] Post drafted, one diagram, one gotcha, one demo GIF/screenshot
- [ ] Repo tagged v0.1, README a stranger could run
- [ ] Published: LinkedIn (primary, B2B audience) + repo link; X secondary
- [ ] 10 manual outreaches referencing the post within 7 days (LED-004
      gate metric starts counting HERE)
- [ ] bd issue closed with the post URL as the reason

## Explicit non-goals for chapter 1
Ollama integration (ch2), Docker sandboxing (ch2), any second MCP server.
One chapter, one artifact, then stop and publish.
