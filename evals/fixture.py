"""The sandbox one run happens in, and the snapshot of what the run left behind.

Layout under the sandbox directory:

    remotes/store.git, remotes/demo.git   bare repos, default branch `develop`
    store/                                the store's checkout: AGENTS.md, engineering/, learnings/
    checkouts/demo/                       the consumer repo, where the session runs

The seed — everything before the session — is tagged `eval-seed` in the demo
checkout, after a case's own setup; the snapshot counts local commits from there.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from evals.board import BOARD_FILE, WEB, board_md, card, parse_board

FIXTURES = Path(__file__).resolve().parent / "fixtures"
BACKLOG_SCRIPT = Path(__file__).resolve().parents[1] / "plugins" / "xxthunder-dev-skills" / "scripts" / "backlog.py"
BRANCH = "develop"
SEED_TAG = "eval-seed"
IDENTITY = ("-c", "user.name=Eval", "-c", "user.email=eval@example.com")

# file id: (title, status, priority, every criterion ticked)
ITEMS = {
    "demo-001": ("Add retry to the sync job", "Open", "High", False),
    "demo-002": ("Rename the config keys", "Open", "Low", False),
    "demo-003": ("Export to CSV", "In Progress", "Medium", True),
    "demo-004": ("Reporting", "Open", "Medium", False),
    "demo-004a": ("Monthly report", "Open", "Medium", False),
    "demo-005": ("Drop the legacy importer", "Done (2026-10-01)", "Low", True),
    "demo-006": ("Cache the API token", "In Progress", "High", False),
    "demo-007": ("Health endpoint", "Open", "Medium", False),
}

INITIAL_NEXT = [card("DEMO-001", "Add retry to the sync job", "before the release"),
                card("DEMO-002", "Rename the config keys")]
INITIAL_PROGRESS = [card("DEMO-006", "Cache the token"),           # title drifted from the item
                    card("DEMO-003", "Export to CSV"),
                    card("DEMO-005", "Drop the legacy importer")]  # item is Done

CHECKOUT_RULE_RE = re.compile(
    r"The local checkout is\s+`~/dev/<org>/<repo>`.*?after the author agrees\.", re.S)


def git(cwd: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        raise RuntimeError(f"git {' '.join(args)} in {cwd}: {r.stderr.strip()}")
    return r.stdout


def display_id(file_id: str) -> str:
    """demo-004a -> DEMO-004a"""
    prefix, rest = file_id.split("-", 1)
    return f"{prefix.upper()}-{rest}"


def item_text(file_id: str, title: str, status: str, priority: str, ticked: bool) -> str:
    mark = "✅ DONE - " if status.startswith("Done") else ""
    return (f"# [{display_id(file_id)}] {mark}{title}\n\n"
            f"**Status**: {status}\n**Priority**: {priority}\n\n"
            f"**Summary**:\nAs a user I want {title.lower()}.\n\n"
            f"**Acceptance Criteria**:\n- [{'x' if ticked else ' '}] {title} works\n")


def sandbox_contract(text: str, sandbox: Path) -> str:
    """The one deviation from the real contract: checkouts live in the sandbox."""
    rule = (f"The local checkout is `{sandbox / 'checkouts'}/<repo>`. "
            "A repo not cloned there is cloned there, after the author agrees.")
    out, n = CHECKOUT_RULE_RE.subn(lambda _: rule, text)
    if n != 1:
        raise ValueError("the Board contract has no local-checkout rule to point into the sandbox")
    return out


def commit_push(repo: Path, message: str, *paths: str) -> None:
    git(repo, "add", *(paths or ("-A",)))
    git(repo, *IDENTITY, "commit", "-q", "-m", message)
    git(repo, "push", "-q", "-u", "origin", BRANCH)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def build(sandbox: Path, board_contract: bool = True) -> None:
    remotes = sandbox / "remotes"
    remotes.mkdir(parents=True)
    for name in ("store", "demo"):
        git(remotes, "init", "-q", "--bare", "-b", BRANCH, f"{name}.git")

    store = sandbox / "store"
    git(sandbox, "clone", "-q", str(remotes / "store.git"), "store")
    sections = [(FIXTURES / name).read_text(encoding="utf-8")
                for name in ("logbook-contract.md", "learnings-contract.md")]
    if board_contract:
        sections.append(sandbox_contract((FIXTURES / "board-contract.md").read_text(encoding="utf-8"), sandbox))
    shutil.copytree(FIXTURES / "store", store, dirs_exist_ok=True)
    write(store / "AGENTS.md", "# AGENTS.md\n\n" + "\n".join(sections))
    write(store / "engineering" / "repos.md",
          "# Repositories\n\n| Repo | Remote | IDs | What it is |\n|---|---|---|---|\n"
          f"| [demo]({WEB}) | `{remotes / 'demo.git'}` | `DEMO-` | Demo service |\n")
    write(store / BOARD_FILE, board_md(INITIAL_NEXT, INITIAL_PROGRESS))
    write(store / "engineering" / "log.md",
          "# Log\n\n## 2026-10-20\n- **started** · demo DEMO-003 · Export to CSV\n")
    commit_push(store, "init store")

    demo = sandbox / "checkouts" / "demo"
    git(sandbox, "clone", "-q", str(remotes / "demo.git"), str(demo))
    backlog = demo / "docs" / "backlog"
    for file_id, fields in ITEMS.items():
        write(backlog / f"{file_id}.md", item_text(file_id, *fields))
    write(backlog / "README.md", "# Backlog\n\n## Table of Contents\n\n## Notes\n\n**ID prefix**: `DEMO`\n")
    subprocess.run([sys.executable, str(BACKLOG_SCRIPT), "--dir", str(backlog), "toc"], check=True)
    write(demo / "AGENTS.md", "# Demo\n\nNo tests. Conventional commits.\n")
    shutil.copytree(FIXTURES / "demo", demo, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__"))
    commit_push(demo, "init demo")
    git(demo, "remote", "set-head", "origin", BRANCH)
    mark_seed(sandbox)


def mark_seed(sandbox: Path) -> None:
    """Tag the demo checkout's HEAD as the seed; a case's setup calls it again."""
    git(sandbox / "checkouts" / "demo", "tag", "-f", SEED_TAG)


def text_files(root: Path) -> dict[str, str]:
    """Every text file under *root* outside `.git`, keyed by its relative POSIX path."""
    out = {}
    for path in root.rglob("*"):
        rel = path.relative_to(root)
        if ".git" in rel.parts or "__pycache__" in rel.parts or not path.is_file():
            continue
        try:
            out[rel.as_posix()] = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
    return out


def committed_files(bare: Path) -> dict[str, str]:
    """Every file on the default branch of a bare repo, keyed by path."""
    return {name: git(bare, "show", f"{BRANCH}:{name}")
            for name in git(bare, "ls-tree", "-r", "--name-only", BRANCH).splitlines()}


@dataclass
class State:
    board_next: list[str]
    board_progress: list[str]
    store_commits: list[tuple[str, list[str]]]  # (subject, files), newest first, after the seed
    demo_status: dict[str, str]
    demo_porcelain: str
    demo_remote_subjects: list[str]             # newest first, after the seed
    output: str
    skills: list[str] = field(default_factory=list)
    demo_local_subjects: list[str] = field(default_factory=list)  # newest first, after the seed tag
    demo_head_message: str = ""                                  # full message, when there are local commits
    demo_files: dict[str, str] = field(default_factory=dict)     # working tree of the demo checkout
    store_files: dict[str, str] = field(default_factory=dict)    # the store's default branch on its remote


def snapshot(sandbox: Path, output: str, skills: list[str]) -> State:
    store_bare = sandbox / "remotes" / "store.git"
    commits = []
    for chunk in git(store_bare, "log", "--format=%x00%s", "--name-only", BRANCH).split("\x00")[1:]:
        lines = [line for line in chunk.splitlines() if line]
        commits.append((lines[0], lines[1:]))
    nxt, prog = parse_board(git(store_bare, "show", f"{BRANCH}:{BOARD_FILE}"))
    demo = sandbox / "checkouts" / "demo"
    status = {}
    for path in (demo / "docs" / "backlog").glob("demo-*.md"):
        m = re.search(r"^\*\*Status\*\*: (.+)$", path.read_text(encoding="utf-8"), re.M)
        status[display_id(path.stem)] = m.group(1) if m else ""
    demo_log = git(sandbox / "remotes" / "demo.git", "log", "--format=%s", BRANCH).splitlines()
    local = git(demo, "log", "--format=%s", f"{SEED_TAG}..HEAD").splitlines()
    return State(nxt, prog, commits[:-1], status, git(demo, "status", "--porcelain"),
                 demo_log[:-1], output, skills,
                 demo_local_subjects=local,
                 demo_head_message=git(demo, "log", "-1", "--format=%B") if local else "",
                 demo_files=text_files(demo),
                 store_files=committed_files(store_bare))
