# ADR-0016 — The closed loop is a thin conductor over superpowers' SDD

**Status**: Accepted
**Date**: 2026-11-05
**Related**: [XAS-055](../backlog/xas-055.md), [ADR-0013](0013-skill-work-builds-on-superpowers-and-skill-creator.md)

## Context

XAS-055 drives one backlog item from the board to a pull request. `superpowers:subagent-driven-development`
(SDD) already runs a plan task by task: implementer, task reviewer, fix rounds, a final
reviewer. Its task reviewer gets the plan's `## Global Constraints` verbatim, and its final
reviewer reads the plan file, so a rubric reaches every reviewer through the plan. SDD does
not find the target repository's gate, end on it, keep the tests away from the implementer,
or write the evidence package. SDD ends when its final review is clean.

## Decision

- **The skill is a thin conductor.** SDD stays unchanged; the skill adds the parts SDD
  lacks and writes no orchestrator of its own.
- **Rules are layered on for the run**, not patched into SDD: the split of each task into a
  tester and an implementer, disputes going to a fresh tester, the guard that checks the
  implementer left the tester's files alone, and the stops where only the author can
  decide.
- **The loop's state lives in the worktree's git directory**, kept by `loop.py`, so a
  resumed loop reads it from the worktree it works in.
- **Tester and implementer commits stay apart until the gate is green**, so the guard can
  tell them apart; `loop.py` makes the implementer's commits as `amend!`/`fixup!` commits
  of the tester's commit and folds them with git's autosquash before the push — one
  commit per unit, code and tests together. The repository's commit hooks run on each.
- **The gate and the evidence package come from the target repository's contract**, read
  fresh at every start — never from the skill (see the item's Scope Decisions).
- **The loop ends on the gate**, never on a reviewer's approval.

## Alternatives considered

- **A wrapper around SDD, or a fork of it.** Not needed for the rubric, which reaches the
  reviewers through the plan's Global Constraints. A copy of SDD's files would be one more
  piece to keep in step with the upstream plugin (ADR-0013).
- **An orchestrator of the skill's own.** It would rebuild what SDD does; the item names it
  a non-goal.
- **Ending on the reviewer's approval, as SDD does.** The same model that wrote the change
  would judge it. The item calls this an anti-goal: the loop ends on a deterministic gate.

## Consequences

- A change in SDD's behaviour reaches the loop unfiltered; the loop's own rules sit on top
  and may need a look after an SDD upgrade.
- The loop's rules are carried by the skill's text and by the plan, so only evals show
  whether a run follows them.
- A repository with neither gate nor CI does not take part.
