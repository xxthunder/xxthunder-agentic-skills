# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""List, reply to, add and resolve CriticMarkup marks in one file.

Mirrors the parser of the criticmark-review VS Code extension (src/markup/parse.ts),
so files written here round trip in the editor. A `.review` file is a sidecar:
code detection is off, and only `list` and `reply` apply to it.

    criticmark.py list FILE [--kind K] [--author A] [--open] [--grep TEXT]
    criticmark.py reply FILE ID TEXT
    criticmark.py comment FILE (--quote TEXT | --line N) TEXT
    criticmark.py accept FILE ID [ID ...]
    criticmark.py reject FILE ID [ID ...]
    criticmark.py clean FILE
"""

from __future__ import annotations

import argparse
import datetime
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ATTR = r'[A-Za-z][\w-]*="[^"{}\n]*"'
META = rf"((?:{ATTR}(?:[ \t]+{ATTR})*[ \t]*)?)"
BODY = r"([\s\S]*?)"

PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("comment", re.compile(rf"\{{{META}>>{BODY}<<\}}")),
    ("addition", re.compile(rf"\{{{META}\+\+{BODY}\+\+\}}")),
    ("deletion", re.compile(rf"\{{{META}--{BODY}--\}}")),
    ("substitution", re.compile(rf"\{{{META}~~{BODY}~>{BODY}~~\}}")),
    ("highlight", re.compile(rf"\{{{META}=={BODY}==\}}")),
    ("aitext", re.compile(rf"\{{{META}=\+{BODY}\+=\}}")),
]
SUGGESTIONS = ("addition", "deletion", "substitution")

ATTR_PAIR = re.compile(r'([A-Za-z][\w-]*)="([^"{}\n]*)"')
LEGACY_AUTHOR = re.compile(r"^\s*([A-Za-z][\w.-]{0,29})\s*:\s*")
FENCE = re.compile(r"(^|\n)( {0,3})(```+|~~~+)[^\n]*\n[\s\S]*?(?:\n {0,3}\3[ \t]*(?=\r?\n|$)|$)")
INLINE_CODE = re.compile(r"`[^`\n]+`")


@dataclass
class Node:
    kind: str
    start: int
    end: int
    raw: str
    text: str
    old_text: str | None = None
    author: str | None = None
    date: str | None = None
    status: str | None = None


@dataclass
class Thread:
    root: int
    replies: list[int] = field(default_factory=list)
    anchor: int | None = None
    start: int = 0
    end: int = 0

    @property
    def last(self) -> int:
        return self.replies[-1] if self.replies else self.root

    @property
    def members(self) -> list[int]:
        return [self.root, *self.replies]


@dataclass
class Parsed:
    text: str
    nodes: list[Node]
    threads: list[Thread]


def _read_attrs(meta: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for name, value in ATTR_PAIR.findall(meta):
        name, value = name.lower(), value.strip()
        if value and name not in attrs:
            attrs[name] = value
    return attrs


def _indented_code(text: str, fences: list[tuple[int, int]]) -> list[tuple[int, int]]:
    def in_fence(pos: int) -> bool:
        return any(a <= pos < b for a, b in fences)

    ranges: list[tuple[int, int]] = []
    pos, after_blank, start = 0, True, -1
    while pos <= len(text):
        newline = text.find("\n", pos)
        end = len(text) if newline == -1 else newline
        line = text[pos:end].removesuffix("\r")  # a CRLF line ends before its \r
        if in_fence(pos):
            if start >= 0:
                ranges.append((start, pos))
                start = -1
            after_blank = False
        else:
            blank = re.fullmatch(r"[ \t]*", line) is not None
            indented = not blank and re.match(r"( {4,}|\t)", line) is not None
            if start < 0:
                if indented and after_blank:
                    start = pos
            elif not indented and not blank:
                ranges.append((start, pos))
                start = -1
            after_blank = blank
        if newline == -1:
            break
        pos = newline + 1
    if start >= 0:
        ranges.append((start, len(text)))
    return ranges


def code_ranges(text: str) -> list[tuple[int, int]]:
    ranges = [(m.start() + len(m.group(1)), m.end()) for m in FENCE.finditer(text)]
    ranges += _indented_code(text, ranges)
    inline = [(m.start(), m.end()) for m in INLINE_CODE.finditer(text) if not any(a <= m.start() < b for a, b in ranges)]
    return sorted(ranges + inline)


def _to_node(kind: str, m: re.Match[str]) -> Node:
    attrs = _read_attrs(m.group(1))
    node = Node(kind, m.start(), m.end(), m.group(0), m.group(2), author=attrs.get("author"), date=attrs.get("date"), status=attrs.get("status"))
    if kind == "substitution":
        node.old_text, node.text = m.group(2), m.group(3)
    if kind == "comment":
        legacy = LEGACY_AUTHOR.match(m.group(2))
        if legacy:
            node.author = node.author or legacy.group(1)
            node.text = m.group(2)[legacy.end() :]
    return node


def _scan(text: str) -> list[Node]:
    # One element at a time from left to right, so quoted code that looks like markup cannot run on into a later entry.
    nodes: list[Node] = []
    pos = 0
    while True:
        first: tuple[str, re.Match[str]] | None = None
        for kind, pattern in PATTERNS:
            m = pattern.search(text, pos)
            if m and (first is None or m.start() < first[1].start()):
                first = (kind, m)
        if first is None:
            return nodes
        nodes.append(_to_node(*first))
        pos = first[1].end()


def parse(text: str, sidecar: bool = False) -> Parsed:
    code = [] if sidecar else code_ranges(text)

    def in_code(pos: int) -> bool:
        return any(a <= pos < b for a, b in code)

    found = _scan(text) if sidecar else [_to_node(kind, m) for kind, pattern in PATTERNS for m in pattern.finditer(text)]
    found.sort(key=lambda n: n.start)
    nodes: list[Node] = []
    end = -1
    for node in found:
        if node.start < end or in_code(node.start) or in_code(node.end - 1):
            continue
        nodes.append(node)
        end = node.end

    threads: list[Thread] = []
    current: Thread | None = None
    last = -1
    for i, node in enumerate(nodes):
        if node.kind != "comment":
            continue
        if current and last >= 0 and re.fullmatch(r"[ \t]*", text[nodes[last].end : node.start]):
            current.replies.append(i)
            current.end = node.end
            last = i
            continue
        prev = nodes[i - 1] if i > 0 else None
        anchored = prev is not None and prev.end == node.start and prev.kind not in ("comment", "aitext")
        current = Thread(root=i, anchor=i - 1 if anchored else None, start=prev.start if anchored and prev else node.start, end=node.end)
        threads.append(current)
        last = i
    return Parsed(text, nodes, threads)


def line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def comment_markup(body: str, author: str, date: str) -> str:
    if "<<}" in body:
        raise ValueError("A comment cannot contain the closing marker <<}.")
    name = re.sub(r'[\x00-\x1f\x7f\u2028\u2029"{}]', "", author).strip()
    meta = f'author="{name}" date="{date}"' if name else f'date="{date}"'
    return f"{{{meta}>>{body}<<}}"


def thread_of(parsed: Parsed, index: int) -> Thread:
    for thread in parsed.threads:
        if index in thread.members or index == thread.anchor:
            return thread
    raise ValueError(f"#{index + 1} is not part of a comment thread.")


def reply(parsed: Parsed, index: int, body: str, author: str, date: str) -> str:
    last = parsed.nodes[thread_of(parsed, index).last]
    return parsed.text[: last.end] + comment_markup(body, author, date) + parsed.text[last.end :]


def _check_new_mark(parsed: Parsed, start: int, end: int) -> None:
    def hits(a: int, b: int) -> bool:
        return a < start < b if start == end else a < end and start < b

    if any(hits(n.start, n.end) for n in parsed.nodes):
        raise ValueError("The place overlaps an existing mark.")
    if any(hits(a, b) for a, b in code_ranges(parsed.text)):
        raise ValueError("The place is inside code.")
    if "==}" in parsed.text[start:end]:
        raise ValueError("A quote must stay on one line and cannot contain ==}.")


def comment_on_quote(parsed: Parsed, quote: str, body: str, author: str, date: str) -> str:
    if "\n" in quote or "\r" in quote:
        raise ValueError("A quote must stay on one line and cannot contain ==}.")
    hits = [m.start() for m in re.finditer(re.escape(quote), parsed.text)]
    if len(hits) != 1:
        raise ValueError(f"The quote must occur exactly once; found {len(hits)}.")
    start, end = hits[0], hits[0] + len(quote)
    _check_new_mark(parsed, start, end)
    return parsed.text[:start] + f"{{=={quote}==}}" + comment_markup(body, author, date) + parsed.text[end:]


def comment_on_line(parsed: Parsed, line: int, body: str, author: str, date: str) -> str:
    lines = parsed.text.split("\n")
    if not 1 <= line <= len(lines):
        raise ValueError(f"Line {line} does not exist.")
    pos = sum(len(x) + 1 for x in lines[: line - 1]) + len(lines[line - 1].removesuffix("\r"))  # before a CRLF's \r
    _check_new_mark(parsed, pos, pos)
    return parsed.text[:pos] + comment_markup(body, author, date) + parsed.text[pos:]


def resolve(parsed: Parsed, indexes: list[int], accept: bool) -> str:
    text = parsed.text
    for index in sorted(set(indexes), key=lambda i: parsed.nodes[i].start, reverse=True):
        node = parsed.nodes[index]
        if node.kind not in SUGGESTIONS:
            raise ValueError(f"#{index + 1} is a {node.kind}, not a suggestion.")
        kept = {"addition": node.text, "deletion": "", "substitution": node.text} if accept else {"addition": "", "deletion": node.text, "substitution": node.old_text or ""}
        # The decision closes the discussion, so a thread anchored to the suggestion goes with it.
        end = next((t.end for t in parsed.threads if t.anchor == index), node.end)
        text = text[: node.start] + kept[node.kind] + text[end:]
    return text


def mark_resolved(parsed: Parsed, indexes: list[int]) -> str:
    text = parsed.text
    roots = {thread_of(parsed, i).root for i in indexes}
    for index in sorted(roots, key=lambda i: parsed.nodes[i].start, reverse=True):
        node = parsed.nodes[index]

        def with_status(m: re.Match[str]) -> str:
            meta = re.sub(r'[ \t]*status="[^"]*"', "", m.group(1).strip())
            return "{" + f'{meta} status="resolved"'.strip() + m.group(0)[m.end(1) - m.start() :]

        text = text[: node.start] + PATTERNS[0][1].sub(with_status, node.raw, count=1) + text[node.end :]
    return text


def clean(parsed: Parsed) -> str:
    open_suggestions = [i for i, n in enumerate(parsed.nodes) if n.kind in SUGGESTIONS]
    if open_suggestions:
        raise ValueError("Resolve these suggestions first: " + ", ".join(f"#{i + 1}" for i in open_suggestions))
    text = parsed.text
    for node in reversed(parsed.nodes):
        text = text[: node.start] + ("" if node.kind == "comment" else node.text) + text[node.end :]
    return text


def _short(text: str) -> str:
    one = " ".join(text.split())
    return one if len(one) <= 100 else one[:97] + "..."


def describe(parsed: Parsed, index: int) -> str:
    node = parsed.nodes[index]
    parts = [f"#{index + 1}", f"L{line_of(parsed.text, node.start)}", node.kind]
    if node.kind == "comment":
        thread = thread_of(parsed, index)
        parts.append(f"thread=#{thread.root + 1}")
    parts += [x for x in (node.author, node.date, node.status) if x]
    body = f"{node.old_text} -> {node.text}" if node.kind == "substitution" else node.text
    return " ".join(parts) + ": " + _short(body)


def _selected(parsed: Parsed, kind: str | None, author: str | None, only_open: bool, grep: str | None) -> list[int]:
    chosen = []
    for i, node in enumerate(parsed.nodes):
        if kind and node.kind != kind:
            continue
        if author and (node.author or "").lower() != author.lower():
            continue
        if grep and grep.lower() not in (node.text + (node.old_text or "")).lower():
            continue
        threads = [t for t in parsed.threads if i in t.members or i == t.anchor]  # a bare highlight has none
        if only_open and threads and any(parsed.nodes[m].status == "resolved" for m in threads[0].members):
            continue
        chosen.append(i)
    return chosen


def _index(parsed: Parsed, ident: str) -> int:
    number = int(ident.lstrip("#"))
    if not 1 <= number <= len(parsed.nodes):
        raise ValueError(f"No mark #{number}; the file has {len(parsed.nodes)}.")
    return number - 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="List, reply to, add and resolve CriticMarkup marks in one file.")
    sub = ap.add_subparsers(dest="command", required=True)

    def command(name: str, help: str) -> argparse.ArgumentParser:
        p = sub.add_parser(name, help=help)
        p.add_argument("file", type=Path)
        return p

    p_list = command("list", "print every mark with its number, line, kind, author and text")
    p_list.add_argument("--kind", choices=[k for k, _ in PATTERNS])
    p_list.add_argument("--author")
    p_list.add_argument("--open", action="store_true", help="skip comments and highlights of resolved threads")
    p_list.add_argument("--grep", help="only marks whose text contains this, ignoring case")
    p_reply = command("reply", "append a reply to the thread that holds mark ID")
    p_reply.add_argument("id")
    p_reply.add_argument("text")
    p_comment = command("comment", "add a new comment on a quote or at the end of a line")
    where = p_comment.add_mutually_exclusive_group(required=True)
    where.add_argument("--quote", help="text that occurs exactly once; it gets highlighted")
    where.add_argument("--line", type=int)
    p_comment.add_argument("text")
    for name, verb in (("accept", "keep"), ("reject", "drop")):
        command(name, f"{verb} the suggested change of each ID, and remove its thread").add_argument("ids", nargs="+")
    command("resolve", "mark the thread that holds each ID as resolved").add_argument("ids", nargs="+")
    command("clean", "after approval: remove all comments and highlights; fails while a suggestion is open")
    for p in (p_reply, p_comment):
        p.add_argument("--author", default="Claude")
        p.add_argument("--date", default=datetime.date.today().isoformat())
    args = ap.parse_args(argv)

    path: Path = args.file
    sidecar = path.suffix == ".review"
    try:
        with path.open(encoding="utf-8", newline="") as f:  # newline="": keep CRLF as it is
            parsed = parse(f.read(), sidecar)
        if args.command == "list":
            for i in _selected(parsed, args.kind, args.author, args.open, args.grep):
                print(describe(parsed, i))
            return 0
        if sidecar and args.command != "reply":
            raise ValueError(f"'{args.command}' does not apply to a sidecar; reply in it, and delete it after approval.")
        if args.command == "reply":
            new = reply(parsed, _index(parsed, args.id), args.text, args.author, args.date)
        elif args.command == "comment":
            if args.quote is not None:
                new = comment_on_quote(parsed, args.quote, args.text, args.author, args.date)
            else:
                new = comment_on_line(parsed, args.line, args.text, args.author, args.date)
        elif args.command == "resolve":
            new = mark_resolved(parsed, [_index(parsed, i) for i in args.ids])
        elif args.command in ("accept", "reject"):
            new = resolve(parsed, [_index(parsed, i) for i in args.ids], args.command == "accept")
        else:
            new = clean(parsed)
            left = parse(new).nodes
            if left:
                raise ValueError(f"{len(left)} marks are left after cleaning.")
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write(new)
    return 0


if __name__ == "__main__":
    sys.exit(main())
