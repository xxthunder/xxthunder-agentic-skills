# Contributing

Thanks for your interest. This document tells you what this marketplace accepts,
and what it does not. Read it before you open a pull request.

## Scope

This repository is a marketplace of agentic skill plugins. A skill must add a
capability to the coding agent. Claude Code is the current target. Additional
agent targets are planned — see the [backlog](docs/backlog/README.md).

A skill is code and instructions that the agent runs. A skill is not product
documentation, not a setup guide, and not a link collection.

## Acceptance bar for a new skill or plugin

A pull request must meet all of these points:

1. **It adds a capability.** The skill must let the agent do something it cannot
   do without the skill. If the whole content is "install this product, then set
   this environment variable", it is documentation. Publish it as documentation
   in your own repository.
2. **It targets a supported agent.** The skill must run in Claude Code, or in
   another target listed in the backlog. A skill that configures a different
   agent runtime is out of scope.
3. **It is portable.** Do not hardcode absolute paths, user home paths, host
   names, or repository-specific assumptions. Shell snippets must work on
   Windows and on Linux, because CI runs both. See the "Skills are portable"
   rule in [CLAUDE.md](CLAUDE.md).

   Referring to another *plugin's* skill is not a portability violation.
   `xxthunder-dev-skills` declares a dependency on `superpowers`, so its skills
   may name `superpowers:brainstorming` and friends directly. What the rule
   forbids is assuming something about the repository the skill is installed
   into — a path, a layout, a project name.
4. **Helper code has tests.** Python helper scripts use PEP 723 inline metadata
   and run with `uv run <script>`. Add pytest tests under `tests/`. Run
   `uv run --group dev pytest` before you push.
5. **It carries a backlog item.** Add or reference an item under
   `docs/backlog/` with the `XAS` prefix, with acceptance criteria. See the
   [backlog conventions](docs/backlog/README.md).
6. **Versions match.** When you change any file under
   `plugins/<plugin-name>/` — skills, hooks, or the manifest — bump the version
   in both
   `plugins/<plugin-name>/.claude-plugin/plugin.json` and the matching entry in
   `.claude-plugin/marketplace.json`. Use semantic versioning.
7. **Commits follow the convention.** This repository uses conventional
   commits. Use the skill name as the scope, for example
   `feat(split-batch): ...`. Use `chore` for version bumps and `docs(backlog)`
   for backlog changes.
8. **You own the content.** Do not submit a plugin branded for a third party
   unless you maintain it and you say so plainly.

## Behavioural evals

`pytest` tests the helper code. It cannot tell whether a skill still does what
its `SKILL.md` says. The evals under `evals/` check that: each case builds a
throwaway sandbox, with a store and a consumer repo that both have local bare
remotes. It runs one prompt headless with `claude -p` against the plugin as it
is at a git ref, and checks the files, commits and statuses the run leaves behind.

A change to a skill's behaviour needs a case. Write the case first, and check
that it fails against `develop` before it passes on your branch: a case that
passes on both tests nothing. This is the RED and GREEN of
`superpowers:writing-skills`, which every skill change follows. What this
repository takes from `superpowers` and `skill-creator`, and why it keeps its
own harness, is recorded in
[ADR-0013](docs/adr/0013-skill-work-builds-on-superpowers-and-skill-creator.md). Every skill already has cases for what it does
today. Those pass on `develop` by design, and they catch a regression.

The plugin is exported from the ref with `git archive`, which sees commits
only. To evaluate uncommitted work, pass `--ref "$(git stash create)"`: it makes
a commit of the working tree without moving a branch.

```bash
uv run --group dev python -m evals list
uv run --group dev python -m evals run --ref develop --runs 1
uv run --group dev python -m evals run --ref <your-branch> --runs 3
uv run --group dev python -m evals report --ref <your-branch>
```

Every run is a real agent session on your own Claude Code login, so it costs
tokens and takes minutes. Use `--case <name>` and `-j <n>` to run fewer cases or
more in parallel. The runner loads no user settings and no MCP servers, and it
clears every store variable pair (`*_PATH`/`*_REMOTE`) from the environment.
Plugins that the plugin depends on are taken from your plugin cache, so install
them first. Results, with each run's transcript, go to
`<tmp>/xxthunder-evals/<ref>/`, outside the checkout. Record the pass rates in
the pull request.

## What this repository does not accept

These pull requests are closed without a detailed review:

- **Vendor promotion.** A skill whose purpose is to advertise a product, a
  hosted API, or a paid service.
- **Templated or mass-submitted pull requests.** The same contribution sent to
  many unrelated marketplaces at the same time.
- **SEO and backlink placement.** Content added to gain inbound links.
- **Documentation wrappers.** A `SKILL.md` that restates another project's
  README and links back to it.
- **Manifest changes without a stated defect.** Do not restructure
  `marketplace.json` or `plugin.json` unless the current form breaks something.
  Cite the [official schema](https://code.claude.com/docs/en/plugin-marketplaces)
  and the failure you saw.

## Before you open a pull request

Open an issue first and describe the skill. This saves your time if the idea is
out of scope.

Then check:

- [ ] The skill adds a capability, not documentation.
- [ ] No hardcoded paths. Shell works on Windows and Linux.
- [ ] `uv run --group dev pytest` passes.
- [ ] A behaviour change in a skill has an eval case; its pass rates are in the pull request.
- [ ] Versions bumped in `plugin.json` and `marketplace.json`.
- [ ] Backlog item added or referenced.
- [ ] README skill table and trigger list updated.
- [ ] Commit messages use conventional commit format.

## Validation claims

State only what you ran. Paste the real output. Do not list checks you did not
perform.

## License

Contributions are licensed under [MIT](LICENSE).
