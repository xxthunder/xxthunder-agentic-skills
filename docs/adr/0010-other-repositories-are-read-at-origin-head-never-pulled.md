# ADR-0010 — Other repositories are read at `origin/HEAD`, never pulled

**Status**: Accepted
**Date**: 2026-10-21
**Related**: [XAS-040](../backlog/xas-040.md)

## Context

Until `next`, every skill read and wrote only two places: the consuming
repository the session works in, and a store resolved under
[ADR-0007](0007-cross-repo-stores-are-configured-not-discovered.md). `next` is
the first skill that **reads other repositories** — every repo its list or the
logbook names — to show each item's status and priority.

Those repositories are local checkouts the maintainer also works in, often
from several sessions at once, each on its own branch or worktree. A checkout's
working tree can be behind its remote, or on a feature branch whose backlog
says something the default branch does not yet say. The skill must read the
state the repository has agreed on, and must not move the ground under a
session that is working in that checkout.

## Decision

A skill that reads a repository other than the session's own and other than a
resolved store **fetches it and reads it at `origin/HEAD`**. It never pulls,
checks out, resets or stashes there; that repository's working tree, index and
`HEAD` stay exactly as they were. `origin/HEAD` names the default branch,
whatever it is called — once it is set from the remote, which a fetch does not
do.

The reading is tested code, not shell in a `SKILL.md`: the plugin's
`backlog.py` does it for a backlog (`--repo`). How it fetches, finds the
default branch and gets at the files is that script's specification, and can
change without this decision changing.

## Alternatives considered

- **Pull, then read the working tree.** Rejected: a pull in a checkout where
  another session is working moves its ground — it can fail on local changes,
  or succeed and change files under the other session.
- **Read the working tree as it is.** Rejected: it can be stale, or on a
  feature branch, so the answer depends on what the checkout happens to hold
  rather than on what the repository has agreed on.
- **Export with `git archive origin/HEAD … | tar -x` from the skill's
  `SKILL.md`.** Rejected in review: shell in a `SKILL.md` is untested. A
  failed export went unnoticed and surfaced as a traceback or as "no such
  item" for every ID; `origin/HEAD` is missing in a checkout that was not
  cloned and goes stale when the remote's default branch is renamed; it needs
  `tar` on Windows; and each fetch, archive and clean-up step is one more
  command outside the skill's pre-approved tools.

## Consequences

- A status change that lives only on an unmerged feature branch is invisible
  until it is merged. For *Done* that is right: the default branch does not
  contain the work yet. For *In Progress* it is not — an item pulled on a
  branch still reads *Open* — so a pull goes to the default branch at once
  ([XAS-041](../backlog/xas-041.md)). Either way the skill reports a mismatch
  as a contradiction instead of hiding it.
- Every read costs a `git fetch` per repository, with the network and
  authentication that needs.
- A repository that is not cloned locally cannot be read; the skill asks
  before cloning it.
- The store itself is not covered by this decision: it is pulled by its
  resolver, because it is written to.
