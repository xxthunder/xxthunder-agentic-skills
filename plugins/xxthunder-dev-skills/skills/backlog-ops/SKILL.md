---
name: backlog-ops
description: "Apply lifecycle operations to a backlog item — pull (Open → In Progress), tick an acceptance or UAT criterion, or close an item (→ Done) with automatic epic-status cascade. Stages file edits and never produces its own commit in the repository; a pull is handed to commit-helper for the default branch, and a configured Kanban board gets the item's card moved on pull and close. Trigger with: 'start XAS-025', 'pull XAS-025', 'mark AC 2 done on XAS-025', 'tick UAT 1 on XAS-025', 'close XAS-025', 'complete XAS-025'."
user_invocable: true
allowed-tools: Bash(uv run ${CLAUDE_PLUGIN_ROOT}/scripts/backlog.py *), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/store *)
---

<!-- Source: https://github.com/xxthunder/xxthunder-agentic-skills/tree/develop/plugins/xxthunder-dev-skills/skills/backlog-ops -->

# Backlog Operations

Mechanical lifecycle operations on a single backlog item: **pull**, **check** (tick an AC/UAT box), **complete**. Status changes go through the plugin's backlog script, which writes the item file, applies the epic-status cascade described in [references/epic-cascade.md](references/epic-cascade.md), and regenerates the `README.md` table of contents from the items:

```bash
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/backlog.py" <command>
```

Its commands and output are described in `refinement`'s `references/backlog-format.md` ("The backlog script"). **A non-zero exit ends the operation**: show the script's message and stop.

This skill **edits and stages files**; it never creates a commit in this repository itself. A **pull** is the one operation that reaches the default branch at once: it is handed to `commit-helper` for a commit of its own, and pushed ([Pull](#pull-open--in-progress), steps 4–5). A check or a complete stays staged for the user, who commits it on the feature branch — a ticked criterion with the code it claims, a close as the branch's last commit.

When a **board** is configured on the machine, a pull and a complete also move the item's card on it — one commit in the board's store, never in this repository ([Board move](#board-move)).

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
- A `README.md` in the same folder whose table of contents is derived from the items; the item's own `**Status**:` line is its status
- Item headings are `# [PREFIX-###] Title` or `# [PREFIX-###<letter>] Title`
- Item files carry a `**Status**:` line
- Acceptance Criteria are GitHub-flavored checkboxes (`- [ ]` / `- [x]`) under a `**Acceptance Criteria**:` heading; optionally also a `**UAT**:` or `**User Acceptance Tests**:` block with the same checkbox syntax

If any of these invariants look violated, stop and ask the user rather than guessing.

## Workflow

### Step 1: Resolve the item

Given an ID like `XAS-025` or `XAS-003a`:

1. Locate the backlog directory. The script finds `docs/backlog/` from anywhere inside the repository; for a backlog elsewhere, ask the user and pass `--dir <path>` before the command.
2. Find the item file — filename is the lowercased ID (`xas-025.md`, `xas-003a.md`).
3. Read the file. Extract current `**Status**:`, the Acceptance Criteria block, and the UAT block if present.

The item's `**Status**:` line is its current status. The README follows from it; `set-status` and `toc` regenerate it.

### Step 2: Apply the operation

#### Pull (Open → In Progress)

1. Precondition: current status is `Open`. On the default branch, bring it up to date first — `git fetch`, then `git merge --ff-only @{u}`, which keeps whatever else is staged — so the status read is the one other sessions see. If already `In Progress`, report that and stop. If `Done`, refuse and ask the user to confirm intent (they may want to re-open, which is a different operation).
2. Run `set-status <ID> "In Progress"`. It writes the item, pulls an `Open` parent epic to `In Progress` along with it, and regenerates the TOC.
3. Report the script's output lines — one per status change, the cascade included.
4. **Decide where the pull lands.** *In Progress* says that someone is working on the item, and other sessions read it on the default branch — so it lands there at once, in a commit of its own, before any feature branch exists (step 5). It stays staged for the feature branch instead, and the report names the reason, when:
   - the repository's `AGENTS.md` / `CLAUDE.md` sends backlog or docs changes through a pull request — name that rule;
   - the checkout is on another branch than the default branch, such as a feature branch or its worktree;
   - the repository has no remote.
5. **Land it on the default branch:**
   1. Stage exactly the files the script changed: the item, an epic the cascade moved, and the README.
   2. Hand off to `commit-helper` for one commit `docs(backlog): pull <ID>` that holds those files and nothing else that is staged — commit them by path (`git commit -m "…" -- <files>`).
   3. Push it. A push rejected as non-fast-forward: `git pull --rebase --autostash`, then push once more; other changes that were staged come back unstaged — say so.
   4. When `commit-helper` makes no commit, or the remote refuses the push for any other reason — a protected branch, a hook — the pull stays staged for the feature branch, and the report quotes the message. If the pull commit was made, undo it with `git reset --soft HEAD~1`, so the default branch matches its remote again.
   5. The feature branch for the work starts from the pushed commit.
6. **Move the card** into the in-progress column — whether the pull landed on the default branch or stayed staged ([Board move](#board-move)).

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

3. Run `set-status <ID> Done`. It writes `**Status**: Done (YYYY-MM-DD)` dated today from the system clock (pass `--date YYYY-MM-DD` when the user names another day), adds the `✅ DONE -` heading prefix, and regenerates the TOC. It refuses to close an epic while a substory is neither Done nor Superseded.
4. **Take the card off the board** ([Board move](#board-move)) — for this item only; an epic closed by the cascade below has no card.
5. **Epic cascade**: when the script prints `<PARENT>: every substory is closed; the epic can be closed`, prompt the user: "All substories of `PREFIX-###` are now closed. Close the epic too?" If yes, run the Complete operation on the parent (its ACs still get the same precondition check — an epic may have its own ACs independent of substory completion).
6. Report: the script's output lines, the board move or why there was none — only when a board is configured —, any cascade decisions (accepted or deferred), and whether a binding-design candidate was found and what the user chose.

### Board move

A board is the author's Kanban board in a store of its own, configured on the machine by the variable pair `BOARD_PATH` / `BOARD_REMOTE` — never named in this repository or in this file. This step only runs from a pull or a complete above.

1. **Resolve the store**:
   ```bash
   "${CLAUDE_PLUGIN_ROOT}/scripts/store" resolve BOARD
   ```
   Exit 2 means no board is configured: skip this step silently — the operation behaves exactly as it would without one. Any other non-zero exit: keep the script's message for the summary and skip the step. The pull or complete stands either way.
2. **Read the contract** — the section headed `Board` in the store's `AGENTS.md`, following its imports:
   ```bash
   "${CLAUDE_PLUGIN_ROOT}/scripts/store" contract "<store>" Board
   ```
   A non-zero exit: keep the message for the summary and skip the step. The contract names the board file, its columns and order, the card format and link, and the commit subject — this skill ships none of them.
3. **Address the card** as the contract says, with this repository's name and the item ID. A repo the contract's registry does not list: name the missing row in the summary and write no card.
4. **Move it**:
   - after a **pull**: read the item with
     ```bash
     uv run "${CLAUDE_PLUGIN_ROOT}/scripts/backlog.py" show --in-progress <ID>
     ```
     It prints the item's line only when the item is In Progress *as work* — never for an epic or the ongoing refinement item, which get no card. No line → no card, nothing to do. Otherwise the item's card goes into the in-progress column at the place the contract names — out of the waiting column if it is there, newly made otherwise — with the title exactly as the script prints it. A card already in the in-progress column is left where it is.
   - after a **complete**: the item's card leaves the board. No card → nothing to do.

   Only the item named in the operation moves; keep every other card exactly as it was, in the layout the contract names.
5. **Commit and push the board file alone**, with the contract's subject — only when step 4 changed it; nothing changed, no commit:
   ```bash
   "${CLAUDE_PLUGIN_ROOT}/scripts/store" commit-push "<store>" "<subject>" <board-file>
   ```
   The script commits only the named file, so whatever else is staged — in the store, or in this repository when it is the store — stays staged. A rejected push or a conflict is reported in the summary; the script keeps the commit locally, and the pull or complete stands. Never resolve conflicts in the store.

### Step 3: Summarize staged changes

Print a short summary: files edited, lines changed (conceptually — "ticked AC 2", "moved XAS-025 from Open to In Progress"), and any cascade actions. After a pull or a complete with a board configured, name the board move and its commit — or why there was none; say nothing about a board when none is configured. After a pull, name the commit and the push — or why the pull stayed staged. After a check or a complete, remind the user:

> Staged but not committed. Review with `git diff --cached` and commit it on the feature branch via `commit-helper` — a ticked criterion with the code it claims, a close as the branch's last commit.

Then, after a **pull** or a **complete** only, one last line — a suggestion, never a call:

- after a pull: *Log the start with `logbook start`?*
- after a complete: *Log the close with `logbook done`?* — naming every item closed in this
  invocation (a substory and its cascaded epic get one suggestion, not two). `logbook done`
  is also where the question whether anything outlives the repo is asked; this skill never
  asks it itself.

This skill does not know whether a logbook is configured; `logbook` finds out and says so.

## What This Skill Does NOT Do

- **No commits of its own** in this repository. A pull is handed to `commit-helper` (Pull, step 5); every other backlog edit is committed by the user on the feature branch. The one commit this skill makes is the [board move](#board-move), in the board's store.
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
- **The TOC belongs to the script.** Every change to it goes through `set-status` or `toc`; the item files are what you edit.
- **Done lands with the code.** A check or a complete stays staged for the user, so *Done* and every ticked criterion reach the default branch with the work they claim.

## Integration Points

- **Boundary transitions come from this skill's own triggers** — "start XAS-025" at the beginning of a unit of work, "tick AC 2 on XAS-025" as criteria are met, "close XAS-025" at the end. No other skill needs to drive them, and none should auto-check ACs mid-flight: only the user knows which criterion a given change satisfied.
- **`commit-helper`** commits a pull on its own, on the default branch, at once; it commits every other staged backlog edit on the feature branch — a ticked criterion with its code, a close as the last commit. Mention the backlog ID in the commit subject or body per conventional-commit practice.
- **`refinement`** hands off to this skill for any status mutation; it does not edit `**Status**:` fields directly.
- **`design-record`** receives the hand-off from the binding-design check on Complete. Closing an item is the last moment to lift design that outlives it into the ADR log, because nothing keeps a closed item current.
- **`next`** shows the board this skill moves cards on; both read the store's `Board` contract. This skill never ranks — placing a card in the waiting column is `next put`.
- **`logbook`** is suggested — one line, never invoked — after a pull and after a close, so a
  session's start and end can reach a cross-repo chronicle without this skill knowing
  whether one exists.
