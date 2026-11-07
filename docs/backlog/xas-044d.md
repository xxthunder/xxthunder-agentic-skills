# [XAS-044d] Read-only requirements scan for bootstrapping

**Status**: Open
**Priority**: Medium
**Component**: a read-only requirements scan (new skill, or a mode of `architecture-scan`)
**Depends on**: [XAS-044a](xas-044a.md), [XAS-044b](xas-044b.md), [XAS-044c](xas-044c.md)

**Summary**:
As the maintainer of an existing repository that adopts sphinx-needs, I want a read-only scan that proposes requirements from the code, tests and user docs of one area, so that traceability can be retrofitted onto a repository with history.

**Description**:
It follows `architecture-scan` ([ADR-0003](../adr/0003-one-writer-for-the-design-record.md), [ADR-0005](../adr/0005-bootstrap-architecture-never-reconstruct-adrs.md)): derive from what is true now, propose, and let `design-record` apply what the author approves.

It does not replay stories: their deltas include reversed and superseded decisions. In shortcuts, SC-040 says px does not start at logon and SC-067 says it does; only the code, its tests and the runbook say which is true.

**Scope Decisions**:
- **One area at a time**: the scan takes an area (a tool, a component); shortcuts starts with px-proxy.
- **No mapping of closed items** (2026-11-07, XAS-044): items are history and link to no requirement, so the scan proposes requirements only.
- **Omission beats invention**: behaviour the scan cannot determine — code, tests and docs disagree, or say nothing — is named as open, not guessed.
- **Decided in this item**: a new skill, or a mode of `architecture-scan`.

**Acceptance Criteria**:
- [ ] For a named area, the scan proposes requirements, and writes nothing
- [ ] Applying an approved proposal goes through `design-record`
- [ ] Behaviour the scan cannot determine is listed as open
- [ ] Used on shortcuts px-proxy (SC-073c)
- [ ] The plugin version is bumped (minor)
