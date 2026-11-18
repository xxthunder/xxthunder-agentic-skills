"""The closed-loop helper `scripts/host.py`: core contract and GitHub backend.

It opens or updates a pull request and waits for CI checks on GitHub, Gitea or
Bitbucket Server. Exit codes: 0 done / green, 1 red, 2 unsupported remote,
3 host call failed. Expectations are literal values written by hand; `gh` is a
fake. No shell, so the tests run on Windows too.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

from host_fakes import (HOST, FakeBitbucket, FakeGitea, commit_on_feat, env, log, repo, run,
                        write_bitbucket_profile, write_gh, write_tea, write_tea_config)

GH_URL = "https://github.com/o/r.git"
BODY = "body.md"


def load_host():
    spec = importlib.util.spec_from_file_location("host", HOST)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def pr_args(work: Path, body: Path) -> list:
    return ["pr", work, "--base", "develop", "--head", "feat", "--title", "T",
            "--body-file", body]


# ---------- split_remote ----------


@pytest.mark.parametrize("url, expected", [
    ("https://h/org/repo.git", ("h", "org/repo")),
    ("git@h:org/repo.git", ("h", "org/repo")),
    ("ssh://git@h:7999/proj/repo.git", ("h", "proj/repo")),
    ("https://h/scm/PROJ/repo.git", ("h", "scm/PROJ/repo")),
    ("/srv/git/repo.git", (None, "/srv/git/repo")),
    ("file:///srv/git/repo.git", (None, "/srv/git/repo")),
])
def test_split_remote(url, expected):
    assert load_host().split_remote(url) == expected


def test_split_remote_ignores_port_and_user():
    assert load_host().split_remote("http://u@127.0.0.1:7990/org/repo") == (
        "127.0.0.1", "org/repo")


# ---------- GitHub backend ----------


def test_github_pr_creates(tmp_path):
    bin_dir = write_gh(tmp_path, token={"github.com": "t"}, pr_list="",
                       create_url="https://github.com/o/r/pull/7")
    work = repo(tmp_path, GH_URL)
    body = tmp_path / BODY
    body.write_text("B", encoding="utf-8")
    r = run(*pr_args(work, body), env=env(tmp_path, bin_dir))
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == {
        "backend": "github", "action": "created",
        "url": "https://github.com/o/r/pull/7",
    }
    assert ["pr", "create", "--base", "develop", "--head", "feat", "--title", "T",
            "--body-file", str(body)] in log(tmp_path)


def test_github_pr_on_container_worktree(tmp_path):
    """A worktree made in a dev container names a container path in its `.git` file."""
    bin_dir = write_gh(tmp_path, token={"github.com": "t"}, pr_list="",
                       create_url="https://github.com/o/r/pull/7")
    checkout = tmp_path / "repo"
    checkout.mkdir()
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com"]
    subprocess.run([*git, "init", "-q", "-b", "develop"], cwd=checkout, check=True,
                   capture_output=True)
    subprocess.run([*git, "remote", "add", "origin", GH_URL], cwd=checkout, check=True,
                   capture_output=True)
    subprocess.run([*git, "commit", "-q", "--allow-empty", "-m", "init"], cwd=checkout,
                   check=True, capture_output=True)
    subprocess.run([*git, "worktree", "add", "-q", ".worktrees/t", "-b", "feat"],
                   cwd=checkout, check=True, capture_output=True)
    work = checkout / ".worktrees" / "t"
    gitfile = "gitdir: /workspaces/repo/.git/worktrees/t\n"
    # Git for Windows hides .git, and Windows refuses to open a hidden file for writing.
    (work / ".git").unlink()
    (work / ".git").write_text(gitfile, encoding="utf-8", newline="\n")
    body = tmp_path / BODY
    body.write_text("B", encoding="utf-8")
    r = run(*pr_args(work, body), env=env(tmp_path, bin_dir))
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == {
        "backend": "github", "action": "created",
        "url": "https://github.com/o/r/pull/7",
    }
    assert (work / ".git").read_bytes() == gitfile.encode("utf-8")


def test_pr_on_unmatched_container_gitdir(tmp_path):
    """No `.git/worktrees/<name>` matches the container path: exit 3, the path named."""
    bin_dir = write_gh(tmp_path, token={"github.com": "t"}, pr_list="",
                       create_url="https://github.com/o/r/pull/7")
    checkout = tmp_path / "repo"
    checkout.mkdir()
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com"]
    subprocess.run([*git, "init", "-q", "-b", "develop"], cwd=checkout, check=True,
                   capture_output=True)
    subprocess.run([*git, "remote", "add", "origin", GH_URL], cwd=checkout, check=True,
                   capture_output=True)
    subprocess.run([*git, "commit", "-q", "--allow-empty", "-m", "init"], cwd=checkout,
                   check=True, capture_output=True)
    subprocess.run([*git, "worktree", "add", "-q", ".worktrees/t", "-b", "feat"],
                   cwd=checkout, check=True, capture_output=True)
    work = checkout / ".worktrees" / "t"
    gitfile = "gitdir: /workspaces/other/.git/worktrees/zz\n"
    # Git for Windows hides .git, and Windows refuses to open a hidden file for writing.
    (work / ".git").unlink()
    (work / ".git").write_text(gitfile, encoding="utf-8", newline="\n")
    body = tmp_path / BODY
    body.write_text("B", encoding="utf-8")
    r = run(*pr_args(work, body), env=env(tmp_path, bin_dir))
    assert r.returncode == 3
    assert "/workspaces/other/.git/worktrees/zz" in r.stderr
    assert (work / ".git").read_bytes() == gitfile.encode("utf-8")


def test_github_pr_updates_open_pr(tmp_path):
    url = "https://github.com/o/r/pull/3"
    bin_dir = write_gh(tmp_path, token={"github.com": "t"}, pr_list=url,
                       create_url="https://github.com/o/r/pull/99")
    work = repo(tmp_path, GH_URL)
    body = tmp_path / BODY
    body.write_text("B", encoding="utf-8")
    r = run(*pr_args(work, body), env=env(tmp_path, bin_dir))
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == {"backend": "github", "action": "updated", "url": url}
    calls = log(tmp_path)
    assert ["pr", "edit", url, "--title", "T", "--body-file", str(body)] in calls
    assert not [c for c in calls if c[:2] == ["pr", "create"]]


def run_(name, conclusion, status="COMPLETED"):
    """A CheckRun entry of `gh pr view --json statusCheckRollup`."""
    return {"__typename": "CheckRun", "name": name, "status": status,
            "conclusion": conclusion}


def ctx(context, state):
    """A StatusContext entry of `gh pr view --json statusCheckRollup`."""
    return {"__typename": "StatusContext", "context": context, "state": state}


def views(tmp_path):
    return [c for c in log(tmp_path) if c[:2] == ["pr", "view"]]


OLD = "0" * 40  # a SHA that is not the local commit of `feat`


def checks(tmp_path, *extra, **gh_config):
    """Run `host.py checks` on GitHub against a fake `gh` configured by gh_config.

    The worktree holds a commit on `feat`. `heads` defaults to that commit; in a
    `heads` list given by the test, None stands for that commit.
    """
    work = repo(tmp_path, GH_URL)
    sha = commit_on_feat(work)
    heads = gh_config.pop("heads", [sha])
    heads = [sha if h is None else h for h in heads]
    bin_dir = write_gh(tmp_path, token={"github.com": "t"}, heads=heads, **gh_config)
    return run("checks", work, "--head", "feat", *extra, env=env(tmp_path, bin_dir))


def test_github_checks_green_lists_checks(tmp_path):
    r = checks(tmp_path, rollups=[[run_("build", "SUCCESS"), ctx("ci/lint", "SUCCESS")]])
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == {
        "backend": "github", "state": "green",
        "checks": [{"name": "build", "state": "SUCCESS"},
                   {"name": "ci/lint", "state": "SUCCESS"}],
    }
    calls = log(tmp_path)
    assert ["pr", "view", "feat", "--json", "headRefOid,statusCheckRollup"] in calls
    assert not [c for c in calls if c[:2] == ["pr", "checks"]]


def test_github_checks_red_lists_green_and_red(tmp_path):
    r = checks(tmp_path, rollups=[[run_("build", "SUCCESS"), run_("test", "FAILURE")]])
    assert r.returncode == 1, r.stderr
    assert json.loads(r.stdout) == {
        "backend": "github", "state": "red",
        "checks": [{"name": "build", "state": "SUCCESS"},
                   {"name": "test", "state": "FAILURE"}],
    }


def test_github_checks_waits_for_a_first_check(tmp_path):
    r = checks(tmp_path, "--interval", "0", rollups=[[], [run_("build", "SUCCESS")]])
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["state"] == "green"
    assert len(views(tmp_path)) == 2


@pytest.mark.parametrize("pending", [
    run_("test", "", "IN_PROGRESS"),
    run_("test", "", "QUEUED"),
    ctx("ci/x", "PENDING"),
    ctx("ci/x", "EXPECTED"),
])
def test_github_checks_waits_while_a_check_runs(tmp_path, pending):
    r = checks(tmp_path, "--interval", "0", rollups=[
        [run_("build", "SUCCESS"), pending],
        [run_("build", "SUCCESS"), run_("test", "SUCCESS")],
    ])
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["state"] == "green"
    assert len(views(tmp_path)) == 2


def test_github_checks_never_reported_times_out(tmp_path):
    r = checks(tmp_path, "--interval", "0.05", "--timeout", "2", rollups=[[]])
    assert r.returncode == 3
    assert "timed out" in r.stderr
    assert r.stdout == ""
    assert len(views(tmp_path)) >= 2


def test_github_checks_stale_green_never_decides(tmp_path):
    # first answer: the previous commit, green; second: the pushed commit, red
    r = checks(tmp_path, "--interval", "0", heads=[OLD, None],
               rollups=[[run_("build", "SUCCESS")], [run_("build", "FAILURE")]])
    assert r.returncode == 1, r.stderr
    assert json.loads(r.stdout)["state"] == "red"
    assert len(views(tmp_path)) == 2


def test_github_checks_stale_red_never_decides(tmp_path):
    # first answer: the previous commit, red; second: the pushed commit, green
    r = checks(tmp_path, "--interval", "0", heads=[OLD, None],
               rollups=[[run_("build", "FAILURE")], [run_("build", "SUCCESS")]])
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["state"] == "green"
    assert len(views(tmp_path)) == 2


def test_github_checks_head_never_reaches_pushed_commit_times_out(tmp_path):
    r = checks(tmp_path, "--interval", "0.05", "--timeout", "1", heads=[OLD],
               rollups=[[run_("build", "SUCCESS")]])
    assert r.returncode == 3
    assert "timed out" in r.stderr
    assert r.stdout == ""
    assert len(views(tmp_path)) >= 2


def test_github_checks_head_not_a_branch_is_exit_3(tmp_path):
    bin_dir = write_gh(tmp_path, token={"github.com": "t"}, heads=[OLD],
                       rollups=[[run_("build", "SUCCESS")]])
    work = repo(tmp_path, GH_URL)  # no commit, no branch `feat`
    r = run("checks", work, "--head", "feat", env=env(tmp_path, bin_dir))
    assert r.returncode == 3
    assert "feat" in r.stderr
    assert not views(tmp_path)


def test_github_checks_skipped_and_neutral_pass(tmp_path):
    r = checks(tmp_path, rollups=[[run_("build", "SUCCESS"), run_("docs", "SKIPPED"),
                                   run_("lint", "NEUTRAL")]])
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["state"] == "green"
    assert out["checks"] == [{"name": "build", "state": "SUCCESS"},
                             {"name": "docs", "state": "SKIPPED"},
                             {"name": "lint", "state": "NEUTRAL"}]


def test_github_checks_hung_view_is_bounded_by_timeout(tmp_path):
    r = checks(tmp_path, "--interval", "0.05", "--timeout", "1", view_sleep=5,
               rollups=[[run_("build", "SUCCESS")]])
    assert r.returncode == 3
    assert "timed out" in r.stderr


@pytest.mark.parametrize("failed", [
    run_("x", "FAILURE"),
    run_("x", "CANCELLED"),
    run_("x", "TIMED_OUT"),
    run_("x", "ACTION_REQUIRED"),
    run_("x", "STARTUP_FAILURE"),
    run_("x", "STALE"),
    ctx("x", "FAILURE"),
    ctx("x", "ERROR"),
])
def test_github_checks_red_conclusions(tmp_path, failed):
    r = checks(tmp_path, rollups=[[run_("build", "SUCCESS"), failed]])
    assert r.returncode == 1, r.stderr
    assert json.loads(r.stdout)["state"] == "red"


# ---------- backend choice and exit codes ----------


def bare_repo(tmp_path: Path) -> Path:
    path = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(path)], check=True,
                   capture_output=True)
    return path


def test_hostless_remote_goes_to_github(tmp_path):
    bin_dir = write_gh(tmp_path, create_url="https://github.com/o/r/pull/1")
    work = repo(tmp_path, str(bare_repo(tmp_path)))
    body = tmp_path / BODY
    body.write_text("B", encoding="utf-8")
    r = run(*pr_args(work, body), env=env(tmp_path, bin_dir))
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["backend"] == "github"


def test_hostless_remote_gh_fails_is_unsupported(tmp_path):
    bin_dir = write_gh(tmp_path, fail={"pr create": {
        "exit": 1, "stderr": "none of the git remotes configured for this repository"
                             " point to a known GitHub host\n"}})
    work = repo(tmp_path, str(bare_repo(tmp_path)))
    body = tmp_path / BODY
    body.write_text("B", encoding="utf-8")
    r = run(*pr_args(work, body), env=env(tmp_path, bin_dir))
    assert r.returncode == 2
    assert r.stderr.startswith("unsupported remote")


def test_unserved_host_is_unsupported(tmp_path):
    bitbucket = tmp_path / ".bitbucket"
    bitbucket.mkdir()
    (bitbucket / "profiles.json").write_text(json.dumps({"profiles": {"work": {
        "url": "https://bitbucket.example.com", "token": "x"}}}), encoding="utf-8")
    tea = tmp_path / "xdg" / "tea"
    tea.mkdir(parents=True)
    (tea / "config.yml").write_text(
        "logins:\n  - name: home\n    url: https://gitea.example.com\n    token: y\n",
        encoding="utf-8")
    bin_dir = write_gh(tmp_path, token={}, create_url="https://github.com/o/r/pull/1")
    work = repo(tmp_path, "https://forge.example.com/o/r.git")
    body = tmp_path / BODY
    body.write_text("B", encoding="utf-8")
    r = run(*pr_args(work, body), env=env(tmp_path, bin_dir))
    assert r.returncode == 2
    assert "forge.example.com" in r.stderr
    assert not [c for c in log(tmp_path) if c[:2] == ["pr", "create"]]


def test_gh_failure_on_served_host_is_exit_3(tmp_path):
    bin_dir = write_gh(tmp_path, token={"github.com": "t"}, pr_list="",
                       fail={"pr create": {"exit": 1, "stderr": "boom from gh\n"}})
    work = repo(tmp_path, GH_URL)
    body = tmp_path / BODY
    body.write_text("B", encoding="utf-8")
    r = run(*pr_args(work, body), env=env(tmp_path, bin_dir))
    assert r.returncode == 3
    assert "boom from gh" in r.stderr


NO_PR = {"pr view": {"exit": 1, "stderr": "no pull requests found for branch \"feat\"\n"}}


def test_github_checks_gh_error_on_served_host_is_exit_3(tmp_path):
    r = checks(tmp_path, fail=NO_PR)
    assert r.returncode == 3
    assert 'no pull requests found for branch "feat"' in r.stderr


def test_github_checks_hostless_gh_error_is_unsupported(tmp_path):
    bin_dir = write_gh(tmp_path, fail=NO_PR)
    work = repo(tmp_path, str(bare_repo(tmp_path)))
    commit_on_feat(work)
    r = run("checks", work, "--head", "feat", env=env(tmp_path, bin_dir))
    assert r.returncode == 2
    assert r.stderr.startswith("unsupported remote")


@pytest.mark.parametrize("view_raw", [
    "{}", "not json", '{"statusCheckRollup": ["x"]}',
    '{"statusCheckRollup": []}', '{"headRefOid": 7, "statusCheckRollup": []}',
])
def test_github_checks_answer_without_head_or_rollup_is_exit_3(tmp_path, view_raw):
    # a malformed answer fails at once; it is not waited out (the short timeout only
    # bounds a backend that would wait, and then "timed out" shows it did)
    r = checks(tmp_path, "--interval", "0.05", "--timeout", "2", view_raw=view_raw)
    assert r.returncode == 3
    assert r.stderr != ""
    assert "timed out" not in r.stderr
    assert "Traceback" not in r.stderr


@pytest.mark.parametrize("rollups, message", [
    ([None], "statusCheckRollup list"),
    ([["x"]], "not an object"),
])
def test_github_checks_malformed_rollup_for_our_head_is_exit_3(tmp_path, rollups, message):
    # the head matches the local commit, so the rollup itself is read and rejected
    r = checks(tmp_path, "--interval", "0.05", "--timeout", "2", rollups=rollups)
    assert r.returncode == 3
    assert message in r.stderr
    assert "timed out" not in r.stderr
    assert "Traceback" not in r.stderr


# ---------- remote parsing and secrets ----------


def test_scp_remote_host_is_lowercased():
    assert load_host().split_remote("git@GitHub.example.com:o/r.git") == (
        "github.example.com", "o/r")


def test_token_never_printed(tmp_path):
    secret = "tok-SECRET-123"
    body = tmp_path / BODY
    body.write_text("B", encoding="utf-8")
    outputs = []

    # pr, create path
    d1 = tmp_path / "create"
    d1.mkdir()
    bin_dir = write_gh(d1, token={"github.com": secret}, pr_list="",
                       create_url="https://github.com/o/r/pull/7")
    outputs.append(run(*pr_args(repo(d1, GH_URL), body), env=env(d1, bin_dir)))

    # checks, red path
    d2 = tmp_path / "red"
    d2.mkdir()
    work2 = repo(d2, GH_URL)
    sha = commit_on_feat(work2)
    bin_dir = write_gh(d2, token={"github.com": secret}, heads=[sha],
                       rollups=[[run_("build", "FAILURE")]])
    outputs.append(run("checks", work2, "--head", "feat",
                       env=env(d2, bin_dir)))

    # gh failure path
    d3 = tmp_path / "fail"
    d3.mkdir()
    bin_dir = write_gh(d3, token={"github.com": secret}, pr_list="",
                       fail={"pr create": {"exit": 1, "stderr": "boom from gh\n"}})
    outputs.append(run(*pr_args(repo(d3, GH_URL), body), env=env(d3, bin_dir)))

    assert [o.returncode for o in outputs] == [0, 1, 3]
    for o in outputs:
        assert secret not in o.stdout
        assert secret not in o.stderr


# ---------- credentials in the remote, missing origin, usage, help ----------


def test_remote_credential_never_printed(tmp_path):
    body = tmp_path / BODY
    body.write_text("B", encoding="utf-8")

    # unserved host: exit 2, the host is named, the credential is not
    d1 = tmp_path / "unserved"
    d1.mkdir()
    bin_dir = write_gh(d1, token={})
    work = repo(d1, "https://u:SECRET123@forge.example.com/o/r.git")
    r1 = run(*pr_args(work, body), env=env(d1, bin_dir))
    assert r1.returncode == 2
    assert r1.stderr.startswith("unsupported remote")
    assert "forge.example.com" in r1.stderr

    # served host, gh fails: exit 3, the credential is not printed
    d2 = tmp_path / "served"
    d2.mkdir()
    bin_dir = write_gh(d2, token={"github.com": "t"}, pr_list="",
                       fail={"pr create": {"exit": 1, "stderr": "boom from gh\n"}})
    work = repo(d2, "https://u:SECRET123@github.com/o/r.git")
    r2 = run(*pr_args(work, body), env=env(d2, bin_dir))
    assert r2.returncode == 3

    for r in (r1, r2):
        assert "SECRET123" not in r.stdout
        assert "SECRET123" not in r.stderr


def test_no_origin_is_unsupported(tmp_path):
    bin_dir = write_gh(tmp_path, token={"github.com": "t"})
    work = tmp_path / "work"
    work.mkdir()
    subprocess.run(["git", "init", "-q", str(work)], check=True, capture_output=True)
    body = tmp_path / BODY
    body.write_text("B", encoding="utf-8")
    r = run(*pr_args(work, body), env=env(tmp_path, bin_dir))
    assert r.returncode == 2
    assert "origin" in r.stderr


def test_usage_error_is_exit_3(tmp_path):
    bin_dir = write_gh(tmp_path, token={"github.com": "t"})
    work = repo(tmp_path, GH_URL)
    r = run("pr", work, "--base", "develop", "--head", "feat", "--body-file", BODY,
            env=env(tmp_path, bin_dir))
    assert r.returncode == 3
    assert "usage" in r.stderr.lower()


def test_help_describes_output(tmp_path):
    r = run("--help", env=env(tmp_path, write_gh(tmp_path)))
    assert r.returncode == 0, r.stderr
    assert "url" in r.stdout
    assert "unsupported remote" in r.stdout
    for backend in ("GitHub", "Gitea", "Bitbucket"):
        assert backend in r.stdout


def test_relative_body_file_github(tmp_path):
    bin_dir = write_gh(tmp_path, token={"github.com": "t"}, pr_list="",
                       create_url="https://github.com/o/r/pull/7")
    work = repo(tmp_path, GH_URL)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / BODY).write_text("the relative body", encoding="utf-8")
    r = run("pr", work, "--base", "develop", "--head", "feat", "--title", "T",
            "--body-file", BODY, env=env(tmp_path, bin_dir), cwd=elsewhere)
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "fake-log.jsonl.body").read_text(encoding="utf-8") == "the relative body"


# ---------- backend precedence on one host ----------


def test_backend_precedence_same_host(tmp_path):
    body = tmp_path / BODY
    body.write_text("B", encoding="utf-8")

    # Bitbucket profile, tea login and gh token all serve 127.0.0.1: Bitbucket wins
    d1 = tmp_path / "bb"
    d1.mkdir()
    bb = FakeBitbucket().start()
    try:
        bb.created = {"links": {"self": [{"href": "http://127.0.0.1/pull/1"}]}}
        write_bitbucket_profile(d1, bb.port)
        write_tea_config(d1, bb.port)
        bin_dir = write_gh(d1, token={"127.0.0.1": "t"})
        work = repo(d1, f"http://127.0.0.1:{bb.port}/scm/PROJ/repo.git")
        r1 = run(*pr_args(work, body), env=env(d1, bin_dir))
    finally:
        bb.stop()
    assert r1.returncode == 0, r1.stderr
    assert json.loads(r1.stdout)["backend"] == "bitbucket"

    # tea login and gh token serve 127.0.0.1: Gitea wins
    d2 = tmp_path / "gitea"
    d2.mkdir()
    gitea = FakeGitea(d2 / "tea-created").start()
    try:
        gitea.pulls_after = [{"number": 5, "html_url": "http://127.0.0.1/o/r/pulls/5",
                              "head": {"ref": "feat", "sha": "abc"}}]
        write_tea_config(d2, gitea.port)
        write_gh(d2, token={"127.0.0.1": "t"})
        bin_dir = write_tea(d2)
        work = repo(d2, f"http://127.0.0.1:{gitea.port}/o/r.git")
        e = env(d2, bin_dir)
        e["FAKE_TEA_MARK"] = str(d2 / "tea-created")
        r2 = run(*pr_args(work, body), env=e)
    finally:
        gitea.stop()
    assert r2.returncode == 0, r2.stderr
    assert json.loads(r2.stdout)["backend"] == "gitea"
