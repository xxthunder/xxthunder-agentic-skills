---
name: commit-helper
description: "Create a conventional commit after running pre-commit checks (unit tests, plus integration tests when source dependencies change, plus linting). Use when the user asks to commit, says 'let's commit', 'commit this', 'create a commit', stages changes for commit, or finishes a unit of work that should land. Enforces conventional-commit format, atomic commits, and AI co-author attribution. Do not trigger on incidental mentions of 'commit' in unrelated conversation."
---

<!-- Source: https://github.com/xxthunder/xxthunder-agentic-skills/tree/develop/plugins/xxthunder-dev-skills/skills/commit-helper -->

# Commit Helper

Guide for creating conventional commits with mandatory pre-commit checks.

## Tests Ship With Code

A change that alters behaviour arrives with its tests, in the same commit. The
checklist below enforces the consequence — the suite passes, and a changed
function has a changed test — but the expectation is worth stating outright,
because by commit time the choice has already been made.

**Write the test first.** The cycle comes from
`superpowers:test-driven-development`, which this plugin depends on. It is not
restated here.

One limitation worth knowing: this skill is pull-based, so it states the
expectation at the last possible moment rather than the right one. A repo that
wants the expectation present *before* implementation starts should put it in
its own always-on context — `CLAUDE.md`, `AGENTS.md`, or the equivalent. This
plugin's own repository does exactly that.

## Pre-Commit Checklist

**What "verified" means here is not defined in this skill.** It is
`superpowers:verification-before-completion`'s gate function: identify the
command that would prove the claim, run it in full, read the whole output and
the exit code, confirm it actually supports the claim, and only then say so.
Invoke that skill for the discipline; this checklist only says *which* commands
this marketplace needs.

That skill is stronger than anything written here, and it triggers on a state —
being about to claim success — rather than on a phrase. This one triggers when
a human says "let's commit". Pairing them is deliberate: the reliable trigger
pulls in the better discipline.

**Before every commit, you MUST:**

1. **Run unit tests** using the project's test execution skill
   - All tests must pass
   - If any fail, fix them before committing

2. **Run integration tests** (using the project's test execution skill) when ANY of the following apply:
   - Moved, renamed, or changed import paths in integration test files (detected by case-insensitive match of "integration" in the file path relative to the project root)
   - Modified source files that integration tests depend on
   - Refactored directory structure affecting test file locations or relative paths
   - Fixed a bug that was caught or verified by integration tests
   - Investigating whether a refactor broke an existing fix — always run integration tests to verify
   **Rule of thumb:** If the change touches anything in the dependency chain of an integration test — run them. When in doubt, run them.

3. **Verify linting** (runs automatically via the project's test execution skill)
   - Fix any Error/Warning severity issues

4. **Check whether the staged diff moves a module boundary** — a directory added, deleted or moved, or a manifest entry added or removed. If it does, and the repo keeps an architecture document, mention that `design-record` can update it.
   - **This is a suggestion, never a gate.** The commit proceeds either way. Do not withhold the commit, do not ask twice, and do not treat a declined suggestion as a problem.
   - Changes inside a module — a new function, a renamed local, a widened test — are not boundary changes and warrant no mention.

**Never commit if:**
- Any unit test fails
- Any integration test fails
- You changed a function but didn't update its tests
- You're unsure if tests cover your changes

## Conventional Commits Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Type

Must be one of:

- **feat**: New feature
- **fix**: Bug fix
- **docs**: Documentation changes
- **style**: Code style changes (formatting, no logic change)
- **refactor**: Code refactoring (no feature change or bug fix)
- **perf**: Performance improvements
- **test**: Adding or updating tests
- **chore**: Maintenance tasks (dependencies, build, etc.)
- **ci**: CI/CD changes

### Scope (Optional)

Component affected (project-specific, e.g., `api`, `auth`, `cli`, `test`).

### Subject

- Imperative mood ("add feature" not "added feature")
- Lowercase
- No period at the end
- Max 72 characters for the full line — type, scope and issue ID included
- If a JIRA or GitHub or any other backlog issue with a known id is associated, place the issue ID in parentheses at the end: `<type>(<scope>): <description> (<ISSUE-ID>)`. Omit the parenthesized ID entirely when no tracker item applies — do not commit a literal `<ISSUE-ID>` placeholder.

### Body (Optional)

- Explain what and why (not how)
- Wrap at 72 characters
- Separate from subject with blank line

### Footer (Optional)

- Breaking changes: `BREAKING CHANGE: description`
- Issue references: `Closes #123`
- Co-authored commits: `Co-Authored-By: Name <email>`

## Examples

### Simple Feature

```
feat: add input validation function (<ISSUE-ID>)

Add validateInput() to check user-supplied values.
Returns false for null or empty strings.

Co-Authored-By: Claude <model> <noreply@anthropic.com>
```

### Bug Fix

```
fix: handle names with spaces in lookup (<ISSUE-ID>)

Properly quote name parameter to support values containing spaces.

Closes #42
Co-Authored-By: Claude <model> <noreply@anthropic.com>
```

### Refactoring

```
refactor: consolidate error handling in utils (<ISSUE-ID>)

Extract common error handling pattern into helper function.
No behavior change.

Co-Authored-By: Claude <model> <noreply@anthropic.com>
```

### Multiple Changes

```
feat(api): add silent mode to command executor (<ISSUE-ID>)

- Suppresses console output when silent flag is used
- Useful for background operations
- Tests updated to verify behavior

Co-Authored-By: Claude <model> <noreply@anthropic.com>
```

## Co-Authoring with AI

When AI assists with the code, add a `Co-Authored-By` trailer naming the actual model in use — e.g., `Claude Opus 4.7`, `Claude Sonnet 4.6`. The examples in this skill use `<model>` as a placeholder; substitute the real model name when committing. This keeps attribution accurate as models evolve.

```
feat: add new feature (<ISSUE-ID>)

Description of feature.

Co-Authored-By: Claude <model> <noreply@anthropic.com>
```

For other AI assistants:

```
Co-Authored-By: GitHub Copilot <noreply@github.com>
```

## Pre-Commit Workflow

### 1. Stage Changes

```bash
git add src/module.ext test/module.test.ext
```

**Important:** Stage tests and implementation together!

### 2. Run Pre-Commit Checks

Run unit tests (and integration tests if needed) using the project's test execution skill.

### 3. Create Commit

Using heredoc for proper formatting:

```bash
git commit -m "$(cat <<'EOF'
feat: add new feature (<ISSUE-ID>)

Detailed description of the feature.

Co-Authored-By: Claude <model> <noreply@anthropic.com>
EOF
)"
```

Or interactive:

```bash
git commit
# Opens editor for commit message
```

### 4. Verify Commit

```bash
git log -1 --pretty=format:"%h %s"
git show HEAD --stat
```

## Common Patterns

### Feature Addition

```bash
# 1. Write tests
# 2. Implement feature
# 3. Run tests using the project's test execution skill

# 4. Stage changes (tests + implementation together)
git add src/validation.ext test/validation.test.ext

# 5. Commit
git commit -m "$(cat <<'EOF'
feat: add input validation helper (<ISSUE-ID>)

Add validateInput function for common input validation patterns.

Co-Authored-By: Claude <model> <noreply@anthropic.com>
EOF
)"
```

### Bug Fix

```bash
# 1. Write test reproducing bug
# 2. Fix bug
# 3. Run tests using the project's test execution skill

# 4. Stage and commit
git add src/validation.ext test/validation.test.ext
git commit -m "$(cat <<'EOF'
fix: handle null input in validation (<ISSUE-ID>)

Add null check before string operations to prevent null reference error.

Closes #123
Co-Authored-By: Claude <model> <noreply@anthropic.com>
EOF
)"
```

### Documentation Update

```bash
git add README.md
git commit -m "docs: update installation instructions (<ISSUE-ID>)"
```

### Test Updates

```bash
git add test/validation.test.ext
git commit -m "test: add coverage for edge cases (<ISSUE-ID>)"
```

## Commit Message Templates

See [commit-templates.md](references/commit-templates.md) for more examples.

## Troubleshooting

### Tests Failing Before Commit

Run tests using the project's test execution skill with detailed verbosity to see failures. Fix failing tests, run tests again, and commit once all tests pass.

### Forgot to Stage Tests, or Forgot Co-Author

Amending the most recent commit (`git commit --amend`) is allowed when **all** of the following hold:

1. **You are amending only `HEAD`** — never reach further back. Use a follow-up commit if the omission is in an older commit.
2. **You are on a feature / topic branch**, not a shared trunk (`main`, `master`, `develop`, `release/*`, or any branch others build on). Rewriting history on shared branches breaks every collaborator's local clone.
3. **The previous commit actually exists** — i.e., it was not blocked by a failing pre-commit hook. A hook failure means no commit was made, so `--amend` would rewrite the commit *before* the one you thought you made. After a hook failure, fix the issue, re-stage, and create a new commit.

If the commit has already been pushed, the amend is still fine on a feature branch — push it back with `git push --force-with-lease` (preferred over plain `--force` because it refuses to overwrite work you haven't seen). If any of the conditions above don't hold, add a follow-up commit instead, such as `test: add missed coverage for <feature>` or `chore: attribute co-author for <commit-sha>`.

### Need to Run Integration Tests

Run integration tests using the project's test execution skill. If they pass, commit.
