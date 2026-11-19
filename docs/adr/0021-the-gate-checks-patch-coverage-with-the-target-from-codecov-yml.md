# ADR-0021: The gate checks patch coverage with the target from codecov.yml

**Status**: Accepted
**Date**: 2026-11-19
**Related**: [XAS-026f](../backlog/xas-026f.md), [ADR-0014](0014-eval-results-count-per-plugin-and-case-version.md)

## Context

Codecov reports patch and project coverage on every pull request, but until
XAS-026f nothing before the push measured coverage. PR 46 (XAS-080) had both
test jobs green and still failed `codecov/patch` and `codecov/project`: the
gate ran pytest without `--cov`, so the closed loop, which ends on the gate,
could not see the gap and pushed it.

Coverage is a number a script can decide, so it belongs in the gate, not in a
reviewer's rubric. The gate and Codecov then both need the patch target, and
two copies of one number drift.

## Decision

- `codecov.yml` is the one source of the coverage rules, the patch target
  included. Change a threshold there and nowhere else.
- `scripts/gate` runs pytest with coverage into a report outside the working
  tree, reads the patch target from `codecov.yml`, and runs `diff-cover`
  against `origin/develop` with that target as `--fail-under`. The gate is red
  when the changed lines fall below the target.
- The gate checks patch coverage only. The project rule stays with Codecov.

## Alternatives considered

- **The patch target in `pyproject.toml` or in the gate's code.** Codecov reads
  only its own `codecov.yml` and cannot take a number from another file. With
  the number anywhere else, two copies would exist, so the gate reads it from
  Codecov's file instead.
- **The gate computes diff coverage itself** from `git diff` and the coverage
  report. `diff-cover` is the known tool for exactly this, and the
  repository's rule is to build only the gap an existing tool leaves. It
  leaves none here.
- **A rubric criterion for reviewers** ("does the change ship tests for its
  lines"). A reviewer judges what a script cannot decide; a percentage is
  decidable, and a rubric answer is a model's judgment where a gate gives an
  exit code.

## Consequences

- `diff-cover` is a new dev dependency, and the gate now runs the whole suite
  under coverage, which makes each gate run and each push slower.
- The gate measures on the machine it runs on, Linux in practice. Codecov
  merges the Ubuntu and Windows uploads, so the two numbers can differ for
  platform-specific lines; Codecov's check on the pull request stays the final
  word.
- `diff-cover` sees changed Python lines only. A change to the coverage
  configuration itself can move the project number without any changed line:
  in XAS-026f a relative `omit` pattern reported two files at 0%, the gate
  stayed green and only `codecov/project` caught it. Such a change needs a
  test of its effect.
- `diff-cover` compares with the local `origin/develop` and does not fetch it.
  It diffs from the merge-base, so a stale ref widens the diff rather than
  hiding lines.
- The escape hatch is cheap: dropping the step from `evals/gate.py` leaves
  Codecov's checks as they were before.
