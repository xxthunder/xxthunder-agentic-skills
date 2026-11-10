# ADR-0019: An ADR's need mirrors its Markdown header

**Status**: Accepted
**Date**: 2026-11-10
**Related**: [XAS-044b](../backlog/xas-044b.md), [ADR-0018](0018-requirements-are-binding-where-sphinx-needs-is-in-use.md)

## Context

[ADR-0018](0018-requirements-are-binding-where-sphinx-needs-is-in-use.md) turns ADR headers
into needs where a repository has a root `ubproject.toml`, so that an ADR can link the
requirements it constrains. It leaves the shape of that header to `design-record`'s ADR
format reference.

The same ADR file has three readers. GitHub renders the Markdown and shows a need only as
a code block. Sphinx takes the page title from the `#` heading; a page without one breaks a
`-W` build once it sits in a toctree. ubCode and `ubc` read the need. A header that serves
only one of them leaves the others with a page that has no title, or with a status nobody
sees.

## Decision

The Markdown header stays complete and is the source; the need mirrors it.

- The `# ADR-NNNN: Title` heading stays, and the need's title repeats its text.
- The `**Status**` line stays, with its links, and the need's `:status:` repeats its first
  word.
- `adr.py migrate` writes the need from the header and re-syncs `:status:` from the Status
  line on every run. `design-record` runs it after it writes an ADR, after a supersede and
  after a narrowing.

The exact header, field order and the status words are specified in `design-record`'s
`references/adr-format.md`, not here.

## Alternatives considered

- **The need instead of the heading.** Rejected (2026-11-08): Sphinx needs the `#` heading
  as the page title, and GitHub shows the need only as a code block, so the file would have
  no visible title there.
- **The need's `:status:` alone, with `:supersedes:` and `:narrows:` as need link types
  instead of the Status line.** Rejected (2026-11-10): GitHub shows the need as a code
  block, so only the Status line shows a GitHub reader the status and the link to the
  superseding ADR. The ADR index reads the Status line too.

## Consequences

- Title and status stand twice in every need-shaped ADR. The script keeps the status in
  line; a hand edit of `:status:` alone is overwritten by the next run.
- The script does not re-sync the title. A correction of an ADR's heading, which is rare
  because ADRs are not edited in substance, has to change the need's title by hand.
- Dropping the duplicate later is a new ADR plus a migration of every need-shaped ADR, and
  `design-record` would need the two link types.
