"""The backlog script, exercised against small backlogs under `tmp_path`.

`scripts/backlog.py` owns every mechanical backlog step (ADR-0009): it derives
the README table of contents from the item files, allocates IDs, sets a status
and checks the backlog. Expectations here are literal README text, written by
hand, never computed by the script under test.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import backlog

NOTES = "---\n\n## Notes\n\n- **ID prefix**: `SC` (shortcuts)\n"


def item_text(iid: str, title: str, status: str) -> str:
    mark = "✅ DONE - " if status.startswith("Done") else ""
    return f"# [{iid}] {mark}{title}\n\n**Status**: {status}\n\nBody.\n"


def make_backlog(tmp_path: Path, items, toc: str = "### Open\n\n", notes: str = NOTES) -> Path:
    """Write items as (id, title, status) and a README whose TOC block is *toc*.

    Files are written with LF on every platform; the CRLF tests convert them.
    """
    b = tmp_path / "docs" / "backlog"
    b.mkdir(parents=True)
    for iid, title, status in items:
        (b / f"{iid.lower()}.md").write_text(item_text(iid, title, status), encoding="utf-8", newline="\n")
    readme = f"# Backlog\n\nIntro.\n\n## Table of Contents\n\n{toc}{notes}"
    (b / "README.md").write_text(readme, encoding="utf-8", newline="\n")
    return b


def readme(b: Path) -> str:
    return (b / "README.md").read_text(encoding="utf-8")


# ---------- toc ----------


def test_toc_lists_sections_in_fixed_order_with_newest_first(tmp_path):
    b = make_backlog(tmp_path, [
        ("SC-001", "First", "Open"),
        ("SC-002", "Second", "Done (2026-01-02)"),
        ("SC-003", "Third", "Open"),
        ("SC-004", "Fourth", "In Progress"),
    ])

    backlog.write_toc(b)

    assert readme(b) == (
        "# Backlog\n\nIntro.\n\n## Table of Contents\n\n"
        "### Open\n"
        "- [SC-003 — Third](sc-003.md)\n"
        "- [SC-001 — First](sc-001.md)\n"
        "\n"
        "### In Progress\n"
        "- [SC-004 — Fourth](sc-004.md)\n"
        "\n"
        "### Done\n"
        "- [SC-002 — Second](sc-002.md)\n"
        "\n" + NOTES
    )


def test_toc_writes_empty_sections_and_adds_superseded_only_when_used(tmp_path):
    b = make_backlog(tmp_path, [("SC-001", "Old plan", "Superseded (2026-07-10)")])

    backlog.write_toc(b)

    assert "### Open\n\n### In Progress\n\n### Done\n\n### Superseded\n- [SC-001 — Old plan](sc-001.md)\n\n---" in readme(b)


def test_toc_without_superseded_items_has_no_superseded_section(tmp_path):
    b = make_backlog(tmp_path, [("SC-001", "Plan", "Open")])

    backlog.write_toc(b)

    assert "Superseded" not in readme(b)


def test_toc_sorts_an_epic_below_its_substories(tmp_path):
    b = make_backlog(tmp_path, [
        ("SC-026", "Epic", "Open"),
        ("SC-026a", "Sub a", "Open"),
        ("SC-026b", "Sub b", "Open"),
        ("SC-027", "Next", "Open"),
    ])

    backlog.write_toc(b)

    assert (
        "### Open\n"
        "- [SC-027 — Next](sc-027.md)\n"
        "- [SC-026b — Sub b](sc-026b.md)\n"
        "- [SC-026a — Sub a](sc-026a.md)\n"
        "- [SC-026 — Epic](sc-026.md)\n\n"
    ) in readme(b)


def test_toc_groups_mixed_prefixes_by_prefix_then_number(tmp_path):
    b = make_backlog(tmp_path, [
        ("SC-002", "Two", "Open"),
        ("BUG-004", "Bug four", "Open"),
        ("SC-010", "Ten", "Open"),
        ("BUG-001", "Bug one", "Open"),
    ])

    backlog.write_toc(b)

    assert (
        "### Open\n"
        "- [SC-010 — Ten](sc-010.md)\n"
        "- [SC-002 — Two](sc-002.md)\n"
        "- [BUG-004 — Bug four](bug-004.md)\n"
        "- [BUG-001 — Bug one](bug-001.md)\n\n"
    ) in readme(b)


def test_toc_takes_the_title_from_the_heading_without_the_done_marker(tmp_path):
    b = make_backlog(tmp_path, [("SC-001", "Finished thing", "Done (2026-01-01)")])

    backlog.write_toc(b)

    assert "- [SC-001 — Finished thing](sc-001.md)\n" in readme(b)


ANNOTATED = [("SC-036b", "Old plan", "Superseded (2026-07-10)"),
             ("SC-036f", "New part", "Open"), ("SC-040", "New plan", "Open")]
ANNOTATED_TOC = ("### Superseded\n\n"
                 "- [SC-036b — Old plan](sc-036b.md) — replaced by [SC-040](sc-040.md) + [SC-036f](sc-036f.md)\n\n")


def test_toc_refuses_a_line_with_text_after_its_link_and_leaves_the_readme_alone(tmp_path):
    b = make_backlog(tmp_path, ANNOTATED, toc=ANNOTATED_TOC)
    before = readme(b)

    with pytest.raises(backlog.BacklogError, match=r"README\.md:9: .*replaced by"):
        backlog.write_toc(b)

    assert readme(b) == before


def test_toc_accepts_a_line_that_is_exactly_the_derived_form(tmp_path):
    toc = "### Open\n- [SC-001 — One](sc-001.md)\n\n### In Progress\n\n### Done\n\n"
    b = make_backlog(tmp_path, [("SC-001", "One", "Open")], toc=toc)
    before = readme(b)

    backlog.write_toc(b)

    assert readme(b) == before


def test_toc_accepts_trailing_whitespace_after_the_link(tmp_path):
    toc = "### Open\n- [SC-001 — One](sc-001.md)  \n\n"
    b = make_backlog(tmp_path, [("SC-001", "One", "Open")], toc=toc)

    backlog.write_toc(b)

    assert "- [SC-001 — One](sc-001.md)\n" in readme(b)


def test_toc_accepts_its_own_line_for_a_title_that_holds_a_link(tmp_path):
    b = make_backlog(tmp_path, [("SC-002", "Follow up [SC-001](sc-001.md)", "Open"), ("SC-001", "One", "Open")])
    backlog.write_toc(b)
    first = readme(b)

    backlog.write_toc(b)

    assert readme(b) == first
    assert "- [SC-002 — Follow up [SC-001](sc-001.md)](sc-002.md)\n" in first


def test_toc_ends_at_a_level_two_heading_when_there_is_no_rule(tmp_path):
    b = make_backlog(tmp_path, [("SC-001", "One", "Open")], notes="## Notes\n\nKept.\n")

    backlog.write_toc(b)

    assert readme(b).endswith("### Done\n\n## Notes\n\nKept.\n")


def test_toc_run_twice_changes_nothing(tmp_path):
    b = make_backlog(tmp_path, [("SC-001", "One", "Open"), ("SC-002", "Two", "Done (2026-01-01)")])
    backlog.write_toc(b)
    first = readme(b)

    backlog.write_toc(b)

    assert readme(b) == first


def test_toc_keeps_crlf_line_endings(tmp_path):
    b = make_backlog(tmp_path, [("SC-001", "One", "Open")])
    p = b / "README.md"
    p.write_bytes(p.read_bytes().replace(b"\n", b"\r\n"))

    backlog.write_toc(b)

    raw = p.read_bytes()
    assert b"- [SC-001 \xe2\x80\x94 One](sc-001.md)\r\n" in raw
    assert b"\n" not in raw.replace(b"\r\n", b"")


def test_toc_flattens_an_indented_substory_line(tmp_path):
    toc = "### Open\n- [SC-024 — Epic](sc-024.md)\n  - [SC-024a — Sub](sc-024a.md)\n\n"
    b = make_backlog(tmp_path, [("SC-024", "Epic", "Open"), ("SC-024a", "Sub", "Open")], toc=toc)

    backlog.write_toc(b)

    assert "### Open\n- [SC-024a — Sub](sc-024a.md)\n- [SC-024 — Epic](sc-024.md)\n\n" in readme(b)


def test_toc_accepts_a_title_with_brackets(tmp_path):
    toc = "### Open\n- [SC-046 — Make `[settings]` configurable](sc-046.md)\n\n"
    b = make_backlog(tmp_path, [("SC-046", "Make `[settings]` configurable", "Open")], toc=toc)

    backlog.write_toc(b)

    assert "- [SC-046 — Make `[settings]` configurable](sc-046.md)\n" in readme(b)


def test_toc_refuses_content_no_item_produces_and_leaves_the_readme_alone(tmp_path):
    toc = "### Open\n\n### Closing an item (checklist)\n\n1. Verify the criteria.\n\n"
    b = make_backlog(tmp_path, [("SC-001", "One", "Open")], toc=toc)
    before = readme(b)

    with pytest.raises(backlog.BacklogError, match=r"README\.md:9: .*Closing an item"):
        backlog.write_toc(b)

    assert readme(b) == before


def test_toc_refuses_a_line_linking_to_a_missing_item(tmp_path):
    b = make_backlog(tmp_path, [("SC-001", "One", "Open")], toc="### Open\n- [SC-009 — Ghost](sc-009.md)\n\n")

    with pytest.raises(backlog.BacklogError, match="sc-009.md"):
        backlog.write_toc(b)


def test_toc_refuses_an_item_with_an_unknown_status(tmp_path):
    b = make_backlog(tmp_path, [("SC-001", "One", "Blocked")])

    with pytest.raises(backlog.BacklogError, match=r"sc-001\.md: .*'Blocked'"):
        backlog.write_toc(b)


def test_toc_refuses_a_readme_without_a_table_of_contents(tmp_path):
    b = make_backlog(tmp_path, [("SC-001", "One", "Open")])
    (b / "README.md").write_text("# Backlog\n\nNothing here.\n", encoding="utf-8")

    with pytest.raises(backlog.BacklogError, match="Table of Contents"):
        backlog.write_toc(b)


# ---------- next-id ----------


def test_next_id_follows_the_highest_number_of_the_backlogs_prefix(tmp_path):
    b = make_backlog(tmp_path, [
        ("SC-003", "Three", "Open"),
        ("SC-010", "Ten", "Done (2026-01-01)"),
        ("SC-010a", "Ten a", "Open"),
        ("BUG-042", "Legacy bug", "Done (2026-01-01)"),
    ])

    assert backlog.next_id(b) == "SC-011"


def test_next_id_in_an_empty_backlog_is_001(tmp_path):
    b = make_backlog(tmp_path, [])

    assert backlog.next_id(b) == "SC-001"


def test_next_id_under_a_parent_takes_the_next_letter(tmp_path):
    b = make_backlog(tmp_path, [
        ("SC-003", "Epic", "Open"),
        ("SC-003a", "Sub a", "Open"),
        ("SC-003b", "Sub b", "Done (2026-01-01)"),
    ])

    assert backlog.next_id(b, "SC-003") == "SC-003c"


def test_next_id_under_a_story_without_substories_starts_at_a(tmp_path):
    b = make_backlog(tmp_path, [("SC-003", "Story", "Open")])

    assert backlog.next_id(b, "SC-003") == "SC-003a"


def test_next_id_refuses_a_parent_that_does_not_exist(tmp_path):
    b = make_backlog(tmp_path, [("SC-003", "Story", "Open")])

    with pytest.raises(backlog.BacklogError, match="SC-004"):
        backlog.next_id(b, "SC-004")


def test_next_id_refuses_a_substory_as_parent(tmp_path):
    b = make_backlog(tmp_path, [("SC-003", "Epic", "Open"), ("SC-003a", "Sub", "Open")])

    with pytest.raises(backlog.BacklogError, match="SC-003a"):
        backlog.next_id(b, "SC-003a")


def test_next_id_refuses_a_backlog_without_an_id_prefix_note(tmp_path):
    b = make_backlog(tmp_path, [("SC-001", "One", "Open")], notes="## Notes\n\nNone.\n")

    with pytest.raises(backlog.BacklogError, match="ID prefix"):
        backlog.next_id(b)


# ---------- set-status ----------

TODAY = "2026-10-03"


def item(b: Path, iid: str) -> str:
    return (b / f"{iid.lower()}.md").read_text(encoding="utf-8")


def test_set_status_pulls_an_item_and_moves_it_in_the_toc(tmp_path):
    b = make_backlog(tmp_path, [("SC-001", "One", "Open")])

    messages = backlog.set_status(b, "SC-001", "In Progress", TODAY)

    assert item(b, "SC-001") == "# [SC-001] One\n\n**Status**: In Progress\n\nBody.\n"
    assert "### Open\n\n### In Progress\n- [SC-001 — One](sc-001.md)\n" in readme(b)
    assert messages == ["SC-001: Open → In Progress"]


def test_set_status_done_writes_the_date_and_the_heading_marker(tmp_path):
    b = make_backlog(tmp_path, [("SC-001", "One", "In Progress")])

    backlog.set_status(b, "SC-001", "Done", TODAY)

    assert item(b, "SC-001") == "# [SC-001] ✅ DONE - One\n\n**Status**: Done (2026-10-03)\n\nBody.\n"
    assert "### Done\n- [SC-001 — One](sc-001.md)\n" in readme(b)


def test_set_status_reopening_removes_the_date_and_the_marker(tmp_path):
    b = make_backlog(tmp_path, [("SC-001", "One", "Done (2026-01-01)")])

    backlog.set_status(b, "SC-001", "Open", TODAY)

    assert item(b, "SC-001") == "# [SC-001] One\n\n**Status**: Open\n\nBody.\n"


def test_set_status_superseded_writes_the_date_without_the_done_marker(tmp_path):
    b = make_backlog(tmp_path, [("SC-001", "One", "Open")])

    backlog.set_status(b, "SC-001", "Superseded", TODAY)

    assert item(b, "SC-001") == "# [SC-001] One\n\n**Status**: Superseded (2026-10-03)\n\nBody.\n"
    assert "### Superseded\n- [SC-001 — One](sc-001.md)\n" in readme(b)


def test_set_status_keeps_crlf_in_the_item_file(tmp_path):
    b = make_backlog(tmp_path, [("SC-001", "One", "Open")])
    p = b / "sc-001.md"
    p.write_bytes(p.read_bytes().replace(b"\n", b"\r\n"))

    backlog.set_status(b, "SC-001", "In Progress", TODAY)

    assert p.read_bytes() == b"# [SC-001] One\r\n\r\n**Status**: In Progress\r\n\r\nBody.\r\n"


def test_set_status_refuses_an_unknown_status_and_writes_nothing(tmp_path):
    b = make_backlog(tmp_path, [("SC-001", "One", "Open")])

    with pytest.raises(backlog.BacklogError, match="Blocked"):
        backlog.set_status(b, "SC-001", "Blocked", TODAY)

    assert "**Status**: Open" in item(b, "SC-001")


def test_set_status_refuses_an_unknown_item(tmp_path):
    b = make_backlog(tmp_path, [("SC-001", "One", "Open")])

    with pytest.raises(backlog.BacklogError, match="SC-002"):
        backlog.set_status(b, "SC-002", "Open", TODAY)


def test_set_status_pulling_a_substory_pulls_its_open_epic(tmp_path):
    b = make_backlog(tmp_path, [("SC-003", "Epic", "Open"), ("SC-003a", "Sub", "Open")])

    messages = backlog.set_status(b, "SC-003a", "In Progress", TODAY)

    assert "**Status**: In Progress" in item(b, "SC-003")
    assert "### In Progress\n- [SC-003a — Sub](sc-003a.md)\n- [SC-003 — Epic](sc-003.md)\n" in readme(b)
    assert messages == ["SC-003a: Open → In Progress", "SC-003: Open → In Progress (epic follows SC-003a)"]


def test_set_status_leaves_an_epic_alone_that_is_already_in_progress(tmp_path):
    b = make_backlog(tmp_path, [("SC-003", "Epic", "In Progress"), ("SC-003a", "Sub", "Open")])

    messages = backlog.set_status(b, "SC-003a", "In Progress", TODAY)

    assert messages == ["SC-003a: Open → In Progress"]


def test_set_status_refuses_to_close_an_epic_with_an_open_substory(tmp_path):
    b = make_backlog(tmp_path, [
        ("SC-003", "Epic", "In Progress"),
        ("SC-003a", "Sub a", "Done (2026-01-01)"),
        ("SC-003b", "Sub b", "Open"),
    ])

    with pytest.raises(backlog.BacklogError, match="SC-003b"):
        backlog.set_status(b, "SC-003", "Done", TODAY)

    assert "**Status**: In Progress" in item(b, "SC-003")


def test_set_status_closes_an_epic_whose_substories_are_done_or_superseded(tmp_path):
    b = make_backlog(tmp_path, [
        ("SC-003", "Epic", "In Progress"),
        ("SC-003a", "Sub a", "Done (2026-01-01)"),
        ("SC-003b", "Sub b", "Superseded (2026-01-01)"),
    ])

    backlog.set_status(b, "SC-003", "Done", TODAY)

    assert "**Status**: Done (2026-10-03)" in item(b, "SC-003")


def test_set_status_closing_the_last_substory_says_the_epic_can_close(tmp_path):
    b = make_backlog(tmp_path, [
        ("SC-003", "Epic", "In Progress"),
        ("SC-003a", "Sub a", "Done (2026-01-01)"),
        ("SC-003b", "Sub b", "In Progress"),
    ])

    messages = backlog.set_status(b, "SC-003b", "Done", TODAY)

    assert "**Status**: In Progress" in item(b, "SC-003")
    assert messages == ["SC-003b: In Progress → Done", "SC-003: every substory is closed; the epic can be closed"]


def test_set_status_refuses_before_writing_when_the_toc_cannot_be_derived(tmp_path):
    toc = "### Open\n\nA hand-written note.\n\n"
    b = make_backlog(tmp_path, [("SC-001", "One", "Open")], toc=toc)

    with pytest.raises(backlog.BacklogError, match="hand-written"):
        backlog.set_status(b, "SC-001", "In Progress", TODAY)

    assert "**Status**: Open" in item(b, "SC-001")


def test_set_status_refuses_a_line_with_text_after_its_link_and_writes_nothing(tmp_path):
    b = make_backlog(tmp_path, ANNOTATED, toc=ANNOTATED_TOC)
    before = readme(b)

    with pytest.raises(backlog.BacklogError, match=r"README\.md:9: .*replaced by"):
        backlog.set_status(b, "SC-040", "In Progress", TODAY)

    assert "**Status**: Open" in item(b, "SC-040")
    assert readme(b) == before


# ---------- check ----------


def clean_backlog(tmp_path, items):
    b = make_backlog(tmp_path, items)
    backlog.write_toc(b)
    return b


def write_item(b: Path, iid: str, text: str) -> None:
    (b / f"{iid.lower()}.md").write_text(text, encoding="utf-8", newline="\n")


def test_check_passes_a_clean_backlog(tmp_path):
    b = clean_backlog(tmp_path, [("SC-001", "One", "Open"), ("SC-002", "Two", "Done (2026-01-01)")])

    assert backlog.check(b) == []


def test_check_reports_a_toc_that_is_not_derived_from_the_items(tmp_path):
    b = make_backlog(tmp_path, [("SC-001", "One", "Open"), ("SC-002", "Two", "Open")],
                     toc="### Open\n- [SC-001 — One](sc-001.md)\n- [SC-002 — Two](sc-002.md)\n\n")

    assert backlog.check(b) == ["README.md: the table of contents differs from the items; run `backlog.py toc`"]


def test_check_reports_a_toc_block_the_script_would_refuse(tmp_path):
    b = make_backlog(tmp_path, [("SC-001", "One", "Open")], toc="### Open\n\nA hand-written note.\n\n")

    assert any("hand-written" in p for p in backlog.check(b))


def test_check_reports_a_heading_that_names_another_id(tmp_path):
    b = clean_backlog(tmp_path, [("SC-001", "One", "Open")])
    write_item(b, "SC-001", "# [SC-002] One\n\n**Status**: Open\n")

    assert "sc-001.md: heading says SC-002" in backlog.check(b)


def test_check_reports_an_item_without_a_status(tmp_path):
    b = clean_backlog(tmp_path, [("SC-001", "One", "Open")])
    write_item(b, "SC-001", "# [SC-001] One\n\nNo status.\n")

    assert "sc-001.md: no '**Status**:' line" in backlog.check(b)


def test_check_reports_an_unknown_status(tmp_path):
    b = clean_backlog(tmp_path, [("SC-001", "One", "Open")])
    write_item(b, "SC-001", "# [SC-001] One\n\n**Status**: Blocked\n")

    assert "sc-001.md: unknown status 'Blocked'" in backlog.check(b)


def test_check_reports_a_date_that_does_not_parse(tmp_path):
    b = clean_backlog(tmp_path, [("SC-001", "One", "Done (01-01-2026)")])

    assert "sc-001.md: date '01-01-2026' does not parse" in backlog.check(b)


def test_check_reports_a_done_marker_on_an_item_that_is_not_done(tmp_path):
    b = clean_backlog(tmp_path, [("SC-001", "One", "Open")])
    write_item(b, "SC-001", "# [SC-001] ✅ DONE - One\n\n**Status**: Open\n")

    assert "sc-001.md: heading marked DONE but status is 'Open'" in backlog.check(b)


@pytest.mark.parametrize("marker", ["✅ DONE — ", "COMPLETED - "])
def test_check_reports_a_heading_with_an_unknown_done_marker(tmp_path, marker):
    b = clean_backlog(tmp_path, [("SC-001", "One", "Done (2026-01-01)")])
    write_item(b, "SC-001", f"# [SC-001] {marker}One\n\n**Status**: Done (2026-01-01)\n")

    assert f"sc-001.md: heading starts with {marker!r}, not the done marker '✅ DONE - '" in backlog.check(b)


def test_check_tolerates_a_legacy_done_without_date_or_marker(tmp_path):
    """XAS-016..024 shape: Done, no date, no marker. Not a defect."""
    b = make_backlog(tmp_path, [])
    write_item(b, "SC-001", "# [SC-001] Legacy\n\n**Status**: Done\n")
    backlog.write_toc(b)

    assert backlog.check(b) == []


def test_check_reports_an_epic_done_while_a_substory_is_open(tmp_path):
    b = clean_backlog(tmp_path, [("SC-001", "Epic", "Done (2026-01-01)"), ("SC-001a", "Sub", "Open")])

    assert "SC-001 is Done while SC-001a is not closed" in backlog.check(b)


def test_check_passes_an_epic_done_with_every_substory_closed(tmp_path):
    b = clean_backlog(tmp_path, [
        ("SC-001", "Epic", "Done (2026-01-01)"),
        ("SC-001a", "Sub a", "Done (2026-01-01)"),
        ("SC-001b", "Sub b", "Superseded (2026-01-01)"),
    ])

    assert backlog.check(b) == []


def test_check_reports_a_link_that_resolves_to_nothing(tmp_path):
    b = clean_backlog(tmp_path, [("SC-001", "One", "Open")])
    write_item(b, "SC-001", item_text("SC-001", "One", "Open") + "\nSee [SC-999](sc-999.md).\n")

    assert "sc-001.md: link 'sc-999.md' resolves to nothing" in backlog.check(b)


def test_check_ignores_web_links_and_anchors(tmp_path):
    b = clean_backlog(tmp_path, [("SC-001", "One", "Open")])
    write_item(b, "SC-001", item_text("SC-001", "One", "Open")
               + "\n[web](https://example.com) [anchor](#top) [file](README.md#notes)\n")

    assert backlog.check(b) == []


def test_check_reports_a_stale_toc_next_to_other_problems(tmp_path):
    b = make_backlog(tmp_path, [("SC-001", "One", "Open")], toc="### Open\n\n")
    write_item(b, "SC-001", item_text("SC-001", "One", "Open") + "\nSee [gone](gone.md).\n")

    assert backlog.check(b) == [
        "sc-001.md: link 'gone.md' resolves to nothing",
        "README.md: the table of contents differs from the items; run `backlog.py toc`",
    ]


# ---------- show ----------


def with_priority(b: Path, iid: str, priority: str) -> None:
    """Add a `**Priority**:` line under the status of an item written by make_backlog."""
    path = b / f"{iid.lower()}.md"
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace("\n\nBody.", f"\n**Priority**: {priority}\n\nBody."), encoding="utf-8", newline="\n")


def test_show_prints_id_status_priority_and_title_in_the_order_asked(tmp_path):
    b = make_backlog(tmp_path, [
        ("SC-001", "First", "Open"),
        ("SC-002", "Second", "In Progress"),
    ])
    with_priority(b, "SC-001", "High")
    with_priority(b, "SC-002", "Low")

    lines, missing = backlog.show(b, ["SC-002", "SC-001"])

    assert lines == ["SC-002\tIn Progress\tLow\tSecond", "SC-001\tOpen\tHigh\tFirst"]
    assert missing == []


def test_show_without_ids_prints_every_item_oldest_first(tmp_path):
    b = make_backlog(tmp_path, [
        ("SC-002", "Second", "Open"),
        ("SC-001", "First", "Open"),
        ("SC-001a", "Sub", "Open"),
    ])

    lines, _ = backlog.show(b, [])

    assert [line.split("\t")[0] for line in lines] == ["SC-001", "SC-001a", "SC-002"]


def test_show_prints_a_dash_for_an_item_without_priority(tmp_path):
    b = make_backlog(tmp_path, [("SC-001", "First", "Open")])

    lines, _ = backlog.show(b, ["SC-001"])

    assert lines == ["SC-001\tOpen\t—\tFirst"]


def test_show_keeps_the_status_date_and_drops_the_done_marker(tmp_path):
    b = make_backlog(tmp_path, [("SC-001", "First", "Done (2026-01-02)")])
    with_priority(b, "SC-001", "High (prerequisite for SC-007)")

    lines, _ = backlog.show(b, ["SC-001"])

    assert lines == ["SC-001\tDone (2026-01-02)\tHigh (prerequisite for SC-007)\tFirst"]


def test_show_names_the_ids_that_resolve_to_no_item(tmp_path):
    b = make_backlog(tmp_path, [("SC-001", "First", "Open")])

    lines, problems = backlog.show(b, ["SC-009", "SC-001", "nonsense"])

    assert lines == ["SC-001\tOpen\t—\tFirst"]
    assert problems == ["SC-009: no such item", "nonsense: no such item"]


def test_show_reports_an_unreadable_item_as_unreadable_not_as_missing(tmp_path):
    b = make_backlog(tmp_path, [("SC-001", "First", "Open"), ("SC-002", "Second", "Open")])
    write_item(b, "SC-001", "# [SC-001] First\n\nNo status line.\n")

    lines, problems = backlog.show(b, ["SC-001", "SC-002"])

    assert lines == ["SC-002\tOpen\t—\tSecond"]
    assert problems == ["sc-001.md: no '**Status**:' line"]


def test_show_without_ids_prints_every_readable_item_and_names_the_rest(tmp_path):
    b = make_backlog(tmp_path, [
        ("SC-001", "First", "Open"),
        ("SC-002", "Second", "Open"),
        ("SC-003", "Third", "In Progress"),
    ])
    write_item(b, "SC-002", "No heading.\n\n**Status**: Open\n")

    lines, problems = backlog.show(b, [])

    assert lines == ["SC-001\tOpen\t—\tFirst", "SC-003\tIn Progress\t—\tThird"]
    assert problems == ["sc-002.md: no '# [PREFIX-###] Title' heading"]


def test_show_in_progress_prints_only_the_items_in_progress_as_work(tmp_path):
    b = make_backlog(tmp_path, [
        ("SC-001", "Backlog refinement", "In Progress"),
        ("SC-002", "Epic", "In Progress"),
        ("SC-002a", "Sub", "In Progress"),
        ("SC-002b", "Later sub", "Open"),
        ("SC-003", "Story", "In Progress"),
        ("SC-004", "Waiting", "Open"),
        ("SC-005", "Finished", "Done (2026-10-01)"),
    ])

    lines, problems = backlog.show(b, [], in_progress=True)

    assert [line.split("\t")[0] for line in lines] == ["SC-002a", "SC-003"]
    assert problems == []


def test_show_in_progress_keeps_a_refinement_item_with_a_priority_out(tmp_path):
    b = make_backlog(tmp_path, [("SC-001", "Backlog refinement", "In Progress")])
    with_priority(b, "SC-001", "Medium")

    lines, _ = backlog.show(b, [], in_progress=True)

    assert lines == []


def test_show_in_progress_with_ids_filters_those_ids(tmp_path):
    b = make_backlog(tmp_path, [
        ("SC-001", "Epic", "In Progress"),
        ("SC-001a", "Sub", "Open"),
        ("SC-002", "Story", "In Progress"),
        ("SC-003", "Other", "In Progress"),
    ])

    lines, problems = backlog.show(b, ["SC-001", "SC-002", "SC-009"], in_progress=True)

    assert lines == ["SC-002\tIn Progress\t—\tStory"]
    assert problems == ["SC-009: no such item"]


def test_cli_show_in_progress(tmp_path, capsys):
    b = make_backlog(tmp_path, [
        ("SC-001", "Backlog refinement", "In Progress"),
        ("SC-002", "Story", "In Progress"),
    ])

    assert backlog.main(["--dir", str(b), "show", "--in-progress"]) == 0
    assert capsys.readouterr().out == "SC-002\tIn Progress\t—\tStory\n"


# ---------- another repository, read at its remote's default branch ----------


def git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "-c", "commit.gpgsign=false", *args],
        cwd=cwd, capture_output=True, check=True,
    )
    return result.stdout.decode("utf-8")


def publish(upstream: Path, message: str) -> None:
    git(upstream, "add", "-A")
    git(upstream, "commit", "-q", "-m", message)
    git(upstream, "push", "-q", "origin", "HEAD")


@pytest.fixture
def remote(tmp_path):
    """A bare remote whose default branch is `trunk`, and an upstream working copy that pushes to it."""
    bare = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", "-b", "trunk", str(bare))
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    git(upstream, "init", "-q", "-b", "trunk")
    git(upstream, "remote", "add", "origin", str(bare))
    make_backlog(upstream, [("SC-001", "First", "Open"), ("SC-002", "Second", "Open")])
    publish(upstream, "items")
    return bare, upstream


def state(checkout: Path) -> tuple[str, str, str]:
    return git(checkout, "rev-parse", "HEAD"), git(checkout, "status", "--porcelain"), git(checkout, "branch", "--show-current")


def test_repo_reads_the_items_the_remote_default_branch_has_now(tmp_path, remote, capsys):
    bare, upstream = remote
    git(tmp_path, "clone", "-q", str(bare), "checkout")
    checkout = tmp_path / "checkout"
    git(checkout, "switch", "-q", "-c", "feature")
    write_item(checkout / "docs" / "backlog", "SC-002", item_text("SC-002", "Second", "In Progress"))
    write_item(upstream / "docs" / "backlog", "SC-001", item_text("SC-001", "First", "Done (2026-10-21)"))
    publish(upstream, "close SC-001")
    before = state(checkout)

    assert backlog.main(["--repo", str(checkout), "show", "SC-001", "SC-002"]) == 0

    assert capsys.readouterr().out == "SC-001\tDone (2026-10-21)\t—\tFirst\nSC-002\tOpen\t—\tSecond\n"
    assert state(checkout) == before


def test_repo_show_in_progress_reads_the_remote_default_branch(tmp_path, remote, capsys):
    bare, upstream = remote
    write_item(upstream / "docs" / "backlog", "SC-002", item_text("SC-002", "Second", "In Progress"))
    publish(upstream, "pull SC-002")
    git(tmp_path, "clone", "-q", str(bare), "checkout")

    assert backlog.main(["--repo", str(tmp_path / "checkout"), "show", "--in-progress"]) == 0

    assert capsys.readouterr().out == "SC-002\tIn Progress\t—\tSecond\n"


def test_repo_finds_the_default_branch_where_origin_head_was_never_set(tmp_path, remote, capsys):
    bare, _ = remote
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    git(checkout, "init", "-q", "-b", "local")
    git(checkout, "remote", "add", "origin", str(bare))

    assert backlog.main(["--repo", str(checkout), "show"]) == 0

    assert capsys.readouterr().out == "SC-001\tOpen\t—\tFirst\nSC-002\tOpen\t—\tSecond\n"


def test_repo_without_a_backlog_on_the_default_branch_fails_with_a_message(tmp_path, remote, capsys):
    bare, upstream = remote
    git(upstream, "rm", "-q", "-r", "docs")
    publish(upstream, "no backlog")
    git(tmp_path, "clone", "-q", str(bare), "checkout")

    assert backlog.main(["--repo", str(tmp_path / "checkout"), "show"]) == 1

    out, err = capsys.readouterr()
    assert out == ""
    assert err.startswith("backlog: ") and "docs/backlog" in err


def test_repo_without_a_remote_fails_with_a_message(tmp_path, capsys):
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    git(checkout, "init", "-q")

    assert backlog.main(["--repo", str(checkout), "show"]) == 1

    err = capsys.readouterr().err
    assert err.startswith("backlog: ") and "'origin'" in err


@pytest.mark.parametrize("command", [["toc"], ["set-status", "SC-001", "Done"], ["next-id"], ["check"]])
def test_repo_serves_show_only(tmp_path, remote, capsys, command):
    bare, _ = remote
    git(tmp_path, "clone", "-q", str(bare), "checkout")

    assert backlog.main(["--repo", str(tmp_path / "checkout"), *command]) == 1

    assert "--repo" in capsys.readouterr().err


# ---------- command line ----------

SCRIPT = Path(backlog.__file__)


def test_cli_toc_rewrites_the_readme(tmp_path):
    b = make_backlog(tmp_path, [("SC-001", "One", "Open")])

    assert backlog.main(["--dir", str(b), "toc"]) == 0
    assert "- [SC-001 — One](sc-001.md)" in readme(b)


def test_cli_next_id_prints_the_id(tmp_path, capsys):
    b = make_backlog(tmp_path, [("SC-003", "Epic", "Open")])

    assert backlog.main(["--dir", str(b), "next-id"]) == 0
    assert backlog.main(["--dir", str(b), "next-id", "SC-003"]) == 0
    assert capsys.readouterr().out == "SC-004\nSC-003a\n"


def test_cli_show_prints_the_items_and_fails_on_a_missing_one(tmp_path, capsys):
    b = make_backlog(tmp_path, [("SC-001", "First", "Open")])

    assert backlog.main(["--dir", str(b), "show", "SC-001"]) == 0
    assert capsys.readouterr().out == "SC-001\tOpen\t—\tFirst\n"

    assert backlog.main(["--dir", str(b), "show", "SC-001", "SC-009"]) == 1
    out, err = capsys.readouterr()
    assert out == "SC-001\tOpen\t—\tFirst\n"
    assert err == "backlog: SC-009: no such item\n"


def test_cli_set_status_prints_what_changed(tmp_path, capsys):
    b = make_backlog(tmp_path, [("SC-001", "One", "In Progress")])

    assert backlog.main(["--dir", str(b), "set-status", "SC-001", "Done", "--date", "2026-10-03"]) == 0
    assert capsys.readouterr().out == "SC-001: In Progress → Done\n"
    assert "**Status**: Done (2026-10-03)" in item(b, "SC-001")


def test_cli_set_status_dates_a_close_today_by_default(tmp_path):
    from datetime import date

    b = make_backlog(tmp_path, [("SC-001", "One", "In Progress")])

    backlog.main(["--dir", str(b), "set-status", "SC-001", "Done"])

    assert f"**Status**: Done ({date.today().isoformat()})" in item(b, "SC-001")


def test_cli_check_is_silent_and_succeeds_on_a_clean_backlog(tmp_path, capsys):
    b = clean_backlog(tmp_path, [("SC-001", "One", "Open")])

    assert backlog.main(["--dir", str(b), "check"]) == 0
    assert capsys.readouterr().out == ""


def test_cli_check_lists_problems_and_fails(tmp_path, capsys):
    b = make_backlog(tmp_path, [("SC-001", "One", "Open")])

    assert backlog.main(["--dir", str(b), "check"]) == 1
    assert "differs from the items" in capsys.readouterr().out


def test_cli_refusal_goes_to_stderr_and_fails(tmp_path, capsys):
    b = make_backlog(tmp_path, [("SC-001", "One", "Open")])

    assert backlog.main(["--dir", str(b), "set-status", "SC-009", "Open"]) == 1
    assert "SC-009: no such item" in capsys.readouterr().err


def test_cli_finds_the_backlog_from_inside_the_repository(tmp_path, monkeypatch, capsys):
    make_backlog(tmp_path, [("SC-001", "One", "Open")])
    monkeypatch.chdir(tmp_path / "docs")

    assert backlog.main(["next-id"]) == 0
    assert capsys.readouterr().out == "SC-002\n"


def test_cli_without_a_backlog_says_how_to_name_one(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    assert backlog.main(["check"]) == 1
    assert "--dir" in capsys.readouterr().err


def test_script_runs_standalone_and_prints_utf8(tmp_path):
    """The way the skills call it, minus `uv`: a fresh interpreter, output piped."""
    import subprocess
    import sys

    b = make_backlog(tmp_path, [("SC-001", "One", "Open")])
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--dir", str(b), "set-status", "SC-001", "In Progress"],
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    assert result.stdout.decode("utf-8").splitlines() == ["SC-001: Open → In Progress"]


def test_check_ignores_links_inside_code(tmp_path):
    b = clean_backlog(tmp_path, [("SC-001", "One", "Open")])
    write_item(b, "SC-001", item_text("SC-001", "One", "Open")
               + "\nInline `[n](ziel.md \"T\")` and:\n\n```markdown\n[p](<ziel x.md>)\n```\n")

    assert backlog.check(b) == []


def test_check_ignores_links_with_any_uri_scheme(tmp_path):
    b = clean_backlog(tmp_path, [("SC-001", "One", "Open")])
    write_item(b, "SC-001", item_text("SC-001", "One", "Open") + "\n[call](tel:+49123) [vault](obsidian://open)\n")

    assert backlog.check(b) == []
