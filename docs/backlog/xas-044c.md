# [XAS-044c] `design-record` keeps requirements true, and closing an item changes them

**Status**: Open
**Priority**: Medium
**Component**: `plugins/xxthunder-dev-skills/skills/design-record/`, `plugins/xxthunder-dev-skills/skills/backlog-ops/` (close), `plugins/xxthunder-dev-skills/skills/refinement/`, the `SessionStart` hook
**Depends on**: [XAS-044a](xas-044a.md), [XAS-044b](xas-044b.md)

**Summary**:
As the maintainer of a repository with a root `ubproject.toml`, I want closing an item to bring the requirements it changes up to date, drafted by the agent and approved by me, so that requirements stay true without a separate chore.

**Description**:
The lifecycle of [XAS-044](xas-044.md): when an item is written, it names the requirements it will change. Its behaviour criteria are the delta. At close, the requirement needs are created or edited to the new state, and the item keeps its links to them. The item then freezes as history; the requirement stays current.

**Scope Decisions**:
- **`design-record` writes, `backlog-ops` triggers** ([ADR-0003](../adr/0003-one-writer-for-the-design-record.md)): a close in a switched repository hands the requirement change to `design-record` before it sets Done.
- **The author approves the wording**: the agent drafts each requirement change, as it drafts an ADR body.
- **Decided in this item**:
  - What happens to a requirement whose behaviour is removed: deleted, or kept with a status.
  - What a requirement may say: one statement of current behaviour per need, with a stable ID.
- **`refinement` asks for the requirements** when it writes an item in a switched repository.
- **The `SessionStart` orientation** names requirements as part of the record where the switch is on.

**Acceptance Criteria**:
- [ ] `design-record` has a procedure to create, change and retire a requirement need
- [ ] In a switched repository, `backlog-ops` close refuses an item that neither links requirements nor says it changes none, and applies the requirement change through `design-record` before setting Done
- [ ] `refinement` asks for the requirements an item changes when it writes the item in a switched repository
- [ ] The `SessionStart` orientation mentions requirements where the switch is on, and nothing changes where it is off
- [ ] The skills stay generic: no repository-specific path or ID
- [ ] The plugin version is bumped (minor)
