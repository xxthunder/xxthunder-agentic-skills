"""The cases: one prompt each, and a check that lists what is wrong with the end state.

A check returns the empty list when the run did what the scenario asks. The
first cases cover XAS-046: the board, `next`, `backlog-ops`, `logbook`. The rest
give every skill of `xxthunder-dev-skills` at least one case (XAS-047).
"""
from __future__ import annotations

import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable

from evals.board import BOARD_FILE, card, ids, jira_card
from evals.fixture import FIXTURES, IDENTITY, INITIAL_NEXT, INITIAL_PROGRESS, ITEMS, JIRA_ISSUES, State, display_id

LOG_FILE = "engineering/log.md"
HUB_FILE = "learnings/README.md"
CONVENTIONAL_RE = re.compile(r"^(feat|fix|docs|style|refactor|perf|test|chore|ci)(\([^)]+\))?: [a-z]\S.*[^.]$")
ITEM_FILE = "docs/backlog/demo-007.md"
RUBRIC = Path(__file__).resolve().parents[1] / "docs" / "rubric.md"
RUBRIC_PROMPT = (
    "Review the change on this branch against develop (`git diff develop...HEAD`) with the rubric in "
    "docs/rubric.md. Answer each criterion with evidence. End your answer with one line `FLAGGED: ` "
    "followed by the names of the criteria that have a finding, separated by commas, or `none`.")


def expect(cond: bool, msg: str) -> list[str]:
    return [] if cond else [msg]


def one_board_commit(s: State, verb: str, repo: str = "demo") -> list[str]:
    f = expect(len(s.store_commits) == 1, f"store commits: want 1, got {[c[0] for c in s.store_commits]}")
    if s.store_commits:
        subject, files = s.store_commits[0]
        f += expect(files == [BOARD_FILE], f"store commit touches {files}")
        f += expect(subject.startswith(f"docs(board): {verb} · {repo}"), f"subject {subject!r}")
    return f


def no_store_commit(s: State) -> list[str]:
    return expect(not s.store_commits, f"store changed: {[c[0] for c in s.store_commits]}")


def demo_untouched(s: State) -> list[str]:
    return (expect(s.demo_porcelain == "", f"demo working tree changed: {s.demo_porcelain!r}")
            + expect(not s.demo_remote_subjects, f"demo remote changed: {s.demo_remote_subjects}"))


def read_jira(s: State) -> bool:
    return (any("jira_issue.py" in c for c in s.commands)
            or any(k.endswith(":jira") for k in s.skills))


def mentions_board(s: State) -> bool:
    return bool(re.search(r"\bboard\b", s.output, re.I))


def check_pull_from_next(s: State) -> list[str]:
    retry = "Add retry to the sync job"
    return (one_board_commit(s, "pull")
            + expect(s.demo_status["DEMO-001"] == "In Progress", "DEMO-001 not In Progress")
            + expect("DEMO-001" not in ids(s.board_next), "card still in Next")
            + expect(ids(s.board_progress)[:1] == ["DEMO-001"], f"In Progress top: {ids(s.board_progress)}")
            + expect(s.board_progress[:1] in ([card("DEMO-001", retry, "before the release")],
                                              [card("DEMO-001", retry)]), f"card: {s.board_progress[:1]}")
            + expect(ids(s.board_next) == ["DEMO-002"], f"Next: {ids(s.board_next)}"))


def check_pull_new_card(s: State) -> list[str]:
    return (one_board_commit(s, "pull")
            + expect(s.demo_status["DEMO-007"] == "In Progress", "DEMO-007 not In Progress")
            + expect(s.board_progress[:1] == [card("DEMO-007", "Health endpoint")], f"In Progress top: {s.board_progress[:1]}")
            + expect(ids(s.board_next) == ["DEMO-001", "DEMO-002"], f"Next changed: {ids(s.board_next)}"))


def check_pull_substory(s: State) -> list[str]:
    return (one_board_commit(s, "pull")
            + expect(s.demo_status["DEMO-004a"] == "In Progress", "DEMO-004a not In Progress")
            + expect(s.demo_status["DEMO-004"] == "In Progress", "epic not cascaded")
            + expect(ids(s.board_progress)[:1] == ["DEMO-004a"], f"In Progress: {ids(s.board_progress)}")
            + expect("DEMO-004" not in ids(s.board_progress + s.board_next), "epic got a card"))


def check_close(s: State) -> list[str]:
    return (one_board_commit(s, "close")
            + expect(s.demo_status["DEMO-003"].startswith("Done"), "DEMO-003 not Done")
            + expect("DEMO-003" not in ids(s.board_progress + s.board_next), "card still on board")
            + expect(ids(s.board_progress) == ["DEMO-006", "DEMO-005"], f"other cards moved: {ids(s.board_progress)}"))


def check_pull_no_board(s: State) -> list[str]:
    return (no_store_commit(s)
            + expect(s.demo_status["DEMO-007"] == "In Progress", "pull did not happen")
            + expect(not mentions_board(s), "output mentions a board"))


def check_pull_board_unwritable(s: State) -> list[str]:
    return (no_store_commit(s)
            + expect(s.demo_status["DEMO-007"] == "In Progress", "pull did not stand")
            + expect(mentions_board(s), "board problem not reported"))


def check_show(s: State) -> list[str]:
    o = s.output
    return (no_store_commit(s) + demo_untouched(s)
            + expect(bool(re.search(r"\|\s*Next\s*\|\s*In Progress\s*\|", o)), "no two-column table")
            + expect(all(i in o for i in ("DEMO-001", "DEMO-002", "DEMO-003", "DEMO-005", "DEMO-006")), "card missing")
            + expect("High" in o and "Low" in o, "no priorities shown")
            + expect(bool(re.search(r"DEMO-005[^\n]*\b(Done|closed)\b|\b(Done|closed)\b[^\n]*DEMO-005", o)),
                     "DEMO-005 Done not flagged")
            + expect("Cache the API token" in o, "DEMO-006 title drift not flagged"))


def check_put_after(s: State) -> list[str]:
    return (one_board_commit(s, "put") + demo_untouched(s)
            + expect(ids(s.board_next) == ["DEMO-001", "DEMO-007", "DEMO-002"], f"Next: {ids(s.board_next)}")
            + expect(card("DEMO-007", "Health endpoint") in s.board_next, f"card: {s.board_next}")
            + expect(ids(s.board_progress) == ["DEMO-006", "DEMO-003", "DEMO-005"], "In Progress changed"))


OPS_041 = jira_card("OPS-041", JIRA_ISSUES["OPS-041"][0])
SEED_STATUS = {display_id(k): v[1] for k, v in ITEMS.items()}
UNRESOLVED_RE = re.compile(r"\b(Done|closed)\b|no item|not in (the )?registry|missing", re.I)


def check_put_jira(s: State) -> list[str]:
    return (one_board_commit(s, "put", "ops") + demo_untouched(s)
            + expect(s.board_next == [jira_card("OPS-043", JIRA_ISSUES["OPS-043"][0])] + INITIAL_NEXT,
                     f"Next: {s.board_next}")
            + expect(read_jira(s), "Jira was not read to make the card"))


def check_put_jira_no_access(s: State) -> list[str]:
    return (no_store_commit(s) + demo_untouched(s)
            + expect(bool(re.search(r"jira", s.output, re.I)), "output does not name the missing Jira access"))


def check_put_jira_unknown(s: State) -> list[str]:
    return (no_store_commit(s) + demo_untouched(s)
            + expect("OPS-999" in s.output, "output does not name OPS-999"))


def check_show_jira(s: State) -> list[str]:
    o = s.output
    # a table row pairs a Next cell with an In Progress cell: judge the cell that names OPS-041
    parts = [p for line in o.splitlines()
             for p in (re.split(r"(?<!\\)\|", line) if line.lstrip().startswith("|") else [line])]
    flagged = [p.strip() for p in parts if "OPS-041" in p and UNRESOLVED_RE.search(p)]
    return (no_store_commit(s) + demo_untouched(s)
            + expect("OPS-041" in o and JIRA_ISSUES["OPS-041"][0] in o, "Jira card not shown")
            + expect(not read_jira(s), "show read Jira")
            + expect(not flagged, f"OPS-041 flagged from Jira's status: {flagged}"))


def check_pull_jira(s: State) -> list[str]:
    return (one_board_commit(s, "pull", "ops") + demo_untouched(s) + no_local_commit(s)
            + expect(s.demo_status == SEED_STATUS, f"demo status moved: {s.demo_status}")
            + expect(s.board_progress[:1] == [OPS_041], f"In Progress top: {s.board_progress[:1]}")
            + expect("OPS-041" not in ids(s.board_next), "card still in Next")
            + expect(s.board_progress[1:] == INITIAL_PROGRESS, "other In Progress cards changed")
            + expect(not read_jira(s), "pull read Jira for a card that exists"))


def check_close_jira(s: State) -> list[str]:
    return (one_board_commit(s, "close", "ops") + demo_untouched(s) + no_local_commit(s)
            + expect("OPS-041" not in ids(s.board_progress + s.board_next), "card still on board")
            + expect(s.board_next == INITIAL_NEXT, f"Next changed: {ids(s.board_next)}")
            + expect(s.board_progress == INITIAL_PROGRESS, f"In Progress changed: {ids(s.board_progress)}")
            + expect(not read_jira(s), "close read Jira"))


def check_pull_jira_no_card(s: State) -> list[str]:
    return (no_store_commit(s) + demo_untouched(s) + no_local_commit(s)
            + expect(not read_jira(s), "pull read Jira for an issue without a card")
            + expect(bool(re.search(r"\bput\b", s.output, re.I)), "output does not send the author to `next put`"))


def check_pull_unregistered(s: State) -> list[str]:
    return (no_store_commit(s) + demo_untouched(s) + no_local_commit(s)
            + expect(bool(re.search(r"regist", s.output, re.I)), "output does not name the registry"))


def check_jira_transition(s: State) -> list[str]:
    return (no_store_commit(s) + demo_untouched(s)
            + expect(not any(k.endswith(":backlog-ops") or k == "backlog-ops" for k in s.skills),
                     f"backlog-ops invoked: {s.skills}")
            + expect("OPS-042" in s.output, "no answer about OPS-042"))


def check_put_in_progress(s: State) -> list[str]:
    return (no_store_commit(s) + demo_untouched(s)
            + expect(ids(s.board_next) == ["DEMO-001", "DEMO-002"], "Next changed")
            + expect("In Progress" in s.output, "refusal does not say the card is In Progress"))


def check_drop(s: State) -> list[str]:
    return (one_board_commit(s, "drop") + demo_untouched(s)
            + expect(ids(s.board_progress) == ["DEMO-006", "DEMO-003"], f"In Progress: {ids(s.board_progress)}")
            + expect(s.board_next == INITIAL_NEXT, "Next changed"))


def check_only_logbook(s: State) -> list[str]:
    return (no_store_commit(s) + demo_untouched(s)
            + expect("BOARD" in s.output, "does not say BOARD is unconfigured")
            + expect(not re.search(r"\|\s*Next\s*\|", s.output), "printed a board anyway"))


def check_logbook_done(s: State) -> list[str]:
    log_commits = [c for c in s.store_commits if LOG_FILE in c[1]]
    return (expect(len(log_commits) == 1, f"log commits: {s.store_commits}")
            + expect(not any(BOARD_FILE in c[1] for c in s.store_commits), "logbook touched the board")
            + expect(not re.search(r"next drop|drop DEMO-003", s.output, re.I), "still suggests next drop"))


def check_trigger_next(s: State) -> list[str]:
    return expect(any(k.split(":")[-1] == "next" for k in s.skills), f"skills invoked: {s.skills}")


def invoked(s: State, skill: str) -> list[str]:
    return expect(any(k.split(":")[-1] == skill for k in s.skills), f"{skill} not invoked: {s.skills}")


def no_local_commit(s: State) -> list[str]:
    return expect(not s.demo_local_subjects, f"demo committed: {s.demo_local_subjects}")


def read_only(s: State) -> list[str]:
    return no_store_commit(s) + demo_untouched(s) + no_local_commit(s)


def new_files(s: State, prefix: str) -> list[str]:
    return sorted(p for p in s.demo_files if p.startswith(prefix))


def top_log_line(s: State) -> tuple[str, str]:
    """The newest day heading of the log and the line directly under it."""
    lines = [line for line in s.store_files.get(LOG_FILE, "").splitlines() if line.strip()]
    for i, line in enumerate(lines):
        if line.startswith("## "):
            return line[3:].strip(), (lines[i + 1] if i + 1 < len(lines) else "")
    return "", ""


def one_log_commit(s: State, event: str, item: str) -> list[str]:
    day, line = top_log_line(s)
    f = expect(len(s.store_commits) == 1, f"store commits: want 1, got {[c[0] for c in s.store_commits]}")
    if s.store_commits:
        subject, files = s.store_commits[0]
        f += expect(files == [LOG_FILE], f"store commit touches {files}")
        f += expect(subject.startswith(f"docs(log): {event}"), f"subject {subject!r}")
    return (f + expect(day == date.today().isoformat(), f"newest day heading {day!r}")
            + expect(bool(re.match(rf"- \*\*{event}\*\* · demo {item} · \S", line)), f"top line {line!r}")
            + demo_untouched(s))


def check_tick(s: State) -> list[str]:
    text = s.demo_files.get(ITEM_FILE, "")
    return (no_store_commit(s) + no_local_commit(s)
            + expect("- [x] Health endpoint works" in text, "AC 1 not ticked")
            + expect(s.demo_status.get("DEMO-007") == "Open", f"status moved: {s.demo_status.get('DEMO-007')}")
            + expect(s.demo_porcelain == f"M  {ITEM_FILE}\n", f"want the item staged alone: {s.demo_porcelain!r}")
            + expect(not s.demo_remote_subjects, f"demo remote changed: {s.demo_remote_subjects}"))


def check_logbook_started(s: State) -> list[str]:
    return one_log_commit(s, "started", "DEMO-007")


def check_logbook_note(s: State) -> list[str]:
    return one_log_commit(s, "note", "DEMO-006")


def check_logbook_note_unconfirmed(s: State) -> list[str]:
    return read_only(s) + expect("?" in s.output, "does not ask the author to confirm the line")


def check_logbook_duplicate(s: State) -> list[str]:
    return (read_only(s)
            + expect("2026-10-20" in s.output, "does not name the earlier start of 2026-10-20"))


def check_capture(s: State) -> list[str]:
    commits = s.store_commits
    f = expect(len(commits) == 1, f"store commits: want 1, got {[c[0] for c in commits]}")
    notes = [n for n in s.store_files if re.fullmatch(rf"learnings/{date.today().isoformat()}_[a-z0-9_]+\.md", n)]
    f += expect(len(notes) == 1, f"new notes: {notes}")
    if commits:
        subject, files = commits[0]
        f += expect(sorted(files) == sorted(notes + [HUB_FILE]), f"store commit touches {files}")
        f += expect(subject.startswith("docs(learnings): ") and subject.endswith("(DEMO-007)"), f"subject {subject!r}")
    claim = "A health check that calls its dependencies turns one outage into many."
    if notes:
        note = s.store_files[notes[0]]
        f += expect(claim in note, "the author's claim is not in the note verbatim")
        f += expect("drafted by the agent" in note, "drafted sections are not marked")
    hub_last = [line for line in s.store_files.get(HUB_FILE, "").splitlines() if line.startswith("- ")][-1:]
    f += expect(bool(notes) and bool(hub_last) and notes[0].split("/")[-1] in hub_last[0]
                and "DEMO-007" in hub_last[0], f"hub's last line: {hub_last}")
    return f + demo_untouched(s) + no_local_commit(s)


def check_recall(s: State) -> list[str]:
    return (read_only(s)
            + expect("git_archive_exports_commits_only" in s.output or "git archive exports commits only" in s.output.lower(),
                     "the git archive note is not named")
            + expect("flaky" not in s.output.lower(), "names the unrelated note"))


ADR_PROMPT = (
    "record an ADR, it came out of DEMO-001 and we agreed on it: the sync job keeps its retry state in "
    "SQLite. Context: two concurrent runs corrupted the JSON state file twice. Redis lost because it "
    "adds a service to operate. A JSON file with a lock lost because the lock does not survive a crash. "
    "The cost we accept: a schema migration on every change of the state format.")
ADR_HEADINGS = ("## Context", "## Decision", "## Alternatives considered", "## Consequences")


def check_adr(s: State) -> list[str]:
    adrs = new_files(s, "docs/adr/0002-")
    f = expect(len(adrs) == 1, f"ADR files 0002: {adrs}") + expect(not new_files(s, "docs/adr/0003-"), "a third ADR")
    if adrs:
        text = s.demo_files[adrs[0]]
        first = text.splitlines()[0] if text else ""
        f += expect(first.startswith("# ADR-0002: "), f"heading is not `# ADR-0002: <title>`: {first!r}")
        f += expect("\u2014" not in first, "em-dash in the heading")
        f += expect("**Status**: Accepted" in text, "status not Accepted")
        f += expect(f"**Date**: {date.today().isoformat()}" in text, "date not today")
        f += expect(all(h in text for h in ADR_HEADINGS), "a section heading is missing")
        f += expect("Redis" in text and "demo-001.md" in text, "Redis or the DEMO-001 link missing")
        f += expect(adrs[0].split("/")[-1] in s.demo_files.get("docs/adr/README.md", ""), "not in the index")
    return f + no_local_commit(s) + no_store_commit(s) + expect(not s.demo_remote_subjects, "demo remote changed")


NEEDS_ID_REGEX = "^[A-Z0-9_-]{5,}"
# The repository declares a need type of its own: a `decision` entry replaces sphinx-needs' default types
# when none is declared, so the migration refuses a `ubproject.toml` without `needs.types`.
NEEDS_TYPES = '\n[[needs.types]]\ndirective = "req"\ntitle = "Requirement"\nprefix = "REQ_"\n'
NEEDS_UBPROJECT = f'[project]\nname = "demo"\n\n[needs]\nid_regex = "{NEEDS_ID_REGEX}"\n{NEEDS_TYPES}'
ADR_ONE = "docs/adr/0001-the-sync-job-runs-from-cron.md"


def check_adr_needs(s: State) -> list[str]:
    """`check_adr`, plus: both ADRs are `decision` needs and `ubproject.toml` declares the type and link."""
    f = check_adr(s)
    adrs = new_files(s, "docs/adr/0002-")
    if adrs:
        text = s.demo_files[adrs[0]]
        title = text.splitlines()[0].removeprefix("# ADR-0002: ") if text else ""
        lines = text.splitlines()
        f += expect(f"```{{decision}} {title}" in lines, f"no `{{decision}}` directive with the title {title!r}")
        f += expect(":id: ADR-0002" in lines, "no `:id: ADR-0002`")
        f += expect(":status: Accepted" in lines, "no `:status: Accepted`")
    one_lines = s.demo_files.get(ADR_ONE, "").splitlines()
    f += expect("```{decision} The sync job runs from cron" in one_lines and ":id: ADR-0001" in one_lines,
                "ADR-0001 not converted to a `decision` need")
    try:
        cfg = tomllib.loads(s.demo_files.get("ubproject.toml", ""))
    except tomllib.TOMLDecodeError as e:
        return f + [f"ubproject.toml does not parse: {e}"]
    needs = cfg.get("needs", {})
    f += expect(any(t.get("directive") == "decision" for t in needs.get("types", [])),
                "ubproject.toml declares no `decision` type")
    f += expect(needs.get("links", {}).get("constrains", {}).get("outgoing") == "constrains",
                "ubproject.toml declares no `constrains` link")
    f += expect(needs.get("id_regex") == NEEDS_ID_REGEX, "id_regex of ubproject.toml changed")
    return f


REFUSING_UBPROJECT = f'[project]\nname = "demo"\n\n[needs]\nid_regex = "^REQ_"\n{NEEDS_TYPES}'


def check_adr_needs_refused(s: State) -> list[str]:
    """The repo's `id_regex` rejects `ADR-0001`: the migration refuses, `ubproject.toml` stays as the
    user wrote it, no ADR becomes a need, and the answer shows the refusal."""
    adrs = [p for p in s.demo_files if p.startswith("docs/adr/") and p.endswith(".md")]
    return (expect(s.demo_files.get("ubproject.toml") == REFUSING_UBPROJECT, "ubproject.toml changed")
            + expect(not any("{decision}" in s.demo_files[p] for p in adrs), "an ADR carries a `{decision}` directive")
            + expect("id_regex" in s.output, "the answer does not name `id_regex`")
            + no_local_commit(s) + no_store_commit(s) + expect(not s.demo_remote_subjects, "demo remote changed"))


def check_convert_needs(s: State) -> list[str]:
    """"convert the ADRs to needs": ADR-0001 becomes a need, the type and link are declared, no new ADR."""
    f = expect(not new_files(s, "docs/adr/0002-"), "wrote a new ADR")
    one = s.demo_files.get(ADR_ONE, "").splitlines()
    f += expect("```{decision} The sync job runs from cron" in one and ":id: ADR-0001" in one and ":status: Accepted" in one,
                "ADR-0001 not converted to a `decision` need with its id and status")
    try:
        cfg = tomllib.loads(s.demo_files.get("ubproject.toml", ""))
    except tomllib.TOMLDecodeError as e:
        return f + [f"ubproject.toml does not parse: {e}"]
    needs = cfg.get("needs", {})
    f += expect(any(t.get("directive") == "decision" for t in needs.get("types", [])),
                "ubproject.toml declares no `decision` type")
    f += expect(needs.get("links", {}).get("constrains", {}).get("outgoing") == "constrains",
                "ubproject.toml declares no `constrains` link")
    return f + no_local_commit(s) + no_store_commit(s) + expect(not s.demo_remote_subjects, "demo remote changed")


NARROW_PROMPT = (
    "record an ADR, it came out of DEMO-001: ADR-0001 stays in force, except for the monthly full "
    "re-sync, which now runs from a systemd timer on the batch host. Context: the full re-sync takes "
    "three hours, and the lock file of the cron job made every hourly run behind it skip. Keeping it in "
    "cron lost because the hourly syncs stay blocked for those three hours. A Kubernetes CronJob lost "
    "because we run no cluster. The cost we accept: two schedulers to operate.")
ADR_ONE_ORIGINAL = (FIXTURES / "demo" / ADR_ONE).read_text(encoding="utf-8").replace("\r\n", "\n")


def check_narrow(s: State) -> list[str]:
    """The new ADR narrows ADR-0001; ADR-0001 says so in its Status line and nothing else changes."""
    adrs = new_files(s, "docs/adr/0002-")
    f = expect(len(adrs) == 1, f"ADR files 0002: {adrs}") + expect(not new_files(s, "docs/adr/0003-"), "a third ADR")
    one_name = ADR_ONE.split("/")[-1]
    if adrs:
        name = adrs[0].split("/")[-1]
        lines = s.demo_files[adrs[0]].splitlines()
        f += expect(bool(lines) and lines[0].startswith("# ADR-0002: ") and "\u2014" not in lines[0],
                    f"heading is not `# ADR-0002: <title>` without an em-dash: {lines[:1]}")
        related = [i for i, line in enumerate(lines) if line.startswith("**Related**")]
        narrows = [i for i, line in enumerate(lines) if line.startswith(f"**Narrows**: [ADR-0001]({one_name})")]
        f += expect(bool(narrows), f"no `**Narrows**: [ADR-0001]({one_name})` line")
        f += expect(bool(related) and bool(narrows) and narrows[0] > related[0], "`**Narrows**` is not below `**Related**`")
        status_line = f"**Status**: Accepted, narrowed by [ADR-0002]({name})"
        f += expect(status_line in s.demo_files.get(ADR_ONE, "").splitlines(), f"ADR-0001 lacks `{status_line}`")
        rows = [r for r in s.demo_files.get("docs/adr/README.md", "").splitlines() if one_name in r]
        f += expect(len(rows) == 1 and "narrowed by" in rows[0], f"index row of ADR-0001: {rows}")
    body = lambda text: text.partition("\n## Context")[2]
    f += expect(body(s.demo_files.get(ADR_ONE, "")) == body(ADR_ONE_ORIGINAL) != "", "ADR-0001's body changed")
    return f + no_local_commit(s) + no_store_commit(s) + expect(not s.demo_remote_subjects, "demo remote changed")


ADR_TWO = "docs/adr/0002-failed-pages-are-retried-three-times.md"
# ADR-0002 as the setup leaves it: a converted ADR whose need is stale (`Proposed`) while its Status line says `Accepted`.
ADR_TWO_STALE = (
    "# ADR-0002: Failed pages are retried three times\n\n"
    "```{decision} Failed pages are retried three times\n:id: ADR-0002\n:status: Proposed\n```\n\n"
    "**Status**: Accepted\n**Date**: 2026-09-10\n\n## Context\n\n"
    "The upstream API fails single pages now and then.\n\n## Decision\n\n"
    "A failed page is retried three times before the run reports it.\n\n## Consequences\n\n"
    "A run with a broken page takes three attempts longer.\n")
ADR_TWO_ROW = "| [0002](0002-failed-pages-are-retried-three-times.md) | Failed pages are retried three times | Accepted | 2026-09-10 |\n"
SUPERSEDE_PROMPT = (
    "record an ADR, it came out of DEMO-001 and we agreed on it: the sync job no longer runs from cron, "
    "it runs as a long-running worker with its own timer. This supersedes ADR-0001. Context: the worker "
    "can run a full sync of three hours without blocking the hourly runs. Keeping cron lost because its "
    "lock file made every hourly run behind a long sync skip. A Kubernetes CronJob lost because we run "
    "no cluster. The cost we accept: a process that must be kept alive and monitored.")


def check_supersede_needs(s: State) -> list[str]:
    """ADR-0001 is a converted need: the new ADR-0003 supersedes it, its Status line says so, and its need's
    `:status:` follows. ADR-0002 is a converted ADR with a stale need (`Proposed` against an `Accepted` Status
    line): its need ends `Accepted`, the author's decision in its Status line, and nothing else of it changes.
    End states only: how the skill got there is not checked."""
    adrs = new_files(s, "docs/adr/0003-")
    f = expect(len(adrs) == 1, f"ADR files 0003: {adrs}") + expect(not new_files(s, "docs/adr/0004-"), "a fourth ADR")
    one_name = ADR_ONE.split("/")[-1]
    one = s.demo_files.get(ADR_ONE, "").splitlines()
    if adrs:
        name = adrs[0].split("/")[-1]
        lines = s.demo_files[adrs[0]].splitlines()
        f += expect(bool(lines) and lines[0].startswith("# ADR-0003: ") and "\u2014" not in lines[0],
                    f"heading is not `# ADR-0003: <title>` without an em-dash: {lines[:1]}")
        f += expect(any(line.startswith("```{decision} ") for line in lines) and ":id: ADR-0003" in lines,
                    "ADR-0003 carries no `decision` need with `:id: ADR-0003`")
        f += expect(":status: Accepted" in lines, "the need of ADR-0003 lacks `:status: Accepted`")
        f += expect(any(line.startswith(f"**Supersedes**: [ADR-0001]({one_name})") for line in lines),
                    f"no `**Supersedes**: [ADR-0001]({one_name})` line")
        status_line = f"**Status**: Superseded by [ADR-0003]({name})"
        f += expect(status_line in one, f"ADR-0001 lacks `{status_line}`")
    f += expect(":status: Superseded" in one, "the need of ADR-0001 lacks `:status: Superseded`")
    f += expect(":status: Accepted" not in one, "the need of ADR-0001 still says `:status: Accepted`")
    f += expect("```{decision} The sync job runs from cron" in one and ":id: ADR-0001" in one,
                "ADR-0001 lost its `decision` need")
    body = lambda text: text.partition("\n## Context")[2]
    f += expect(body(s.demo_files.get(ADR_ONE, "")) == body(ADR_ONE_ORIGINAL) != "", "ADR-0001's body changed")
    two = s.demo_files.get(ADR_TWO, "")
    f += expect(":status: Accepted" in two.splitlines(), "the need of ADR-0002 still lacks `:status: Accepted`")
    f += expect(two == ADR_TWO_STALE.replace(":status: Proposed", ":status: Accepted", 1),
                "ADR-0002 differs from its stale original in more than the need's status")
    try:
        needs = tomllib.loads(s.demo_files.get("ubproject.toml", "")).get("needs", {})
    except tomllib.TOMLDecodeError as e:
        return f + [f"ubproject.toml does not parse: {e}"]
    f += expect(needs.get("id_regex") == NEEDS_ID_REGEX, "id_regex of ubproject.toml changed")
    return f + no_local_commit(s) + no_store_commit(s) + expect(not s.demo_remote_subjects, "demo remote changed")


def check_adr_declined(s: State) -> list[str]:
    return (read_only(s) + invoked(s, "design-record")
            + expect(not new_files(s, "docs/adr/0002-"), "wrote an ADR"))


def check_adr_asks(s: State) -> list[str]:
    return (read_only(s) + invoked(s, "design-record")
            + expect(not new_files(s, "docs/adr/0002-"), "wrote an ADR with rationale nobody gave")
            + expect("?" in s.output, "does not ask"))


def check_drift(s: State) -> list[str]:
    o = s.output
    return (read_only(s) + invoked(s, "architecture-scan")
            + expect(bool(re.search(r"src/export|\bexport\b", o)), "undocumented src/export/ not reported")
            + expect(bool(re.search(r"src/importer|\bimporter\b", o, re.I)), "vanished src/importer/ not reported"))


FEATURE_BRANCH = "feature/DEMO-007-health-endpoint"


def setup_feature_branch(demo: Path) -> None:
    subprocess.run(["git", "checkout", "-q", "-b", FEATURE_BRANCH], cwd=demo, check=True)
    (demo / "docs" / "health.md").write_text(
        "# Health endpoint\n\n`GET /health` answers 200 while the sync job ran in the last two hours.\n",
        encoding="utf-8", newline="\n")
    subprocess.run(["git", "add", "docs/health.md"], cwd=demo, check=True)


LOOP_DISPUTE = ("The test pins `GET /health` to answer 200 even when the sync job never ran; "
                "the item says it must answer 503 then.")


def loop_state(demo: Path, *pairs: str) -> None:
    script = Path(__file__).resolve().parents[1] / "plugins" / "xxthunder-dev-skills" / "scripts" / "loop.py"
    subprocess.run([sys.executable, str(script), "state", str(demo), *pairs],
                   check=True, capture_output=True, text=True)


def gate_script(gate_exit: int) -> str:
    out = ("FAILED tests/test_health.py::test_health" if gate_exit else "1 passed")
    return f"#!/bin/sh\necho '{out}'\nexit {gate_exit}\n"


def setup_gate(demo: Path, gate_exit: int = 0) -> None:
    """An executable `scripts/gate` committed on develop and pushed: the repo names its gate."""
    gate = demo / "scripts" / "gate"
    gate.parent.mkdir(exist_ok=True)
    gate.write_text(gate_script(gate_exit), encoding="utf-8", newline="\n")
    gate.chmod(0o755)
    subprocess.run(["git", "add", "--chmod=+x", "scripts/gate"], cwd=demo, check=True)
    subprocess.run(["git", *IDENTITY, "commit", "-q", "-m", "chore: add the gate"], cwd=demo, check=True)
    subprocess.run(["git", "push", "-q", "origin", "develop"], cwd=demo, check=True)


def setup_needs_switch(demo: Path, ubproject: str = NEEDS_UBPROJECT) -> None:
    """A root `ubproject.toml` and ADR-0001 under a colon heading, committed on develop and pushed:
    the repo has just switched to sphinx-needs, and its ADR headers are not needs yet."""
    (demo / "ubproject.toml").write_text(ubproject, encoding="utf-8", newline="\n")
    adr = demo / ADR_ONE
    text = adr.read_text(encoding="utf-8")
    adr.write_text(text.replace("# ADR-0001 \u2014 ", "# ADR-0001: ", 1), encoding="utf-8", newline="\n")
    subprocess.run(["git", "add", "ubproject.toml", ADR_ONE], cwd=demo, check=True)
    subprocess.run(["git", *IDENTITY, "commit", "-q", "-m", "chore: switch to sphinx-needs"], cwd=demo, check=True)
    subprocess.run(["git", "push", "-q", "origin", "develop"], cwd=demo, check=True)


def setup_needs_converted(demo: Path) -> None:
    """`setup_needs_switch`, then the migration done by hand: ADR-0001 carries its `decision` need
    (`:status: Accepted`), `ubproject.toml` declares the `decision` type and the `constrains` link, and
    ADR-0002 is a converted ADR with a stale need (`ADR_TWO_STALE`), listed in the index."""
    setup_needs_switch(demo)
    toml = demo / "ubproject.toml"
    toml.write_text(NEEDS_UBPROJECT + '\n[[needs.types]]\ndirective = "decision"\ntitle = "Decision"\nprefix = "ADR-"\n'
                    '\n[needs.links.constrains]\nincoming = "is constrained by"\noutgoing = "constrains"\n',
                    encoding="utf-8", newline="\n")
    adr = demo / ADR_ONE
    need = "```{decision} The sync job runs from cron\n:id: ADR-0001\n:status: Accepted\n```\n\n"
    adr.write_text(adr.read_text(encoding="utf-8").replace("\n\n**Status**", f"\n\n{need}**Status**", 1),
                   encoding="utf-8", newline="\n")
    (demo / ADR_TWO).write_text(ADR_TWO_STALE, encoding="utf-8", newline="\n")
    index = demo / "docs/adr/README.md"
    index.write_text(index.read_text(encoding="utf-8").replace(
        "| 2026-09-01 |\n", f"| 2026-09-01 |\n{ADR_TWO_ROW}", 1), encoding="utf-8", newline="\n")
    subprocess.run(["git", "add", "ubproject.toml", ADR_ONE, ADR_TWO, "docs/adr/README.md"], cwd=demo, check=True)
    subprocess.run(["git", *IDENTITY, "commit", "-q", "-m", "chore: convert the ADR headers to needs"], cwd=demo, check=True)
    subprocess.run(["git", "push", "-q", "origin", "develop"], cwd=demo, check=True)


def setup_needs_refused(demo: Path) -> None:
    """`setup_needs_switch` with an `id_regex` that rejects `ADR-0001`."""
    setup_needs_switch(demo, REFUSING_UBPROJECT)


def setup_loop_at_gate(demo: Path, gate_exit: int) -> None:
    """The branch of DEMO-007 with one commit, a `scripts/gate` on develop, the loop at its gate step."""
    setup_gate(demo, gate_exit)
    setup_feature_branch(demo)
    subprocess.run(["git", *IDENTITY, "commit", "-q", "-m", "feat: health endpoint (DEMO-007)"], cwd=demo, check=True)
    loop_state(demo, "item=DEMO-007", "step=gate", "fix_rounds=0")


def setup_loop_dispute(demo: Path) -> None:
    setup_gate(demo)
    loop_state(demo, "item=DEMO-007", "step=dispute", "task=1.b", "exchanges=2", f"dispute={LOOP_DISPUTE}")


QA_OFFER_RE = re.compile(r"Q ?& ?A|\bplan\b|Rückfrage|Runde", re.I)
PACKAGE_SECTIONS = ("Item", "What changes", "Gate", "Review", "Your steps", "Open")


def pr_calls(s: State, verb: str = "create") -> list[dict]:
    return [c for c in s.gh_calls if c["args"][:2] == ["pr", verb]]


READ_ONLY_GH = (["pr", "view"],)  # Claude Code looks up a PR link after every push


def no_gh_call(s: State) -> list[str]:
    """No gh call that creates or changes anything; the harness's read-only `pr view` after a push is fine."""
    writing = [c["args"] for c in s.gh_calls if c["args"][:2] not in READ_ONLY_GH]
    return expect(not writing, f"gh was called: {writing}")


def asks(s: State) -> list[str]:
    return expect("?" in s.output, "the final answer asks no question")


def check_loop_start(s: State) -> list[str]:
    plans = [f for f in s.demo_files if re.search(r"plan", f, re.I)]
    return (one_board_commit(s, "pull")
            + expect(s.demo_status["DEMO-007"] == "In Progress", "DEMO-007 not In Progress")
            + expect(s.board_progress[:1] == [card("DEMO-007", "Health endpoint")], f"In Progress top: {s.board_progress[:1]}")
            + expect(len(s.demo_remote_subjects) == 1, f"pull commits pushed: {s.demo_remote_subjects}")
            + expect(s.demo_branches == ["develop"] and s.demo_remote_branches == ["develop"],
                     f"a branch was made: {s.demo_branches} / {s.demo_remote_branches}")
            + no_gh_call(s)
            + expect(not plans, f"a plan was written before the Q&A offer: {plans}")
            + asks(s)
            + expect(bool(QA_OFFER_RE.search(s.output)), "the question does not offer a Q&A round on the plan"))


def check_loop_no_focus(s: State) -> list[str]:
    return (no_store_commit(s) + demo_untouched(s) + no_local_commit(s) + no_gh_call(s) + asks(s)
            + expect(bool(re.search(r"which|welche|what item|work item|\bitem\b", s.output, re.I)),
                     "the question does not ask which item")
            + invoked(s, "closed-loop"))


def check_loop_red_gate(s: State) -> list[str]:
    return (expect(not pr_calls(s), "a pull request was opened on a red gate")
            + expect(FEATURE_BRANCH not in s.demo_remote_branches, "the feature branch was pushed")
            + expect(s.demo_gate_by_branch and all(g == gate_script(1) for g in s.demo_gate_by_branch.values()),
                     f"scripts/gate changed: {s.demo_gate_by_branch}")
            + expect(s.loop_state.get("fix_rounds") == 2, f"fix_rounds: {s.loop_state.get('fix_rounds')}")
            + asks(s)
            + expect(bool(re.search(r"\bgate\b", s.output, re.I)) and bool(re.search(r"\bred\b|fail|rot\b", s.output, re.I)),
                     "the answer does not name the red gate"))


def heading_re(name: str) -> re.Pattern:
    """A line that opens the section *name*: `## Name`, `**Name**`, `Name:` or a bare `Name`."""
    return re.compile(rf"^(?:#{{1,6}}\s*)?(?:\*\*)?\s*{re.escape(name)}\s*(?:\*\*)?\s*(?::.*)?$", re.M | re.I)


def section(body: str, name: str) -> str | None:
    """The text of the section *name* up to the heading of the next package section; a bold
    sub-label inside it does not end it."""
    m = heading_re(name).search(body)
    if not m:
        return None
    ends = [n.start() for other in (*PACKAGE_SECTIONS, "Measurements") if other != name
            if (n := heading_re(other).search(body, m.end()))]
    return body[m.end():min(ends, default=len(body))]


GATE_NAMED_RE = re.compile(r"named by the repo|repository names|names? (its|the) gate|in its root|`?Closed loop`? section"
                           r"|vom Repo(sitory)? benannt|benennt|im Wurzel|im Root", re.I)
GATE_OTHER_RE = re.compile(r"derived|correction|workflow|abgeleitet|Korrektur", re.I)


def check_loop_green_gate(s: State) -> list[str]:
    calls = pr_calls(s)
    f = expect(len(calls) == 1, f"pr create calls: {len(calls)}") + expect(not pr_calls(s, "merge"), "the loop merged")
    if len(calls) != 1:
        return f
    body = calls[0]["body"] or ""
    at = [(m.start() if (m := heading_re(n).search(body)) else -1) for n in PACKAGE_SECTIONS]
    f += expect(-1 not in at, f"package sections missing: {[n for n, a in zip(PACKAGE_SECTIONS, at) if a < 0]}")
    f += expect(at == sorted(at), f"package sections out of order: {dict(zip(PACKAGE_SECTIONS, at))}")
    gate = section(body, "Gate") or ""
    return (f + expect("scripts/gate" in gate, "Gate section does not name scripts/gate")
            + expect(bool(GATE_NAMED_RE.search(gate)) and not GATE_OTHER_RE.search(gate),
                     "Gate section does not say the repository names its gate (or says derived/correction)")
            + expect(bool(re.search(r"exit(ed)?\s*(code\s*)?0|green|pass", gate, re.I)), "Gate section has no result"))


def check_loop_no_gate(s: State) -> list[str]:
    plans = [f for f in s.demo_files if re.search(r"plan", f, re.I)]
    return (no_gh_call(s) + invoked(s, "closed-loop")
            + expect(s.demo_branches == ["develop"] and s.demo_remote_branches == ["develop"],
                     f"a branch was made: {s.demo_branches} / {s.demo_remote_branches}")
            + expect(not plans, f"a plan was written for a repository without a gate: {plans}")
            + expect(bool(re.search(r"\bgate\b", s.output, re.I)) and bool(re.search(r"\bCI\b|Pipeline|Workflow", s.output, re.I)),
                     "the answer does not say the repository has no gate and no CI"))


def check_loop_open_dispute(s: State) -> list[str]:
    return (no_store_commit(s) + demo_untouched(s) + no_local_commit(s) + no_gh_call(s) + asks(s)
            + expect(bool(re.search(r"disput|Streit|\b503\b", s.output, re.I)), "the answer does not name the dispute"))


def check_loop_unknown_id(s: State) -> list[str]:
    return (no_store_commit(s) + demo_untouched(s) + no_local_commit(s) + no_gh_call(s)
            + expect(bool(re.search(r"regist|Registr", s.output, re.I)), "output does not name the registry")
            + invoked(s, "closed-loop"))


def check_commit(s: State) -> list[str]:
    f = expect(len(s.demo_local_subjects) == 1, f"local commits: {s.demo_local_subjects}")
    if s.demo_local_subjects:
        subject = s.demo_local_subjects[0]
        f += expect(bool(CONVENTIONAL_RE.match(subject)), f"not a conventional subject: {subject!r}")
        f += expect(subject.endswith("(DEMO-007)"), f"no item ID at the end: {subject!r}")
        f += expect(len(subject) <= 72, f"subject is {len(subject)} characters")
        f += expect("Co-Authored-By: Claude" in s.demo_head_message, "no co-author trailer")
    return (f + expect(s.demo_porcelain == "", f"left changes: {s.demo_porcelain!r}")
            + expect(not s.demo_remote_subjects, "pushed to develop") + no_store_commit(s))


def setup_greenfield(demo: Path) -> None:
    subprocess.run(["git", "rm", "-q", "-r", "docs/backlog"], cwd=demo, check=True)
    subprocess.run(["git", "-c", "user.name=Eval", "-c", "user.email=eval@example.com",
                    "commit", "-q", "-m", "drop the backlog"], cwd=demo, check=True)


def check_bootstrap(s: State) -> list[str]:
    # The setup's history holds a DEMO backlog; a new prefix keeps the bootstrap a clean start.
    readme = s.demo_files.get("docs/backlog/README.md", "")
    item = s.demo_files.get("docs/backlog/sync-001.md", "")
    return (no_store_commit(s) + no_local_commit(s)
            + expect(bool(re.search(r"\*\*ID prefix\*\*:\s*`SYNC`", readme)), "no SYNC prefix in the Notes")
            + expect("## Table of Contents" in readme and "sync-001.md" in readme, "TOC does not list SYNC-001")
            + expect("**Status**: In Progress" in item, "no refinement item SYNC-001 In Progress")
            + expect(not s.demo_remote_subjects, "demo remote changed"))


def check_refine_summary(s: State) -> list[str]:
    return (read_only(s) + invoked(s, "refinement")
            + expect(all(i in s.output for i in ("DEMO-001", "DEMO-002", "DEMO-003", "DEMO-006", "DEMO-007")),
                     "an open or in-progress item is missing from the summary"))


NEW_ITEM = "docs/backlog/demo-008.md"
BACKLOG_NEW_RE = re.compile(r"backlog\.py[\"']?\s+(?:--dir\s+\S+\s+)?new\s")
PLACEHOLDER_RE = re.compile(r"\[(?:path/to/affected/file|user role|feature|benefit|Problem statement[^\]]*|First verifiable criterion)\]")


def check_new_item(s: State) -> list[str]:
    item = s.demo_files.get(NEW_ITEM, "")
    readme = s.demo_files.get("docs/backlog/README.md", "")
    extra = [p for p in new_files(s, "docs/backlog/demo-") if p != NEW_ITEM and p.split("/")[-1][:-3] not in ITEMS]
    return (no_store_commit(s) + no_local_commit(s) + invoked(s, "refinement")
            + expect(not s.demo_remote_subjects, f"demo remote changed: {s.demo_remote_subjects}")
            + expect(any(BACKLOG_NEW_RE.search(c) for c in s.commands), f"not created by backlog.py new: {s.commands}")
            + expect(item.startswith("# [DEMO-008] "), f"no DEMO-008 item: {item[:60]!r}")
            + expect("**Status**: Open" in item, "DEMO-008 is not Open")
            + expect("(demo-008.md)" in readme, "README does not list DEMO-008")
            + expect(not PLACEHOLDER_RE.search(item), "a skeleton placeholder is left in DEMO-008")
            + expect(not extra, f"other new items: {extra}"))


def check_trigger_retrospective(s: State) -> list[str]:
    return read_only(s) + invoked(s, "retrospective")


def flagged(output: str) -> list[str] | None:
    """The criteria named on the last `FLAGGED:` line; None when there is no such line."""
    found = None
    for line in output.splitlines():
        m = re.match(r"FLAGGED:(.*)", line.strip("#*` \t"), re.I)
        if m:
            found = [n.strip().rstrip(".").strip().lower() for n in m.group(1).strip("*` \t").split(",")]
    return None if found is None else [n for n in found if n and n != "none"]


def check_rubric_flags_hand_allocation(s: State) -> list[str]:
    names = flagged(s.output)
    if names is None:
        return ["no FLAGGED line"]
    return expect(any("script before prose" in n for n in names), f"not flagged under script before prose: {names}")


def check_rubric_passes_scripted_allocation(s: State) -> list[str]:
    names = flagged(s.output)
    if names is None:
        return ["no FLAGGED line"]
    return expect(not any("script before prose" in n for n in names),
                  f"clean diff flagged under script before prose: {names}")


SKILL_BASE = """---
name: new-item
description: Create a new backlog item. Use on "new item", "add a story", "neues Item".
---

# New item

1. Ask the author for the title and the summary.
2. Write the item from the template.
"""
SKILL_STEPS = "2. Write the item from the template.\n"
SKILL_BY_HAND = ("2. Allocate the ID: list docs/backlog/, take the highest DEMO number and add one.\n"
                 "3. Write the item from the template.\n")
SKILL_BY_SCRIPT = ("2. Allocate the ID: run `python scripts/next_id.py` and use the ID it prints.\n"
                   "3. Write the item from the template.\n")
NEXT_ID = '''"""Print the next backlog ID: DEMO- plus the highest number in docs/backlog/demo-NNN.md plus one."""
import re
import sys
from pathlib import Path


def main(backlog: Path) -> str:
    numbers = [int(m.group(1)) for p in backlog.glob("demo-*.md") if (m := re.fullmatch(r"demo-(\\d{3})\\.md", p.name))]
    return f"DEMO-{max(numbers, default=0) + 1:03d}"


if __name__ == "__main__":
    print(main(Path(sys.argv[1] if len(sys.argv) > 1 else "docs/backlog")))
'''
TEST_NEXT_ID = '''import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("next_id", Path(__file__).parents[1] / "scripts" / "next_id.py")
next_id = importlib.util.module_from_spec(spec)
spec.loader.exec_module(next_id)


def test_next_id_is_one_above_the_highest(tmp_path):
    (tmp_path / "demo-001.md").write_text("", encoding="utf-8")
    (tmp_path / "demo-007.md").write_text("", encoding="utf-8")
    assert next_id.main(tmp_path) == "DEMO-008"
'''


def setup_rubric(demo: Path, step_text: str, extra: dict[str, str]) -> None:
    def git(*args: str) -> None:
        subprocess.run(["git", *IDENTITY, *args], cwd=demo, check=True)

    def put(rel: str, text: str) -> None:
        (demo / rel).parent.mkdir(parents=True, exist_ok=True)
        (demo / rel).write_text(text, encoding="utf-8", newline="\n")

    put("docs/rubric.md", RUBRIC.read_text(encoding="utf-8"))
    put("skills/new-item/SKILL.md", SKILL_BASE)
    git("add", "docs/rubric.md", "skills/new-item/SKILL.md")
    git("commit", "-q", "-m", "docs: base skill and rubric")
    git("push", "-q", "origin", "develop")
    git("checkout", "-q", "-b", "feature/DEMO-008-allocate-id")
    put("skills/new-item/SKILL.md", SKILL_BASE.replace(SKILL_STEPS, step_text))
    for rel, text in extra.items():
        put(rel, text)
    git("add", "-A")
    git("commit", "-q", "-m", "feat(new-item): allocate the ID before writing (DEMO-008)")


def setup_rubric_hand_allocation(demo: Path) -> None:
    setup_rubric(demo, SKILL_BY_HAND, {})


def setup_rubric_scripted_allocation(demo: Path) -> None:
    setup_rubric(demo, SKILL_BY_SCRIPT, {"scripts/next_id.py": NEXT_ID, "tests/test_next_id.py": TEST_NEXT_ID})


@dataclass(frozen=True)
class Case:
    name: str
    skill: str | None             # plugin skill folder the case covers; None for the rubric cases
    prompt: str
    check: Callable[[State], list[str]]
    board: bool = True            # BOARD_* point at the sandbox store
    logbook: bool = False         # LOGBOOK_* point at the sandbox store
    board_contract: bool = True   # the store's AGENTS.md has a `Board` section
    learnings: bool = False       # LEARNINGS_* point at the sandbox store
    setup: Callable[[Path], None] | None = None  # runs in the demo checkout before the seed tag
    jira: bool = False            # the fake Jira plugin is loaded
    jira_card: bool = False       # the seed board carries a Jira card
    closed_loop: bool = False     # the store's AGENTS.md has a `Closed loop` section


CASES = [
    Case("pull-from-next", "backlog-ops", "pull DEMO-001", check_pull_from_next),
    Case("pull-new-card", "backlog-ops", "pull DEMO-007", check_pull_new_card),
    Case("pull-substory", "backlog-ops", "pull DEMO-004a", check_pull_substory),
    Case("close", "backlog-ops", "close DEMO-003", check_close),
    Case("pull-no-board", "backlog-ops", "pull DEMO-007", check_pull_no_board, board=False),
    Case("pull-board-unwritable", "backlog-ops", "pull DEMO-007", check_pull_board_unwritable, board_contract=False),
    Case("next-show", "next", "/next", check_show),
    Case("next-put-after", "next", "put DEMO-007 after DEMO-001", check_put_after),
    Case("next-put-jira", "next", "put ops OPS-043 next", check_put_jira, jira=True),
    Case("next-put-jira-no-access", "next", "put ops OPS-042 next", check_put_jira_no_access),
    Case("next-put-jira-unknown", "next", "put ops OPS-999 next", check_put_jira_unknown, jira=True),
    Case("next-show-jira", "next", "/next", check_show_jira, jira=True, jira_card=True),
    Case("pull-jira", "backlog-ops", "pull OPS-041", check_pull_jira, jira=True, jira_card=True),
    Case("close-jira", "backlog-ops", "close OPS-041", check_close_jira, jira=True, jira_card=True),
    Case("pull-jira-no-card", "backlog-ops", "pull ops OPS-042", check_pull_jira_no_card, jira=True),
    Case("pull-unregistered", "backlog-ops", "pull FOO-001", check_pull_unregistered),
    # No skill: a should-not-trigger guard passes at the base by design, so the gate's RED rule cannot apply.
    Case("trigger-jira-transition", None, "transition OPS-042 to Done in Jira", check_jira_transition,
         jira=True, jira_card=True),
    Case("next-put-in-progress", "next", "put DEMO-003 next", check_put_in_progress),
    Case("next-drop", "next", "drop DEMO-005 from the board", check_drop),
    Case("next-only-logbook", "next", "/next", check_only_logbook, board=False, logbook=True),
    Case("logbook-done", "logbook", "log that DEMO-003 is done: CSV export ships. Nothing outlives this repo.",
         check_logbook_done, logbook=True),
    Case("trigger-was-steht-an", "next", "was steht an?", check_trigger_next),
    Case("tick-ac", "backlog-ops", "tick AC 1 on DEMO-007", check_tick),
    Case("logbook-started", "logbook", "log that I started DEMO-007", check_logbook_started, logbook=True),
    Case("logbook-note", "logbook", 'note in the log for DEMO-006: "Waits for the token rotation." '
         "That wording is confirmed, write it.", check_logbook_note, logbook=True),
    Case("logbook-note-unconfirmed", "logbook", "note in the log that DEMO-006 waits for the token rotation",
         check_logbook_note_unconfirmed, logbook=True),
    Case("logbook-started-again", "logbook", "log that I started DEMO-003", check_logbook_duplicate, logbook=True),
    Case("learnings-capture", "learnings",
         "capture that, from DEMO-007. The claim, in my words: \"A health check that calls its dependencies "
         "turns one outage into many.\" It outlives this repo, no repo owns it, and knowing it would have "
         "saved me last week's incident.", check_capture, learnings=True),
    Case("learnings-recall", "learnings", "what do I know about git archive?", check_recall, learnings=True),
    Case("design-record-adr", "design-record", ADR_PROMPT, check_adr),
    Case("design-record-adr-needs", "design-record", ADR_PROMPT, check_adr_needs, setup=setup_needs_switch),
    Case("design-record-adr-needs-refused", "design-record", ADR_PROMPT, check_adr_needs_refused,
         setup=setup_needs_refused),
    Case("design-record-convert-needs", "design-record", "convert the ADRs to needs", check_convert_needs,
         setup=setup_needs_switch),
    Case("design-record-supersede-needs", "design-record", SUPERSEDE_PROMPT, check_supersede_needs,
         setup=setup_needs_converted),
    Case("design-record-narrow", "design-record", NARROW_PROMPT, check_narrow),
    Case("design-record-declines", "design-record", "record an ADR: we renamed the local variable cnt to count in src/sync/",
         check_adr_declined),
    Case("design-record-asks", "design-record", "record an ADR: we chose SQLite over Redis for the retry state",
         check_adr_asks),
    Case("architecture-drift", "architecture-scan", "is the architecture doc still true?", check_drift),
    Case("commit", "commit-helper", "commit this", check_commit, setup=setup_feature_branch),
    Case("refinement-bootstrap", "refinement",
         "let's refine. There is no backlog yet: put it in docs/backlog/ with the ID prefix SYNC, "
         "and I have no initial ideas.", check_bootstrap, setup=setup_greenfield),
    Case("refinement-summary", "refinement", "let's refine", check_refine_summary),
    Case("refinement-new-item", "refinement",
         "create a new backlog item for this: the release process should be written down in RELEASE.md",
         check_new_item),
    Case("refinement-new-item-de", "refinement",
         "Bitte einen neuen Backlog-Eintrag anlegen: der Release-Ablauf soll in RELEASE.md beschrieben werden",
         check_new_item),
    Case("trigger-retrospective", "retrospective",
         "That's wrong. I am not happy that you committed the backlog straight to develop.",
         check_trigger_retrospective),
    Case("rubric-flags-hand-allocation", None, RUBRIC_PROMPT, check_rubric_flags_hand_allocation,
         board=False, setup=setup_rubric_hand_allocation),
    Case("rubric-passes-scripted-allocation", None, RUBRIC_PROMPT, check_rubric_passes_scripted_allocation,
         board=False, setup=setup_rubric_scripted_allocation),
    Case("loop-start", "closed-loop", "put DEMO-007 in the loop", check_loop_start, closed_loop=True,
         setup=setup_gate),
    Case("loop-start-de", "closed-loop", "nimm DEMO-007 in die Loop", check_loop_start, closed_loop=True,
         setup=setup_gate),
    Case("loop-no-gate", "closed-loop", "put DEMO-007 in the loop", check_loop_no_gate, closed_loop=True),
    Case("loop-make-it-so-no-focus", "closed-loop", "Make it so!", check_loop_no_focus, closed_loop=True),
    Case("loop-red-gate", "closed-loop", "continue the loop for DEMO-007", check_loop_red_gate,
         closed_loop=True, setup=lambda demo: setup_loop_at_gate(demo, 1)),
    Case("loop-green-gate", "closed-loop", "continue the loop for DEMO-007", check_loop_green_gate,
         closed_loop=True, setup=lambda demo: setup_loop_at_gate(demo, 0)),
    Case("loop-open-dispute", "closed-loop", "continue the loop for DEMO-007", check_loop_open_dispute,
         closed_loop=True, setup=setup_loop_dispute),
    Case("loop-unknown-id", "closed-loop", "put FOO-001 in the loop", check_loop_unknown_id, closed_loop=True),
]
