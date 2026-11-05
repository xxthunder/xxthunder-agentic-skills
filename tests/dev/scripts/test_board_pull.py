"""The board script's `pull`, Jira cards and issue cards, exercised under `tmp_path`.

`scripts/board.py` owns every edit of the Kanban board (XAS-060): a pull moves
the card of an item that is work in progress to the top of *In Progress*, a
Jira card is made from a summary that comes in as an argument, and an issue
card (`#12`, a repo without a backlog) has no title. Expectations here are
literal board text, written by hand, never computed by the script under test.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import board

WEB = "https://example.com/team/demo"
OTHER_WEB = "https://example.com/team/other"
DOCS = f"{WEB}/src/branch/develop/docs/backlog"
JIRA = "https://jira.example.com"

REGISTRY = (
    "# Repositories\n\n"
    "| Repo | Remote | IDs | What it is |\n|---|---|---|---|\n"
    f"| [demo]({WEB}) | `git@example.com:team/demo.git` | DEMO | Demo service |\n"
    f"| [other]({OTHER_WEB}) | `git@example.com:team/other.git` | OTH | Other service |\n\n"
    "| Jira project | Site | Key | What it is |\n|---|---|---|---|\n"
    f"| [ops]({JIRA}/projects/OPS) | {JIRA} | OPS | Ops team |\n"
)

INTRO = "# Board\n\nWhat comes next and what is in progress, across repos.\n\n"
HEAD = "| Next | In Progress |\n|---|---|\n"

A = f"[DEMO-001]({DOCS}/demo-001.md) · [demo]({WEB}) — Alpha"
X = f"[DEMO-004]({DOCS}/demo-004.md) · [demo]({WEB}) — Xi"
N = f"[DEMO-007]({DOCS}/demo-007.md) · [demo]({WEB}) — Health endpoint"
OPS = f"[OPS-043]({JIRA}/browse/OPS-043) · [ops]({JIRA}/projects/OPS) — Renew the certificate"
ISSUE = f"[#12]({WEB}/issues/12) · [demo]({WEB})"
OTHER_ISSUE = f"[#12]({OTHER_WEB}/issues/12) · [other]({OTHER_WEB})"


def git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "-c", "commit.gpgsign=false", *args],
        cwd=cwd, capture_output=True, check=True,
    )
    return result.stdout.decode("utf-8")


def make_backlog(tmp_path: Path, items, substories=()) -> Path:
    """A backlog in a git repo on branch `develop` without an origin; return the backlog directory.

    *items* are (id, title, status); *substories* are file names such as `demo-004a.md`.
    """
    repo = tmp_path / "demo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "develop")
    b = repo / "docs" / "backlog"
    b.mkdir(parents=True)
    for iid, title, status in items:
        text = f"# [{iid}] {title}\n\n**Status**: {status}\n**Priority**: Medium\n\nBody.\n"
        (b / f"{iid.lower()}.md").write_text(text, encoding="utf-8", newline="\n")
    for name in substories:
        iid = name[:-3].upper()
        text = f"# [{iid}] Sub\n\n**Status**: In Progress\n**Priority**: Medium\n\nBody.\n"
        (b / name).write_text(text, encoding="utf-8", newline="\n")
    readme = "# Backlog\n\nIntro.\n\n## Table of Contents\n\n### Open\n\n---\n\n## Notes\n\n- **ID prefix**: `DEMO` (demo)\n"
    (b / "README.md").write_text(readme, encoding="utf-8", newline="\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "items")
    return b


def setup(tmp_path: Path, text: str) -> tuple[Path, Path]:
    """Write a board and the registry under *tmp_path*; return (board, registry)."""
    b = tmp_path / "board.md"
    r = tmp_path / "repos.md"
    b.write_bytes(text.encode("utf-8"))
    r.write_bytes(REGISTRY.encode("utf-8"))
    return b, r


def run(b: Path, r: Path, *args: str) -> int:
    return board.main(["--board", str(b), "--registry", str(r), *args])


def pull(b: Path, r: Path, backlog_dir: Path, item: str = "DEMO-007") -> int:
    return run(b, r, "pull", "demo", item, "--dir", str(backlog_dir))


def read(b: Path) -> str:
    return b.read_bytes().decode("utf-8")


def assert_refused(code: int, capsys, b: Path, before: bytes) -> None:
    assert code == 1
    assert b.read_bytes() == before
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("board: ")
    assert len(captured.err.splitlines()) == 1


def assert_jira_put_works(b: Path, r: Path) -> None:
    """A valid Jira put on the same board succeeds: the refusal above came from the check, not from a missing command."""
    assert run(b, r, "put", "ops", "OPS-043", "--title", "Renew the certificate") == 0
    assert "[OPS-043](" in read(b)


def test_pull_moves_a_card_from_next_to_the_top_of_in_progress(tmp_path, capsys):
    backlog_dir = make_backlog(tmp_path, [("DEMO-007", "Health endpoint", "In Progress")])
    stale = f"[DEMO-007]({DOCS}/demo-007.md) · [demo]({WEB}) — Old · name · before the export"
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | {X} |\n| {stale} | |\n")

    code = pull(b, r, backlog_dir)

    assert code == 0
    assert read(b) == INTRO + HEAD + f"| {A} | {N} · before the export |\n| | {X} |\n"
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("changed:")
    assert lines[1] == "title: Health endpoint"


def test_pull_without_a_card_makes_a_new_one_on_top_of_in_progress(tmp_path, capsys):
    backlog_dir = make_backlog(tmp_path, [("DEMO-007", "Health endpoint", "In Progress")])
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | {X} |\n")

    code = pull(b, r, backlog_dir)

    assert code == 0
    assert read(b) == INTRO + HEAD + f"| {A} | {N} |\n| | {X} |\n"
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("changed:")
    assert lines[1] == "title: Health endpoint"


def test_pull_of_a_card_already_in_progress_leaves_it_in_place(tmp_path, capsys):
    backlog_dir = make_backlog(tmp_path, [("DEMO-007", "Health endpoint", "In Progress")])
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | {X} |\n| | {N} · later |\n")
    before = b.read_bytes()

    code = pull(b, r, backlog_dir)

    assert code == 0
    assert b.read_bytes() == before
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("unchanged:")
    assert lines[1] == "title: Health endpoint"


def test_pull_refreshes_a_drifted_title_in_progress_in_place(tmp_path, capsys):
    backlog_dir = make_backlog(tmp_path, [("DEMO-007", "Health endpoint", "In Progress")])
    drifted = f"[DEMO-007]({DOCS}/demo-007.md) · [demo]({WEB}) — Old · name · later"
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | {X} |\n| | {drifted} |\n")

    code = pull(b, r, backlog_dir)

    assert code == 0
    # The card stays below DEMO-004; only its title is fresh, and the reason stays.
    assert read(b) == INTRO + HEAD + f"| {A} | {X} |\n| | {N} · later |\n"
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("changed:")
    assert lines[1] == "title: Health endpoint"


def test_pull_of_an_epic_makes_no_card(tmp_path, capsys):
    # DEMO-007 is In Progress only because its substory demo-007a is.
    backlog_dir = make_backlog(
        tmp_path, [("DEMO-007", "Health endpoint", "In Progress")], substories=["demo-007a.md"]
    )
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | {X} |\n")
    before = b.read_bytes()

    code = pull(b, r, backlog_dir)

    assert code == 0
    assert b.read_bytes() == before
    assert capsys.readouterr().out.splitlines()[0].startswith("unchanged:")


def test_pull_of_the_refinement_item_makes_no_card(tmp_path, capsys):
    backlog_dir = make_backlog(tmp_path, [("DEMO-007", "Backlog refinement", "In Progress")])
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | {X} |\n")
    before = b.read_bytes()

    code = pull(b, r, backlog_dir)

    assert code == 0
    assert b.read_bytes() == before
    assert capsys.readouterr().out.splitlines()[0].startswith("unchanged:")


def test_pull_of_an_item_not_in_progress_makes_no_card(tmp_path, capsys):
    backlog_dir = make_backlog(tmp_path, [("DEMO-007", "Health endpoint", "Open")])
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | {X} |\n")
    before = b.read_bytes()

    code = pull(b, r, backlog_dir)

    assert code == 0
    assert b.read_bytes() == before
    assert capsys.readouterr().out.splitlines()[0].startswith("unchanged:")


def test_put_of_a_jira_key_makes_a_card_from_the_given_summary(tmp_path, capsys):
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | {X} |\n")

    code = run(b, r, "put", "ops", "OPS-043", "--title", "Rotate the | certs")

    assert code == 0
    assert read(b) == INTRO + HEAD + (
        f"| [OPS-043]({JIRA}/browse/OPS-043) · [ops]({JIRA}/projects/OPS) — Rotate the \\| certs | {X} |\n"
        f"| {A} | |\n"
    )
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("changed:")
    assert lines[1] == "title: Rotate the | certs"

    # A reason follows the summary, its pipe escaped too.
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | |\n")

    code = run(b, r, "put", "ops", "OPS-043", "--title", "Renew", "--reason", "before | Q4")

    assert code == 0
    assert read(b) == INTRO + HEAD + (
        f"| [OPS-043]({JIRA}/browse/OPS-043) · [ops]({JIRA}/projects/OPS) — Renew · before \\| Q4 | |\n"
        f"| {A} | |\n"
    )


def test_put_of_a_jira_key_without_title_and_card_is_refused(tmp_path, capsys):
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | {X} |\n")
    before = b.read_bytes()

    code = run(b, r, "put", "ops", "OPS-043")

    assert_refused(code, capsys, b, before)
    assert_jira_put_works(b, r)


def test_put_moves_a_jira_card_as_written_without_a_title(tmp_path, capsys):
    written = f"{OPS} · before Q4"
    text = INTRO + HEAD + f"| {A} | |\n| {written} | |\n"
    b, r = setup(tmp_path, text)

    code = run(b, r, "put", "ops", "OPS-043", "--at", "1")

    assert code == 0
    assert read(b) == INTRO + HEAD + f"| {written} | |\n| {A} | |\n"
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("changed:")
    assert lines[1] == "title: Renew the certificate"

    # A given --title is not used: the card is a snapshot.
    b, r = setup(tmp_path, text)

    code = run(b, r, "put", "ops", "OPS-043", "--at", "1", "--title", "Something else")

    assert code == 0
    assert read(b) == INTRO + HEAD + f"| {written} | |\n| {A} | |\n"
    assert capsys.readouterr().out.splitlines()[1] == "title: Renew the certificate"


def test_title_on_a_non_jira_address_is_refused(tmp_path, capsys):
    backlog_dir = make_backlog(tmp_path, [("DEMO-007", "Health endpoint", "Open")])
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | {X} |\n")
    before = b.read_bytes()

    # An item ID takes its title from the item.
    code = run(b, r, "put", "demo", "DEMO-007", "--dir", str(backlog_dir), "--title", "Mine")

    assert_refused(code, capsys, b, before)

    # An issue has no title at all.
    code = run(b, r, "put", "demo", "#12", "--title", "Mine")

    assert_refused(code, capsys, b, before)

    # The same puts without --title succeed.
    assert run(b, r, "put", "demo", "DEMO-007", "--dir", str(backlog_dir)) == 0
    assert "— Health endpoint" in read(b)
    assert run(b, r, "put", "demo", "#12") == 0
    assert "[#12](" in read(b)


def test_pull_moves_a_jira_card_as_written(tmp_path, capsys):
    written = f"{OPS} · before Q4"
    b, r = setup(tmp_path, INTRO + HEAD + f"| {written} | {X} |\n| {A} | |\n")

    code = run(b, r, "pull", "ops", "OPS-043")

    assert code == 0
    assert read(b) == INTRO + HEAD + f"| {A} | {written} |\n| | {X} |\n"
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("changed:")
    assert lines[1] == "title: Renew the certificate"


def test_pull_of_a_jira_key_without_a_card_changes_nothing(tmp_path, capsys):
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | {X} |\n")
    before = b.read_bytes()

    code = run(b, r, "pull", "ops", "OPS-043")

    assert code == 0
    assert b.read_bytes() == before
    out = capsys.readouterr().out
    assert out.splitlines()[0].startswith("unchanged:")
    assert "put it on the board first" in out


def test_put_of_an_issue_makes_an_issue_card(tmp_path, capsys):
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | {X} |\n")

    code = run(b, r, "put", "demo", "#12", "--reason", "before the export")

    assert code == 0
    assert read(b) == INTRO + HEAD + f"| {ISSUE} · before the export | {X} |\n| {A} | |\n"
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("changed:")
    assert not any(line.startswith("title:") for line in lines)


def test_drop_of_an_issue_card_matches_repo_and_number(tmp_path, capsys):
    b, r = setup(tmp_path, INTRO + HEAD + f"| {ISSUE} · now | {X} |\n| {OTHER_ISSUE} | |\n| {A} | |\n")

    code = run(b, r, "drop", "demo", "#12")

    assert code == 0
    assert read(b) == INTRO + HEAD + f"| {OTHER_ISSUE} | {X} |\n| {A} | |\n"
    assert capsys.readouterr().out.splitlines()[0].startswith("changed:")

    # The other repo's card answers to its own repo name.
    code = run(b, r, "drop", "other", "#12")

    assert code == 0
    assert read(b) == INTRO + HEAD + f"| {A} | {X} |\n"


def test_put_with_a_reason_replaces_the_reason_of_an_existing_jira_card(tmp_path, capsys):
    card = f"[OPS-043]({JIRA}/browse/OPS-043) · [ops]({JIRA}/projects/OPS) — Renew"
    b, r = setup(tmp_path, INTRO + HEAD + f"| {card} · old reason | |\n| {A} | |\n")

    code = run(b, r, "put", "ops", "OPS-043", "--reason", "new reason")

    assert code == 0
    assert read(b) == INTRO + HEAD + f"| {card} · new reason | |\n| {A} | |\n"
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("changed:")
    assert lines[1] == "title: Renew"


def test_pull_of_an_issue_without_a_card_makes_one_on_top_of_in_progress(tmp_path, capsys):
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | {X} |\n")

    code = run(b, r, "pull", "demo", "#12")

    assert code == 0
    assert read(b) == INTRO + HEAD + f"| {A} | {ISSUE} |\n| | {X} |\n"
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("changed:")
    assert not any(line.startswith("title:") for line in lines)


def test_pull_moves_an_issue_card_from_next_and_keeps_its_reason(tmp_path, capsys):
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | {X} |\n| {ISSUE} · before the release | |\n")

    code = run(b, r, "pull", "demo", "#12")

    assert code == 0
    assert read(b) == INTRO + HEAD + f"| {A} | {ISSUE} · before the release |\n| | {X} |\n"
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("changed:")
    assert not any(line.startswith("title:") for line in lines)


def test_put_moves_an_issue_card_and_keeps_its_reason(tmp_path, capsys):
    b, r = setup(tmp_path, INTRO + HEAD + f"| {ISSUE} · before the release | |\n| {A} | |\n")

    code = run(b, r, "put", "demo", "#12", "--at", "2")

    assert code == 0
    assert read(b) == INTRO + HEAD + f"| {A} | |\n| {ISSUE} · before the release | |\n"
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("changed:")
    assert not any(line.startswith("title:") for line in lines)


def test_a_malformed_issue_number_is_refused(tmp_path, capsys):
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | {X} |\n")
    before = b.read_bytes()

    code = run(b, r, "put", "demo", "#abc")

    assert_refused(code, capsys, b, before)

    # A well-formed number on the same board succeeds.
    assert run(b, r, "put", "demo", "#12") == 0
    assert "[#12](" in read(b)


def test_pull_of_a_jira_card_already_in_progress_leaves_it_in_place(tmp_path, capsys):
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | {X} |\n| | {OPS} · before Q4 |\n")
    before = b.read_bytes()

    code = run(b, r, "pull", "ops", "OPS-043")

    assert code == 0
    assert b.read_bytes() == before
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("unchanged:")
    assert lines[1] == "title: Renew the certificate"


def test_a_jira_address_needs_a_key_of_its_project(tmp_path, capsys):
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | {X} |\n")
    before = b.read_bytes()

    # An issue number is not a key of the Jira project.
    code = run(b, r, "put", "ops", "#12", "--title", "X")

    assert_refused(code, capsys, b, before)

    # Neither is a key of another project.
    code = run(b, r, "put", "ops", "FOO-001", "--title", "X")

    assert_refused(code, capsys, b, before)

    # A key of the project on the same board succeeds.
    assert run(b, r, "put", "ops", "OPS-050", "--title", "X") == 0
    assert "[OPS-050](" in read(b)


def test_pull_of_an_item_not_in_progress_leaves_its_card_in_next(tmp_path, capsys):
    backlog_dir = make_backlog(tmp_path, [("DEMO-007", "Health endpoint", "Open")])
    b, r = setup(tmp_path, INTRO + HEAD + f"| {N} · soon | {X} |\n")
    before = b.read_bytes()

    code = pull(b, r, backlog_dir)

    assert code == 0
    assert b.read_bytes() == before
    assert capsys.readouterr().out.splitlines()[0].startswith("unchanged:")


def test_pull_of_a_lowercase_id_moves_the_existing_card(tmp_path, capsys):
    backlog_dir = make_backlog(tmp_path, [("DEMO-007", "Health endpoint", "In Progress")])
    stale = f"[DEMO-007]({DOCS}/demo-007.md) · [demo]({WEB}) — Old · name · before the export"
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | {X} |\n| {stale} | |\n")

    code = pull(b, r, backlog_dir, "demo-007")

    assert code == 0
    assert read(b) == INTRO + HEAD + f"| {A} | {N} · before the export |\n| | {X} |\n"
    assert capsys.readouterr().out.splitlines()[1] == "title: Health endpoint"


def test_put_of_a_new_jira_card_without_title_names_the_flag(tmp_path, capsys):
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | {X} |\n")
    before = b.read_bytes()

    code = run(b, r, "put", "ops", "OPS-043")

    assert code == 1
    assert b.read_bytes() == before
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "board: OPS-043 has no card: give its summary with --title\n"
    assert_jira_put_works(b, r)
