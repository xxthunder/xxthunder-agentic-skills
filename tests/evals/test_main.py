"""The command line, as far as it runs without an agent session."""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

import pytest

import evals
from evals.fingerprint import fingerprint, shared
from evals.__main__ import REPO_ROOT, main, results_dir
from evals.cases import CASES
from evals.runner import PLUGIN


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()


def commit(repo: Path, msg: str) -> str:
    git(repo, "add", "-A")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", msg)
    return git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path):
    """A repo whose one commit holds a plugin file and a README."""
    r = tmp_path / "repo"
    (r / PLUGIN).mkdir(parents=True)
    git(r, "init", "-q", "-b", "develop")
    (r / PLUGIN / "plugin.json").write_text("{}\n", encoding="utf-8")
    (r / "README.md").write_text("# demo\n", encoding="utf-8")
    commit(r, "one")
    return r


def head_dir(root: Path) -> Path:
    return results_dir("HEAD", str(root), REPO_ROOT)


def test_results_dir_is_keyed_by_the_plugin_version(repo, tmp_path):
    out = tmp_path / "out"
    tree = git(repo, "rev-parse", f"HEAD:{PLUGIN}")
    assert len(tree) == 40
    assert results_dir("HEAD", str(out), repo) == out / tree
    assert results_dir("develop", str(out), repo) == out / tree


def test_a_commit_that_leaves_the_plugin_alone_shares_its_results_dir(repo, tmp_path):
    before = results_dir("HEAD", str(tmp_path), repo)
    (repo / "README.md").write_text("# changed\n", encoding="utf-8")
    commit(repo, "readme only, as a rebase onto a newer develop brings")
    assert results_dir("HEAD", str(tmp_path), repo) == before


def test_a_commit_that_changes_the_plugin_gets_a_new_results_dir(repo, tmp_path):
    before = results_dir("HEAD", str(tmp_path), repo)
    (repo / PLUGIN / "plugin.json").write_text('{"version": "1"}\n', encoding="utf-8")
    commit(repo, "plugin")
    assert results_dir("HEAD", str(tmp_path), repo) != before


def test_results_dir_refuses_a_commit_without_the_plugin(repo, tmp_path):
    git(repo, "rm", "-q", "-r", "plugins")
    commit(repo, "no plugin")
    with pytest.raises(ValueError, match=f"no {PLUGIN} at HEAD"):
        results_dir("HEAD", str(tmp_path), repo)


def test_results_dir_lives_outside_the_checkout_by_default(repo):
    d = results_dir("HEAD", None, repo)
    assert d == Path(tempfile.gettempdir()) / "xxthunder-evals" / git(repo, "rev-parse", f"HEAD:{PLUGIN}")


def test_results_dir_refuses_an_unknown_ref(repo, tmp_path):
    with pytest.raises(ValueError, match="unknown ref: nope"):
        results_dir("nope", str(tmp_path), repo)


@pytest.mark.parametrize("cmd", ["run", "report"])
def test_an_unknown_ref_is_an_argument_error(cmd, tmp_path, capsys, monkeypatch):
    monkeypatch.setattr("evals.__main__.shutil.which", lambda _: "/bin/claude")
    with pytest.raises(SystemExit):
        main([cmd, "--ref", "nope", "--out", str(tmp_path)])
    assert "unknown ref: nope" in capsys.readouterr().err


def test_list_prints_every_case(capsys):
    assert main(["list"]) == 0
    out = capsys.readouterr().out
    assert all(c.name in out for c in CASES)


def test_run_refuses_an_unknown_case(capsys):
    with pytest.raises(SystemExit):
        main(["run", "--case", "no-such-case"])
    assert "unknown case: no-such-case" in capsys.readouterr().err


def test_run_refuses_an_unknown_skill(capsys):
    with pytest.raises(SystemExit):
        main(["run", "--skill", "no-such-skill"])
    assert "unknown skill: no-such-skill" in capsys.readouterr().err


def test_run_skill_selects_that_skills_cases(tmp_path, no_agent):
    assert main(["run", "--skill", "logbook", "--runs", "1", "--out", str(tmp_path)]) == 0
    assert sorted(c for c, _, _ in no_agent["runs"]) == sorted(c.name for c in CASES if c.skill == "logbook")
    assert no_agent["runs"]


def test_list_prints_each_cases_skill(capsys):
    main(["list"])
    lines = capsys.readouterr().out.splitlines()
    assert any(l.split()[:2] == ["logbook-started", "logbook"] for l in lines)
    assert any(l.split()[:2] == ["rubric-flags-hand-allocation", "-"] for l in lines)


def test_run_needs_claude_on_path(monkeypatch, capsys):
    monkeypatch.setattr("evals.__main__.shutil.which", lambda _: None)
    with pytest.raises(SystemExit):
        main(["run", "--case", CASES[0].name])
    assert "`claude` is not on PATH" in capsys.readouterr().err


def test_report_reads_earlier_results(tmp_path, capsys):
    d = head_dir(tmp_path) / "close-1"
    d.mkdir(parents=True)
    (d / "result.json").write_text(json.dumps({"case": "close", "run": 1, "pass": False, "failures": ["x"]}))
    assert main(["report", "--ref", "HEAD", "--out", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "close" in out and "0/1" in out and "close#1: x" in out


@pytest.fixture
def no_agent(monkeypatch, tmp_path):
    """`run` without a session: the plugin export and each run are recorded, not done."""
    calls = {"export": [], "runs": [], "fps": []}

    def export(repo, ref, dest):
        calls["export"].append(ref)
        return tmp_path / "plugin"

    def run(case, dirs, n, out, fp=""):
        calls["fps"].append(fp)
        calls["runs"].append((case.name, n, dirs))
        (out / f"{case.name}-{n}").mkdir(parents=True)
        result = {"case": case.name, "run": n, "pass": n == 1, "failures": [] if n == 1 else ["x"], "fingerprint": fp}
        (out / f"{case.name}-{n}" / "result.json").write_text(json.dumps(result))
        return result

    monkeypatch.setattr("evals.__main__.shutil.which", lambda _: "/bin/claude")
    monkeypatch.setattr("evals.__main__.export_plugin", export)
    monkeypatch.setattr("evals.__main__.dependency_dirs", lambda plugin, config: [Path("/dep")])
    monkeypatch.setattr("evals.__main__.run_one", run)
    return calls


def test_run_runs_each_chosen_case_n_times_against_the_ref(tmp_path, no_agent, capsys):
    out = tmp_path / "results"
    assert main(["run", "--ref", "HEAD", "--runs", "2", "--case", "close", "--case", "next-drop",
                 "-j", "1", "--out", str(out)]) == 0
    assert no_agent["export"] == ["HEAD"]
    assert sorted((c, n) for c, n, _ in no_agent["runs"]) == [("close", 1), ("close", 2), ("next-drop", 1), ("next-drop", 2)]
    assert all(dirs == [Path("/dep"), tmp_path / "plugin"] for _, _, dirs in no_agent["runs"])
    printed = capsys.readouterr().out
    assert "4 runs of HEAD" in printed and "PASS close#1" in printed and "FAIL close#2" in printed
    assert "close                    1/2" in printed and "close#2: x" in printed


def test_run_stamps_each_run_with_its_cases_fingerprint(tmp_path, no_agent):
    main(["run", "--ref", "HEAD", "--runs", "1", "--case", "close", "--case", "next-drop", "--out", str(tmp_path)])
    by_name = {c.name: c for c in CASES}
    shared_hash = tracked_hash()
    fps = dict(zip([c for c, _, _ in no_agent["runs"]], no_agent["fps"]))
    assert fps == {n: fingerprint(by_name[n], shared_hash) for n in ("close", "next-drop")}
    assert fps["close"] != fps["next-drop"]


def tracked_hash() -> str:
    files = git(REPO_ROOT, "ls-files", "-z", "--", "evals").split("\0")
    return shared(Path(evals.__file__).parent, CASES, [f.removeprefix("evals/") for f in files if f])


def test_run_hashes_only_the_files_git_tracks(tmp_path, no_agent):
    close = next(c for c in CASES if c.name == "close")
    stray = Path(evals.__file__).parent / "stray-file-of-a-test.txt"
    stray.write_text("not tracked\n", encoding="utf-8")
    try:
        main(["run", "--ref", "HEAD", "--runs", "1", "--case", "close", "--out", str(tmp_path)])
        with_stray = shared(Path(evals.__file__).parent, CASES)
    finally:
        stray.unlink()
    assert no_agent["fps"] != [fingerprint(close, with_stray)]
    assert no_agent["fps"] == [fingerprint(close, tracked_hash())]


def test_run_replaces_earlier_results_of_the_chosen_cases_only(tmp_path, no_agent, capsys):
    out = head_dir(tmp_path / "results")
    for name in ("close-3", "next-drop-1"):
        (out / name).mkdir(parents=True)
        (out / name / "result.json").write_text(json.dumps({"case": name[:-2], "run": int(name[-1]),
                                                             "pass": True, "failures": []}))
    main(["run", "--ref", "HEAD", "--runs", "1", "--case", "close", "--out", str(tmp_path / "results")])
    assert not (out / "close-3").exists()
    assert (out / "next-drop-1" / "result.json").exists()
    assert "next-drop                1/1" in capsys.readouterr().out


def test_run_keeps_the_results_of_a_case_whose_name_starts_with_the_chosen_one(tmp_path, no_agent):
    out = head_dir(tmp_path / "results")
    for name in ("logbook-started-1", "logbook-started-again-1"):
        (out / name).mkdir(parents=True)
    main(["run", "--ref", "HEAD", "--runs", "1", "--case", "logbook-started", "--out", str(tmp_path / "results")])
    assert (out / "logbook-started-again-1").exists()
    assert (out / "logbook-started-1" / "result.json").exists()  # replaced by the new run


def test_python_dash_m_evals_exits_with_the_command_status(monkeypatch, capsys):
    import runpy
    import sys

    monkeypatch.setattr("sys.argv", ["python -m evals", "list"])
    monkeypatch.delitem(sys.modules, "evals.__main__", raising=False)  # run it fresh, as `python -m` does
    with pytest.raises(SystemExit) as done:
        runpy.run_module("evals", run_name="__main__")
    assert done.value.code == 0
    assert CASES[0].name in capsys.readouterr().out
