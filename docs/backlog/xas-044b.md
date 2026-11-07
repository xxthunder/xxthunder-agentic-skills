# [XAS-044b] ADR headers as needs

**Status**: In Progress
**Priority**: Medium
**Component**: `plugins/xxthunder-dev-skills/skills/design-record/` (ADR header, migration), `tests/`
**Depends on**: [XAS-044a](xas-044a.md)

**Summary**:
As the maintainer of a repository with a root `ubproject.toml`, I want every ADR to carry its header as a sphinx-needs need, so that ubCode and the Sphinx build index ADRs and check their links to the requirements they constrain.

**Description**:
Today an ADR's header is a block of bold-field lines. Where the switch is on (XAS-044), that block becomes one need directive and the rest of the file stays plain Markdown:

````markdown
```{decision} Two design artifacts, split by lifetime
:id: ADR-0001
:status: Accepted
:constrains: REQ-...
```
````

Backlog items keep their format: they are history, not product knowledge (XAS-044), and never become needs. An ADR that came out of an item names it in plain text, not as a need link.

**Scope Decisions**:
- **Only ADRs** (2026-11-07): item headers stay bold-field lines in every repository; `backlog.py` is not touched.
- **Switch per repository, not per ADR**: a root `ubproject.toml`. `design-record` writes the format the switch selects.
- **Migration**: one command converts all ADRs at once; it is idempotent and refuses an ADR log it cannot convert completely.
- **Decided in this item**:
  - Whether the `#` heading stays beside the need title (readable on GitHub, but the title twice) or the need title replaces it; the ADR index takes its title from whichever stays.
  - Which need type, fields and link types the consuming repository has to declare in its `ubproject.toml`, and whether the skill writes those declarations or documents them.
  - The need ID pattern: ADR IDs such as `ADR-0001` need a `needs_id_regex` that allows them.

**Acceptance Criteria**:
- [ ] `design-record` specifies the need-shaped ADR header, the switch and the migration
- [ ] `design-record` writes need-shaped ADR headers where the switch is on, and the old format where it is off
- [ ] The migration converts a fixture ADR log; a second run changes nothing
- [ ] A migrated fixture builds with Sphinx `-W` and passes `ubc check` without findings
- [ ] The plugin version is bumped (minor)
