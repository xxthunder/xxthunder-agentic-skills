# ADR-0013 — Skill work builds on superpowers and skill-creator

**Status**: Accepted
**Date**: 2026-10-31
**Related**: [XAS-054](../backlog/xas-054.md), [XAS-055](../backlog/xas-055.md), [XAS-056](../backlog/xas-056.md), [ADR-0012](0012-skill-changes-are-verified-by-local-behavioural-evals.md)

## Context

The author wants a closed engineering loop for skill changes: an orchestrator, a
test-first implementer and a reviewer. The loop should end on evidence, so the
author confirms results and does not read every `SKILL.md` diff. The first design
in the conversation was an orchestrator and a reviewer of this repository's own.

The author stopped that with a principle: we are not the first with this problem.
Look for what exists before building, and apply the same to work already merged.
The plugins installed next to this one ship most of the loop:

- `superpowers:subagent-driven-development` runs an implementer subagent per task.
  A task reviewer then checks spec compliance and quality, and fix rounds follow,
  with a stronger model when rounds run out. Its reviewer takes binding
  constraints from the plan.
- `superpowers:writing-skills` treats a skill change as TDD. The scenario fails
  without the change (RED), passes with it (GREEN), and loopholes get closed
  (REFACTOR). It also says to automate a mechanical constraint and keep prose for
  judgment.
- `skill-creator` runs with-skill and baseline sessions, grades and benchmarks
  them, compares versions blind, and optimises a skill's description for
  triggering. It too says that work every run repeats belongs in a bundled script.

This repository had used none of them by name. XAS-047 built `evals/` without
recording why `skill-creator` did not serve, and XAS-051 was written without
`writing-skills`, although its evals did fail on `develop` and pass on the branch.

ADR-0012 rejects an LLM judge that grades eval runs. A reviewer in the loop is
also a model passing a verdict, so the line between the two had to be drawn
before a reviewer is added.

## Decision

Skill work in this repository builds on what `superpowers` and `skill-creator`
ship. It adds only what they lack, and says why.

- **The loop is `superpowers:subagent-driven-development`.** This repository
  writes no orchestrator. What it adds for skills reaches the loop through the
  places the loop already offers, such as the constraints the plan hands its
  reviewer.
- **The method is `superpowers:writing-skills`.** Every change to a `SKILL.md`
  follows it. The RED step is an eval case that fails against `develop`
  (ADR-0012).
- **Mechanical checks are code; judgment goes to a reviewer.** Whatever can be
  checked by a script, a hook or an eval assertion is checked there. That
  includes a step a skill asks the agent to perform by hand when a script could
  perform it. A reviewer gets only what needs judgment.
- **A reviewer judges the diff, never the run.** A reviewer reads a change
  against a rubric and reports findings. It does not decide whether an eval case
  passed, and its approval does not replace a green eval run. ADR-0012 stands
  unchanged: runs are graded by assertions.
- **`skill-creator` is adopted where it adds to `evals/`, provisionally.** Its
  description optimisation answers a question `evals/` cannot answer: does the
  description trigger? Its rule to bundle repeated work as a script is the rule
  above. Its harness is not adopted for now. The cases in `evals/` grade git
  state across a store and a consumer repository on bare remotes, which its
  output-based runs do not. XAS-056 makes the final call, part by part. A
  different result there is recorded as a new ADR that supersedes this point.

## Alternatives considered

- **An orchestrator and reviewer of our own.** This was the first proposal in the
  conversation. It lost to the author's principle: `subagent-driven-development`
  already has the orchestrator, the implementer, the reviewer and the fix rounds.
  A copy would duplicate them and drift from them.
- **An LLM judge over eval runs.** ADR-0012 rejected it, and the reasons still
  hold: a second source of variance in the verdict, and a second model call per
  run.
- **Carrying on as before.** Skills would keep being written without
  `writing-skills`, and tooling would keep being built without first looking for
  what exists. XAS-047 and XAS-051 show both.

## Consequences

- This repository depends on how `superpowers` and `skill-creator` work, not only
  on their being installed. When they change, how our rubric reaches the loop may
  have to change with them.
- The implementer and the reviewer in the loop are the same model, so they share
  blind spots. The eval gate and the author's merge remain the checks outside
  the model.
- Each loop round that runs evals costs dozens of agent sessions. How many rounds
  run before the loop stops and asks is XAS-055's to settle.
- An implementer that knows the rubric and the cases can optimise for the
  checks. XAS-055 settles who writes a case before the implementer starts.
- Escape hatch: the decision adds no code. If `subagent-driven-development` does
  not take a skill rubric, XAS-055 adds a thin skill around it, still without an
  orchestrator of our own.
