---
name: design-record
description: "Record a design decision as an ADR, or update the living architecture document, in a repo that keeps a record of how it is built and why. Drafts the ADR body from the conversation, allocates the next number, maintains the ADR index, and edits named sections of architecture.md. Stages file edits only; never produces its own commit. Trigger with: 'record an ADR', 'document this decision', 'we decided X — write it up', 'why did we choose Y — capture it', 'update the architecture doc'."
---

<!-- Source: https://github.com/xxthunder/xxthunder-agentic-skills/tree/develop/plugins/xxthunder-dev-skills/skills/design-record -->

# Design Record

Writes the two artifacts that outlive a unit of work: the **ADR log** at
`docs/adr/`, and the living **`architecture.md`**. Formats live in
[references/adr-format.md](references/adr-format.md) and
[references/architecture-format.md](references/architecture-format.md).

This skill **stages file edits only**. It never creates a commit. Commits are
the user's call — typically via `commit-helper` — so a record change can ride in
the same commit as the code change that justifies it.

## Why this skill authors prose, unlike `backlog-ops`

`backlog-ops` refuses to author content: it applies mechanical lifecycle
operations and leaves all writing to `refinement`. This skill deliberately
breaks that seam and drafts ADR bodies itself.

The reason is frequency. Most decisions worth recording produce both an ADR and
an architecture edit, so splitting authorship across a conversation skill and a
mechanics skill would make recording a decision a two-invocation ritual on the
highest-frequency path in the whole design — and a two-step ritual on the common
path is how a practice quietly stops being followed.

**Do not "fix" this inconsistency.** It is a considered divergence, recorded in
ADR-0003 of this skill's home repository. Removing it reintroduces the friction
it exists to avoid.

## When This Skill Triggers

| Trigger phrase | Operation | Section |
|----------------|-----------|---------|
| "record an ADR", "document this decision", "write up why we chose X" | record decision | [Recording a decision](#recording-a-decision) |
| "supersede ADR-0004", "we're changing our mind about X" | supersede | [Superseding](#superseding-an-adr) |
| "ADR-0018 narrows ADR-0001", "ADR-0001 stays in force, except for X" | narrow | [Narrowing](#narrowing-an-adr) |
| "convert the ADRs to needs", "make the ADRs sphinx-needs needs" | migrate | [ADRs as needs](#adrs-as-needs) |
| "regenerate the ADR index", "the index is out of date" | reindex | [The index](#maintaining-the-index) |
| "update the architecture doc", "redraw the container diagram", "document this module" | edit architecture | [Editing architecture.md](#editing-architecturemd) |

Do **not** trigger on:
- "let's refine", "add a new story", "prioritise the backlog" — that is `refinement`.
- "start XAS-025", "close XAS-025", "tick AC 2" — that is `backlog-ops`.
  The exception is `backlog-ops`' binding-design check, which hands off *from*
  a close: that arrives as a decision to record, not as a lifecycle request,
  and is handled normally below.
- "check the docs against reality", "is the architecture doc still true" — that
  is `architecture-scan`, which is read-only and proposes changes this skill
  then applies.

## The three-part test

Not every decision earns an ADR. A log that records everything is a log nobody
reads. **All three must hold:**

1. **The consequences outlive the change.** After the story is Done and its
   backlog item is closed, does this still constrain what the repo can do?
2. **A competent engineer could have chosen otherwise.** If there was only one
   sensible option, there was no decision — just work.
3. **The reason is not recoverable from the code.** If reading the
   implementation makes the rationale obvious, the code is already the record.

**When a request fails the test, decline and redirect.** Say which part it fails
and point at the alternative:

- Fails (1) — rationale local to this change → the backlog item's
  `**Scope Decisions**:` field.
- Fails (2) or (3) → nowhere. Not every choice needs a paper trail, and saying
  so is part of this skill's job.

The escalation ladder, in full: trivial → nothing; local to this change →
`Scope Decisions`; outlives the change → ADR.

## Recording a decision

### Step 1: Apply the three-part test

Run the test above before doing anything else. If it fails, redirect and stop.

### Step 2: Locate the log and allocate a number

1. Find the ADR directory — `docs/adr/`, then `docs/architecture/adr/` for a
   repo that keeps a directory-based record. If neither exists, say so and
   offer to bootstrap `docs/adr/` (Step 6 handles the index).
2. List `docs/adr/NNNN-*.md`. Take the **maximum** leading number, increment by
   one, zero-pad to four digits.
3. Never reuse a number, including numbers belonging to Rejected or Superseded
   ADRs. If the directory is empty, the first ADR is `0001`.

### Step 3: Draft the body from the conversation

Draft `## Context`, `## Decision`, `## Alternatives considered` and
`## Consequences` from what was actually said.

**Never invent rationale.** This is the guardrail that matters most in this
skill. If the conversation does not contain why an alternative lost, **ask** —
do not fill the section in with something plausible. A fabricated
"Alternatives considered" reads as history and is not, which is strictly worse
than an absent one, because a reader cannot tell the difference.

Specifically, ask rather than infer when:
- An alternative is named but the reason it lost was never stated.
- The `## Consequences` would otherwise list only benefits — a decision with no
  accepted cost usually means the cost was not discussed.
- The `## Context` would have to assert a constraint nobody mentioned.
- The decision was reached before this conversation started, so the reasoning
  exists only in someone's memory. Ask for it; do not reconstruct it from the
  state of the code.

### Step 3b: Name specifications, do not copy them

Before writing, check the draft for anything that could change without the
decision changing — a path list, a search order, a schema, a set of permitted
values. Name the artifact that owns it instead of reproducing it. The test is
in [references/adr-format.md](references/adr-format.md): *if this detail
changed tomorrow, would the decision still stand?*

An ADR is never edited, so a copied specification is frozen at the moment it
was written and starts drifting immediately.

### Step 4: Set the header block

`**Status**: Proposed` unless the user has clearly already agreed, in which case
`Accepted`. `**Date**` is today's — read it from the environment or ask; never
fabricate it. `**Related**` links the backlog item that produced the decision,
if there is one.

### Step 5: Write the file

`docs/adr/NNNN-kebab-title.md`. The title is sentence case, kebab-cased for the
filename, and short enough to read in an index row.

Write the file in the template of
[references/adr-format.md](references/adr-format.md): the first line is
`# ADR-NNNN: Title`, a colon after the number. Older ADRs in the log may use
another separator, such as a dash; do not copy it. Write the bold-field header
block even where the repository uses sphinx-needs: Step 6b turns it into a
need, so there is no second template.

### Step 6: Update the index

Add the row to `docs/adr/README.md` per
[Maintaining the index](#maintaining-the-index). Create that file if absent.

### Step 6b: Make the ADR a need

Where a `ubproject.toml` exists in the repository root, run the migration as
described in [ADRs as needs](#adrs-as-needs). Without that file, skip this step.

When the migration succeeds, stage every file it changed: the new ADR, older
ADRs it converted, and `ubproject.toml`. `git status` lists them.

When the migration refuses, the ADR and the index row from Steps 5 and 6 stay
as written, in the bold-field form. Show the refusal message as the script
printed it (it names what to set, such as `id_regex` or `needs.types`). In
Step 7, report what was written and that the migration did not run, then stop.
Do not write the directive, `id_regex` or the need types yourself.

### Step 7: Report

State the path written, the number allocated, the status, whether the
migration ran, and that the change is staged and uncommitted.

## Superseding an ADR

1. Write the **new** ADR through the normal flow, adding a `**Supersedes**:`
   line linking the old one.
2. Edit the old ADR's `**Status**` line to
   `Superseded by [ADR-NNNN](NNNN-....md)`.
3. **Touch nothing else in the old file.** Its body is history and stays wrong
   if it was wrong.
4. Update both rows in the index.
5. Run Step 6b (the migration, where a root `ubproject.toml` exists): it sets
   the old ADR's `:status:` to `Superseded`. Stage what it changed.

## Narrowing an ADR

Use this when the old decision still stands for some cases; use
[Superseding](#superseding-an-adr) when it stands for none. The operation is
"The narrowing path" in [references/adr-format.md](references/adr-format.md):

1. Write the **new** ADR through the normal flow, adding a `**Narrows**:` line
   that links the old one and names the scope it takes over.
2. Edit the old ADR's `**Status**` line to
   `Accepted, narrowed by [ADR-NNNN](NNNN-....md)`.
3. **Touch nothing else in the old file.**
4. Update both rows in the index: the old ADR's status column becomes
   `Accepted, narrowed by ADR-NNNN`.
5. Run Step 6b (the migration, where a root `ubproject.toml` exists), and stage
   what it changed.

## ADRs as needs

Where the repository root holds a `ubproject.toml`, the repository builds its
docs with sphinx-needs, and every ADR carries a `decision` need below its
heading. The header's shape is "The need-shaped header" in
[references/adr-format.md](references/adr-format.md). The script does the
conversion; do not write the directive by hand:

```bash
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/adr.py" migrate --repo <repo root>
```

It turns every ADR header that is not a need yet into one, sets the `:status:`
of a converted ADR to the word of its Status line where they differ (it prints
`updated: <path>`), and declares the need type and link type in `ubproject.toml`. A
second run changes nothing.

On the request "convert the ADRs to needs", run only this command, stage the
files it changed, then report what it changed.

**A refusal ends the step.** The script refuses when an ADR does not fit the
template or a declaration in `ubproject.toml` conflicts, and then writes
nothing. Show its message to the user and stop. Do not fix the refusal
yourself: in particular, never write or change `id_regex` or `needs.types` in
`ubproject.toml`; the message names what the user has to set. A `ubproject.toml`
without `needs.types` is refused, because a `decision` entry would replace
sphinx-needs' default need types.

## Maintaining the index

`docs/adr/README.md` carries a table of all ADRs and a `## Notes` section
stating the conventions.

**The index is derived from the files.** Where they disagree, the files win —
regenerate the table by scanning `docs/adr/NNNN-*.md` and reading each one's
title, `**Status**` and `**Date**`. Do not resolve a disagreement the other way.

When bootstrapping `docs/adr/` from nothing, create `README.md` with the table
and a `## Notes` section covering: the derived-index rule, sequential
non-reused numbering, immutability of Accepted ADRs, the status values, the
three-part test, and the one-way linking rule.

## Editing architecture.md

Format, slot list and canonical order live in
[references/architecture-format.md](references/architecture-format.md). This
section is the workflow.

### Step 1: Locate or create the document

Resolve the path by discovery, in the order given in the format reference:
`docs/architecture.md`, then root `ARCHITECTURE.md`, then create
`docs/architecture.md` if neither exists, and ask if both do.

If it is absent, create the skeleton with **every** slot present, each either
populated or carrying an honest one-line note. Do not create a partial document
intending to fill it in later — the missing slots are what a later session
appends to instead of editing.

### Step 2: Identify the slot

Map the change to exactly one slot. A change that seems to touch several
usually means the structural change is larger than described — say so and ask,
rather than editing four slots on an assumption.

### Step 3: Edit in place

- If the slot exists, **edit its content**. Do not append a second diagram to a
  structural slot.
- If the slot is missing, insert it at its **canonical position** in the order
  above — never at the end of the file.
- If the change is a new behavioural flow, add a diagram under `## Key flows`.
  This is the only slot that grows.

### Step 4: Degrade honestly

If the slot has nothing real to say for this repository, write the one-line
note. Never leave an empty heading, and never invent a box to fill a diagram.

### Step 5: Report

State which slot changed, whether it was edited or inserted, and that the
change is staged and uncommitted.

## What This Skill Does NOT Do

- **No commits.** Ever. The record edit rides in the user's next commit.
- **No invented rationale.** It asks instead. See Step 3.
- **No reconstructed ADRs for past decisions.** Rationale is not recoverable
  from code, so an ADR inferred from a repo's current state is confident
  fiction — the opposite of what this log is for.
- **No editing an Accepted ADR's substance.** Its `**Status**` line at supersede
  time, and meaning-preserving corrections (typo, broken link, wording that
  misleads about what it already decided) — nothing else. If a reader would
  decide differently after the change, it is a new ADR that supersedes.
- **No reading the codebase to find drift.** That is `architecture-scan`.
- **No backlog status changes.** That is `backlog-ops`.

## Guidelines

- **Ask rather than guess, every time.** The cost of one question is a
  sentence; the cost of a fabricated alternative is a record nobody can trust.
- **Decline decisions that fail the three-part test**, and say which part.
- **Preserve file formatting.** Do not reflow prose, renumber, or touch lines
  the operation does not require.
- **Never auto-commit.** Always leave changes staged.

## Integration Points

- **`refinement`** applies the three-part test during its Architecture topic and
  hands off here for decisions that pass; decisions that fail stay in the
  backlog item's `Scope Decisions`.
- **`architecture-scan`** is read-only and proposes; this skill applies what the
  user approves.
- **`backlog-ops`** hands off here from its binding-design check when closing an
  item, having already applied the three-part test. Closing is the last moment
  to lift design that outlives the item, because nothing keeps a closed item
  current.
- **`commit-helper`** commits the staged record edit alongside the code change.
