# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Mechanical edits of the Kanban board: the script owns the board's format (XAS-060, ADR-0017).

The board is one Markdown table, `| Next | In Progress |`, of cards. `put`, `drop`,
`pull` and `close` edit it; the skills call this script instead of editing the
table by hand. Every line outside the table rows stays byte for byte, line
endings included. Paths of the board and the registry arrive as arguments.
"""
from __future__ import annotations

import argparse
import itertools
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from backlog import (BACKLOG_IN_REPO, REMOTE, BacklogError, Item, epics, git, is_work_in_progress, item_path, parse_item,
                     read_text, remote_backlog, write_text)

COLUMNS = ["Next", "In Progress"]
# The first two header cells of the registry tables we read: value is "is it the Jira table".
REGISTRY_HEADS = {("Repo", "Remote"): False, ("Jira project", "Site"): True}
CELL_SPLIT_RE = re.compile(r"(?<!\\)\|")
SEPARATOR_RE = re.compile(r"^\|[\s:|-]+\|$")
LINK_RE = re.compile(r"\[((?:[^\]\\]|\\.)*)\]\(([^)]*)\)")
CARD_HEAD_RE = re.compile(rf"^{LINK_RE.pattern} · {LINK_RE.pattern}")
REASON_SEP = " · "
TITLE_SEP = " — "
ISSUE_RE = re.compile(r"^#\d+$")


@dataclass(frozen=True)
class RegistryEntry:
    """A row of the registry: a repo of the repos table or a project of the Jira table."""

    name: str
    web: str
    site: str  # the Site column of a Jira project (its base URL); empty for a repo
    jira: bool
    key: str = ""  # the Key column of a Jira project; empty for a repo


@dataclass
class Table:
    """The board table: the line range of its rows and the two columns, packed."""

    start: int  # index of the first row line (after header and separator)
    end: int  # index after the last row line
    columns: list[list[str]]


def cells_of(line: str) -> list[str]:
    """The cells of a table row, split on unescaped pipes and stripped."""
    parts = CELL_SPLIT_RE.split(line.strip())
    return [c.strip() for c in parts[1:-1]]


def is_row(line: str) -> bool:
    stripped = line.strip()
    return len(stripped) > 1 and stripped.startswith("|") and stripped.endswith("|")


def read_registry(path: Path) -> dict[str, RegistryEntry]:
    """Both tables of the registry, keyed by the link text of the first column."""
    text, _ = read_text(path)
    entries: dict[str, RegistryEntry] = {}
    kind: bool | None = None  # None outside a table, else: is it the Jira table?
    for line in text.split("\n"):
        if not is_row(line):
            kind = None
            continue
        cells = cells_of(line)
        if cells[0] in ("Repo", "Jira project"):  # a header row: another table of the file reads as none
            kind = REGISTRY_HEADS.get(tuple(cells[:2]))
            continue
        if kind is None or SEPARATOR_RE.match(line.strip()) or len(cells) < 2:
            continue
        link = LINK_RE.match(cells[0])
        if link is None:
            continue
        second = cells[1].strip("`")
        entries[link.group(1)] = RegistryEntry(link.group(1), link.group(2), second if kind else "", kind,
                                               cells[2].strip("`") if kind and len(cells) > 2 else "")
    return entries


def find_table(lines: list[str]) -> Table:
    """Locate the `| Next | In Progress |` table; its rows become two packed columns."""
    for i, line in enumerate(lines[:-1]):
        if is_row(line) and cells_of(line) == COLUMNS and SEPARATOR_RE.match(lines[i + 1].strip()):
            start = i + 2
            end = start
            while end < len(lines) and is_row(lines[end]):
                end += 1
            columns: list[list[str]] = [[], []]
            for row in lines[start:end]:
                cells = cells_of(row)
                if len(cells) > len(COLUMNS):
                    raise BacklogError(f"a board row has {len(cells)} cells, the table has {len(COLUMNS)}: {row}")
                for column, cell in zip(columns, cells):
                    if cell:
                        column.append(cell)
            return Table(start, end, columns)
    raise BacklogError("no '| Next | In Progress |' table in the board file")


def render_rows(columns: list[list[str]]) -> list[str]:
    """The rows of the packed columns; an empty cell renders as a space between pipes."""
    rows = itertools.zip_longest(*columns, fillvalue="")
    return ["|" + "".join(f" {cell} |" if cell else " |" for cell in row) for row in rows]


def card_id(card: str) -> tuple[str, str] | None:
    """A card's identity: its first link text and its second."""
    head = CARD_HEAD_RE.match(card)
    return (head.group(1), head.group(3)) if head else None


def card_tail(card: str) -> str | None:
    """The text after ' — ' on a card (the title and its reason); None for a card without a title."""
    head = CARD_HEAD_RE.match(card)
    rest = card[head.end():] if head else ""
    return rest[len(TITLE_SEP):] if rest.startswith(TITLE_SEP) else None


def card_title(card: str) -> str | None:
    """The title as written: the tail up to the reason; None for a card without one."""
    title = card_tail(card)
    if title is None:
        return None
    if REASON_SEP in title:
        title = title.rsplit(REASON_SEP, 1)[0]
    return title.replace("\\|", "|")


def find_card(columns: list[list[str]], item_id: str, repo: str) -> tuple[int, int] | None:
    """(column, index) of the card with this ID, compared case-insensitively; an issue `#n` also needs the repo's name."""
    for c, column in enumerate(columns):
        for i, card in enumerate(column):
            identity = card_id(card)
            if identity and identity[0].casefold() == item_id.casefold() and (not item_id.startswith("#") or identity[1] == repo):
                return c, i
    return None


def registry_entry(registry: Path, repo: str) -> RegistryEntry:
    entry = read_registry(registry).get(repo)
    if entry is None:
        raise BacklogError(f"{repo!r} is not in the registry {registry}")
    return entry


def save(board: Path, lines: list[str], table: Table, columns: list[list[str]], crlf: bool) -> None:
    """Write *columns* back as the table's rows; every other line stays."""
    lines[table.start:table.end] = render_rows(columns)
    write_text(board, "\n".join(lines), crlf)


def remove_card(board: Path, registry: Path, repo: str, item_id: str, verb: str) -> list[str]:
    """Drop or close: remove the card, pack the columns, keep every other line. Returns stdout lines."""
    registry_entry(registry, repo)
    text, crlf = read_text(board)
    lines = text.split("\n")
    table = find_table(lines)
    found = find_card(table.columns, item_id, repo)
    if found is None:
        return [f"unchanged: {item_id} is not on the board"]
    column, index = found
    card = table.columns[column].pop(index)
    save(board, lines, table, table.columns, crlf)
    out = [f"changed: {verb} {item_id}, removed from {COLUMNS[column]}"]
    title = card_title(card)
    if title is not None:
        out.append(f"title: {title}")
    return out


def escape(text: str) -> str:
    """Text for a card: a pipe would split the cell."""
    return text.replace("|", "\\|")


def default_branch(repo: Path) -> str:
    """The branch the item links point to: the remote's default branch, else the current one."""
    try:
        return git(repo, "symbolic-ref", "--short", f"refs/remotes/{REMOTE}/HEAD").decode("utf-8").strip().removeprefix(f"{REMOTE}/")
    except BacklogError:
        branch = git(repo, "branch", "--show-current").decode("utf-8").strip()
        if not branch:
            raise BacklogError(f"{repo}: detached HEAD and no remote HEAD; cannot name a branch for the item link")
        return branch


def item_url(web: str, branch: str, item_id: str) -> str:
    """Where the item file lives on the web, by the kind of forge the repo's web link names."""
    parts = urlparse(web)
    name = f"{BACKLOG_IN_REPO}/{item_id.lower()}.md"
    if parts.hostname == "github.com":
        return f"{web}/blob/{branch}/{name}"
    if re.search(r"/projects/[^/]+/repos/[^/]+", parts.path):
        return f"{web}/browse/{name}"
    return f"{web}/src/branch/{branch}/{name}"


def card_reason(card: str, title: str | None) -> str:
    """The reason as written on *card*, '' for none. *title* is the card's fresh title;
    None for an issue card, which has no title: its reason is whatever follows the links."""
    if title is None:
        head = CARD_HEAD_RE.match(card)
        return (card[head.end():] if head else "").removeprefix(REASON_SEP)
    rest = card_tail(card)
    fresh = escape(title)
    if rest is None or rest == fresh:
        return ""
    if rest.startswith(fresh + REASON_SEP):
        return rest[len(fresh) + len(REASON_SEP):]
    return rest.rsplit(REASON_SEP, 1)[1] if REASON_SEP in rest else ""


def read_item(directory: Path | None, checkout: Path | None, item_id: str) -> tuple[Item, bool, str]:
    """(item, is it work in progress, branch), read from a backlog directory or from a checkout's remote."""
    def load(backlog: Path) -> tuple[Item, bool]:
        item = parse_item(item_path(backlog, item_id))
        return item, is_work_in_progress(item, epics(backlog))

    if directory is not None:
        return *load(directory), default_branch(directory)
    if checkout is not None:
        with remote_backlog(checkout) as backlog:
            item, wip = load(backlog)
        return item, wip, default_branch(checkout)
    raise BacklogError("name the backlog with --dir or --repo")


def check_id(entry: RegistryEntry, item_id: str) -> None:
    """A Jira project takes `<Key>-<n>` of its own key, a repo an item ID or `#<n>`."""
    if entry.jira:
        if not re.fullmatch(rf"{re.escape(entry.key)}-\d+", item_id):
            raise BacklogError(f"{item_id}: a card of Jira project {entry.name!r} is written {entry.key}-<number>")
    elif item_id.startswith("#") and not ISSUE_RE.match(item_id):
        raise BacklogError(f"{item_id}: an issue is written #<number>")


def look_up(args: argparse.Namespace) -> tuple[Item | None, bool, str]:
    """(item, is it work in progress, branch) of an item ID; an issue `#n` has no item."""
    if args.id.startswith("#"):
        return None, True, ""
    return read_item(args.dir, args.checkout, args.id)


def derived_card(entry: RegistryEntry, item_id: str, title: str | None, branch: str, old: str | None,
                 given: str | None = None) -> str:
    """An item card, or an issue card when *title* is None, built fresh; the reason of *old* stays
    unless *given* replaces it."""
    if title is None:
        link = f"[{item_id}]({entry.web}/issues/{item_id[1:]})"
    else:
        link = f"[{item_id}]({item_url(entry.web, branch, item_id)})"
    reason = card_reason(old, title) if old else ""
    return build_card(link, entry, title, escape(given) if given is not None else reason)


def build_card(link: str, entry: RegistryEntry, title: str | None, reason: str) -> str:
    return (f"{link} · [{entry.name}]({entry.web})" + (f"{TITLE_SEP}{escape(title)}" if title is not None else "")
            + (f"{REASON_SEP}{reason}" if reason else ""))


def jira_card(entry: RegistryEntry, args: argparse.Namespace, old: str | None) -> tuple[str, str]:
    """(card, title) of a Jira card. A Jira card is a snapshot: one on the board keeps its summary as
    written and takes only a new reason, a new one takes the summary given with --title."""
    if old is None:
        if args.title is None:
            raise BacklogError(f"{args.id} has no card: give its summary with --title")
        link = f"[{args.id}]({entry.site.rstrip('/')}/browse/{args.id})"
        return build_card(link, entry, args.title, escape(args.reason or "")), args.title
    if args.reason is None:
        return old, card_title(old)
    tail = card_tail(old) or ""
    base = old[:old.rindex(REASON_SEP)] if REASON_SEP in tail else old
    return base + (f"{REASON_SEP}{escape(args.reason)}" if args.reason else ""), card_title(old)


def put_card(board: Path, registry: Path, args: argparse.Namespace) -> list[str]:
    """Place or move a card in Next. Returns stdout lines."""
    entry = registry_entry(registry, args.repo)
    if args.title is not None and not entry.jira:
        raise BacklogError("--title is for the card of a Jira issue")
    if args.at is not None and args.at < 1:
        raise BacklogError("--at counts from 1")
    check_id(entry, args.id)
    text, crlf = read_text(board)
    lines = text.split("\n")
    table = find_table(lines)
    columns = [list(column) for column in table.columns]
    nxt = columns[0]
    found = find_card(columns, args.id, args.repo)
    if found and found[0] == 1:
        raise BacklogError(f"{args.id} is in {COLUMNS[1]}; put would move work back to waiting")
    old = nxt.pop(found[1]) if found else None
    if entry.jira:
        card, title = jira_card(entry, args, old)
    else:
        item, _, branch = look_up(args)
        title = item.title if item else None
        card = derived_card(entry, item.id if item else args.id, title, branch, old, args.reason)
    if args.after is not None:
        after = find_card([nxt], args.after, args.repo)
        if after is None:
            raise BacklogError(f"{args.after} is not in {COLUMNS[0]}")
        index = after[1] + 1
    elif args.at is not None:
        index = min(args.at - 1, len(nxt))
    else:
        index = 0
    nxt.insert(index, card)
    title_line = [] if title is None else [f"title: {title}"]
    if columns == table.columns:
        return [f"unchanged: {args.id} is already at position {index + 1} in {COLUMNS[0]}", *title_line]
    save(board, lines, table, columns, crlf)
    verb = "moved" if found else "placed"
    return [f"changed: {verb} {args.id} to position {index + 1} in {COLUMNS[0]}", *title_line]


def pull_card(board: Path, registry: Path, args: argparse.Namespace) -> list[str]:
    """Move a card to the top of In Progress, out of Next or new. Returns stdout lines."""
    entry = registry_entry(registry, args.repo)
    check_id(entry, args.id)
    text, crlf = read_text(board)
    lines = text.split("\n")
    table = find_table(lines)
    columns = [list(column) for column in table.columns]
    found = find_card(columns, args.id, args.repo)
    old = columns[found[0]].pop(found[1]) if found else None
    if entry.jira:
        if old is None:
            return [f"unchanged: {args.id} has no card; put it on the board first"]
        card, title = old, card_title(old)
    else:
        item, wip, branch = look_up(args)
        if not wip:
            return [f"unchanged: {args.id} is not work in progress (status {item.status}; an epic or the "
                    "refinement item gets no card)", f"title: {item.title}"]
        title = item.title if item else None
        card = derived_card(entry, item.id if item else args.id, title, branch, old)
    title_line = [] if title is None else [f"title: {title}"]
    index = found[1] if found and found[0] == 1 else 0
    columns[1].insert(index, card)
    if columns == table.columns:
        return [f"unchanged: {args.id} is already in {COLUMNS[1]}", *title_line]
    save(board, lines, table, columns, crlf)
    where = f"refreshed in {COLUMNS[1]}" if found and found[0] == 1 else f"moved to the top of {COLUMNS[1]}"
    return [f"changed: {args.id} {where}", *title_line]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--board", type=Path, required=True, help="the board file")
    parser.add_argument("--registry", type=Path, required=True, help="the registry of repos and Jira projects")
    sub = parser.add_subparsers(dest="command", required=True)

    def where(p: argparse.ArgumentParser) -> None:
        group = p.add_mutually_exclusive_group()
        group.add_argument("--dir", type=Path, help="read the item from this backlog directory (working tree)")
        group.add_argument("--repo", type=Path, dest="checkout",
                           help="read the item from this checkout at its remote's default branch, after a fetch")

    p_put = sub.add_parser("put", help="place or move a card in Next")
    p_put.add_argument("repo")
    p_put.add_argument("id")
    where(p_put)
    position = p_put.add_mutually_exclusive_group()
    position.add_argument("--at", type=int, help="rank in Next, 1 is the top")
    position.add_argument("--after", metavar="ID", help="put the card right after this card of Next")
    p_put.add_argument("--reason", help="why now")
    p_put.add_argument("--title", help="the summary of a Jira card")
    p_pull = sub.add_parser("pull", help="move a card from Next, or a new one, to the top of In Progress")
    p_pull.add_argument("repo")
    p_pull.add_argument("id")
    where(p_pull)
    for name, text in (("drop", "remove a card from either column"), ("close", "take a finished item's card off the board")):
        p = sub.add_parser(name, help=text)
        p.add_argument("repo")
        p.add_argument("id")
    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    try:
        if args.command == "put":
            for line in put_card(args.board, args.registry, args):
                print(line)
        elif args.command == "pull":
            for line in pull_card(args.board, args.registry, args):
                print(line)
        else:
            verb = "dropped" if args.command == "drop" else "closed"
            for line in remove_card(args.board, args.registry, args.repo, args.id, verb):
                print(line)
    except (BacklogError, OSError) as e:
        print(f"board: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
