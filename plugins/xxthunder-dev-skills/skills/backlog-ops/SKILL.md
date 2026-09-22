---
name: backlog-ops
description: "Apply lifecycle operations to a backlog item — pull (Open → In Progress), tick an acceptance or UAT criterion, or close an item (→ Done) with automatic epic-status cascade. Stages file edits only; never produces its own commit. Trigger with: 'start XAS-025', 'pull XAS-025', 'mark AC 2 done on XAS-025', 'tick UAT 1 on XAS-025', 'close XAS-025', 'complete XAS-025'."
user_invocable: true
---

<!-- Source: https://github.com/xxthunder/xxthunder-agentic-skills/tree/develop/plugins/xxthunder-dev-skills/skills/backlog-ops -->

# Backlog Operations

Mechanical lifecycle operations on a single backlog item: **pull**, **check** (tick an AC/UAT box), **complete**. Every operation keeps the item file and the `README.md` table of contents consistent and respects the epic-status cascade described in [references/epic-cascade.md](references/epic-cascade.md).

This skill **stages file edits only**. It never creates a commit. Commits are the user's call (typically via the `commit-helper` skill) so the backlog change can ride in the same commit as the code change that justifies it.

## When This Skill Triggers

| Trigger phrase                                  | Operation | Section                           |
|-------------------------------------------------|-----------|-----------------------------------|
| "start XAS-025", "pull XAS-025", "begin XAS-025" | pull      | [Pull](#pull-open--in-progress)   |
| "mark AC 2 done on XAS-025", "tick AC 1 for XAS-025", "check UAT 3 on XAS-025" | check     | [Check](#check-tick-an-acuat-box) |
| "close XAS-025", "complete XAS-025", "finish XAS-025", "mark XAS-025 done" | complete  | [Complete](#complete-in-progress--done) |

Do **not** trigger on refinement phrases ("let's refine", "add a new story") — those belong to the `refinement` skill.

## Core Assumptions

The skill assumes the backlog follows the format documented by the `refinement` skill:
- One markdown file per item at `docs/backlog/<prefix>-###[<letter>].md` (or equivalent — discover the directory by locating `README.md` in the repo's backlog folder)
- A `README.md` in the same folder whose `### Open` / `### In Progress` / `### Done` sections list items and are the authoritative status
- Item headings are `# [PREFIX-###] Title` or `# [PREFIX-###<letter>] Title`
- Item files carry a `**Status**:` line
- Acceptance Criteria are GitHub-flavored checkboxes (`- [ ]` / `- [x]`) under a `**Acceptance Criteria**:` heading; optionally also a `**UAT**:` or `**User Acceptance Tests**:` block with the same checkbox syntax

If any of these invariants look violated, stop and ask the user rather than guessing.

## Workflow

### Step 1: Resolve the item

Given an ID like `XAS-025` or `XAS-003a`:

1. Locate the backlog directory (look for `docs/backlog/README.md`, `BACKLOG.md`, or ask the user).
2. Find the item file — filename is the lowercased ID (`xas-025.md`, `xas-003a.md`).
3. Read the file. Extract current `**Status**:`, the Acceptance Criteria block, and the UAT block if present.
4. Read the backlog `README.md` and note which section currently lists the item.

If the file's `**Status**:` and the README section disagree, **the README wins** — treat that as the current status and flag the mismatch so the user can decide whether to resync.

### Step 2: Apply the operation

#### Pull (Open → In Progress)

1. Precondition: current status is `Open`. If already `In Progress`, report that and stop. If `Done`, refuse and ask the user to confirm intent (they may want to re-open, which is a different operation).
2. In the item file: replace `**Status**: Open` with `**Status**: In Progress`.
3. In `README.md`: move the item's TOC line from the `### Open` section to the `### In Progress` section. Preserve the ID-based sort order within the target section.
4. **Epic cascade**: if the item is a substory (`PREFIX-###<letter>`) and the parent `PREFIX-###` is currently in `### Open`, move the parent to `### In Progress` as well (and update the parent file's `**Status**:` if it carries one). See [references/epic-cascade.md](references/epic-cascade.md).
5. Report the changes (files touched, old → new status, cascade if any).

#### Check (tick an AC/UAT box)

1. Identify which checkbox to tick. The user specifies either:
   - **By index**: "AC 2" / "UAT 1" — 1-based index into the checkbox list under the named section.
   - **By substring**: "the 'deterministic output' AC" — match against the checkbox text, first substring hit wins.
2. Precondition: the checkbox is currently `- [ ]`. If already `- [x]`, report and stop.
3. In the item file: replace that single `- [ ]` with `- [x]`. Do not touch any other checkbox.
4. Do **not** change the item's `**Status**:` or the README — ticking criteria does not move an item between sections. Status transitions happen only on pull / complete.
5. Report which criterion was ticked and how many remain unchecked.

#### Complete (→ Done)

1. Precondition checks:
   - Current status is `In Progress` (or `Open` — warn that the item skipped `In Progress`, ask the user to confirm).
   - All Acceptance Criteria checkboxes are `- [x]`. If any remain unchecked, list them and ask the user whether to force-complete. Do not silently complete an item with open ACs.
   - If a UAT block exists and has unchecked boxes, apply the same rule.
2. **Binding-design check** (only if the repo keeps a record — an ADR directory or an architecture document). Read the item's `Description` and `Scope Decisions`, and look for statements that no linked ADR already covers and that pass the **same three-part test `design-record` applies**: the consequences outlive this item, a competent engineer could have chosen otherwise, and the reason is not recoverable from the code. A closed item stays in the repo but stops being kept current, so design left inside it stops being true of anything — findable, but no longer describing the product.

   Apply all three parts, not just the first. `design-record` runs the same test on arrival and stops if it fails, so nominating on "this outlives the item" alone produces a hand-off that gets refused.

   If you find candidates, name them and ask once:

   > `PREFIX-###` states: "<the statement>". That looks like it outlives this item and no ADR covers it. Record it with `design-record` before closing?

   - **Yes** → hand off to `design-record`, then return here and continue with the item-file edit below.
   - **No**, or nothing found → continue with the item-file edit below.

   ("Below" means the next numbered item in this Complete list — not the `### Step 3` heading further down the page.)

   This check **prompts and hands off**. It never authors the ADR itself, and it never blocks the close — declining completes the item as normal. Enforcement is out of scope by design.

3. In the item file:
   - Replace `**Status**: In Progress` with `**Status**: Done (YYYY-MM-DD)` using today's date (ask the user or read from the environment; never fabricate).
   - Prefix the top-level heading with `✅ DONE -` if not already present, e.g. `# [XAS-025] Title` → `# [XAS-025] ✅ DONE - Title`.
4. In `README.md`: move the item's TOC line from its current section to `### Done`. Keep `### Done` sorted by ID.
5. **Epic cascade**: if the item is a substory, re-evaluate the parent:
   - If **all** siblings (including this item's new Done state) are `Done`, prompt the user: "All substories of `PREFIX-###` are now Done. Close the epic too?" If yes, run the Complete operation recursively on the parent (its ACs still get the same precondition check — an epic may have its own ACs independent of substory completion).
   - Otherwise, leave the parent where it is. If the parent was incorrectly sitting in `### Open` while any substory was `In Progress` or `Done`, correct it to `### In Progress`.
6. Report: status transition, which section of README was updated, any cascade decisions (accepted or deferred), and whether a binding-design candidate was found and what the user chose.

### Step 3: Summarize staged changes

Print a short summary: files edited, lines changed (conceptually — "ticked AC 2", "moved XAS-025 from Open to In Progress"), and any cascade actions. Then remind the user:

> Staged but not committed. Review with `git diff` and commit alongside the related code change (e.g., via `commit-helper`).

Then, after a **pull** or a **complete** only, one last line — a suggestion, never a call:

- after a pull: *Log the start with `logbook start`?*
- after a complete: *Log the close with `logbook done`?* — naming every item closed in this
  invocation (a substory and its cascaded epic get one suggestion, not two). `logbook done`
  is also where the question whether anything outlives the repo is asked; this skill never
  asks it itself.

This skill does not know whether a logbook is configured; `logbook` finds out and says so.

## What This Skill Does NOT Do

- **No commits.** Ever. The backlog edit rides in the user's next commit.
- **No new items.** Creating items is `refinement`'s job.
- **No AC authoring.** Editing AC text is `refinement`'s job.
- **No ADR authoring.** The binding-design check names a candidate and hands off. `design-record` is the record's only writer.
- **No sprint / velocity / estimation concepts.** Out of scope by design.
- **No guessing which AC a code change satisfied.** The user names the AC to tick; the skill does not infer.
- **No reverse transitions without explicit confirmation.** Re-opening a Done item or moving In Progress back to Open requires the user to spell it out.

## Guidelines

- **One operation per invocation.** If the user says "pull XAS-025 and tick AC 1", do pull first, report, then do the check. Report each step — do not batch silently.
- **Be explicit about cascades.** If moving a substory caused the parent epic to move, say so in the summary.
- **Refuse ambiguity.** If "mark AC done on XAS-025" doesn't say which AC, ask — don't pick one.
- **Preserve file formatting.** Don't reflow markdown, renumber lists, or touch anything outside the specific lines the operation requires.
- **Preserve TOC sort order.** Within each status section, TOC entries are sorted by ID. Insert at the right position, don't append blindly.
- **Never auto-commit.** Always leave the changes staged for the user.

## Integration Points

- **Boundary transitions come from this skill's own triggers** — "start XAS-025" at the beginning of a unit of work, "tick AC 2 on XAS-025" as criteria are met, "close XAS-025" at the end. No other skill needs to drive them, and none should auto-check ACs mid-flight: only the user knows which criterion a given change satisfied.
- **`commit-helper`** commits the staged backlog edit alongside the code change. Mention the backlog ID in the commit subject or body per conventional-commit practice.
- **`refinement`** hands off to this skill for any status mutation; it does not edit `**Status**:` fields directly.
- **`design-record`** receives the hand-off from the binding-design check on Complete. Closing an item is the last moment to lift design that outlives it into the ADR log, because nothing keeps a closed item current.
- **`logbook`** is suggested — one line, never invoked — after a pull and after a close, so a
  session's start and end can reach a cross-repo chronicle without this skill knowing
  whether one exists.
