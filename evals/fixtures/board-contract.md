## Board

The contract for the `next` skill and for `backlog-ops` — and for anyone moving a card by
hand. The board says what comes next and what is in progress, across repos, in the author's
order; the items stay in their repos. The skills read this section and nothing else about
this repository; keep it complete.

- **Where**: `engineering/board.md`, below the intro paragraph — one Markdown table.
- **Columns**: `| Next | In Progress |`. The header and separator rows always stay, also on an
  empty board. The two columns are independent lists: a row pairs nothing, and a shorter
  column leaves its cells empty. Each column is packed from the top — a move or a drop
  closes the gap — and a row whose two cells are both empty goes.
- **Order**: *Next* top down, rank 1 first — the position is the rank. *In Progress* newest
  pull on top.
- **Card**: `[<ITEM-ID>](<item-url>) · [<repo>](<web>) — <title> [· <why now>]`, one cell:
  the item ID linked to the item, the repo name linked to the repo, then the title. The title
  is the item's heading without its `[ID]` and done marker, in the item's own language. The
  reason is optional, the author's, and English.
  Example: `[ZK-012](https://example.com/team/notes/src/branch/main/docs/backlog/zk-012.md) · [zettelkasten](https://example.com/team/notes) — Lint rejects wiki-links · before the next export`
- **Escaping**: a `|` in a title or reason is written `\|`.
- **Links**: `<web>` is the web link on the repo's name in `engineering/repos.md`. The item
  link is `<web>` plus the item's path on the repo's default branch — GitHub
  `<web>/blob/<branch>/<path>`, Gitea `<web>/src/branch/<branch>/<path>`, Bitbucket Server
  `<web>/browse/<path>`. An address `<repo> #<n>` is written `[#<n>](<web>/issues/<n>) ·
  [<repo>](<web>)` and has no title, only the reason.
- **What a card never holds**: status or priority — they are read from the item.
- **Moves**: a pull puts the item's card into *In Progress* — out of *Next*, or new; a close
  takes it off the board. Only work gets a card: an epic and the ongoing refinement item
  never do. `put` places or moves a card in *Next*; `drop` removes one from either column.
  Every write reads the title of the card it writes fresh from the item.
- **Address**: as in the logbook — `<repo>` is the name in the first column of
  `engineering/repos.md`; a repo without a backlog uses `<repo> #<issue>`. A repo missing
  from the registry gets no card: the skill says so, and the author adds the row.
- **Repos**: the registry's **Remote** column is the remote. The local checkout is
  `~/dev/<org>/<repo>`, where `<org>` and `<repo>` are the remote's path
  (`git@example.com:team/notes.git` → `~/dev/team/notes`). A repo not cloned there is
  cloned there, after the author agrees.
- **Commit**: one commit per change, pushed immediately, with the subject
  `docs(board): <put|drop|pull|close> · <repo> · <text> (<ITEM-ID>)` — `<text>` is the new
  position, the reason for a drop — or the item's title when the author gave none — or the
  item's title on a pull or close.
- **Language**: English (`asf/CONVENTIONS.md` → Language).

