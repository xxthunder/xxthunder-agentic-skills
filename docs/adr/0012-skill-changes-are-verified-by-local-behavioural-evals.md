# ADR-0012 — Skill changes are verified by local behavioural evals

**Status**: Accepted
**Date**: 2026-10-27
**Related**: [XAS-047](../backlog/xas-047.md), [XAS-049](../backlog/xas-049.md), [XAS-050](../backlog/xas-050.md)

## Context

Most changes in this repository change prose, not code: a `SKILL.md` says what
the agent does, and the agent does it. `pytest` covers the helper scripts and
the hook, and nothing else. The XAS-046 pull request changed three skills and
no executable code; all tests passed, and none of them checked the new
behaviour. It was verified by hand, once, against the author's real store.

When a harness that runs the skills was first pointed at that branch, it found
two bugs the manual check had missed: `next show` printed one table per column,
and `next drop` stopped to ask for a reason nobody needed to give.

## Decision

A change to a skill's behaviour is verified by behavioural evals. Each case runs
one prompt headless against the plugin at a git ref, in a throwaway sandbox with
its own repositories and stores, and grades the end state with plain assertions:
files, commits, item status, the final answer. No case reads or writes a real
store, so the evals run on any machine with Claude Code.

The author runs them locally — from time to time, and before a skill change is
merged. CI does not run them. How to run them, and when a change needs a case,
is in `CONTRIBUTING.md`.

## Alternatives considered

- **A manual end-to-end check against the author's store.** It is how XAS-046
  was verified, and it missed both bugs above. It also runs once, against real
  data, and cannot be repeated for the next change.
- **Running the evals in CI.** A full run is 84 agent sessions, which is too
  expensive for every pull request, and CI would need a key for them.
- **An LLM judge to grade the runs.** A second model adds its own variance, so a
  failing case could not tell whether the skill or the judge erred; assertions
  on files and commits give the same verdict every time. It would also cost a
  second model call per run, on top of a session that is already the expensive
  part.

## Consequences

- Verification depends on the author running the evals. A habit lapses exactly
  when a change looks small; XAS-049 adds a `pre-push` guard for that.
- Every run costs tokens and minutes on the author's own login.
- The agent is not deterministic, so one green run proves little. Each case runs
  several times and must pass every run.
- A case can encode a wrong expectation and reward the wrong behaviour. The
  grading is unit-tested against hand-built end states, which checks the
  grader, not whether the expectation matches the skill.
- The sessions get unrestricted `Bash`; isolation rests on the environment, not
  on enforcement. XAS-050 closes that gap.
- Escape hatch: the runner is plain Python and a case is a test like any other —
  one that stops paying for itself is loosened or deleted.
