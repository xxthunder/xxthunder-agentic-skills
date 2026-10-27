"""One run end to end, with a fake agent in place of `claude -p`."""
from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest

import evals.runner as runner
from evals.cases import CASES, Case, expect
from evals.runner import run_one

FAKE_AGENT = Path(__file__).resolve().parent / "fake_agent.py"
BY_NAME = {c.name: c for c in CASES}


@pytest.fixture(autouse=True)
def fake_claude(monkeypatch):
    monkeypatch.setattr(runner, "claude_command", lambda prompt, dirs, sandbox: [sys.executable, str(FAKE_AGENT), prompt])


def case(prompt: str, check=lambda s: [], **kw) -> Case:
    return Case("fake", prompt, check, **kw)


def answer(sandbox: Path) -> dict:
    return json.loads((sandbox / "output.md").read_text(encoding="utf-8"))


def test_a_run_records_stream_stderr_final_answer_and_result(tmp_path):
    result = run_one(case("report"), [], 1, tmp_path)
    sandbox = tmp_path / "fake-1"
    assert result == {"case": "fake", "run": 1, "pass": True, "failures": []}
    assert json.loads((sandbox / "result.json").read_text(encoding="utf-8")) == result
    assert '"type": "result"' in (sandbox / "stream.jsonl").read_text(encoding="utf-8")
    assert "a warning on stderr" in (sandbox / "stderr.txt").read_text(encoding="utf-8")
    assert "Now the board check." not in (sandbox / "output.md").read_text(encoding="utf-8")


def test_the_session_runs_in_the_demo_checkout_with_stores_in_the_sandbox(tmp_path, monkeypatch):
    monkeypatch.setenv("BOARD_PATH", "/the/real/board")
    monkeypatch.setenv("LOGBOOK_PATH", "/the/real/logbook")
    monkeypatch.setenv("CLAUDECODE", "1")
    run_one(case("report"), [], 1, tmp_path)
    seen = answer(tmp_path / "fake-1")
    assert Path(seen["cwd"]).resolve() == (tmp_path / "fake-1" / "checkouts" / "demo").resolve()
    assert Path(seen["BOARD_PATH"]).resolve() == (tmp_path / "fake-1" / "store").resolve()
    assert seen["LOGBOOK_PATH"] is None and seen["CLAUDECODE"] is None


def test_the_check_grades_the_skills_the_session_invoked(tmp_path):
    result = run_one(replace(BY_NAME["trigger-was-steht-an"], prompt="report"), [], 1, tmp_path)
    assert result["pass"], result["failures"]


def test_a_real_case_grades_what_the_session_left_behind(tmp_path):
    passed = run_one(replace(BY_NAME["pull-no-board"], prompt="pull"), [], 1, tmp_path)
    failed = run_one(replace(BY_NAME["pull-no-board"], prompt="report"), [], 2, tmp_path)
    assert passed["pass"], passed["failures"]  # the narration mentions a board; the answer does not
    assert "pull did not happen" in failed["failures"]


def test_the_setup_is_part_of_the_seed_not_of_the_session(tmp_path):
    result = run_one(replace(BY_NAME["commit"], prompt="report"), [], 1, tmp_path)
    assert "local commits: []" in result["failures"]
    assert "left changes: 'A  docs/health.md\\n'" in result["failures"]


def test_a_session_that_hangs_is_cut_off_and_graded_on_what_it_said(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "TIMEOUT", 2)
    result = run_one(case("sleep", lambda s: expect("board" in s.output, "no narration")), [], 1, tmp_path)
    sandbox = tmp_path / "fake-1"
    assert result["pass"]
    assert (sandbox / "stderr.txt").read_text(encoding="utf-8") == "timed out after 2s"
    assert "Now the board check." in (sandbox / "stream.jsonl").read_text(encoding="utf-8")


def test_a_check_that_crashes_is_a_failure_not_a_crash(tmp_path):
    result = run_one(case("report", lambda s: s.demo_status["DEMO-999"]), [], 1, tmp_path)
    assert not result["pass"]
    assert result["failures"][0].startswith("grading error: KeyError")


def test_a_rerun_replaces_the_earlier_sandbox(tmp_path):
    run_one(case("pull"), [], 1, tmp_path)
    run_one(case("report"), [], 1, tmp_path)
    item = tmp_path / "fake-1" / "checkouts" / "demo" / "docs" / "backlog" / "demo-007.md"
    assert "**Status**: Open" in item.read_text(encoding="utf-8")
