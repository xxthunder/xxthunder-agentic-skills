"""The cases: one prompt each, and a check that lists what is wrong with the end state.

A check returns the empty list when the run did what the scenario asks. The
first cases cover XAS-046: the board, `next`, `backlog-ops`, `logbook`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from evals.board import BOARD_FILE, card, ids
from evals.fixture import INITIAL_NEXT, State

LOG_FILE = "engineering/log.md"


def expect(cond: bool, msg: str) -> list[str]:
    return [] if cond else [msg]


def one_board_commit(s: State, verb: str) -> list[str]:
    f = expect(len(s.store_commits) == 1, f"store commits: want 1, got {[c[0] for c in s.store_commits]}")
    if s.store_commits:
        subject, files = s.store_commits[0]
        f += expect(files == [BOARD_FILE], f"store commit touches {files}")
        f += expect(subject.startswith(f"docs(board): {verb} · demo"), f"subject {subject!r}")
    return f


def no_store_commit(s: State) -> list[str]:
    return expect(not s.store_commits, f"store changed: {[c[0] for c in s.store_commits]}")


def demo_untouched(s: State) -> list[str]:
    return (expect(s.demo_porcelain == "", f"demo working tree changed: {s.demo_porcelain!r}")
            + expect(not s.demo_remote_subjects, f"demo remote changed: {s.demo_remote_subjects}"))


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


@dataclass(frozen=True)
class Case:
    name: str
    prompt: str
    check: Callable[[State], list[str]]
    board: bool = True            # BOARD_* point at the sandbox store
    logbook: bool = False         # LOGBOOK_* point at the sandbox store
    board_contract: bool = True   # the store's AGENTS.md has a `Board` section


CASES = [
    Case("pull-from-next", "pull DEMO-001", check_pull_from_next),
    Case("pull-new-card", "pull DEMO-007", check_pull_new_card),
    Case("pull-substory", "pull DEMO-004a", check_pull_substory),
    Case("close", "close DEMO-003", check_close),
    Case("pull-no-board", "pull DEMO-007", check_pull_no_board, board=False),
    Case("pull-board-unwritable", "pull DEMO-007", check_pull_board_unwritable, board_contract=False),
    Case("next-show", "/next", check_show),
    Case("next-put-after", "put DEMO-007 after DEMO-001", check_put_after),
    Case("next-put-in-progress", "put DEMO-003 next", check_put_in_progress),
    Case("next-drop", "drop DEMO-005 from the board", check_drop),
    Case("next-only-logbook", "/next", check_only_logbook, board=False, logbook=True),
    Case("logbook-done", "log that DEMO-003 is done: CSV export ships. Nothing outlives this repo.",
         check_logbook_done, logbook=True),
    Case("trigger-was-steht-an", "was steht an?", check_trigger_next),
]
