"""The ADR log check knows the colon heading and the narrowing relation (XAS-044b).

Three things the checks in `test_adr_log.py` must accept or report:

- the heading `# ADR-NNNN: Title`, beside the older `# ADR-NNNN <em-dash> Title`;
- the status `Accepted, narrowed by ADR-NNNN`, with or without a Markdown link;
- the field `**Narrows**: ADR-NNNN`, which must be mutual: the narrowed ADR
  carries the status `Accepted, narrowed by ADR-<narrower>`.

Same style as `test_adr_log.py`: a broken log produces a finding, a clean one
none. `check_narrowing` is the new check; it lives next to the others.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from test_adr_log import (
    ADR_DIR,
    GOOD_BODY,
    build_log,
    check_headers,
    check_narrowing,
    check_statuses,
    parse_adr,
)

pytestmark = pytest.mark.skipif(
    not ADR_DIR.is_dir(),
    reason="no docs/adr/ in this repository; nothing to check",
)

NARROWS_0001 = "**Narrows**: [ADR-0001](0001-first-decision.md)\n"


def write_colon_adr(tmp_path: Path) -> Path:
    """A valid log whose only ADR uses the heading `# ADR-0001: Title`."""
    adr_dir = build_log(tmp_path)
    p = next(adr_dir.glob("0001-*.md"))
    p.write_text(
        p.read_text(encoding="utf-8").replace(
            "# ADR-0001 \N{EM DASH} First decision", "# ADR-0001: First decision"
        ),
        encoding="utf-8",
    )
    assert "# ADR-0001: First decision" in p.read_text(encoding="utf-8")
    return adr_dir


def test_colon_heading_is_accepted(tmp_path):
    adr_dir = write_colon_adr(tmp_path)
    assert check_headers(adr_dir) == []
    adr = parse_adr(next(adr_dir.glob("0001-*.md")))
    assert adr["number"] == "0001"
    assert adr["title"] == "First decision"


def test_colon_heading_with_wrong_number_is_still_caught(tmp_path):
    adr_dir = write_colon_adr(tmp_path)
    p = next(adr_dir.glob("0001-*.md"))
    p.write_text(
        p.read_text(encoding="utf-8").replace("# ADR-0001:", "# ADR-0007:"),
        encoding="utf-8",
    )
    assert any("heading says ADR-0007" in x for x in check_headers(adr_dir))


@pytest.mark.parametrize(
    "status",
    [
        "Accepted, narrowed by [ADR-0002](0002-second-decision.md)",
        "Accepted, narrowed by ADR-0002",
    ],
    ids=["linked", "plain"],
)
def test_narrowed_status_is_accepted(tmp_path, status):
    adr_dir = build_log(
        tmp_path, adrs=(("0001", "First decision", status, "2026-01-01", ""),)
    )
    assert check_statuses(adr_dir) == []


def test_malformed_narrowed_status_is_still_caught(tmp_path):
    adr_dir = build_log(
        tmp_path,
        adrs=(("0001", "First decision", "Accepted, narrowed by someone", "2026-01-01", ""),),
    )
    assert any("not a permitted value" in x for x in check_statuses(adr_dir))


def test_narrowing_must_be_mutual(tmp_path):
    """0002 narrows 0001, but 0001 still reads plain Accepted."""
    adr_dir = build_log(
        tmp_path,
        adrs=(
            ("0001", "First decision", "Accepted", "2026-01-01", ""),
            ("0002", "Second decision", "Accepted", "2026-01-02", NARROWS_0001),
        ),
    )
    problems = check_narrowing(adr_dir)
    assert len(problems) == 1
    assert "0001" in problems[0] and "0002" in problems[0]


def test_mutual_narrowing_passes(tmp_path):
    adr_dir = build_log(
        tmp_path,
        adrs=(
            ("0001", "First decision", "Accepted, narrowed by ADR-0002", "2026-01-01", ""),
            ("0002", "Second decision", "Accepted", "2026-01-02", NARROWS_0001),
        ),
    )
    assert check_narrowing(adr_dir) == []


def test_mutual_narrowing_with_linked_status_passes(tmp_path):
    adr_dir = build_log(
        tmp_path,
        adrs=(
            (
                "0001",
                "First decision",
                "Accepted, narrowed by [ADR-0002](0002-second-decision.md)",
                "2026-01-01",
                "",
            ),
            ("0002", "Second decision", "Accepted", "2026-01-02", NARROWS_0001),
        ),
    )
    assert check_narrowing(adr_dir) == []


def test_narrowed_status_without_narrows_field_is_caught(tmp_path):
    """0001 says it is narrowed by 0002, but 0002 claims no **Narrows**."""
    adr_dir = build_log(
        tmp_path,
        adrs=(
            ("0001", "First decision", "Accepted, narrowed by ADR-0002", "2026-01-01", ""),
            ("0002", "Second decision", "Accepted", "2026-01-02", ""),
        ),
    )
    problems = check_narrowing(adr_dir)
    assert len(problems) == 1
    assert "0001" in problems[0] and "0002" in problems[0]


def test_narrowing_a_missing_adr_is_caught(tmp_path):
    adr_dir = build_log(
        tmp_path,
        adrs=(
            (
                "0002",
                "Second decision",
                "Accepted",
                "2026-01-02",
                "**Narrows**: [ADR-0009](0009-nothing.md)\n",
            ),
        ),
    )
    assert any("0009" in x for x in check_narrowing(adr_dir))


def test_log_without_narrowing_has_no_findings(tmp_path):
    assert check_narrowing(build_log(tmp_path)) == []


def test_real_log_has_no_narrowing_findings():
    assert check_narrowing(ADR_DIR) == []
