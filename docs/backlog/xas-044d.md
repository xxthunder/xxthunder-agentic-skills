# [XAS-044d] Read-only requirements scan for bootstrapping

**Status**: Open
**Priority**: Medium
**Component**: a read-only requirements scan (new skill, or a mode of `architecture-scan`)
**Depends on**: [XAS-044a](xas-044a.md), [XAS-044b](xas-044b.md), [XAS-044c](xas-044c.md)

**Summary**:
As the maintainer of an existing repository that adopts sphinx-needs, I want a read-only scan that proposes requirements from the code, tests and user docs of one area and maps the closed items onto them, so that traceability can be retrofitted onto a repository with history.

**Description**:
It follows `architecture-scan` ([ADR-0003](../adr/0003-one-writer-for-the-design-record.md), [ADR-0005](../adr/0005-bootstrap-architecture-never-reconstruct-adrs.md)): derive from what is true now, propose, and let `design-record` apply what the author approves.

It does not replay stories: their deltas include reversed and superseded decisions. In shortcuts, SC-040 says px does not start at logon and SC-067 says it does; only the code, its tests and the runbook say which is true.

**Scope Decisions**:
- **One area at a time**: the scan takes an area (a tool, a component); shortcuts starts with px-proxy.
- **Two steps in one proposal**: first the requirements of the area; then, for each closed item that touched the area, the requirements it changed, or that it changed none.
- **Omission beats invention**: a mapping the scan cannot determine is named as such, not guessed.
- **Decided in this item**: a new skill, or a mode of `architecture-scan`.

**Acceptance Criteria**:
- [ ] For a named area, the scan proposes requirements and a mapping of the closed items, and writes nothing
- [ ] Applying an approved proposal goes through `design-record` and the item headers of XAS-044b
- [ ] A mapping the scan cannot determine is listed as undetermined
- [ ] Used on shortcuts px-proxy (SC-073c)
- [ ] The plugin version is bumped (minor)
