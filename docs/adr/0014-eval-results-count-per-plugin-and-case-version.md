# ADR-0014 — Eval results count per plugin version and case version

**Status**: Accepted
**Date**: 2026-11-02
**Related**: [XAS-049](../backlog/xas-049.md), [ADR-0012](0012-skill-changes-are-verified-by-local-behavioural-evals.md)

## Context

ADR-0012 leaves the evals to the author, run locally, and names the gap: a habit
lapses exactly when a change looks small. XAS-049 closes it with a gate that runs
before every push. A full eval run is 96 agent sessions (32 cases, 3 runs each); it costs tokens and
minutes on the author's own login.

The gate has to decide whether the results on disk still say something about the
change being pushed. That needs a rule for what a result belongs to. Two things
decide whether a run would come out the same: the plugin the agent reads, and the
case that prompts and grades it.

## Decision

- **The gate checks results; it never runs an eval.** When a result is missing, it
  stops the push and prints the exact command. The author decides when to spend
  the tokens and the minutes.
- **A result counts for one plugin version**: the tree hash of
  `plugins/xxthunder-dev-skills` at the ref the run evaluated. The runner files
  results under that hash.
- **A result counts for one version of the case**: each `result.json` carries the
  case's fingerprint. It covers what only the case holds (prompt, flags, the source
  of its check and setup) and what every case shares under `evals/`, as git tracks
  it. The tooling around the cases — the command line, the fingerprint and the
  gate — is not part of it: changing them changes no result.
- **The RED step applies only to new or changed cases of a touched skill.** Such a
  case must have failed at least once against the base plugin. A case that sees
  only a shared change is a regression case and passes at the base by design.

Which cases a change asks for, and the threshold, are in `CONTRIBUTING.md` → The
gate.

## Alternatives considered

- **Keying results by the ref name.** A branch name points at a new commit after
  every commit, so results of an older plugin would count for a newer one.
- **Keying results by the commit SHA.** Every rebase gives each commit a new SHA
  but leaves plugin and cases as they were, so a rebase onto a newer `develop`
  would void every result and ask for runs that cannot come out differently.
- **Running the evals in the `pre-push` hook.** A push would wait minutes and spend
  tokens without the author choosing to.
- **Running the evals in CI.** Too expensive for every pull request, and CI would
  need a key for the sessions (ADR-0012).

## Consequences

- A rebase, or a commit outside the plugin and `evals/`, keeps every result.
- Two branches with the same plugin tree share results; this is intended — the run
  would be the same.
- A change to a shared helper under `evals/` asks for a run of every case.
- A file under `evals/` that git does not track does not change a fingerprint;
  until it is committed, the runner does not hash it.
- The gate trusts the `result.json` files on disk; it cannot tell a hand-written
  one from a real run.
- CI does not call the gate yet: it holds no results, so it would stop every skill
  change. How CI takes part is open in XAS-049.
