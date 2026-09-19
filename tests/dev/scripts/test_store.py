"""The shared store resolver, exercised as a subprocess against real git repos.

`scripts/store` resolves a cross-repo store from a variable pair
(`<PREFIX>_PATH`, `<PREFIX>_REMOTE`) and commits-and-pushes a result into it.
Both halves are git plumbing with a right answer, so the tests use real bare
repositories under `tmp_path` and assert on what git ends up holding — never on
the script's internals.

Every failure path must fail *loudly*: non-zero exit and a message on stderr.
A store that silently resolves to nothing is the one outcome the skill exists
to prevent (see XAS-034, "the skill never guesses").
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "xxthunder-dev-skills"
STORE = PLUGIN_ROOT / "scripts" / "store"


def resolve_bash() -> str:
    """Find a real bash, the way `run-hook.cmd` does — see test_session_start.py.

    On the Windows runner a bare `bash` can resolve to the WSL launcher, which
    exits 1 with a "no installed distributions" notice. Git for Windows first.
    """
    for candidate in (
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files (x86)\Git\bin\bash.exe",
    ):
        if Path(candidate).is_file():
            return candidate
    return shutil.which("bash") or "bash"


BASH = resolve_bash()


# --- helpers -----------------------------------------------------------------


def git(*args: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True
    ).stdout.strip()


def base_env(tmp_path: Path) -> dict[str, str]:
    """A hermetic environment: no user git config, a private cache, an identity."""
    return {
        "PATH": os.environ["PATH"],
        "HOME": str(tmp_path / "home"),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "test@example.invalid",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "test@example.invalid",
        "XDG_CACHE_HOME": str(tmp_path / "cache"),
    }


def run_store(
    args: list[str], *, cwd: Path, env: dict[str, str]
) -> subprocess.CompletedProcess:
    return subprocess.run(
        [BASH, str(STORE), *args],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def env(tmp_path: Path) -> dict[str, str]:
    (tmp_path / "home").mkdir()
    return base_env(tmp_path)


@pytest.fixture
def remote(tmp_path: Path, env: dict[str, str]) -> Path:
    """A bare repo with one commit on `main`, standing in for the store's origin."""
    bare = tmp_path / "remote.git"
    subprocess.run(
        ["git", "init", "--bare", "--initial-branch=main", str(bare)],
        check=True, capture_output=True,
    )
    seed = tmp_path / "seed"
    subprocess.run(["git", "clone", "-q", str(bare), str(seed)], check=True, env=env)
    (seed / "README.md").write_text("# store\n")
    subprocess.run(["git", "add", "README.md"], cwd=seed, check=True, env=env)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=seed, check=True, env=env)
    subprocess.run(["git", "push", "-q", "-u", "origin", "main"], cwd=seed, check=True, env=env)
    # The seed clone stays on disk: shutil.rmtree cannot remove a git object
    # store on Windows (objects are read-only), and pytest's tmp_path cleanup
    # handles that case itself. Nothing reads the seed again.
    return bare


def clone(remote: Path, dest: Path, env: dict[str, str]) -> Path:
    subprocess.run(["git", "clone", "-q", str(remote), str(dest)], check=True, env=env)
    return dest


def push_commit(remote: Path, tmp_path: Path, env: dict[str, str], name: str,
                filename: str = "other.md", content: str | None = None) -> str:
    """Land a commit on the remote from a throwaway clone; return its sha."""
    other = clone(remote, tmp_path / f"other-{name}", env)
    (other / filename).write_text(content if content is not None else f"{name}\n")
    subprocess.run(["git", "add", filename], cwd=other, check=True, env=env)
    subprocess.run(["git", "commit", "-q", "-m", name], cwd=other, check=True, env=env)
    subprocess.run(["git", "push", "-q"], cwd=other, check=True, env=env)
    return git("rev-parse", "HEAD", cwd=other)  # the clone stays; see `remote`


def elsewhere(tmp_path: Path) -> Path:
    """A directory that is not a store — the consuming repo's stand-in."""
    d = tmp_path / "consuming"
    d.mkdir(exist_ok=True)
    return d


# --- resolve: the negative control comes first -------------------------------


def test_resolve_stops_with_message_when_nothing_configured(tmp_path, env):
    result = run_store(["resolve", "LEARNINGS"], cwd=elsewhere(tmp_path), env=env)

    assert result.returncode != 0
    assert result.stdout == ""
    assert "LEARNINGS_PATH" in result.stderr
    assert "LEARNINGS_REMOTE" in result.stderr


def test_resolve_rejects_missing_prefix(tmp_path, env):
    result = run_store(["resolve"], cwd=elsewhere(tmp_path), env=env)

    assert result.returncode != 0
    assert result.stdout == ""
    assert "usage" in result.stderr.lower()


def test_resolve_uses_cwd_as_is_when_it_is_the_configured_path(tmp_path, env, remote):
    store = clone(remote, tmp_path / "store", env)
    before = git("rev-parse", "HEAD", cwd=store)
    push_commit(remote, tmp_path, env, "newer")
    env["LEARNINGS_PATH"] = str(store)

    result = run_store(["resolve", "LEARNINGS"], cwd=store, env=env)

    assert result.returncode == 0, result.stderr
    assert Path(result.stdout.strip()).resolve() == store.resolve()
    # "as-is": the current directory is not pulled behind the session's back
    assert git("rev-parse", "HEAD", cwd=store) == before


def test_resolve_uses_cwd_when_its_origin_is_the_configured_remote(tmp_path, env, remote):
    store = clone(remote, tmp_path / "store", env)
    env["LEARNINGS_REMOTE"] = str(remote)

    result = run_store(["resolve", "LEARNINGS"], cwd=store, env=env)

    assert result.returncode == 0, result.stderr
    assert Path(result.stdout.strip()).resolve() == store.resolve()
    assert not (tmp_path / "cache").exists(), "must not clone when cwd already is the store"


def test_resolve_pulls_configured_path_fast_forward(tmp_path, env, remote):
    store = clone(remote, tmp_path / "store", env)
    newer = push_commit(remote, tmp_path, env, "newer")
    env["LEARNINGS_PATH"] = str(store)

    result = run_store(["resolve", "LEARNINGS"], cwd=elsewhere(tmp_path), env=env)

    assert result.returncode == 0, result.stderr
    assert Path(result.stdout.strip()).resolve() == store.resolve()
    assert git("rev-parse", "HEAD", cwd=store) == newer


def test_resolve_fails_when_configured_path_cannot_fast_forward(tmp_path, env, remote):
    store = clone(remote, tmp_path / "store", env)
    (store / "local.md").write_text("diverging\n")
    subprocess.run(["git", "add", "local.md"], cwd=store, check=True, env=env)
    subprocess.run(["git", "commit", "-q", "-m", "local"], cwd=store, check=True, env=env)
    push_commit(remote, tmp_path, env, "newer")
    env["LEARNINGS_PATH"] = str(store)

    result = run_store(["resolve", "LEARNINGS"], cwd=elsewhere(tmp_path), env=env)

    assert result.returncode != 0
    assert result.stdout == ""
    assert str(store) in result.stderr


def test_resolve_fails_when_configured_path_is_not_a_checkout(tmp_path, env):
    plain = tmp_path / "plain"
    plain.mkdir()
    env["LEARNINGS_PATH"] = str(plain)

    result = run_store(["resolve", "LEARNINGS"], cwd=elsewhere(tmp_path), env=env)

    assert result.returncode != 0
    assert result.stdout == ""
    assert "not a git checkout" in result.stderr


def test_resolve_clones_remote_into_cache_when_no_path(tmp_path, env, remote):
    env["LEARNINGS_REMOTE"] = str(remote)
    consuming = elsewhere(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=consuming, check=True, env=env)

    result = run_store(["resolve", "LEARNINGS"], cwd=consuming, env=env)

    assert result.returncode == 0, result.stderr
    expected = tmp_path / "cache" / "xxthunder-dev-skills" / "stores" / "learnings"
    assert Path(result.stdout.strip()).resolve() == expected.resolve()
    assert git("rev-parse", "HEAD", cwd=expected) == git("rev-parse", "main", cwd=remote)
    # the consuming repo is never written to
    assert git("status", "--porcelain", cwd=consuming) == ""


def test_resolve_reuses_cached_clone_and_pulls(tmp_path, env, remote):
    env["LEARNINGS_REMOTE"] = str(remote)
    first = run_store(["resolve", "LEARNINGS"], cwd=elsewhere(tmp_path), env=env)
    assert first.returncode == 0, first.stderr
    newer = push_commit(remote, tmp_path, env, "newer")

    second = run_store(["resolve", "LEARNINGS"], cwd=elsewhere(tmp_path), env=env)

    assert second.returncode == 0, second.stderr
    assert second.stdout == first.stdout
    assert git("rev-parse", "HEAD", cwd=Path(second.stdout.strip())) == newer


def test_resolve_falls_back_to_remote_when_path_is_missing(tmp_path, env, remote):
    env["LEARNINGS_PATH"] = str(tmp_path / "does-not-exist")
    env["LEARNINGS_REMOTE"] = str(remote)

    result = run_store(["resolve", "LEARNINGS"], cwd=elsewhere(tmp_path), env=env)

    assert result.returncode == 0, result.stderr
    assert "stores/learnings" in result.stdout


def test_resolve_prefix_is_honoured(tmp_path, env, remote):
    """`LOGBOOK` must not see `LEARNINGS_*` — the resolver is parameterised, not aliased."""
    env["LEARNINGS_REMOTE"] = str(remote)

    result = run_store(["resolve", "LOGBOOK"], cwd=elsewhere(tmp_path), env=env)

    assert result.returncode != 0
    assert "LOGBOOK_PATH" in result.stderr


# --- commit-push -------------------------------------------------------------


def test_commit_push_lands_the_commit_on_the_remote(tmp_path, env, remote):
    store = clone(remote, tmp_path / "store", env)
    (store / "learnings").mkdir()
    (store / "learnings" / "note.md").write_text("# a learning\n")

    result = run_store(
        ["commit-push", str(store), "learning: a learning", "learnings/note.md"],
        cwd=elsewhere(tmp_path), env=env,
    )

    assert result.returncode == 0, result.stderr
    assert git("log", "-1", "--format=%s", "main", cwd=remote) == "learning: a learning"
    assert git("status", "--porcelain", cwd=store) == ""


def test_commit_push_refuses_when_there_is_nothing_to_commit(tmp_path, env, remote):
    store = clone(remote, tmp_path / "store", env)

    result = run_store(
        ["commit-push", str(store), "empty", "README.md"], cwd=elsewhere(tmp_path), env=env,
    )

    assert result.returncode != 0
    assert "nothing to commit" in result.stderr.lower()


def test_commit_push_retries_once_after_a_rejected_push(tmp_path, env, remote):
    store = clone(remote, tmp_path / "store", env)
    (store / "mine.md").write_text("mine\n")
    push_commit(remote, tmp_path, env, "theirs")  # remote moves on before we push

    result = run_store(
        ["commit-push", str(store), "mine", "mine.md"], cwd=elsewhere(tmp_path), env=env,
    )

    assert result.returncode == 0, result.stderr
    subjects = git("log", "--format=%s", "main", cwd=remote).splitlines()
    assert subjects[:2] == ["mine", "theirs"]


def test_commit_push_stops_on_a_rebase_conflict_and_leaves_no_rebase_in_progress(
    tmp_path, env, remote
):
    store = clone(remote, tmp_path / "store", env)
    (store / "README.md").write_text("# mine\n")
    push_commit(remote, tmp_path, env, "theirs", filename="README.md", content="# theirs\n")

    result = run_store(
        ["commit-push", str(store), "mine", "README.md"], cwd=elsewhere(tmp_path), env=env,
    )

    assert result.returncode != 0
    assert "conflict" in result.stderr.lower()
    assert not (store / ".git" / "rebase-merge").exists()
    assert not (store / ".git" / "rebase-apply").exists()
    # our commit is kept locally so the author can resolve and push by hand
    assert git("log", "-1", "--format=%s", cwd=store) == "mine"
    assert git("log", "-1", "--format=%s", "main", cwd=remote) == "theirs"


def test_commit_push_gives_up_when_the_second_push_is_rejected_too(tmp_path, env, remote):
    hook = remote / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\necho 'rejected by policy' >&2\nexit 1\n")
    hook.chmod(0o755)
    store = clone(remote, tmp_path / "store", env)
    (store / "mine.md").write_text("mine\n")

    result = run_store(
        ["commit-push", str(store), "mine", "mine.md"], cwd=elsewhere(tmp_path), env=env,
    )

    assert result.returncode != 0
    assert "push" in result.stderr.lower()
    assert git("log", "-1", "--format=%s", "main", cwd=remote) == "seed"
    assert git("log", "-1", "--format=%s", cwd=store) == "mine"
