# ADR-0007 — Cross-repo stores are configured, not discovered

**Status**: Accepted
**Date**: 2026-09-18
**Related**: [XAS-034](../backlog/xas-034.md), [XAS-035](../backlog/xas-035.md)

## Context

[ADR-0006](0006-record-locations-are-discovered.md) resolves the design record
by discovery and rejects configuration as per-repo upkeep. It can do that
because the record lives *inside* the consuming repository: there is something
on disk to find.

The `learnings` skill writes somewhere else. A learning is what stays true
after the project is deleted, so its home is a personal knowledge repo outside
every consuming repository — one store, written to from sessions in many repos.
The skill therefore has to know where that store is, and the direction rule
[XAS-034](../backlog/xas-034.md) sets says where it may *not* find out:

> The store points into repositories; no repository points into the store.

No `CLAUDE.md`, `AGENTS.md`, backlog item, hook configuration or skill text in
a consuming repo may name the store, its path or its remote. Some of those
repos are public; all of them are the author's repositories, not the store's
concern. Discovery from the consuming repo has nothing to discover, by design.

Two further forces: the skill must also work from an ephemeral devcontainer
that has no checkout of the store at all, and it must never guess — a store
that silently resolves to the wrong place, or to the consuming repo, is the
one failure worse than not running.

## Decision

A cross-repo store is resolved from **machine-level configuration**: a pair of
variables in the user's own settings, `<PREFIX>_PATH` (a local checkout) and
`<PREFIX>_REMOTE` (a clone URL), never in any repository. One shared resolver,
`scripts/store`, reads the pair, parameterised by prefix so several stores —
learnings, logbook, whatever comes next — are configured independently and
may or may not be the same repo. With nothing configured it stops and says so.
It never guesses and never falls back to the current repository.

The resolution order — which source wins when several apply, and where a
clone from `<PREFIX>_REMOTE` lands — is a specification, stated once in the
script's header, and can change without this decision changing.

## Alternatives considered

- **Discovery from the consuming repo, as ADR-0006 does for the record.**
  Rejected because the direction rule leaves nothing to discover. ADR-0006's
  reasoning holds where it was written; the store is the case it does not
  cover, and this ADR is the considered divergence, not a reversal.
- **A gitignored dotfile in the consuming repo's working tree naming the
  store.** Rejected on the direction rule as stated: the rule is that no
  repository points into the store, not that no *committed* file does. It also
  reintroduces per-checkout upkeep — every clone and every devcontainer would
  need the file recreated — which is the cost ADR-0006 removed on the record
  side.
- **Name one store in the skill text.** Rejected without discussion of merit:
  the skill is installed into public repositories, and "mention any specific
  store in its own text" is on the skill's never-list.

## Consequences

- Every machine, and every fresh devcontainer, needs the two variables set
  once before the skills do anything. That is per-machine upkeep, accepted in
  exchange for zero per-repo upkeep — the inverse of ADR-0006's trade, for the
  inverse situation.
- The unconfigured case is a test, not a hope: the resolver's give-up path
  fails with a non-zero exit and a message, asserted in `tests/dev/scripts/`,
  so a store can never silently resolve to nothing.
- Each operation pays for freshness — a `pull` or a `clone` — before it does
  anything, because in an ephemeral container the cached copy may be minutes
  or weeks old. The exception is a session already working inside the store,
  which is used as-is so the resolver never moves the ground under it.
- ADR-0006's escape hatch — extend the search order — does not apply here.
  If the variable pair proves insufficient, the escape is another variable
  under the same prefix, never a file in a repository.
- Authentication is out of scope: SSH keys and `GIT_SSH_COMMAND` are the
  environment's business, and a clone or push that fails for that reason is
  reported, not worked around.
