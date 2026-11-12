# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6"]
# ///
"""The closed loop's one way to talk to the host of a repository.

Opens or updates a pull request and waits for its CI checks, through a backend per host:
GitHub (`gh`), Gitea (`tea`) or Bitbucket Server (REST API).

Subcommands (output is JSON on stdout, errors go to stderr):

  pr <worktree> --base <branch> --head <branch> --title <text> --body-file <path>
      Opens a pull request from <head> into <base>, or updates the open one for <head>:
      {"backend", "action": "created"|"updated", "url": <pull request web URL>}.
  checks <worktree> --head <branch> [--interval <seconds, default 30>]
         [--timeout <seconds, default 7200>]
      Waits until the checks on <head> are done:
      {"backend", "state": "green"|"red", "checks": [{"name", "state"}]}.
      GitHub: `gh pr checks --watch` waits; exit 0 is green, exit 1 with its check table
      is red, any other failure of gh is exit 3 (exit 2 on a remote without a host);
      checks is [].

The remote is the raw `remote.origin.url` of <worktree>. The backend is the first that
serves its host, in this order:
  1. Bitbucket: a profile in ~/.bitbucket/profiles.json whose url has that hostname.
  2. Gitea: a login in tea's config.yml ($XDG_CONFIG_HOME/tea, else ~/.config/tea) whose
     url has that hostname; `tea` must be on PATH.
  3. GitHub: `gh auth token --hostname <host>` succeeds. A remote without a host (a local
     path or file:// URL) always goes to GitHub.

Exit codes (both subcommands):
  0  done / checks green
  1  checks red
  2  unsupported remote: "unsupported remote <url>: <what is missing>"
  3  the host call failed or the checks timed out: the CLI's or API's message

Gitea: `tea pr create` / `tea pr edit` (with --login and --repo) open or update the pull
request; the REST API (<login url>/api/v1, the login's token) finds the open one by its
head branch; `checks` polls the combined commit status of <head> as the worktree has it
(the pushed commit), never the pull request's head.sha, which Gitea updates late; <head>
not a branch in the worktree is exit 3. The tea flags follow tea's documentation; this
repository's tests run a fake tea, not a real one. `checks` waits until the status has at
least one entry and is no longer pending; green only on success.

A token is never printed, also not in an error message. Stdlib plus PyYAML; no shell, so
it runs on Windows.
"""
from __future__ import annotations

import argparse
import http.client
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse

import yaml

SCP_RE = re.compile(r"^(?:[^@/]+@)?(?P<host>[^:/]+):(?P<path>.+)$")
DRIVE_RE = re.compile(r"^[A-Za-z]:[\\/]")


class Unsupported(Exception):
    """No backend serves the remote: exit 2."""


class HostError(Exception):
    """The host call failed or timed out: exit 3."""


class Backend(Protocol):
    name: str

    def pr(self, worktree: str, base: str, head: str, title: str, body: str) -> tuple[str, str]:
        """Open or update the pull request; return (action, url). `body` is the file path."""

    def checks(self, worktree: str, head: str, interval: float,
               timeout: float) -> tuple[bool, list[dict]]:
        """Wait for the checks on `head`; return (green, [{"name", "state"}])."""


def split_remote(url: str) -> tuple[str | None, str]:
    """(hostname without port and user, path without leading / and trailing .git).

    A local path or file:// URL gives (None, the path).
    """
    if DRIVE_RE.match(url):
        return None, url.removesuffix(".git")
    if "://" in url:
        parsed = urlparse(url)
        if parsed.scheme == "file" or not parsed.hostname:
            return None, parsed.path.removesuffix(".git")
        return parsed.hostname, parsed.path.strip("/").removesuffix(".git")
    m = SCP_RE.match(url)
    if m:
        return m["host"].lower(), m["path"].strip("/").removesuffix(".git")
    return None, url.removesuffix(".git")


def hostname(url: str) -> str | None:
    return urlparse(url).hostname


def executable(name: str) -> str | None:
    """The full path of `name` on PATH, so `.cmd` shims resolve on Windows."""
    return shutil.which(name)


def run(exe: str, *args: str, cwd: str | None = None,
        timeout: float | None = None) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            [exe, *args], capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=cwd, timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        raise HostError(f"timed out after {timeout:g} s: {Path(exe).name} {' '.join(args[:2])}") from e
    except OSError as e:
        raise HostError(f"cannot run {Path(exe).name}: {e.strerror or e}") from e


def message(out: subprocess.CompletedProcess, default: str) -> str:
    return out.stderr.strip() or out.stdout.strip() or default


# ---------- GitHub ----------


class GitHub:
    name = "github"

    def __init__(self, gh: str, served: bool) -> None:
        self.gh = gh
        # A failing call on a host gh does not serve means the remote is unsupported.
        self.error = HostError if served else Unsupported

    def call(self, worktree: str, *args: str,
             timeout: float | None = None) -> subprocess.CompletedProcess:
        out = run(self.gh, *args, cwd=worktree, timeout=timeout)
        if out.returncode != 0:
            raise self.error(message(out, f"gh {' '.join(args[:2])} failed"))
        return out

    def pr(self, worktree: str, base: str, head: str, title: str, body: str) -> tuple[str, str]:
        found = self.call(worktree, "pr", "list", "--head", head, "--state", "open",
                          "--json", "url", "--jq", ".[0].url").stdout.strip()
        if found:
            self.call(worktree, "pr", "edit", found, "--title", title, "--body-file", body)
            return "updated", found
        out = self.call(worktree, "pr", "create", "--base", base, "--head", head,
                        "--title", title, "--body-file", body)
        lines = [line.strip() for line in out.stdout.splitlines() if line.strip()]
        if not lines:
            raise self.error("gh pr create printed no pull request URL")
        return "created", lines[-1]

    def checks(self, worktree: str, head: str, interval: float,
               timeout: float) -> tuple[bool, list[dict]]:
        out = run(self.gh, "pr", "checks", head, "--watch", cwd=worktree, timeout=timeout)
        if out.returncode == 0:
            return True, []
        # Exit 1 with the check table means a check failed; anything else (exit 8
        # pending, "no checks reported", auth) is gh failing, not the CI.
        if out.returncode == 1 and out.stdout.strip():
            return False, []
        raise self.error(message(out, f"gh pr checks failed with exit {out.returncode}"))


# ---------- Gitea ----------


class Gitea:
    name = "gitea"
    PAGE = 50

    def __init__(self, tea: str, login: dict, path: str) -> None:
        self.tea = tea
        self.login = str(login.get("name", ""))
        self.token = str(login.get("token", ""))
        self.api_base = str(login.get("url", "")).rstrip("/") + "/api/v1"
        self.repo = path
        self.where = ("--login", self.login, "--repo", self.repo)

    def api(self, path: str):
        request = urllib.request.Request(self.api_base + path, headers={
            "Authorization": f"token {self.token}", "Accept": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try:
                detail = json.loads(e.read().decode("utf-8")).get("message", "")
            except (OSError, ValueError, AttributeError):
                detail = ""
            raise HostError(f"Gitea API {e.code} on GET {path}: {detail or e.reason}") from None
        except urllib.error.URLError as e:
            raise HostError(f"Gitea API on GET {path}: {e.reason}") from None
        except (OSError, ValueError, http.client.HTTPException) as e:
            raise HostError(f"Gitea API on GET {path}: {e}") from None

    @staticmethod
    def field(pull: dict, *keys: str):
        """pull[k1][k2]…; a missing field is a HostError, not a traceback."""
        value = pull
        for key in keys:
            if not isinstance(value, dict) or key not in value:
                raise HostError(f"Gitea API answer without {'.'.join(keys)} "
                                f"for pull request {pull.get('number', '?')}")
            value = value[key]
        return value

    def open_pull(self, head: str) -> dict | None:
        page = 1
        while True:
            pulls = self.api(f"/repos/{self.repo}/pulls?state=open"
                             f"&limit={self.PAGE}&page={page}")
            # Gitea may cap the limit below PAGE, so only an empty page is the end.
            if not isinstance(pulls, list) or not pulls:
                return None
            for pull in pulls:
                if isinstance(pull, dict) and (pull.get("head") or {}).get("ref") == head:
                    return pull
            page += 1

    def call(self, worktree: str, *args: str) -> None:
        out = run(self.tea, *args, cwd=worktree)
        if out.returncode != 0:
            raise HostError(message(out, f"tea {' '.join(args[:2])} failed"))

    def pr(self, worktree: str, base: str, head: str, title: str, body: str) -> tuple[str, str]:
        try:
            text = Path(body).read_text(encoding="utf-8")
        except OSError as e:
            raise HostError(f"cannot read the body file {body}: {e.strerror or e}") from None
        found = self.open_pull(head)
        if found:
            url = self.field(found, "html_url")
            self.call(worktree, "pr", "edit", str(self.field(found, "number")), *self.where,
                      "--title", title, "--description", text)
            return "updated", url
        self.call(worktree, "pr", "create", *self.where, "--base", base, "--head", head,
                  "--title", title, "--description", text)
        found = self.open_pull(head)
        if not found:
            raise HostError(f"tea pr create succeeded, but no open pull request for {head}")
        return "created", self.field(found, "html_url")

    def head_sha(self, worktree: str, head: str) -> str:
        """The commit to poll: <head> in the worktree, i.e. the pushed commit.

        Gitea updates the pull request's head.sha only some time after a push, so a stale
        head with a final success would read green; so there is no fallback to it.
        """
        git = executable("git") or "git"
        out = run(git, "-C", worktree, "rev-parse", "--verify", "--quiet", f"{head}^{{commit}}")
        sha = out.stdout.strip()
        if out.returncode != 0 or not sha:
            raise HostError(f"{head} is not a branch in {worktree}: cannot tell which commit "
                            f"to wait for")
        return sha

    def checks(self, worktree: str, head: str, interval: float,
               timeout: float) -> tuple[bool, list[dict]]:
        deadline = time.monotonic() + timeout
        sha = self.head_sha(worktree, head)
        while True:
            status = self.api(f"/repos/{self.repo}/commits/{sha}/status")
            if not isinstance(status, dict):
                raise HostError(f"Gitea API answer for the status of {sha} is not an object")
            entries = status.get("statuses") or []
            # No entry yet means the CI has not reported: keep waiting, never green.
            if entries and status.get("state") != "pending":
                return status.get("state") == "success", [
                    {"name": s.get("context"), "state": s.get("status")} for s in entries]
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise HostError(f"timed out after {timeout:g} s waiting for the checks on {head}")
            time.sleep(min(interval, remaining))


# ---------- backend choice ----------


def bitbucket_served(host: str) -> bool:
    file = Path.home() / ".bitbucket" / "profiles.json"
    if not file.is_file():
        return False
    try:
        profiles = json.loads(file.read_text(encoding="utf-8")).get("profiles", {})
    except (OSError, ValueError, AttributeError):
        return False
    return any(isinstance(p, dict) and hostname(p.get("url", "")) == host
               for p in profiles.values())


def tea_config() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "tea" / "config.yml"


def tea_login(host: str) -> dict | None:
    """The first login in tea's config whose url has hostname `host`."""
    file = tea_config()
    if not file.is_file():
        return None
    try:
        logins = (yaml.safe_load(file.read_text(encoding="utf-8")) or {}).get("logins") or []
    except (OSError, yaml.YAMLError, AttributeError):
        return None
    return next((login for login in logins
                 if isinstance(login, dict) and hostname(login.get("url", "")) == host), None)


def gh_served(gh: str, host: str) -> bool:
    out = run(gh, "auth", "token", "--hostname", host)
    # The token itself is discarded here; it is never printed.
    return out.returncode == 0 and bool(out.stdout.strip())


def choose(host: str | None, path: str) -> Backend:
    """The first backend that serves `host`; raises Unsupported if none does."""
    gh = executable("gh")
    if host is None:
        if not gh:
            raise Unsupported(f"no gh on PATH for the local remote {path}")
        return GitHub(gh, served=False)
    if bitbucket_served(host):
        raise HostError(f"the Bitbucket backend is not implemented yet ({host})")
    login = tea_login(host)
    if login:
        tea = executable("tea")
        if not tea:
            raise Unsupported(f"tea login for {host} found, but no tea on PATH")
        return Gitea(tea, login, path)
    if gh and gh_served(gh, host):
        return GitHub(gh, served=True)
    raise Unsupported(f"no Bitbucket profile, tea login or gh token for {host}")


# ---------- CLI ----------


def remote_url(worktree: str) -> str:
    git = executable("git") or "git"
    out = run(git, "-C", worktree, "config", "--get", "remote.origin.url")
    url = out.stdout.strip()
    if out.returncode != 0 or not url:
        raise Unsupported("no remote.origin.url")
    return url


def cmd_pr(args: argparse.Namespace, backend: Backend) -> int:
    action, url = backend.pr(args.worktree, args.base, args.head, args.title, args.body_file)
    print(json.dumps({"backend": backend.name, "action": action, "url": url}))
    return 0


def cmd_checks(args: argparse.Namespace, backend: Backend) -> int:
    green, checks = backend.checks(args.worktree, args.head, args.interval, args.timeout)
    print(json.dumps({"backend": backend.name, "state": "green" if green else "red",
                      "checks": checks}))
    return 0 if green else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pull requests and CI checks on the repository's host.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("pr", help="open or update the pull request for a branch")
    p.add_argument("worktree")
    p.add_argument("--base", required=True)
    p.add_argument("--head", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--body-file", required=True)
    p.set_defaults(func=cmd_pr)

    p = sub.add_parser("checks", help="wait for the CI checks on a branch")
    p.add_argument("worktree")
    p.add_argument("--head", required=True)
    p.add_argument("--interval", type=float, default=30)
    p.add_argument("--timeout", type=float, default=7200)
    p.set_defaults(func=cmd_checks)

    args = parser.parse_args(argv)
    url = None
    try:
        url = remote_url(args.worktree)
        backend = choose(*split_remote(url))
        return args.func(args, backend)
    except Unsupported as e:
        print(f"unsupported remote {url or args.worktree}: {e}", file=sys.stderr)
        return 2
    except HostError as e:
        print(str(e), file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
