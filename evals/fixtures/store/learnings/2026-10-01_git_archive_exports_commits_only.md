# git archive exports commits only

**Origin**: demo `DEMO-003`, 2026-10-01

## Claim

`git archive` exports a commit, never the working tree: an uncommitted change is not in the archive.

## Why it holds
*(drafted by the agent)*

It reads a tree object. The working tree is not an object.

## Consequence
*(drafted by the agent)*

To archive uncommitted changes, archive `git stash create`, which makes a commit without moving a branch.
