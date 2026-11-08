# ADR-0018 — Requirements are a binding design artifact where sphinx-needs is in use

**Status**: Accepted
**Date**: 2026-11-08
**Related**: [XAS-044a](../backlog/xas-044a.md), [XAS-044](../backlog/xas-044.md), [ADR-0001](0001-two-design-artifacts-split-by-lifetime.md)
**Narrows**: [ADR-0001](0001-two-design-artifacts-split-by-lifetime.md), for repositories with a root `ubproject.toml`

## Context

[ADR-0001](0001-two-design-artifacts-split-by-lifetime.md) keeps two binding design
artifacts, the ADR log and `architecture.md`, and rejected a standing requirements
document for two reasons: it duplicates what a story's Summary and Acceptance Criteria
already say, and staying truthful would need bidirectional traceability machinery that
was out of scope.

In a repository that uses sphinx-needs with ubCode and sphinx-codelinks, that machinery
exists: needs with IDs, typed links, checks that fail a build, traces from code comments
and from test reports. The second reason no longer holds there. The first falls to
ADR-0001's own sorting rule, lifetime: an acceptance criterion verifies one change and is
no longer maintained after Done; a requirement states current behaviour and stays true.

What made it pressing: code that traces to a story traces to history. In shortcuts,
SC-040 decided that px does not start at logon and SC-067 reversed it. A code marker
pointing at SC-040 would be silently wrong today; a marker pointing at the requirement
stays right. The question came up at the useblocks user day on 2026-10-23, together with
shortcuts SC-073, the first repository to use it.

## Decision

In a repository with a root `ubproject.toml`, requirements are a third binding design
artifact, beside the ADR log and `architecture.md`. Without that file, ADR-0001 holds
unchanged.

- **The switch** is the root `ubproject.toml`: it is the one configuration ubCode, `ubc`
  and Sphinx read, so a repository that has it uses sphinx-needs.
- **Requirements are native needs**, edited in place like `architecture.md`. Where they
  live and how they are split is the consuming repository's choice.
- **One writer** ([ADR-0003](0003-one-writer-for-the-design-record.md)): `design-record`
  writes requirements as it writes ADRs and `architecture.md`. A read-only scan may
  propose; applying goes through `design-record`.
- **Traces point at the present**: ADRs link to the requirements they constrain; code and
  tests link to the requirements they implement and test. Nothing links to a backlog item.
- **Backlog items stay history**: an item is no need and links to no requirement. Its
  behaviour criteria are the delta; the commit that closes it changes the requirements,
  and git records which ones.
- **ADR headers become needs**, so that an ADR can link the requirements it constrains.
  The header format is specified by `design-record`'s ADR format reference, not here.
- **Bootstrap from what is true now**: the first requirements of an area are derived from
  its code, tests and user documentation, never by replaying closed stories, whose deltas
  include reversed decisions ([ADR-0005](0005-bootstrap-architecture-never-reconstruct-adrs.md)).
- **Only what both readers understand**: nothing the skills write depends on a
  Sphinx-only directive or needs function.

## Alternatives considered

- **Generate needs from the plain-Markdown items at build time.** Rejected: ubCode indexes
  native needs while editing, a generator would have to track the item format, and each
  item would exist twice.
- **Let the existing items decide the format, without a switch.** Rejected: a root
  `ubproject.toml` is where useblocks keeps the one configuration both readers use, so it
  is the natural switch.
- **Make item headers needs too, and let stories link to the requirements they change.**
  Rejected (2026-11-07): a Done item is history, not product knowledge; it must not show
  up in the product view, not even as a backlink. Git history already links an item to the
  changes it made.
- **Keep "the story is the requirement" (ADR-0001) and trace code to stories.** Rejected:
  a closed story is history, and the trace goes stale silently, as SC-040 and SC-067 in
  shortcuts show.

## Consequences

- The design record has two shapes, chosen per repository by the switch. Every skill that
  writes the record reads the switch first, and ADR headers exist in two formats.
- Closing an item in such a repository gains a step: the requirement change, drafted by the
  agent and approved by the author, in the same commit that sets the item Done.
- Which requirements an item changed is found only in git, not in the documentation. That
  is accepted: the documentation shows the product, not its history.
- Adopting sphinx-needs in an existing repository costs a bootstrap per area and a
  one-time migration of its ADR headers.
- ADR-0001's "no third place" still holds wherever the switch is off. Removing
  `ubproject.toml` returns a repository to ADR-0001, but leaves its requirement files
  behind as documents no skill maintains.
