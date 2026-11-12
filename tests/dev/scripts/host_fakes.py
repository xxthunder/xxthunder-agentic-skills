"""Shared helpers for the tests of `scripts/host.py`.

A fake executable is a Python script plus a `.cmd` shim, so it runs on Linux
and on Windows. The fake `gh` records every call as one JSON line in $FAKE_LOG
and answers from the JSON file $FAKE_GH. No shell is used anywhere.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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


# ---------- Gitea: fake `tea` and fake REST API ----------

TEA_FAKE = '''\
import json
import os
import sys
from pathlib import Path

args = sys.argv[1:]
with open(os.environ["FAKE_LOG"], "a", encoding="utf-8", newline="\\n") as f:
    f.write(json.dumps(args) + "\\n")
if args[:2] == ["pr", "create"]:
    if os.environ.get("FAKE_TEA_FAIL"):
        sys.stderr.write(os.environ["FAKE_TEA_FAIL"])
        sys.exit(1)
    Path(os.environ["FAKE_TEA_MARK"]).write_text("created", encoding="utf-8")
sys.exit(0)
'''


def write_tea(tmp_path: Path) -> Path:
    """Install the fake `tea`; `pr create` leaves a marker the fake API reads."""
    return fake_bin(tmp_path, "tea", TEA_FAKE)


def write_tea_config(tmp_path: Path, port: int, token: str = "secret-t") -> None:
    """tea's config.yml (JSON is valid YAML) with the login `home` for 127.0.0.1."""
    cfg = tmp_path / "xdg" / "tea" / "config.yml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    login = {"name": "home", "url": f"http://127.0.0.1:{port}", "token": token}
    cfg.write_text(json.dumps({"logins": [login]}), encoding="utf-8")


class FakeGitea:
    """A Gitea API on 127.0.0.1, scripted and recording.

    pulls: open PRs listed until the fake `tea` created one; pulls_after: listed afterwards.
    statuses: answers of the status endpoint in order, the last one repeats.
    pull_pages: if set, the open PRs per `page` query parameter (1-based); an absent page is empty.
    stale_sha: a commit whose status endpoint always answers a final success.
    errors: {path fragment: (http code, json body)} answered instead of the script.
    requests: one dict per request: method, path, headers, body.
    """

    def __init__(self, mark: Path) -> None:
        self.mark = mark
        self.pulls: list = []
        self.pulls_after: list = []
        self.statuses: list = []
        self.pull_pages: list | None = None
        self.stale_sha: str | None = None
        self.errors: dict = {}
        self.requests: list = []
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):  # keep pytest output quiet
                pass

            def do_GET(self):
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length).decode("utf-8") if length else ""
                fake.requests.append({"method": "GET", "path": self.path,
                                      "headers": dict(self.headers), "body": body})
                code, payload = fake.answer(self.path)
                data = json.dumps(payload).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def answer(self, path: str):
        for fragment, (code, body) in self.errors.items():
            if fragment in path:
                return code, body
        if re.search(r"/pulls(\?|$)", path):
            if self.pull_pages is not None:
                m = re.search(r"[?&]page=(\d+)", path)
                page = int(m.group(1)) if m else 1
                return 200, self.pull_pages[page - 1] if page <= len(self.pull_pages) else []
            return 200, self.pulls_after if self.mark.exists() else self.pulls
        if path.split("?")[0].endswith("/status"):
            if self.stale_sha and f"/commits/{self.stale_sha}/status" in path:
                return 200, {"state": "success",
                             "statuses": [{"context": "ci/old", "status": "success"}]}
            n = len([r for r in self.status_requests()
                     if not (self.stale_sha and f"/commits/{self.stale_sha}/" in r["path"])]) - 1
            return 200, self.statuses[min(n, len(self.statuses) - 1)]
        return 404, {"message": "not found"}

    def status_requests(self) -> list:
        return [r for r in self.requests if r["path"].split("?")[0].endswith("/status")]

    def start(self) -> "FakeGitea":
        self.thread.start()
        return self

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()


def commit_on_feat(work) -> str:
    """A real commit on branch `feat` in the worktree; return its sha."""
    git = ["git", "-C", str(work), "-c", "user.name=t", "-c", "user.email=t@example.com"]
    subprocess.run([*git, "checkout", "-q", "-b", "feat"], check=True, capture_output=True)
    subprocess.run([*git, "commit", "-q", "--allow-empty", "-m", "c"], check=True, capture_output=True)
    out = subprocess.run([*git, "rev-parse", "feat"], check=True, capture_output=True, text=True)
    return out.stdout.strip()


# ---------- Bitbucket Server: profile and fake REST API ----------

def write_bitbucket_profile(tmp_path: Path, port: int, token: str = "secret-b",
                            ca_bundle: str | None = None) -> None:
    """~/.bitbucket/profiles.json with the profile `work` for 127.0.0.1."""
    cfg = tmp_path / ".bitbucket" / "profiles.json"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    profile = {"url": f"http://127.0.0.1:{port}", "token": token}
    if ca_bundle:
        profile["ca_bundle"] = ca_bundle
    cfg.write_text(json.dumps({"profiles": {"work": profile}}), encoding="utf-8")


class FakeBitbucket:
    """A Bitbucket Server REST API on 127.0.0.1, scripted and recording.

    pr_pages: the answers of the pull-request lookup, one `values` list per page; page i
    is served for `start=<10*i>` and says isLastPage false until the final one.
    created: the answer to a POST of a pull request; updated: the answer to a PUT.
    statuses: the `values` lists of the build-status endpoint in order, the last one repeats.
    stale_sha: a commit whose build-status endpoint always answers a final SUCCESSFUL.
    errors: {path fragment: (http code, json body)} answered instead of the script.
    requests: one dict per request: method, path, headers, body (parsed JSON or None).
    """

    def __init__(self) -> None:
        self.pr_pages: list = [[]]
        self.created: dict = {}
        self.updated: dict = {}
        self.statuses: list = []
        self.stale_sha: str | None = None
        self.errors: dict = {}
        self.requests: list = []
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):  # keep pytest output quiet
                pass

            def handle_any(self):
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length).decode("utf-8") if length else ""
                fake.requests.append({"method": self.command, "path": self.path,
                                      "headers": dict(self.headers),
                                      "body": json.loads(raw) if raw else None})
                code, payload = fake.answer(self.command, self.path)
                data = json.dumps(payload).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            do_GET = do_POST = do_PUT = handle_any

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def answer(self, method: str, path: str):
        for fragment, (code, body) in self.errors.items():
            if fragment in path:
                return code, body
        bare = path.split("?")[0]
        if "/build-status/1.0/commits/" in bare:
            if self.stale_sha and bare.endswith(f"/commits/{self.stale_sha}"):
                return 200, {"values": [{"state": "SUCCESSFUL", "name": "ci/old"}],
                             "isLastPage": True}
            n = len([r for r in self.status_requests()
                     if not (self.stale_sha and r["path"].split("?")[0].endswith(self.stale_sha))]) - 1
            return 200, {"values": self.statuses[min(n, len(self.statuses) - 1)],
                         "isLastPage": True}
        if bare.endswith("/pull-requests") and method == "GET":
            m = re.search(r"[?&]start=(\d+)", path)
            page = int(m.group(1)) // 10 if m else 0
            last = page >= len(self.pr_pages) - 1
            values = self.pr_pages[page] if page < len(self.pr_pages) else []
            answer = {"values": values, "isLastPage": last}
            if not last:
                answer["nextPageStart"] = (page + 1) * 10
            return 200, answer
        if bare.endswith("/pull-requests") and method == "POST":
            return 201, self.created
        if "/pull-requests/" in bare and method == "PUT":
            return 200, self.updated
        return 404, {"errors": [{"message": "not found"}]}

    def status_requests(self) -> list:
        return [r for r in self.requests if "/build-status/1.0/commits/" in r["path"]]

    def start(self) -> "FakeBitbucket":
        self.thread.start()
        return self

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()
