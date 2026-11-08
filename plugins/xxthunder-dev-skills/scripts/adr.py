# /// script
# requires-python = ">=3.11"
# dependencies = ["tomlkit>=0.13"]
# ///
"""Mechanical ADR operations: `migrate` turns ADR headers into sphinx-needs needs (XAS-044b, ADR-0018).

Where a root `ubproject.toml` switches sphinx-needs on, every ADR carries a
`decision` need below its heading: the heading's title as the need title,
`:id: ADR-NNNN` and the first word of its Status line as `:status:`. The
bold-field lines stay below the need, so the ADR index and the log checks keep
reading them. `migrate` also declares the need type `decision` and the link type
`constrains` in `ubproject.toml`, keeping its comments and order.

It knows only `design-record`'s template header and validates the whole log and
the declarations first: one ADR it cannot convert, or a declaration that
conflicts, refuses the run and leaves every file byte for byte. It refuses a
`ubproject.toml` without `needs.types`, because a `decision` entry would replace
sphinx-needs' default types. The need's `:status:` follows the Status line: a run
rewrites it where they differ and reports `updated:`. A second run changes nothing.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import tomlkit
from tomlkit.container import Container
from tomlkit.exceptions import TOMLKitError
from tomlkit.items import AoT, Comment, Table, Whitespace

from backlog import read_text, write_text

ADR_DIRS = ("docs/adr", "docs/architecture/adr")  # in the order design-record looks for them
ADR_FILE_RE = re.compile(r"^(\d{4})-.+\.md$")
HEADING_RE = re.compile(r"^# (ADR-(\d{4})): (.*\S)\s*$")
FIELD_RE = re.compile(r"^\*\*([^*]+)\*\*: ")
FIELDS = ("Status", "Date", "Related", "Supersedes", "Narrows")
LINK_RE = re.compile(r"\[[^\]]*\]\([^)]*\)")
STATUSES = ("Proposed", "Accepted", "Rejected", "Superseded")
NEED_OPEN = "```{decision}"
NEED_TYPE = {"directive": "decision", "title": "Decision", "prefix": "ADR-"}
LINK_NAME = "constrains"
LINK_TYPE = {"incoming": "is constrained by", "outgoing": "constrains"}
DEFAULT_ID_REGEX = "^[A-Z0-9_]{5,}"  # what sphinx-needs uses where the repository sets no id_regex


class AdrError(Exception):
    """An ADR log or a declaration this script refuses to change."""


def find_adr_dir(repo: Path) -> Path:
    for name in ADR_DIRS:
        if (repo / name).is_dir():
            return repo / name
    raise AdrError(f"no ADR directory in {repo}: neither {ADR_DIRS[0]}/ nor {ADR_DIRS[1]}/")


def convert(text: str, number: str) -> tuple[str, str | None, str]:
    """Return the ADR's ID, its new text (None when nothing changes) and the report word.

    The word is `converted` (a need was added), `updated` (the need's status was brought in step with
    the Status line) or `unchanged`.

    *number* is the file name's; the heading must carry the same.
    """
    lines = text.split("\n")
    heading = HEADING_RE.match(lines[0])
    if not heading:
        raise AdrError("the first line is not a heading `# ADR-NNNN: Title`")
    adr_id, heading_number, title = heading.groups()
    if heading_number != number:
        raise AdrError(f"the heading says {adr_id}, the file name {number}")
    start = 1
    while start < len(lines) and lines[start] == "":
        start += 1
    if start < len(lines) and lines[start].startswith(NEED_OPEN):
        return resync(lines, start, adr_id)
    end = start
    status = None
    while end < len(lines) and lines[end] != "":
        field = FIELD_RE.match(lines[end])
        if not field:
            raise AdrError(f"header line {end + 1} is not a `**Field**: value` line: {lines[end]!r}")
        if field.group(1) not in FIELDS:
            raise AdrError(f"header line {end + 1} has an unknown field {field.group(1)!r}")
        if field.group(1) == "Status":
            status = status_word(lines[end][field.end():])
        end += 1
    if status is None:
        raise AdrError("the header has no `**Status**` line")
    need = [f"{NEED_OPEN} {title}", f":id: {adr_id}", f":status: {status}", "```"]
    return adr_id, "\n".join([lines[0], "", *need, "", *lines[start:]]), "converted"


def resync(lines: list[str], start: int, adr_id: str) -> tuple[str, str | None, str]:
    """Set the `:status:` of the need that opens at *start* to the word of the ADR's Status line."""
    end = start
    while end < len(lines) and lines[end] != "```":
        end += 1
    if end == len(lines):
        raise AdrError("the need is not closed with a ``` line")
    option = next((i for i in range(start + 1, end) if lines[i].startswith(":status:")), None)
    if option is None:
        raise AdrError("the need has no `:status:` option")
    word = None
    for line in lines[end + 1:]:
        field = FIELD_RE.match(line)
        if field is None and word is None and line == "":
            continue
        if field is None:
            break
        if field.group(1) == "Status":
            word = status_word(line[field.end():])
    if word is None:
        raise AdrError("the header has no `**Status**` line")
    if lines[option] == f":status: {word}":
        return adr_id, None, "unchanged"
    lines = [*lines[:option], f":status: {word}", *lines[option + 1:]]
    return adr_id, "\n".join(lines), "updated"


def status_word(value: str) -> str:
    """The first word of a Status value, its links removed: `Superseded by [ADR-0003](...)` gives `Superseded`."""
    word = re.match(r"[A-Za-z]*", LINK_RE.sub("", value).strip()).group(0)
    if word not in STATUSES:
        raise AdrError(f"the status {value!r} does not start with one of {', '.join(STATUSES)}")
    return word


def container_of(item: Container | Table) -> Container:
    return item if isinstance(item, Container) else item.value


def last_table(item: Container | Table | AoT) -> Container | Table:
    """The table whose body ends *item* in the file: its last entry or child table, recursively."""
    owner = item[-1] if isinstance(item, AoT) else item
    body = container_of(owner).body
    if body and isinstance(body[-1][1], (Table, AoT)):
        return last_table(body[-1][1])
    return owner


def append_table(parent: Container | Table | AoT, key: str | None, child: Table | AoT) -> None:
    """Append *child* to *parent* (under *key* unless *parent* is an array) and move the comments and blank
    lines that ended *parent* below it: in the file they introduce what follows, not what came before."""
    owner = container_of(last_table(parent)) if len(parent) else None
    moved = []
    while owner is not None and owner.body and owner.body[-1][0] is None \
            and isinstance(owner.body[-1][1], (Whitespace, Comment)):
        moved.insert(0, owner.body.pop()[1])
    if moved:
        owner.append(None, tomlkit.nl())
    if isinstance(parent, AoT):
        parent.append(child)
    else:
        parent.append(key, child)
    target = container_of(last_table(child))
    for trivia in moved:
        target.append(None, trivia)


def new_table(values: dict[str, str], super_table: bool = False) -> Table:
    table = tomlkit.table(is_super_table=super_table)
    for key, value in values.items():
        table[key] = value
    return table


def declare(text: str, ids: list[str]) -> tuple[str | None, list[str]]:
    """Return ubproject.toml with the need type and link type added, or None if both are there; and what was added."""
    try:
        doc = tomlkit.parse(text)
    except TOMLKitError as e:
        raise AdrError(f"cannot be read: {e}") from e
    needs = doc.get("needs")
    if needs is not None and not isinstance(needs, Table):
        raise AdrError("`needs` is not a table")
    regex = needs.get("id_regex") if needs is not None else None
    if regex is not None and not isinstance(regex, str):
        raise AdrError("`needs.id_regex` is not a string")
    try:
        rejected = [i for i in ids if not re.match(DEFAULT_ID_REGEX if regex is None else regex, i)]
    except re.error as e:
        raise AdrError(f"id_regex {str(regex)!r} is not a regular expression: {e}") from e
    if rejected:
        which = f"id_regex {str(regex)!r}" if regex is not None else \
            f"no id_regex is set, and sphinx-needs' default {DEFAULT_ID_REGEX!r}"
        raise AdrError(f"{which} rejects {', '.join(rejected)}; set an id_regex in [needs] that accepts "
                       "ADR-NNNN, migrate never writes id_regex")
    types = needs.get("types") if needs is not None else None
    if types is None:
        raise AdrError("`needs.types` is not declared: a `decision` entry would replace sphinx-needs' default "
                       "types (req, spec, impl, test, need); declare the types the repository uses in "
                       "[[needs.types]], migrate never writes them")
    if not isinstance(types, AoT):
        raise AdrError("`needs.types` is not an array of tables")
    links = needs.get("links") if needs is not None else None
    if links is not None and not isinstance(links, Table):
        raise AdrError("`needs.links` is not a table")
    have_type = False
    for t in types:
        if t.get("directive") == NEED_TYPE["directive"]:
            if any(t.get(key) != value for key, value in NEED_TYPE.items()):
                raise AdrError(f"need type {NEED_TYPE['directive']!r} exists with other settings; "
                               f"migrate needs {NEED_TYPE}")
            have_type = True
    link = links.get(LINK_NAME) if links is not None else None
    if link is not None and not isinstance(link, Table):
        raise AdrError(f"`needs.links.{LINK_NAME}` is not a table")
    if link is not None and any(link.get(key) != value for key, value in LINK_TYPE.items()):
        raise AdrError(f"link type {LINK_NAME!r} exists with other settings; migrate needs {LINK_TYPE}")
    if have_type and link is not None:
        return None, []

    declared = []
    if not have_type:
        append_table(types, None, new_table(NEED_TYPE))
        declared.append(f"declared: need type {NEED_TYPE['directive']}")
    if link is None:
        if links is None:
            links = new_table({}, super_table=True)
            links.append(LINK_NAME, new_table(LINK_TYPE))
            append_table(needs, "links", links)
        else:
            append_table(links, LINK_NAME, new_table(LINK_TYPE))
        declared.append(f"declared: link type {LINK_NAME}")
    return tomlkit.dumps(doc), declared


def migrate(repo: Path) -> list[str]:
    """Convert every ADR of *repo* and declare the types; return one line per change. Writes only if all is valid."""
    toml_path = repo / "ubproject.toml"
    if not toml_path.is_file():
        raise AdrError(f"no ubproject.toml in {repo}: the switch is off, ADR headers stay bold-field lines")
    adr_dir = find_adr_dir(repo)
    problems: list[str] = []
    writes: list[tuple[Path, str, bool]] = []
    report: list[str] = []
    seen: dict[str, str] = {}
    for path in sorted(p for p in adr_dir.iterdir() if p.is_file() and ADR_FILE_RE.match(p.name)):
        rel = path.relative_to(repo).as_posix()
        text, crlf = read_text(path)
        try:
            adr_id, new, word = convert(text, ADR_FILE_RE.match(path.name).group(1))
        except AdrError as e:
            problems.append(f"{rel}: {e}")
            continue
        if adr_id in seen:
            problems.append(f"{rel}: {adr_id} is also the ID of {seen[adr_id]}")
            continue
        seen[adr_id] = rel
        if new is not None:
            writes.append((path, new, crlf))
        report.append(f"{word}: {rel}")
    toml_text, toml_crlf = read_text(toml_path)
    try:
        new_toml, declared = declare(toml_text, list(seen))
    except AdrError as e:
        problems.append(f"ubproject.toml: {e}")
    if problems:
        raise AdrError("refused, nothing written:\n" + "\n".join(problems))
    for path, new, crlf in writes:
        write_text(path, new, crlf)
    if new_toml is not None:
        write_text(toml_path, new_toml, toml_crlf)
    return report + declared


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p_migrate = sub.add_parser("migrate", help="turn every ADR header into a decision need and declare the need "
                               "and link types in ubproject.toml; refuse and write nothing if any ADR does not fit")
    p_migrate.add_argument("--repo", type=Path, default=Path("."), help="repository root (default: .)")
    args = parser.parse_args(argv)
    try:
        for line in migrate(args.repo):
            print(line)
    except (AdrError, OSError, UnicodeDecodeError) as e:
        print(f"adr: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
