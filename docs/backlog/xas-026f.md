# [XAS-026f] Coverage thresholds via codecov.yml

**Status**: Open
**Priority**: Low
**Component**: `codecov.yml`, `scripts/gate` (`evals/gate.py`), `pyproject.toml`

**Summary**:
As a maintainer, I want enforced coverage thresholds so that PRs that meaningfully drop coverage are flagged automatically.

**Description**:
XAS-026b ships Codecov reporting only — no thresholds. Once the numbers have stabilized over a handful of PRs and we have a baseline, add a `codecov.yml` to enforce a minimum target and a maximum allowed dip.

**Depends on**: XAS-026b (need a stable baseline before setting numbers)

**Acceptance Criteria**:
- [ ] `codecov.yml` at repo root defines a `coverage.status.project` rule with `target` (a sensible baseline observed from recent PRs) and `threshold` (small allowed dip, e.g., 1%)
- [ ] `coverage.status.patch` rule enforces a target on the PR diff itself (catches new code that ships untested)
- [ ] At least one PR exercises the rule (deliberate dip below threshold) and the Codecov check fails as expected
- [ ] README or CONTRIBUTING notes the threshold policy and how to update it
- [ ] `scripts/gate` measures coverage and fails when the patch coverage against `origin/develop` is below the patch target
- [ ] The gate and `codecov.yml` take the patch target from one place
- [ ] Code that runs only in eval sessions (`evals/cases.py`, `evals/fixture.py`) is covered by pytest or excluded from the measurement, by a decision written in this item

**Technical Notes**:
- Set numbers from observed baseline, not from a wishlist — too-aggressive targets cause merge friction without quality gain.
- Per-component thresholds (per plugin, per skill) can come later if the single global rule proves too coarse.

**Scope Decisions**:
- **The gate checks patch coverage too** (author, 2026-11-19). PR 46 (XAS-080) had both
  matrix jobs green, but `codecov/patch` and `codecov/project` red: patch coverage 80.6%,
  24 lines missing, 18 of them eval-only code in `evals/`. The gate runs `pytest -q` without
  `--cov`, so the closed loop could not see the gap and pushed it. Coverage is a number a
  script decides, so it goes into the gate, not into `docs/rubric.md`.
