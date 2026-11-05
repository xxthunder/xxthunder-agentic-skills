"""The closed-loop helper `scripts/loop.py`, exercised as a subprocess.

It owns the mechanical lookups of the closed-loop skill: a remote's checkout
path, a row of a registry table, the first matching glob, and the loop's state
file in the git dir. Output is JSON on stdout, errors go to stderr. Expectations
are literal values written by hand. No shell, so the tests run on Windows too.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
LOOP = REPO_ROOT / "plugins" / "xxthunder-dev-skills" / "scripts" / "loop.py"


def run(*args, cwd=None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(LOOP), *map(str, args)],
        capture_output=True, text=True, cwd=str(cwd) if cwd else None,
    )


def ok(*args, cwd=None):
    r = run(*args, cwd=cwd)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def git(*args, cwd: Path) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=T", "-c", "user.email=t@example.com", *args],
        cwd=str(cwd), check=True, capture_output=True, text=True,
    ).stdout.strip()


# ---------- checkout ----------


def test_checkout_https():
    assert ok("checkout", "https://example.com/team/notes.git") == {
        "org": "team", "repo": "notes",
    }
    assert ok("checkout", "https://example.com/team/notes")["repo"] == "notes"


def test_checkout_prints_no_path():
    assert "path" not in ok("checkout", "https://example.com/team/notes.git")


def test_checkout_scp():
    assert ok("checkout", "git@example.com:team/notes.git") == {
        "org": "team", "repo": "notes",
    }


def test_checkout_bitbucket_ssh():
    assert ok("checkout", "ssh://git@git.example.com:7999/~alice/notes.git") == {
        "org": "~alice", "repo": "notes",
    }


# ---------- row ----------

REGISTRY = (
    "# Repos\n\n"
    "| Repo | Remote | IDs | What it is |\n"
    "| --- | --- | --- | --- |\n"
    "| [other](https://example.com/other) | git@example.com:t/other.git | OTH | Another |\n"
    "| [demo](https://example.com/demo) | git@example.com:t/demo.git | DEMO | The demo |\n"
)


def write(tmp_path: Path, text: str, newline="\n") -> Path:
    f = tmp_path / "repos.md"
    f.write_text(text, encoding="utf-8", newline=newline)
    return f


def test_row_finds_by_column(tmp_path):
    f = write(tmp_path, REGISTRY)
    assert ok("row", f, "Repo,Remote", "IDs", "DEMO") == {
        "Repo": "[demo](https://example.com/demo)",
        "Remote": "git@example.com:t/demo.git",
        "IDs": "DEMO",
        "What it is": "The demo",
    }


def test_row_by_link_text(tmp_path):
    f = write(tmp_path, REGISTRY)
    got = ok("row", f, "Repo,Remote", "Repo", "demo")
    assert got["Repo"] == "[demo](https://example.com/demo)"
    assert got["IDs"] == "DEMO"


def test_row_second_table(tmp_path):
    text = REGISTRY + (
        "\n## Gate corrections\n\n"
        "| Repo | Gate | Runs in |\n"
        "| --- | --- | --- |\n"
        "| demo | `make check` | host |\n"
    )
    f = write(tmp_path, text)
    assert ok("row", f, "Repo,Gate", "Repo", "demo") == {
        "Repo": "demo", "Gate": "`make check`", "Runs in": "host",
    }


def test_row_matches_backticked_cell_without_backticks(tmp_path):
    text = (
        "| Repo | Gate | Runs in |\n"
        "| --- | --- | --- |\n"
        "| other | `make test` | host |\n"
        "| demo | `make check` | host |\n"
    )
    f = write(tmp_path, text)
    got = ok("row", f, "Repo,Gate", "Gate", "make check")
    assert got == {"Repo": "demo", "Gate": "`make check`", "Runs in": "host"}


def test_row_bare_prefix_cell_found_with_or_without_dash(tmp_path):
    text = (
        "| Repo | Remote | IDs |\n"
        "| --- | --- | --- |\n"
        "| xas | git@example.com:t/xas.git | XAS |\n"
    )
    f = write(tmp_path, text)
    want = {"Repo": "xas", "Remote": "git@example.com:t/xas.git", "IDs": "XAS"}
    assert ok("row", f, "Repo,Remote", "IDs", "XAS-") == want
    assert ok("row", f, "Repo,Remote", "IDs", "XAS") == want


def test_row_backticked_dash_cell_matches_bare_value(tmp_path):
    text = (
        "| Repo | Remote | IDs |\n"
        "| --- | --- | --- |\n"
        "| demo | git@example.com:t/demo.git | `DEMO-` |\n"
    )
    f = write(tmp_path, text)
    assert ok("row", f, "Repo,Remote", "IDs", "DEMO")["Repo"] == "demo"


def test_row_escaped_pipe(tmp_path):
    text = (
        "| Repo | Note | Last |\n"
        "| --- | --- | --- |\n"
        "| demo | a \\| b | z |\n"
    )
    f = write(tmp_path, text)
    got = ok("row", f, "Repo,Note", "Repo", "demo")
    assert got["Note"] == "a | b"
    assert got["Last"] == "z"
    assert list(got) == ["Repo", "Note", "Last"]


def test_row_not_found_exit_1(tmp_path):
    f = write(tmp_path, REGISTRY)
    r = run("row", f, "Repo,Remote", "IDs", "NOPE")
    assert r.returncode == 1
    assert "not found" in r.stderr
    r = run("row", f, "Repo,Gate", "Repo", "demo")  # no such table
    assert r.returncode == 1
    assert "not found" in r.stderr


def test_row_crlf(tmp_path):
    f = write(tmp_path, REGISTRY, newline="\r\n")
    assert b"\r\n" in f.read_bytes()
    got = ok("row", f, "Repo,Remote", "IDs", "DEMO")
    assert got["What it is"] == "The demo"
    assert got["IDs"] == "DEMO"


# ---------- first ----------


def test_first_in_given_order(tmp_path):
    (tmp_path / "Jenkinsfile").write_text("x", encoding="utf-8")
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "ci.yml").write_text("x", encoding="utf-8")
    assert ok("first", tmp_path, "pypeline.yaml", ".github/workflows/*.yml", "Jenkinsfile") == {
        "match": ".github/workflows/ci.yml", "pattern": ".github/workflows/*.yml",
    }


def test_first_earlier_glob_wins_over_sort_order(tmp_path):
    (tmp_path / "Jenkinsfile").write_text("x", encoding="utf-8")
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "ci.yml").write_text("x", encoding="utf-8")
    assert ok("first", tmp_path, "Jenkinsfile", ".github/workflows/*.yml") == {
        "match": "Jenkinsfile", "pattern": "Jenkinsfile",
    }


def test_first_sorted_first_of_several(tmp_path):
    (tmp_path / "b.yml").write_text("x", encoding="utf-8")
    (tmp_path / "a.yml").write_text("x", encoding="utf-8")
    assert ok("first", tmp_path, "*.yml") == {"match": "a.yml", "pattern": "*.yml"}


def test_first_none(tmp_path):
    assert ok("first", tmp_path, "pypeline.yaml", "Jenkinsfile") == {"match": None, "pattern": None}


# ---------- state ----------


def make_repo(tmp_path: Path) -> Path:
    r = tmp_path / "r"
    r.mkdir()
    git("init", "-q", cwd=r)
    for key, value in (("user.name", "Test"), ("user.email", "test@example.com"),
                       ("commit.gpgsign", "false")):
        git("config", key, value, cwd=r)
    (r / "f.txt").write_text("x", encoding="utf-8")
    git("add", "f.txt", cwd=r)
    git("commit", "-q", "-m", "init", cwd=r)
    return r


def test_state_empty(tmp_path):
    r = make_repo(tmp_path)
    assert ok("state", r) == {}


def test_state_roundtrip(tmp_path):
    r = make_repo(tmp_path)
    ok("state", r, "item=DEMO-007", "step=gate", "fix_rounds=0")
    got = ok("state", r, "fix_rounds=1")
    assert got == {"item": "DEMO-007", "step": "gate", "fix_rounds": 1}
    assert isinstance(got["fix_rounds"], int)
    git_dir = Path(git("rev-parse", "--absolute-git-dir", cwd=r))
    assert json.loads((git_dir / "closed-loop.json").read_text(encoding="utf-8")) == got
    assert git("status", "--porcelain", cwd=r) == ""
    assert ok("state", r) == got


def test_state_in_linked_worktree(tmp_path):
    r = make_repo(tmp_path)
    wt = tmp_path / "wt"
    git("worktree", "add", "-q", "-b", "feature/x", str(wt), cwd=r)
    ok("state", wt, "item=DEMO-007", "fix_rounds=2")
    wt_git = Path(git("rev-parse", "--absolute-git-dir", cwd=wt))
    main_git = Path(git("rev-parse", "--absolute-git-dir", cwd=r))
    assert wt_git != main_git
    assert json.loads((wt_git / "closed-loop.json").read_text(encoding="utf-8")) == {
        "item": "DEMO-007", "fix_rounds": 2,
    }
    assert not (main_git / "closed-loop.json").exists()
    assert ok("state", r) == {}
    assert git("status", "--porcelain", cwd=wt) == ""


def test_state_merges_without_item_check(tmp_path):
    r = make_repo(tmp_path)
    ok("state", r, "item=DEMO-007")
    assert ok("state", r, "item=OTHER-001", "step=plan") == {"item": "OTHER-001", "step": "plan"}


# ---------- guard ----------


def commit_files(r: Path, files: dict[str, str], msg: str) -> str:
    for name, text in files.items():
        f = r / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")
        git("add", name, cwd=r)
    git("commit", "-q", "-m", msg, cwd=r)
    return git("rev-parse", "HEAD", cwd=r)


def guard_repo(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    """Base, tests, impl and more-impl commits; the tests commit adds two test files."""
    r = make_repo(tmp_path)
    base = commit_files(r, {"scripts/gate": "gate v1\n", "src/app.py": "v1\n"}, "base")
    tests = commit_files(
        r, {"tests/test_a.py": "a\n", "tests/test_b.py": "b\n"}, "tests"
    )
    return r, {"base": base, "tests": tests}


def test_guard_clean(tmp_path):
    r, c = guard_repo(tmp_path)
    impl = commit_files(r, {"src/app.py": "v2\n", "src/new.py": "n\n"}, "impl")
    got = ok(
        "guard", r, "--tests", f"{c['base']}..{c['tests']}",
        "--impl", f"{c['tests']}..{impl}", "--protect", "scripts/gate",
    )
    assert got == {"ok": True}


def test_guard_impl_changes_test_file(tmp_path):
    r, c = guard_repo(tmp_path)
    impl = commit_files(r, {"src/app.py": "v2\n", "tests/test_a.py": "a changed\n"}, "impl")
    res = run(
        "guard", r, "--tests", f"{c['base']}..{c['tests']}",
        "--impl", f"{c['tests']}..{impl}",
    )
    assert res.returncode == 1
    assert json.loads(res.stdout) == {"ok": False, "touched": ["tests/test_a.py"]}


def test_guard_protect_gate(tmp_path):
    r, c = guard_repo(tmp_path)
    impl = commit_files(r, {"src/app.py": "v2\n", "scripts/gate": "gate v2\n"}, "impl")
    res = run(
        "guard", r, "--tests", f"{c['base']}..{c['tests']}",
        "--impl", f"{c['tests']}..{impl}", "--protect", "scripts/gate",
    )
    assert res.returncode == 1
    assert json.loads(res.stdout) == {"ok": False, "touched": ["scripts/gate"]}
    # without --protect the gate change is not a violation
    assert ok(
        "guard", r, "--tests", f"{c['base']}..{c['tests']}",
        "--impl", f"{c['tests']}..{impl}",
    ) == {"ok": True}


def test_guard_ranges_with_several_commits(tmp_path):
    r = make_repo(tmp_path)
    base = commit_files(r, {"scripts/gate": "g\n"}, "base")
    commit_files(r, {"tests/test_a.py": "a\n"}, "tests 1")
    tests = commit_files(r, {"tests/test_b.py": "b\n"}, "tests 2")
    commit_files(r, {"src/app.py": "v1\n"}, "impl 1")
    commit_files(r, {"src/app.py": "v2\n", "docs/x.md": "x\n"}, "impl 2")
    impl = commit_files(r, {"src/other.py": "o\n"}, "impl 3")
    tests_range, impl_range = f"{base}..{tests}", f"{tests}..{impl}"
    assert ok("guard", r, "--tests", tests_range, "--impl", impl_range,
              "--protect", "scripts/gate") == {"ok": True}
    # a touch in the first tests commit, made by a later impl commit, is caught
    bad = commit_files(r, {"tests/test_a.py": "a2\n"}, "impl 4")
    res = run("guard", r, "--tests", tests_range, "--impl", f"{tests}..{bad}")
    assert res.returncode == 1
    assert json.loads(res.stdout) == {"ok": False, "touched": ["tests/test_a.py"]}


def test_guard_touched_sorted_and_unique(tmp_path):
    r, c = guard_repo(tmp_path)
    commit_files(r, {"tests/test_b.py": "b1\n", "scripts/gate": "g2\n"}, "impl 1")
    impl = commit_files(
        r, {"tests/test_b.py": "b2\n", "tests/test_a.py": "a2\n", "scripts/gate": "g3\n"}, "impl 2"
    )
    res = run(
        "guard", r, "--tests", f"{c['base']}..{c['tests']}",
        "--impl", f"{c['tests']}..{impl}", "--protect", "scripts/gate",
    )
    assert res.returncode == 1
    assert json.loads(res.stdout) == {
        "ok": False, "touched": ["scripts/gate", "tests/test_a.py", "tests/test_b.py"],
    }


def test_guard_takes_several_tests_ranges(tmp_path):
    r = make_repo(tmp_path)
    base = commit_files(r, {"src/app.py": "v1\n"}, "base")
    t1 = commit_files(r, {"tests/test_a.py": "a\n"}, "tests unit 1")
    i1 = commit_files(r, {"src/app.py": "v2\n"}, "impl unit 1")
    t2 = commit_files(r, {"tests/test_b.py": "b\n"}, "tests unit 2")
    ranges = ["--tests", f"{base}..{t1}", "--tests", f"{i1}..{t2}"]
    # a fix round that changes the first unit's test file is caught
    bad = commit_files(r, {"src/app.py": "v3\n", "tests/test_a.py": "a2\n"}, "fix round")
    res = run("guard", r, *ranges, "--impl", f"{t2}..{bad}")
    assert res.returncode == 1
    assert json.loads(res.stdout) == {"ok": False, "touched": ["tests/test_a.py"]}
    # a fix round that changes only src files passes
    good = commit_files(r, {"src/app.py": "v4\n", "src/new.py": "n\n"}, "fix round 2")
    assert ok("guard", r, *ranges, "--impl", f"{bad}..{good}") == {"ok": True}
    # the second range's file is protected too: the union, not just the first range
    bad_b = commit_files(r, {"tests/test_b.py": "b2\n"}, "fix round 3")
    res = run("guard", r, *ranges, "--impl", f"{good}..{bad_b}")
    assert res.returncode == 1
    assert json.loads(res.stdout) == {"ok": False, "touched": ["tests/test_b.py"]}


def test_guard_tests_range_counts_its_net_diff(tmp_path):
    r = make_repo(tmp_path)
    base = commit_files(r, {"src/app.py": "v1\n"}, "base")
    commit_files(r, {"tests/test_a.py": "a\n", "tests/scratch.py": "s\n"}, "tests unit 1")
    git("rm", "-q", "tests/scratch.py", cwd=r)
    git("commit", "-q", "-m", "tests unit 1, drop scratch", cwd=r)
    t1 = git("rev-parse", "HEAD", cwd=r)
    t2 = commit_files(r, {"tests/test_b.py": "b\n"}, "tests unit 2")
    ranges = ["--tests", f"{base}..{t1}", "--tests", f"{t1}..{t2}"]
    # a path the range added and deleted again is not protected
    impl = commit_files(r, {"tests/scratch.py": "again\n", "src/app.py": "v2\n"}, "impl")
    assert ok("guard", r, *ranges, "--impl", f"{t2}..{impl}") == {"ok": True}
    # the file the range kept is
    bad = commit_files(r, {"tests/test_a.py": "a2\n"}, "impl 2")
    res = run("guard", r, *ranges, "--impl", f"{impl}..{bad}")
    assert res.returncode == 1
    assert json.loads(res.stdout) == {"ok": False, "touched": ["tests/test_a.py"]}


def test_guard_bad_later_tests_range_exits_2(tmp_path):
    r = make_repo(tmp_path)
    base = commit_files(r, {"src/app.py": "v1\n"}, "base")
    t1 = commit_files(r, {"tests/test_a.py": "a\n"}, "tests")
    impl = commit_files(r, {"src/app.py": "v2\n"}, "impl")
    res = run(
        "guard", r, "--tests", f"{base}..{t1}", "--tests", "nonexistent..HEAD",
        "--impl", f"{t1}..{impl}",
    )
    assert res.returncode == 2


# ---------- commit-impl, fixup, fold ----------


def subject(r: Path, rev: str = "HEAD") -> str:
    return git("log", "-1", "--format=%s", rev, cwd=r)


def body(r: Path, rev: str = "HEAD") -> str:
    return git("log", "-1", "--format=%b", rev, cwd=r)


def stage(r: Path, name: str, text: str) -> None:
    (r / name).write_text(text, encoding="utf-8")
    git("add", name, cwd=r)


def test_commit_impl_makes_an_amend_commit(tmp_path):
    r = make_repo(tmp_path)
    b = commit_files(r, {"t.py": "test\n"}, "test: pin it")
    stage(r, "impl.py", "impl\n")
    msg = tmp_path / "dir with space" / "msg.txt"
    msg.parent.mkdir()
    msg.write_text("feat: make it pass\n\nwhy\n", encoding="utf-8")
    got = ok("commit-impl", r, b, msg)
    assert got == {"commit": git("rev-parse", "HEAD", cwd=r)}
    assert git("rev-list", "--count", f"{b}..HEAD", cwd=r) == "1"
    assert subject(r) == f"amend! {b}"
    assert body(r) == "feat: make it pass\n\nwhy"


def test_commit_impl_nothing_staged_exits_1(tmp_path):
    r = make_repo(tmp_path)
    b = commit_files(r, {"t.py": "test\n"}, "test: pin it")
    msg = tmp_path / "msg.txt"
    msg.write_text("feat: x\n", encoding="utf-8")
    assert run("commit-impl", r, b, msg).returncode == 1
    assert git("rev-parse", "HEAD", cwd=r) == b


def test_fixup_makes_a_fixup_commit(tmp_path):
    r = make_repo(tmp_path)
    b = commit_files(r, {"t.py": "test\n"}, "test: pin it")
    stage(r, "t.py", "test fixed\n")
    got = ok("fixup", r, b)
    assert got == {"commit": git("rev-parse", "HEAD", cwd=r)}
    assert subject(r) == f"fixup! {b}"


def test_fixup_nothing_staged_exits_1(tmp_path):
    r = make_repo(tmp_path)
    b = commit_files(r, {"t.py": "test\n"}, "test: pin it")
    assert run("fixup", r, b).returncode == 1


def fold_repo(tmp_path: Path):
    r = make_repo(tmp_path)
    base = git("rev-parse", "HEAD", cwd=r)
    b1 = commit_files(r, {"a_test.py": "a\n"}, "test: unit one")
    stage(r, "a.py", "a impl\n")
    msg = tmp_path / "msg.txt"
    msg.write_text("feat: unit one done\n", encoding="utf-8")
    ok("commit-impl", r, b1, msg)
    b2 = commit_files(r, {"b_test.py": "b\n"}, "test: unit two")
    stage(r, "b_test.py", "b fixed\n")
    ok("fixup", r, b2)
    commit_files(r, {"plain.txt": "p\n"}, "docs: plain")
    return r, base


def test_fold_squashes_amend_and_fixup_commits(tmp_path):
    r, base = fold_repo(tmp_path)
    old = git("rev-parse", "HEAD", cwd=r)
    got = ok("fold", r, base)
    new = git("rev-parse", "HEAD", cwd=r)
    assert got == {"head": new, "commits": 3}
    assert git("diff", old, "HEAD", cwd=r) == ""
    subjects = git("log", "--reverse", "--format=%s", f"{base}..HEAD", cwd=r).splitlines()
    assert subjects == ["feat: unit one done", "test: unit two", "docs: plain"]
    assert not [s for s in subjects if s.startswith(("amend! ", "fixup! "))]


def test_fold_conflict_aborts_and_keeps_head(tmp_path):
    r = make_repo(tmp_path)
    base = git("rev-parse", "HEAD", cwd=r)
    b = commit_files(r, {"c.txt": "one\n"}, "test: c")
    commit_files(r, {"c.txt": "two\n"}, "test: c again")
    stage(r, "c.txt", "conflicting\n")
    # fixup of an earlier commit conflicts with the later change to the same file
    git("-c", "core.editor=true", "commit", "-q", "--fixup", b, cwd=r)
    old = git("rev-parse", "HEAD", cwd=r)
    res = run("fold", r, base)
    assert res.returncode == 1
    assert res.stderr.strip()
    assert git("rev-parse", "HEAD", cwd=r) == old
    assert not (r / ".git" / "rebase-merge").exists()
    assert git("status", "--porcelain", cwd=r) == ""


# ---------- the loop's commits run the repo's hooks ----------


def block_commits(r: Path) -> None:
    hook = r / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8", newline="\n")
    hook.chmod(0o755)


@pytest.mark.skipif(sys.platform == "win32", reason="hook execution is unreliable on Windows")
def test_commit_impl_runs_the_pre_commit_hook(tmp_path):
    r = make_repo(tmp_path)
    b = commit_files(r, {"t.py": "test\n"}, "test: pin it")
    stage(r, "impl.py", "impl\n")
    msg = tmp_path / "msg.txt"
    msg.write_text("feat: x\n", encoding="utf-8")
    block_commits(r)
    assert run("commit-impl", r, b, msg).returncode == 1
    assert git("rev-parse", "HEAD", cwd=r) == b


@pytest.mark.skipif(sys.platform == "win32", reason="hook execution is unreliable on Windows")
def test_fixup_runs_the_pre_commit_hook(tmp_path):
    r = make_repo(tmp_path)
    b = commit_files(r, {"t.py": "test\n"}, "test: pin it")
    stage(r, "t.py", "test fixed\n")
    block_commits(r)
    assert run("fixup", r, b).returncode == 1
    assert git("rev-parse", "HEAD", cwd=r) == b
