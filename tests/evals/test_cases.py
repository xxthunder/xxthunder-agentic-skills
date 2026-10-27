"""Evaluate the evaluator: every case fails on the untouched sandbox and passes
on the end state its scenario asks for — built here by hand, without an agent."""
from __future__ import annotations

from dataclasses import replace

import pytest

from evals.board import BOARD_FILE, card
from evals.cases import CASES
from evals.fixture import INITIAL_NEXT, INITIAL_PROGRESS, ITEMS, State, display_id

LOG_FILE = "engineering/log.md"
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
