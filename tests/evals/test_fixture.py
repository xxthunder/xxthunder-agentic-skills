"""The sandbox a case runs in, built from real git repos with local bare remotes."""
from __future__ import annotations

import pytest

from evals.board import BOARD_FILE, ids
from evals.fixture import (
    INITIAL_NEXT,
    INITIAL_PROGRESS,
    build,
    display_id,
    sandbox_contract,
    snapshot,
)


def test_display_id_keeps_the_substory_letter_lowercase():
    assert display_id("demo-004a") == "DEMO-004a"
    assert display_id("demo-001") == "DEMO-001"


def test_sandbox_contract_moves_checkouts_into_the_sandbox(tmp_path):
    text = "- **Repos**: The local checkout is\n  `~/dev/<org>/<repo>`, where ... A repo not cloned there is\n  cloned there, after the author agrees.\n"
    out = sandbox_contract(text, tmp_path)
    assert "~/dev" not in out
    assert str(tmp_path / "checkouts") in out


def test_sandbox_contract_keeps_backslashes_of_windows_paths(tmp_path):
    text = "The local checkout is `~/dev/<org>/<repo>`. A repo not cloned there is cloned there, after the author agrees."
    sandbox = tmp_path / "a\\b"
    assert str(sandbox / "checkouts") in sandbox_contract(text, sandbox)


def test_sandbox_contract_refuses_a_contract_without_the_checkout_rule(tmp_path):
    with pytest.raises(ValueError, match="checkout"):
        sandbox_contract("no such rule", tmp_path)


@pytest.fixture(scope="module")
def sandbox(tmp_path_factory):
    sb = tmp_path_factory.mktemp("sb")
    build(sb)
    return sb


def test_build_publishes_store_and_demo_with_nothing_pending(sandbox):
    s = snapshot(sandbox, "", [])
    assert s.store_commits == []
    assert s.demo_remote_subjects == []
    assert s.demo_porcelain == ""


def test_build_seeds_the_board(sandbox):
    s = snapshot(sandbox, "", [])
    assert (s.board_next, s.board_progress) == (INITIAL_NEXT, INITIAL_PROGRESS)


def test_build_seeds_the_backlog_with_a_derived_toc(sandbox):
    s = snapshot(sandbox, "", [])
    assert s.demo_status["DEMO-004a"] == "Open"
    assert s.demo_status["DEMO-005"].startswith("Done")
    readme = (sandbox / "checkouts" / "demo" / "docs" / "backlog" / "README.md").read_text(encoding="utf-8")
    assert "- [DEMO-006 — Cache the API token](demo-006.md)" in readme


def test_store_holds_both_contracts_with_sandbox_checkouts(sandbox):
    agents = (sandbox / "store" / "AGENTS.md").read_text(encoding="utf-8")
    assert "## Logbook" in agents and "## Board" in agents
    assert str(sandbox / "checkouts") in agents


def test_build_without_board_contract(tmp_path):
    build(tmp_path, board_contract=False)
    agents = (tmp_path / "store" / "AGENTS.md").read_text(encoding="utf-8")
    assert "## Logbook" in agents and "## Board" not in agents


def test_snapshot_sees_a_store_commit(tmp_path):
    from evals.fixture import commit_push

    build(tmp_path)
    board = tmp_path / "store" / BOARD_FILE
    board.write_text(board.read_text(encoding="utf-8").replace("Rename the config keys", "x"), encoding="utf-8")
    commit_push(tmp_path / "store", "docs(board): put · demo · 2 (DEMO-002)", BOARD_FILE)
    s = snapshot(tmp_path, "", [])
    assert s.store_commits == [("docs(board): put · demo · 2 (DEMO-002)", [BOARD_FILE])]
    assert ids(s.board_next) == ["DEMO-001", "DEMO-002"]


def test_build_seeds_the_adr_log_the_drifted_architecture_and_the_learnings(sandbox):
    s = snapshot(sandbox, "", [])
    assert "docs/adr/0001-the-sync-job-runs-from-cron.md" in s.demo_files
    assert "src/importer/" in s.demo_files["docs/architecture.md"]
    assert "src/export/__init__.py" in s.demo_files and not any(p.startswith("src/importer") for p in s.demo_files)
    assert "learnings/2026-10-01_git_archive_exports_commits_only.md" in s.store_files
    assert "## Learnings" in s.store_files["AGENTS.md"]


def test_snapshot_counts_local_commits_from_the_seed_tag(tmp_path):
    from evals.fixture import git

    build(tmp_path)
    demo = tmp_path / "checkouts" / "demo"
    (demo / "x.md").write_text("x\n", encoding="utf-8")
    git(demo, "add", "x.md")
    git(demo, "-c", "user.name=E", "-c", "user.email=e@x", "commit", "-q", "-m", "docs: x\n\nbody")
    s = snapshot(tmp_path, "", [])
    assert s.demo_local_subjects == ["docs: x"]
    assert "body" in s.demo_head_message
    assert s.demo_remote_subjects == []


@pytest.mark.parametrize("name", ["commit", "refinement-bootstrap"])
def test_setup_leaves_a_seed_with_no_local_commits(tmp_path, name):
    from evals.cases import CASES
    from evals.fixture import mark_seed

    case = next(c for c in CASES if c.name == name)
    build(tmp_path)
    case.setup(tmp_path / "checkouts" / "demo")
    mark_seed(tmp_path)
    s = snapshot(tmp_path, "", [])
    assert s.demo_local_subjects == []
    assert case.check(s), f"{name} passes on its own setup"
