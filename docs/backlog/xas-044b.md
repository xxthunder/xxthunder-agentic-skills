# [XAS-044b] Item and ADR headers as needs

**Status**: Open
**Priority**: Medium
**Component**: `plugins/xxthunder-dev-skills/scripts/backlog.py`, `tests/`, `plugins/xxthunder-dev-skills/skills/refinement/references/backlog-format.md`, `plugins/xxthunder-dev-skills/skills/design-record/` (ADR header), `plugins/xxthunder-dev-skills/skills/backlog-ops/`
**Depends on**: [XAS-044a](xas-044a.md)

**Summary**:
As the maintainer of a repository with a root `ubproject.toml`, I want every backlog item and ADR to carry its header as a sphinx-needs need, so that ubCode and the Sphinx build index items and ADRs and can check the links to and from them.

**Description**:
Today an item's header is a block of bold-field lines (`**Status**: Open`), which `backlog.py` parses and writes. Where the switch is on (XAS-044), that block becomes one need directive and the rest of the file stays plain Markdown:

````markdown
```{story} Backlog index the backlog script can derive
:id: SC-072
:status: Done
:priority: Medium
```
````

ADRs get the same with a `decision` need; an ADR's context item becomes a link to the story need. The format is a specification in `backlog-format.md`, enforced by the script's tests ([ADR-0009](../adr/0009-backlog-items-are-the-truth-the-toc-is-derived.md)).

**Scope Decisions**:
- **Switch per repository, not per item**: a root `ubproject.toml`. `backlog.py` reads and writes the format the switch selects, and `check` reports a backlog that mixes both.
- **Migration**: one command converts all items and ADRs at once; it is idempotent and refuses a backlog it cannot convert completely.
- **Decided in this item**:
  - Whether the `#` heading stays beside the need title (readable on GitHub, but the title twice) or the need title replaces it; the TOC takes its title from whichever stays.
  - How an item says it changes no requirement without a link to a need that does not exist (a broken link fails the build). The rule "every Done story links to a requirement or says none" must be expressible as a check both readers run.
  - Which need types, fields and link types the consuming repository has to declare in its `ubproject.toml`, and whether the script writes those declarations or documents them.
  - The need ID pattern: item IDs such as `SC-072` and `SC-016a` need a `needs_id_regex` that allows a hyphen and a lower-case letter.

**Acceptance Criteria**:
- [ ] `backlog-format.md` specifies the need-shaped header, the switch and the migration
- [ ] `next-id`, `set-status`, `toc`, `check` and `show` work in both formats; tests cover both
- [ ] The migration converts a fixture backlog with ADRs; `check` passes afterwards, and a second run changes nothing
- [ ] `design-record` writes need-shaped ADR headers where the switch is on
- [ ] A migrated fixture builds with Sphinx `-W` and passes `ubc check` without findings
- [ ] The plugin version is bumped (minor)
