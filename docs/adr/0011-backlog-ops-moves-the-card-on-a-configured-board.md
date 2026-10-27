# ADR-0011 — `backlog-ops` moves the card on a configured board

**Status**: Accepted
**Date**: 2026-10-27
**Related**: [XAS-046](../backlog/xas-046.md), [ADR-0007](0007-cross-repo-stores-are-configured-not-discovered.md), [ADR-0008](0008-the-stores-agents-md-is-the-contract.md)

## Context

`next` turned from a ranked list into a Kanban board: what comes next and what
is in progress, across repositories, in one file in a store. A board is only
worth looking at if it is current, and the two moments that change it are the
two lifecycle transitions `backlog-ops` owns — a pull puts an item into
progress, a close finishes it.

Until now `backlog-ops` never wrote outside the consuming repository. It
reached the cross-repo stores only by suggestion: one line after a pull and
one after a close proposing `logbook`, which owns the chronicle and, through
`done`, suggested a `drop` from the list. The board needs no chronicle, and
the logbook is optional — the author's colleague, one of the first people
expected to use a board, does not keep one.

[ADR-0007](0007-cross-repo-stores-are-configured-not-discovered.md) forbids a
repository pointing at a store, not a skill reaching one through the
machine's configuration: `learnings`, `logbook` and `next` already do that.

## Decision

**When a board is configured on the machine, `backlog-ops` moves the item's
card itself**: a pull puts it into the in-progress column, a close takes it
off the board. The board is a store of its own, resolved by its own variable
pair (`BOARD_PATH` / `BOARD_REMOTE`); its format is the store's `Board`
contract ([ADR-0008](0008-the-stores-agents-md-is-the-contract.md)), which
`next` reads too. Without a board configured, `backlog-ops` behaves as it did
before, with no extra output. The board and the logbook know nothing of each
other.

## Alternatives considered

- **`logbook start` and `logbook done` move the card.** The logbook already
  shares the store and already runs at both moments. Rejected by the author:
  it ties the board to a chronicle that is optional, so anyone who keeps a
  board without a log would get a board nobody moves.
- **Cards move by hand only** — `next put` and `next drop`, as with the
  ranked list. Rejected: the author wants a pull to put the card into
  progress in every repository, without a step to remember.

## Consequences

- `backlog-ops` now makes a commit outside the consuming repository — one in
  the board's store per pull and per close. Its own repository is untouched
  by that step, and the commit names only the board file, so nothing staged
  is swept into it.
- A close takes the card off the board at once, while the item's Done reaches
  the default branch only with the merge. `next` therefore does not report an
  item In Progress without a card as a contradiction.
- Two skills read the `Board` contract section. Renaming it in a store breaks
  both, and both must follow when its format changes.
- A board that is configured but cannot be written is reported, never
  blocking: the pull or close stands without its card move.
