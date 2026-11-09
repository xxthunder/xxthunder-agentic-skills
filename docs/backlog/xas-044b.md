# [XAS-044b] ADR headers as needs

**Status**: In Progress
**Priority**: Medium
**Component**: `plugins/xxthunder-dev-skills/skills/design-record/` (ADR header, migration), `tests/`
**Depends on**: [XAS-044a](xas-044a.md)

**Summary**:
As the maintainer of a repository with a root `ubproject.toml`, I want every ADR to carry its header as a sphinx-needs need, so that ubCode and the Sphinx build index ADRs and check their links to the requirements they constrain.

**Description**:
Today an ADR's header is a block of bold-field lines. Where the switch is on (XAS-044), that block becomes one need directive and the rest of the file stays plain Markdown:

````markdown
```{decision} Two design artifacts, split by lifetime
:id: ADR-0001
:status: Accepted
:constrains: REQ-...
```
````

Backlog items keep their format: they are history, not product knowledge (XAS-044), and never become needs. An ADR that came out of an item names it in plain text, not as a need link.

**Scope Decisions**:
- **Only ADRs** (2026-11-07): item headers stay bold-field lines in every repository; `backlog.py` is not touched.
- **Switch per repository, not per ADR**: a root `ubproject.toml`. `design-record` writes the format the switch selects.
- **Migration**: one command converts all ADRs at once; it is idempotent and refuses an ADR log it cannot convert completely.
- **The heading stays beside the need title** (author, 2026-11-08): Sphinx needs a `#` heading as the page title (a page without one breaks a `-W` build in a toctree), and GitHub shows the need only as a code block. Both carry the same text; the migration copies the heading into the need title, and its tests check that they are equal. The ADR index keeps taking its title from the heading.
- **The migration writes the declarations** (author, 2026-11-08): it adds the need type `decision` and the link type `constrains` to `ubproject.toml` where they are missing, keeping the file's comments. It refuses when either already exists with other settings, or when the repository's `id_regex` rejects the ADR IDs (`ADR-0001`); it never changes `id_regex`. `status` is a built-in field.
- **The migration knows only the template** (author, 2026-11-08): it converts headers in `design-record`'s template format and refuses any other. A repository whose ADR headers differ normalizes them first, in an item of its own; for shortcuts that is a substory of SC-073.
- **A partial supersede** (author, 2026-11-08, from XAS-044a): `design-record`'s ADR format gains the status `Accepted, narrowed by ADR-NNNN`, for an ADR that stays binding outside the scope a later ADR takes over; the narrowing ADR names it in a `**Narrows**:` line below `**Related**`, as `**Supersedes**:` does (the agent's call, not discussed). ADR-0001 gets that Status line, pointing at ADR-0018, in this item's pull request.
- **The template heading is `# ADR-NNNN: Title`** (author, 2026-11-08): the em-dash is banned in new text everywhere (global rule), so `design-record`'s template separates number and title with a colon. Existing ADRs keep their headings; the migration accepts only the colon form.
- **`ubc check` runs in CI** (author, 2026-11-08): the repository is public, so `useblocks/ubc-action` needs no licence key; the action runs on Linux runners only, so the check is a step of the `ubuntu-latest` job. `ubc` ships only inside ubCode, not on PyPI, so it cannot run locally and the CI is the gate for this check; Sphinx `-W` runs in pytest.
- **The need's status follows the Status line** (author, 2026-11-09): every run of the migration rewrites `:status:` of an already converted ADR from its `**Status**` line where they differ, and reports it as `updated: <path>`; a run with nothing to change still changes nothing. `design-record` runs the migration after a supersede and after a narrowing, too, so the need never keeps `Accepted` while the Status line says `Superseded by`.
- **The migration keeps sphinx-needs' default need types** (author, 2026-11-09): a `decision` entry with `title` and `prefix` replaces sphinx-needs' default types (`req`, `spec`, `impl`, `test`, `need`) when the repository declares none. So the migration refuses a `ubproject.toml` without `needs.types` and names what to declare, as it does for a missing `id_regex`; it never writes the default types itself.
- **Loop rulings** (closed loop, 2026-11-08 and 2026-11-09; the agent's call, not discussed): the need carries only `:id:` and `:status:`, no `:constrains:`; linking requirements is the consuming repository's work. A missing `id_regex` counts as sphinx-needs' default `^[A-Z0-9_]{5,}`, which rejects `ADR-0001`, so the migration refuses it. `design-record` always writes the bold-field template and then runs the migration; there is no second template. The dev group pins `sphinx-needs>=9.2.0`, the release `ubc` 0.39.0 is built against.

**Acceptance Criteria**:
- [ ] `design-record` specifies the need-shaped ADR header, the switch and the migration
- [ ] `design-record` writes need-shaped ADR headers where the switch is on, and the old format where it is off
- [ ] The migration converts a fixture ADR log; a second run changes nothing
- [ ] A migrated fixture builds with Sphinx `-W` and passes `ubc check` without findings
- [ ] `design-record` specifies the status `Accepted, narrowed by ADR-NNNN`, and ADR-0001 carries it, pointing at ADR-0018
- [ ] The plugin version is bumped (minor)
