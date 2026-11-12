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

from host_fakes import HOST, env, log, repo, run, write_gh

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


RED_TABLE = "build\tfail\t1m\thttps://example.com/run/1\n"


@pytest.mark.parametrize("checks_exit, checks_stdout, code, state", [
    (0, "", 0, "green"),
    (1, RED_TABLE, 1, "red"),
])
def test_github_checks(tmp_path, checks_exit, checks_stdout, code, state):
    bin_dir = write_gh(tmp_path, token={"github.com": "t"}, checks_exit=checks_exit,
                       checks_stdout=checks_stdout)
    work = repo(tmp_path, GH_URL)
    r = run("checks", work, "--head", "feat", env=env(tmp_path, bin_dir))
    assert r.returncode == code, r.stderr
    out = json.loads(r.stdout)
    assert out["backend"] == "github"
    assert out["state"] == state
    assert ["pr", "checks", "feat", "--watch"] in log(tmp_path)


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


NO_CHECKS = "no checks reported on the 'feat' branch\n"


def test_github_checks_gh_error_on_served_host_is_exit_3(tmp_path):
    bin_dir = write_gh(tmp_path, token={"github.com": "t"}, checks_exit=1,
                       checks_stderr=NO_CHECKS)
    work = repo(tmp_path, GH_URL)
    r = run("checks", work, "--head", "feat", env=env(tmp_path, bin_dir))
    assert r.returncode == 3
    assert "no checks reported on the 'feat' branch" in r.stderr


def test_github_checks_pending_exit_8_is_exit_3(tmp_path):
    bin_dir = write_gh(tmp_path, token={"github.com": "t"}, checks_exit=8)
    work = repo(tmp_path, GH_URL)
    r = run("checks", work, "--head", "feat", env=env(tmp_path, bin_dir))
    assert r.returncode == 3


def test_github_checks_hostless_gh_error_is_unsupported(tmp_path):
    bin_dir = write_gh(tmp_path, checks_exit=1, checks_stderr=NO_CHECKS)
    work = repo(tmp_path, str(bare_repo(tmp_path)))
    r = run("checks", work, "--head", "feat", env=env(tmp_path, bin_dir))
    assert r.returncode == 2
    assert r.stderr.startswith("unsupported remote")


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
    bin_dir = write_gh(d2, token={"github.com": secret}, checks_exit=1,
                       checks_stdout=RED_TABLE)
    outputs.append(run("checks", repo(d2, GH_URL), "--head", "feat",
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
