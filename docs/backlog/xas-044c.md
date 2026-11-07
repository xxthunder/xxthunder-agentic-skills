# [XAS-044c] `design-record` keeps requirements true, and closing an item changes them

**Status**: Open
**Priority**: Medium
**Component**: `plugins/xxthunder-dev-skills/skills/design-record/`, `plugins/xxthunder-dev-skills/skills/backlog-ops/` (close), the `SessionStart` hook
**Depends on**: [XAS-044a](xas-044a.md), [XAS-044b](xas-044b.md)

**Summary**:
As the maintainer of a repository with a root `ubproject.toml`, I want closing an item to bring the requirements it changes up to date, drafted by the agent and approved by me, so that requirements stay true without a separate chore.

**Description**:
The lifecycle of [XAS-044](xas-044.md): an item's behaviour criteria are the delta. At close, the requirement needs are created or edited to the new state, in the same commit that sets the item Done. The item keeps no link to them: it freezes as history, and the commit records which requirements it changed. The requirement stays current.

**Scope Decisions**:
- **`design-record` writes, `backlog-ops` triggers** ([ADR-0003](../adr/0003-one-writer-for-the-design-record.md)): a close in a switched repository hands the requirement change to `design-record` before it sets Done.
- **The author approves the wording**: the agent drafts each requirement change, as it drafts an ADR body.
- **Decided in this item**:
  - What happens to a requirement whose behaviour is removed: deleted, or kept with a status.
  - What a requirement may say: one statement of current behaviour per need, with a stable ID.
- **No link from item to requirement** (2026-11-07, XAS-044): an item may name requirements in its prose while it is open, but nothing checks or keeps such a reference after Done.
- **The `SessionStart` orientation** names requirements as part of the record where the switch is on.

**Acceptance Criteria**:
- [ ] `design-record` has a procedure to create, change and retire a requirement need
- [ ] In a switched repository, `backlog-ops` close drafts the requirement change from the item's behaviour criteria, applies it through `design-record` after the author approves, and commits it together with the item set to Done
- [ ] A close adds no link from the item to a requirement
- [ ] The `SessionStart` orientation mentions requirements where the switch is on, and nothing changes where it is off
- [ ] The skills stay generic: no repository-specific path or ID
- [ ] The plugin version is bumped (minor)
