## Closed loop

The contract for the skill that drives an item through the closed loop — and for every
repository that takes part in it. The loop is the same in every repository: pull a card,
work in a worktree through `superpowers:subagent-driven-development`, end on the
repository's gate, hand the author an evidence package. What differs per repository comes from the
repository — named by it, or derived from its CI. The architecture is in
[architecture/workspace.dsl](architecture/workspace.dsl). The skill reads this section
and nothing else about this repository; keep it complete.

- **The loop**: the item becomes a plan of tasks (`superpowers:writing-plans`);
  `superpowers:subagent-driven-development` runs it — an implementer subagent per task,
  test first, a reviewer subagent after each task, fix rounds, a final reviewer for the
  whole branch. Nothing of that is rebuilt; this contract adds the gate, the rubric and
  the evidence package.
- **Gate**: the command that runs every deterministic check of the target repository —
  tests, lint, evals, Molecule, whatever it has — and exits 0 only when all are green. The
  repository decides what green means, not the loop: its own gate, or its CI. The first of
  these is the gate:
  1. the one the repository names — in its `Closed loop` section, or an executable
     `scripts/gate` in its root;
  2. a correction in the registry `engineering/repos.md`, in a table headed
     `Gate corrections` — `| Repo | Gate | Runs in |`, started with the first correction;
  3. the one derived from the repository's CI: `pypeline.yaml` gives `pypeline run`;
     otherwise the check steps that `.github/workflows/`, `.gitea/workflows/` or the
     `Jenkinsfile` run on a pull request, as local commands, without the CI's own setup.

  The derivation runs fresh at every start of the loop; the CI stays the source, and
  nothing derived from it is stored. A wrong one the author corrects in the registry. The
  gate runs where the repository's commands run: in its dev container if it has one.
- **CI as the gate**: where a check of the CI cannot run locally — secrets, a build matrix,
  hardware, a runner of its own — the CI itself is the gate. The checks that do run locally
  give the fix rounds their feedback; the loop pushes the branch and waits for the CI.
- **Rubric**: the general [rubric.md](rubric.md) here, which holds for every repository,
  and the repository's own, for what only its changes need: the one its `Closed loop`
  section names, else `docs/rubric.md`, else its `CONTRIBUTING.md`. Both are handed to the
  reviewers as binding constraints of the plan. Each criterion is answered with evidence
  from the diff. Only what needs judgment: whatever a script, a test or the gate can decide
  belongs there instead. A criterion that holds for every repository goes into the general
  rubric, not into a repository's.
- **Where a repository says so**: its `AGENTS.md` — or `CLAUDE.md` where it has no
  `AGENTS.md` — may name its gate, its rubric and where the gate runs in a section headed
  `Closed loop`. A repository that has none is not asked for one: the loop takes part in
  other people's repositories as they are.
- **No CI and no gate, no loop**: a repository that names no gate and has no CI does not
  take part. The skill says so and stops; a loop that ends on a reviewer's approval alone
  ends on a model's judgment.
- **The end**: the loop ends when the gate exits 0 after the final review — or, where the
  CI is the gate, when the pull request's CI checks are green — never on a reviewer's
  approval alone. A red gate sends the work back into a fix round.
- **Evidence package**: the body of the pull request, for now — the pull request stays so
  the loop can be evaluated as a whole. Its sections, in this order:
  - **Item** — the item's ID, title and link.
  - **What changes** — one line per commit, with the reason.
  - **Gate** — the command, how it was found (named by the repository, a registry
    correction, or derived from which CI file), where it ran, its result, and the tail of
    its output on failure; where the CI is the gate, its checks and their result.
  - **Review** — the findings of each round and how each was resolved; the number of rounds.
  - **Measurements** — optional: eval runs, trigger runs, costs.
  - **Your steps** — what only the author can do, as exact commands: a run against real
    hosts, a merge.
  - **Open** — what is not done, each with its follow-up item.
- **Language**: the evidence package is English (`asf/CONVENTIONS.md` → Language).

