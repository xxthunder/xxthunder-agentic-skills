# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Mechanical backlog operations: the item files are the truth (ADR-0009).

The README's table of contents is derived from the items and rewritten by
this script; the skills call it instead of editing the TOC by hand.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

ITEM_FILE_RE = re.compile(r"^([a-z]+)-(\d{3})([a-z]?)\.md$")
HEADING_RE = re.compile(r"^#\s+\[([A-Z]+-\d{3}[a-z]?)\]\s*(.*)$", re.M)
STATUS_RE = re.compile(r"^\*\*Status\*\*:[ \t]*(.+?)[ \t]*$", re.M)
TOC_LINE_RE = re.compile(r"^\s*- \[.*?\]\(([a-z]+-\d{3}[a-z]?\.md)\)")
PREFIX_NOTE_RE = re.compile(r"\*\*ID prefix\*\*:\s*`([A-Z]+)`")
DATE_RE = re.compile(r"\((.+)\)$")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
CODE_RE = re.compile(r"^```.*?^```|`[^`\n]+`", re.M | re.S)
SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
DONE_MARK = "✅ DONE - "

SECTIONS = ("Open", "In Progress", "Done", "Superseded")
ALWAYS_SHOWN = ("Open", "In Progress", "Done")
CLOSED = ("Done", "Superseded")
TOC_HEADING = "## Table of Contents"


class BacklogError(Exception):
    """A backlog the script cannot work on safely; the message says why."""


@dataclass(frozen=True)
class Item:
    path: Path
    id: str
    title: str
    status: str
    marked: bool

    @property
    def sort_key(self) -> tuple[str, int, str]:
        prefix, number, letter = ITEM_FILE_RE.match(self.path.name).groups()
        return prefix, int(number), letter

    @property
    def section(self) -> str:
        for name in SECTIONS:
            if self.status == name or self.status.startswith(f"{name} ("):
                return name
        raise BacklogError(f"{self.path.name}: unknown status {self.status!r}")


def read_text(path: Path) -> tuple[str, bool]:
    """Return the file's text with LF line endings, and whether it used CRLF."""
    raw = path.read_bytes().decode("utf-8")
    return raw.replace("\r\n", "\n"), "\r\n" in raw


def write_text(path: Path, text: str, crlf: bool) -> None:
    path.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))


def item_files(backlog: Path) -> list[Path]:
    return sorted(p for p in backlog.iterdir() if ITEM_FILE_RE.match(p.name))


def parse_item(path: Path) -> Item:
    text, _ = read_text(path)
    heading = HEADING_RE.search(text)
    status = STATUS_RE.search(text)
    if heading is None:
        raise BacklogError(f"{path.name}: no '# [PREFIX-###] Title' heading")
    if status is None:
        raise BacklogError(f"{path.name}: no '**Status**:' line")
    title = heading.group(2).removeprefix(DONE_MARK)
    marked = heading.group(2).startswith(DONE_MARK)
    return Item(path, heading.group(1), title, status.group(1), marked)


def load_items(backlog: Path) -> list[Item]:
    return [parse_item(p) for p in item_files(backlog)]


def render_toc(items: list[Item]) -> str:
    """The TOC block body: one section per status, newest ID first."""
    by_section: dict[str, list[Item]] = {name: [] for name in SECTIONS}
    for item in items:
        by_section[item.section].append(item)
    out = []
    for name in SECTIONS:
        members = sorted(by_section[name], key=lambda i: i.sort_key, reverse=True)
        if not members and name not in ALWAYS_SHOWN:
            continue
        out.append(f"### {name}\n")
        out.extend(f"- [{i.id} — {i.title}]({i.path.name})\n" for i in members)
        out.append("\n")
    return "".join(out)


def toc_block(lines: list[str]) -> tuple[int, int]:
    """Line indices (start, end) of the TOC body: after its heading, up to the
    next level-two heading or horizontal rule, or the end of the file."""
    try:
        start = lines.index(TOC_HEADING) + 1
    except ValueError:
        raise BacklogError(f"README.md: no '{TOC_HEADING}' heading") from None
    end = start
    while end < len(lines) and not (lines[end].startswith("## ") or lines[end] == "---"):
        end += 1
    return start, end


def check_block_is_derived(lines: list[str], start: int, end: int, backlog: Path) -> None:
    """Refuse any line in the TOC block that no item produces."""
    headings = {f"### {name}" for name in SECTIONS}
    for n in range(start, end):
        line = lines[n]
        if not line.strip() or line in headings:
            continue
        link = TOC_LINE_RE.match(line)
        if link and (backlog / link.group(1)).is_file():
            continue
        raise BacklogError(
            f"README.md:{n + 1}: {line!r} is not derived from an item; "
            "move it out of the table of contents"
        )


def derived_readme(backlog: Path) -> tuple[str, str, bool]:
    """Return (current, derived) README text and whether it uses CRLF."""
    current, crlf = read_text(backlog / "README.md")
    lines = current.split("\n")
    start, end = toc_block(lines)
    check_block_is_derived(lines, start, end, backlog)
    head = "\n".join(lines[:start]) + "\n\n"
    tail = "\n".join(lines[end:])
    return current, head + render_toc(load_items(backlog)) + tail, crlf


def write_toc(backlog: Path) -> None:
    current, derived, crlf = derived_readme(backlog)
    if derived != current:
        write_text(backlog / "README.md", derived, crlf)


def id_prefix(backlog: Path) -> str:
    """The prefix a new item takes, as stated in the README's Notes."""
    text, _ = read_text(backlog / "README.md")
    m = PREFIX_NOTE_RE.search(text)
    if m is None:
        raise BacklogError("README.md: no '**ID prefix**: `PREFIX`' line in the Notes")
    return m.group(1)


def next_id(backlog: Path, parent: str | None = None) -> str:
    """The next free top-level ID, or the next substory ID under *parent*."""
    prefix = id_prefix(backlog).lower()
    parts = [ITEM_FILE_RE.match(p.name).groups() for p in item_files(backlog)]
    if parent is None:
        numbers = [int(n) for pre, n, _ in parts if pre == prefix]
        return f"{prefix.upper()}-{max(numbers, default=0) + 1:03d}"
    m = re.fullmatch(r"([A-Za-z]+)-(\d{3})", parent)
    if m is None or not (backlog / f"{parent.lower()}.md").is_file():
        raise BacklogError(f"{parent}: no such top-level item to add a substory to")
    pre, number = m.group(1).lower(), m.group(2)
    letters = [letter for p, n, letter in parts if p == pre and n == number and letter]
    following = chr(ord(max(letters)) + 1) if letters else "a"
    return f"{parent.upper()}{following}"


def find_item(backlog: Path, item_id: str) -> Item:
    path = backlog / f"{item_id.lower()}.md"
    if not ITEM_FILE_RE.match(path.name) or not path.is_file():
        raise BacklogError(f"{item_id}: no such item")
    return parse_item(path)


def substories(items: list[Item], epic: Item) -> list[Item]:
    prefix, number, letter = epic.sort_key
    if letter:
        return []
    return [i for i in items if i.sort_key[:2] == (prefix, number) and i.sort_key[2]]


def is_closed(item: Item) -> bool:
    try:
        return item.section in CLOSED
    except BacklogError:
        return False


def open_substories(items: list[Item], epic: Item) -> list[str]:
    return [s.id for s in substories(items, epic) if not is_closed(s)]


def parent_of(backlog: Path, item: Item) -> Item | None:
    prefix, number, letter = item.sort_key
    path = backlog / f"{prefix}-{number:03d}.md"
    return parse_item(path) if letter and path.is_file() else None


def write_status(item: Item, status: str, today: str) -> None:
    """Rewrite the item's status line and heading marker; nothing else."""
    text, crlf = read_text(item.path)
    value = f"{status} ({today})" if status in CLOSED else status
    text = STATUS_RE.sub(f"**Status**: {value}", text, count=1)
    mark = DONE_MARK if status == "Done" else ""
    text = HEADING_RE.sub(lambda m: f"# [{m.group(1)}] {mark}{item.title}", text, count=1)
    write_text(item.path, text, crlf)


def set_status(backlog: Path, item_id: str, status: str, today: str) -> list[str]:
    """Set an item's status, cascade to its epic, and rewrite the TOC.

    Everything that can refuse is checked before the first file is written.
    """
    if status not in SECTIONS:
        raise BacklogError(f"unknown status {status!r}; use one of {', '.join(SECTIONS)}")
    item = find_item(backlog, item_id)
    derived_readme(backlog)
    items = load_items(backlog)
    if status == "Done":
        still_open = open_substories(items, item)
        if still_open:
            raise BacklogError(f"{item.id}: cannot close while {', '.join(still_open)} is not closed")

    messages = [f"{item.id}: {item.section} → {status}"]
    write_status(item, status, today)
    parent = parent_of(backlog, item)
    if parent is not None and status != "Open" and parent.section == "Open":
        write_status(parent, "In Progress", today)
        messages.append(f"{parent.id}: Open → In Progress (epic follows {item.id})")
    if parent is not None and status in CLOSED and parent.section not in CLOSED:
        if not open_substories(load_items(backlog), parent):
            messages.append(f"{parent.id}: every substory is closed; the epic can be closed")
    write_toc(backlog)
    return messages


def check_item(item: Item) -> list[str]:
    problems = []
    if item.id.lower() != item.path.stem:
        problems.append(f"{item.path.name}: heading says {item.id}")
    try:
        section = item.section
    except BacklogError as e:
        return problems + [str(e)]
    m = DATE_RE.search(item.status)
    if m:
        try:
            date.fromisoformat(m.group(1))
        except ValueError:
            problems.append(f"{item.path.name}: date {m.group(1)!r} does not parse")
    if item.marked and section != "Done":
        problems.append(f"{item.path.name}: heading marked DONE but status is {item.status!r}")
    return problems


def check_links(path: Path) -> list[str]:
    problems = []
    text, _ = read_text(path)
    for target in LINK_RE.findall(CODE_RE.sub("", text)):
        target = target.split("#", 1)[0].strip()
        if not target or SCHEME_RE.match(target):
            continue
        if not (path.parent / target).exists():
            problems.append(f"{path.name}: link {target!r} resolves to nothing")
    return problems


def check(backlog: Path) -> list[str]:
    """Every problem in the backlog, as one line each; empty when clean."""
    problems: list[str] = []
    items: list[Item] = []
    for path in item_files(backlog):
        try:
            items.append(parse_item(path))
        except BacklogError as e:
            problems.append(str(e))
    for item in items:
        problems += check_item(item)
    for item in items:
        if item.status.startswith("Done"):
            still_open = open_substories(items, item)
            if still_open:
                problems.append(f"{item.id} is Done while {', '.join(still_open)} is not closed")
    for path in item_files(backlog) + [backlog / "README.md"]:
        problems += check_links(path)
    try:
        current, derived, _ = derived_readme(backlog)
    except BacklogError as e:
        if str(e) not in problems:
            problems.append(str(e))
    else:
        if derived != current:
            problems.append("README.md: the table of contents differs from the items; run `backlog.py toc`")
    return problems


def find_backlog(start: Path) -> Path:
    """The nearest `docs/backlog/` with a README, from *start* upwards."""
    for d in [start, *start.parents]:
        if (d / "docs" / "backlog" / "README.md").is_file():
            return d / "docs" / "backlog"
    raise BacklogError(f"no docs/backlog/README.md above {start}; name the directory with --dir")


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", type=Path, help="backlog directory (default: docs/backlog/ of this repository)")
    sub = parser.add_subparsers(dest="command", required=True)
    p_next = sub.add_parser("next-id", help="print the next free ID, or the next substory ID under PARENT")
    p_next.add_argument("parent", nargs="?")
    p_set = sub.add_parser("set-status", help="set an item's status, cascade to its epic, rewrite the TOC")
    p_set.add_argument("id")
    p_set.add_argument("status", choices=SECTIONS)
    p_set.add_argument("--date", default=date.today().isoformat(), help="date for Done or Superseded (default: today)")
    sub.add_parser("toc", help="rewrite the README table of contents from the items")
    sub.add_parser("check", help="list every problem in the backlog; exit 1 if there is one")
    args = parser.parse_args(argv)

    try:
        b = args.dir or find_backlog(Path.cwd())
        if args.command == "next-id":
            print(next_id(b, args.parent))
        elif args.command == "set-status":
            for message in set_status(b, args.id, args.status, args.date):
                print(message)
        elif args.command == "toc":
            write_toc(b)
        else:
            problems = check(b)
            for problem in problems:
                print(problem)
            return 1 if problems else 0
    except BacklogError as e:
        print(f"backlog: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
