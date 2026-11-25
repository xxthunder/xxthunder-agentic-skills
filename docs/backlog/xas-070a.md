# [XAS-070a] One resolver turns every item address into its kind and repository

**Status**: Open
**Priority**: Medium
**Component**: `plugins/xxthunder-dev-skills/scripts/` (a resolver, new), `plugins/xxthunder-dev-skills/scripts/board.py`, `plugins/xxthunder-dev-skills/scripts/loop.py`, `plugins/xxthunder-dev-skills/skills/closed-loop/SKILL.md`, `plugins/xxthunder-dev-skills/skills/backlog-ops/SKILL.md`, `docs/adr/`

**Summary**:
As the author, I want one script to decide what an item address means, so that every skill
and script treats a backlog item, a GitHub issue and a Jira issue the same way.

**Description**:
The registry gives each repository an `IDs` cell: the prefix of its backlog, or `#` when it
has none (`asf/CONVENTIONS.md` of the store). The board and the log address an issue of a
repository without a backlog as `<repo> #<n>`, and a Jira issue as `<name> <KEY-123>`.

Today three places each work out what an address means, and each knows only part of it:

| Where | How it reads the registry | Knows `#<n>` | Knows Jira |
|---|---|---|---|
| `board.py` (`read_registry`, `check_id`) | its own typed parser of both tables | yes | yes |
| `loop.py row` (`find_row`), called by `closed-loop` | a generic table lookup without types | no | no |
| `backlog-ops` SKILL.md (resolve the item) | in prose: own prefix, Jira key, another repository's prefix | no | yes |

The `#` bug follows from this. `loop.py row <registry> "Repo,Remote" IDs "#"` treats `#` as a
prefix and returns the first of the many rows without a backlog, which was another
repository. The general rubric already asks for one source of truth; a reviewer did not
catch the duplication, because it grew over several pull requests and no single diff
showed it. So the guard is a test in the gate, not a rubric line.

**Scope Decisions**:
- 2026-11-25: The order of resolution is fixed once: the current backlog's own prefix first,
  as `backlog-ops` rules today, then a Jira project key, then another repository's prefix.
  `#` is never a prefix; an issue address takes its repository from the name in front.

**Acceptance Criteria**:
- [ ] One script resolves `<PREFIX>-<n>`, `<repo> #<n>` and `<KEY>-<n>` to one typed answer:
      the kind (backlog item, issue, Jira issue), the repository, its remote and its web link
- [ ] A Jira address without a named repository resolves to its project and says that a
      repository is needed. It names no repository
- [ ] `#` matches no registry row as a prefix
- [ ] `board.py`, `closed-loop` and `backlog-ops` resolve addresses through this script.
      `loop.py row` is gone or no longer reads the `IDs` column
- [ ] A test in the gate fails when a script other than the resolver reads the registry
- [ ] An ADR records that an item address is resolved in one place
