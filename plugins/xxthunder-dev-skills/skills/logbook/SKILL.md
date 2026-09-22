---
name: logbook
description: "Chronicle what a session starts, notes and finishes into the author's personal logbook repo — one line per event, across all repositories. Use on the qualified phrases only: 'log the start', 'log that I started X', 'log that …', 'note that … in the log', 'log the close', 'log that X is done'. `backlog-ops` suggests logging after a pull and after a close; the author accepts or not. Never writes into the current repository; the logbook is configured on the machine and never named in any repo."
user_invocable: true
allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/scripts/store *)
---

<!-- Source: https://github.com/xxthunder/xxthunder-agentic-skills/tree/develop/plugins/xxthunder-dev-skills/skills/logbook -->

# Logbook

Three operations on a **logbook** — a git repo that keeps a dated log in the
author's own conventions. `start`, `note` and `done` each add **one line**.

A **chronicle** answers "what did I work on, and what came of it" across repos.
`git log` holds that per repo and records commits, not what a session set out
to do or found on the way; nothing holds it across repos. This skill does.

## The direction rule

**The logbook points into repositories; no repository points into the logbook.**
A log line cites the repo and item ID it is about. No file in a consuming repo
names the logbook, its path or its remote — some of those repos are public.
What knows the logbook is the **machine**: the variable pair `LOGBOOK_PATH` /
`LOGBOOK_REMOTE` in the user's settings (`~/.claude/settings.json` → `env`),
never in a repo. The logbook and the `learnings` store may be one repo or two;
this skill only ever reads the `LOGBOOK` pair.

The logbook may be the repository the session is working in — the author's own
notes repo is the common case. A line is then still one commit of the log file
alone; whatever else is staged there stays staged and untouched.

## When This Skill Triggers

**Only on a qualified phrase**, never on a bare "done" or "start X" — those
belong to `backlog-ops` and `commit-helper`:

- **`start`** — "log the start", "log that I started X", "start the log for X".
- **`note`** — "log that …", "note that … in the log".
- **`done`** — "log the close", "log that X is done", "log the milestone".

How this skill is reached: **by suggestion, not by machinery.** `backlog-ops`
ends its pull with one line proposing `logbook start` and its close with one
proposing `logbook done`; the author accepts or not. No hook, no memory, no
description trigger runs this skill unprompted.

## Step 1: Resolve the logbook — fresh, every time

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/store" resolve LOGBOOK
```

Prints the logbook's absolute path on stdout. The resolution order — the
current directory when it is the logbook, then the local checkout, then a
cached clone of the remote — is stated once, in the script's own header; do
not restate or assume it. **A non-zero exit ends the operation.** Show the
script's message and stop. Never guess a logbook, never fall back to the
current repository, never create one. Authentication is the environment's
business.

## Step 2: Read the contract — the logbook's `AGENTS.md`

The rules for a log line are the **logbook's**, stated once, in its own
`AGENTS.md`, in the section headed **`Logbook`**. Read that section and follow
it. It names:

- where the log is
- the order — how days are headed, and **where a new line goes**
- the line format for `started`, `note` and `done`
- how an address is written (`<repo> <ITEM-ID>`) and where repo names resolve
- how a duplicate `started` is recognised
- the language

This skill ships **no format, no placement rule and no language of its own**.
A logbook that changes any of these changes its `AGENTS.md`; this plugin does
not ship a new version. If the section is missing, or names none of the items
above, stop and say what the logbook has to provide — do not improvise.

## The address

Every line is about `<repo> <ITEM-ID>`:

- **repo**: the consuming repo's name — the last segment of its `origin` URL
  **without a trailing `.git`**, or the checkout's directory name if it has no
  remote. If the contract points at a registry and this repo is not in it, say
  so and let the author add the row before writing the line.
- **item**: the backlog item or issue the session is on, as the repo spells it
  (`XAS-035`, `HSH-072`, `#123`). No item → ask; never invent one.

## Writing a line

Every operation writes its line the same way; the operations below differ only
in what they check first and what they say after.

1. Resolve (Step 1) and read the contract (Step 2).
2. Compose the line in the contract's format and language.
3. Insert it **where the contract says** — including a new day heading when
   the contract's order calls for one and today has none yet.
4. Commit and push that file alone:
   ```bash
   "${CLAUDE_PLUGIN_ROOT}/scripts/store" commit-push "<logbook>" "log: <type> · <repo> <ITEM-ID> · <text>" <log-file>
   ```
   One commit per line, pushed immediately — in an ephemeral container an
   unpushed line is not a line. The script retries once after `pull --rebase`
   when someone pushed first; a conflict is aborted and reported, and the
   commit is kept locally. Show the message and stop; never resolve conflicts
   in the logbook.

## `start`

1. Look the address up in the log and report what is there in one line —
   *"you started this on 2026-09-11; no done yet"* — or that it is new.
2. If a `started` line for this address exists **without a later `done`**,
   this is a resumption: **stop here.** Write nothing, say so, and do not
   suggest anything further.
3. Otherwise write a `started` line ([Writing a line](#writing-a-line)).
4. Then suggest, in one line, `learnings recall` for the topic's terms. Do not
   run it unasked.

## `note`

1. One line about what was done or found — in the author's words or yours,
   **confirmed by the author before it is written**.
2. Write it as a `note` line.

## `done`

1. Look the address up in the log. An existing `done` for it with no later
   `started` means the item is already closed in the chronicle: say so and
   ask whether a second `done` is really wanted before writing one.
2. Write a `done` line: the one-line result and links to what was involved —
   the note, the pull request — as the contract's link rules allow. Not the
   learning: none exists yet at this point, and a line is never edited later.
   A learning carries its own origin; it does not need the log to point at it.
3. Then ask **once**: *"Does anything here outlive this repo?"* A yes hands off
   to `learnings capture`. A no ends here. This is how the capture question
   reaches the end of an item without `backlog-ops` knowing that learnings
   exist.

## What This Skill Never Does

- **Write into the consuming repository.** Its working tree stays exactly as
  it was — `git status` there is unchanged by a log line. When the logbook
  *is* the working repository, the log file is the only thing the line commits.
- **Edit or delete an existing log line.** A correction is a new line.
- **Run without configuration.** No variables, no logbook, no guessing.
- **Name any specific logbook** in its own text — not a path, not a remote,
  not a repo name. This file is installed into public repositories.
- **Invent an address.** No item ID known → ask.
- **Run unprompted.** It is suggested and invoked, never hooked, remembered or
  triggered by an unqualified word.

## Integration Points

- **`backlog-ops`**: suggests `logbook start` after a pull and `logbook done`
  after a close — one line each, never a call. It does not know whether a
  logbook is configured; this skill finds out and says so.
- **`learnings`**: `start` suggests its `recall`; `done` asks the one question
  whose yes is its `capture`. Two skills, two contracts, possibly one repo.
- **`commit-helper`** is not involved. The logbook's commit is made by the
  script, in the logbook; the consuming repo has nothing to commit.
