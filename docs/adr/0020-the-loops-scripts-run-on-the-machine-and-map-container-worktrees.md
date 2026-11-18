# ADR-0020: The loop's scripts run on the machine and map container worktrees

**Status**: Accepted
**Date**: 2026-11-18
**Related**: [XAS-080](../backlog/xas-080.md), [ADR-0016](0016-the-closed-loop-is-a-thin-conductor-over-sdd.md)

## Context

The team develops in dev containers under WSL, and also on native Windows. `git worktree
add` run in a container writes container paths (`/workspaces/<workspace>/...`) into the
worktree's `.git` file and into the checkout's link back to it
(`.git/worktrees/<name>/gitdir`). On the machine, such a worktree is not a git repository,
and git lists its link as prunable. The closed loop calls `loop.py` from the plugin cache on
the machine, so every subcommand that runs git failed there.

## Decision

The loop's scripts run where the agent runs. They map a worktree made in a container.

- `loop.py`, the push and `host.py` run on the machine. The repository's commands and its
  gate run in the container.
- When the worktree's `.git` file names a git dir that does not exist here, the scripts find
  the `.git/worktrees/<name>` of the checkout above the worktree. They run git with `GIT_DIR`
  and `GIT_WORK_TREE` set to it and to the worktree. Neither the `.git` file nor the link
  back is changed.
- `loop.py git` runs any other git call of the loop this way. `loop.py find` derives the
  worktree of an item on the machine from the loop states under `.git/worktrees/`.

The mapping itself is specified in `gitpaths.py` and `loop.py --help`, not here.

## Alternatives considered

- **Run `loop.py` in the container.** Rejected (2026-11-18): it works, because `loop.py`
  needs only the standard library, but the copy is lost when the container is rebuilt. It
  also fails for the team members on native Windows, who have no container, and the push
  and `host.py` need the machine's credentials anyway.
- **`git worktree add --relative-paths`.** Rejected (2026-11-18): it needs git 2.48 and sets
  `extensions.relativeWorktrees`. An older git then refuses the whole repository, main
  checkout included (tried with git 2.47.3). The company's git on Windows is 2.45.
- **`git worktree repair`.** Rejected (2026-11-18): it rewrites the paths to the machine's
  paths, and the container then cannot read the worktree.

## Consequences

- The loop needs no copy of its scripts in the container and no second Python there.
- Every git call of the loop on a worktree goes through `loop.py git`. A plain `git` on a
  container worktree fails on the machine, and a skill that forgets this breaks only for the
  teams that use containers.
- The mapping assumes the checkout holds the worktree below it, as the global rules place
  it. A worktree made in a container outside the checkout is not found, and the scripts
  exit 2 with the path they looked for.
- `git worktree list` is wrong for a container worktree on the machine, so Resume cannot rely
  on it. `loop.py find` replaces it.
- If a git version ever makes relative worktree paths safe for the whole team, the mapping
  can go. The scripts that call `loop.py git` stay valid.
