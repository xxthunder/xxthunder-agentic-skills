# ADR-0008 — The store's `AGENTS.md` is the contract

**Status**: Accepted
**Date**: 2026-09-18
**Related**: [XAS-034](../backlog/xas-034.md), [XAS-035](../backlog/xas-035.md)

## Context

A skill that writes into a cross-repo store
([ADR-0007](0007-cross-repo-stores-are-configured-not-discovered.md)) writes
into a repository it does not own, under conventions it does not know: where a
learning goes, how the file is named, what the note template is, which hub or
index gains a line, what tests a candidate has to pass, in which language. The
store is one author's repository and changes shape whenever the author
chooses. The plugin is versioned and installed into many repositories, some
public.

Someone has to own the format. If the plugin owns it, every change to the
author's own conventions is a plugin release, and one author's note format
ships inside a tool meant to be generic. If the store owns it, the skill needs
a way to read the rules that does not depend on knowing the store in advance.

The plugin already has this seam one repository in: `design-record` follows
the conventions the consuming repository's own record states. This is the same
seam, one repository further out.

## Decision

**The rules live in the store, stated once, in the store's own `AGENTS.md`**,
in a section headed with the kind of store — `Learnings` for the learnings
skill, `Logbook` for the chronicle. The skill reads that section and follows
it. The only thing the skill hardcodes is that the section exists and what it
must name; it ships no template, no tests, no hub format and no language rule
of its own. A store without the section stops the skill with a message saying
what the store has to provide — the skill never improvises a format.

Which items a section must name is stated in each skill's `SKILL.md` and can
grow without this decision changing.

## Alternatives considered

- **The skill ships the template and format**, in a `references/` file the way
  `design-record` ships `adr-format.md`. Rejected because the analogy breaks
  at ownership: `adr-format.md` states a convention this plugin proposes to
  every consumer, while a learning's shape belongs to the one author whose
  words it holds. A store that changes its template would otherwise wait for
  a plugin release, and the plugin would carry a format that is nobody's
  business but the author's.

## Consequences

- Every store must carry the section, in prose the agent interprets. Format
  compliance therefore has no unit test in this plugin; the verification is
  the end-to-end run against a real store, and a store that wants stricter
  checking adds it on its own side.
- The coupling between plugin and store is exactly one string per skill — the
  section heading. Renaming it in the store breaks the skill; that is the
  whole interface, and it is visible in both places.
- The plugin does not version with the store's format. A store can change its
  template, hub, tests or language on any day without this repository noticing.
- The decision is written for the general case — *a cross-repo store a skill
  writes to* — so `logbook` cites this ADR and ADR-0007 rather than writing its
  own. If implementing it shows they were not general enough, they are
  superseded here, not forked there.
- If prose turns out too loose for what a skill needs, the cheap escape is a
  machine-readable block under the same heading in the same file. The rules
  still live in the store; only their form changes.
