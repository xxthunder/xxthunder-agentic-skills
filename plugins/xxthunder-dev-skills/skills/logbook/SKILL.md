---
name: logbook
description: "Chronicle what a session starts, notes and finishes into the author's personal logbook repo — one line per event, across all repositories. Use `start` when a topic begins (an item pulled, a refinement, 'let's work on X'), `note` for a one-line finding along the way ('note that', 'log that'), `done` when an item closes or a milestone lands ('done', 'log the close'). `backlog-ops` suggests start and done at pull and close. Never writes into the current repository; the logbook is configured on the machine and never named in any repo."
user_invocable: true
allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/scripts/store *)
---

<!-- Source: https://github.com/xxthunder/xxthunder-agentic-skills/tree/develop/plugins/xxthunder-dev-skills/skills/logbook -->

# Logbook

Three operations on a **logbook** — a git repo that keeps a dated log in the
author's own conventions. `start`, `note` and `done` each add **one line**. The
logbook is never the repository the session is working in.

A **chronicle** answers "what did I work on, and what came of it" across repos.
`git log` holds that per repo and records commits, not what a session set out
to do or found on the way; nothing holds it across repos. This skill does.

## The direction rule

**The logbook points into repositories; no repository points into the logbook.**
A log line cites the repo and item ID it is about. No file in a consuming repo
names the logbook, its path or its remote — some of those repos are public.
What knows the logbook is the **machine**: two variables in the user's settings
(`~/.claude/settings.json` → `env`), never in a repo.

| Variable | Meaning |
|---|---|
| `LOGBOOK_PATH` | a local checkout of the logbook, used when present |
| `LOGBOOK_REMOTE` | a clone URL, cloned once into a cache when no checkout is present (ephemeral devcontainers) |

The logbook and the `learnings` store may be one repo or two. This skill does
not assume either; it only ever reads the `LOGBOOK` pair.

## When This Skill Triggers

- **`start`** — at the start of a topic: an item pulled (`backlog-ops` suggests
  it after every pull), a refinement session, "let's work on X", "start on X".
- **`note`** — "note that …", "log that …", or when something worth one line
  turns up mid-work and the author agrees it should be kept.
- **`done`** — an item closed (`backlog-ops` suggests it after every close), a
  milestone reached, "done with X", "log the close".

How this skill is reached: **by suggestion, not by machinery.** `backlog-ops`
ends its pull with one line proposing `logbook start` and its close with one
proposing `logbook done`; the author says yes or not. There is no hook and no
memory that runs this skill unprompted.

## Step 1: Resolve the logbook — fresh, every time

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/store" resolve LOGBOOK
```

Prints the logbook's absolute path on stdout. Its order, first match wins:

1. the current directory *is* the logbook (it is `LOGBOOK_PATH`, or its `origin`
   is `LOGBOOK_REMOTE`) → used as-is
2. `LOGBOOK_PATH` exists → `git pull --ff-only`, then used
3. `LOGBOOK_REMOTE` is set → cloned once into the user's cache, pulled after
4. neither → the script says so and exits non-zero

**A non-zero exit ends the operation.** Show the script's message and stop.
Never guess a logbook, never fall back to the current repository, never create
one. Authentication is the environment's business.

## Step 2: Read the contract — the logbook's `AGENTS.md`

The rules for a log line are the **logbook's**, stated once, in its own
`AGENTS.md`, in the section headed **`Logbook`**. Read that section and follow
it. It names:

- where the log is
- how days are headed and whether newest is first — that is, *where to insert*
- the line format for `started`, `note` and `done`
- how an address is written (`<repo> <ITEM-ID>`) and where repo names resolve
- how a duplicate `started` is recognised
- the language

This skill ships **no format of its own**. A logbook that changes its line
format changes its `AGENTS.md`; this plugin does not ship a new version. If the
section is missing, stop and say what the logbook has to provide — do not
improvise a format.

## The address

Every line is about `<repo> <ITEM-ID>`:

- **repo**: the consuming repo's name — the last segment of its `origin` URL,
  or the checkout's directory name if it has no remote. The contract may point
  at a registry where names resolve; if this repo is not in it, say so and let
  the author add it before writing the line.
- **item**: the backlog item or issue the session is on, as the repo spells it
  (`XAS-035`, `HSH-072`, `#123`). No item → say so and ask; do not invent one.

## `start`

1. Resolve (Step 1), read the contract (Step 2).
2. Look the address up in the log. Report what is there in one line — *"you
   started this on 2026-09-11; no done yet"* — or that it is new.
3. If a `started` line for this address exists **without a later `done`**, this
   is a resumption: write **nothing** and say so.
4. Otherwise insert a `started` line where the contract says (top, under
   today's heading — create the heading if today has none), in the contract's
   format, English unless the contract says otherwise.
5. Commit and push the one line:
   ```bash
   "${CLAUDE_PLUGIN_ROOT}/scripts/store" commit-push "<logbook>" "log: started · <repo> <ITEM-ID> · <text>" <log-file>
   ```
6. Then suggest, in one line, `learnings recall` for the topic's terms. Do not
   run it unasked.

## `note`

1. Resolve, read the contract.
2. One line about what was done or found — in the author's words or yours,
   **confirmed by the author before it is written**.
3. Insert at the top under today's heading; commit and push as above with a
   `log: note · …` message.

## `done`

1. Resolve, read the contract.
2. Insert a `done` line: the one-line result and links to what was involved —
   the note, the learning, the PR — as the contract's link rules allow.
3. Commit and push as above with a `log: done · …` message.
4. Then ask **once**: *"Does anything here outlive this repo?"* A yes hands off
   to `learnings capture`. A no ends here. This is how the capture question
   reaches the end of an item without `backlog-ops` knowing that learnings
   exist.

## Concurrency

Every line is one commit, pushed immediately — in an ephemeral container an
unpushed line is not a line. The script retries once after `pull --rebase` when
someone pushed first. Two sessions inserting under the same day heading can
still conflict on that retry; the script aborts the rebase, keeps the commit
locally and reports it. Show the message and stop — do not resolve conflicts in
the logbook.

## What This Skill Never Does

- **Write into the consuming repository.** Its working tree stays exactly as it
  was — `git status` there is unchanged by a log line.
- **Edit or delete an existing log line.** A correction is a new line.
- **Run without configuration.** No variables, no logbook, no guessing.
- **Name any specific logbook** in its own text — not a path, not a remote, not
  a repo name. This file is installed into public repositories.
- **Invent an address.** No item ID known → ask.
- **Run unprompted.** It is suggested and invoked, never hooked or remembered.

## Integration Points

- **`backlog-ops`**: suggests `logbook start` after a pull and `logbook done`
  after a close — one line each, never a call. It does not know whether a
  logbook is configured; this skill finds out and says so.
- **`learnings`**: `start` suggests its `recall`; `done` asks the one question
  whose yes is its `capture`. Two skills, two contracts, possibly one repo.
- **`commit-helper`** is not involved. The logbook's commit is made by the
  script, in the logbook; the consuming repo has nothing to commit.
