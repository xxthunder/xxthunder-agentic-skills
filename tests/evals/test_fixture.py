"""The sandbox a case runs in, built from real git repos with local bare remotes."""
from __future__ import annotations

import pytest

from evals.board import BOARD_FILE, ids, jira_card
from evals.fixture import (
    INITIAL_NEXT,
    INITIAL_PROGRESS,
    JIRA_ISSUES,
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


def test_snapshot_sees_a_push_from_another_clone(tmp_path):
    from evals.fixture import commit_push, git

    build(tmp_path)
    other = tmp_path / "other"
    git(tmp_path, "clone", "-q", str(tmp_path / "remotes" / "demo.git"), str(other))
    (other / "x.txt").write_text("x", encoding="utf-8")
    commit_push(other, "docs: from elsewhere (DEMO-007)")
    assert snapshot(tmp_path, "", []).demo_remote_subjects == ["docs: from elsewhere (DEMO-007)"]


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


def test_a_failing_git_command_names_itself_and_its_directory(tmp_path):
    from evals.fixture import git

    with pytest.raises(RuntimeError, match=r"git log in .*: fatal"):
        git(tmp_path, "log")


def test_text_files_skips_binaries_git_and_caches(tmp_path):
    from evals.fixture import text_files

    (tmp_path / "notes.md").write_text("ü\n", encoding="utf-8")
    (tmp_path / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n\xff\xfe")
    for d in (".git", "__pycache__"):
        (tmp_path / d).mkdir()
        (tmp_path / d / "x.txt").write_text("x", encoding="utf-8")
    assert text_files(tmp_path) == {"notes.md": "ü\n"}


def test_registry_has_the_jira_projects_table(sandbox):
    repos = (sandbox / "store" / "engineering" / "repos.md").read_text(encoding="utf-8")
    assert "| Jira project | Site | Key | What it is |" in repos
    assert "| [ops](https://jira.example.com/projects/OPS) | https://jira.example.com | OPS | Ops team |" in repos


def test_registry_ids_cell_is_the_bare_prefix(sandbox):
    repos = (sandbox / "store" / "engineering" / "repos.md").read_text(encoding="utf-8")
    assert " | DEMO | Demo service |" in repos


def test_build_with_jira_card_seeds_it_at_the_bottom_of_next(tmp_path):
    build(tmp_path / "with", jira_card=True)
    build(tmp_path / "without")
    summary = JIRA_ISSUES["OPS-041"][0]
    s = snapshot(tmp_path / "with", "", [])
    assert s.board_next == INITIAL_NEXT + [jira_card("OPS-041", summary)]
    assert s.board_progress == INITIAL_PROGRESS
    assert snapshot(tmp_path / "without", "", []).board_next == INITIAL_NEXT


# --- XAS-055: fake gh, the Closed loop contract, loop setups ---

def run_fake_gh(sandbox, *args, stdin=None):
    """Run the fake `gh` the way the sandbox PATH would: as a Python script, `$EVAL_SANDBOX` set."""
    import os
    import subprocess
    import sys

    from evals.fixture import FIXTURES

    env = {**os.environ, "EVAL_SANDBOX": str(sandbox)}
    return subprocess.run([sys.executable, str(FIXTURES / "bin" / "gh"), *args],
                          capture_output=True, text=True, encoding="utf-8", env=env, cwd=sandbox, input=stdin)


def read_calls(sandbox):
    import json

    path = sandbox / "gh-calls.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_fake_gh_records_pr_create_and_prints_the_url(tmp_path):
    r = run_fake_gh(tmp_path, "pr", "create", "--title", "t", "--body", "b")
    assert r.returncode == 0
    assert r.stdout.strip() == "https://example.com/demo/pull/1"
    assert read_calls(tmp_path) == [{"args": ["pr", "create", "--title", "t", "--body", "b"], "body": "b"}]


def test_fake_gh_reads_the_body_from_a_body_file(tmp_path):
    (tmp_path / "pr.md").write_text("## Item\n\nDEMO-007\n", encoding="utf-8")
    run_fake_gh(tmp_path, "pr", "create", "--title", "t", "--body-file", "pr.md")
    assert read_calls(tmp_path)[0]["body"] == "## Item\n\nDEMO-007\n"


def test_fake_gh_pr_checks_prints_nothing_and_each_call_is_one_more_line(tmp_path):
    run_fake_gh(tmp_path, "pr", "create", "--title", "t", "--body", "b")
    r = run_fake_gh(tmp_path, "pr", "checks", "1", "--watch")
    assert (r.returncode, r.stdout) == (0, "")
    calls = read_calls(tmp_path)
    assert [c["args"][:2] for c in calls] == [["pr", "create"], ["pr", "checks"]]
    assert calls[1]["body"] is None


def test_fake_gh_ships_a_windows_wrapper():
    from evals.fixture import FIXTURES

    assert (FIXTURES / "bin" / "gh.cmd").is_file()


def test_snapshot_returns_the_gh_calls(tmp_path):
    build(tmp_path)
    assert snapshot(tmp_path, "", []).gh_calls == []
    run_fake_gh(tmp_path, "pr", "create", "--title", "t", "--body", "b")
    assert snapshot(tmp_path, "", []).gh_calls == [
        {"args": ["pr", "create", "--title", "t", "--body", "b"], "body": "b"}]


def test_store_has_a_closed_loop_section_only_when_the_case_asks(tmp_path):
    build(tmp_path / "with", closed_loop=True)
    build(tmp_path / "without")
    with_ = (tmp_path / "with" / "store" / "AGENTS.md").read_text(encoding="utf-8")
    without = (tmp_path / "without" / "store" / "AGENTS.md").read_text(encoding="utf-8")
    assert "## Closed loop" in with_ and "## Logbook" in with_
    assert "## Closed loop" not in without


def test_closed_loop_contract_carries_gate_order_package_sections_and_stop_rule():
    from evals.fixture import FIXTURES

    text = (FIXTURES / "closed-loop-contract.md").read_text(encoding="utf-8")
    assert text.startswith("## Closed loop")
    for needle in ("scripts/gate", "Evidence package", "No CI and no gate, no loop",
                   "Item", "What changes", "Gate", "Review", "Your steps", "Open"):
        assert needle in text, needle


def setup_demo(tmp_path):
    build(tmp_path)
    return tmp_path / "checkouts" / "demo"


def loop_state(demo):
    import json
    import subprocess
    import sys

    from evals.fixture import BACKLOG_SCRIPT

    script = BACKLOG_SCRIPT.parent / "loop.py"
    out = subprocess.run([sys.executable, str(script), "state", str(demo)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


@pytest.mark.parametrize("gate_exit, marker", [(1, "FAILED tests/test_health.py::test_health"), (0, "1 passed")])
def test_setup_loop_at_gate_cuts_the_branch_and_leaves_a_gate_and_state(tmp_path, gate_exit, marker):
    import os
    import subprocess
    import sys

    from evals.cases import setup_loop_at_gate
    from evals.fixture import git, mark_seed

    demo = setup_demo(tmp_path)
    setup_loop_at_gate(demo, gate_exit)
    mark_seed(tmp_path)
    assert git(demo, "branch", "--show-current").strip() == "feature/DEMO-007-health-endpoint"
    assert loop_state(demo) == {"item": "DEMO-007", "step": "gate", "fix_rounds": 0}
    gate = demo / "scripts" / "gate"
    assert marker in gate.read_text(encoding="utf-8")
    assert git(demo, "status", "--porcelain") == ""
    if sys.platform != "win32":
        assert os.access(gate, os.X_OK)
        r = subprocess.run([str(gate)], cwd=demo, capture_output=True, text=True)
        assert r.returncode == gate_exit and marker in r.stdout


def test_setup_loop_at_gate_keeps_the_gate_out_of_the_branch_diff(tmp_path):
    from evals.cases import setup_loop_at_gate
    from evals.fixture import git

    demo = setup_demo(tmp_path)
    setup_loop_at_gate(demo, 1)
    assert "scripts/gate" in git(demo, "ls-tree", "-r", "--name-only", "develop")
    changed = git(demo, "diff", "--name-only", "develop...HEAD").splitlines()
    assert changed and "scripts/gate" not in changed
    assert len(git(demo, "log", "--format=%s", "develop..HEAD").splitlines()) == 1


def test_setup_loop_dispute_writes_the_dispute_state(tmp_path):
    from evals.cases import setup_loop_dispute

    demo = setup_demo(tmp_path)
    setup_loop_dispute(demo)
    state = loop_state(demo)
    assert {k: state[k] for k in ("item", "step", "task", "exchanges")} == {
        "item": "DEMO-007", "step": "dispute", "task": "1.b", "exchanges": 2}
    assert isinstance(state["dispute"], str) and state["dispute"]


def test_fake_gh_takes_the_body_from_stdin_with_body_file_dash(tmp_path):
    run_fake_gh(tmp_path, "pr", "create", "--title", "t", "--body-file", "-", stdin="## Item\n\nfrom stdin\n")
    call = read_calls(tmp_path)[0]
    assert call["body"] == "## Item\n\nfrom stdin\n"
    assert call["args"] == ["pr", "create", "--title", "t", "--body-file", "-"]


def test_fake_gh_takes_the_body_in_the_equals_form(tmp_path):
    run_fake_gh(tmp_path, "pr", "create", "--title=t", "--body=b c")
    assert read_calls(tmp_path)[0]["body"] == "b c"


def test_fake_gh_records_an_unknown_subcommand_and_stays_silent(tmp_path):
    r = run_fake_gh(tmp_path, "pr", "view", "1")
    assert (r.returncode, r.stdout) == (0, "")
    assert read_calls(tmp_path) == [{"args": ["pr", "view", "1"], "body": None}]


def test_fake_gh_is_an_executable_script_with_a_shebang():
    import os
    import sys

    from evals.fixture import FIXTURES

    if sys.platform == "win32":
        pytest.skip("POSIX exec bit and shebang")
    gh = FIXTURES / "bin" / "gh"
    assert os.access(gh, os.X_OK)
    assert gh.read_text(encoding="utf-8").startswith("#!")


def test_gh_by_name_resolves_through_the_sandbox_path(tmp_path):
    import os
    import subprocess
    import sys

    from evals.runner import clean_env

    if sys.platform == "win32":
        pytest.skip("POSIX PATH lookup without a shell")
    env = clean_env(dict(os.environ), tmp_path, board=True, logbook=False)
    r = subprocess.run(["gh", "pr", "create", "--title", "t", "--body", "b"],
                       env=env, capture_output=True, text=True, cwd=tmp_path)
    assert r.returncode == 0 and r.stdout.strip() == "https://example.com/demo/pull/1"
    assert read_calls(tmp_path) == [{"args": ["pr", "create", "--title", "t", "--body", "b"], "body": "b"}]


def test_gh_cmd_runs_python_on_the_gh_script_and_forwards_arguments():
    from evals.fixture import FIXTURES

    text = (FIXTURES / "bin" / "gh.cmd").read_text(encoding="utf-8")
    assert "python" in text.lower() and "gh" in text and "%*" in text
