"""Git paths of a worktree that was made in a dev container.

`git worktree add` run inside a dev container writes container paths into the worktree's
`.git` file (`gitdir: /workspaces/<repo>/.git/worktrees/<name>`), which do not exist on the
host. `worktree_env` finds the matching git directory in the checkout that holds the
worktree and returns the environment (GIT_DIR, GIT_WORK_TREE) that makes git work there,
without touching the `.git` file. Stdlib only, no shell, so it runs on Windows.
"""
from __future__ import annotations

import re
from pathlib import Path


def worktree_env(path: str) -> dict[str, str]:
    """The environment that maps a worktree made in a container; {} when none is needed.

    Walks up from `path` to the first directory with a `.git` entry (the worktree root).
    A `.git` directory, a gitdir that exists here, or no `.git` at all gives {} (git
    reports the last by itself). Otherwise the gitdir's last component is the worktree's
    name, and the first directory above the worktree with `.git/worktrees/<name>` is the
    checkout. Raises ValueError when there is none.
    """
    start = Path(path).resolve()
    root = next((d for d in (start, *start.parents) if (d / ".git").exists()), None)
    if root is None or (root / ".git").is_dir():
        return {}
    first = (root / ".git").read_text(encoding="utf-8", errors="replace").splitlines()
    gitdir = next((ln.split(":", 1)[1].strip() for ln in first if ln.startswith("gitdir:")), "")
    if not gitdir or (root / gitdir).is_dir():
        return {}
    name = re.split(r"[/\\]", gitdir.rstrip("/\\"))[-1]
    for d in root.parents:
        candidate = d / ".git" / "worktrees" / name
        if candidate.is_dir():
            return {"GIT_DIR": str(candidate), "GIT_WORK_TREE": str(root)}
    raise ValueError(
        f"the worktree's git dir {gitdir} does not exist here, and no .git/worktrees/{name} "
        f"was found above {root}"
    )
