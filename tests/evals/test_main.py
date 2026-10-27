"""The command line, as far as it runs without an agent session."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from evals.__main__ import main, results_dir
from evals.cases import CASES


def test_results_dir_lives_outside_the_checkout_and_slugs_the_ref():
    d = results_dir("origin/feature/XAS-046-board", None)
    assert d == Path(tempfile.gettempdir()) / "xxthunder-evals" / "origin_feature_XAS-046-board"


def test_results_dir_honours_out(tmp_path):
    assert results_dir("develop", str(tmp_path)) == tmp_path / "develop"


def test_list_prints_every_case(capsys):
    assert main(["list"]) == 0
    out = capsys.readouterr().out
    assert all(c.name in out for c in CASES)


def test_run_refuses_an_unknown_case(capsys):
    with pytest.raises(SystemExit):
        main(["run", "--case", "no-such-case"])
    assert "unknown case: no-such-case" in capsys.readouterr().err


def test_run_needs_claude_on_path(monkeypatch, capsys):
    monkeypatch.setattr("evals.__main__.shutil.which", lambda _: None)
    with pytest.raises(SystemExit):
        main(["run", "--case", CASES[0].name])
    assert "`claude` is not on PATH" in capsys.readouterr().err


def test_report_reads_earlier_results(tmp_path, capsys):
    d = tmp_path / "develop" / "close-1"
    d.mkdir(parents=True)
    (d / "result.json").write_text(json.dumps({"case": "close", "run": 1, "pass": False, "failures": ["x"]}))
    assert main(["report", "--ref", "develop", "--out", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "close" in out and "0/1" in out and "close#1: x" in out


@pytest.fixture
def no_agent(monkeypatch, tmp_path):
    """`run` without a session: the plugin export and each run are recorded, not done."""
    calls = {"export": [], "runs": []}

    def export(repo, ref, dest):
        calls["export"].append(ref)
        return tmp_path / "plugin"

    def run(case, dirs, n, out):
        calls["runs"].append((case.name, n, dirs))
        (out / f"{case.name}-{n}").mkdir(parents=True)
        result = {"case": case.name, "run": n, "pass": n == 1, "failures": [] if n == 1 else ["x"]}
        (out / f"{case.name}-{n}" / "result.json").write_text(json.dumps(result))
        return result

    monkeypatch.setattr("evals.__main__.shutil.which", lambda _: "/bin/claude")
    monkeypatch.setattr("evals.__main__.export_plugin", export)
    monkeypatch.setattr("evals.__main__.dependency_dirs", lambda plugin, config: [Path("/dep")])
    monkeypatch.setattr("evals.__main__.run_one", run)
    return calls


def test_run_runs_each_chosen_case_n_times_against_the_ref(tmp_path, no_agent, capsys):
    out = tmp_path / "results"
    assert main(["run", "--ref", "develop", "--runs", "2", "--case", "close", "--case", "next-drop",
                 "-j", "1", "--out", str(out)]) == 0
    assert no_agent["export"] == ["develop"]
    assert sorted((c, n) for c, n, _ in no_agent["runs"]) == [("close", 1), ("close", 2), ("next-drop", 1), ("next-drop", 2)]
    assert all(dirs == [Path("/dep"), tmp_path / "plugin"] for _, _, dirs in no_agent["runs"])
    printed = capsys.readouterr().out
    assert "4 runs of develop" in printed and "PASS close#1" in printed and "FAIL close#2" in printed
    assert "close                    1/2" in printed and "close#2: x" in printed


def test_run_replaces_earlier_results_of_the_chosen_cases_only(tmp_path, no_agent, capsys):
    out = tmp_path / "results" / "develop"
    for name in ("close-3", "next-drop-1"):
        (out / name).mkdir(parents=True)
        (out / name / "result.json").write_text(json.dumps({"case": name[:-2], "run": int(name[-1]),
                                                             "pass": True, "failures": []}))
    main(["run", "--ref", "develop", "--runs", "1", "--case", "close", "--out", str(tmp_path / "results")])
    assert not (out / "close-3").exists()
    assert (out / "next-drop-1" / "result.json").exists()
    assert "next-drop                1/1" in capsys.readouterr().out


def test_python_dash_m_evals_exits_with_the_command_status(monkeypatch, capsys):
    import runpy
    import sys

    monkeypatch.setattr("sys.argv", ["python -m evals", "list"])
    monkeypatch.delitem(sys.modules, "evals.__main__", raising=False)  # run it fresh, as `python -m` does
    with pytest.raises(SystemExit) as done:
        runpy.run_module("evals", run_name="__main__")
    assert done.value.code == 0
    assert CASES[0].name in capsys.readouterr().out
