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

from backlog import BacklogError, git, item_path, parse_item, read_text, remote_backlog, write_text

COLUMNS = ["Next", "In Progress"]
# The first two header cells of the registry tables we read: value is "is it the Jira table".
REGISTRY_HEADS = {("Repo", "Remote"): False, ("Jira project", "Site"): True}
CELL_SPLIT_RE = re.compile(r"(?<!\\)\|")
SEPARATOR_RE = re.compile(r"^\|[\s:|-]+\|$")
LINK_RE = re.compile(r"\[((?:[^\]\\]|\\.)*)\]\(([^)]*)\)")
CARD_HEAD_RE = re.compile(rf"^{LINK_RE.pattern} · {LINK_RE.pattern}")
REASON_SEP = " · "
TITLE_SEP = " — "
NOT_IMPLEMENTED = "{} is not implemented yet"


@dataclass(frozen=True)
class RegistryEntry:
    """A row of the registry: a repo of the repos table or a project of the Jira table."""

    name: str
    web: str
    remote: str  # the Remote column of a repo; empty for a Jira project
    site: str  # the Site column of a Jira project (its base URL); empty for a repo
    jira: bool


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
        entries[link.group(1)] = RegistryEntry(link.group(1), link.group(2), "" if kind else second,
                                               second if kind else "", kind)
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


def card_title(card: str) -> str | None:
    """The title as written: the text after ' — ' up to the reason; None for a card without one."""
    head = CARD_HEAD_RE.match(card)
    rest = card[head.end():] if head else ""
    if not rest.startswith(TITLE_SEP):
        return None
    title = rest[len(TITLE_SEP):]
    if REASON_SEP in title:
        title = title.rsplit(REASON_SEP, 1)[0]
    return title.replace("\\|", "|")


def find_card(columns: list[list[str]], item_id: str, repo: str) -> tuple[int, int] | None:
    """(column, index) of the card with this ID; an issue `#n` also needs the repo's name."""
    for c, column in enumerate(columns):
        for i, card in enumerate(column):
            identity = card_id(card)
            if identity and identity[0] == item_id and (not item_id.startswith("#") or identity[1] == repo):
                return c, i
    return None


def remove_card(board: Path, registry: Path, repo: str, item_id: str, verb: str) -> list[str]:
    """Drop or close: remove the card, pack the columns, keep every other line. Returns stdout lines."""
    if repo not in read_registry(registry):
        raise BacklogError(f"{repo!r} is not in the registry {registry}")
    text, crlf = read_text(board)
    lines = text.split("\n")
    table = find_table(lines)
    found = find_card(table.columns, item_id, repo)
    if found is None:
        return [f"unchanged: {item_id} is not on the board"]
    column, index = found
    card = table.columns[column].pop(index)
    lines[table.start:table.end] = render_rows(table.columns)
    write_text(board, "\n".join(lines), crlf)
    out = [f"changed: {verb} {item_id}, removed from {COLUMNS[column]}"]
    title = card_title(card)
    if title is not None:
        out.append(f"title: {title}")
    return out


def escape(text: str) -> str:
    """Text for a card: a pipe would split the cell."""
    return text.replace("|", "\\|")


def default_branch(repo: Path) -> str:
    """The branch the item links point to: origin's default branch, else the current one."""
    try:
        return git(repo, "symbolic-ref", "--short", "refs/remotes/origin/HEAD").decode("utf-8").strip().removeprefix("origin/")
    except BacklogError:
        branch = git(repo, "branch", "--show-current").decode("utf-8").strip()
        if not branch:
            raise BacklogError(f"{repo}: detached HEAD and no origin/HEAD; cannot name a branch for the item link")
        return branch


def item_url(web: str, branch: str, item_id: str) -> str:
    """Where the item file lives on the web, by the kind of forge the repo's web link names."""
    parts = urlparse(web)
    name = f"docs/backlog/{item_id.lower()}.md"
    if parts.hostname == "github.com":
        return f"{web}/blob/{branch}/{name}"
    if re.search(r"/projects/[^/]+/repos/[^/]+", parts.path):
        return f"{web}/browse/{name}"
    return f"{web}/src/branch/{branch}/{name}"


def card_reason(card: str, title: str) -> str:
    """The reason as written on *card*, '' for none. *title* is the card's fresh title."""
    head = CARD_HEAD_RE.match(card)
    rest = card[head.end():] if head else ""
    if not rest.startswith(TITLE_SEP):
        return ""
    rest = rest[len(TITLE_SEP):]
    fresh = escape(title)
    if rest == fresh:
        return ""
    if rest.startswith(fresh + REASON_SEP):
        return rest[len(fresh) + len(REASON_SEP):]
    return rest.rsplit(REASON_SEP, 1)[1] if REASON_SEP in rest else ""


def read_item(directory: Path | None, checkout: Path | None, item_id: str) -> tuple[str, str]:
    """(title, branch) of an item, read from a backlog directory or from a checkout's remote."""
    if directory is not None:
        return parse_item(item_path(directory, item_id)).title, default_branch(directory)
    if checkout is not None:
        with remote_backlog(checkout) as backlog:
            title = parse_item(item_path(backlog, item_id)).title
        return title, default_branch(checkout)
    raise BacklogError("name the backlog with --dir or --repo")


def put_card(board: Path, registry: Path, args: argparse.Namespace) -> list[str]:
    """Place or move an item's card in Next. Returns stdout lines."""
    entry = read_registry(registry).get(args.repo)
    if entry is None:
        raise BacklogError(f"{args.repo!r} is not in the registry {registry}")
    if args.title is not None and not entry.jira:
        raise BacklogError("--title is for the card of a Jira issue")
    if args.at is not None and args.at < 1:
        raise BacklogError("--at counts from 1")
    if entry.jira or args.id.startswith("#"):
        raise BacklogError(NOT_IMPLEMENTED.format("put of a Jira issue or an issue number"))
    title, branch = read_item(args.dir, args.checkout, args.id)
    text, crlf = read_text(board)
    lines = text.split("\n")
    table = find_table(lines)
    columns = [list(column) for column in table.columns]
    nxt = columns[0]
    found = find_card(columns, args.id, args.repo)
    if found and found[0] == 1:
        raise BacklogError(f"{args.id} is in {COLUMNS[1]}; put would move work back to waiting")
    reason = ""
    if found:
        reason = card_reason(nxt.pop(found[1]), title)
    if args.reason is not None:
        reason = escape(args.reason)
    if args.after is not None:
        after = find_card([nxt], args.after, args.repo)
        if after is None:
            raise BacklogError(f"{args.after} is not in {COLUMNS[0]}")
        index = after[1] + 1
    elif args.at is not None:
        index = min(args.at - 1, len(nxt))
    else:
        index = 0
    card = (f"[{args.id}]({item_url(entry.web, branch, args.id)}) · [{entry.name}]({entry.web})"
            f"{TITLE_SEP}{escape(title)}" + (f"{REASON_SEP}{reason}" if reason else ""))
    nxt.insert(index, card)
    if columns == table.columns:
        return [f"unchanged: {args.id} is already at position {index + 1} in {COLUMNS[0]}", f"title: {title}"]
    lines[table.start:table.end] = render_rows(columns)
    write_text(board, "\n".join(lines), crlf)
    verb = "moved" if found else "placed"
    return [f"changed: {verb} {args.id} to position {index + 1} in {COLUMNS[0]}", f"title: {title}"]


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
        elif args.command in ("drop", "close"):
            verb = "dropped" if args.command == "drop" else "closed"
            for line in remove_card(args.board, args.registry, args.repo, args.id, verb):
                print(line)
        else:
            raise BacklogError(NOT_IMPLEMENTED.format(args.command))
    except (BacklogError, OSError) as e:
        print(f"board: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
