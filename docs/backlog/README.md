# Backlog

## Status Legend

- **Open** - Ready to be picked up
- **In Progress** - Currently being worked on
- **Done** - Completed

## Table of Contents

### Open
- [XAS-003 — Multi-agent skill authoring (single source, multi-target)](xas-003.md)
- [XAS-003a — Define canonical skill source format](xas-003a.md)
- [XAS-003b — Build generator that emits Claude Code plugin artifacts](xas-003b.md)
- [XAS-003c — Document how to add a new agent target](xas-003c.md)
- [XAS-004 — Marketplace tooling and CI](xas-004.md)
- [XAS-004a — Pre-commit validation of canonical source format](xas-004a.md)
- [XAS-004b — Auto-sync version between plugin.json and marketplace.json](xas-004b.md)
- [XAS-004c — CI check that generated artifacts match canonical sources](xas-004c.md)
- [XAS-015a — Add auto-file skill (sort into configurable folder structure)](xas-015a.md)
- [XAS-015e — Harden split-batch page-number rule: detect self-contained pages](xas-015e.md)
- [XAS-026c — Claude Code interactive bot (`@claude` mentions)](xas-026c.md)
- [XAS-026d — JSON schema validation for `marketplace.json` and `plugin.json`](xas-026d.md)
- [XAS-026e — PR title conventional-commit linter](xas-026e.md)
- [XAS-026f — Coverage thresholds via `codecov.yml`](xas-026f.md)
- [XAS-029 — Semantic release via Release Please](xas-029.md)
- [XAS-034 — `zettelkasten` skill: consult and feed a personal learnings repo from any session](xas-034.md)

### In Progress
- [XAS-001 — Backlog refinement](xas-001.md)
- [XAS-015 — Launch xxthunder-paperless-skills plugin](xas-015.md)
- [XAS-026 — CI / GitHub Actions setup](xas-026.md)
- [XAS-027 — Agentic Engineering-as-Code — durable design record](xas-027.md)
- [XAS-027g — Verify in a consuming repo; retire the per-repo `AGENTS.md` text](xas-027g.md)
- [XAS-032 — Establish whether `retrospective` triggers in practice](xas-032.md)

### Done
- [XAS-002 — Rename repo and restructure as agentic-skills marketplace](xas-002.md)
- [XAS-005 — Phase 1 — Rename GitHub repo and update URL references](xas-005.md)
- [XAS-006 — Phase 2 — Rename marketplace registry and update manifest descriptions](xas-006.md)
- [XAS-007 — Phase 2 — Rewrite README to describe marketplace purpose](xas-007.md)
- [XAS-014 — Phase 2 — Restructure to multi-plugin marketplace layout](xas-014.md)
- [XAS-015b — Add split-batch skill (detect + split multi-document PDFs)](xas-015b.md)
- [XAS-015c — Unit test harness + backfill for plugin Python scripts](xas-015c.md)
- [XAS-015d — Privacy opt-in for LLM content analysis in naps2-scan and split-batch](xas-015d.md)
- [XAS-016 — Scaffold xxthunder-paperless-skills plugin and register in marketplace](xas-016.md)
- [XAS-017 — Migrate simplex-merge from user-global skills into the plugin](xas-017.md)
- [XAS-018 — Add naps2-scan skill (scan → OCR → merge → filename proposal)](xas-018.md)
- [XAS-020 — Document ExcludeBlankPages profile option in naps2-scan](xas-020.md)
- [XAS-021 — Persist naps2-scan session settings across invocations](xas-021.md)
- [XAS-022 — Migrate simplex-merge to uv-run script with PEP 723 deps](xas-022.md)
- [XAS-023 — Fix skill trigger descriptions so new scans pick naps2-scan](xas-023.md)
- [XAS-024 — Persist scanner type (simplex/duplex) in naps2-scan config](xas-024.md)
- [XAS-025 — Scrum conventions and backlog-ops skill](xas-025.md)
- [XAS-026a — Pytest workflow on push/PR (matrix: ubuntu + windows)](xas-026a.md)
- [XAS-026b — Coverage upload + JUnit test report](xas-026b.md)
- [XAS-026g — Codecov status badge in README](xas-026g.md)
- [XAS-026h — Grant `checks: write` so the JUnit report can publish](xas-026h.md)
- [XAS-027a — `design-record` skill: ADR authoring, numbering, index](xas-027a.md)
- [XAS-027b — `design-record` skill: `architecture.md` slots and diagram editing](xas-027b.md)
- [XAS-027c — `SessionStart` orientation hook](xas-027c.md)
- [XAS-027d — `architecture-scan` skill: bootstrap and drift report](xas-027d.md)
- [XAS-027e — Wire-up: `refinement`, `tdd-workflow`, `commit-helper`](xas-027e.md)
- [XAS-027f — Dogfood: this repo's own `architecture.md` and ADRs](xas-027f.md)
- [XAS-027h — ADR-log invariant tests](xas-027h.md)
- [XAS-027i — Widen record discovery to nested layouts](xas-027i.md)
- [XAS-027j — Correct the lifetime wording; lift durable design at close](xas-027j.md)
- [XAS-027k — ADRs record decisions, not specifications](xas-027k.md)
- [XAS-028 — Declare the `superpowers` dependency in the marketplace](xas-028.md)
- [XAS-030 — Remove `tdd-workflow`](xas-030.md)
- [XAS-031 — `commit-helper` cites the verification gate instead of restating it](xas-031.md)
- [XAS-033 — Backlog TOC invariant tests](xas-033.md)

---

## Notes

- **ID prefix**: `XAS` (xxthunder-agentic-skills)
- **Top-level items** use `XAS-###` (zero-padded sequential). **Substories** append a letter suffix: `XAS-003a`, `XAS-003b`, …
- An item is an **epic** iff at least one substory (letter-suffixed sibling) exists. No explicit "epic" type field; no explicit back-reference from substories to the parent (the suffix encodes it).
- Epic status is **derived** from its substories — an epic stays out of `Done` while any substory is not `Done`. The `backlog-ops` skill handles this cascade automatically.
- TOC is **flat** — no "Stories under X" groupings. Each item sits in the section matching **its own** status, so an epic and its substories may appear in different sections at the same time (e.g., an In-Progress epic with one substory In Progress and two still Open). Natural sort by ID keeps related rows adjacent *within* a section when they happen to share a status.
- Legacy Done substories under XAS-015 (XAS-016 through XAS-024, excluding XAS-015a) use bare sequential IDs — they predate the convention and are not renamed.
- Keep items actionable with clear acceptance criteria.
- Do NOT list commit hashes in backlog entries — the backlog is part of the commit itself, so hashes are circular and go stale after squash/rebase.
