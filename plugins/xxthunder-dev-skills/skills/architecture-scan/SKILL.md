---
name: architecture-scan
description: "Derive a repository's real structure from its code and compare it against the architecture document. Produces a bootstrap proposal when no document exists, and a drift report when one does. Read-only — it proposes, and design-record applies. Trigger with: 'check the docs against reality', 'is the architecture doc still true', 'bootstrap the architecture doc', 'has the architecture drifted'."
---

<!-- Source: https://github.com/xxthunder/xxthunder-agentic-skills/tree/develop/plugins/xxthunder-dev-skills/skills/architecture-scan -->

# Architecture Scan

Reads the codebase, derives the structure that is actually there, and compares
it against what the architecture document claims. Two outputs from one
capability:

- **No document yet** → a *bootstrap proposal* covering the fixed slots.
- **A populated document** → a *drift report* naming where the two disagree.

Bootstrap and drift detection are the same operation with a different baseline —
bootstrap is a drift report against an empty document — so this is one skill,
not two.

## This skill is read-only

**It never writes.** Not the architecture document, not an ADR, not the ADR
index. It produces a proposal or a report; applying anything routes through
`design-record`, which is the record's only writer.

That means recording a structural change is a two-step move here — scan, then
apply — while `design-record` records a *decision* in one. The asymmetry is
deliberate. Recording a decision happens constantly and should be one move; a
bootstrap or a drift sweep is occasional and produces a large body of inferred
content that deserves reading before it lands. An explicit apply step is a
review gate, not friction.

Do not "optimise" this by giving the scan write access. One skill owning the
format is what keeps the conventions from diverging.

## When This Skill Triggers

| Trigger phrase | Operation |
|----------------|-----------|
| "bootstrap the architecture doc", "we have no architecture.md" | [Bootstrap proposal](#bootstrap-proposal) |
| "check the docs against reality", "is the architecture doc still true", "has the architecture drifted" | [Drift report](#drift-report) |

Do **not** trigger on:
- "record an ADR", "update the architecture doc", "document this decision" —
  that is `design-record`, which writes.
- "let's refine", "add a story" — that is `refinement`.

## Locating the document

Same discovery order `design-record` uses, and it must stay the same:

1. `docs/architecture.md`
2. Root `ARCHITECTURE.md`
3. `docs/architecture/README.md` — a directory-based record uses its README as
   the entry point.
4. None → this is a **bootstrap**.
5. More than one → **ask** which is authoritative. Do not scan against one and
   silently ignore the others.

The ADR log follows the same shape: `docs/adr/`, then `docs/architecture/adr/`.

## Deriving the real structure

Work from what the repository actually contains:

- **Directories** — the top-level layout, and the significant subdivisions
  inside each unit.
- **Manifests** — `package.json`, `pyproject.toml`, `plugin.json`,
  `marketplace.json`, `Cargo.toml`, `go.mod`, `pom.xml` and equivalents. These
  name the units and their boundaries better than directory names do.
- **Entry points** — `main`, `__main__`, `bin`, `scripts`, `index`, declared
  console scripts, published hooks.
- **Dependency edges** — imports and requires that cross a unit boundary, plus
  declared dependencies between units in the manifests.

**Omission beats invention.** Where the scan cannot derive a slot, report it as
*not yet documented* and stop. Never offer a plausible guess. A wrong box in an
architecture document is worse than a missing one, because a reader cannot tell
which boxes were inferred.

## Bootstrap proposal

1. Confirm no architecture document exists (see [Locating the document](#locating-the-document)).
2. Derive the structure.
3. Produce a proposal covering the fixed slots in canonical order — Purpose,
   System context, Containers, Components, Key flows, Glossary, Decisions.
4. **Mark the whole thing as proposed.** State plainly that it is inferred from
   code and has not been reviewed.
5. For each slot, either give derived content or the explicit note
   *"not yet documented — the scan could not derive this"*. Purpose in
   particular is rarely derivable; a README may state it, and if nothing does,
   say so rather than inventing a mission statement.
6. Hand off: the user reviews, then `design-record` writes what they approve.

## Drift report

Compare the derived structure against the document and report only real
disagreements. Four categories:

1. **Undocumented modules** — present in the code, absent from the document.
2. **Documented modules that no longer exist** — named in the document, gone
   from the code.
3. **Diagram nodes with no counterpart** — a box or edge in a mermaid diagram
   that matches nothing derivable.
4. **ADRs whose referenced paths have disappeared** — an ADR naming a file or
   directory that is no longer there.

On the fourth: this checks **paths only**. The skill does not judge whether a
decision is still honoured in general, because it cannot. An ADR can be fully
respected by code that has moved, and fully violated by code that has not. Say
what was checked, and do not imply more.

Report nothing when nothing drifted. "The document matches the code" is a
useful answer and should not be padded.

## What This Skill Does NOT Do

- **No writes of any kind.** Proposals and reports only.
- **No reconstructed ADRs.** The scan never infers a decision record for a past
  choice. Rationale is not recoverable from code — the alternatives that lost
  left no trace — so an inferred ADR is confident fiction, which is the exact
  opposite of what the log is for. Where a structural choice looks significant
  and unexplained, say that an ADR is *missing* and let a human supply the
  reasoning.
- **No fabricated structure.** A slot that cannot be derived is reported as not
  yet documented.
- **No code-level detail.** Classes and call graphs are out of scope, matching
  the architecture format.
- **No judgement about whether the architecture is good.** It reports agreement
  and disagreement, not quality.

## Guidelines

- **Report, then stop.** Do not begin applying a proposal because it looks
  obviously right.
- **Be specific.** "Module `foo` is undocumented" beats "some modules are
  undocumented" — a reviewer must be able to act on each line without rerunning
  the scan.
- **Separate derived from documented.** Every finding should make clear which
  side it came from.
- **Scale the sweep.** On a large repository, cover units and their boundaries
  rather than every file; the document does not describe files.

## Integration Points

- **`design-record`** applies anything the user approves. It owns the format and
  is the only writer.
- **`refinement`** may call for a scan when discussing architecture, to ground
  the discussion in what is actually there.
