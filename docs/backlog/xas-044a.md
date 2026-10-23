# [XAS-044a] ADR: requirements become a binding design artifact where sphinx-needs is in use

**Status**: Open
**Priority**: Medium
**Component**: `docs/adr/` (new ADR, ADR-0001), `docs/adr/README.md`, `docs/architecture.md`

**Summary**:
As the maintainer, I want the decision of [XAS-044](xas-044.md) recorded as an ADR that narrows ADR-0001, so that every repository and every skill follows one rule about where requirements live.

**Description**:
The decision and its reasons are in XAS-044 (Description and Scope Decisions). It changes a rule all consuming repositories follow, so it is an ADR and not a Scope Decision of one item. It goes first: XAS-044b to XAS-044d build on it.

ADR-0001 stays binding for repositories without a root `ubproject.toml`. The new ADR narrows it rather than replacing it.

**Scope Decisions**:
- **Alternatives to record**, from the conversation of 2026-10-23:
  - Generate needs from the plain-Markdown items at build time. Rejected: ubCode indexes native needs while editing, a generator would have to track the item format, and each item would exist twice.
  - Let the existing items decide the format, without a switch. Rejected: a root `ubproject.toml` is where useblocks keeps the one configuration both readers use, so it is the natural switch.
  - Keep "the story is the requirement" (ADR-0001) and trace code to stories. Rejected: a closed story is history, and the trace goes stale silently (SC-040 and SC-067 in shortcuts).

**Acceptance Criteria**:
- [ ] A new ADR, recorded through `design-record`, states context (ADR-0001's two reasons and what changed), decision (XAS-044's Scope Decisions), the alternatives above and the consequences
- [ ] ADR-0001 points to the new ADR, following `design-record`'s rules for superseding, and still reads as binding for repositories without a root `ubproject.toml`
- [ ] The ADR index and `docs/architecture.md` name the new artifact where they list the design record
