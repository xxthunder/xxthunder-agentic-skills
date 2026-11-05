---
name: closed-loop
description: "Drive one backlog item through the closed loop — from the board to a pull request whose body is the evidence package, ended on the target repository's gate, never on a reviewer's approval. Use on 'put ABC-012 in the loop', 'start the loop for ABC-012', 'continue the loop for ABC-012'; German 'nimm ABC-012 in die Loop', 'bring ABC-012 in den Loop', 'starte die Loop für ABC-012', 'mach weiter mit der Loop für ABC-012'; and, for the item in focus, 'Make it so!', 'Engage!', 'Start the loop!', 'Energie!', 'Starte die Loop!'. Works from any repository: the item is found in the current backlog or the board's registry. Not for repeating a prompt on an interval."
allowed-tools: Bash(uv run ${CLAUDE_PLUGIN_ROOT}/scripts/loop.py *), Bash(uv run ${CLAUDE_PLUGIN_ROOT}/scripts/backlog.py *), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/store *)
---

<!-- Source: https://github.com/xxthunder/xxthunder-agentic-skills/tree/develop/plugins/xxthunder-dev-skills/skills/closed-loop -->

# Closed loop

One item runs from the board through `superpowers:writing-plans` and
`superpowers:subagent-driven-development` (SDD) to the target repository's gate and a pull
request whose body is the evidence package. SDD stays as it is; this skill adds what SDD does
not do: find the gate, end on it, keep the tests away from the implementer, write the package.

The author starts the loop and walks away. Ask at the start; after that, run on your own and
stop only where the author alone can decide ([Stops](#stops)).

**What the loop is, where the gate and rubric come from, and what the package holds, is the
contract's — never this skill's.** Read it fresh at every start and resume; follow its order
and its file names exactly as it states them.

Every mechanical step is a script call. The scripts:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/store" <resolve|contract> ...
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/loop.py" <checkout|row|first|state|guard|commit-impl|fixup|fold> ...
```

Below, `store` and `loop.py` stand for these two calls. `loop.py --help` describes each
subcommand's arguments and output.
A non-zero exit you do not expect ends the step: show the message and stop.

## What starts what

| The author says | Do |
|---|---|
| "put ABC-012 in the loop", "start the loop for ABC-012", "nimm ABC-012 in die Loop", "starte die Loop für ABC-012" | [Start](#start), up to the Q&A offer |
| the same, followed by "Make it so!" / "Engage!" / "Energie!" in one message | [Start](#start) without the Q&A offer |
| "Make it so!", "Engage!", "Start the loop!", "Energie!", "Starte die Loop!" | act on the item in focus — the one named earlier in this conversation. With none in focus, ask which item, and do nothing else: no lookup of the board, the state or the backlog to guess one |
| "continue the loop for ABC-012", "mach weiter mit der Loop für ABC-012" | [Resume](#resume) |

Speak of "die Loop" in German.

## Find the item, its repository, the contract

1. **The store and the contracts.** `store resolve BOARD` gives the store; exit 2 means no
   board is configured: say the loop needs one, and stop. Read both sections:
   `store contract <store> "Closed loop"` and `store contract <store> Board`. The Board
   contract names the registry. A link in a contract is relative to the file that holds the
   section — the store's `AGENTS.md` or a file it imports.
2. **The repository.** The ID's prefix decides:
   - the current repository's own prefix → the current repository. The own prefix is the
     prefix of the ID `uv run "${CLAUDE_PLUGIN_ROOT}/scripts/backlog.py" next-id` prints (the
     part before its last `-`); a non-zero exit means the repository has no backlog and no
     own prefix;
   - any other prefix → `loop.py row <registry> "Repo,Remote" IDs <PREFIX>`. Not found →
     say the ID is in neither this backlog nor the registry, name the missing registry row,
     and stop. Found → `loop.py checkout <remote>` gives the remote's org and repo; the
     Board contract's checkout rule turns them into the local path. Not cloned there → ask
     before cloning, as the rule says.
3. **Its rules.** Read the target repository's `AGENTS.md` / `CLAUDE.md` and the documents
   they name as binding. Every later step runs in that repository and follows them —
   branch and worktree rules, dev container, commit format.

## Find the gate and the rubric

Run this fresh at every start and every resume; store nothing of it.

1. Take the contract's list of where a gate comes from, **in the contract's order**, and
   check each with the script that answers it — the first that answers is the gate:
   - a section the contract names in the repository: `store contract <repo> "<section>"`
     (exit 1 = the repository has none);
   - a file the contract names: `loop.py first <repo> <path>` and, for a script, `test -x`;
   - a correction table in the registry: `loop.py row <registry> "<header cells>" <column> <repo>`;
   - CI files: `loop.py first <repo> <glob>...` with the contract's CI files as globs, in its
     order. A derived gate turns the CI's check steps into local commands as the contract
     says — that is your judgment; keep the file it came from.
2. Record three facts for the package: the **command**; **how it was found** — the
   contract's own line for the source that answered, quoted, and only that one, plus the
   CI file for a derived gate; and **where it runs**, as the contract says.
3. **No gate and no CI → no loop.** Say the repository names no gate and has no CI, so it
   cannot take part, and stop — before the pull, before any branch or plan.
4. The rubrics: the general one the contract names, and the repository's own in the
   contract's order — `loop.py first <repo> <path>...`. Read both; they go into the plan
   verbatim. A rubric that does not exist is not a stop: go on with the ones that do, and
   name the missing file under *Open* in the package.

## Start

1. [Find the item](#find-the-item-its-repository-the-contract), then
   [the gate and rubric](#find-the-gate-and-the-rubric).
2. **Pull.** Invoke `backlog-ops` with "pull <ID>" in the target checkout. It moves the
   status to In Progress, lands the pull on the default branch, and moves the card on the
   board. An item already In Progress is fine — go on.
3. **The Q&A offer.** Unless the author already said "Make it so!" or the like, end the turn
   with one question: "Q&A round on the plan first?" — German: "Erst eine Q&A-Runde zum
   Plan?". Make no branch, worktree or plan before the answer.
   - **Yes**: talk the item through. Write each answer into the item's `**Scope
     Decisions**:` with the date, and commit and push that before the plan is written — on
     the default branch, as the repository's rules allow for backlog changes. The plan
     argues from the item, not from the chat.
   - **No**, or "Make it so!" / "Engage!" / "Energie!": go on.
4. **Worktree.** Create the feature branch and its worktree as the target repository's rules
   say; without such a rule, follow `superpowers:using-git-worktrees`. From here, record the
   run: `loop.py state <worktree> item=<ID> branch=<branch> step=plan fix_rounds=0 exchanges=0`.
5. Track each step of this run in the session's task list, so the author can follow it.
6. [Plan](#plan), [Build](#build), [Gate](#gate), [Package](#package).

## Plan

Invoke `superpowers:writing-plans` with these rules on top of its own:

- **Global Constraints**: the general rubric and the repository's rubric, both **verbatim**,
  under `## Global Constraints`, next to the repository rules the plan needs.
- **Split tester and implementer**: each task with behaviour to test becomes two tasks.
  `N.a` (tester) writes the failing tests from the task and the item's acceptance criteria,
  without an implementation in sight, and shows that they fail. `N.b` (implementer) makes
  them pass and refactors, and changes no file `N.a` added or changed.
- **Eval-only gates**: where the gate checks eval results instead of running evals, the plan
  runs them — the tester at the base, where the new case must fail, and once after the
  change.

Then `loop.py state <worktree> step=build`, and notify: plan written.

## Build

Invoke `superpowers:subagent-driven-development` on the plan. These rules hold on top of it:

1. **Commits stay apart until the gate is green.** Each unit keeps its tester's and its
   implementer's commits apart, so the guard can tell them apart; git folds them later
   ([Package](#package)).
   - After `N.a`, record the tester's range of unit N:
     `loop.py state <worktree> tests_<N>=<A>..<B>` — `A` the commit before `N.a`, `B` its
     commit.
   - `N.b`'s first commit: stage the change, write the unit's final message to a file
     outside the working tree, and run `loop.py commit-impl <worktree> <B> <file>`. Every
     later commit of the unit — review fixes too — is staged and committed with
     `loop.py fixup <worktree> <B>`. Both name `B` by its full SHA, so two units with the
     same subject cannot mix.
   - The repository's commit hooks run on every one of these commits. A refused commit is a
     failed step: the hook's message goes back to the agent that made the change, as a fix
     round of its task. A hook that refuses the `amend!`/`fixup!` subjects themselves is
     the [stop](#stops) *hook refuses fold commits*.
2. **Test guard after each `N.b`, before its review.** Run
   `loop.py guard <worktree> --tests <range>... --impl <C>..HEAD --protect <gate file> --protect <CI file>...`
   with every tester range of the unit, `C` the unit's last tester commit, and the gate
   script and every CI file the lookup checked as `--protect`. Exit 1 → send the task back
   to the implementer with the listed files; their changes are undone.
3. **A dispute goes to a fresh tester.** An implementer that reports `BLOCKED` with
   `DISPUTE:` gets no controller ruling. Record it:
   `loop.py state <worktree> step=dispute task=<N.b> exchanges=<n> dispute="<the reason>"`.
   A fresh tester subagent gets the dispute; it fixes the test and commits it with `loop.py fixup <worktree> <B>`,
   recorded as one more range of the unit (`tests_<N>_<k>=<before>..<its commit>`), or it
   rejects the dispute with a reason; then the implementer runs again. Count each tester
   answer as one exchange. Agreement → `step=build`. Two exchanges without agreement, or a
   dispute that shows an acceptance criterion is wrong → [stop](#stops).
4. **Scope questions stop the loop.** A question that would change the item's scope or an
   acceptance criterion is the author's: [stop](#stops). SDD rules on every other ambiguity
   as usual; keep its rulings for the package.

As SDD runs, append each review round's findings and how each was resolved, every dispute
and every ruling SDD made to `closed-loop-review.md` in the worktree's git dir
(`git rev-parse --absolute-git-dir`), so a resumed run can still write *Review*.

After SDD's final review: `loop.py state <worktree> step=gate`.

## Gate

Run the gate command where the lookup said, in the worktree. **Its exit code is the
verdict**: exit 0 is green, anything else is red. What the gate checks is the repository's
decision, not the loop's — take the verdict as it comes, also from a gate that looks thin.
A concern about the gate itself goes into the package under *Open*; it is not a stop.

- **Green** → `loop.py state <worktree> step=package`, notify: gate green, go to
  [Package](#package).
- **Red, `fix_rounds` below 2** → one fix round, also when a fix looks hopeless — the two
  rounds are the rule, and only a red gate after both is a stop. A fix subagent (where the
  harness has none, you) gets the gate's output and fixes the cause in the work, never in
  the gate script, a CI file or a tester's test; it commits with
  `loop.py fixup <worktree> <B>` of the unit the fix belongs to — the last unit when it
  belongs to none —, so the fold leaves no separate fix commit. Check that
  with `loop.py guard <worktree> --tests <range>... --impl <before>..HEAD --protect <gate file> --protect <CI file>...`
  — every `tests_*` range in the state — and undo what it lists. Then
  `loop.py state <worktree> fix_rounds=<n+1>` and run the gate again.
- **Red with `fix_rounds` at 2** → [stop](#stops): no push, no pull request.

**CI as the gate**, where the contract says the CI is the gate: push the branch **unfolded**
(`git push -u origin <branch>`) — a fold now would rewrite the commits the `tests_*` ranges
name, and every later guard would check ranges that no longer exist. Open the pull request
with `gh pr create` and an interim body, record `loop.py state <worktree> pr=<url>`, and
wait with `gh pr checks <number> --watch`. A red check is a red gate (same rounds; push
each fix unfolded). All green → fold ([Package](#package) step 1), push with
`--force-with-lease`, and wait for the checks once more: the fold leaves the tree identical,
but it re-runs the CI, and the loop ends only on that run's green. A red check on that run
is the [stop](#stops) *red CI after the fold* — no fix round: the tree is the one that was
green, so the cause lies in the CI, and the ranges and fixup targets no longer exist.

**GitHub only, for now.** Pull requests and their checks go through `gh`. Whether it serves
the remote is `gh`'s answer, not the remote URL's: a non-zero exit of `gh pr create` or
`gh pr checks` is the [stop](#stops) *unsupported remote*, with `gh`'s message.

## Package

1. **Fold** each unit into one commit, now that the gate is green — on the CI path this
   happened already in [Gate](#gate): `loop.py fold <worktree> <base>`, `<base>` the commit
   the branch started from (`git merge-base origin/<default branch> HEAD`). Code and its
   tests land together, under the implementer's message. Exit 1 → the fold is undone; show
   its message and [stop](#stops) as *fold failed*.
2. Push the branch: `git push -u origin <branch>` (`--force-with-lease` when it was pushed
   before the fold).
3. Write the body to a file outside the working tree — the worktree's git dir
   (`git rev-parse --absolute-git-dir`). Its sections, their names and their order are the
   contract's, each as a `## <Name>` heading, English, filled as the contract describes.
   Where a section needs data from this run:
   - *What changes*: one line per commit of `git log <base>..HEAD`, with its reason.
   - *Gate*: the three recorded facts — the command, the contract's line for its source, where
     it ran — and the result: exit code, and the output's tail on failure; for the CI as
     gate, its checks and their results.
   - *Review*: from `closed-loop-review.md` — each round's findings and how each was
     resolved, the number of rounds, every dispute and how it ended, every ruling SDD made
     on the author's behalf, and the gate's fix rounds.
   - *Measurements*: eval runs and costs where this run measured them; else leave the
     section out.
4. Open it: `gh pr create --base <default branch> --head <branch> --title "<ID>: <title>" --body-file <file>`
   — or, when the state already holds a `pr` (CI as the gate),
   `gh pr edit <number> --body-file <file>`.
5. `loop.py state <worktree> step=done pr=<url>`, and notify with the link.

The loop ends here. The author merges, ticks the acceptance criteria and closes the item.

## Stops

A stop is a decision only the author can make. These seven are the only stops; everything
else the loop carries on through, and what worries you goes under *Open* in the package:

| Stop | When |
|---|---|
| red gate | the gate still red after two fix rounds |
| dispute | still open after two exchanges, or an acceptance criterion found wrong |
| scope | a plan or build question the item does not settle |
| unsupported remote | `gh` cannot open the pull request or read its checks |
| hook refuses fold commits | a commit hook of the repository rejects the `amend!`/`fixup!` subjects the loop folds by |
| fold failed | `loop.py fold` exits 1 |
| red CI after the fold | a check red on the folded branch whose unfolded tree was green — the notification names the red checks, says the tree is unchanged since the green run, and asks the author to re-run or fix the CI |

At a stop:

1. Record it: `loop.py state <worktree> stop=<stop>`; keep `step` where it stopped.
2. Notify: name the decision. Use the harness's push-notification tool where there is one;
   otherwise the answer is the notification.
3. End the turn with the decision as one question — the gate's output tail, the dispute's
   text and the test it is about, or the open question. Make no commit, push or pull request
   while it waits.

Milestones get a notification too: plan written, gate green or red, pull request opened.

## Resume

"continue the loop for <ID>":

1. [Find the item](#find-the-item-its-repository-the-contract) and
   [the gate and rubric](#find-the-gate-and-the-rubric) again.
2. Find the state: `loop.py state <path>` for the target checkout and each of its worktrees
   (`git worktree list`). A state whose `item` is another item → say which item it holds and
   ask before anything else. No state → say so and offer [Start](#start).
3. A state with `stop` set, or `step=dispute` with `exchanges` at 2: the stop still stands.
   With the author's answer in this message, act on it and clear the stop
   (`stop=`); without one, present the stop again as in [Stops](#stops).
4. Otherwise continue at its `step`: `plan`, `build`, `gate`, `package` — with the counters
   from the state. The state is the run's record: the steps before it are done, so go on
   from it without checking them again — no second pull, no audit of the branch.

## What the loop never does

Every one of these is the author's step — name it under *Your steps* instead:

- merge the pull request;
- tick an acceptance criterion or close the item;
- end on a reviewer's approval without a green gate;
- open the pull request with an unresolved stop under *Open*;
- change the gate script or a CI file to make the gate green.
