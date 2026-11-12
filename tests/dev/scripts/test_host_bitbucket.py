"""The Bitbucket Server backend of `scripts/host.py`: the REST API opens or updates
the pull request, and Jenkins' verdict is read from the build statuses Bitbucket
holds for the commit.

The API is a local HTTP server; the profile token is `secret-b` and must never
reach stdout or stderr.
"""
from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse

import pytest

from host_fakes import (FakeBitbucket, commit_on_feat, env, fake_bin, repo, run, write_bitbucket_profile)

TOKEN = "secret-b"
SHA = "abc123"
PRS = "/rest/api/1.0/projects/PROJ/repos/repo/pull-requests"
URL = "http://127.0.0.1/projects/PROJ/repos/repo/pull-requests/{}"


@pytest.fixture
def api():
    server = FakeBitbucket().start()
    yield server
    server.stop()


def setup(tmp_path, api, origin="http://127.0.0.1:{port}/scm/PROJ/repo.git"):
    """Bitbucket profile for the fake API, a worktree with a matching origin."""
    write_bitbucket_profile(tmp_path, api.port)
    work = repo(tmp_path, origin.format(port=api.port))
    return work, env(tmp_path, fake_bin(tmp_path, "unrelated", ""))


def pull(pr_id, version=0, url=None, head="feat"):
    return {"id": pr_id, "version": version,
            "links": {"self": [{"href": url or URL.format(pr_id)}]},
            "fromRef": {"id": f"refs/heads/{head}", "latestCommit": SHA}}


def status(name, state):
    return {"name": name, "key": name, "state": state}


def pr_run(tmp_path, work, e):
    body = tmp_path / "body.md"
    body.write_text("the body", encoding="utf-8")
    return run("pr", work, "--base", "develop", "--head", "feat", "--title", "T",
               "--body-file", body, env=e)


def checks_run(work, e, *extra):
    return run("checks", work, "--head", "feat", "--interval", "0", *extra, env=e)


def calls(api, method):
    return [q for q in api.requests if q["method"] == method]


def test_bitbucket_pr_creates(tmp_path, api):
    api.pr_pages = [[]]
    api.created = pull(5, url="http://127.0.0.1/projects/PROJ/repos/repo/pull-requests/5")
    work, e = setup(tmp_path, api)
    r = pr_run(tmp_path, work, e)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == {
        "backend": "bitbucket", "action": "created", "url": URL.format(5)}
    lookup = calls(api, "GET")[0]
    parsed = urlparse(lookup["path"])
    assert parsed.path == PRS
    assert parse_qs(parsed.query) == {
        "state": ["OPEN"], "direction": ["OUTGOING"], "at": ["refs/heads/feat"]}
    (post,) = calls(api, "POST")
    assert post["path"] == PRS
    body = post["body"]
    assert body["title"] == "T" and body["description"] == "the body"
    assert body["fromRef"]["id"] == "refs/heads/feat"
    assert body["toRef"]["id"] == "refs/heads/develop"
    for ref in ("fromRef", "toRef"):
        assert body[ref]["repository"]["slug"] == "repo"
        assert body[ref]["repository"]["project"]["key"] == "PROJ"
    assert not calls(api, "PUT")
    assert TOKEN not in r.stdout + r.stderr


def test_bitbucket_pr_updates_open_pr(tmp_path, api):
    api.pr_pages = [[pull(12, version=3)]]
    api.updated = pull(12, version=4)
    work, e = setup(tmp_path, api)
    r = pr_run(tmp_path, work, e)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == {
        "backend": "bitbucket", "action": "updated", "url": URL.format(12)}
    (put,) = calls(api, "PUT")
    assert put["path"] == f"{PRS}/12"
    assert put["body"]["version"] == 3
    assert put["body"]["title"] == "T" and put["body"]["description"] == "the body"
    assert not calls(api, "POST")
    assert TOKEN not in r.stdout + r.stderr


def test_bitbucket_sends_bearer_token(tmp_path, api):
    api.pr_pages = [[]]
    api.created = pull(5)
    work, e = setup(tmp_path, api)
    r = pr_run(tmp_path, work, e)
    assert r.returncode == 0, r.stderr
    assert {q["method"] for q in api.requests} == {"GET", "POST"}
    assert all(q["headers"].get("Authorization") == f"Bearer {TOKEN}" for q in api.requests)
    assert TOKEN not in r.stdout + r.stderr


def test_bitbucket_ssh_remote(tmp_path, api):
    api.pr_pages = [[]]
    api.created = pull(5)
    work, e = setup(tmp_path, api, origin="ssh://git@127.0.0.1:7999/proj/repo.git")
    r = pr_run(tmp_path, work, e)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["backend"] == "bitbucket"
    assert urlparse(calls(api, "GET")[0]["path"]).path == "/rest/api/1.0/projects/proj/repos/repo/pull-requests"
    (post,) = calls(api, "POST")
    assert post["path"] == "/rest/api/1.0/projects/proj/repos/repo/pull-requests"
    assert post["body"]["fromRef"]["repository"]["project"]["key"] == "proj"
    assert post["body"]["fromRef"]["repository"]["slug"] == "repo"


def test_bitbucket_pr_finds_open_pr_on_second_page(tmp_path, api):
    api.pr_pages = [[pull(1, head="other"), pull(2, head="other")], [pull(9, version=1)]]
    api.updated = pull(9, version=2)
    work, e = setup(tmp_path, api)
    r = pr_run(tmp_path, work, e)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == {
        "backend": "bitbucket", "action": "updated", "url": URL.format(9)}
    lookups = calls(api, "GET")
    assert len(lookups) == 2
    assert parse_qs(urlparse(lookups[1]["path"]).query)["start"] == ["10"]
    (put,) = calls(api, "PUT")
    assert put["path"] == f"{PRS}/9" and put["body"]["version"] == 1
    assert not calls(api, "POST")


def test_bitbucket_missing_field_is_exit_3(tmp_path, api):
    broken = pull(7)
    del broken["links"]
    api.pr_pages = [[broken]]
    api.updated = broken
    work, e = setup(tmp_path, api)
    r = pr_run(tmp_path, work, e)
    assert r.returncode == 3
    assert api.requests, "the API was never called"
    assert "links" in r.stderr
    assert "Traceback" not in r.stderr
    assert TOKEN not in r.stdout + r.stderr


def test_bitbucket_http_error_is_exit_3_without_token(tmp_path, api):
    api.errors = {"/pull-requests": (409, {"errors": [{"message": "only one pull request may be open"}]})}
    work, e = setup(tmp_path, api)
    r = pr_run(tmp_path, work, e)
    assert r.returncode == 3
    assert "409" in r.stderr and "only one pull request may be open" in r.stderr
    assert "Traceback" not in r.stderr
    assert TOKEN not in r.stdout + r.stderr


def test_bitbucket_checks_waits_until_final(tmp_path, api):
    api.statuses = [
        [],
        [status("build", "INPROGRESS")],
        [status("build", "SUCCESSFUL"), status("test", "SUCCESSFUL")],
    ]
    work, e = setup(tmp_path, api)
    local = commit_on_feat(work)
    r = checks_run(work, e)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == {
        "backend": "bitbucket", "state": "green",
        "checks": [{"name": "build", "state": "SUCCESSFUL"},
                   {"name": "test", "state": "SUCCESSFUL"}]}
    reqs = api.status_requests()
    assert len(reqs) == 3
    assert all(urlparse(q["path"]).path == f"/rest/build-status/1.0/commits/{local}" for q in reqs)
    assert all(q["headers"].get("Authorization") == f"Bearer {TOKEN}" for q in reqs)
    assert TOKEN not in r.stdout + r.stderr


def test_bitbucket_checks_red(tmp_path, api):
    api.statuses = [[status("build", "SUCCESSFUL"), status("test", "FAILED")]]
    work, e = setup(tmp_path, api)
    commit_on_feat(work)
    r = checks_run(work, e)
    assert r.returncode == 1, r.stderr
    out = json.loads(r.stdout)
    assert out["backend"] == "bitbucket" and out["state"] == "red"
    assert {"name": "test", "state": "FAILED"} in out["checks"]
    assert len(api.status_requests()) == 1


def test_bitbucket_checks_empty_values_keeps_waiting(tmp_path, api):
    api.statuses = [[], [], [status("build", "SUCCESSFUL")]]
    work, e = setup(tmp_path, api)
    commit_on_feat(work)
    r = checks_run(work, e)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["checks"] == [{"name": "build", "state": "SUCCESSFUL"}]
    assert len(api.status_requests()) == 3


def test_bitbucket_checks_timeout(tmp_path, api):
    api.statuses = [[status("build", "INPROGRESS")]]
    work, e = setup(tmp_path, api)
    local = commit_on_feat(work)
    r = checks_run(work, e, "--timeout", "0.2")
    assert r.returncode == 3, r.stderr
    assert "timed out" in r.stderr
    assert api.status_requests()
    assert all(f"/commits/{local}" in q["path"] for q in api.status_requests())
    assert TOKEN not in r.stdout + r.stderr


def test_bitbucket_checks_polls_the_pushed_commit(tmp_path, api):
    work, e = setup(tmp_path, api)
    local = commit_on_feat(work)
    assert local != SHA
    api.pr_pages = [[pull(7)]]  # latestCommit is the stale SHA
    api.stale_sha = SHA
    api.statuses = [[], [status("build", "FAILED")]]
    r = checks_run(work, e)
    assert r.returncode == 1, r.stderr
    out = json.loads(r.stdout)
    assert out["state"] == "red"
    assert out["checks"] == [{"name": "build", "state": "FAILED"}]
    paths = [urlparse(q["path"]).path for q in api.status_requests()]
    assert paths == [f"/rest/build-status/1.0/commits/{local}"] * 2


def test_bitbucket_checks_without_local_branch_is_exit_3(tmp_path, api):
    api.statuses = [[status("build", "SUCCESSFUL")]]
    work, e = setup(tmp_path, api)  # no commit, no branch `feat`
    r = checks_run(work, e)
    assert r.returncode == 3
    assert "feat" in r.stderr
    assert "Traceback" not in r.stderr
    assert not api.status_requests()
    assert TOKEN not in r.stdout + r.stderr


def test_bitbucket_status_http_error_is_exit_3(tmp_path, api):
    api.errors = {"/build-status/": (401, {"errors": [{"message": "bad credentials"}]})}
    work, e = setup(tmp_path, api)
    commit_on_feat(work)
    r = checks_run(work, e)
    assert r.returncode == 3
    assert "401" in r.stderr and "bad credentials" in r.stderr
    assert "Traceback" not in r.stderr
    assert TOKEN not in r.stdout + r.stderr


def test_bitbucket_ca_bundle_is_used(tmp_path, api):
    missing = tmp_path / "missing.pem"
    write_bitbucket_profile(tmp_path, api.port, ca_bundle=str(missing))
    work = repo(tmp_path, f"http://127.0.0.1:{api.port}/scm/PROJ/repo.git")
    e = env(tmp_path, fake_bin(tmp_path, "unrelated", ""))
    commit_on_feat(work)
    r = pr_run(tmp_path, work, e)
    assert r.returncode == 3, r.stderr
    assert str(missing) in r.stderr
    assert "Traceback" not in r.stderr
    assert TOKEN not in r.stdout + r.stderr


def test_bitbucket_remote_path_not_project_repo_is_unsupported(tmp_path, api):
    work, e = setup(tmp_path, api, origin="http://127.0.0.1:{port}/scm/PROJ/sub/repo.git")
    r = pr_run(tmp_path, work, e)
    assert r.returncode == 2, r.stderr
    assert r.stderr.startswith("unsupported remote")
    assert api.requests == []
