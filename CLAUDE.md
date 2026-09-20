# xxthunder-agentic-skills

Marketplace of agentic skill plugins. Hosts one or more plugins that extend coding agents; initial target is Claude Code, with additional agent targets planned.

## Project Structure

- `.claude-plugin/marketplace.json` — marketplace registry (one entry per plugin)
- `plugins/<plugin-name>/.claude-plugin/plugin.json` — plugin manifest + version
- `plugins/<plugin-name>/skills/<skill-name>/SKILL.md` — skill definitions
- `plugins/<plugin-name>/skills/<skill-name>/references/` — supporting material
- `plugins/<plugin-name>/scripts/` — plugin-level helper scripts shared by several skills (tested under `tests/`)
- `docs/backlog/` — epics and user stories (prefix `XAS`)

Current plugins:
- `xxthunder-dev-skills` — dev workflow skills (refinement, retrospective, commit-helper, backlog-ops, design-record, architecture-scan, learnings)
- `xxthunder-paperless-skills` — skills for digitizing household paperwork (scan, OCR, merge, file)

Plugins version independently; a change in one plugin only bumps that plugin's version (plus its entry in `marketplace.json`).

## Key Rules

### Skills are portable

Skills under any plugin's `skills/` are installed into other repos via the plugin system. Never add repo-specific logic, paths, or assumptions to skill files. Keep them generic and reusable.

### Version bump on every plugin change

When any file under `plugins/<plugin-name>/` is added, modified, or removed, you MUST bump the version in **both**:
- `plugins/<plugin-name>/.claude-plugin/plugin.json` → `"version"`
- `.claude-plugin/marketplace.json` → the matching `plugins[...].version`

Use semantic versioning: patch for fixes/wording, minor for behavior changes or new skills, major for breaking changes.

The rule covers the whole plugin directory, not just `skills/` — hooks under `hooks/` and the manifest itself are shipped to consumers exactly as skills are, and a change to any of them changes what an installer receives.

### Code lands through a pull request

Docs-only changes may be committed to `develop` directly: `docs/`, `README.md`,
`CONTRIBUTING.md`, this file. **Anything else** — anything under `plugins/`,
`tests/`, `.github/`, `pyproject.toml`, the manifests — goes on a feature
branch and reaches `develop` through a pull request, merged by rebase (the
`develop` ruleset allows no other method) only after **both** matrix jobs,
`Tests (ubuntu-latest)` and `Tests (windows-latest)`, are green.

A local `uv run --group dev pytest` is Linux-only evidence. Shell scripts,
hooks and path handling are exactly what differs on Windows, so for them the
CI matrix is the test, not the local run.

Why this is written here: the ruleset on `develop` requires all of the above,
but repository admins bypass it silently — a direct push by the maintainer, or
by an agent acting as the maintainer, is accepted without a word. This rule is
what protects `develop` on that path.

### Code changes ship with tests

Executable code in this repo — plugin helper scripts, the `SessionStart` hook —
changes with its tests, in the same commit. A change that alters behaviour
without touching a test is a change nobody can verify.

Write the test first. The cycle itself comes from
`superpowers:test-driven-development`, which this plugin depends on; it is not
restated here. Run the suite with:

```bash
uv run --group dev pytest
```

This rule is stated here, in always-on context, on purpose. A skill is
pull-based: it shapes behaviour only once something invokes it, and nothing
reliably invokes a TDD skill at the moment someone starts writing
implementation code. A convention has to be present before that moment, which
is what this file is for. See [XAS-030](docs/backlog/xas-030.md).

### Conventional commits

This repo uses conventional commit format. Scope should match the skill name when the change is skill-specific (e.g., `refactor(refinement): ...`, `feat(design-record): ...`). Use `chore` for version bumps and repo maintenance, and `docs(backlog)` for backlog changes.
