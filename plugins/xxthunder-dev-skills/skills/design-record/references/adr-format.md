# ADR Format

An Architecture Decision Record captures **why** a structural choice was made,
at the moment it was made, while the alternatives that lost are still known.
Code shows what was decided; only an ADR shows what else was on the table.

## Location and naming

ADRs live at `docs/adr/NNNN-kebab-title.md` relative to the repository root.
`NNNN` is four digits, zero-padded, sequential. **Numbers are never reused** —
not even for a rejected or superseded ADR, because references to a number
appear in commit messages and other ADRs that are not going to be rewritten.

If `docs/adr/` does not exist, create it along with a `README.md` index.

## Template

    # ADR-NNNN — Title in sentence case

    **Status**: Proposed
    **Date**: YYYY-MM-DD
    **Related**: [PREFIX-###](../backlog/prefix-###.md)

    ## Context

    The forces in play. What made a decision necessary, what constraints
    applied, and what tension had to be resolved. Written so a reader who
    was not there understands why this was hard.

    ## Decision

    What was chosen, stated in the present tense as a standing position
    rather than as a narrative of the meeting.

    ## Alternatives considered

    Each alternative that was genuinely on the table, with the reason it
    lost. An alternative nobody actually considered does not belong here.

    ## Consequences

    What follows from the decision — including the costs accepted and the
    cheap escape hatch if it turns out wrong. Not a list of benefits.

## Record the decision, not the specification

An ADR records **what was decided and why**. Anything that can change without
the decision changing — a path list, a search order, a schema, a set of
permitted values, a slot list — is **named, not reproduced**. Point at whatever
owns it.

The test: *if this detail changed tomorrow, would the decision still stand?*
If yes, it is a specification and belongs wherever it is maintained. If no, it
is part of the decision and belongs here.

Worked example, from this repository's own log:

- **Decision** — "record locations are discovered, never hardcoded or
  configured". Still stands. Belongs in the ADR.
- **Specification** — the search order `docs/architecture.md`, then
  `ARCHITECTURE.md`, then `docs/architecture/README.md`. This changed within
  days of being written, when a real consuming repo turned out to keep a
  directory rather than a file. The decision was untouched by that change.
  Belongs in the format reference the skills read.

An ADR that copies the list ends up stating something untrue while remaining
frozen, which is worse than vague: it is a permanent document lying with
authority about how the system behaves. Three ADRs in this log did exactly
that before the rule existed.

Naming the owner in prose is enough — "the order is stated in
`architecture-format.md`". A link is optional and often wrong: in a consuming
repository, a link into the plugin directory does not resolve.

## Statuses

| Status | Meaning |
|--------|---------|
| `Proposed` | Drafted, not yet agreed |
| `Accepted` | Agreed and in force |
| `Rejected` | Considered and declined |
| `Superseded by ADR-NNNN` | Replaced by a later decision |

**Rejected ADRs stay in the log.** "We considered this and said no" is as useful
a record as a yes, and deleting it guarantees the same idea is re-litigated.

## Immutability

**An Accepted ADR is immutable in substance.** A changed mind is a new ADR, not
an edit to the old one — an edited ADR silently rewrites history and destroys
the only thing the log is for.

Exactly two edits are permitted:

1. Its `**Status**` line, at supersede time.
2. A correction that changes no meaning: a typo, a broken link, or wording that
   misleads about what the ADR already decided.

The test for the second is whether a reader would decide anything differently
after the change. If they would, it is a new ADR that supersedes — not an edit.
Note the correction in the backlog item that made it, so the change is
traceable to a reason rather than appearing as silent drift.

## The supersede path

When ADR-0009 replaces ADR-0004:

1. ADR-0009 gains a `**Supersedes**: [ADR-0004](0004-....md)` line in its header
   block, below `**Related**`.
2. ADR-0004's `**Status**` line becomes `Superseded by ADR-0009`, linked:
   `**Status**: Superseded by [ADR-0009](0009-....md)`.
3. **ADR-0004's body is not touched.** Not corrected, not annotated, not
   softened.

## The index is derived

`docs/adr/README.md` holds a table of ADRs and a `## Notes` section. **Where the
index and the files disagree, the files win** and the index is regenerated from
them.

The backlog follows the same rule: its item files are the truth, and its
README's table of contents is derived from them. A table that carries nothing
its files do not already hold is safe to treat as a cache; treating it as a
source would be a second place for the truth to live.

Index row format:

    | [NNNN](NNNN-kebab-title.md) | Title | Status | YYYY-MM-DD |

## Links point one way

An ADR names the backlog item that produced it, in `**Related**`. The backlog
item is **not** required to link back. One direction is free; two directions
cost an edit every time and rot silently when only one side is updated.
