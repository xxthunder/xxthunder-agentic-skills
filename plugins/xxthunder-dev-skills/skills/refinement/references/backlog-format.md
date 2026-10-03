# Backlog Format Reference

This defines the backlog structure, entry format, and conventions used by the refinement skill. Use this reference when creating a new backlog or adding entries to an existing one.

## File Structure

The backlog uses a flat folder with one file per item. All items live in the same directory regardless of status or hierarchy:

```
docs/backlog/
├── README.md             # Status legend, flat TOC, Notes
├── prefix-001.md         # Top-level item (story or epic)
├── prefix-002.md
├── prefix-003.md         # Epic (has substories)
├── prefix-003a.md        # First substory of PREFIX-003
├── prefix-003b.md        # Second substory of PREFIX-003
└── prefix-015.md
```

The **item files are the single source of truth**: an item's status is its own `**Status**:` line. The README's table of contents is derived from the items by the backlog script and regenerated after every change — see [The backlog script](#the-backlog-script).

### `README.md`

Contains only metadata and navigation — no item content, no hierarchy groupings. The TOC is flat: each item lives in the section that matches **its own** status — an epic and its substories may sit in different sections at the same time. The letter-suffix ID convention visually groups epic and substory *only within a single section*, because each section lists the newest ID first.

```markdown
# Backlog

## Status Legend

- **Open** - Ready to be picked up
- **In Progress** - Currently being worked on
- **Done** - Completed

## Table of Contents

### Open
- [PREFIX-015 — Standalone story](prefix-015.md)
- [PREFIX-003c — Third substory](prefix-003c.md)
- [PREFIX-003b — Second substory](prefix-003b.md)

### In Progress
- [PREFIX-003a — First substory (being worked on)](prefix-003a.md)
- [PREFIX-003 — Epic title](prefix-003.md)
- [PREFIX-001 — Ongoing refinement](prefix-001.md)

### Done
- [PREFIX-002 — Completed item](prefix-002.md)

---

## Notes

- **ID prefix**: `PREFIX` (e.g., `HSH` for HomeSweetHome)
- Keep items actionable with clear acceptance criteria
- Do NOT list commit hashes in backlog entries — the backlog is part of the commit itself, so hashes are circular and go stale after squash/rebase
```

Note in the example above: `PREFIX-003` is an In-Progress epic. One of its substories (`PREFIX-003a`) has been pulled and appears next to the epic in `### In Progress`. The other two substories (`PREFIX-003b`, `PREFIX-003c`) are still `Open` and sit in `### Open`. This is the normal state while an epic is being worked through — substories scatter across sections as they transition individually.

**No "Stories under X" groupings.** Each item sorts into the section its own status dictates; newest-first ID order within a section keeps related IDs adjacent when they happen to share a status.

### Item files

Each item is a standalone file in the backlog folder. The heading is `#` (top-level, since it's the only item in the file):

```markdown
# [PREFIX-015] Brief descriptive title

**Status**: Open
**Priority**: Medium
**Component**: `path/to/affected/file.ext`

**Summary**:
As a [user role], I want [feature] so that [benefit].

**Description**:
[Problem statement. Current behavior. Why this matters.]

**Acceptance Criteria**:
- [ ] First verifiable criterion
- [ ] Second verifiable criterion
- [ ] All existing tests continue to pass
```

## The backlog script

Every mechanical step goes through one script that ships with this plugin. It needs `uv` on PATH.

```bash
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/backlog.py" <command>
```

| Command | What it does |
|---------|--------------|
| `next-id` | Prints the next free top-level ID; the prefix comes from the README's Notes |
| `next-id PREFIX-NNN` | Prints the next substory ID under `PREFIX-NNN` |
| `set-status ID STATUS` | Sets `Open`, `"In Progress"`, `Done` or `Superseded` — status line, date, heading marker, epic cascade — and regenerates the TOC |
| `toc` | Regenerates the README's table of contents from the items |
| `check` | Lists every problem in the backlog, one per line; exit 1 if there is one |

Run it from anywhere inside the repository; it finds `docs/backlog/` by walking up. For a backlog elsewhere, put `--dir <path>` before the command.

**A non-zero exit ends the operation.** Show the script's message to the user and stop. The fix belongs in the item the message names, or — when the message names a README line — in moving that line out of the table of contents.

## Item ID Convention

Two shapes of ID:

| Shape               | Meaning                                   | Example        |
|---------------------|-------------------------------------------|----------------|
| `PREFIX-###`        | Top-level item (story OR epic)            | `HSH-003`      |
| `PREFIX-###<letter>`| Substory under the matching top-level item | `HSH-003a`     |

- The prefix is a short, memorable abbreviation of the repository/project name (e.g., `HSH` for HomeSweetHome).
- The three-digit number is zero-padded and **global and sequential** across top-level items.
- Substory letters start at `a` and continue `b`, `c`, … in the order substories are added. No gaps are intentional.
- There is **no explicit "Epic" type field**. An item *is* an epic if (and only if) at least one `PREFIX-###<letter>` sibling file exists. Epic-ness is emergent — a top-level story is "promoted" to an epic simply by adding its first substory.
- The prefix is stored in the **Notes** section of `README.md` so it is always discoverable.

Examples:
- `HSH-003` — top-level story. Becomes an epic if/when `HSH-003a` is added.
- `HSH-003a`, `HSH-003b` — substories of `HSH-003`.
- `HSH-015` — top-level story with no substories.

### Allocating the next ID

**New top-level item**: `next-id`. It takes the highest number among the backlog's own prefix and adds one.

**New substory under `PREFIX-NNN`**: `next-id PREFIX-NNN`. It advances past the latest letter used, or starts at `a`. If the parent is currently a standalone story, no rename is needed — adding the first substory implicitly promotes it.

### Back-reference fields (do not use)

Do **not** add a `**Epic**: PREFIX-###` field inside substory files. The letter suffix encodes the parent — adding an explicit back-reference duplicates information and drifts on rename.

## Entry Fields

### Required fields (all entries)

| Field                  | Description                                              |
|------------------------|----------------------------------------------------------|
| **Status**             | `Open`, `In Progress`, `Done (YYYY-MM-DD)`, or `Superseded (YYYY-MM-DD)` for an item replaced by another |
| **Priority**           | `High`, `Medium`, `Low`, or `—` (none)                  |
| **Component**          | File path(s) affected (e.g., `roles/ssl-certify/`)       |
| **Summary**            | User story: "As a [user], I want [feature] so that [benefit]" |
| **Description**        | Detailed problem statement, current state, rationale     |
| **Acceptance Criteria**| Checkbox list: `- [ ] Criterion` (unchecked) / `- [x] Criterion` (checked) |

### Optional fields

| Field                    | When to include                                     |
|--------------------------|-----------------------------------------------------|
| **Depends on**           | When blocked by another item (e.g., `HSH-006`)     |
| **Related**              | When related to other items (not blocking)           |
| **Scope Decisions**      | When key architectural choices have been made        |
| **Technical Notes**      | Implementation-specific details (socket paths, config snippets) |
| **Dependencies**         | External system prerequisites                        |
| **Related Documentation**| Links to guides or external references               |

### Epic-only content

A top-level item that has (or will have) substories may include a narrative **Substories** section listing the children by ID and title. This is purely informative — each substory's status is its own `**Status**:` line, not this list. Keep it as a bulleted list of `PREFIX-###<letter> — title` entries.

### Open entry

File: `prefix-015.md`

```markdown
# [HSH-015] Brief descriptive title

**Status**: Open
**Priority**: Medium
**Component**: `path/to/affected/file.ext`

**Summary**:
As a [user role], I want [feature] so that [benefit].

**Description**:
[Problem statement. Current behavior. Why this matters.]

**Acceptance Criteria**:
- [ ] First verifiable criterion
- [ ] Second verifiable criterion
- [ ] All existing tests continue to pass
```

### In Progress entry

Same as Open but with `**Status**: In Progress` and some criteria may be checked off.

### Completed entry

File: `prefix-001.md`

```markdown
# [HSH-001] ✅ DONE - Brief descriptive title

**Status**: Done (YYYY-MM-DD)
**Priority**: Medium
**Component**: `path/to/affected/file.ext`

[... all other fields with all acceptance criteria checked ...]
```

### TOC format (in `README.md`)

`toc` writes the block under `## Table of Contents`, up to the next `## ` heading or `---` rule:

- **Sections in a fixed order**: `### Open`, `### In Progress`, `### Done`, then `### Superseded` only when an item has that status.
- **Newest ID first** in every section. The sort key is prefix, then number, then letter, so an epic sits below its own substories and a legacy prefix forms a block of its own.
- **One line per item**: `- [ID — title](file)`, the title taken from the item heading without the `✅ DONE -` marker. Nothing else goes on the line; what an item needs to say, it says in its own file.

```markdown
### Open
- [HSH-015 — Brief title](hsh-015.md)
- [HSH-003c — Third substory (still open)](hsh-003c.md)

### In Progress
- [HSH-003a — First substory (being worked on)](hsh-003a.md)
- [HSH-003 — Epic title](hsh-003.md)
- [HSH-001 — Backlog refinement](hsh-001.md)

### Done
- [HSH-003b — Second substory (finished)](hsh-003b.md)
- [HSH-002 — Completed item](hsh-002.md)
```

An epic and its substories are not constrained to share a section. Each row sits in the section for **its own** status. Anything else in the block — a note, a checklist — makes `toc` refuse; it belongs below the table of contents.

## Plans Versus Items

An implementation plan — `superpowers:writing-plans` output, or any equivalent —
is a **task breakdown and a sequence**. The backlog item is the design; the plan
is the order of work.

Two rules keep them from collapsing into each other:

- **A plan that reproduces the design is a spec under another name.** If it
  carries the finished text of the files it is planning, or restates the
  reasoning already in the item, that content belongs in the item. A second
  copy of a design drifts from the first, and the plan is the copy nobody
  maintains.
- **A plan is deleted once its stories close.** It stops being true of anything
  when the work lands. Leaving it turns a working document into a stale account
  of a design, findable but wrong.

Both were learned from a real failure rather than reasoned out: a plan written
for two stories in this plugin's own repository ran 743 lines, 64% of it inside
code fences holding the complete text of three files that then shipped. It
duplicated the items it was planning from, and after those items were corrected
it was the last place still carrying the superseded wording.

## Epics and Status Cascade

An epic has no status of its own in the usual sense — its status is derived from its substories:

| Substory states                                        | Epic status   |
|--------------------------------------------------------|---------------|
| All substories `Done`                                  | `Done`        |
| At least one substory `In Progress`                    | `In Progress` |
| All substories `Open` (and none `In Progress`/`Done`)  | `Open`        |
| Mix of `Open` and `Done` (no `In Progress`)            | `In Progress` |

**Practical rule:** an epic stays out of `Done` as long as any substory is not `Done`.

`set-status` applies the cascade: a substory leaving `Open` pulls an `Open` epic to `In Progress`, and an epic cannot be set `Done` while a substory is neither `Done` nor `Superseded`. When the last substory closes, the script says so; closing the epic is the user's call.

An epic may also carry its own acceptance criteria (e.g., "End-to-end smoke test passes across all substories"). Those are checked independently. Avoid redundant ACs like "Child stories X/Y/Z completed" — substory completion is tracked by the cascade, not by a checkbox.

## Ongoing Refinement Item

Every backlog should include an ongoing refinement item that is never completed. All refinement commits reference this ID:

File: `prefix-0xx.md`

```markdown
# [PREFIX-0XX] Backlog refinement

**Status**: In Progress
**Priority**: —

**Description**:
Ongoing backlog refinement — create, review, clarify, and update user stories. Add research findings, scope decisions, acceptance criteria, and implementation details as needed. This item is never completed; all refinement commits reference this ID.
```

## Status Transitions

```
Open → In Progress → Done
                   ↘ Superseded (replaced by another item)
```

Change a status with `set-status ID STATUS`. It writes the `**Status**` line (dated today for `Done` and `Superseded`), adds or removes the `✅ DONE -` heading prefix, applies the epic cascade above, and regenerates the TOC.

No file moves needed — all items stay in the same folder.

## Legacy IDs

A backlog created before the letter-suffix convention may contain Done substories that use bare sequential IDs (e.g., `PREFIX-018` was a child of `PREFIX-015` even though its ID has no letter suffix). These are left alone — renaming closed items churns git history and commit references for no practical gain. The convention applies going forward; the **Substories** list in an epic may mix legacy bare IDs and new letter-suffix IDs during the transition period.
