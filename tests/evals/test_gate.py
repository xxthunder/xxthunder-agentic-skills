"""The gate asks for eval results of exactly the cases a change asks for."""
from __future__ import annotations

import io
import json
import shutil
import subprocess
from pathlib import Path

import pytest

import evals
from evals import gate
from evals.runner import PLUGIN

EVALS = Path(evals.__file__).parent
REPO_ROOT = EVALS.parent
SKILL = f"{PLUGIN}/skills/next/SKILL.md"


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()


def commit(repo: Path, msg: str) -> str:
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", msg)
    return git(repo, "rev-parse", "HEAD")


def edit(repo: Path, rel: str, old: str, new: str) -> None:
    path = repo / rel
    text = path.read_text(encoding="utf-8")
    assert old in text, f"{old!r} not in {rel}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


@pytest.fixture
def repo(tmp_path):
    """A clone of a bare `origin` whose `develop` holds the real `evals/` and the `next` skill, on branch `feature`."""
    origin = tmp_path / "origin.git"
    git(tmp_path, "init", "-q", "--bare", "-b", "develop", str(origin))
    r = tmp_path / "repo"
    r.mkdir()
    git(r, "init", "-q", "-b", "develop")
    git(r, "config", "user.name", "t")
    git(r, "config", "user.email", "t@t")
    git(r, "config", "core.autocrlf", "false")
    shutil.copytree(EVALS, r / "evals", ignore=shutil.ignore_patterns("__pycache__"))
    (r / SKILL).parent.mkdir(parents=True)
    shutil.copy(REPO_ROOT / SKILL, r / SKILL)
    (r / "README.md").write_text("# demo\n", encoding="utf-8")
    commit(r, "base")
    git(r, "remote", "add", "origin", str(origin))
    git(r, "push", "-q", "origin", "develop")
    git(r, "checkout", "-q", "-b", "feature")
    return r


def write_results(out: Path, sha: str, case: str, fp: str, passes: list[bool], repo: Path) -> None:
    for n, ok in enumerate(passes, 1):
        d = gate.results_dir(sha, str(out), repo) / f"{case}-{n}"
        d.mkdir(parents=True)
        (d / "result.json").write_text(json.dumps({"case": case, "run": n, "pass": ok, "fingerprint": fp}),
                                       encoding="utf-8")


def green(out: Path, repo: Path, sha: str, names) -> None:
    table = gate.case_table(repo, sha)
    for name in names:
        write_results(out, sha, name, table[name][2], [True] * 3, repo)


def cases_of(repo: Path, sha: str, skill: str) -> list[str]:
    return sorted(n for n, (s, _, _) in gate.case_table(repo, sha).items() if s == skill)


def touch_skill(repo: Path) -> str:
    edit(repo, SKILL, "\n", "\nA changed line.\n")
    return commit(repo, "change next")


def test_no_skill_and_no_case_change_is_green(repo, tmp_path):
    (repo / "README.md").write_text("# changed\n", encoding="utf-8")
    commit(repo, "readme")
    assert gate.check(repo, "HEAD", str(tmp_path / "out")) == []


def test_touched_skill_without_results_is_red_and_names_the_command(repo, tmp_path):
    sha = touch_skill(repo)
    problems = "\n".join(gate.check(repo, "HEAD", str(tmp_path / "out")))
    names = cases_of(repo, sha, "next")
    assert names and all(n in problems for n in names)
    assert f"python -m evals run --ref {sha}" in problems
    assert "--runs 1" not in problems  # the cases' own definitions did not change: no RED run asked


def test_touched_skill_with_three_green_runs_is_green(repo, tmp_path):
    sha = touch_skill(repo)
    out = tmp_path / "out"
    green(out, repo, sha, cases_of(repo, sha, "next"))
    assert gate.check(repo, "HEAD", str(out)) == []


def test_a_commit_that_leaves_plugin_and_evals_alone_keeps_the_results(repo, tmp_path):
    sha = touch_skill(repo)
    out = tmp_path / "out"
    green(out, repo, sha, cases_of(repo, sha, "next"))
    (repo / "README.md").write_text("# changed\n", encoding="utf-8")
    commit(repo, "readme, as a rebase onto a newer develop brings")
    assert gate.check(repo, "HEAD", str(out)) == []


def test_touched_skill_without_cases_is_red(repo, tmp_path):
    (repo / PLUGIN / "skills" / "fresh").mkdir()
    (repo / PLUGIN / "skills" / "fresh" / "SKILL.md").write_text("# fresh\n", encoding="utf-8")
    commit(repo, "a skill without a case")
    assert gate.check(repo, "HEAD", str(tmp_path / "out")) == ["skill fresh has no eval case"]


def test_two_of_three_is_red(repo, tmp_path):
    sha = touch_skill(repo)
    out = tmp_path / "out"
    names = cases_of(repo, sha, "next")
    green(out, repo, sha, names[1:])
    write_results(out, sha, names[0], gate.case_table(repo, sha)[names[0]][2], [True, False, True], repo)
    problems = "\n".join(gate.check(repo, "HEAD", str(out)))
    assert f"{names[0]} 2/3" in problems
    assert f"--case {names[0]}" in problems
    assert f"--case {names[1]}" not in problems


def test_results_for_an_older_case_version_do_not_count(repo, tmp_path):
    sha = touch_skill(repo)
    out = tmp_path / "out"
    names = cases_of(repo, sha, "next")
    for name in names:
        write_results(out, sha, name, "an older fingerprint", [True] * 3, repo)
    problems = "\n".join(gate.check(repo, "HEAD", str(out)))
    note = "(results exist but none match the current version of the case)"
    assert all(f"{n} 0/0 {note}" in problems for n in names)


def test_no_results_at_all_has_no_note(repo, tmp_path):
    touch_skill(repo)
    assert "results exist" not in "\n".join(gate.check(repo, "HEAD", str(tmp_path / "out")))


def test_a_case_whose_name_starts_another_does_not_borrow_its_results(repo, tmp_path):
    sha = git(repo, "rev-parse", "HEAD")
    out = tmp_path / "out"
    fp = gate.case_table(repo, sha)["logbook-started"][2]
    write_results(out, sha, "logbook-started-again", fp, [True] * 3, repo)
    assert gate.results(gate.results_dir(sha, str(out), repo), "logbook-started", fp) == []


def test_changed_case_without_touched_skill_asks_for_that_case_only(repo, tmp_path):
    edit(repo, "evals/cases.py", "def check_tick(s: State) -> list[str]:\n",
         "def check_tick(s: State) -> list[str]:\n    s = s\n")
    sha = commit(repo, "change tick-ac")
    problems = gate.check(repo, "HEAD", str(tmp_path / "out"))
    commands = [p for p in problems if "python -m evals run" in p]
    assert commands == [f"  uv run --group dev python -m evals run --ref {sha} --out {tmp_path / 'out'} --case tick-ac"]


def test_changed_shared_helper_asks_for_every_case(repo, tmp_path):
    edit(repo, "evals/cases.py", "def expect(cond: bool, msg: str) -> list[str]:\n",
         "def expect(cond: bool, msg: str) -> list[str]:\n    cond = bool(cond)\n")
    sha = commit(repo, "change a helper")
    problems = "\n".join(gate.check(repo, "HEAD", str(tmp_path / "out")))
    assert all(f"--case {n} " in problems + " " for n in gate.case_table(repo, sha))
    assert "--runs 1" not in problems  # regression cases pass at the base by design


NEW_CASE = '    Case("next-show-again", "next", "/next again", check_show),\n'


def add_case_and_touch_skill(repo: Path) -> tuple[str, str]:
    base = git(repo, "rev-parse", "HEAD")
    edit(repo, "evals/cases.py", "CASES = [\n", "CASES = [\n" + NEW_CASE)
    edit(repo, SKILL, "\n", "\nA changed line.\n")
    return base, commit(repo, "new case for next")


def test_new_case_of_touched_skill_needs_a_red_run_at_base(repo, tmp_path):
    base, sha = add_case_and_touch_skill(repo)
    out = tmp_path / "out"
    green(out, repo, sha, cases_of(repo, sha, "next"))
    problems = gate.check(repo, "HEAD", str(out))
    text = "\n".join(problems)
    assert "next-show-again" in text
    assert f"python -m evals run --ref {base} --out {out} --runs 1 --case next-show-again" in text
    assert "--case next-show " not in text + " "


def test_new_case_of_touched_skill_is_green_with_a_failing_base_run(repo, tmp_path):
    base, sha = add_case_and_touch_skill(repo)
    out = tmp_path / "out"
    green(out, repo, sha, cases_of(repo, sha, "next"))
    write_results(out, base, "next-show-again", gate.case_table(repo, sha)["next-show-again"][2], [False], repo)
    assert gate.check(repo, "HEAD", str(out)) == []


def test_a_passing_base_run_is_not_red(repo, tmp_path):
    base, sha = add_case_and_touch_skill(repo)
    out = tmp_path / "out"
    green(out, repo, sha, cases_of(repo, sha, "next"))
    write_results(out, base, "next-show-again", gate.case_table(repo, sha)["next-show-again"][2], [True], repo)
    assert "next-show-again 1/1" in "\n".join(gate.check(repo, "HEAD", str(out)))


OLD_CASES = '''from __future__ import annotations
from dataclasses import dataclass
from typing import Callable


def check_show(s) -> list[str]:
    return []


@dataclass(frozen=True)
class Case:
    name: str
    prompt: str
    check: Callable
    board: bool = True


CASES = [Case("next-show", "/next", check_show)]
'''


def test_base_without_skill_field_loads(repo):
    shutil.rmtree(repo / "evals")
    (repo / "evals").mkdir()
    (repo / "evals" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "evals" / "cases.py").write_text(OLD_CASES, encoding="utf-8")
    sha = commit(repo, "an evals/ before skill and fingerprint.py")
    table = gate.case_table(repo, sha)
    assert list(table) == ["next-show"]
    skill, own, full = table["next-show"]
    assert skill is None and len(own) == 64 and len(full) == 64


def test_no_evals_folder_is_an_empty_table(repo):
    shutil.rmtree(repo / "evals")
    assert gate.case_table(repo, commit(repo, "no evals")) == {}


def test_missing_base_ref_is_a_message(repo, tmp_path):
    git(repo, "update-ref", "-d", "refs/remotes/origin/develop")
    problems = gate.check(repo, "HEAD", str(tmp_path / "out"))
    assert len(problems) == 1 and gate.BASE in problems[0]


def test_unknown_head_is_a_message(repo, tmp_path):
    assert gate.check(repo, "no-such-ref", str(tmp_path / "out")) == ["unknown ref: no-such-ref"]


def test_deleted_skill_asks_for_nothing(repo, tmp_path):
    shutil.rmtree(repo / SKILL.rsplit("/", 1)[0])
    commit(repo, "delete next")
    assert gate.check(repo, "HEAD", str(tmp_path / "out")) == []


def test_a_case_to_run_without_the_plugin_is_a_message(repo, tmp_path):
    shutil.rmtree(repo / "plugins")
    edit(repo, "evals/cases.py", "def check_tick(s: State) -> list[str]:\n",
         "def check_tick(s: State) -> list[str]:\n    s = s\n")
    sha = commit(repo, "no plugin, a changed case")
    assert gate.check(repo, "HEAD", str(tmp_path / "out")) == [f"no {PLUGIN} at {sha}"]


def test_a_file_moved_between_skills_touches_both(repo):
    src, dest = f"{PLUGIN}/skills/logbook/references/notes.md", f"{PLUGIN}/skills/next/references/notes.md"
    (repo / src).parent.mkdir(parents=True)
    (repo / src).write_text("Notes that stay the same when moved.\n" * 5, encoding="utf-8")
    base = commit(repo, "notes in logbook")
    (repo / dest).parent.mkdir(parents=True)
    git(repo, "mv", src, dest)
    head = commit(repo, "notes move to next")
    assert gate.touched_skills(gate.changed_paths(repo, base, head)) == {"logbook", "next"}


def test_changed_paths_are_not_quoted(repo):
    base = git(repo, "rev-parse", "HEAD")
    (repo / PLUGIN / "skills" / "next" / "größe.md").write_text("x\n", encoding="utf-8")
    head = commit(repo, "a non-ASCII name")
    assert gate.changed_paths(repo, base, head) == [f"{PLUGIN}/skills/next/größe.md"]


def test_pytest_gets_no_stdin(monkeypatch):
    seen = {}
    monkeypatch.setattr(gate.subprocess, "run", lambda cmd, **kw: seen.update(kw) or subprocess.CompletedProcess(cmd, 0))
    assert gate.tests_pass()
    assert seen["stdin"] is subprocess.DEVNULL  # the pre-push hook's ref lines on stdin stay for the gate


def test_touched_skills_counts_only_the_covered_plugin():
    paths = [f"{PLUGIN}/skills/next/references/x.md", f"{PLUGIN}/skills/logbook/SKILL.md",
             "plugins/xxthunder-paperless-skills/skills/scan/SKILL.md", f"{PLUGIN}/scripts/a.py", "README.md"]
    assert gate.touched_skills(paths) == {"next", "logbook"}


ZERO = "0" * 40


@pytest.fixture
def stubbed(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(gate, "tests_pass", lambda: True)
    monkeypatch.setattr(gate, "check", lambda repo, head, out=None: calls.append(head) or [])
    return calls


def test_pre_push_skips_a_deletion(stubbed, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO(f"(delete) {ZERO} refs/heads/old {'a' * 40}\n"))
    assert gate.main(["--pre-push"]) == 0
    assert stubbed == []


def test_pre_push_checks_each_pushed_sha(stubbed, monkeypatch):
    lines = f"refs/heads/a {'1' * 40} refs/heads/a {ZERO}\nrefs/heads/b {'2' * 40} refs/heads/b {'3' * 40}\n"
    monkeypatch.setattr("sys.stdin", io.StringIO(lines))
    assert gate.main(["--pre-push"]) == 0
    assert stubbed == ["1" * 40, "2" * 40]


def test_problems_make_the_gate_red(stubbed, monkeypatch, capsys):
    monkeypatch.setattr(gate, "check", lambda repo, head, out=None: ["skill next has no eval case"])
    assert gate.main([]) == 1
    assert capsys.readouterr().out.splitlines()[-1] == "gate: red"


def test_red_tests_make_the_gate_red(stubbed, monkeypatch, capsys):
    monkeypatch.setattr(gate, "tests_pass", lambda: False)
    assert gate.main([]) == 1
    assert capsys.readouterr().out.splitlines()[-1] == "gate: red"


def test_green_ends_with_green(stubbed, capsys):
    assert gate.main(["--head", "HEAD"]) == 0
    assert stubbed == ["HEAD"]
    assert capsys.readouterr().out.splitlines()[-1] == "gate: green"


def test_gate_script_runs_the_gate_module():
    text = (REPO_ROOT / "scripts" / "gate").read_text(encoding="utf-8")
    assert text.startswith("#!/bin/sh\n")
    assert "XAS-049" in text
    assert 'exec uv run --group dev python -m evals.gate "$@"' in text


def test_pre_push_hook_calls_the_gate():
    text = (REPO_ROOT / ".githooks" / "pre-push").read_text(encoding="utf-8")
    assert text.startswith("#!/bin/sh\n")
    assert 'exec "$(git rev-parse --show-toplevel)/scripts/gate" --pre-push' in text


def test_gate_files_are_executable_in_git():
    out = git(REPO_ROOT, "ls-files", "-s", "scripts/gate", ".githooks/pre-push")
    modes = [line.split()[0] for line in out.splitlines()]
    assert modes == ["100755", "100755"]


def test_gate_files_keep_lf_line_endings():
    out = git(REPO_ROOT, "check-attr", "eol", "--", "scripts/gate", ".githooks/pre-push")
    assert out.splitlines() == [
        "scripts/gate: eol: lf",
        ".githooks/pre-push: eol: lf",
    ]
