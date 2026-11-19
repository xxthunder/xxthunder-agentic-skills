# [XAS-026f] ✅ DONE - Coverage thresholds via codecov.yml

**Status**: Done (2026-11-19)
**Priority**: Low
**Component**: `codecov.yml`, `scripts/gate` (`evals/gate.py`), `pyproject.toml`

**Summary**:
As a maintainer, I want enforced coverage thresholds so that PRs that meaningfully drop coverage are flagged automatically.

**Description**:
XAS-026b ships Codecov reporting only — no thresholds. Once the numbers have stabilized over a handful of PRs and we have a baseline, add a `codecov.yml` to enforce a minimum target and a maximum allowed dip.

**Depends on**: XAS-026b (need a stable baseline before setting numbers)

**Acceptance Criteria**:
- [x] `codecov.yml` at repo root defines a `coverage.status.project` rule with `target` (a sensible baseline observed from recent PRs) and `threshold` (small allowed dip, e.g., 1%)
- [x] `coverage.status.patch` rule enforces a target on the PR diff itself (catches new code that ships untested)
- [x] At least one PR exercises the rule (deliberate dip below threshold) and the Codecov check fails as expected
- [x] README or CONTRIBUTING notes the threshold policy and how to update it
- [x] `scripts/gate` measures coverage and fails when the patch coverage against `origin/develop` is below the patch target
- [x] The gate and `codecov.yml` take the patch target from one place
- [x] Code that runs only in eval sessions (`evals/cases.py`, `evals/fixture.py`) is covered by pytest or excluded from the measurement, by a decision written in this item

**Technical Notes**:
- Set numbers from observed baseline, not from a wishlist — too-aggressive targets cause merge friction without quality gain.
- Per-component thresholds (per plugin, per skill) can come later if the single global rule proves too coarse.

**Scope Decisions**:
- **The gate checks patch coverage too** (author, 2026-11-19). PR 46 (XAS-080) had both
  matrix jobs green, but `codecov/patch` and `codecov/project` red: patch coverage 80.6%,
  24 lines missing, 18 of them eval-only code in `evals/`. The gate runs `pytest -q` without
  `--cov`, so the closed loop could not see the gap and pushed it. Coverage is a number a
  script decides, so it goes into the gate, not into `docs/rubric.md`.
- **Baseline** (Q&A, 2026-11-19). Codecov check runs of PRs 39 to 47: project coverage
  91.2% to 98.0%, 97.4% to 98.0% since PR 41. Patch coverage 100% on most PRs, 92.5% on
  PR 41, 85.5% on the last head of PR 46. Without a `codecov.yml`, Codecov compares the
  project with the base at 0% threshold, so PR 46 and PR 47 failed `codecov/project` on a
  dip of 0.39%.
- **Project rule: `target: auto`, `threshold: 1%`** (author, 2026-11-19). It follows the
  base and stops the false alarms of a small dip. No fixed number has to be raised by hand.
- **Patch target: 90%** (author, 2026-11-19). It catches PR 46 (85.5%) and lets PR 41
  (92.5%) pass. Codecov and the gate use this one number.
- **`codecov.yml` holds the patch target; the gate reads it from there** (Q&A,
  2026-11-19). The file Codecov reads cannot read another file, so the number lives in
  it, and the gate parses it with `pyyaml`, which the dev group already has.
- **The gate measures patch coverage with `diff-cover`** (Q&A, 2026-11-19), against
  `origin/develop` and with the patch target as `--fail-under`. It is the known tool for
  this job, so the gate does not compute the diff coverage itself.
- **Eval-session code is excluded from the measurement** (author, 2026-11-19), AC 7.
  `evals/cases.py` and `evals/fixture.py` run only in eval sessions, and the evals verify
  them. They go into `omit` under `[tool.coverage.run]`. Other files in `evals/` that
  pytest tests, such as `evals/gate.py`, stay measured.
- **The loop opens the dip PR of AC 3** (author, 2026-11-19). After the main pull request
  is green, a draft pull request from its branch adds an untested function. The red
  `codecov/patch` check goes into the evidence package, and the draft is then closed.
