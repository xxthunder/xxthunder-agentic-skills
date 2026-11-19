"""The runner's plumbing: plugin export, dependency lookup, environment, command, stream."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from evals.runner import (
    claude_command,
    clean_env,
    config_dir,
    dependency_dirs,
    export_plugin,
    parse_stream,
    report,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_export_plugin_writes_the_plugin_at_a_ref(tmp_path):
    plugin = export_plugin(REPO_ROOT, "HEAD", tmp_path)
    assert (plugin / ".claude-plugin" / "plugin.json").is_file()
    assert (plugin / "skills" / "next" / "SKILL.md").is_file()


def test_export_plugin_names_an_unknown_ref(tmp_path):
    with pytest.raises(RuntimeError, match="no-such-ref"):
        export_plugin(REPO_ROOT, "no-such-ref", tmp_path)


def test_config_dir_honours_claude_config_dir(tmp_path):
    assert config_dir({"CLAUDE_CONFIG_DIR": str(tmp_path)}) == tmp_path
    assert config_dir({}) == Path.home() / ".claude"


def write_plugin(path: Path, deps: list[dict]) -> Path:
    (path / ".claude-plugin").mkdir(parents=True)
    (path / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": "p", "dependencies": deps}))
    return path


def test_dependency_dirs_pick_the_highest_cached_version(tmp_path):
    plugin = write_plugin(tmp_path / "p", [{"name": "superpowers", "marketplace": "official"}])
    cache = tmp_path / "cfg" / "plugins" / "cache" / "official" / "superpowers"
    for v in ("6.4.1", "7.0.0", "10.0.0"):
        (cache / v).mkdir(parents=True)
    assert dependency_dirs(plugin, tmp_path / "cfg") == [cache / "10.0.0"]


def test_dependency_dirs_say_what_is_missing(tmp_path):
    plugin = write_plugin(tmp_path / "p", [{"name": "superpowers", "marketplace": "official"}])
    with pytest.raises(RuntimeError, match="superpowers@official"):
        dependency_dirs(plugin, tmp_path / "cfg")


def test_dependency_dirs_without_dependencies(tmp_path):
    assert dependency_dirs(write_plugin(tmp_path / "p", []), tmp_path) == []


def test_clean_env_drops_every_store_pair_and_the_parent_session(tmp_path):
    base = {"PATH": "/bin", "LD_LIBRARY_PATH": "/lib", "LOGBOOK_PATH": "/k", "LOGBOOK_REMOTE": "r",
            "LEARNINGS_PATH": "/k", "OTHER_PATH": "/o", "OTHER_REMOTE": "o", "BOARD_PATH": "/b",
            "CLAUDECODE": "1", "CLAUDE_CODE_ENTRYPOINT": "cli", "CLAUDE_CODE_OAUTH_TOKEN": "t"}
    env = clean_env(base, tmp_path, board=False, logbook=False)
    assert env["PATH"].split(os.pathsep)[-1] == "/bin" and env["LD_LIBRARY_PATH"] == "/lib"
    assert env["CLAUDE_CODE_OAUTH_TOKEN"] == "t"
    for gone in ("LOGBOOK_PATH", "LOGBOOK_REMOTE", "LEARNINGS_PATH", "OTHER_PATH", "OTHER_REMOTE",
                 "BOARD_PATH", "CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT"):
        assert gone not in env
    assert env["XDG_CACHE_HOME"] == str(tmp_path / "cache")


def test_clean_env_points_the_requested_stores_into_the_sandbox(tmp_path):
    env = clean_env({}, tmp_path, board=True, logbook=True, learnings=True)
    for prefix in ("BOARD", "LOGBOOK", "LEARNINGS"):
        assert env[f"{prefix}_PATH"] == str(tmp_path / "store")
        assert env[f"{prefix}_REMOTE"] == str(tmp_path / "remotes" / "store.git")


def test_clean_env_leaves_learnings_unset_unless_asked(tmp_path):
    env = clean_env({"LEARNINGS_PATH": "/k"}, tmp_path, board=True, logbook=True)
    assert "LEARNINGS_PATH" not in env and "LEARNINGS_REMOTE" not in env


def test_claude_command_isolates_settings_and_loads_the_plugins(tmp_path):
    cmd = claude_command("pull DEMO-001", [Path("/dep"), Path("/plugin")], tmp_path)
    assert cmd[:3] == ["claude", "-p", "pull DEMO-001"]
    assert cmd[cmd.index("--setting-sources") + 1] == "project"
    assert "--strict-mcp-config" in cmd
    dirs = [cmd[i + 1] for i, a in enumerate(cmd) if a == "--plugin-dir"]
    assert dirs == [str(Path("/dep")), str(Path("/plugin"))]
    assert cmd[cmd.index("--output-format") + 1] == "stream-json"


def test_parse_stream_collects_text_skill_calls_and_bash_commands():
    events = [
        {"type": "system", "subtype": "init"},
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Skill", "input": {"skill": "xxthunder-dev-skills:next"}},
            {"type": "text", "text": "The board:"}]}},
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Bash", "input": {"command": "git status"}},
            {"type": "tool_use", "name": "Read", "input": {"file_path": "x"}},
            {"type": "text", "text": "done"}]}},
    ]
    stream = "\n".join(json.dumps(e) for e in events) + "\nnot json\n"
    assert parse_stream(stream) == ("The board:\ndone\n", ["xxthunder-dev-skills:next"], ["git status"])


def test_parse_stream_output_is_the_final_answer_when_the_run_finished():
    events = [
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "Now the board check."}]}},
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "Pulled DEMO-007."}]}},
        {"type": "result", "subtype": "success", "result": "Pulled DEMO-007."},
    ]
    stream = "\n".join(json.dumps(e) for e in events)
    assert parse_stream(stream) == ("Pulled DEMO-007.", [], [])


def test_report_prints_pass_rate_and_failures(tmp_path):
    for n, ok in ((1, True), (2, False)):
        d = tmp_path / f"close-{n}"
        d.mkdir()
        (d / "result.json").write_text(json.dumps(
            {"case": "close", "run": n, "pass": ok, "failures": [] if ok else ["card still on board"]}))
    lines = report(tmp_path)
    assert any(l.startswith("close") and "1/2" in l for l in lines)
    assert any("close#2" in l and "card still on board" in l for l in lines)


def test_remove_tree_removes_read_only_files_as_git_leaves_them(tmp_path):
    import stat

    from evals.runner import remove_tree

    objects = tmp_path / "sandbox" / "remotes" / "store.git" / "objects" / "ab"
    objects.mkdir(parents=True)
    blob = objects / "cdef"
    blob.write_bytes(b"x")
    blob.chmod(stat.S_IREAD)  # git writes its objects read-only; Windows then refuses to delete them
    remove_tree(tmp_path / "sandbox")
    assert not (tmp_path / "sandbox").exists()


def test_remove_tree_of_a_missing_path_does_nothing(tmp_path):
    from evals.runner import remove_tree

    remove_tree(tmp_path / "never-built")


def test_clean_env_puts_the_fake_gh_first_on_the_path_and_names_the_sandbox(tmp_path):
    import os

    from evals.fixture import FIXTURES

    env = clean_env({"PATH": "/bin"}, tmp_path, board=True, logbook=False)
    assert env["PATH"].split(os.pathsep) == [str(FIXTURES / "bin"), "/bin"]
    assert env["EVAL_SANDBOX"] == str(tmp_path)


def test_a_case_defaults_to_no_closed_loop_contract():
    from evals.cases import CASES, Case

    assert Case("x", None, "p", lambda s: []).closed_loop is False


def home_env(tmp_path, **base):
    return clean_env(base, tmp_path, board=False, logbook=False)


def test_clean_env_drops_gits_config_overrides_but_keeps_other_git_variables(tmp_path):
    overrides = ["GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM", "GIT_CONFIG_NOSYSTEM", "GIT_CONFIG_COUNT",
                 "GIT_CONFIG_KEY_0", "GIT_CONFIG_VALUE_0", "GIT_CONFIG_KEY_1", "GIT_CONFIG_VALUE_1"]
    env = home_env(tmp_path, GIT_EDITOR="true", **{name: "x" for name in overrides})
    assert not [name for name in overrides if name in env]
    assert env["GIT_EDITOR"] == "true"


def test_clean_env_gives_the_run_its_own_home(tmp_path):
    env = home_env(tmp_path, HOME="/the/real/home", USERPROFILE="C:/the/real/home")
    assert env["HOME"] == str(tmp_path / "home")
    assert env["USERPROFILE"] == str(tmp_path / "home")


@pytest.mark.parametrize("base", [{}, {"XDG_CONFIG_HOME": "/the/real/config"}])
def test_clean_env_points_xdg_config_home_into_the_new_home(tmp_path, base):
    assert home_env(tmp_path, **base)["XDG_CONFIG_HOME"] == str(tmp_path / "home" / ".config")


def test_clean_env_names_the_real_claude_config_dir_from_the_base(tmp_path):
    real = tmp_path / "real-claude"
    assert home_env(tmp_path, CLAUDE_CONFIG_DIR=str(real))["CLAUDE_CONFIG_DIR"] == str(real)


@pytest.mark.parametrize("platform", ["linux", "win32"])
def test_clean_env_names_the_default_claude_config_dir_when_the_base_sets_none(tmp_path, monkeypatch, platform):
    from evals import runner
    monkeypatch.setattr(runner.sys, "platform", platform)
    env = home_env(tmp_path, HOME="/the/real/home")
    assert env["CLAUDE_CONFIG_DIR"] == str(config_dir({}))
    assert Path(env["CLAUDE_CONFIG_DIR"]).is_absolute()


def test_clean_env_sets_no_claude_config_dir_on_macos_when_the_base_sets_none(tmp_path, monkeypatch):
    # on macOS a set CLAUDE_CONFIG_DIR makes Claude Code look for another Keychain entry than the login's
    from evals import runner
    monkeypatch.setattr(runner.sys, "platform", "darwin")
    assert "CLAUDE_CONFIG_DIR" not in home_env(tmp_path, HOME="/the/real/home")


def test_clean_env_keeps_the_uv_python_install_dir_of_the_base(tmp_path):
    env = home_env(tmp_path, UV_PYTHON_INSTALL_DIR="/the/real/pythons")
    assert env["UV_PYTHON_INSTALL_DIR"] == "/the/real/pythons"


def test_clean_env_asks_uv_for_its_python_dir_when_the_base_sets_none(tmp_path, monkeypatch):
    monkeypatch.delenv("UV_PYTHON_INSTALL_DIR", raising=False)
    asked = subprocess.run(["uv", "python", "dir"], capture_output=True, text=True, check=True).stdout.strip()
    assert home_env(tmp_path)["UV_PYTHON_INSTALL_DIR"] == asked


@pytest.mark.parametrize("platform, linked", [("darwin", True), ("linux", False), ("win32", False)])
def test_make_home_links_the_keychains_on_macos_only(tmp_path, monkeypatch, platform, linked):
    # macOS finds the Claude login in the Keychain under HOME; a fresh HOME without it is logged out
    from evals import runner
    real = tmp_path / "real"
    (real / "Library" / "Keychains").mkdir(parents=True)
    monkeypatch.setattr(runner.sys, "platform", platform)
    monkeypatch.setattr(runner.Path, "home", lambda: real)
    link = runner.make_home(tmp_path / "sandbox") / "Library" / "Keychains"
    assert link.is_symlink() == linked
    if linked:
        assert link.resolve() == (real / "Library" / "Keychains").resolve()
        runner.remove_tree(tmp_path / "sandbox")
        assert (real / "Library" / "Keychains").is_dir()


def test_make_home_creates_a_home_with_a_git_identity(tmp_path):
    from evals.runner import make_home
    home = make_home(tmp_path)
    assert home == tmp_path / "home"
    env = {**os.environ, "HOME": str(home), "USERPROFILE": str(home)}
    for var in ("GIT_CONFIG_GLOBAL", "XDG_CONFIG_HOME"):
        env.pop(var, None)
    out = {key: subprocess.run(["git", "config", "--global", key], env=env, capture_output=True,
                               text=True, check=True).stdout.strip() for key in ("user.name", "user.email")}
    assert out == {"user.name": "Eval", "user.email": "eval@example.com"}


def test_uv_python_dir_names_the_command_when_uv_cannot_start(monkeypatch):
    from evals import runner

    def missing(*args, **kwargs):
        raise FileNotFoundError("no uv")

    runner.uv_python_dir.cache_clear()
    monkeypatch.setattr(runner.subprocess, "run", missing)
    try:
        with pytest.raises(RuntimeError, match=r"`uv python dir` failed: .*no uv"):
            runner.uv_python_dir()
    finally:
        runner.uv_python_dir.cache_clear()


def test_uv_python_dir_names_the_command_and_stderr_on_a_non_zero_exit(monkeypatch):
    from evals import runner

    def failing(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="boom\n")

    runner.uv_python_dir.cache_clear()
    monkeypatch.setattr(runner.subprocess, "run", failing)
    try:
        with pytest.raises(RuntimeError, match=r"`uv python dir` failed: boom$"):
            runner.uv_python_dir()
    finally:
        runner.uv_python_dir.cache_clear()
