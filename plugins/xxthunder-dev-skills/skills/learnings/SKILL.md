---
name: learnings
description: "Capture a learning that outlives the current repository into the author's personal knowledge repo, or recall what earlier sessions learned about a topic. Use `capture` when the author corrects the agent, when a result plainly holds beyond this project, when `logbook done` asks whether anything outlives the repo, or on 'capture', 'capture that', 'that's a learning', 'keep that for later'. Use `recall` at the start of a topic or on 'what do I know about X', 'have I run into this before', 'recall X'. Never writes into the current repository; the knowledge repo is configured on the machine and never named in any repo."
user_invocable: true
allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/scripts/store *)
---

<!-- Source: https://github.com/xxthunder/xxthunder-agentic-skills/tree/develop/plugins/xxthunder-dev-skills/skills/learnings -->

# Learnings

Two operations on a **store** — a git repo of atomic notes in the author's own
words; a Zettelkasten, a second brain, whatever the author runs. `capture`
writes one learning into it. `recall` reads from it. The store is never the
repository the session is working in.

A **learning** is what stays true after the project is deleted: a correction
the author made, a limit a tool turned out to have, a rule that would have made
an earlier session go differently. It has no home in the project's ADRs or
`CLAUDE.md` — those end with the project. This skill carries it out.

## The direction rule

**The store points into repositories; no repository points into the store.**
A learning cites the repo, item ID and date it came from. But no `CLAUDE.md`,
`AGENTS.md`, backlog item or skill text in a consuming repo names the store,
its path or its remote — some of those repos are public. What knows the store
is the **machine**: two variables in the user's settings
(`~/.claude/settings.json` → `env`), never in a repo.

| Variable | Meaning |
|---|---|
| `LEARNINGS_PATH` | a local checkout of the store, used when present |
| `LEARNINGS_REMOTE` | a clone URL, cloned once into a cache when no checkout is present (ephemeral devcontainers) |

## When This Skill Triggers

**`capture`** — propose it, do not wait to be asked, at these moments:

- the author **corrects** you — the highest signal there is. `retrospective`
  ends at the project's guidelines; `capture` asks what holds beyond them
- a result plainly **outlives the repo** — a tool limit, a vendor behaviour, a
  rule about how sessions go
- `logbook done` asks its one question, "does anything here outlive this repo?"
- the author says "capture", "capture that", "that's a learning"

**`recall`** — at the start of a topic, when `logbook start` suggests it, or on
"what do I know about X", "have I run into this before", "recall X".

Do **not** capture on your own. Every capture goes through the author's
wording, below. Do not summarise the conversation into the store; that is a
different tool's job and the opposite of "in the author's own words".

## Step 1: Resolve the store — fresh, every time

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/store" resolve LEARNINGS
```

Prints the store's absolute path on stdout. The resolution order — the
current directory when it is the store, then the local checkout, then a cached
clone of the remote — is stated once, in the script's own header; do not
restate or assume it. **A non-zero exit ends the operation.** Show the script's message and stop.
Never guess a store, never fall back to the current repository, never create
one. Authentication (SSH keys, `GIT_SSH_COMMAND`) is the environment's
business — a failed clone or pull is reported, not worked around.

## Step 2: Read the contract — the store's `AGENTS.md`

The rules for a learning are the **store's**, stated once, in its own
`AGENTS.md`, in the section headed **`Learnings`**. Read that section and
follow it. It names:

- where learnings go (a directory) and how files are named
- the note template, and which parts the author writes versus the agent drafts
- the hub or index a new note is added to, and the shape of its line
- the tests a learning has to pass before it is written
- the language
- where a capture goes that is not ready yet (see Step 3)

This skill ships **no template and no tests of its own**. A store that changes
its format changes its `AGENTS.md`; this plugin does not ship a new version.
If the section is missing, stop and say what the store has to provide — do not
improvise a format.

## `capture`

### Step 3: Run the store's tests, out loud

Take the tests from the contract and walk them in the chat, one line each,
naming what passes and what fails. Most candidates fail here, and that is the
point: a full day of work yields two learnings, not twenty.

If exactly the test about the author's own wording fails — the thing is true
and useful but the author cannot yet say it — the contract names where such a
capture goes (an inbox, a drafts folder). Put it there, in the words available,
and stop; do not add it to the hub. Any other failure: no learning, say why in
one line, move on.

### Step 4: The author words the claim

Ask for the claim in the author's words — the sentence that will be the
learning's core. **Never write the claim yourself.** Wait for it. If the
author offers a rough version and asks you to tighten it, offer one tightened
version and let them pick; the result is theirs.

### Step 5: Draft the rest from the template

Fill the template's remaining parts — origin, reasoning, consequence, open
questions, whatever it offers — and mark those parts as your contribution the
way the template says (a comment, a section note). Origin means:

- **repo**: the consuming repo's name — the last segment of its `origin` URL
  without a trailing `.git`, or the checkout's directory name if it has no
  remote
- **item**: the backlog item or issue the session was on, if any
- **date**: today, read from the environment; never made up

Links in the note point **into** the consuming repo (item IDs, paths, URLs) as
the contract allows. Nothing in the consuming repo is created or edited.

### Step 6: Write, index, commit, push

Write the note where the contract says. Add its line to the hub or index as
the contract says. Then, from the store:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/store" commit-push "<store>" "<message>" <note> <hub>
```

One commit of exactly these files, pushed immediately — in an ephemeral
container an unpushed note is not a note. When the store *is* the working
repository, whatever else is staged there stays staged and untouched. The
script retries once after `pull --rebase` when someone pushed first; a
conflict is aborted and reported, and the commit is kept locally for the
author. Show its message and stop; do not resolve conflicts in the store.

### Step 7: Report

One line: the note's path in the store and the claim. Then back to the work.

## `recall`

1. Resolve the store (Step 1) and read where learnings live (Step 2).
2. Search the learnings directory for the topic's terms — words from the item
   title, component names, tags the author uses — case-insensitive, titles and
   bodies.
3. Present up to **five** hits as one-liners: title, and the path in the store.
   No hits: say so in one line.
4. Carry the hits as context for the session. `recall` writes nothing.

## What This Skill Never Does

- **Write into the consuming repository.** Its working tree stays exactly as it
  was — `git status` there is unchanged by a capture.
- **Create a learning without the author's wording.** No claim, no note.
- **Run without configuration.** No variables, no store, no guessing.
- **Name any specific store** in its own text — not a path, not a remote, not
  a repo name. This file is installed into public repositories.
- **Summarise the conversation** into the store, or capture unprompted.
- **Edit an existing learning.** Sharpening a learning is the author's work,
  done in the store.

## Integration Points

- **`logbook`** (the chronicle skill): its `start` suggests `recall`; its `done`
  asks once whether anything outlives the repo, and a yes lands here. The two
  stores may be one repo or two; neither skill assumes either.
- **`retrospective`**: ends at the project's guidelines. When it has run, ask
  whether what it found holds beyond this project — that is a `capture`
  candidate.
- **`commit-helper`** is not involved. The store's commit is made by the
  script, in the store; the consuming repo has nothing to commit.
