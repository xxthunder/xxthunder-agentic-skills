"""Run cases headless with `claude -p` and collect the results.

A run sees only its sandbox: user settings are not loaded, MCP servers are
not started, every store variable pair is cleared from the environment and
only the pairs the case asks for point into the sandbox.
"""
from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

from evals.cases import Case
from evals.fixture import build, mark_seed, snapshot

PLUGIN = "plugins/xxthunder-dev-skills"
STORE_PREFIXES = ("BOARD", "LOGBOOK", "LEARNINGS")
PARENT_SESSION = ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT")
TOOLS = ("Bash", "Read", "Edit", "Write", "Glob", "Grep", "Skill")
TIMEOUT = 900


def remove_tree(path: Path) -> None:
    """Delete *path* if it exists, read-only files included — git writes its objects
    read-only, and on Windows `rmtree` refuses to delete those."""
    def clear_and_retry(func, target, _exc):
        os.chmod(target, stat.S_IWRITE)
        func(target)

    if not path.exists():
        return
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=clear_and_retry)
    else:
        shutil.rmtree(path, onerror=clear_and_retry)


def export_plugin(repo: Path, ref: str, dest: Path) -> Path:
    """The plugin as it is at *ref*, extracted under *dest*; returns its directory."""
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "plugin.tar"
        r = subprocess.run(["git", "archive", "--format=tar", "-o", str(archive), ref, PLUGIN],
                           cwd=repo, capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError(f"cannot export {PLUGIN} at {ref}: {r.stderr.strip()}")
        remove_tree(dest / "plugins")
        with tarfile.open(archive) as tar:
            tar.extractall(dest, **({"filter": "data"} if hasattr(tarfile, "data_filter") else {}))
    return dest / PLUGIN


def config_dir(env: dict[str, str]) -> Path:
    return Path(env["CLAUDE_CONFIG_DIR"]) if env.get("CLAUDE_CONFIG_DIR") else Path.home() / ".claude"


def version_key(path: Path) -> tuple[int, ...]:
    return tuple(int(p) if p.isdigit() else -1 for p in path.name.split("."))


def dependency_dirs(plugin: Path, config: Path) -> list[Path]:
    """The installed plugins *plugin* depends on, newest cached version of each."""
    manifest = json.loads((plugin / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    dirs = []
    for dep in manifest.get("dependencies", []):
        versions = sorted((p for p in (config / "plugins" / "cache" / dep["marketplace"] / dep["name"]).glob("*")
                           if p.is_dir()), key=version_key)
        if not versions:
            raise RuntimeError(f"dependency {dep['name']}@{dep['marketplace']} is not installed — "
                               f"`claude plugin install {dep['name']}@{dep['marketplace']}`")
        dirs.append(versions[-1])
    return dirs


def clean_env(base: dict[str, str], sandbox: Path, board: bool, logbook: bool,
              learnings: bool = False) -> dict[str, str]:
    pairs = {k[: -len("_REMOTE")] for k in base if k.endswith("_REMOTE")} | set(STORE_PREFIXES)
    env = {k: v for k, v in base.items()
           if k not in PARENT_SESSION and not any(k in (f"{p}_PATH", f"{p}_REMOTE") for p in pairs)}
    env["XDG_CACHE_HOME"] = str(sandbox / "cache")
    for prefix, wanted in (("BOARD", board), ("LOGBOOK", logbook), ("LEARNINGS", learnings)):
        if wanted:
            env[f"{prefix}_PATH"] = str(sandbox / "store")
            env[f"{prefix}_REMOTE"] = str(sandbox / "remotes" / "store.git")
    return env


def claude_command(prompt: str, plugin_dirs: list[Path], sandbox: Path) -> list[str]:
    cmd = ["claude", "-p", prompt, "--output-format", "stream-json", "--verbose",
           "--setting-sources", "project", "--strict-mcp-config", "--add-dir", str(sandbox)]
    for d in plugin_dirs:
        cmd += ["--plugin-dir", str(d)]
    return cmd + ["--allowedTools", *TOOLS]


def parse_stream(stream: str) -> tuple[str, list[str], list[str]]:
    """The assistant's final answer, the skills it invoked and the Bash commands it ran,
    from a stream-json transcript.

    The output is the `result` event's text, so narration between tool calls is
    not graded. A run cut off before that event falls back to all of its text.
    """
    output, skills, commands, final = "", [], [], None
    for line in stream.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "result" and isinstance(event.get("result"), str):
            final = event["result"]
        if event.get("type") != "assistant":
            continue
        for block in event["message"].get("content", []):
            if block.get("type") == "text":
                output += block["text"] + "\n"
            elif block.get("type") == "tool_use" and block.get("name") == "Skill":
                skills.append(block["input"].get("skill", ""))
            elif block.get("type") == "tool_use" and block.get("name") == "Bash":
                commands.append(block["input"].get("command", ""))
    return (output if final is None else final), skills, commands


def run_one(case: Case, plugin_dirs: list[Path], n: int, out: Path) -> dict:
    sandbox = out / f"{case.name}-{n}"
    remove_tree(sandbox)
    build(sandbox, case.board_contract)
    if case.setup:
        case.setup(sandbox / "checkouts" / "demo")
        mark_seed(sandbox)
    env = clean_env(dict(os.environ), sandbox, case.board, case.logbook, case.learnings)
    try:
        r = subprocess.run(claude_command(case.prompt, plugin_dirs, sandbox), cwd=sandbox / "checkouts" / "demo",
                           env=env, capture_output=True, text=True, encoding="utf-8", timeout=TIMEOUT)
        stream, err = r.stdout, r.stderr
    except subprocess.TimeoutExpired as e:
        stream, err = e.stdout or "", f"timed out after {TIMEOUT}s"
        stream = stream.decode() if isinstance(stream, bytes) else stream
    (sandbox / "stream.jsonl").write_text(stream, encoding="utf-8")
    (sandbox / "stderr.txt").write_text(err or "", encoding="utf-8")
    output, skills, commands = parse_stream(stream)
    (sandbox / "output.md").write_text(output, encoding="utf-8")
    try:
        failures = case.check(snapshot(sandbox, output, skills, commands))
    except Exception as e:  # a broken end state is a failure, not a crash
        failures = [f"grading error: {e!r}"]
    result = {"case": case.name, "run": n, "pass": not failures, "failures": failures}
    (sandbox / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def report(out: Path) -> list[str]:
    results = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(out.glob("*/result.json"))]
    by_case: dict[str, list[dict]] = {}
    for r in results:
        by_case.setdefault(r["case"], []).append(r)
    lines = []
    for name, runs in by_case.items():
        lines.append(f"{name:24} {sum(r['pass'] for r in runs)}/{len(runs)}")
    for name, runs in by_case.items():
        for r in sorted(runs, key=lambda r: r["run"]):
            if not r["pass"]:
                lines.append(f"  {name}#{r['run']}: {'; '.join(r['failures'])}")
    return lines
