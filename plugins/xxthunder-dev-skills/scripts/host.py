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

Bitbucket Server: the REST API (<profile url>/rest/api/1.0, `Authorization: Bearer <token>`,
the profile's ca_bundle as CA file when set) does it all. The remote path, without a
leading scm/, is <project>/<repo>; the project key keeps its case. `pr` looks up the open
outgoing pull request at refs/heads/<head> (all pages) and updates its title and
description with its version, or creates one from <head> into <base>; the URL is
links.self[0].href. `checks` polls the build statuses (Jenkins' verdict) of <head> as the
worktree has it, never the pull request's latestCommit; <head> not a branch in the
worktree is exit 3. It waits until there is at least one status and none is INPROGRESS;
green only when all are SUCCESSFUL. Each check is {"name": name or key, "state": the raw
state}.

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
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, Protocol
from urllib.parse import quote, urlparse

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


# ---------- REST helpers (Gitea, Bitbucket) ----------


class RestApi:
    """JSON over HTTP with a token; every failure is a HostError that never holds the token.

    `detail` pulls the server's message out of an error answer's JSON body.
    """

    def __init__(self, label: str, base: str, auth: str, detail: Callable[[dict], str],
                 ca_bundle: str | None = None) -> None:
        self.label = label
        self.base = base.rstrip("/")
        self.headers = {"Authorization": auth, "Accept": "application/json"}
        self.detail = detail
        self.context = None
        if ca_bundle:
            try:
                self.context = ssl.create_default_context(cafile=ca_bundle)
            except (OSError, ssl.SSLError) as e:
                raise HostError(f"cannot load the CA bundle {ca_bundle}: {e}") from None

    def call(self, method: str, path: str, payload: dict | None = None):
        headers = dict(self.headers)
        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(self.base + path, data=data, headers=headers,
                                         method=method)
        where = f"{self.label} API on {method} {path}"
        try:
            with urllib.request.urlopen(request, timeout=60, context=self.context) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try:
                detail = self.detail(json.loads(e.read().decode("utf-8")))
            except (OSError, ValueError, AttributeError, TypeError, KeyError, IndexError):
                detail = ""
            raise HostError(f"{self.label} API {e.code} on {method} {path}: "
                            f"{detail or e.reason}") from None
        except urllib.error.URLError as e:
            raise HostError(f"{where}: {e.reason}") from None
        except (OSError, ValueError, http.client.HTTPException) as e:
            raise HostError(f"{where}: {e}") from None


def field(answer, *keys, where: str):
    """answer[k1][k2]…; a missing field is a HostError naming it, not a traceback."""
    value = answer
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        elif isinstance(value, list) and isinstance(key, int) and -len(value) <= key < len(value):
            value = value[key]
        else:
            raise HostError(f"{where} without {'.'.join(map(str, keys))}")
    return value


def read_body(body: str) -> str:
    try:
        return Path(body).read_text(encoding="utf-8")
    except OSError as e:
        raise HostError(f"cannot read the body file {body}: {e.strerror or e}") from None


def head_sha(worktree: str, head: str) -> str:
    """The commit to poll: <head> in the worktree, i.e. the pushed commit.

    The host updates the pull request's head commit only some time after a push, so a stale
    head with a final success would read green; so there is no fallback to it.
    """
    git = executable("git") or "git"
    out = run(git, "-C", worktree, "rev-parse", "--verify", "--quiet", f"{head}^{{commit}}")
    sha = out.stdout.strip()
    if out.returncode != 0 or not sha:
        raise HostError(f"{head} is not a branch in {worktree}: cannot tell which commit "
                        f"to wait for")
    return sha


def wait_for(poll: Callable[[], tuple[bool, list[dict]] | None], head: str,
             interval: float, timeout: float) -> tuple[bool, list[dict]]:
    """Call `poll` until it gives a verdict (not None), at most `timeout` seconds."""
    deadline = time.monotonic() + timeout
    while True:
        verdict = poll()
        if verdict is not None:
            return verdict
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise HostError(f"timed out after {timeout:g} s waiting for the checks on {head}")
        time.sleep(min(interval, remaining))


# ---------- Gitea ----------


class Gitea:
    name = "gitea"
    PAGE = 50

    def __init__(self, tea: str, login: dict, path: str) -> None:
        self.tea = tea
        self.login = str(login.get("name", ""))
        self.rest = RestApi("Gitea", str(login.get("url", "")).rstrip("/") + "/api/v1",
                            f"token {login.get('token', '')}",
                            lambda answer: answer.get("message", ""))
        self.repo = path
        self.where = ("--login", self.login, "--repo", self.repo)

    @staticmethod
    def field(pull: dict, *keys: str):
        return field(pull, *keys, where=f"Gitea API answer for pull request "
                                        f"{pull.get('number', '?')}")

    def open_pull(self, head: str) -> dict | None:
        page = 1
        while True:
            pulls = self.rest.call("GET", f"/repos/{self.repo}/pulls?state=open"
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
        text = read_body(body)
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

    def checks(self, worktree: str, head: str, interval: float,
               timeout: float) -> tuple[bool, list[dict]]:
        sha = head_sha(worktree, head)

        def poll():
            status = self.rest.call("GET", f"/repos/{self.repo}/commits/{sha}/status")
            if not isinstance(status, dict):
                raise HostError(f"Gitea API answer for the status of {sha} is not an object")
            entries = status.get("statuses") or []
            # No entry yet means the CI has not reported: keep waiting, never green.
            if not entries or status.get("state") == "pending":
                return None
            return status.get("state") == "success", [
                {"name": s.get("context"), "state": s.get("status")} for s in entries]

        return wait_for(poll, head, interval, timeout)


# ---------- Bitbucket Server ----------


def bitbucket_detail(answer: dict) -> str:
    return "; ".join(str(e.get("message", "")) for e in answer.get("errors") or []
                     if isinstance(e, dict))


class Bitbucket:
    name = "bitbucket"

    def __init__(self, profile: dict, path: str) -> None:
        parts = path.removeprefix("scm/").split("/")
        if len(parts) != 2 or not all(parts):
            raise Unsupported(f"{path} is not a Bitbucket <project>/<repo> path")
        self.project, self.slug = parts
        self.rest = RestApi("Bitbucket", str(profile.get("url", "")),
                            f"Bearer {profile.get('token', '')}", bitbucket_detail,
                            profile.get("ca_bundle") or None)
        self.pulls = f"/rest/api/1.0/projects/{self.project}/repos/{self.slug}/pull-requests"

    def values(self, path: str, query: str):
        """Every entry of a paged answer, following nextPageStart until isLastPage."""
        start = None
        while True:
            params = [q for q in (query, f"start={start}" if start is not None else "") if q]
            page = self.rest.call("GET", path + ("?" + "&".join(params) if params else ""))
            if not isinstance(page, dict):
                raise HostError(f"Bitbucket API answer on GET {path} is not an object")
            yield from page.get("values") or []
            if page.get("isLastPage", True) or page.get("nextPageStart") is None:
                return
            start = page["nextPageStart"]

    def ref(self, branch: str) -> dict:
        return {"id": f"refs/heads/{branch}",
                "repository": {"slug": self.slug, "project": {"key": self.project}}}

    @staticmethod
    def url(pull) -> str:
        ident = pull.get("id", "?") if isinstance(pull, dict) else "?"
        return field(pull, "links", "self", 0, "href",
                     where=f"Bitbucket API answer for pull request {ident}")

    def pr(self, worktree: str, base: str, head: str, title: str, body: str) -> tuple[str, str]:
        text = read_body(body)
        ref = f"refs/heads/{head}"
        found = next((p for p in self.values(
            self.pulls, f"state=OPEN&direction=OUTGOING&at={quote(ref, safe='/')}")
            if isinstance(p, dict) and (p.get("fromRef") or {}).get("id") == ref), None)
        if found:
            where = f"Bitbucket API answer for pull request {found.get('id', '?')}"
            ident = field(found, "id", where=where)
            updated = self.rest.call("PUT", f"{self.pulls}/{ident}", {
                "version": field(found, "version", where=where),
                "title": title, "description": text})
            return "updated", self.url(updated)
        created = self.rest.call("POST", self.pulls, {
            "title": title, "description": text,
            "fromRef": self.ref(head), "toRef": self.ref(base)})
        return "created", self.url(created)

    def checks(self, worktree: str, head: str, interval: float,
               timeout: float) -> tuple[bool, list[dict]]:
        sha = head_sha(worktree, head)

        def poll():
            entries = [s for s in self.values(f"/rest/build-status/1.0/commits/{sha}", "")
                       if isinstance(s, dict)]
            # No status yet means Jenkins has not reported: keep waiting, never green.
            if not entries or any(s.get("state") == "INPROGRESS" for s in entries):
                return None
            return all(s.get("state") == "SUCCESSFUL" for s in entries), [
                {"name": s.get("name") or s.get("key"), "state": s.get("state")}
                for s in entries]

        return wait_for(poll, head, interval, timeout)


# ---------- backend choice ----------


def bitbucket_profile(host: str) -> dict | None:
    """The first profile in ~/.bitbucket/profiles.json whose url has hostname `host`."""
    file = Path.home() / ".bitbucket" / "profiles.json"
    if not file.is_file():
        return None
    try:
        profiles = json.loads(file.read_text(encoding="utf-8")).get("profiles", {})
        return next((p for p in profiles.values()
                     if isinstance(p, dict) and hostname(p.get("url", "")) == host), None)
    except (OSError, ValueError, AttributeError):
        return None


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
    profile = bitbucket_profile(host)
    if profile:
        return Bitbucket(profile, path)
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
