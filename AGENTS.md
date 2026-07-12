# Agent Instructions (Antigravity / Gemini and other non-Claude agents)

Copied into each project by init-project.ps1. Project specifics go below the rules.

## Model Routing (Gemini)
- Gemini Pro: planning and implementation.
- Gemini Flash: grunt work -- search, exploration, parallel subagents.
- Role split with Claude Code: Claude (Opus+Sonnet) sets direction and establishes the pattern (conventions, key files, test command, done-criteria) in a handoff doc; Antigravity takes over AFTER that for grunt implementation and directed research, executing against the doc. Never set direction unilaterally; novel or pattern-setting code stays with Claude. Do not duplicate work across both.

## Grounded APIs (mandatory -- never be confidently wrong)
- Before using any library/framework API you are not certain of, resolve it against live documentation first: use the Context7 MCP server (must be configured in this IDE; flag it if missing) or fetch the official docs. Never write framework code from memory alone.
- If the docs cannot be reached, say so explicitly and mark the code as unverified against current API.

## Skill/Context Discipline (mandatory)
- Progressive disclosure: load instructions, docs, and files only when the task actually needs them; never preload packs, whole directories, or "just in case" context.
- Anything reusable you are told to keep: write it as a small plain-markdown instruction file with ONE tight trigger description line; the description is the only part that is always loaded, so it carries the whole matching burden.
- Prefer a deterministic script over prose instructions wherever the behavior can be scripted; prose is only for judgment calls.
- Write such files like onboarding docs for a new hire: self-contained, exact paths, exact commands, no context assumed.

## Idea Evaluation (cross-tool)
- Any new product/business/side-project idea goes through the idea-killer
  protocol at `D:\Claude setups\payload\skills\idea-killer\SKILL.md` before any
  design or build work. Read it and execute it EXACTLY; its Execution Notes are
  binding on every model. History and priors live in `D:\Claude setups\ledger\`.

## Task Tracking (beads) -- single source of truth across ALL tools
- All task tracking via `bd`. Run `bd prime` for workflow context.
- `bd ready` -> `bd update <id> --claim` -> work -> `bd close <id> --reason "..."`.
- Conservative git policy: no commits, pushes, or dolt sync unless explicitly asked. Report changed files and proposed commands at handoff.

## Reasoning Protocol
- Before labeling something a gap or bug: check for intent first; if unconfirmed, ask -- don't prescribe.
- State observation and inference separately; verify assumptions with a tool call before acting on them.
- Never report a task done on generated code alone -- run the test/build/app, or state that grounding wasn't possible.

## Checklist Gates (read the file when its gate applies)
Located in `~\.claude\checklists\` (or the workspace `checklists\` folder):
- Before writing code for a task -> `pre-implementation.md`
- On any failure/error -> `debugging.md` (no fix before a confirmed root cause)
- Before claiming done/fixed/working -> `completion-gate.md`
- Medium-stakes decisions -> `decision-lenses.md`

## Non-Interactive Shell
Always use non-interactive flags: `cp -f`, `mv -f`, `rm -f`, `rm -rf`; `ssh/scp -o BatchMode=yes`; `apt-get -y`.

---

## Project Specifics

_Build & test commands, architecture overview, conventions -- fill in per project._

<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:6cd5cc61 -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

**Architecture in one line:** issues live in a local Dolt DB; sync uses `refs/dolt/data` on your git remote; `.beads/issues.jsonl` is a passive export. See https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md for details and anti-patterns.

## Agent Context Profiles

The managed Beads block is task-tracking guidance, not permission to override repository, user, or orchestrator instructions.

- **Conservative (default)**: Use `bd` for task tracking. Do not run git commits, git pushes, or Dolt remote sync unless explicitly asked. At handoff, report changed files, validation, and suggested next commands.
- **Minimal**: Keep tool instruction files as pointers to `bd prime`; use the same conservative git policy unless active instructions say otherwise.
- **Team-maintainer**: Only when the repository explicitly opts in, agents may close beads, run quality gates, commit, and push as part of session close. A current "do not commit" or "do not push" instruction still wins.

## Session Completion

This protocol applies when ending a Beads implementation workflow. It is subordinate to explicit user, repository, and orchestrator instructions.

1. **File issues for remaining work** - Create beads for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **Handle git/sync by active profile**:
   ```bash
   # Conservative/minimal/default: report status and proposed commands; wait for approval.
   git status

   # Team-maintainer opt-in only, unless current instructions forbid it:
   git pull --rebase
   git push
   git status
   ```
5. **Hand off** - Summarize changes, validation, issue status, and any blocked sync/commit/push step

**Critical rules:**
- Explicit user or orchestrator instructions override this Beads block.
- Do not commit or push without clear authority from the active profile or the current user request.
- If a required sync or push is blocked, stop and report the exact command and error.
<!-- END BEADS INTEGRATION -->

<!-- BEGIN BEADS CODEX SETUP: generated by bd setup codex -->
## Beads Issue Tracker

Use Beads (`bd`) for durable task tracking in repositories that include it. Use the `beads` skill at `.agents/skills/beads/SKILL.md` (project install) or `~/.agents/skills/beads/SKILL.md` (global install) for Beads workflow guidance, then use the `bd` CLI for issue operations.

### Quick Reference

```bash
bd ready                # Find available work
bd show <id>            # View issue details
bd update <id> --claim  # Claim work
bd close <id>           # Complete work
bd prime                # Refresh Beads context
```

### Rules

- Use `bd` for all task tracking; do not create markdown TODO lists.
- Run `bd prime` when Beads context is missing or stale. Codex 0.129.0+ can load Beads context automatically through native hooks; use `/hooks` to inspect or toggle them.
- Keep persistent project memory in Beads via `bd remember`; do not create ad hoc memory files.

**Architecture in one line:** issues live in a local Dolt DB; sync uses `refs/dolt/data` on your git remote; `.beads/issues.jsonl` is a passive export. See https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md for details and anti-patterns.
<!-- END BEADS CODEX SETUP -->
