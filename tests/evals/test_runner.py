"""The runner's plumbing: plugin export, dependency lookup, environment, command, stream."""
from __future__ import annotations

import json
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
    assert env["PATH"] == "/bin" and env["LD_LIBRARY_PATH"] == "/lib"
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
