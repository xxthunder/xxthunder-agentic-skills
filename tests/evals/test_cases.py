"""Evaluate the evaluator: every case fails on the untouched sandbox and passes
on the end state its scenario asks for — built here by hand, without an agent."""
from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from evals.board import BOARD_FILE, card
from evals.cases import CASES
from evals.fixture import INITIAL_NEXT, INITIAL_PROGRESS, ITEMS, State, display_id

LOG_FILE = "engineering/log.md"
TODAY = date.today().isoformat()
SEED_LOG = "# Log\n\n## 2026-10-20\n- **started** · demo DEMO-003 · Export to CSV\n"
CLAIM = "A health check that calls its dependencies turns one outage into many."
NOTE = f"learnings/{TODAY}_health_checks_spread_outages.md"
ADR = "docs/adr/0002-the-sync-job-keeps-its-retry-state-in-sqlite.md"
BY_NAME = {c.name: c for c in CASES}


def untouched(output: str = "", skills: list[str] | None = None) -> State:
    return State(
        board_next=list(INITIAL_NEXT),
        board_progress=list(INITIAL_PROGRESS),
        store_commits=[],
        demo_status={display_id(k): v[1] for k, v in ITEMS.items()},
        demo_porcelain="",
        demo_remote_subjects=[],
        output=output,
        skills=skills or [],
    )


def status(s: State, **changes: str) -> dict[str, str]:
    return {**s.demo_status, **{k.replace("_", "-"): v for k, v in changes.items()}}


def board_commit(verb: str) -> list[tuple[str, list[str]]]:
    return [(f"docs(board): {verb} · demo · x (DEMO-000)", [BOARD_FILE])]


SHOW_OUTPUT = """
| Next | In Progress |
|---|---|
| DEMO-001 — Add retry to the sync job (Open, High) | DEMO-006 — Cache the token (In Progress, High) |
| DEMO-002 — Rename the config keys (Open, Low) | DEMO-003 — Export to CSV (In Progress, Medium) |
| | DEMO-005 — Drop the legacy importer (Done, Low) |

Contradictions:
- DEMO-005 is Done but still on the board.
- DEMO-006: the card says "Cache the token", the item says "Cache the API token".
"""


def expected(name: str) -> State:
    s = untouched()
    if name == "pull-from-next":
        return replace(s, store_commits=board_commit("pull"),
                       demo_status=status(s, DEMO_001="In Progress"),
                       demo_remote_subjects=["docs(backlog): pull DEMO-001"],
                       board_next=INITIAL_NEXT[1:],
                       board_progress=[INITIAL_NEXT[0]] + INITIAL_PROGRESS)
    if name == "pull-new-card":
        return replace(s, store_commits=board_commit("pull"),
                       demo_status=status(s, DEMO_007="In Progress"),
                       board_progress=[card("DEMO-007", "Health endpoint")] + INITIAL_PROGRESS)
    if name == "pull-substory":
        return replace(s, store_commits=board_commit("pull"),
                       demo_status={**s.demo_status, "DEMO-004a": "In Progress", "DEMO-004": "In Progress"},
                       board_progress=[card("DEMO-004a", "Monthly report")] + INITIAL_PROGRESS)
    if name == "close":
        return replace(s, store_commits=board_commit("close"),
                       demo_status=status(s, DEMO_003="Done (2026-10-27)"),
                       demo_porcelain="M  docs/backlog/demo-003.md\n",
                       board_progress=[INITIAL_PROGRESS[0], INITIAL_PROGRESS[2]])
    if name == "pull-no-board":
        return replace(s, demo_status=status(s, DEMO_007="In Progress"), output="Pulled DEMO-007.")
    if name == "pull-board-unwritable":
        return replace(s, demo_status=status(s, DEMO_007="In Progress"),
                       output="Pulled DEMO-007. Board: the store has no `Board` section, no card moved.")
    if name == "next-show":
        return replace(s, output=SHOW_OUTPUT)
    if name == "next-put-after":
        return replace(s, store_commits=board_commit("put"),
                       board_next=[INITIAL_NEXT[0], card("DEMO-007", "Health endpoint"), INITIAL_NEXT[1]])
    if name == "next-put-in-progress":
        return replace(s, output="DEMO-003 is In Progress; moving it back to Next is a reverse transition.")
    if name == "next-drop":
        return replace(s, store_commits=board_commit("drop"), board_progress=INITIAL_PROGRESS[:2])
    if name == "next-only-logbook":
        return replace(s, output="store: BOARD is not configured — set BOARD_PATH or BOARD_REMOTE.")
    if name == "logbook-done":
        return replace(s, store_commits=[("docs(log): done · demo · CSV export ships (DEMO-003)", [LOG_FILE])],
                       output="Logged. Does anything here outlive this repo?")
    if name == "trigger-was-steht-an":
        return replace(s, skills=["xxthunder-dev-skills:next"])
    if name == "tick-ac":
        return replace(s, demo_porcelain="M  docs/backlog/demo-007.md\n",
                       demo_files={"docs/backlog/demo-007.md": "**Status**: Open\n- [x] Health endpoint works\n"})
    if name in ("logbook-started", "logbook-note"):
        event, item = ("started", "DEMO-007") if name == "logbook-started" else ("note", "DEMO-006")
        log = SEED_LOG.replace("## 2026-10-20", f"## {TODAY}\n- **{event}** · demo {item} · x\n\n## 2026-10-20")
        return replace(s, store_commits=[(f"docs(log): {event} · demo · x ({item})", [LOG_FILE])],
                       store_files={LOG_FILE: log})
    if name == "logbook-note-unconfirmed":
        return replace(s, output="I'd add `- **note** · demo DEMO-006 · Waits for the token rotation`. Write it?")
    if name == "logbook-started-again":
        return replace(s, output="DEMO-003 was started on 2026-10-20 and has no done yet; nothing written.")
    if name == "learnings-capture":
        note = f"# Health checks spread outages\n\n## Claim\n\n{CLAIM}\n\n## Why it holds\n*(drafted by the agent)*\n"
        hub = f"# Learnings\n\n- [old](old.md) — demo `DEMO-003`, 2026-10-01\n- [{CLAIM}]({NOTE.split('/')[-1]}) — demo DEMO-007, {TODAY}\n"
        return replace(s, store_commits=[("docs(learnings): health checks spread outages (DEMO-007)",
                                          [NOTE, "learnings/README.md"])],
                       store_files={NOTE: note, "learnings/README.md": hub})
    if name == "learnings-recall":
        return replace(s, output="- git archive exports commits only — learnings/2026-10-01_git_archive_exports_commits_only.md")
    if name == "design-record-adr":
        adr = (f"# ADR-0002 — The sync job keeps its retry state in SQLite\n\n**Status**: Accepted\n"
               f"**Date**: {TODAY}\n**Related**: [DEMO-001](../backlog/demo-001.md)\n\n## Context\n\n"
               "## Decision\n\n## Alternatives considered\n\nRedis.\n\n## Consequences\n")
        return replace(s, demo_porcelain=" M docs/adr/README.md\n?? docs/adr/0002\n",
                       demo_files={ADR: adr, "docs/adr/README.md": "| [0002](0002-the-sync-job-keeps-its-retry-state-in-sqlite.md) |"})
    if name == "design-record-declines":
        return replace(s, skills=["xxthunder-dev-skills:design-record"],
                       output="This fails part 2 of the three-part test: nothing to record.")
    if name == "design-record-asks":
        return replace(s, skills=["xxthunder-dev-skills:design-record"], output="Why did Redis lose?")
    if name == "architecture-drift":
        return replace(s, skills=["xxthunder-dev-skills:architecture-scan"],
                       output="- `src/export/` is undocumented.\n- `src/importer/` no longer exists.")
    if name == "commit":
        return replace(s, demo_local_subjects=["docs: describe the health endpoint (DEMO-007)"],
                       demo_head_message="docs: describe the health endpoint (DEMO-007)\n\n"
                                         "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\n")
    if name == "refinement-bootstrap":
        return replace(s, demo_status={}, demo_porcelain="?? docs/backlog/\n",
                       demo_files={"docs/backlog/README.md": "## Table of Contents\n\n- [SYNC-001 — Refinement](sync-001.md)\n"
                                                             "\n## Notes\n\n**ID prefix**: `SYNC`\n",
                                   "docs/backlog/sync-001.md": "# [SYNC-001] Refinement\n\n**Status**: In Progress\n"})
    if name == "refinement-summary":
        return replace(s, skills=["xxthunder-dev-skills:refinement"],
                       output="In Progress: DEMO-003, DEMO-006. Open: DEMO-001, DEMO-002, DEMO-004, DEMO-007.")
    if name == "trigger-retrospective":
        return replace(s, skills=["xxthunder-dev-skills:retrospective"])
    raise KeyError(name)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_case_fails_on_the_untouched_sandbox(case):
    assert case.check(untouched()), f"{case.name} passes without anything happening"


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_case_passes_on_its_expected_end_state(case):
    assert case.check(expected(case.name)) == []


def test_every_case_has_a_unique_name():
    assert len(BY_NAME) == len(CASES)


def test_pull_with_a_second_store_commit_fails():
    s = expected("pull-from-next")
    s = replace(s, store_commits=s.store_commits * 2)
    assert any("store commits" in f for f in BY_NAME["pull-from-next"].check(s))


def test_pull_whose_store_commit_touches_another_file_fails():
    s = replace(expected("pull-new-card"), store_commits=[("docs(board): pull · demo · x", [BOARD_FILE, LOG_FILE])])
    assert any("touches" in f for f in BY_NAME["pull-new-card"].check(s))


def test_epic_with_a_card_fails():
    s = expected("pull-substory")
    s = replace(s, board_progress=[card("DEMO-004", "Reporting")] + s.board_progress)
    assert BY_NAME["pull-substory"].check(s)


def test_no_board_run_that_talks_about_a_board_fails():
    s = replace(expected("pull-no-board"), output="No board configured.")
    assert any("board" in f for f in BY_NAME["pull-no-board"].check(s))


def test_show_as_two_separate_tables_fails():
    two_tables = SHOW_OUTPUT.replace("| Next | In Progress |", "| Next |\n\n| In Progress |")
    assert any("two-column" in f for f in BY_NAME["next-show"].check(replace(untouched(), output=two_tables)))


def test_show_that_writes_into_the_consumer_fails():
    s = replace(expected("next-show"), demo_porcelain=" M docs/backlog/README.md\n")
    assert any("demo working tree" in f for f in BY_NAME["next-show"].check(s))


def test_logbook_done_that_still_suggests_next_drop_fails():
    s = replace(expected("logbook-done"), output="Logged. Suggest: `next drop DEMO-003`.")
    assert any("next drop" in f for f in BY_NAME["logbook-done"].check(s))


def test_tick_that_moves_the_status_fails():
    s = expected("tick-ac")
    s = replace(s, demo_status=status(s, DEMO_007="In Progress"))
    assert any("status moved" in f for f in BY_NAME["tick-ac"].check(s))


def test_tick_that_commits_fails():
    s = replace(expected("tick-ac"), demo_local_subjects=["docs(backlog): tick AC 1 (DEMO-007)"])
    assert any("committed" in f for f in BY_NAME["tick-ac"].check(s))


def test_log_line_appended_at_the_bottom_fails():
    s = expected("logbook-started")
    s = replace(s, store_files={LOG_FILE: SEED_LOG + f"\n## {TODAY}\n- **started** · demo DEMO-007 · x\n"})
    assert BY_NAME["logbook-started"].check(s)


def test_capture_that_rewords_the_claim_fails():
    s = expected("learnings-capture")
    s = replace(s, store_files={k: v.replace(CLAIM, "Health checks should not call dependencies.")
                                for k, v in s.store_files.items()})
    assert any("verbatim" in f for f in BY_NAME["learnings-capture"].check(s))


def test_capture_that_writes_into_the_consumer_fails():
    s = replace(expected("learnings-capture"), demo_porcelain="?? learnings/\n")
    assert any("demo working tree" in f for f in BY_NAME["learnings-capture"].check(s))


def test_recall_that_lists_every_note_fails():
    s = replace(expected("learnings-recall"), output=expected("learnings-recall").output + "\n- Flaky tests hide in retries")
    assert any("unrelated" in f for f in BY_NAME["learnings-recall"].check(s))


def test_adr_that_commits_fails():
    s = replace(expected("design-record-adr"), demo_local_subjects=["docs(adr): record ADR-0002"])
    assert any("committed" in f for f in BY_NAME["design-record-adr"].check(s))


def test_adr_that_reuses_number_one_fails():
    s = expected("design-record-adr")
    s = replace(s, demo_files={k.replace("0002", "0001"): v for k, v in s.demo_files.items()})
    assert any("ADR files 0002" in f for f in BY_NAME["design-record-adr"].check(s))


def test_adr_written_without_rationale_fails():
    s = replace(expected("design-record-asks"), demo_files={ADR: "# ADR-0002"}, demo_porcelain="?? docs/adr/\n")
    assert BY_NAME["design-record-asks"].check(s)


def test_scan_that_edits_the_document_fails():
    s = replace(expected("architecture-drift"), demo_porcelain=" M docs/architecture.md\n")
    assert any("demo working tree" in f for f in BY_NAME["architecture-drift"].check(s))


def test_commit_without_the_item_id_fails():
    s = replace(expected("commit"), demo_local_subjects=["docs: describe the health endpoint"])
    assert any("item ID" in f for f in BY_NAME["commit"].check(s))


def test_commit_that_pushes_to_develop_fails():
    s = replace(expected("commit"), demo_remote_subjects=["docs: describe the health endpoint (DEMO-007)"])
    assert any("pushed" in f for f in BY_NAME["commit"].check(s))


def test_bootstrap_that_commits_fails():
    s = replace(expected("refinement-bootstrap"), demo_local_subjects=["docs(backlog): bootstrap"])
    assert any("committed" in f for f in BY_NAME["refinement-bootstrap"].check(s))


def test_note_written_without_confirmation_fails():
    s = replace(expected("logbook-note"), output="Logged.")
    assert any("store changed" in f for f in BY_NAME["logbook-note-unconfirmed"].check(s))


def test_bootstrap_that_continues_the_old_numbering_fails():
    s = expected("refinement-bootstrap")
    s = replace(s, demo_files={k.replace("sync-001", "sync-008"): v.replace("sync-001", "sync-008")
                               for k, v in s.demo_files.items()})
    assert BY_NAME["refinement-bootstrap"].check(s)
