# ADR-0015 — The plugin ships no Jira client

**Status**: Accepted
**Date**: 2026-11-04
**Related**: [XAS-053](../backlog/xas-053.md), [ADR-0008](0008-the-stores-agents-md-is-the-contract.md)

## Context

XAS-053 puts Jira issues on the board next to backlog items. Making such a card needs the
issue's summary, and so a way to read Jira. The author's sessions that work with Jira
already have that way: a Jira plugin, with its own credentials and its own setup.

## Decision

- **The plugin ships no Jira client**: no script, no credentials, no Jira URL, no proxy
  handling of its own.
- **`next put` reads the issue through the Jira access the session already has**, whatever
  tool that is. The skills name no Jira tool and no credential variable. Without that
  access, `put` makes no card and says why.
- **Nothing else reads Jira.** A Jira card is a snapshot taken at `put`; `show`, and a pull
  or close in `backlog-ops`, never call Jira.

## Alternatives considered

- **A Jira client next to `backlog.py`**, the design drafted on 2026-10-29: a script that
  reads the Jira Cloud REST API with `JIRA_EMAIL` / `JIRA_TOKEN` from the machine's settings,
  so that `show` reads status and priority fresh on every run. It lost for three reasons:
  - the session's existing Jira access already reads Jira;
  - it would keep Jira credentials in yet another place;
  - it is one more piece of code to maintain.

## Consequences

- The board does not notice an issue that is closed or renamed in Jira; the author drops or
  closes its card by hand.
- `show` reports no contradictions for Jira cards: it has no status to compare.
- `put` on a Jira address works only in a session that can reach Jira.
- The evals stand in a fake Jira plugin for the session's access, since there is no client
  of the plugin's own to test.
