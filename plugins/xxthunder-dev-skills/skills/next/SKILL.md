---
name: next
description: "Show the author's Kanban board — what is in progress and what comes next across all of the author's repositories — from one board file in the author's personal store, with each card's status and priority read fresh from its own backlog. Also places a card on the board or drops one. Use on '/next', 'what's next', 'was steht an' — when asked about the work backlog across repos, not about plans in general; and on 'put HSH-089 next', 'put X after Y', 'drop X from the board'. Never writes into the current repository; the store is configured on the machine and never named in any repo."
user_invocable: true
allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/scripts/store *), Bash(uv run ${CLAUDE_PLUGIN_ROOT}/scripts/backlog.py *)
---

<!-- Source: https://github.com/xxthunder/xxthunder-agentic-skills/tree/develop/plugins/xxthunder-dev-skills/skills/next -->

# Next

Three operations on a **Kanban board** — what comes next and what is in
progress, across repos, in the author's order. `show` reads; `put` and `drop`
change the board, one commit each. `backlog-ops` moves a card on pull and
close; this skill shows the board and places cards by hand.

The items stay in their repositories. Inside one backlog, `**Priority**` says
how much an item matters; priorities from two backlogs cannot be compared, a
position on the board can. A card holds the link to its item, the item's title
and the author's reason. Status and priority are always read from the item
itself, never copied onto the board.

## The direction rule

**The board points into repositories; no repository points into the board.** A
card cites the repo and item ID it is about. No file in a consuming repo names
the store, its path or its remote — some of those repos are public. What knows
the store is the **machine**: the variable pair `BOARD_PATH` / `BOARD_REMOTE`
in the user's settings (`~/.claude/settings.json` → `env`), never in a repo.
The board may share its repository with other stores or have one of its own;
this skill only ever reads the `BOARD` pair.

## When This Skill Triggers

- **`show`** — `/next`, "what's next", "was steht an", "what am I working on" —
  when the question is about the work across repositories. Everyday use of
  the phrases ("was steht am Wochenende an?") is not a trigger: `show`
  fetches every repo on the board.
- **`put`** — "put HSH-089 next", "put OHC-004 after OHC-003", "put SC-061 at 1".
- **`drop`** — "drop HSH-089 from the board".

## Step 1: Resolve the store — fresh, every time

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/store" resolve BOARD
```

Prints the store's absolute path on stdout and brings it up to date; the
resolution order is stated once, in the script's own header. **A non-zero exit
ends the operation.** Show the script's message and stop. Never guess a store,
never fall back to the current repository, never create one.

## Step 2: Read the contract — the store's `AGENTS.md`

The rules for the board are the **store's**, stated once, in its `AGENTS.md`,
in the section headed **`Board`**.
That section may sit in a file the `AGENTS.md` pulls in with an `@path`
import line. Get it with the script, which follows the imports:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/store" contract "<store>" Board
```

Follow what it prints. It names:

- where the board is, its columns, and the order within each column
- the card format, and how a card's link is built
- which moves there are, and what a card never holds
- how a repo name resolves to its remote and to its local checkout
- the language, and the commit subject of a change

This skill ships **no board format, no path and no language of its own**. If
the script exits non-zero — the section is missing or in more than one place —
or the section names none of the items above, stop and say what
the store has to provide — do not improvise.

## Step 3: Read the items — fetched, never pulled

The rule behind this step is ADR-0010 of this plugin's home repository.

For every repo that a card on the board names:

1. **Find the checkout** the contract names. Not there → ask the author
   whether to clone it there. Yes clones it and goes on; no leaves the repo
   out, and the report says so.
2. **Read its backlog**, once per repo, with the plugin's backlog script:
   ```bash
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/backlog.py" --repo <checkout> show
   ```
   The script fetches, takes the default branch from the remote and reads the
   items there — the working tree may be behind or on a feature branch. It
   never pulls, checks out, resets or stashes: another session may be working
   in that checkout, and its working tree, index and `HEAD` stay exactly as
   they were. Do not run those commands yourself either.

   One line per item: `ID`, status, priority, title, tab-separated. An item
   that does not parse goes to stderr and the exit code is 1 — that is a
   finding, not a failure; keep the lines that did print. A non-zero exit
   with **no** lines means the repo could not be read — no remote, no backlog
   on the default branch, a failed fetch: leave the repo out and report the
   script's message.

The one output serves every card in that repo: an ID that is not in it
resolves to no item. A card without a backlog item (`<repo> #<issue>`) is
shown as written, with no status.

## `show`

Resolve, read the contract, read the items. Then print the board as **one**
table with the board's own header row — the contract's columns side by side,
never one table per column — in the board's order. Each card is one cell: its
address, its title and its reason as the board has them, plus status and
priority read from its item.

Then **contradictions — reported, never smoothed over**:

- a card whose item is Done or Superseded
- a card in the in-progress column whose item is not *In Progress*
- a card whose title differs from its item's title
- a card whose address resolves to no item, or whose repo is missing from the
  registry the contract names
- an item that does not parse, with the script's message
- a repo that was left out — not cloned, or not readable — with the reason

An item that is *In Progress* without a card is not a contradiction: a close
takes the card off the board at once, while the item reads Done on the
default branch only after its feature branch is merged.

No contradictions → say so in one line. `show` never changes anything.

## `put`

1. Resolve and read the contract.
2. The item must exist: read it as in Step 3, with its ID after `show`. No
   item → say so and stop.
3. A card for it in the in-progress column → `put` would move work back to
   waiting, a reverse transition: say so and stop.
4. Already in the waiting column → move it; otherwise make its card, with the
   title read from the item and the link the contract describes. Where: "next"
   or no position is the top — the item that comes next; "after X" directly
   below X; "at n" at position n.
5. Write the board in the contract's format, keeping every other card exactly
   as it was. Write a reason only if the author gave one; ask for one only if
   the contract requires it.
6. Commit and push that file alone with the contract's subject:
   ```bash
   "${CLAUDE_PLUGIN_ROOT}/scripts/store" commit-push "<store>" "<subject>" <board-file>
   ```
   A conflict is reported and the operation stops; never resolve conflicts
   in the store.
7. Show the board as it now stands, without fetching again.

## `drop`

1. Resolve and read the contract.
2. Not on the board → say so and stop.
3. Remove the card from its column, keeping every other card exactly as it
   was, in the layout the contract names; commit and push as in `put`. A
   reason is the author's if they gave one; never ask for one — without it,
   the subject takes what the contract names for that case.

## What This Skill Never Does

- **Pull, check out, reset or stash** in any repository other than the
  store — not even the one the session is in.
- **Write into a consuming repository.** `git status` there is unchanged.
- **Change an item's status or priority.** That is `backlog-ops`.
- **Copy status or priority onto the board.** They are read each time.
- **Clone a repository unasked.**
- **Run without configuration.** No variables, no store, no guessing.
- **Name any specific store** in its own text — not a path, not a remote,
  not a repo name. This file is installed into public repositories.

## Integration Points

- **`backlog-ops`** moves a card when a board is configured: a pull puts the
  item's card into the in-progress column, a close takes it off the board. It
  reads the same contract; this skill shows the result.
- **`backlog.py`** reads the items: `show` prints status, priority and title;
  `--repo` reads them at the remote's default branch, after a fetch.
