# [XAS-070b] The closed loop takes a GitHub issue as its item

**Status**: Open
**Priority**: Medium
**Component**: `plugins/xxthunder-dev-skills/skills/closed-loop/SKILL.md`, `plugins/xxthunder-dev-skills/scripts/host.py`
**Depends on**: [XAS-070a](xas-070a.md)

**Summary**:
As the author, I want to put a GitHub issue into the closed loop, so that a repository
without a backlog of its own, such as an upstream project, can take part.

**Description**:
On 2026-11-05 a run for `spl-core #382` had to resolve the repository by name and take the
issue text as the item by hand. With [XAS-070a](xas-070a.md) the address resolves; what is
left is reading the issue as the item and linking it from the evidence package. A GitHub
issue lives in its repository and is as public as the repository, so it needs none of the
care a Jira issue needs ([XAS-070c](xas-070c.md)).

**Acceptance Criteria**:
- [ ] "put spl-core #382 in the loop" reads the issue (title, body, comments) through
      `host.py` as the item and runs the loop in spl-core
- [ ] The pull moves the issue's card into *In Progress* and writes nothing to GitHub
- [ ] The evidence package's *Item* section links the issue
- [ ] An eval case covers the GitHub path with a stand-in for GitHub
