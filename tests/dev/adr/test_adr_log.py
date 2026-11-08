"""Structural invariants of the ADR log at `docs/adr/`.

The index at `docs/adr/README.md` is *derived* from the ADR files: where the two
disagree, the files win. A derived artifact with nothing checking it is one that
drifts silently, which is what this module exists to prevent.

Checks are pure functions over a directory, so each one can be pointed at this
repository's real log (expected clean) and at a deliberately broken log built in
`tmp_path` (expected to produce a finding). Without the second half, a check
that never fires would look identical to a check that passes.

Structure only — never content. Whether an ADR's reasoning is any good is a
review question and stays one.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
ADR_DIR = REPO_ROOT / "docs" / "adr"

FILENAME_RE = re.compile(r"^(\d{4})-[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
# The heading separator is a colon (`# ADR-NNNN: Title`) or, in older ADRs, an
# em-dash; the em-dash is written as an escape so no new line carries one.
HEADING_RE = re.compile(r"^#\s+ADR-(\d{4})(?::|\s+\N{EM DASH})\s+(.+?)\s*$")
FIELD_RE = re.compile(r"^\*\*(Status|Date|Related|Supersedes|Narrows)\*\*:\s*(.+?)\s*$")
INDEX_ROW_RE = re.compile(
    r"^\|\s*\[(\d{4})\]\(([^)]+)\)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*$"
)
MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
SUPERSEDED_RE = re.compile(r"^Superseded by ADR-(\d{4})$")
SUPERSEDES_RE = re.compile(r"ADR-(\d{4})")
NARROWED_RE = re.compile(r"^Accepted, narrowed by ADR-(\d{4})$")
NARROWS_RE = SUPERSEDES_RE

REQUIRED_SECTIONS = (
    "## Context",
    "## Decision",
    "## Alternatives considered",
    "## Consequences",
)
SIMPLE_STATUSES = ("Proposed", "Accepted", "Rejected")

pytestmark = pytest.mark.skipif(
    not ADR_DIR.is_dir(),
    reason="no docs/adr/ in this repository; nothing to check",
)


def strip_links(text: str) -> str:
    """Reduce `[label](target)` to `label`, leaving plain text untouched."""
    return MD_LINK_RE.sub(r"\1", text)


def read_lines(path: Path) -> list[str]:
    """Read as UTF-8 and split on any line ending, so CRLF checkouts behave."""
    return path.read_text(encoding="utf-8").splitlines()


def adr_files(adr_dir: Path) -> list[Path]:
    return sorted(p for p in adr_dir.glob("*.md") if p.name != "README.md")


def parse_adr(path: Path) -> dict:
    lines = read_lines(path)
    heading = next((HEADING_RE.match(ln) for ln in lines if HEADING_RE.match(ln)), None)
    fields: dict[str, str] = {}
    for ln in lines:
        m = FIELD_RE.match(ln)
        if m and m.group(1) not in fields:
            fields[m.group(1)] = m.group(2)
    return {
        "path": path,
        "name": path.name,
        "number": heading.group(1) if heading else None,
        "title": heading.group(2) if heading else None,
        "status": strip_links(fields["Status"]) if "Status" in fields else None,
        "date": fields.get("Date"),
        "supersedes": fields.get("Supersedes"),
        "narrows": fields.get("Narrows"),
        "sections": [ln for ln in lines if ln.startswith("## ")],
        "links": [m.group(2) for ln in lines for m in MD_LINK_RE.finditer(ln)],
    }


def check_filenames(adr_dir: Path) -> list[str]:
    return [
        f"{p.name}: filename is not NNNN-kebab-title.md"
        for p in adr_files(adr_dir)
        if not FILENAME_RE.match(p.name)
    ]


def check_unique_numbers(adr_dir: Path) -> list[str]:
    seen: dict[str, str] = {}
    problems = []
    for p in adr_files(adr_dir):
        m = FILENAME_RE.match(p.name)
        if not m:
            continue
        num = m.group(1)
        if num in seen:
            problems.append(f"number {num} reused by {seen[num]} and {p.name}")
        seen[num] = p.name
    return problems


def check_headers(adr_dir: Path) -> list[str]:
    problems = []
    for p in adr_files(adr_dir):
        adr = parse_adr(p)
        if adr["number"] is None:
            problems.append(f"{p.name}: no '# ADR-NNNN: Title' heading")
        elif FILENAME_RE.match(p.name) and adr["number"] != p.name[:4]:
            problems.append(
                f"{p.name}: heading says ADR-{adr['number']}, filename says {p.name[:4]}"
            )
        if adr["status"] is None:
            problems.append(f"{p.name}: missing **Status**: line")
        if adr["date"] is None:
            problems.append(f"{p.name}: missing **Date**: line")
        else:
            try:
                date.fromisoformat(adr["date"])
            except ValueError:
                problems.append(f"{p.name}: date {adr['date']!r} is not YYYY-MM-DD")
    return problems


def check_statuses(adr_dir: Path) -> list[str]:
    problems = []
    for p in adr_files(adr_dir):
        status = parse_adr(p)["status"]
        if status is None:
            continue
        if (
            status not in SIMPLE_STATUSES
            and not SUPERSEDED_RE.match(status)
            and not NARROWED_RE.match(status)
        ):
            problems.append(f"{p.name}: status {status!r} is not a permitted value")
    return problems


def check_sections(adr_dir: Path) -> list[str]:
    problems = []
    for p in adr_files(adr_dir):
        present = parse_adr(p)["sections"]
        for required in REQUIRED_SECTIONS:
            if required not in present:
                problems.append(f"{p.name}: missing section {required!r}")
    return problems


def parse_index(adr_dir: Path) -> list[dict]:
    index = adr_dir / "README.md"
    if not index.is_file():
        return []
    rows = []
    for ln in read_lines(index):
        m = INDEX_ROW_RE.match(ln)
        if m:
            rows.append(
                {
                    "number": m.group(1),
                    "target": m.group(2),
                    "title": m.group(3),
                    "status": strip_links(m.group(4)),
                    "date": m.group(5),
                }
            )
    return rows


def check_index_agreement(adr_dir: Path) -> list[str]:
    index = adr_dir / "README.md"
    if not index.is_file():
        return ["docs/adr/README.md is missing"]
    rows = parse_index(adr_dir)
    by_number: dict[str, list[dict]] = {}
    for row in rows:
        by_number.setdefault(row["number"], []).append(row)

    problems = []
    for num, group in by_number.items():
        if len(group) > 1:
            problems.append(f"index lists ADR-{num} {len(group)} times")

    for p in adr_files(adr_dir):
        m = FILENAME_RE.match(p.name)
        if not m:
            continue
        num = m.group(1)
        if num not in by_number:
            problems.append(f"{p.name}: no row in the index")
            continue
        row = by_number[num][0]
        if not (adr_dir / row["target"]).is_file():
            problems.append(f"index row {num} points at missing file {row['target']}")
        adr = parse_adr(p)
        for field in ("title", "status", "date"):
            if adr[field] is not None and row[field] != adr[field]:
                problems.append(
                    f"{p.name}: index {field} {row[field]!r} != file {adr[field]!r}"
                )
    return problems


def check_supersede_symmetry(adr_dir: Path) -> list[str]:
    adrs = {}
    for p in adr_files(adr_dir):
        adr = parse_adr(p)
        if adr["number"]:
            adrs[adr["number"]] = adr

    problems = []
    for num, adr in adrs.items():
        if adr["supersedes"]:
            m = SUPERSEDES_RE.search(strip_links(adr["supersedes"]))
            if not m:
                problems.append(f"{adr['name']}: **Supersedes** names no ADR-NNNN")
                continue
            target = m.group(1)
            other = adrs.get(target)
            if other is None:
                problems.append(f"{adr['name']}: supersedes missing ADR-{target}")
            elif other["status"] != f"Superseded by ADR-{num}":
                problems.append(
                    f"ADR-{target}: status {other['status']!r}, "
                    f"expected 'Superseded by ADR-{num}'"
                )
        status_match = SUPERSEDED_RE.match(adr["status"] or "")
        if status_match:
            by = status_match.group(1)
            other = adrs.get(by)
            if other is None:
                problems.append(f"{adr['name']}: superseded by missing ADR-{by}")
            elif not (
                other["supersedes"]
                and SUPERSEDES_RE.search(strip_links(other["supersedes"]))
                and SUPERSEDES_RE.search(strip_links(other["supersedes"])).group(1) == num
            ):
                problems.append(
                    f"ADR-{by}: claims no **Supersedes** for ADR-{num}"
                )
    return problems


def check_narrowing(adr_dir: Path) -> list[str]:
    """`**Narrows**` and `Accepted, narrowed by` must answer each other."""
    adrs = {}
    for p in adr_files(adr_dir):
        adr = parse_adr(p)
        if adr["number"]:
            adrs[adr["number"]] = adr

    problems = []
    for num, adr in adrs.items():
        if adr["narrows"]:
            m = NARROWS_RE.search(strip_links(adr["narrows"]))
            if not m:
                problems.append(f"{adr['name']}: **Narrows** names no ADR-NNNN")
                continue
            target = m.group(1)
            other = adrs.get(target)
            if other is None:
                problems.append(f"{adr['name']}: narrows missing ADR-{target}")
            elif other["status"] != f"Accepted, narrowed by ADR-{num}":
                problems.append(
                    f"ADR-{target}: status {other['status']!r}, "
                    f"expected 'Accepted, narrowed by ADR-{num}'"
                )
        status_match = NARROWED_RE.match(adr["status"] or "")
        if status_match:
            by = status_match.group(1)
            other = adrs.get(by)
            if other is None:
                problems.append(f"{adr['name']}: narrowed by missing ADR-{by}")
            else:
                named = NARROWS_RE.search(strip_links(other["narrows"] or ""))
                if not named or named.group(1) != num:
                    problems.append(f"ADR-{by}: claims no **Narrows** for ADR-{num}")
    return problems


def check_links_resolve(adr_dir: Path) -> list[str]:
    problems = []
    targets = adr_files(adr_dir) + [adr_dir / "README.md"]
    for p in targets:
        if not p.is_file():
            continue
        for raw in parse_adr(p)["links"] if p.name != "README.md" else [
            m.group(2) for ln in read_lines(p) for m in MD_LINK_RE.finditer(ln)
        ]:
            link = raw.split("#", 1)[0].strip()
            if not link or "://" in link or link.startswith("mailto:"):
                continue
            if not (p.parent / link).is_file():
                problems.append(f"{p.name}: link {link!r} resolves to nothing")
    return problems


ALL_CHECKS = (
    check_filenames,
    check_unique_numbers,
    check_headers,
    check_statuses,
    check_sections,
    check_index_agreement,
    check_supersede_symmetry,
    check_narrowing,
    check_links_resolve,
)


# --------------------------------------------------------------------------
# The real log
# --------------------------------------------------------------------------


@pytest.mark.parametrize("check", ALL_CHECKS, ids=lambda c: c.__name__)
def test_real_log_satisfies(check):
    assert check(ADR_DIR) == []


def test_real_log_is_not_empty():
    """Guard against every check above passing vacuously on an empty directory."""
    assert adr_files(ADR_DIR), "no ADRs found; the checks above would pass vacuously"


# --------------------------------------------------------------------------
# Negative cases — each check must actually bite
# --------------------------------------------------------------------------

GOOD_BODY = """# ADR-{num} — {title}

**Status**: {status}
**Date**: {date}
**Related**: [XAS-001](../backlog/xas-001.md)
{extra}
## Context

Why.

## Decision

What.

## Alternatives considered

Which.

## Consequences

So what.
"""

GOOD_INDEX = """# Architecture Decision Records

## Index

| ADR | Title | Status | Date |
|-----|-------|--------|------|
{rows}
"""


def build_log(
    tmp_path: Path,
    adrs=((("0001"), "First decision", "Accepted", "2026-01-01", ""),),
    index_rows=None,
    filename=None,
) -> Path:
    """Write a minimal, valid-by-default ADR log; callers break one thing."""
    adr_dir = tmp_path / "adr"
    adr_dir.mkdir(exist_ok=True)
    (adr_dir.parent / "backlog").mkdir(exist_ok=True)
    (adr_dir.parent / "backlog" / "xas-001.md").write_text("stub", encoding="utf-8")

    rows = []
    for num, title, status, when, extra in adrs:
        name = filename or f"{num}-{title.lower().replace(' ', '-')}.md"
        (adr_dir / name).write_text(
            GOOD_BODY.format(num=num, title=title, status=status, date=when, extra=extra),
            encoding="utf-8",
        )
        rows.append(f"| [{num}]({name}) | {title} | {status} | {when} |")
    (adr_dir / "README.md").write_text(
        GOOD_INDEX.format(rows="\n".join(index_rows if index_rows is not None else rows)),
        encoding="utf-8",
    )
    return adr_dir


def test_baseline_fixture_is_clean(tmp_path):
    """Every negative case below breaks exactly one thing off this baseline."""
    adr_dir = build_log(tmp_path)
    for check in ALL_CHECKS:
        assert check(adr_dir) == [], check.__name__


def test_bad_filename_is_caught(tmp_path):
    adr_dir = build_log(tmp_path, filename="1-first.md")
    assert check_filenames(adr_dir)


def test_duplicate_number_is_caught(tmp_path):
    adr_dir = build_log(tmp_path)
    (adr_dir / "0001-a-copy.md").write_text(
        GOOD_BODY.format(num="0001", title="A copy", status="Accepted", date="2026-01-01", extra=""),
        encoding="utf-8",
    )
    assert any("reused" in p for p in check_unique_numbers(adr_dir))


def test_missing_date_is_caught(tmp_path):
    adr_dir = build_log(tmp_path)
    p = next(adr_dir.glob("0001-*.md"))
    p.write_text(
        p.read_text(encoding="utf-8").replace("**Date**: 2026-01-01\n", ""),
        encoding="utf-8",
    )
    assert any("missing **Date**" in x for x in check_headers(adr_dir))


def test_malformed_date_is_caught(tmp_path):
    adr_dir = build_log(tmp_path, adrs=(("0001", "First decision", "Accepted", "01-01-2026", ""),))
    assert any("not YYYY-MM-DD" in x for x in check_headers(adr_dir))


def test_invalid_status_is_caught(tmp_path):
    adr_dir = build_log(tmp_path, adrs=(("0001", "First decision", "Maybe", "2026-01-01", ""),))
    assert any("not a permitted value" in x for x in check_statuses(adr_dir))


def test_missing_section_is_caught(tmp_path):
    adr_dir = build_log(tmp_path)
    p = next(adr_dir.glob("0001-*.md"))
    p.write_text(
        p.read_text(encoding="utf-8").replace("## Alternatives considered", "## Options"),
        encoding="utf-8",
    )
    assert any("Alternatives considered" in x for x in check_sections(adr_dir))


def test_index_missing_row_is_caught(tmp_path):
    adr_dir = build_log(tmp_path, index_rows=[])
    assert any("no row in the index" in x for x in check_index_agreement(adr_dir))


def test_index_status_drift_is_caught(tmp_path):
    """The rule this whole module exists for: index drifting from the files."""
    adr_dir = build_log(
        tmp_path,
        index_rows=["| [0001](0001-first-decision.md) | First decision | Proposed | 2026-01-01 |"],
    )
    assert any("index status" in x for x in check_index_agreement(adr_dir))


def test_index_row_pointing_nowhere_is_caught(tmp_path):
    adr_dir = build_log(
        tmp_path,
        index_rows=["| [0001](0001-renamed.md) | First decision | Accepted | 2026-01-01 |"],
    )
    assert any("missing file" in x for x in check_index_agreement(adr_dir))


def test_dangling_superseded_by_is_caught(tmp_path):
    adr_dir = build_log(
        tmp_path, adrs=(("0001", "First decision", "Superseded by ADR-0009", "2026-01-01", ""),)
    )
    assert any("missing ADR-0009" in x for x in check_supersede_symmetry(adr_dir))


def test_one_sided_supersedes_is_caught(tmp_path):
    """0002 claims to supersede 0001, but 0001 still reads Accepted."""
    adr_dir = build_log(
        tmp_path,
        adrs=(
            ("0001", "First decision", "Accepted", "2026-01-01", ""),
            ("0002", "Second decision", "Accepted", "2026-01-02", "**Supersedes**: [ADR-0001](0001-first-decision.md)\n"),
        ),
    )
    assert any("expected 'Superseded by ADR-0002'" in x for x in check_supersede_symmetry(adr_dir))


def test_symmetric_supersede_pair_passes(tmp_path):
    adr_dir = build_log(
        tmp_path,
        adrs=(
            ("0001", "First decision", "Superseded by ADR-0002", "2026-01-01", ""),
            ("0002", "Second decision", "Accepted", "2026-01-02", "**Supersedes**: [ADR-0001](0001-first-decision.md)\n"),
        ),
    )
    assert check_supersede_symmetry(adr_dir) == []


def test_broken_link_is_caught(tmp_path):
    adr_dir = build_log(tmp_path)
    p = next(adr_dir.glob("0001-*.md"))
    p.write_text(
        p.read_text(encoding="utf-8").replace("xas-001.md", "xas-999.md"),
        encoding="utf-8",
    )
    assert any("resolves to nothing" in x for x in check_links_resolve(adr_dir))


def test_crlf_line_endings_are_tolerated(tmp_path):
    """CI runs on windows-latest; a CRLF checkout must not fail every check."""
    adr_dir = build_log(tmp_path)
    for p in list(adr_dir.glob("*.md")):
        p.write_bytes(p.read_text(encoding="utf-8").replace("\n", "\r\n").encode("utf-8"))
    for check in ALL_CHECKS:
        assert check(adr_dir) == [], check.__name__
