# Architecture Decision Records

Why this repository looks the way it does. One decision per file, at
`NNNN-kebab-title.md`.

## Index

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [0001](0001-two-design-artifacts-split-by-lifetime.md) | Two design artifacts, split by lifetime | Accepted | 2026-08-12 |
| [0002](0002-architecture-doc-fixed-slots-for-structure.md) | `architecture.md` uses fixed slots for structure, free-form for behaviour | Accepted | 2026-08-12 |
| [0003](0003-one-writer-for-the-design-record.md) | The design record has exactly one writer | Accepted | 2026-08-12 |
| [0004](0004-always-on-rule-is-orientation-not-enforcement.md) | The always-on rule is orientation, not enforcement | Accepted | 2026-08-12 |
| [0005](0005-bootstrap-architecture-never-reconstruct-adrs.md) | Bootstrap architecture from code; never reconstruct ADRs | Accepted | 2026-08-12 |
| [0006](0006-record-locations-are-discovered.md) | Record locations are discovered, not hardcoded | Accepted | 2026-08-18 |
| [0007](0007-cross-repo-stores-are-configured-not-discovered.md) | Cross-repo stores are configured, not discovered | Accepted | 2026-09-18 |
| [0008](0008-the-stores-agents-md-is-the-contract.md) | The store's `AGENTS.md` is the contract | Accepted | 2026-09-18 |

---

## Notes

- **This index is derived.** Where it disagrees with the files, the files win
  and the index is regenerated. This inverts the rule used by
  [the backlog](../backlog/README.md), whose `README.md` is authoritative —
  deliberately, because that file carries status that lives nowhere else, while
  this table carries nothing the ADRs do not already hold.
- **Numbers are sequential and never reused.** Four digits, zero-padded.
- **An accepted ADR is immutable.** A changed mind is a new ADR that supersedes
  it. The only permitted edit to an existing ADR is its `**Status**` line at
  supersede time.
- **Statuses**: `Proposed` → `Accepted` | `Rejected`, and later
  `Superseded by ADR-NNNN`. Rejected ADRs stay in the log — "we considered this
  and said no" is as useful a record as a yes.
- **What earns an ADR** — all three must hold: the consequences outlive the
  change, a competent engineer could have chosen otherwise, and the reason is
  not recoverable from the code. Rationale that fails the test belongs in the
  backlog item's `Scope Decisions` field, or nowhere.
- **Links point one way.** An ADR names the backlog item that produced it; the
  item is not required to link back.
- ADRs `0001`–`0005` were written by hand while designing
  [XAS-027](../backlog/xas-027.md), before the `design-record` skill existed to
  write them. [XAS-027f](../backlog/xas-027f.md) reconciles them against what
  the skill produces.
