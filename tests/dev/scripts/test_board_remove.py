"""The board script's `drop` and `close`, exercised against small boards under `tmp_path`.

`scripts/board.py` owns every edit of the Kanban board (XAS-060): a drop and a
close remove a card from either column, pack the columns and keep every other
byte of the file. Expectations here are literal board text, written by hand,
never computed by the script under test.
"""
from __future__ import annotations

from pathlib import Path

import board

WEB = "https://example.com/team/demo"
DOCS = f"{WEB}/src/branch/develop/docs/backlog"
JIRA = "https://jira.example.com"

REGISTRY = (
    "# Repositories\n\n"
    "| Repo | Remote | IDs | What it is |\n|---|---|---|---|\n"
    f"| [demo]({WEB}) | `git@example.com:team/demo.git` | DEMO | Demo service |\n\n"
    "| Jira project | Site | Key | What it is |\n|---|---|---|---|\n"
    f"| [ops]({JIRA}/projects/OPS) | {JIRA} | OPS | Ops team |\n"
)

INTRO = "# Board\n\nWhat comes next and what is in progress, across repos.\n\n"
HEAD = "| Next | In Progress |\n|---|---|\n"

A = f"[DEMO-001]({DOCS}/demo-001.md) · [demo]({WEB}) — Alpha"
B = f"[DEMO-002]({DOCS}/demo-002.md) · [demo]({WEB}) — Beta · before the export"
C = f"[DEMO-003]({DOCS}/demo-003.md) · [demo]({WEB}) — Gamma"
X = f"[DEMO-004]({DOCS}/demo-004.md) · [demo]({WEB}) — Xi"
Y = f"[DEMO-005]({DOCS}/demo-005.md) · [demo]({WEB}) — Upsilon · later"
OPS = f"[OPS-043]({JIRA}/browse/OPS-043) · [ops]({JIRA}/projects/OPS) — Renew the certificate"


def setup(tmp_path: Path, text: str, newline: str = "\n") -> tuple[Path, Path]:
    """Write a board and the registry under *tmp_path*; return (board, registry)."""
    b = tmp_path / "board.md"
    r = tmp_path / "repos.md"
    b.write_bytes(text.replace("\n", newline).encode("utf-8"))
    r.write_bytes(REGISTRY.encode("utf-8"))
    return b, r


def run(b: Path, r: Path, *args: str) -> int:
    return board.main(["--board", str(b), "--registry", str(r), *args])


def test_drop_removes_a_card_from_next_and_packs_the_column(tmp_path, capsys):
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | {X} |\n| {B} | |\n| {C} | |\n")

    code = run(b, r, "drop", "demo", "DEMO-002")

    assert code == 0
    assert b.read_bytes().decode("utf-8") == INTRO + HEAD + f"| {A} | {X} |\n| {C} | |\n"
    assert capsys.readouterr().out.startswith("changed:")


def test_drop_removes_a_card_from_in_progress_and_drops_an_empty_row(tmp_path, capsys):
    text = INTRO + HEAD + f"| {A} | {X} |\n| | {Y} |\n"
    b, r = setup(tmp_path, text)

    code = run(b, r, "drop", "demo", "DEMO-005")

    assert code == 0
    assert b.read_bytes().decode("utf-8") == INTRO + HEAD + f"| {A} | {X} |\n"
    assert capsys.readouterr().out.startswith("changed:")

    # Dropping the upper card closes the gap: the lower one moves up.
    b, r = setup(tmp_path, text)

    code = run(b, r, "drop", "demo", "DEMO-004")

    assert code == 0
    assert b.read_bytes().decode("utf-8") == INTRO + HEAD + f"| {A} | {Y} |\n"


def test_drop_of_a_card_not_on_the_board_changes_nothing(tmp_path, capsys):
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | {X} |\n| {C} | |\n")
    before = b.read_bytes()

    code = run(b, r, "drop", "demo", "DEMO-099")

    assert code == 0
    assert b.read_bytes() == before
    out = capsys.readouterr().out
    assert out.startswith("unchanged:")
    assert "title:" not in out


def test_drop_keeps_every_other_card_byte_for_byte(tmp_path):
    odd = f"[DEMO-006]({DOCS}/demo-006.md?ref=a&b=c#top) · [demo]({WEB}?x=1&y=2) — Two  spaces   and a `code`  tail"
    other = f"[DEMO-007]({DOCS}/demo-007.md) · [demo]({WEB}) —  leading space ·  odd · reason"
    b, r = setup(tmp_path, INTRO + HEAD + f"| {odd} | {other} |\n| {A} | |\n| {C} | |\n")

    code = run(b, r, "drop", "demo", "DEMO-001")

    assert code == 0
    assert b.read_bytes().decode("utf-8") == INTRO + HEAD + f"| {odd} | {other} |\n| {C} | |\n"


def test_drop_keeps_a_card_with_an_escaped_pipe(tmp_path):
    piped = f"[DEMO-008]({DOCS}/demo-008.md) · [demo]({WEB}) — Read \\| write split · a \\| b"
    b, r = setup(tmp_path, INTRO + HEAD + f"| {piped} | {X} |\n| {A} | |\n")

    code = run(b, r, "drop", "demo", "DEMO-001")

    assert code == 0
    assert b.read_bytes().decode("utf-8") == INTRO + HEAD + f"| {piped} | {X} |\n"


def test_drop_keeps_everything_outside_the_table(tmp_path):
    below = (
        "\nA paragraph below the board, with a | pipe and a trailing space. \n\n"
        "## Archive\n\n"
        "| Other | Table |\n|---|---|\n"
        f"| {B} | {Y} |\n"
    )
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | {X} |\n| {C} | |\n" + below)

    code = run(b, r, "drop", "demo", "DEMO-003")

    assert code == 0
    assert b.read_bytes().decode("utf-8") == INTRO + HEAD + f"| {A} | {X} |\n" + below


def test_drop_keeps_crlf(tmp_path):
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | {X} |\n| {B} | {Y} |\n| {C} | |\n", newline="\r\n")

    code = run(b, r, "drop", "demo", "DEMO-005")

    assert code == 0
    assert b.read_bytes() == (
        "# Board\r\n\r\nWhat comes next and what is in progress, across repos.\r\n\r\n"
        "| Next | In Progress |\r\n|---|---|\r\n"
        f"| {A} | {X} |\r\n| {B} | |\r\n| {C} | |\r\n"
    ).encode("utf-8")


def test_drop_last_card_keeps_header_and_separator(tmp_path):
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | |\n")

    code = run(b, r, "drop", "demo", "DEMO-001")

    assert code == 0
    assert b.read_bytes().decode("utf-8") == INTRO + HEAD


def test_close_removes_the_card_and_prints_its_title(tmp_path, capsys):
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | {X} |\n| {C} | |\n")

    code = run(b, r, "close", "demo", "DEMO-004")

    assert code == 0
    assert b.read_bytes().decode("utf-8") == INTRO + HEAD + f"| {A} | |\n| {C} | |\n"
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("changed:")
    assert lines[1] == "title: Xi"


def test_close_without_a_card_changes_nothing(tmp_path, capsys):
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | {X} |\n")
    before = b.read_bytes()

    code = run(b, r, "close", "demo", "DEMO-099")

    assert code == 0
    assert b.read_bytes() == before
    out = capsys.readouterr().out
    assert out.startswith("unchanged:")
    assert "title:" not in out


def test_close_of_a_card_with_a_reason_prints_the_title_without_it(tmp_path, capsys):
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | {X} |\n| {B} | |\n")

    code = run(b, r, "close", "demo", "DEMO-002")

    assert code == 0
    assert b.read_bytes().decode("utf-8") == INTRO + HEAD + f"| {A} | {X} |\n"
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 2
    assert lines[0].startswith("changed:")
    assert lines[1] == "title: Beta"


def test_close_of_a_card_with_an_escaped_pipe_prints_the_title_unescaped(tmp_path, capsys):
    piped = f"[DEMO-008]({DOCS}/demo-008.md) · [demo]({WEB}) — A \\| B"
    b, r = setup(tmp_path, INTRO + HEAD + f"| {piped} | {X} |\n")

    code = run(b, r, "close", "demo", "DEMO-008")

    assert code == 0
    assert b.read_bytes().decode("utf-8") == INTRO + HEAD + f"| | {X} |\n"
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("changed:")
    assert lines[1] == "title: A | B"


def test_drop_prints_the_card_title(tmp_path, capsys):
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | {X} |\n")

    code = run(b, r, "drop", "demo", "DEMO-001")

    assert code == 0
    assert b.read_bytes().decode("utf-8") == INTRO + HEAD + f"| | {X} |\n"
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("changed:")
    assert lines[1] == "title: Alpha"


def test_close_of_a_jira_card_removes_it_as_written(tmp_path, capsys):
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | {OPS} |\n")

    code = run(b, r, "close", "ops", "OPS-043")

    assert code == 0
    assert b.read_bytes().decode("utf-8") == INTRO + HEAD + f"| {A} | |\n"
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("changed:")
    assert lines[1] == "title: Renew the certificate"


def test_unknown_repo_is_refused(tmp_path, capsys):
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | {X} |\n")
    before = b.read_bytes()

    code = run(b, r, "drop", "nowhere", "DEMO-001")

    assert code == 1
    assert b.read_bytes() == before
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("board: ")
    assert len(captured.err.splitlines()) == 1


def test_board_without_the_table_is_refused(tmp_path, capsys):
    b, r = setup(tmp_path, "# Board\n\nNothing here yet.\n\n| Todo | Doing |\n|---|---|\n| a | b |\n")
    before = b.read_bytes()

    code = run(b, r, "drop", "demo", "DEMO-001")

    assert code == 1
    assert b.read_bytes() == before
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("board: ")
    assert len(captured.err.splitlines()) == 1


def test_a_registry_table_with_another_header_is_not_read_as_repos(tmp_path, capsys):
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | {X} |\n")
    r.write_bytes(
        (
            REGISTRY
            + "\n| Repo | Gate | Runs in |\n|---|---|---|\n"
            + "| [other](https://example.com/team/other) | `make check` | container |\n"
        ).encode("utf-8")
    )
    before = b.read_bytes()

    code = run(b, r, "drop", "other", "DEMO-001")

    assert code == 1
    assert b.read_bytes() == before
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("board: ")
    assert len(captured.err.splitlines()) == 1

    code = run(b, r, "drop", "demo", "DEMO-001")

    assert code == 0
    assert b.read_bytes().decode("utf-8") == INTRO + HEAD + f"| | {X} |\n"


def test_a_missing_board_file_is_refused(tmp_path, capsys):
    _, r = setup(tmp_path, INTRO + HEAD)
    missing = tmp_path / "nowhere" / "board.md"

    code = run(missing, r, "drop", "demo", "DEMO-001")

    assert code == 1
    assert not missing.exists()
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("board: ")
    assert len(captured.err.splitlines()) == 1
    assert "Traceback" not in captured.err


def test_a_missing_registry_file_is_refused(tmp_path, capsys):
    b, _ = setup(tmp_path, INTRO + HEAD + f"| {A} | {X} |\n")
    missing = tmp_path / "nowhere" / "repos.md"
    before = b.read_bytes()

    code = run(b, missing, "drop", "demo", "DEMO-001")

    assert code == 1
    assert b.read_bytes() == before
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("board: ")
    assert len(captured.err.splitlines()) == 1
    assert "Traceback" not in captured.err


def test_close_of_a_lowercase_id_removes_the_card(tmp_path, capsys):
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | {X} |\n| {C} | |\n")

    code = run(b, r, "close", "demo", "demo-004")

    assert code == 0
    assert b.read_bytes().decode("utf-8") == INTRO + HEAD + f"| {A} | |\n| {C} | |\n"
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("changed:")
    assert lines[1] == "title: Xi"


def test_a_board_row_with_three_cells_is_refused(tmp_path, capsys):
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | {X} | stray |\n| {C} | |\n")
    before = b.read_bytes()

    code = run(b, r, "drop", "demo", "DEMO-001")

    assert code == 1
    assert b.read_bytes() == before
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("board: ")
    assert len(captured.err.splitlines()) == 1

    # The same board with two cells per row succeeds.
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | {X} |\n| {C} | |\n")

    assert run(b, r, "drop", "demo", "DEMO-001") == 0
    assert b.read_bytes().decode("utf-8") == INTRO + HEAD + f"| {C} | {X} |\n"
