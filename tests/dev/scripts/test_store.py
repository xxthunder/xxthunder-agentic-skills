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


def test_resolve_names_unpushed_commits_when_cached_clone_cannot_fast_forward(
    tmp_path, env, remote
):
    """After an aborted rebase the cache holds a kept, unpushed commit. The
    message must say so — never tell the user to delete the clone."""
    env["LEARNINGS_REMOTE"] = str(remote)
    first = run_store(["resolve", "LEARNINGS"], cwd=elsewhere(tmp_path), env=env)
    cache = Path(first.stdout.strip())
    (cache / "kept.md").write_text("kept locally\n")
    subprocess.run(["git", "add", "kept.md"], cwd=cache, check=True, env=env)
    subprocess.run(["git", "commit", "-q", "-m", "kept"], cwd=cache, check=True, env=env)
    push_commit(remote, tmp_path, env, "theirs")

    result = run_store(["resolve", "LEARNINGS"], cwd=elsewhere(tmp_path), env=env)

    assert result.returncode != 0
    assert result.stdout == ""
    assert "unpushed" in result.stderr.lower()
    assert "remove" not in result.stderr.lower()
    assert git("log", "-1", "--format=%s", cwd=cache) == "kept"


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


def test_commit_push_commits_only_the_named_paths(tmp_path, env, remote):
    """A session working inside the store may have staged other files (a backlog
    edit, say). The log commit must not sweep them in."""
    store = clone(remote, tmp_path / "store", env)
    (store / "backlog.md").write_text("staged by someone else\n")
    subprocess.run(["git", "add", "backlog.md"], cwd=store, check=True, env=env)
    (store / "log.md").write_text("- started\n")

    result = run_store(
        ["commit-push", str(store), "log: started", "log.md"], cwd=elsewhere(tmp_path), env=env,
    )

    assert result.returncode == 0, result.stderr
    committed = git("show", "--stat", "--format=", "--name-only", "HEAD", cwd=store).split()
    assert committed == ["log.md"]
    # the other staged change is still there, untouched, for whoever staged it
    assert git("diff", "--cached", "--name-only", cwd=store) == "backlog.md"


def test_commit_push_refuses_when_only_other_files_are_staged(tmp_path, env, remote):
    store = clone(remote, tmp_path / "store", env)
    (store / "backlog.md").write_text("staged by someone else\n")
    subprocess.run(["git", "add", "backlog.md"], cwd=store, check=True, env=env)

    result = run_store(
        ["commit-push", str(store), "empty", "README.md"], cwd=elsewhere(tmp_path), env=env,
    )

    assert result.returncode != 0
    assert "nothing to commit" in result.stderr.lower()
    assert git("log", "-1", "--format=%s", cwd=store) == "seed"


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


# --- contract ----------------------------------------------------------------
#
# `store contract <STORE_DIR> <SECTION>` prints the section headed <SECTION>
# from the store's AGENTS.md or from any file it pulls in with an `@path`
# import line. The contract is one section in one place: missing or found
# twice, the command fails loudly instead of guessing.


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode())
    return path


def run_contract(store: Path, section: str, env: dict[str, str]) -> subprocess.CompletedProcess:
    return run_store(["contract", str(store), section], cwd=store, env=env)


def test_contract_prints_the_section_from_agents_md(tmp_path, env):
    store = tmp_path / "store"
    write(store / "AGENTS.md",
          "# Store\n\n## Logbook\n\nOne line per event.\n\n### Order\n\nNewest first.\n\n"
          "## Next\n\nRanked list.\n")
    result = run_contract(store, "Logbook", env)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "## Logbook\n\nOne line per event.\n\n### Order\n\nNewest first.\n\n"


def test_contract_follows_an_import_relative_to_the_importing_file(tmp_path, env):
    store = tmp_path / "store"
    write(store / "AGENTS.md", "# Store\n\n@asf/AGENTS.md\n\n## Areas\n\nRecipes.\n")
    write(store / "asf" / "AGENTS.md", "# Shared\n\n@contracts.md\n")
    write(store / "asf" / "contracts.md", "## Learnings\n\nOne file per learning.\n")
    result = run_contract(store, "Learnings", env)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "## Learnings\n\nOne file per learning.\n"


def test_contract_section_ends_at_the_end_of_its_file(tmp_path, env):
    store = tmp_path / "store"
    write(store / "AGENTS.md", "@asf/AGENTS.md\n\n## Areas\n\nRecipes.\n")
    write(store / "asf" / "AGENTS.md", "## Next\n\nRanked list.\n")
    result = run_contract(store, "Next", env)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "## Next\n\nRanked list.\n"


def test_contract_fails_and_names_both_files_when_the_section_is_found_twice(tmp_path, env):
    store = tmp_path / "store"
    write(store / "AGENTS.md", "@asf/AGENTS.md\n\n## Logbook\n\nLocal copy.\n")
    write(store / "asf" / "AGENTS.md", "## Logbook\n\nShared copy.\n")
    result = run_contract(store, "Logbook", env)
    assert result.returncode != 0
    assert result.stdout == ""
    assert "AGENTS.md" in result.stderr
    assert "asf/AGENTS.md" in result.stderr


def test_contract_fails_when_the_section_is_missing(tmp_path, env):
    store = tmp_path / "store"
    write(store / "AGENTS.md", "# Store\n\n## Next\n\nRanked list.\n")
    result = run_contract(store, "Logbook", env)
    assert result.returncode != 0
    assert result.stdout == ""
    assert "Logbook" in result.stderr


def test_contract_fails_when_the_store_has_no_agents_md(tmp_path, env):
    store = tmp_path / "store"
    store.mkdir()
    result = run_contract(store, "Logbook", env)
    assert result.returncode != 0
    assert "AGENTS.md" in result.stderr


def test_contract_fails_and_names_a_missing_import(tmp_path, env):
    store = tmp_path / "store"
    write(store / "AGENTS.md", "@asf/AGENTS.md\n\n## Logbook\n\nHere.\n")
    result = run_contract(store, "Logbook", env)
    assert result.returncode != 0
    assert "asf/AGENTS.md" in result.stderr


def test_contract_ignores_headings_and_imports_inside_code_fences(tmp_path, env):
    store = tmp_path / "store"
    write(store / "AGENTS.md",
          "## Recipes\n\n```\n# Title\n## Logbook\n@nowhere.md\n```\n\nDone.\n\n"
          "## Logbook\n\n```\n## Not a heading\n```\n\nNewest first.\n\n## Next\n")
    result = run_contract(store, "Logbook", env)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "## Logbook\n\n```\n## Not a heading\n```\n\nNewest first.\n\n"


def test_contract_survives_an_import_cycle(tmp_path, env):
    store = tmp_path / "store"
    write(store / "AGENTS.md", "@a.md\n")
    write(store / "a.md", "@AGENTS.md\n\n## Next\n\nRanked list.\n")
    result = run_contract(store, "Next", env)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "## Next\n\nRanked list.\n"


def test_contract_reads_crlf_files(tmp_path, env):
    store = tmp_path / "store"
    write(store / "AGENTS.md", "@asf/AGENTS.md\r\n")
    write(store / "asf" / "AGENTS.md", "## Logbook\r\n\r\nNewest first.\r\n\r\n## Next\r\n")
    result = run_contract(store, "Logbook", env)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "## Logbook\n\nNewest first.\n\n"


def test_contract_matches_the_whole_heading_only(tmp_path, env):
    store = tmp_path / "store"
    write(store / "AGENTS.md", "## Logbook archive\n\nOld.\n\n## Logbook\n\nNew.\n")
    result = run_contract(store, "Logbook", env)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "## Logbook\n\nNew.\n"
