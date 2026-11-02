"""The cases: one prompt each, and a check that lists what is wrong with the end state.

A check returns the empty list when the run did what the scenario asks. The
first cases cover XAS-046: the board, `next`, `backlog-ops`, `logbook`. The rest
give every skill of `xxthunder-dev-skills` at least one case (XAS-047).
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable

from evals.board import BOARD_FILE, card, ids, jira_card
from evals.fixture import IDENTITY, INITIAL_NEXT, INITIAL_PROGRESS, ITEMS, JIRA_ISSUES, State, display_id

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


ADR_HEADINGS = ("## Context", "## Decision", "## Alternatives considered", "## Consequences")


def check_adr(s: State) -> list[str]:
    adrs = new_files(s, "docs/adr/0002-")
    f = expect(len(adrs) == 1, f"ADR files 0002: {adrs}") + expect(not new_files(s, "docs/adr/0003-"), "a third ADR")
    if adrs:
        text = s.demo_files[adrs[0]]
        f += expect("**Status**: Accepted" in text, "status not Accepted")
        f += expect(f"**Date**: {date.today().isoformat()}" in text, "date not today")
        f += expect(all(h in text for h in ADR_HEADINGS), "a section heading is missing")
        f += expect("Redis" in text and "demo-001.md" in text, "Redis or the DEMO-001 link missing")
        f += expect(adrs[0].split("/")[-1] in s.demo_files.get("docs/adr/README.md", ""), "not in the index")
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


def setup_feature_branch(demo: Path) -> None:
    for args in (["checkout", "-q", "-b", "feature/DEMO-007-health-endpoint"],):
        subprocess.run(["git", *args], cwd=demo, check=True)
    (demo / "docs" / "health.md").write_text(
        "# Health endpoint\n\n`GET /health` answers 200 while the sync job ran in the last two hours.\n",
        encoding="utf-8", newline="\n")
    subprocess.run(["git", "add", "docs/health.md"], cwd=demo, check=True)


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
    Case("design-record-adr", "design-record",
         "record an ADR, it came out of DEMO-001 and we agreed on it: the sync job keeps its retry state in "
         "SQLite. Context: two concurrent runs corrupted the JSON state file twice. Redis lost because it "
         "adds a service to operate. A JSON file with a lock lost because the lock does not survive a crash. "
         "The cost we accept: a schema migration on every change of the state format.", check_adr),
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
]
