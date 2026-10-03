# ADR-0009 — Backlog items are the truth; the TOC is derived

**Status**: Accepted
**Date**: 2026-10-03
**Related**: [XAS-039](../backlog/xas-039.md)

## Context

The backlog keeps an item's status twice: in the item's `**Status**:` line,
and in the README section that lists the item. Until now the README was the
authoritative copy, and agents kept it current by hand, following rules written
in prose in `refinement` and `backlog-ops`: which section an item belongs in,
and that each section is sorted by ID.

Those rules have one right answer each, and an agent that follows prose gets
them right most of the time, not every time. On 2026-10-01 an agent filed
XAS-038 above XAS-036, and `develop` went red. The invariant tests from
[XAS-033](../backlog/xas-033.md) caught it, but only in CI after the push, and
one of those tests, `check_status_matches_section`, exists only because the
two copies of the status can disagree.

The same skills run against every repository on the author's workbench, not
only this one. Whatever keeps the TOC right has to work there too.

## Decision

**The item files are the single source of truth.** Everything the backlog
README says about an item (its section, its position, its title) is derived
from the item by a script that ships with `xxthunder-dev-skills`. The skills
call the script for every mechanical step: allocating an ID, setting a status,
regenerating the TOC, checking the backlog. They no longer edit the TOC by hand.

The TOC's shape, including section order, sort order and line format, is a
specification. It is stated in `refinement`'s `backlog-format.md` and enforced
by the script's tests, not here.

## Alternatives considered

- **Keep the README authoritative and keep sorting by hand.** That was the
  status quo, and it failed on 2026-10-01. The rule was written down; the model
  did not follow it that time.
- **State the sorting rule explicitly in `refinement`'s New Ideas step.**
  Cheap, but it relies on the model in the same way. It only makes a mistake
  less likely.
- **A pre-commit hook that runs the invariant checks.** It would catch the
  mistake before the push, but it does not sort anything. The check already
  existed; it ran in CI.
- **A script that maintains the README while the README stays
  authoritative.** The status would still live in two places, and a check
  would still be needed to keep them in agreement. Deriving one copy from the
  other removes the second copy instead of guarding it.

## Consequences

- A hand edit to the TOC does not survive the next run. A title is changed in
  the item's heading, a status in the item's `**Status**:` line.
- A TOC line holds only what the item provides. Notes a README carried on a
  line, such as "— replaced by …", are dropped; the item has to say it.
- The script refuses to rewrite a TOC block that holds anything no item
  produces, rather than drop it silently. A repository with such content moves
  it out of the block before the script can run there.
- Every repository that uses the backlog skills needs `uv`, because the script
  is Python run with `uv run`. The author's workbench and hosts all have it.
- The rule in `backlog-ops` that the README wins a disagreement is reversed:
  the item wins, and the README is regenerated.
- The escape hatch is cheap. The README is plain Markdown, so dropping the
  script means editing it by hand again; nothing in the items changes.
