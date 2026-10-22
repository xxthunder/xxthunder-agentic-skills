---
name: next
description: "Show what is in progress and what comes next across all of the author's repositories, from one ranked list in the author's personal store, with each item's status and priority read fresh from its own backlog. Also places an item on the list or drops it. Use on '/next', 'what's next', 'was steht an' — when asked about the work backlog across repos, not about plans in general; and on 'put HSH-089 next', 'put X after Y', 'drop X from the next list'. `logbook done` suggests a drop. Never writes into the current repository; the store is configured on the machine and never named in any repo."
user_invocable: true
allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/scripts/store *), Bash(uv run ${CLAUDE_PLUGIN_ROOT}/scripts/backlog.py *)
---

<!-- Source: https://github.com/xxthunder/xxthunder-agentic-skills/tree/develop/plugins/xxthunder-dev-skills/skills/next -->

# Next

Three operations on a **ranked list** — what comes next, across repos, in the
author's order. `show` reads; `put` and `drop` change the list, one commit
each.

The items stay in their repositories. Inside one backlog, `**Priority**` says
how much an item matters; priorities from two backlogs cannot be compared, a
rank can. The list holds only the order. Status, priority and title are always
read from the item itself, never copied into the list.

## The direction rule

**The list points into repositories; no repository points into the list.** A
line cites the repo and item ID it is about. No file in a consuming repo names
the store, its path or its remote — some of those repos are public. What knows
the store is the **machine**. The list lives in the **logbook's store** and is
resolved with the same variable pair, `LOGBOOK_PATH` / `LOGBOOK_REMOTE`: the
list and the log are read together, so a second store would only be a second
thing to configure.

## When This Skill Triggers

- **`show`** — `/next`, "what's next", "was steht an", "what am I working on" —
  when the question is about the work across repositories. Everyday use of
  the phrases ("was steht am Wochenende an?") is not a trigger: `show`
  fetches every repo on the list.
- **`put`** — "put HSH-089 next", "put OHC-004 after OHC-003", "put SC-061 at 1".
- **`drop`** — "drop HSH-089 from the next list".

`logbook done` ends with one line suggesting a `drop` of the item it closed;
the author accepts or not.

## Step 1: Resolve the store — fresh, every time

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/store" resolve LOGBOOK
```

Prints the store's absolute path on stdout and brings it up to date; the
resolution order is stated once, in the script's own header. **A non-zero exit
ends the operation.** Show the script's message and stop. Never guess a store,
never fall back to the current repository, never create one.

## Step 2: Read the contract — the store's `AGENTS.md`

The rules for the list are the **store's**, stated once, in its `AGENTS.md`,
in the section headed **`Next`**. Read that section and follow it. It names:

- where the list is, and its order
- the line format
- how a repo name resolves to its remote and to its local checkout
- where *in progress* is read from
- the language, and the commit subject of a change

This skill ships **no list format, no path and no language of its own**. If
the section is missing or names none of the items above, stop and say what
the store has to provide — do not improvise.

## Step 3: Read the items — fetched, never pulled

The rule behind this step is ADR-0010 of this plugin's home repository.

For every repo that the list or the in-progress source names:

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
3. **Read what is in progress as work** in that repo, for `show`:
   ```bash
   uv run "${CLAUDE_PLUGIN_ROOT}/scripts/backlog.py" --repo <checkout> show --in-progress
   ```
   The same lines, only for the items In Progress as work — the script leaves
   out what is In Progress without being work that starts and ends.

The one output serves every address in that repo: an ID that is not in it
resolves to no item. An address without a backlog item (`<repo> #<issue>`) is
shown as written, with no status.

## `show`

Resolve, read the contract, read the items. Then print two blocks:

- **In progress** — every open start in the in-progress source the contract
  names, each with status, priority and title from its item.
- **Next** — the list in rank order, each line with status, priority and
  title from its item and the reason the list gives, if any.

Then **contradictions — reported, never smoothed over**:

- an item on the list whose status is Done or Superseded
- an item that `show --in-progress` prints without an open start in the
  in-progress source
- an open start in the in-progress source whose item is not *In Progress* —
  *Open* (not pulled, or pulled on a feature branch because the default
  branch takes no direct push), *Done* or *Superseded*
- an address that resolves to no item, or a repo name missing from the
  registry the contract names
- an item that does not parse, with the script's message
- a repo that was left out — not cloned, or not readable — with the reason

No contradictions → say so in one line. `show` never changes anything.

## `put`

1. Resolve and read the contract.
2. The item must exist: read it as in Step 3, with its ID after `show`. No
   item → say so and stop.
3. Already on the list → move it; otherwise insert it. Where: "next" or no
   position is rank 1 — the item that comes next; "after X" directly below
   X; "at n" at rank n.
4. Write the list in the contract's format, numbered again from 1, keeping
   every other line exactly as it was. Write a reason only if the author gave
   one; ask for one only if the contract requires it.
5. Commit and push that file alone with the contract's subject:
   ```bash
   "${CLAUDE_PLUGIN_ROOT}/scripts/store" commit-push "<store>" "<subject>" <list-file>
   ```
   A conflict is reported and the operation stops; never resolve conflicts
   in the store.
6. Show the list as it now stands, without fetching again.

## `drop`

1. Resolve and read the contract.
2. Not on the list → say so and stop.
3. Remove the line, number the list again, commit and push as in `put`.

## What This Skill Never Does

- **Pull, check out, reset or stash** in any repository other than the
  store — not even the one the session is in.
- **Write into a consuming repository.** `git status` there is unchanged.
- **Change an item's status or priority.** That is `backlog-ops`.
- **Copy status, priority or title into the list.** They are read each time.
- **Clone a repository unasked.**
- **Run without configuration.** No variables, no store, no guessing.
- **Name any specific store** in its own text — not a path, not a remote,
  not a repo name. This file is installed into public repositories.

## Integration Points

- **`logbook`** shares the store and supplies *in progress*. Its `done` ends
  with one line suggesting a `drop` of the item it closed — never a call.
- **`backlog.py`** reads the items: `show` prints status, priority and title,
  `show --in-progress` only the items In Progress as work; `--repo` reads
  them at the remote's default branch, after a fetch.
- **`backlog-ops`** changes an item's status; this skill only reads it.
