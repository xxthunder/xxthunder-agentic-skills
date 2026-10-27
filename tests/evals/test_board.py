"""The board as the evals write and read it: cards, the two-column table, the parser."""
from __future__ import annotations

import pytest

from evals.board import WEB, board_md, card, ids, parse_board


def test_card_links_item_and_repo():
    assert card("DEMO-001", "Add retry") == (
        f"[DEMO-001]({WEB}/src/branch/develop/docs/backlog/demo-001.md) · [demo]({WEB}) — Add retry"
    )


def test_card_appends_the_reason():
    assert card("DEMO-001", "Add retry", "before the release").endswith(" — Add retry · before the release")


def test_board_round_trips_through_the_parser():
    nxt = [card("DEMO-001", "One"), card("DEMO-002", "Two")]
    prog = [card("DEMO-003", "Three")]
    assert parse_board(board_md(nxt, prog)) == (nxt, prog)


def test_shorter_column_leaves_empty_cells():
    text = board_md([], [card("DEMO-003", "Three")])
    assert "| | [DEMO-003]" in text
    assert parse_board(text) == ([], [card("DEMO-003", "Three")])


def test_empty_board_keeps_header_and_separator():
    text = board_md([], [])
    assert "| Next | In Progress |\n|---|---|\n" in text
    assert parse_board(text) == ([], [])


def test_escaped_pipe_stays_inside_the_cell():
    c = card("DEMO-001", r"a \| b")
    assert parse_board(board_md([c], [])) == ([c], [])


def test_rows_outside_the_board_table_are_ignored():
    text = board_md([card("DEMO-001", "One")], []) + "\n| other | table | here |\n"
    assert parse_board(text) == ([card("DEMO-001", "One")], [])


def test_a_row_with_three_cells_is_an_error():
    text = "| Next | In Progress |\n|---|---|\n| a | b | c |\n"
    with pytest.raises(AssertionError, match="3 cells"):
        parse_board(text)


def test_ids_reads_the_item_ids_of_cards():
    assert ids([card("DEMO-004a", "Sub"), card("DEMO-001", "One")]) == ["DEMO-004a", "DEMO-001"]
