# Rubric — what a reviewer judges in a change to this repository

Judge a change to this repository against these criteria, next to the general rubric.
Leave to the tests and the gate what they decide: frontmatter, the version bump, whether
an eval case runs and tells the old behaviour from the new.

Answer each criterion with evidence from the diff: a `file:line` and what it shows. A
criterion that does not apply to the change is answered "not applicable" with the reason.
Give each finding the severity its criterion names, not one of your own.

## 1. Script before prose

Does every mechanical step a skill asks for have a script that does it, and does the
`SKILL.md` tell the agent to run that script? Mechanical steps are those with one right
result: allocating an ID, editing a table of contents, computing a date, moving a board
card, inserting a log line under the right day heading. A finding is a `SKILL.md` that has
the agent do such a step by reading files and editing them — "take the highest number in
`docs/backlog/` and add one" instead of running the script that prints the next ID.

**Severity**: Important.

## 2. Trigger

Does the skill's `description` cover the phrasings real users use, in each language they
write? Does a changed `description` come with a run of `skill-creator`'s trigger tooling,
its result recorded in the pull request? A finding is a kind of request the skill serves
that no phrasing covers, or a changed `description` with no trigger run.

**Severity**: Important for a changed `description` with no trigger run; Minor for a
missing phrasing.

## 3. Portable

Does everything under `plugins/` hold in any repository it is installed into? A finding is
a path, a repository name, a host, a store location or an assumption about one machine or
one repository in a skill, a script or a hook.

**Severity**: Important.

## 4. A case per behaviour change

Does every change to what a skill does add or change an eval case under `evals/` whose
check asserts that behaviour — the end state or the answer the skill must produce? A
finding is a behaviour change with no case, or a case that checks a side effect instead:
that a file was read, that a command ran, that some text appears.

**Severity**: Important.
