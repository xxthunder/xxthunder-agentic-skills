"""The Gitea backend of `scripts/host.py`: `tea` opens or edits the pull request,
the Gitea REST API finds it and reports the commit status.

`tea` is a fake that logs its arguments; the API is a local HTTP server. The
login token is `secret-t` and must never reach stdout or stderr.
"""
from __future__ import annotations

import json

import pytest

from host_fakes import FakeGitea, commit_on_feat, env, fake_bin, log, repo, run, write_tea, write_tea_config

TOKEN = "secret-t"
SHA = "abc123"


@pytest.fixture
def api(tmp_path):
    server = FakeGitea(tmp_path / "tea-created").start()
    yield server
    server.stop()


def setup(tmp_path, api, with_tea=True):
    """Fake tea, tea config for the fake API, a worktree with a matching origin."""
    bin_dir = write_tea(tmp_path) if with_tea else fake_bin(tmp_path, "unrelated", "")
    write_tea_config(tmp_path, api.port)
    work = repo(tmp_path, f"http://127.0.0.1:{api.port}/o/r.git")
    e = env(tmp_path, bin_dir)
    e["FAKE_TEA_MARK"] = str(tmp_path / "tea-created")
    return work, e


def pull(index, head="feat", url=None):
    return {"number": index, "html_url": url or f"http://127.0.0.1/o/r/pulls/{index}",
            "head": {"ref": head, "sha": SHA}}


def pr_run(tmp_path, work, e):
    body = tmp_path / "body.md"
    body.write_text("the body", encoding="utf-8")
    return run("pr", work, "--base", "develop", "--head", "feat", "--title", "T",
               "--body-file", body, env=e)


def checks_run(work, e, *extra):
    return run("checks", work, "--head", "feat", "--interval", "0", *extra, env=e)


def test_gitea_pr_creates(tmp_path, api):
    api.pulls = []
    api.pulls_after = [pull(5, url="http://127.0.0.1/o/r/pulls/5")]
    work, e = setup(tmp_path, api)
    r = pr_run(tmp_path, work, e)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == {
        "backend": "gitea", "action": "created", "url": "http://127.0.0.1/o/r/pulls/5"}
    assert ["pr", "create", "--login", "home", "--repo", "o/r", "--base", "develop",
            "--head", "feat", "--title", "T", "--description", "the body"] in log(tmp_path)
    assert TOKEN not in r.stdout + r.stderr


def test_gitea_pr_updates_open_pr(tmp_path, api):
    api.pulls = [pull(3, head="other"), pull(7, url="http://127.0.0.1/o/r/pulls/7")]
    work, e = setup(tmp_path, api)
    r = pr_run(tmp_path, work, e)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == {
        "backend": "gitea", "action": "updated", "url": "http://127.0.0.1/o/r/pulls/7"}
    calls = log(tmp_path)
    assert ["pr", "edit", "7", "--login", "home", "--repo", "o/r", "--title", "T",
            "--description", "the body"] in calls
    assert not [c for c in calls if c[:2] == ["pr", "create"]]
    assert TOKEN not in r.stdout + r.stderr


def test_gitea_api_sends_token(tmp_path, api):
    api.pulls = [pull(7)]
    work, e = setup(tmp_path, api)
    r = pr_run(tmp_path, work, e)
    assert r.returncode == 0, r.stderr
    assert api.requests, "the API was never called"
    assert all(q["headers"].get("Authorization") == f"token {TOKEN}" for q in api.requests)
    assert api.requests[0]["path"].startswith("/api/v1/repos/o/r/pulls")
    assert "state=open" in api.requests[0]["path"]


def test_gitea_checks_waits_until_final(tmp_path, api):
    api.pulls = [pull(7)]
    api.statuses = [
        {"state": "pending", "statuses": []},
        {"state": "pending", "statuses": [{"context": "ci/build", "status": "pending"}]},
        {"state": "success", "statuses": [{"context": "ci/build", "status": "success"}]},
    ]
    work, e = setup(tmp_path, api)
    local = commit_on_feat(work)
    r = checks_run(work, e)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == {
        "backend": "gitea", "state": "green",
        "checks": [{"name": "ci/build", "state": "success"}]}
    assert len(api.status_requests()) == 3
    assert api.status_requests()[0]["path"].startswith(f"/api/v1/repos/o/r/commits/{local}/status")
    assert TOKEN not in r.stdout + r.stderr


def test_gitea_checks_red(tmp_path, api):
    api.pulls = [pull(7)]
    api.statuses = [{"state": "failure", "statuses": [
        {"context": "ci/build", "status": "success"},
        {"context": "ci/test", "status": "failure"}]}]
    work, e = setup(tmp_path, api)
    local = commit_on_feat(work)
    r = checks_run(work, e)
    assert r.returncode == 1, r.stderr
    out = json.loads(r.stdout)
    assert out["backend"] == "gitea" and out["state"] == "red"
    assert {"name": "ci/test", "state": "failure"} in out["checks"]


def test_gitea_checks_timeout(tmp_path, api):
    api.pulls = [pull(7)]
    api.statuses = [{"state": "pending", "statuses": []}]
    work, e = setup(tmp_path, api)
    local = commit_on_feat(work)
    r = checks_run(work, e, "--timeout", "0.2")
    assert r.returncode == 3, r.stderr
    assert "timed out" in r.stderr
    assert len(api.status_requests()) >= 1
    assert all(f"/commits/{local}/status" in q["path"] for q in api.status_requests())
    assert TOKEN not in r.stdout + r.stderr


def test_gitea_login_without_tea_is_unsupported(tmp_path, api):
    work, e = setup(tmp_path, api, with_tea=False)
    r = pr_run(tmp_path, work, e)
    assert r.returncode == 2
    assert "tea" in r.stderr
    assert not api.requests
    assert TOKEN not in r.stdout + r.stderr


def test_gitea_http_error_is_exit_3_without_token(tmp_path, api):
    api.errors = {"/pulls": (401, {"message": "token is invalid"})}
    work, e = setup(tmp_path, api)
    r = pr_run(tmp_path, work, e)
    assert r.returncode == 3
    assert "401" in r.stderr and "token is invalid" in r.stderr
    assert "Traceback" not in r.stderr
    assert TOKEN not in r.stdout + r.stderr


def test_gitea_status_http_error_is_exit_3(tmp_path, api):
    api.pulls = [pull(7)]
    api.errors = {"/status": (404, {"message": "no such commit"})}
    work, e = setup(tmp_path, api)
    local = commit_on_feat(work)
    r = checks_run(work, e)
    assert r.returncode == 3
    assert "404" in r.stderr and "no such commit" in r.stderr
    assert "Traceback" not in r.stderr
    assert TOKEN not in r.stdout + r.stderr


def test_gitea_checks_polls_the_pushed_commit(tmp_path, api):
    work, e = setup(tmp_path, api)
    local = commit_on_feat(work)
    assert local != SHA
    api.pulls = [pull(7)]  # head.sha is the stale SHA
    api.stale_sha = SHA
    api.statuses = [
        {"state": "pending", "statuses": []},
        {"state": "failure", "statuses": [{"context": "ci/build", "status": "failure"}]},
    ]
    r = checks_run(work, e)
    assert r.returncode == 1, r.stderr
    out = json.loads(r.stdout)
    assert out["state"] == "red"
    assert out["checks"] == [{"name": "ci/build", "state": "failure"}]
    paths = [q["path"] for q in api.status_requests()]
    assert len(paths) == 2
    assert all(p.startswith(f"/api/v1/repos/o/r/commits/{local}/status") for p in paths)
    assert not [p for p in paths if SHA in p]


def test_gitea_pr_finds_open_pr_on_second_page(tmp_path, api):
    api.pull_pages = [
        [pull(1, head="a"), pull(2, head="b"), pull(3, head="c")],
        [pull(9, url="http://127.0.0.1/o/r/pulls/9")],
        [],
    ]
    work, e = setup(tmp_path, api)
    r = pr_run(tmp_path, work, e)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == {
        "backend": "gitea", "action": "updated", "url": "http://127.0.0.1/o/r/pulls/9"}
    calls = log(tmp_path)
    assert ["pr", "edit", "9", "--login", "home", "--repo", "o/r", "--title", "T",
            "--description", "the body"] in calls
    assert not [c for c in calls if c[:2] == ["pr", "create"]]


def test_gitea_checks_success_with_empty_statuses_keeps_waiting(tmp_path, api):
    api.pulls = [pull(7)]
    api.statuses = [
        {"state": "success", "statuses": []},
        {"state": "success", "statuses": [{"context": "ci/build", "status": "success"}]},
    ]
    work, e = setup(tmp_path, api)
    local = commit_on_feat(work)
    r = checks_run(work, e)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["checks"] == [{"name": "ci/build", "state": "success"}]
    assert len(api.status_requests()) == 2
    assert all(f"/commits/{local}/status" in q["path"] for q in api.status_requests())


def test_gitea_tea_failure_is_exit_3(tmp_path, api):
    api.pulls = []
    work, e = setup(tmp_path, api)
    e["FAKE_TEA_FAIL"] = "tea: something failed"
    r = pr_run(tmp_path, work, e)
    assert r.returncode == 3
    assert "tea: something failed" in r.stderr
    assert TOKEN not in r.stdout + r.stderr


def test_gitea_missing_field_is_exit_3(tmp_path, api):
    broken = pull(7)
    del broken["html_url"]
    api.pulls = [broken]
    work, e = setup(tmp_path, api)
    r = pr_run(tmp_path, work, e)
    assert r.returncode == 3
    assert r.stderr.strip()
    assert "Traceback" not in r.stderr
    assert TOKEN not in r.stdout + r.stderr


def test_gitea_checks_without_local_branch_is_exit_3(tmp_path, api):
    api.pulls = [pull(7)]
    api.statuses = [{"state": "success", "statuses": [{"context": "ci/build", "status": "success"}]}]
    work, e = setup(tmp_path, api)  # no commit, no branch `feat`
    r = checks_run(work, e)
    assert r.returncode == 3
    assert "feat" in r.stderr
    assert "Traceback" not in r.stderr
    assert not api.status_requests()
    assert TOKEN not in r.stdout + r.stderr
