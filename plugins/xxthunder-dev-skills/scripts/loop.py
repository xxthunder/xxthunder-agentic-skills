# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Mechanical lookups of the closed-loop skill, so the skill does no parsing by hand.

Subcommands (output is JSON on stdout, errors go to stderr):

  checkout <remote>
      The org and repo of a remote: {"org", "repo"}; the local path is the contract's rule.
      Takes https://host/org/repo(.git), git@host:org/repo.git and
      ssh://git@host:7999/~org/repo.git (a leading ~ stays in org).
  row <markdown-file> <header-cells> <column> <value>
      The first row of the first table whose header starts with the comma-separated
      <header-cells> and whose <column> cell, as link text without backticks, equals
      <value>, with or without one trailing "-" on either side (cell XAS matches XAS- and
      XAS): {header: cell}. Exit 1, "not found", when no table or row matches.
  first <dir> <glob>...
      The first glob, in the given order, that matches anything under <dir>:
      {"match": <sorted first, relative>, "pattern": <glob>}, or both null.
  state <worktree> [key=value ...]
      Merges the pairs into <git-dir>/closed-loop.json and prints the whole state.
      Integers stay integers.
  guard <repo> --tests <A..B>... --impl <A..B> [--protect <path>]...
      Proves the implementer left the tester's files alone. The files each --tests range
      (repeatable) added or changed (net diff, unioned) plus the --protect paths must not
      appear in the --impl range's net diff. Exit 0 and {"ok": true}; else exit 1 and
      {"ok": false, "touched": [sorted unique paths]}.

  commit-impl <worktree> <B> <message-file>
      Commits what is staged as "amend! <B full SHA>" with the message file as body, so a
      fold gives tester commit B the message file as its message. {"commit": <sha>}.
      Exit 1 when nothing is staged.
  fixup <worktree> <B>
      Commits what is staged as "fixup! <B full SHA>". {"commit": <sha>}. Exit 1 when
      nothing is staged.
  fold <worktree> <base>
      Folds every amend!/fixup! commit of <base>..HEAD into its target with a
      non-interactive autosquash rebase: {"head": <sha>, "commits": <n>}. On a conflict the
      rebase is aborted, HEAD stays as it was, exit 1.

Stdlib only; no shell, so it runs on Windows.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse

SCP_RE = re.compile(r"^[^@/]+@[^:/]+:(?P<path>.+)$")
UNESCAPED_PIPE_RE = re.compile(r"(?<!\\)\|")
LINK_TEXT_RE = re.compile(r"^\[([^\]]*)\]\([^)]*\)$")
INT_RE = re.compile(r"^-?\d+$")
STATE_FILE = "closed-loop.json"


def split_remote(remote: str) -> tuple[str, str]:
    m = SCP_RE.match(remote)
    path = m["path"] if m else urlparse(remote).path
    parts = [p for p in path.strip("/").removesuffix(".git").split("/") if p]
    if len(parts) < 2:
        raise ValueError(f"cannot read org and repo from {remote!r}")
    return parts[-2], parts[-1]


def cmd_checkout(args: argparse.Namespace) -> int:
    org, repo = split_remote(args.remote)
    print(json.dumps({"org": org, "repo": repo}))
    return 0


def split_row(line: str) -> list[str]:
    cells = UNESCAPED_PIPE_RE.split(line.strip())[1:]
    if cells and cells[-1].strip() == "":
        cells.pop()
    return [c.strip() for c in cells]


def cell_key(cell: str) -> str:
    m = LINK_TEXT_RE.match(cell)
    return (m[1] if m else cell).replace("`", "")


def same_key(cell: str, value: str) -> bool:
    return cell.removesuffix("-") == value.removesuffix("-")


def find_row(text: str, header: list[str], column: str, value: str) -> dict[str, str] | None:
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        if not lines[i].lstrip().startswith("|"):
            i += 1
            continue
        j = i
        while j < len(lines) and lines[j].lstrip().startswith("|"):
            j += 1
        block = lines[i:j]
        i = j
        names = split_row(block[0])
        if names[: len(header)] != header or column not in names:
            continue
        idx = names.index(column)
        for line in block[2:]:
            cells = split_row(line)
            if idx < len(cells) and same_key(cell_key(cells[idx]), value):
                return {n: c.replace("\\|", "|") for n, c in zip(names, cells)}
    return None


def cmd_row(args: argparse.Namespace) -> int:
    text = Path(args.file).read_text(encoding="utf-8")
    header = [h.strip() for h in args.header.split(",")]
    found = find_row(text, header, args.column, args.value)
    if found is None:
        print(f"not found: {args.column}={args.value} in a table headed {args.header}", file=sys.stderr)
        return 1
    print(json.dumps(found))
    return 0


def cmd_first(args: argparse.Namespace) -> int:
    base = Path(args.dir)
    for pattern in args.globs:
        matches = sorted(p.relative_to(base).as_posix() for p in base.glob(pattern))
        if matches:
            print(json.dumps({"match": matches[0], "pattern": pattern}))
            return 0
    print(json.dumps({"match": None, "pattern": None}))
    return 0


def cmd_state(args: argparse.Namespace) -> int:
    out = subprocess.run(
        ["git", "-C", args.worktree, "rev-parse", "--absolute-git-dir"],
        capture_output=True, text=True,
    )
    if out.returncode != 0:
        print(out.stderr.strip() or "not a git worktree", file=sys.stderr)
        return 1
    file = Path(out.stdout.strip()) / STATE_FILE
    state = json.loads(file.read_text(encoding="utf-8")) if file.exists() else {}
    for pair in args.pairs:
        key, sep, value = pair.partition("=")
        if not sep or not key:
            print(f"expected key=value, got {pair!r}", file=sys.stderr)
            return 2
        state[key] = int(value) if INT_RE.match(value) else value
    if args.pairs:
        file.write_text(json.dumps(state), encoding="utf-8")
    print(json.dumps(state))
    return 0


def changed_files(repo: str, rev_range: str) -> set[str] | None:
    out = subprocess.run(
        ["git", "-C", repo, "diff", "--name-only", "--no-renames", "-z", rev_range, "--"],
        capture_output=True, text=True, encoding="utf-8",
    )
    if out.returncode != 0:
        print(out.stderr.strip() or f"git diff failed for {rev_range}", file=sys.stderr)
        return None
    return {p for p in out.stdout.split("\0") if p}


def cmd_guard(args: argparse.Namespace) -> int:
    ranges = [changed_files(args.repo, r) for r in [*args.tests, args.impl]]
    if any(r is None for r in ranges):
        return 2
    *test_sets, impl = ranges
    tests = set().union(*test_sets)
    touched = sorted(impl & (tests | set(args.protect)))
    if touched:
        print(json.dumps({"ok": False, "touched": touched}))
        return 1
    print(json.dumps({"ok": True}))
    return 0


def git(worktree: str, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", worktree, *args],
        capture_output=True, text=True, encoding="utf-8",
        env={**os.environ, **env} if env else None,
    )


def fail(out: subprocess.CompletedProcess, default: str) -> int:
    print(out.stderr.strip() or out.stdout.strip() or default, file=sys.stderr)
    return 1


def commit_staged(worktree: str, target: str, subject_prefix: str, body: str | None) -> int:
    full = git(worktree, "rev-parse", "--verify", f"{target}^{{commit}}")
    if full.returncode != 0:
        return fail(full, f"unknown commit {target!r}")
    if git(worktree, "diff", "--cached", "--quiet").returncode == 0:
        print("nothing staged", file=sys.stderr)
        return 1
    message = f"{subject_prefix} {full.stdout.strip()}\n"
    if body is not None:
        message += f"\n{body.rstrip()}\n"
    with tempfile.TemporaryDirectory() as tmp:
        msg_file = Path(tmp) / "message.txt"
        msg_file.write_text(message, encoding="utf-8", newline="\n")
        out = git(worktree, "commit", "-F", str(msg_file))
    if out.returncode != 0:
        return fail(out, "git commit failed")
    print(json.dumps({"commit": git(worktree, "rev-parse", "HEAD").stdout.strip()}))
    return 0


def cmd_commit_impl(args: argparse.Namespace) -> int:
    body = Path(args.message_file).read_text(encoding="utf-8")
    return commit_staged(args.worktree, args.target, "amend!", body)


def cmd_fixup(args: argparse.Namespace) -> int:
    return commit_staged(args.worktree, args.target, "fixup!", None)


def cmd_fold(args: argparse.Namespace) -> int:
    head = git(args.worktree, "rev-parse", "HEAD")
    if head.returncode != 0:
        return fail(head, "not a git worktree")
    out = git(
        args.worktree, "-c", "core.editor=true", "rebase", "-i", "--autosquash", args.base,
        env={"GIT_SEQUENCE_EDITOR": "true"},
    )
    if out.returncode != 0:
        message = out.stderr.strip() or out.stdout.strip() or "rebase failed"
        abort = git(args.worktree, "rebase", "--abort")
        if abort.returncode != 0:
            message += f"\nrebase --abort failed: {abort.stderr.strip()}"
        print(message, file=sys.stderr)
        return 1
    count = git(args.worktree, "rev-list", "--count", f"{args.base}..HEAD")
    head = git(args.worktree, "rev-parse", "HEAD")
    print(json.dumps({"head": head.stdout.strip(), "commits": int(count.stdout.strip())}))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Closed-loop helper lookups.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("checkout", help="org and repo of a remote")
    p.add_argument("remote")
    p.set_defaults(func=cmd_checkout)

    p = sub.add_parser("row", help="find a row of a Markdown table")
    p.add_argument("file")
    p.add_argument("header", help="comma-separated first header cells")
    p.add_argument("column")
    p.add_argument("value")
    p.set_defaults(func=cmd_row)

    p = sub.add_parser("first", help="first glob that matches")
    p.add_argument("dir")
    p.add_argument("globs", nargs="+")
    p.set_defaults(func=cmd_first)

    p = sub.add_parser("state", help="read and merge the loop state")
    p.add_argument("worktree")
    p.add_argument("pairs", nargs="*")
    p.set_defaults(func=cmd_state)

    p = sub.add_parser("guard", help="the implementer left the tester's files alone")
    p.add_argument("repo")
    p.add_argument("--tests", required=True, action="append", help="rev range of the tester's commits; repeatable")
    p.add_argument("--impl", required=True, help="rev range of the implementer's commits")
    p.add_argument("--protect", action="append", default=[], help="extra path to protect")
    p.set_defaults(func=cmd_guard)

    p = sub.add_parser("commit-impl", help="commit the staged change as an amend! of a tester commit")
    p.add_argument("worktree")
    p.add_argument("target", metavar="B")
    p.add_argument("message_file")
    p.set_defaults(func=cmd_commit_impl)

    p = sub.add_parser("fixup", help="commit the staged change as a fixup! of a commit")
    p.add_argument("worktree")
    p.add_argument("target", metavar="B")
    p.set_defaults(func=cmd_fixup)

    p = sub.add_parser("fold", help="autosquash the amend!/fixup! commits of <base>..HEAD")
    p.add_argument("worktree")
    p.add_argument("base")
    p.set_defaults(func=cmd_fold)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
