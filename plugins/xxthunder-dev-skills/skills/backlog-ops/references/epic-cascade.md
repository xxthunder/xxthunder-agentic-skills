# Epic Status Cascade

An **epic** in this backlog convention is any top-level item (`PREFIX-###`) that has at least one substory (`PREFIX-###<letter>`). Epic-ness is emergent — no explicit `Type` field. An item that had no substories becomes an epic the moment the first `<letter>` sibling is created.

The epic's status is **derived** from its substories, not asserted independently. The backlog script's `set-status` applies the rule; the README table of contents follows from the item files.

## The Cascade Rule

Given an epic `PREFIX-NNN` and its substories `PREFIX-NNN<a..>`:

| Substory states                                        | Epic status   |
|--------------------------------------------------------|---------------|
| All substories `Done` or `Superseded`                  | `Done`        |
| At least one substory `In Progress`                    | `In Progress` |
| No `In Progress`; mix of `Open` and `Done`             | `In Progress` |
| All substories `Open`                                  | `Open`        |

**Plain English**: as long as any substory is not `Done`, the epic is not `Done`. The moment any substory leaves `Open`, the epic leaves `Open`.

## When the Cascade Fires

The `backlog-ops` skill evaluates the cascade in three situations:

1. **After pulling a substory** (`Open` → `In Progress`): `set-status` moves an `Open` parent to `In Progress` itself and prints the change.
2. **After completing a substory** (`In Progress` → `Done`): when every sibling is closed, `set-status` prints that the epic can be closed. *Prompt* the user to close it. The user may have outstanding epic-level ACs (e.g., a smoke test spanning all substories), so the epic closes only on a yes.
3. **Drift detection, any operation**: if the parent's status is inconsistent with the rule (e.g., parent `Open` while a substory is `In Progress`), correct it with `set-status <PARENT> "In Progress"` and note the correction in the summary.

## Epic-Level ACs vs. Substory Completion

An epic may carry its own Acceptance Criteria — for example an end-to-end smoke test that only makes sense once all substories ship. These ACs are checked independently via the `check` operation and are evaluated in the **Complete** preconditions just like any other ACs.

**Anti-pattern to avoid**: an AC that says "Child stories X, Y, Z completed". That duplicates the cascade and goes stale on rename. The cascade tracks substory completion; ACs should track *additional* epic-level work (integration tests, docs, migrations) that isn't captured by any single substory.

## Legacy Bare-ID Substories

Backlogs created before the letter-suffix convention may have Done substories with bare sequential IDs (e.g., `PREFIX-018` was a child of `PREFIX-015`). These are not detectable by pattern — they look like independent top-level items.

**Policy**: the cascade considers only letter-suffix children (`PREFIX-NNN<letter>`) when computing epic status. Legacy bare-ID Done children are out of scope for automatic cascade. If the user wants the epic treated as Done-contingent on a legacy child, they must either rename the child (not recommended — breaks git history) or close the epic manually once they are satisfied.
