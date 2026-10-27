"""The board as the fixture writes it and the grading reads it.

The format follows the `Board` contract in `fixtures/board-contract.md`: one
Markdown table, `| Next | In Progress |`, a card per cell.
"""
from __future__ import annotations

import re
from itertools import zip_longest

WEB = "https://example.com/team/demo"
BOARD_FILE = "engineering/board.md"

HEADER_RE = re.compile(r"^\|\s*Next\s*\|\s*In Progress\s*\|\s*$")
CELL_SPLIT_RE = re.compile(r"(?<!\\)\|")
CARD_ID_RE = re.compile(r"\[([A-Z]+-\d{3}[a-z]?)\]")


def card(item_id: str, title: str, reason: str = "") -> str:
    url = f"{WEB}/src/branch/develop/docs/backlog/{item_id.lower()}.md"
    return f"[{item_id}]({url}) · [demo]({WEB}) — {title}" + (f" · {reason}" if reason else "")


def board_md(next_col: list[str], progress: list[str]) -> str:
    rows = "".join(f"| {a} | {b} |\n".replace("|  |", "| |")
                   for a, b in zip_longest(next_col, progress, fillvalue=""))
    return ("# Board\n\nWhat comes next and what is in progress, across repos.\n\n"
            "| Next | In Progress |\n|---|---|\n" + rows)


def parse_board(text: str) -> tuple[list[str], list[str]]:
    """The two columns of the board table, top down, empty cells dropped."""
    nxt: list[str] = []
    prog: list[str] = []
    lines = iter(text.splitlines())
    for line in lines:
        if HEADER_RE.match(line):
            next(lines, None)  # separator
            break
    for line in lines:
        if not line.startswith("|"):
            break
        cells = [c.strip() for c in CELL_SPLIT_RE.split(line.strip())[1:-1]]
        if len(cells) != 2:
            raise AssertionError(f"board row with {len(cells)} cells: {line}")
        if cells[0]:
            nxt.append(cells[0])
        if cells[1]:
            prog.append(cells[1])
    return nxt, prog


def ids(cells: list[str]) -> list[str]:
    return [CARD_ID_RE.match(c).group(1) for c in cells]
