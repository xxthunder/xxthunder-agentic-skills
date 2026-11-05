"""The board script's `put`, exercised against small boards and backlogs under `tmp_path`.

`scripts/board.py` owns every edit of the Kanban board (XAS-060): a put places
or moves an item's card in *Next*, reading the item's title and the link's
branch fresh from the backlog. Expectations here are literal board text,
written by hand, never computed by the script under test.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import board

WEB = "https://example.com/team/demo"
DOCS = f"{WEB}/src/branch/develop/docs/backlog"
GITHUB_WEB = "https://github.com/team/demo"
BITBUCKET_WEB = "https://bitbucket.example.com/projects/TEAM/repos/demo"

REGISTRY_HEAD = "# Repositories\n\n| Repo | Remote | IDs | What it is |\n|---|---|---|---|\n"
REGISTRY = REGISTRY_HEAD + f"| [demo]({WEB}) | `git@example.com:team/demo.git` | DEMO | Demo service |\n"

INTRO = "# Board\n\nWhat comes next and what is in progress, across repos.\n\n"
HEAD = "| Next | In Progress |\n|---|---|\n"

A = f"[DEMO-001]({DOCS}/demo-001.md) · [demo]({WEB}) — Alpha"
B = f"[DEMO-002]({DOCS}/demo-002.md) · [demo]({WEB}) — Beta · before the export"
C = f"[DEMO-003]({DOCS}/demo-003.md) · [demo]({WEB}) — Gamma"
X = f"[DEMO-004]({DOCS}/demo-004.md) · [demo]({WEB}) — Xi"
N = f"[DEMO-007]({DOCS}/demo-007.md) · [demo]({WEB}) — Health endpoint"

ITEMS = [
    ("DEMO-004", "Xi"),
    ("DEMO-007", "Health endpoint"),
]


def git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "-c", "commit.gpgsign=false", *args],
        cwd=cwd, capture_output=True, check=True,
    )
    return result.stdout.decode("utf-8")


def write_backlog(repo: Path, items) -> Path:
    """Write items as (id, title) under *repo*/docs/backlog with a README that names the ID prefix."""
    b = repo / "docs" / "backlog"
    b.mkdir(parents=True, exist_ok=True)
    for iid, title in items:
        text = f"# [{iid}] {title}\n\n**Status**: Open\n**Priority**: Medium\n\nBody.\n"
        (b / f"{iid.lower()}.md").write_text(text, encoding="utf-8", newline="\n")
    readme = "# Backlog\n\nIntro.\n\n## Table of Contents\n\n### Open\n\n---\n\n## Notes\n\n- **ID prefix**: `DEMO` (demo)\n"
    (b / "README.md").write_text(readme, encoding="utf-8", newline="\n")
    return b


def make_backlog(tmp_path: Path, items=ITEMS) -> Path:
    """A backlog in a git repo on branch `develop` without an origin; return the backlog directory."""
    repo = tmp_path / "demo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "develop")
    b = write_backlog(repo, items)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "items")
    return b


def setup(tmp_path: Path, text: str, registry: str = REGISTRY) -> tuple[Path, Path]:
    """Write a board and the registry under *tmp_path*; return (board, registry)."""
    b = tmp_path / "board.md"
    r = tmp_path / "repos.md"
    b.write_bytes(text.encode("utf-8"))
    r.write_bytes(registry.encode("utf-8"))
    return b, r


def put(b: Path, r: Path, backlog_dir: Path, *args: str, item: str = "DEMO-007") -> int:
    return board.main(["--board", str(b), "--registry", str(r), "put", "demo", item, "--dir", str(backlog_dir), *args])


def read(b: Path) -> str:
    return b.read_bytes().decode("utf-8")


def assert_refused(code: int, capsys, b: Path, before: bytes) -> None:
    assert code == 1
    assert b.read_bytes() == before
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("board: ")
    assert len(captured.err.splitlines()) == 1


def assert_put_works(b: Path, r: Path, backlog_dir: Path) -> None:
    """A plain put on the same board succeeds: the refusal above came from the check, not from a missing command."""
    assert put(b, r, backlog_dir) == 0
    assert "— Health endpoint" in read(b)


def test_put_without_position_places_a_new_card_on_top_of_next(tmp_path):
    backlog_dir = make_backlog(tmp_path)
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | {X} |\n| {B} | |\n")

    code = put(b, r, backlog_dir)

    assert code == 0
    assert read(b) == INTRO + HEAD + f"| {N} | {X} |\n| {A} | |\n| {B} | |\n"


def test_put_at_a_position(tmp_path):
    backlog_dir = make_backlog(tmp_path)
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | |\n| {B} | |\n| {C} | |\n")

    code = put(b, r, backlog_dir, "--at", "2")

    assert code == 0
    assert read(b) == INTRO + HEAD + f"| {A} | |\n| {N} | |\n| {B} | |\n| {C} | |\n"


def test_put_at_beyond_the_end_appends(tmp_path):
    backlog_dir = make_backlog(tmp_path)
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | {X} |\n| {B} | |\n")

    code = put(b, r, backlog_dir, "--at", "99")

    assert code == 0
    assert read(b) == INTRO + HEAD + f"| {A} | {X} |\n| {B} | |\n| {N} | |\n"


def test_put_after_a_card(tmp_path):
    backlog_dir = make_backlog(tmp_path)
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | |\n| {B} | |\n| {C} | |\n")

    code = put(b, r, backlog_dir, "--after", "DEMO-002")

    assert code == 0
    assert read(b) == INTRO + HEAD + f"| {A} | |\n| {B} | |\n| {N} | |\n| {C} | |\n"


def test_put_after_a_card_not_in_next_is_refused(tmp_path, capsys):
    backlog_dir = make_backlog(tmp_path)
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | {X} |\n| {B} | |\n")
    before = b.read_bytes()

    # A card in In Progress is not a place in Next.
    code = put(b, r, backlog_dir, "--after", "DEMO-004")

    assert_refused(code, capsys, b, before)

    # Neither is a card that is not on the board at all.
    code = put(b, r, backlog_dir, "--after", "DEMO-099")

    assert_refused(code, capsys, b, before)
    assert_put_works(b, r, backlog_dir)


def test_put_at_below_one_is_refused(tmp_path, capsys):
    backlog_dir = make_backlog(tmp_path)
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | |\n")
    before = b.read_bytes()

    code = put(b, r, backlog_dir, "--at", "0")

    assert_refused(code, capsys, b, before)
    assert_put_works(b, r, backlog_dir)


def test_put_moves_a_card_already_in_next(tmp_path):
    backlog_dir = make_backlog(tmp_path)
    text = INTRO + HEAD + f"| {A} | {X} |\n| {B} | |\n| {N} | |\n| {C} | |\n"
    b, r = setup(tmp_path, text)

    # Up: the old place closes, the card lands at the top.
    code = put(b, r, backlog_dir, "--at", "1")

    assert code == 0
    assert read(b) == INTRO + HEAD + f"| {N} | {X} |\n| {A} | |\n| {B} | |\n| {C} | |\n"

    # Down: the card lands after another one, and the gap it left closes.
    b, r = setup(tmp_path, text)

    code = put(b, r, backlog_dir, "--after", "DEMO-003")

    assert code == 0
    assert read(b) == INTRO + HEAD + f"| {A} | {X} |\n| {B} | |\n| {C} | |\n| {N} | |\n"

    # Its position in the new order counts, not the one it had.
    b, r = setup(tmp_path, INTRO + HEAD + f"| {N} | |\n| {A} | |\n| {B} | |\n")

    code = put(b, r, backlog_dir, "--at", "2")

    assert code == 0
    assert read(b) == INTRO + HEAD + f"| {A} | |\n| {N} | |\n| {B} | |\n"


def test_put_moves_a_card_refreshes_a_drifted_title_and_keeps_its_reason(tmp_path):
    backlog_dir = make_backlog(tmp_path)
    drifted = f"[DEMO-007]({DOCS}/demo-007.md) · [demo]({WEB}) — Old · name · before the release"
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | |\n| {drifted} | |\n| {C} | |\n")

    code = put(b, r, backlog_dir, "--at", "1")

    assert code == 0
    assert read(b) == INTRO + HEAD + (
        f"| {N} · before the release | |\n| {A} | |\n| {C} | |\n"
    )


def test_put_to_the_place_it_already_has_changes_nothing(tmp_path, capsys):
    backlog_dir = make_backlog(tmp_path)
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | {X} |\n| {N} · later | |\n| {C} | |\n")
    before = b.read_bytes()

    code = put(b, r, backlog_dir, "--at", "2")

    assert code == 0
    assert b.read_bytes() == before
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("unchanged:")
    assert lines[1] == "title: Health endpoint"


def test_put_with_a_reason_writes_it(tmp_path):
    backlog_dir = make_backlog(tmp_path)
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | |\n")

    code = put(b, r, backlog_dir, "--reason", "before the export")

    assert code == 0
    assert read(b) == INTRO + HEAD + f"| {N} · before the export | |\n| {A} | |\n"


def test_put_escapes_a_pipe_in_the_title(tmp_path, capsys):
    backlog_dir = make_backlog(tmp_path, [("DEMO-007", "Read | write split")])
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | |\n")

    code = put(b, r, backlog_dir, "--reason", "a | b")

    assert code == 0
    assert read(b) == INTRO + HEAD + (
        f"| [DEMO-007]({DOCS}/demo-007.md) · [demo]({WEB}) — Read \\| write split · a \\| b | |\n"
        f"| {A} | |\n"
    )
    assert capsys.readouterr().out.splitlines()[1] == "title: Read | write split"


def test_put_of_a_card_in_progress_is_refused(tmp_path, capsys):
    backlog_dir = make_backlog(tmp_path)
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | {X} |\n")
    before = b.read_bytes()

    code = put(b, r, backlog_dir, item="DEMO-004")

    assert_refused(code, capsys, b, before)
    assert_put_works(b, r, backlog_dir)


def test_put_of_an_unknown_item_is_refused(tmp_path, capsys):
    backlog_dir = make_backlog(tmp_path)
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | {X} |\n")
    before = b.read_bytes()

    code = put(b, r, backlog_dir, item="DEMO-099")

    assert_refused(code, capsys, b, before)
    assert_put_works(b, r, backlog_dir)


def test_put_reads_the_title_and_branch_from_the_remote_default_branch(tmp_path, capsys):
    bare = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", "-b", "trunk", str(bare))
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    git(upstream, "init", "-q", "-b", "trunk")
    git(upstream, "remote", "add", "origin", str(bare))
    write_backlog(upstream, ITEMS)
    git(upstream, "add", "-A")
    git(upstream, "commit", "-q", "-m", "items")
    git(upstream, "push", "-q", "origin", "HEAD")
    git(tmp_path, "clone", "-q", str(bare), "checkout")
    checkout = tmp_path / "checkout"
    # The checkout sits on a feature branch with a stale title; only trunk has the fresh one.
    git(checkout, "switch", "-q", "-c", "feature")
    write_backlog(checkout, [("DEMO-007", "Stale on feature")])
    git(checkout, "add", "-A")
    git(checkout, "commit", "-q", "-m", "stale")
    write_backlog(upstream, [("DEMO-007", "Fresh on trunk")])
    git(upstream, "add", "-A")
    git(upstream, "commit", "-q", "-m", "retitle")
    git(upstream, "push", "-q", "origin", "HEAD")
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | |\n")

    code = board.main(["--board", str(b), "--registry", str(r), "put", "demo", "DEMO-007", "--repo", str(checkout)])

    assert code == 0
    assert read(b) == INTRO + HEAD + (
        f"| [DEMO-007]({WEB}/src/branch/trunk/docs/backlog/demo-007.md) · [demo]({WEB}) — Fresh on trunk | |\n"
        f"| [DEMO-001]({DOCS}/demo-001.md) · [demo]({WEB}) — Alpha | |\n"
    )
    assert capsys.readouterr().out.splitlines()[1] == "title: Fresh on trunk"


def test_put_link_on_github_uses_blob(tmp_path):
    backlog_dir = make_backlog(tmp_path)
    registry = REGISTRY_HEAD + f"| [demo]({GITHUB_WEB}) | `git@github.com:team/demo.git` | DEMO | Demo service |\n"
    b, r = setup(tmp_path, INTRO + HEAD, registry)

    code = put(b, r, backlog_dir)

    assert code == 0
    assert read(b) == INTRO + HEAD + (
        f"| [DEMO-007]({GITHUB_WEB}/blob/develop/docs/backlog/demo-007.md) · [demo]({GITHUB_WEB}) — Health endpoint | |\n"
    )


def test_put_link_on_bitbucket_server_uses_browse(tmp_path):
    backlog_dir = make_backlog(tmp_path)
    registry = (
        REGISTRY_HEAD
        + f"| [demo]({BITBUCKET_WEB}) | `ssh://git@bitbucket.example.com:7999/team/demo.git` | DEMO | Demo service |\n"
    )
    b, r = setup(tmp_path, INTRO + HEAD, registry)

    code = put(b, r, backlog_dir)

    assert code == 0
    assert read(b) == INTRO + HEAD + (
        f"| [DEMO-007]({BITBUCKET_WEB}/browse/docs/backlog/demo-007.md) · [demo]({BITBUCKET_WEB}) — Health endpoint | |\n"
    )


def test_put_prints_changed_and_the_fresh_title(tmp_path, capsys):
    backlog_dir = make_backlog(tmp_path)
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | |\n")

    code = put(b, r, backlog_dir)

    assert code == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 2
    assert lines[0].startswith("changed:")
    assert lines[1] == "title: Health endpoint"


def test_put_of_a_lowercase_id_moves_the_existing_card(tmp_path):
    backlog_dir = make_backlog(tmp_path, [("DEMO-002", "Beta")])
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | |\n| {B} | |\n")

    code = put(b, r, backlog_dir, "--at", "1", item="demo-002")

    assert code == 0
    assert read(b) == INTRO + HEAD + f"| {B} | |\n| {A} | |\n"


def test_put_of_a_lowercase_id_of_a_card_in_progress_is_refused(tmp_path, capsys):
    backlog_dir = make_backlog(tmp_path)
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | {X} |\n")
    before = b.read_bytes()

    code = put(b, r, backlog_dir, item="demo-004")

    assert_refused(code, capsys, b, before)
    assert_put_works(b, r, backlog_dir)


def test_put_of_a_lowercase_id_writes_the_heading_id(tmp_path):
    backlog_dir = make_backlog(tmp_path)
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | |\n")

    code = put(b, r, backlog_dir, item="demo-007")

    assert code == 0
    assert read(b) == INTRO + HEAD + f"| {N} | |\n| {A} | |\n"


def test_put_needs_dir_or_repo_for_an_item(tmp_path, capsys):
    backlog_dir = make_backlog(tmp_path)
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | |\n")
    before = b.read_bytes()

    code = board.main(["--board", str(b), "--registry", str(r), "put", "demo", "DEMO-007"])

    assert_refused(code, capsys, b, before)
    assert_put_works(b, r, backlog_dir)


def test_put_with_a_detached_head_and_no_origin_head_is_refused(tmp_path, capsys):
    backlog_dir = make_backlog(tmp_path)
    repo = backlog_dir.parents[1]
    git(repo, "checkout", "-q", "--detach")
    b, r = setup(tmp_path, INTRO + HEAD + f"| {A} | |\n")
    before = b.read_bytes()

    # Without a remote and on no branch, the link has no branch to name.
    code = put(b, r, backlog_dir)

    assert_refused(code, capsys, b, before)

    git(repo, "checkout", "-q", "develop")
    assert_put_works(b, r, backlog_dir)
