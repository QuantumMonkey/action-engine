# sqlite-readonly: an MCP server that cannot write

One MCP server, one SQLite file, read-only by construction. The model gets
three tools -- `list_tables`, `table_schema(table)`, `run_readonly_query(sql)`
-- and every write attempt comes back as a typed refusal from the server
process, not as a rule in a prompt:

```json
{"error": "read_only_violation",
 "detail": "only SELECT queries are allowed, got 'UPDATE'",
 "attempted_sql": "UPDATE customers SET name = 'x'"}
```

This is chapter 1 of `action-engine` (local-first agents with hands). The
server is the whole shipped artifact; the rest of the repo is planning docs
for chapters that are not built yet. `sqlite_mcp_server/` is about 200 lines.

## How "cannot" is enforced

Three independent layers, all in the server process, none in the prompt:

1. **Statement screen** -- `screen_select_only` in
   `sqlite_mcp_server/guards.py`: comments stripped, exactly one statement,
   first token must be `SELECT` or `WITH`. The screened text is the text that
   runs, so a fake comment cannot smuggle a second statement past it.
2. **sqlite3 authorizer** -- `_authorizer`: a deny-by-default callback
   registered on every connection. Only `SQLITE_SELECT`, `SQLITE_READ` and
   `SQLITE_FUNCTION` are allowed. This is what stops `WITH ... DELETE`,
   `ATTACH`, `PRAGMA` and `load_extension`, none of which the screen can see.
3. **Read-only connection** -- `open_readonly`: a `mode=ro` URI. If the first
   two layers were both wrong, SQLite itself refuses the write.

Plus a **path lock** (`PathLock`): the db path is resolved with `realpath` at
startup and re-resolved on every call. Replace the served file with a symlink
(or swap a parent directory for one) and the next call returns
`{"error": "path_lock_violation"}` instead of whatever is now at the path.

## What it does not do

- It does not detect a file replaced **in place** at the same real path. The
  lock is a path-resolution check, not a content or inode check. Someone with
  write access to the file can change what you read; they cannot use this
  server to do it.
- It does not restrict reads. Everything in the file is readable by the
  model, `sqlite_master` included. Do not point it at a database with secrets
  in it.
- It does not bound CPU or time. A slow `SELECT` is a slow `SELECT`. Rows are
  capped at 200 per call (`max_rows` in `run_query`); there is no statement
  timeout.
- It does not run `PRAGMA` statements or `pragma_*` table-valued functions,
  even read-only ones; the authorizer denies `SQLITE_PRAGMA` outright. Use
  `table_schema` for column names and the `CREATE TABLE` text.
- It does not authenticate anything. It is stdio only: one process per host,
  no network listener.
- It is not a sandbox for the host or the model. It bounds one tool.
- There is a window between the path check and the connection open (two
  adjacent lines in `open_readonly`). A swap timed inside it is served once.

## Known issues (v0.1)

- `WITH RECURSIVE` queries are refused with `read_only_violation`. The
  authorizer allow-list has `31` (`SQLITE_FUNCTION`) where `33`
  (`SQLITE_RECURSIVE`) was meant. `tests/test_guards.py` carries this as a
  strict `xfail` so a fix cannot land unnoticed.

## Install

Python 3.10+ and the official MCP Python SDK; both SDK majors (1.x `FastMCP`
and 2.x `MCPServer`) work.

Windows, with the `py` launcher (`python` may be a Store stub that does
nothing):

```powershell
git clone https://github.com/QuantumMonkey/action-engine
cd action-engine
py -m pip install -e ".[test]"
py scripts\make_fixture.py           # creates fixtures\sample.db (generated, not committed)
py -m pytest tests -q                # guards + real MCP stdio round-trips
```

macOS / Linux:

```sh
git clone https://github.com/QuantumMonkey/action-engine
cd action-engine
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[test]"
python scripts/make_fixture.py
python -m pytest tests -q
```

`pip install -e .` is optional: `pip install "mcp<3" pytest` and running from
the repo root works the same. Whichever way, install into the interpreter
your MCP host will launch, or the host starts a server that cannot import
the SDK.

## Use it from an MCP host

The server takes one argument, the database path, and speaks MCP over stdio:

```
py -m sqlite_mcp_server.server fixtures\sample.db
```

It prints `sqlite-readonly: locked to <absolute path>` on stderr at startup
so a host's MCP log shows which file was locked.

**Claude Code**: `.mcp.json` in this repo already wires it as
`sqlite-readonly` (command `py`; on macOS/Linux change that to `python3`).
Open a Claude Code session in the repo, ask it to list the tables, then ask
it to run an `UPDATE`. The refusal is the demo.

**Claude Desktop**: after `pip install -e .` the module resolves from any
directory. Add to `claude_desktop_config.json`, absolute paths throughout:

```json
{
  "mcpServers": {
    "sqlite-readonly": {
      "command": "py",
      "args": ["-m", "sqlite_mcp_server.server", "C:\\data\\your.db"]
    }
  }
}
```

On macOS/Linux point `command` at the interpreter you installed into, for
example `/home/you/action-engine/.venv/bin/python`.

**Any other host**: it is plain MCP over stdio. `tests/test_server.py` is a
complete client-side example with the official SDK.

## Try to break it

`tests/test_guards.py` and `tests/test_server.py` hold the attempts made so
far: `INSERT`/`UPDATE`/`DELETE`/`DROP`/`CREATE`/`ALTER`, `ATTACH`, `PRAGMA`
writes, `VACUUM INTO`, multi-statement strings, comment and quoting tricks,
CTE-wrapped writes, `load_extension`, odd characters in the db path, and the
symlink swap under a live session. If you find a write path, open an issue
with the SQL.

## Layout

- `sqlite_mcp_server/server.py` -- the three tools and the MCP wiring
- `sqlite_mcp_server/guards.py` -- path lock, statement screen, authorizer,
  read-only connection
- `scripts/make_fixture.py` -- deterministic sample db (customers, orders).
  Fixtures are generated; `*.db` is gitignored.
- `tests/` -- guard tests (no SDK needed) and stdio round-trip tests (SDK
  needed)
- `docs/planning/`, `adrs/`, `.beads/` -- the author's planning pack and
  task tracker for the wider project; not needed to run the server

## Roadmap

Chapters 2 and 3 (local model loop, sandboxed execution, offline workflows)
are planned in `docs/planning/` and not built. This server stands on its own
as v0.1.

## License

MIT. See `LICENSE`.
