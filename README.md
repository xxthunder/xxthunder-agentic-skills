# xxthunder-agentic-skills

<p align="center">
  <a href="https://github.com/xxthunder/xxthunder-agentic-skills/actions/workflows/test.yml">
    <img src="https://github.com/xxthunder/xxthunder-agentic-skills/actions/workflows/test.yml/badge.svg" alt="CI Status">
  </a>
  <a href="https://github.com/xxthunder/xxthunder-agentic-skills/blob/develop/LICENSE">
    <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT">
  </a>
  <a href="https://github.com/xxthunder/xxthunder-agentic-skills">
    <img src="https://img.shields.io/badge/Python-3.11%2B-blue.svg" alt="Python 3.11+">
  </a>
  <a href="https://codecov.io/gh/xxthunder/xxthunder-agentic-skills">
    <img src="https://codecov.io/gh/xxthunder/xxthunder-agentic-skills/branch/develop/graph/badge.svg" alt="Coverage">
  </a>
</p>

Marketplace of agentic skill plugins by xxthunder. Hosts one or more plugins that extend coding agents with reusable skills. Claude Code is the initial supported target; additional agent targets (e.g. GitHub Copilot) are planned.

## Plugins

Each skill links to its `SKILL.md` for the full description, triggers, and instructions.

### `xxthunder-dev-skills`

Developer workflow skills:

| Skill | Description |
|---|---|
| [**architecture-scan**](plugins/xxthunder-dev-skills/skills/architecture-scan/SKILL.md) | Read-only scan — derives real structure from the repo, proposes a bootstrap when `architecture.md` is absent, reports drift when it is not |
| [**backlog-ops**](plugins/xxthunder-dev-skills/skills/backlog-ops/SKILL.md) | Lifecycle operations on backlog items — pull, tick acceptance/UAT criteria, close with epic-status cascade |
| [**commit-helper**](plugins/xxthunder-dev-skills/skills/commit-helper/SKILL.md) | Conventional commit creation with mandatory pre-commit checks |
| [**design-record**](plugins/xxthunder-dev-skills/skills/design-record/SKILL.md) | Durable design record — drafts ADRs with numbering and a derived index, and edits the slotted `architecture.md` |
| [**learnings**](plugins/xxthunder-dev-skills/skills/learnings/SKILL.md) | Captures what outlives a repository into the author's personal knowledge repo — configured on the machine, never named in any repo — and recalls it at the start of a topic |
| [**logbook**](plugins/xxthunder-dev-skills/skills/logbook/SKILL.md) | Chronicles what each session starts, notes and finishes into the author's logbook repo — one line per event, across all repositories; suggested by `backlog-ops` at pull and close |
| [**refinement**](plugins/xxthunder-dev-skills/skills/refinement/SKILL.md) | Interactive backlog refinement sessions — review project state, prioritize work, add new items, discuss architecture |
| [**retrospective**](plugins/xxthunder-dev-skills/skills/retrospective/SKILL.md) | Incident-driven learning — captures lessons from unmet expectations and encodes them into project guidelines |

Beyond skills, `xxthunder-dev-skills` ships a **`SessionStart` hook**. It runs
at the start of every session and states where that repository keeps its design
record — the backlog, the ADR log, the architecture document — naming only the
artifacts that actually exist, with the paths it found them at.

It also ships one plugin-level script, `scripts/store`, which resolves a
cross-repo store from a variable pair (`<PREFIX>_PATH`, `<PREFIX>_REMOTE`) and
commits-and-pushes into it. `learnings` uses it with the `LEARNINGS` prefix,
`logbook` with `LOGBOOK`; the stores themselves are configured in the user's
settings, never in a repository, and may be one repo or two.

It is orientation, not enforcement: it never blocks work. It is also **silent in
repositories that use none of these conventions**, so installing the plugin
costs nothing in a repo without a backlog, an ADR log or an architecture
document.

### `xxthunder-paperless-skills`

Skills for digitizing household paperwork:

| Skill | Description |
|---|---|
| [**naps2-scan**](plugins/xxthunder-paperless-skills/skills/naps2-scan/SKILL.md) | End-to-end scan pipeline — drives NAPS2.Console with OCR, chains into `simplex-merge` for double-sided documents on a simplex scanner, and proposes a content-derived filename |
| [**simplex-merge**](plugins/xxthunder-paperless-skills/skills/simplex-merge/SKILL.md) | Post-processing merge of two existing PDFs (odd + even pages) into one correctly ordered document |
| [**split-batch**](plugins/xxthunder-paperless-skills/skills/split-batch/SKILL.md) | Post-processing split of a single multi-document PDF into one PDF per detected document — boundary detection from page content or blank separator sheets |

## Requirements

`xxthunder-dev-skills` requires [**superpowers**](https://github.com/obra/superpowers), from the `claude-plugins-official` marketplace. The dev skills are built around it: design work reached through `superpowers:brainstorming` lands in a backlog item, and the Red-Green-Refactor discipline comes from `superpowers:test-driven-development` rather than being duplicated here.

The dependency is declared in the plugin manifest, so installing `xxthunder-dev-skills` installs `superpowers` automatically. Two consequences worth knowing:

- Enabling this plugin also enables `superpowers`.
- `claude plugin disable superpowers` is refused while this plugin is enabled — Claude Code has no optional or peer dependency model, so the requirement is hard.

`xxthunder-paperless-skills` has no such dependency and installs standalone.

## Installation

The `/plugin` slash command is supported across Claude Code, VS Code, and the GitHub Copilot CLI. Run these inside the agent's chat — each block is one command.

Add the marketplace:

```text
/plugin marketplace add xxthunder/xxthunder-agentic-skills
```

Install a plugin (swap in `xxthunder-paperless-skills` for the other one):

```text
/plugin install xxthunder-dev-skills@xxthunder-agentic-skills
```

Update plugins — the command shape differs between hosts.

In Claude Code (marketplace-level; bumps installed plugins from the refreshed catalog):

```text
/plugin marketplace update xxthunder-agentic-skills
```

In GitHub Copilot CLI (per-plugin):

```text
/plugin update xxthunder-dev-skills
```

For everything else — enable/disable, uninstall, listing, removing a marketplace, reload — see the host's own `/plugin` documentation (Claude Code, VS Code, or GitHub Copilot CLI). Subcommand availability and flags differ slightly between hosts.

### With claude-code-action (GitHub)

```yaml
- uses: anthropics/claude-code-action@v1
  with:
    plugin_marketplaces: |
      https://github.com/xxthunder/xxthunder-agentic-skills.git
    plugins: |
      xxthunder-dev-skills
      xxthunder-paperless-skills
    anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
```

## Usage

Skills trigger automatically based on conversation context, or can be invoked explicitly. See each skill's `SKILL.md` (linked above) for the full trigger list. Common cues:

**xxthunder-dev-skills**
- [**architecture-scan**](plugins/xxthunder-dev-skills/skills/architecture-scan/SKILL.md): "check the docs against reality", "is the architecture doc still true", "bootstrap the architecture doc"
- [**backlog-ops**](plugins/xxthunder-dev-skills/skills/backlog-ops/SKILL.md): "start XAS-025", "tick AC 2 on XAS-025", "close XAS-025"
- [**commit-helper**](plugins/xxthunder-dev-skills/skills/commit-helper/SKILL.md): triggered when creating commits
- [**design-record**](plugins/xxthunder-dev-skills/skills/design-record/SKILL.md): "record an ADR", "document this decision", "update the architecture doc"
- [**learnings**](plugins/xxthunder-dev-skills/skills/learnings/SKILL.md): "capture that", "that's a learning", "what do I know about X" — also proposed when the author corrects the agent
- [**logbook**](plugins/xxthunder-dev-skills/skills/logbook/SKILL.md): "log the start", "log that …", "log the close" — qualified phrases only; suggested by `backlog-ops` after a pull and after a close
- [**refinement**](plugins/xxthunder-dev-skills/skills/refinement/SKILL.md): "let's refine", "backlog refinement", "what should we work on next?"
- [**retrospective**](plugins/xxthunder-dev-skills/skills/retrospective/SKILL.md): "I'm not happy with...", "that's wrong", "why did you...?"

**xxthunder-paperless-skills**
- [**naps2-scan**](plugins/xxthunder-paperless-skills/skills/naps2-scan/SKILL.md): "scan this", "scan another", "digitize this letter/invoice", "run NAPS2"
- [**simplex-merge**](plugins/xxthunder-paperless-skills/skills/simplex-merge/SKILL.md): "merge these two PDFs", or filenames containing "ungerade"/"gerade", "odd"/"even", "front"/"back"
- [**split-batch**](plugins/xxthunder-paperless-skills/skills/split-batch/SKILL.md): "split this batch", "split this stack", "these are multiple documents", "I scanned a pile", "separate these documents"

## Roadmap

See the [backlog](docs/backlog/README.md) for current epics and stories. Near-term focus:

- Canonical skill source format enabling multi-agent emission
- GitHub Copilot target
- Additional plugins beyond dev-skills

## Development

A pytest suite at repo root covers the plugin helper scripts, the
`SessionStart` hook (exercised as a subprocess, including malformed input and
CRLF), and the ADR log's structural invariants. Tests live under
`tests/paperless/` and `tests/dev/` respectively.

```bash
uv run --group dev pytest
```

The `pyproject.toml` at repo root is a dev-only harness — it is not part of
any plugin and is not installed when users install a plugin via
`claude plugin install`. Helper scripts remain PEP 723 inline-metadata
files invokable via `uv run <script>`; the test harness imports their
top-level functions directly.

To run with coverage and the JUnit report locally (matches CI):

```bash
uv run --group dev pytest --cov --cov-report=xml --junit-xml=junit.xml
```

### CI secrets

CI uploads coverage and test results to [Codecov](https://about.codecov.io/) and
fails the build if the upload errors. The repository must define a
`CODECOV_TOKEN` secret (`Settings → Secrets and variables → Actions`) generated
from the Codecov dashboard for this repo. Without it, every push and PR will
fail at the Codecov upload step.

## License

[MIT](LICENSE)
