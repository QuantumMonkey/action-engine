# action-engine

Local-first AI with hands: local models + MCP tools, zero data egress.
Chapter 1 artifact: a read-only local-SQLite MCP server.

## sqlite-readonly MCP server (v0.1)

Serves exactly ONE SQLite database, read-only by construction:

- **Path lock**: the db path is resolved via `realpath` at startup and
  re-checked on every call. Swap the file for a symlink and you get
  `{"error": "path_lock_violation"}`.
- **SELECT-only**: enforced three ways at the server (statement screen,
  sqlite3 authorizer, `mode=ro` connection) -- never at the prompt.
  Any write/DDL attempt returns
  `{"error": "read_only_violation", "attempted_sql": "..."}`.

Tools: `list_tables`, `table_schema(table)`, `run_readonly_query(sql)`.

## Run it (Windows, Python 3.12+ via the `py` launcher)

```powershell
py -m pip install mcp pytest
py scripts\make_fixture.py          # regenerates fixtures\sample.db
py -m pytest tests -q               # 16 tests incl. refusal + symlink swap
```

Wire into Claude Code: already in [.mcp.json](.mcp.json) as
`sqlite-readonly`. Open a Claude Code session in this repo and ask it to
list tables or run a SELECT; ask it to run an UPDATE to see the typed
refusal (that refusal is the demo).

## Layout

- `sqlite_mcp_server/` -- server + guards (the whole artifact, ~200 lines)
- `scripts/make_fixture.py` -- deterministic sample.db (customers, orders)
- `tests/` -- pytest suite: SELECT paths, 9 refusal cases, symlink swap
- `docs/planning/` -- PRD / TRD / implementation plan (the constitution)

## Roadmap (docs/planning/05-implementation-plan.md)

Ch1 SQLite MCP server (this) -> Ch2 Ollama loop + Docker sandbox ->
Ch3 offline Excel-to-email workflow + egress proof -> v1.0 assembly.
