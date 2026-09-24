# ADR-0001: Identity on the wire is delegated, and the audit row names three parties

- Status: accepted
- Date: 2026-09-24
- Requirements: REQ-11, REQ-13
- Supersedes: nothing

## Context

Chapter B puts the read-only server behind HTTP. The cheap option is a shared
API key per caller. That works, and it produces audit rows nobody can act on:
every entry says "the service account did it", which answers no question an
auditor asks.

Two things changed in 2026 that make the more careful option cheap enough. MCP
added OAuth 2.1 to its HTTP transport in January, with separate paths for a
client acting for a user, an unattended agent acting for itself, and
enterprise-managed access through an identity provider. Enterprise-managed
authorization landed in August. Agent traffic is also the thing organisations
report the least visibility into, so the gap being closed here is real rather
than theoretical.

The failure this is designed against is specific: an agent calls a tool, and
six months later nobody can say which human's decision the call was carrying.

## Decision

1. Every route except /healthz and /openapi.json requires a signed bearer
   token. Verification is local against a published key set; no network call
   on the request path.
2. Three identities are extracted from the token's claims and written to the
   audit row: the agent (`azp`), the subject whose permissions applied
   (`sub`), and the human initiator (`act.sub` for a delegated token, equal to
   `sub` for a direct human call).
3. A service token with no human behind it is legal, and records its initiator
   as the literal string `"unattended"`. Never blank: an auditor must be able
   to count unattended traffic, and a blank field cannot be told apart from a
   bug.
4. Identity supplied in headers is ignored entirely. If a fact is not inside
   the signed token, it does not reach the audit row. There is a test for this
   (`test_initiator_from_token_not_from_header`), because the spoofed header is
   the obvious attack and it is invisible once the row is written.
5. Refusals are typed bodies, never exceptions on the wire (NFR-01): a 401
   returns `{"refused": true, "reason": ..., "detail": ...}` like every other
   refusal in this codebase.

## Consequences

Good: an audit row answers "who decided this" rather than "which key was used".
The design carries straight into the compliance work, where the same three
identities become the hash-chained store's subject. It also matches the
vocabulary the market now uses, which makes the artifact legible to the people
this project is meant to reach.

Costs: token issuance is now a dependency for local development, which is why
`action_engine_api.testing.issue_test_tokens()` exists and is part of the spec
rather than a test-only afterthought. A wrong key-set rotation breaks every
route at once; the mitigation is that key-set fetching is cached and failure
falls back to the last known good set, with the fallback logged.

Rejected alternatives: shared API keys (unattributable, above); mTLS per client
(attributes the machine, still not the human, and heavier to operate for one
service); passing initiator as a header with the key (trusts the caller to tell
the truth about the one fact the row exists to establish).
