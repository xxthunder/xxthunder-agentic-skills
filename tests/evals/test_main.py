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
