# ADR-0017 — The board's format belongs to `board.py`

**Status**: Accepted
**Date**: 2026-11-05
**Related**: [XAS-060](../backlog/xas-060.md), [ADR-0008](0008-the-stores-agents-md-is-the-contract.md), [ADR-0011](0011-backlog-ops-moves-the-card-on-a-configured-board.md)

## Context

`next` (put, drop) and `backlog-ops` (the card move on pull and close) described the board
edit in prose, and the agent edited the Markdown table itself. One session did it five
times with a throwaway snippet written on the spot: once it stopped halfway through a
reordering, once a moved card kept a stale title against the contract's rule that every
write reads the title fresh from the item.

A script that edits the table has to take the format from somewhere.
[ADR-0008](0008-the-stores-agents-md-is-the-contract.md) puts a store's rules in its own
`AGENTS.md`, and [ADR-0011](0011-backlog-ops-moves-the-card-on-a-configured-board.md)
says the board's format is the store's `Board` contract, which both skills read — so the
plugin shipped no board format of its own.

## Decision

**The board's format — columns, card, escaping, links — belongs to the plugin's
`board.py`**, and the store's `Board` contract names the script instead of describing the
format. `board.py` makes every change to the board — `put`, `drop`, `pull`, `close` — and
`next` and `backlog-ops` call it for each. It reads an item's title itself, as `backlog.py
show --repo` does; a Jira card's summary comes in as an argument, since the plugin reads no
Jira ([ADR-0015](0015-the-plugin-ships-no-jira-client.md)). The commit stays with `store
commit-push`, and the skill commits only when the script reports a change.

The contract keeps what is the store's: where the board file and the registry are, the
moves, the checkout location, the language and the commit subject. This amends the format
part of ADR-0008 and ADR-0011 for the board; for learnings and the logbook, ADR-0008 stands
as written.

## Alternatives considered

- **A machine-readable part of the contract**, the escape ADR-0008 named: the script reads
  the card format from the store. Rejected: the script needs the card format anyway to keep
  a card's reason and refresh its title, and a template language for one board is
  variability nobody needs.
- **A command of `store`.** Rejected: `store` knows stores — resolving one, reading a
  contract section, committing into it — not the content of one.

## Consequences

- A change to the board's format is a plugin release, not an edit in the store. The store's
  contract still describes the format until zettelkasten ZK-056 points it to the script;
  until then the script writes the format the contract describes, and the two must not
  drift apart.
- The script's `title:` line, which the skills put into the commit subject, unescapes `\|`
  and splits a reason off at the last ` · `. A title or Jira summary that contains ` · ` and
  has no reason is cut there.
- When a card's title has drifted, the old title and its reason are told apart at the last
  ` · `, so a drifted title that contains ` · ` and has no reason leaves its tail as a reason.
- With `--dir` and no `origin/HEAD`, the item link names the current branch of the
  repository that holds the backlog.
- A pull of an issue address `#n` makes a card when none exists; a Jira pull without a card
  makes none.
- `put --reason` on a Jira card already on the board replaces its reason; its summary stays
  as written, since a Jira card is a snapshot.
