"""Shared helpers for the tests of `scripts/host.py`.

A fake executable is a Python script plus a `.cmd` shim, so it runs on Linux
and on Windows. The fake `gh` records every call as one JSON line in $FAKE_LOG
and answers from the JSON file $FAKE_GH. No shell is used anywhere.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
HOST = REPO_ROOT / "plugins" / "xxthunder-dev-skills" / "scripts" / "host.py"

PROXY_VARS = ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy")

GH_FAKE = '''\
import json
import os
import sys
from pathlib import Path

args = sys.argv[1:]
cfg = json.loads(Path(os.environ["FAKE_GH"]).read_text(encoding="utf-8"))
with open(os.environ["FAKE_LOG"], "a", encoding="utf-8", newline="\\n") as f:
    f.write(json.dumps(args) + "\\n")

key = " ".join(args[:2])
fail = cfg.get("fail", {}).get(key)
if fail:
    sys.stderr.write(fail.get("stderr", ""))
    sys.exit(fail.get("exit", 1))

if key == "auth token":
    host = args[args.index("--hostname") + 1]
    token = cfg.get("token", {}).get(host)
    if token:
        print(token)
        sys.exit(0)
    sys.exit(1)
if key == "pr list":
    print(cfg.get("pr_list", ""))
    sys.exit(0)
if key == "pr create":
    print(cfg.get("create_url", ""))
    sys.exit(0)
if key == "pr checks":
    sys.stdout.write(cfg.get("checks_stdout", ""))
    sys.stderr.write(cfg.get("checks_stderr", ""))
    sys.exit(cfg.get("checks_exit", 0))
sys.exit(0)
'''


def fake_bin(tmp_path: Path, name: str, script: str) -> Path:
    """Write a Python fake `name` and its `.cmd` shim; return the directory."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    exe = bin_dir / name
    exe.write_text(f"#!{sys.executable}\n{script}", encoding="utf-8", newline="\n")
    exe.chmod(0o755)
    (bin_dir / f"{name}.cmd").write_text(
        f'@echo off\r\n"{sys.executable}" "%~dp0{name}" %*\r\n', encoding="utf-8", newline=""
    )
    return bin_dir


def write_gh(tmp_path: Path, **config) -> Path:
    """Install the fake `gh` answering from `config`; return its directory.

    config keys: token {host: token}, pr_list, create_url, checks_exit, checks_stdout, checks_stderr,
    fail {"pr create": {"exit": 1, "stderr": "..."}}.
    """
    (tmp_path / "fake-gh.json").write_text(json.dumps(config), encoding="utf-8")
    return fake_bin(tmp_path, "gh", GH_FAKE)


def env(tmp_path: Path, bin_dir: Path) -> dict:
    """An environment confined to tmp_path, with bin_dir first on PATH."""
    e = dict(os.environ)
    for var in PROXY_VARS:
        e.pop(var, None)
    e["HOME"] = e["USERPROFILE"] = str(tmp_path)
    e["XDG_CONFIG_HOME"] = str(tmp_path / "xdg")
    e["PATH"] = str(bin_dir) + os.pathsep + e.get("PATH", "")
    e["FAKE_GH"] = str(tmp_path / "fake-gh.json")
    e["FAKE_LOG"] = str(tmp_path / "fake-log.jsonl")
    return e


def run(*args, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HOST), *map(str, args)],
        capture_output=True, text=True, env=env,
    )


def repo(tmp_path: Path, origin_url: str) -> Path:
    """A git repository whose raw `origin` URL is `origin_url`."""
    path = tmp_path / "work"
    path.mkdir()
    subprocess.run(["git", "init", "-q", str(path)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(path), "remote", "add", "origin", origin_url],
        check=True, capture_output=True,
    )
    return path


def log(tmp_path: Path) -> list[list[str]]:
    """The fake's recorded calls, one argument list each; [] if none."""
    f = tmp_path / "fake-log.jsonl"
    if not f.exists():
        return []
    return [json.loads(line) for line in f.read_text(encoding="utf-8").splitlines()]
