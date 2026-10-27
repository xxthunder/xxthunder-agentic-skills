## Logbook

The contract for the `logbook` skill — and for anyone writing a log line by hand. The log is
the chronicle of work across repos: one line per event, never edited. The skill reads this
section and nothing else about this repository; keep it complete.

- **Where**: `engineering/log.md`.
- **Order**: newest first — day headings `## YYYY-MM-DD` descending, and within a day the
  newest line directly under the heading. Always insert at the top, never append.
- **Line types**: `started`, `note`, `done` — nothing else.
- **Line format**: `- **<type>** · <repo> <ITEM-ID> · <text> [· links]`, English, one line.
  Example: `- **done** · zettelkasten ZK-012 · Lint rejects wiki-links → [link-rules](link-rules.md)`
- **Address**: `<repo> <ITEM-ID>`. `<repo>` is the name in the first column of
  `engineering/repos.md`, which resolves it to remote and ID prefix; a repo without a backlog
  uses `<repo> #<issue>`. A repo missing from the registry gets a row there first.
- **Duplicates**: before writing `started`, look for an existing `started` line for the same
  address without a later `done` — resumption is not a new start, write nothing.
- **Append-only**: never edit or delete a line; a correction is a new line. One exception:
  links in existing lines follow when a note is renamed or moved, or when the link format
  changes — Obsidian does renames and moves itself (`alwaysUpdateLinks`), anyone working
  outside it does the same. Only the link's target and form change, never the text.
- **Links**: relative Markdown links to notes and learnings in this repository where they
  exist, link text the file name without `.md` — `[slug](slug.md)` within `engineering/`,
  `[slug](../learnings/slug.md)` for a learning. No wiki-links; `asf/scripts/lint.sh` checks
  them like in every area file.
- **Commit**: one commit per line, pushed immediately.
- **Language**: English (`asf/CONVENTIONS.md` → Language).

