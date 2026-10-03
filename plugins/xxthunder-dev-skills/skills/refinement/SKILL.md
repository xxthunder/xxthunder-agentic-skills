---
name: refinement
description: "Start a backlog refinement session to discuss the project mission, review backlog items, prioritize work, and align on next steps. Also bootstraps the backlog structure in greenfield projects. Trigger with: 'another refinement session', 'let's refine', 'refinement time', 'backlog refinement', or similar requests to discuss project direction and priorities."
user_invocable: true
allowed-tools: Bash(uv run ${CLAUDE_PLUGIN_ROOT}/scripts/backlog.py *)
---

<!-- Source: https://github.com/xxthunder/xxthunder-agentic-skills/tree/develop/plugins/xxthunder-dev-skills/skills/refinement -->

# Refinement Session

Interactive backlog refinement session. Reviews project mission, current state, backlog items, and documentation to align on priorities and next steps. Bootstraps the backlog in greenfield projects.

## When This Skill Triggers

- "Another refinement session" / "Let's refine" / "Refinement time"
- "Backlog refinement" / "Let's discuss the backlog"
- Any request to review project status and priorities

Note: a bare "what should we work on next?" is **not** sufficient by itself — it often appears in casual prompts where the user just wants a one-line suggestion, not a structured session. Trigger only when the surrounding context indicates the user wants the full refinement flow (mission review, backlog walk, prioritization).

## Workflow

### Step 1: Load Project Context

Discover and read project documentation to understand current state. Look for:

1. **`README.md`** - Project mission and user-facing documentation
2. **Backlog file** - `docs/backlog/README.md`, `BACKLOG.md`, or equivalent
3. **Roadmap** - `docs/roadmap.md` or equivalent
4. **Development principles** - `docs/development-principles.md`, `CONTRIBUTING.md`, or equivalent

Also check:

5. **`git log --oneline -20`** - Recent activity
6. **`git branch -a`** - Active branches

**If no backlog file exists** → go to Step 1b (Bootstrap).
**If a backlog file exists** → skip to Step 2.

### Step 1b: Bootstrap Backlog (Greenfield)

When no backlog file is found, create one:

1. Read **[references/backlog-format.md](references/backlog-format.md)** for the complete format specification
2. Ask the user where the backlog should live (default: `docs/backlog/`)
3. Ask the user for a **project ID prefix** — a short uppercase abbreviation of the repo/project name (e.g., `HSH` for HomeSweetHome). Store it in the Notes section of the backlog.
4. Create `README.md` with the skeleton structure (Status Legend, an empty `## Table of Contents`, Notes with the ID prefix)
5. Create the ongoing refinement item (`[PREFIX-001]`) as a separate file with `**Status**: In Progress`
6. Run `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/backlog.py" toc` — it writes the table of contents from the item files
7. Ask the user if they have initial ideas to seed the backlog — draft entries using the format from the reference

**Do NOT commit automatically.** Let the user review via `git diff` first.

### Step 2: Present Session Summary

```
## Refinement Session

### Project Mission
[1-2 sentence summary from README.md]

### Current State
- **Active branch**: [current branch and what it's about]
- **Recent activity**: [summary of last few commits]

### Backlog Overview
**In Progress**: [count and brief list]
**Open**: [count and brief list with IDs]
**Recently Done**: [count and last 1-2 done items]

### Open Items for Discussion
[List each Open item with ID, title, priority, and a 1-line summary]
```

### Step 3: Facilitate Discussion

Use AskUserQuestion to let the user choose their focus area:

1. **Prioritize** - Review and reorder backlog items
2. **Deep dive** - Explore a specific backlog item in detail
3. **New ideas** - Add new items to the backlog
4. **Architecture** - Discuss technical direction or decisions
5. **Cleanup** - Review completed items, close stale items, update docs

### Step 4: Topic-Specific Facilitation

#### Prioritize
- Walk through each Open item
- Ask about relative priority and dependencies
- Suggest ordering based on dependencies and value
- Update backlog priorities if agreed

#### Deep Dive
- Read the full backlog item details
- Read related source files and tests
- Identify open questions, risks, and dependencies
- Discuss implementation approach
- **Validate module placement** - Check whether the proposed file/module location fits the existing architecture. Ask: "Is this feature truly coupled to this module, or is it independently useful?" Challenge false coupling — just because feature A is often used alongside feature B doesn't mean A belongs in B's module.
- Use EnterPlanMode if the discussion leads to implementation planning

#### New Ideas
- Help the user articulate the idea
- Read **[references/backlog-format.md](references/backlog-format.md)** for the entry template and ID convention
- Read the project prefix from the **Notes** section of the backlog
- Decide whether this is a **top-level item** or a **substory under an existing item**:
  - If the idea naturally belongs under an existing top-level item as one of several related pieces of work, it's a substory — allocate the next letter suffix (`a`, `b`, `c`, …) under that parent.
  - Otherwise it's top-level — allocate the next free three-digit number.
- Get the next available ID from the backlog script (see "The backlog script" in the format reference):
  - **Top-level**: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/backlog.py" next-id`
  - **Substory of `PREFIX-NNN`**: `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/backlog.py" next-id PREFIX-NNN`
- Draft a backlog entry with all required fields using `[PREFIX-###]` or `[PREFIX-###<letter>]` format (no `**Epic**:` back-reference — the letter suffix encodes the parent)
- If this is the **first substory** under a top-level item, that item is now implicitly an epic. No rename needed; optionally add a **Substories** list to the parent for readability. The parent's status cascade (see format reference) now governs when it can be marked Done.
- After user approval, write the item file, then run `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/backlog.py" toc` — it lists the new item in the README. A non-zero exit from the script ends the step: show its message and stop.

#### Architecture
- Read relevant source files and architecture docs
- Discuss technical decisions and trade-offs
- **Design work belongs to `superpowers:brainstorming`.** This plugin depends on `superpowers`, so hand off rather than re-deriving a design here. Its output belongs in the backlog item — the item *is* the design document for a unit of work, so a separate spec file duplicates it and then drifts from it.
- **Decide where each decision belongs.** Apply the three-part test — all three must hold for a decision to earn an ADR:
  1. The consequences **outlive the change**: after the item closes, does this still constrain the repo?
  2. A competent engineer **could have chosen otherwise**: if there was one sensible option, there was no decision.
  3. The reason is **not recoverable from the code**: if the implementation makes it obvious, the code is already the record.
- **Passes all three** → hand off to `design-record` to write the ADR while the losing alternatives are still in the conversation. They are not recoverable later.
- **Fails any** → the backlog item's `Scope Decisions` field, as before. The ladder is: trivial → nothing; local to this change → `Scope Decisions`; outlives the change → ADR.
- Suggest, do not insist. If the user would rather keep it in `Scope Decisions`, that is their call — a stale document beats a workflow people route around.

#### Cleanup
- Review Done items - any follow-up needed?
- Check for stale Open items
- Update documentation if outdated
- Propose items to archive or remove

### Step 5: Capture Outcomes

```
## Session Outcomes

### Decisions Made
- [list decisions]

### Backlog Changes
- [items added, updated, reprioritized, or removed]

### Next Steps
- [what to work on next]
- [any follow-up items]
```

**Do NOT commit automatically.** Let the user review changes via `git diff` first. Only commit when explicitly asked.

## Guidelines

- **Keep it conversational** - Collaborative discussion, not a status report
- **Ask questions** - Help the user think through priorities and trade-offs
- **Be opinionated** - Offer suggestions based on project context
- **Stay focused** - One topic at a time
- **Respect the user's direction** - They know their priorities best
- **Use the format reference** - New/modified entries must follow [references/backlog-format.md](references/backlog-format.md)
- **Link to code** - Reference specific files and line numbers when discussing items
- **Never auto-commit** - Always let the user review first
- **Hand off state changes to `backlog-ops`** - Refinement is for discussion, prioritization, and entry authoring. When an item needs to be pulled, have an AC ticked, or be closed, invoke the `backlog-ops` skill rather than editing status fields by hand — it handles README TOC consistency and the epic-status cascade for you.
