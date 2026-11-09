"""Evaluate the evaluator: every case fails on the untouched sandbox and passes
on the end state its scenario asks for — built here by hand, without an agent."""
from __future__ import annotations

import subprocess
import tomllib
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from evals.board import BOARD_FILE, card, jira_card
from evals.cases import ADR_ONE, ADR_ONE_ORIGINAL, ADR_TWO, ADR_TWO_ROW, ADR_TWO_STALE, CASES, NEEDS_UBPROJECT, REFUSING_UBPROJECT, FEATURE_BRANCH, RUBRIC, flagged, gate_script
from evals.fixture import INITIAL_NEXT, INITIAL_PROGRESS, ITEMS, JIRA_ISSUES, State, build, display_id

REPO = Path(__file__).resolve().parents[2]
SKILLS = REPO / "plugins/xxthunder-dev-skills/skills"
LOG_FILE = "engineering/log.md"
TODAY = date.today().isoformat()
SEED_LOG = "# Log\n\n## 2026-10-20\n- **started** · demo DEMO-003 · Export to CSV\n"
CLAIM = "A health check that calls its dependencies turns one outage into many."
NOTE = f"learnings/{TODAY}_health_checks_spread_outages.md"
ADR = "docs/adr/0002-the-sync-job-keeps-its-retry-state-in-sqlite.md"
BY_NAME = {c.name: c for c in CASES}
SUPERSEDING_ADR = "docs/adr/0003-the-sync-job-runs-as-a-long-running-worker.md"
# ADR-0001 as the setup of design-record-supersede-needs leaves it: colon heading, a converted header.
ADR_ONE_CONVERTED = ADR_ONE_ORIGINAL.replace("# ADR-0001 \u2014 ", "# ADR-0001: ", 1).replace(
    "\n\n**Status**", "\n\n```{decision} The sync job runs from cron\n:id: ADR-0001\n:status: Accepted\n```\n\n**Status**", 1)
NEW_ITEM = "docs/backlog/demo-008.md"
NEW_ITEM_TEXT = ("# [DEMO-008] Document the release process\n\n**Status**: Open\n**Priority**: Medium\n"
                 "**Component**: `RELEASE.md`\n\n**Summary**:\nAs a maintainer, I want the release steps written down.\n\n"
                 "**Description**:\nNobody remembers them.\n\n**Acceptance Criteria**:\n- [ ] RELEASE.md lists every step\n")


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


def board_commit(verb: str, repo: str = "demo") -> list[tuple[str, list[str]]]:
    return [(f"docs(board): {verb} · {repo} · x (DEMO-000)", [BOARD_FILE])]


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

JIRA_READ = ["uv run /x/scripts/jira_issue.py get OPS-041"]
JIRA_041 = jira_card("OPS-041", JIRA_ISSUES["OPS-041"][0])
SHOW_JIRA_OUTPUT = SHOW_OUTPUT.replace(
    "| | DEMO-005", "| OPS-041 — Rotate the build agents' certificates | DEMO-005")


PACKAGE_BODY = """## Item
DEMO-007 Health endpoint

## What changes
- feat: health endpoint, because the item asks for it

## Gate
`scripts/gate`, named by the repository (executable `scripts/gate`), ran in the checkout: exit 0, 1 passed.

## Review
One round, no findings.

## Your steps
`gh pr merge 1`

## Open
Nothing.
"""


def expected(name: str) -> State:
    s = untouched()
    if name in ("loop-start", "loop-start-de"):
        return replace(s, skills=["xxthunder-dev-skills:closed-loop"], store_commits=board_commit("pull"),
                       demo_status=status(s, DEMO_007="In Progress"),
                       board_progress=[card("DEMO-007", "Health endpoint")] + INITIAL_PROGRESS,
                       demo_remote_subjects=["docs(backlog): pull DEMO-007"],
                       demo_branches=["develop"], demo_remote_branches=["develop"],
                       output="DEMO-007 is pulled. Do you want a Q&A round on the plan first?")
    if name == "loop-no-gate":
        return replace(s, skills=["xxthunder-dev-skills:closed-loop"],
                       demo_branches=["develop"], demo_remote_branches=["develop"],
                       output="DEMO has no gate and no CI, so it does not take part in the loop.")
    if name == "loop-make-it-so-no-focus":
        return replace(s, skills=["xxthunder-dev-skills:closed-loop"], output="Which item should the loop take?")
    if name == "loop-red-gate":
        return replace(s, loop_state={"item": "DEMO-007", "step": "gate", "fix_rounds": 2},
                       demo_branches=["develop", FEATURE_BRANCH], demo_remote_branches=["develop"],
                       demo_gate_by_branch={"develop": gate_script(1), FEATURE_BRANCH: gate_script(1)},
                       output="The gate is still red after two fix rounds. How do you want to go on?")
    if name == "loop-green-gate":
        return replace(s, gh_calls=[{"args": ["pr", "create", "--body-file", "-"], "body": PACKAGE_BODY}])
    if name == "loop-open-dispute":
        return replace(s, output="The tester and the implementer still dispute the 503 test after two exchanges. "
                                 "Which of the two is right?")
    if name == "loop-unknown-id":
        return replace(s, skills=["xxthunder-dev-skills:closed-loop"], output="FOO-001: no row for FOO in the board's registry, so I cannot find its repo.")
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
    if name == "rubric-flags-hand-allocation":
        return replace(s, output="Script before prose: the ID is allocated by hand.\nFLAGGED: Script before prose")
    if name == "rubric-passes-scripted-allocation":
        return replace(s, output="No criterion has a finding.\nFLAGGED: none")
    if name == "pull-no-board":
        return replace(s, demo_status=status(s, DEMO_007="In Progress"), output="Pulled DEMO-007.")
    if name == "pull-board-unwritable":
        return replace(s, demo_status=status(s, DEMO_007="In Progress"),
                       output="Pulled DEMO-007. Board: the store has no `Board` section, no card moved.")
    if name == "next-show":
        return replace(s, output=SHOW_OUTPUT)
    if name == "next-put-jira":
        return replace(s, store_commits=board_commit("put", "ops"),
                       board_next=[jira_card("OPS-043", JIRA_ISSUES["OPS-043"][0])] + INITIAL_NEXT,
                       commands=["uv run /x/scripts/jira_issue.py get OPS-043"])
    if name == "next-put-jira-no-access":
        return replace(s, output="I have no Jira access in this session, so OPS-042 gets no card.")
    if name == "next-put-jira-unknown":
        return replace(s, output="Jira does not know OPS-999; no card.",
                       commands=["uv run /x/scripts/jira_issue.py get OPS-999"])
    if name == "next-show-jira":
        return replace(s, output=SHOW_JIRA_OUTPUT, board_next=INITIAL_NEXT + [JIRA_041])
    if name == "pull-jira":
        return replace(s, store_commits=board_commit("pull", "ops"), board_next=INITIAL_NEXT,
                       board_progress=[JIRA_041] + INITIAL_PROGRESS)
    if name == "close-jira":
        return replace(s, store_commits=board_commit("close", "ops"), board_next=INITIAL_NEXT)
    if name == "pull-jira-no-card":
        return replace(s, output="OPS-042 has no card on the board. Put it on the board first with `next put`.")
    if name == "pull-unregistered":
        return replace(s, output="FOO-001 is neither an item of this backlog nor in the board's registry: "
                                 "no row for FOO.")
    if name == "trigger-jira-transition":
        return replace(s, skills=["jira:jira"], output="I can only read OPS-042 here, not transition it.")
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
        adr = (f"# ADR-0002: The sync job keeps its retry state in SQLite\n\n**Status**: Accepted\n"
               f"**Date**: {TODAY}\n**Related**: [DEMO-001](../backlog/demo-001.md)\n\n## Context\n\n"
               "## Decision\n\n## Alternatives considered\n\nRedis.\n\n## Consequences\n")
        return replace(s, demo_porcelain=" M docs/adr/README.md\n?? docs/adr/0002\n",
                       demo_files={ADR: adr, "docs/adr/README.md": "| [0002](0002-the-sync-job-keeps-its-retry-state-in-sqlite.md) |"})
    if name == "design-record-adr-needs":
        base = expected("design-record-adr")
        adr = base.demo_files[ADR].replace(
            "\n\n**Status**", "\n\n```{decision} The sync job keeps its retry state in SQLite\n:id: ADR-0002\n"
            ":status: Accepted\n```\n\n**Status**", 1)
        one = ("# ADR-0001: The sync job runs from cron\n\n```{decision} The sync job runs from cron\n"
               ":id: ADR-0001\n:status: Accepted\n```\n\n**Status**: Accepted\n")
        toml = NEEDS_UBPROJECT + ('\n[[needs.types]]\ndirective = "decision"\n\n'
                                  '[needs.links.constrains]\nincoming = "is constrained by"\noutgoing = "constrains"\n')
        return replace(base, demo_files={**base.demo_files, ADR: adr, ADR_ONE: one, "ubproject.toml": toml})
    if name == "design-record-adr-needs-refused":
        base = expected("design-record-adr")
        return replace(base, output="The migration refused: ADR-0001 does not match id_regex in ubproject.toml.",
                       demo_files={**base.demo_files, "ubproject.toml": REFUSING_UBPROJECT})
    if name == "design-record-convert-needs":
        one = ("# ADR-0001: The sync job runs from cron\n\n```{decision} The sync job runs from cron\n"
               ":id: ADR-0001\n:status: Accepted\n```\n\n**Status**: Accepted\n")
        toml = NEEDS_UBPROJECT + ('\n[[needs.types]]\ndirective = "decision"\n\n'
                                  '[needs.links.constrains]\nincoming = "is constrained by"\noutgoing = "constrains"\n')
        return replace(s, demo_files={ADR_ONE: one, "ubproject.toml": toml})
    if name == "design-record-narrow":
        new = ("# ADR-0002: The monthly full re-sync runs from a systemd timer\n\n**Status**: Accepted\n"
               f"**Date**: {TODAY}\n**Related**: [DEMO-001](../backlog/demo-001.md)\n"
               "**Narrows**: [ADR-0001](0001-the-sync-job-runs-from-cron.md), for the monthly full re-sync\n\n## Context\n")
        one = ADR_ONE_ORIGINAL.replace("**Status**: Accepted",
                                       "**Status**: Accepted, narrowed by [ADR-0002](0002-the-monthly-full-re-sync-runs-from-a-systemd-timer.md)", 1)
        index = ("| [0001](0001-the-sync-job-runs-from-cron.md) | The sync job runs from cron | Accepted, narrowed by ADR-0002 |\n"
                 "| [0002](0002-the-monthly-full-re-sync-runs-from-a-systemd-timer.md) | x | Accepted |\n")
        return replace(s, demo_files={"docs/adr/0002-the-monthly-full-re-sync-runs-from-a-systemd-timer.md": new,
                                      ADR_ONE: one, "docs/adr/README.md": index})
    if name == "design-record-supersede-needs":
        two = ("# ADR-0003: The sync job runs as a long-running worker\n\n"
               "```{decision} The sync job runs as a long-running worker\n:id: ADR-0003\n:status: Accepted\n```\n\n"
               f"**Status**: Accepted\n**Date**: {TODAY}\n**Related**: [DEMO-001](../backlog/demo-001.md)\n"
               "**Supersedes**: [ADR-0001](0001-the-sync-job-runs-from-cron.md)\n\n## Context\n")
        one = ADR_ONE_CONVERTED.replace("**Status**: Accepted",
                                        "**Status**: Superseded by [ADR-0003](0003-the-sync-job-runs-as-a-long-running-worker.md)", 1
                                        ).replace(":status: Accepted", ":status: Superseded", 1)
        return replace(s, demo_files={SUPERSEDING_ADR: two, ADR_ONE: one, "ubproject.toml": NEEDS_UBPROJECT,
                                      ADR_TWO: ADR_TWO_STALE.replace(":status: Proposed", ":status: Accepted", 1)})
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
    if name in ("refinement-new-item", "refinement-new-item-de"):
        return replace(s, skills=["xxthunder-dev-skills:refinement"], demo_porcelain="?? docs/backlog/demo-008.md\n",
                       commands=['uv run "/p/scripts/backlog.py" new "Document the release process"'],
                       demo_files={NEW_ITEM: NEW_ITEM_TEXT,
                                   "docs/backlog/README.md": "### Open\n- [DEMO-008 — Document the release process](demo-008.md)\n"})
    if name == "trigger-retrospective":
        return replace(s, skills=["xxthunder-dev-skills:retrospective"])
    raise KeyError(name)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_case_fails_on_the_untouched_sandbox(case):
    assert case.check(untouched()), f"{case.name} passes without anything happening"


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_case_passes_on_its_expected_end_state(case):
    assert case.check(expected(case.name)) == []


def test_every_case_names_an_existing_skill():
    for c in CASES:
        skill_less = c.name.startswith("rubric-") or c.name == "trigger-jira-transition"  # the routing guard
        assert (c.skill is None and skill_less) or (SKILLS / c.skill / "SKILL.md").is_file(), c.name


def test_every_skill_has_a_case():
    assert {d.name for d in SKILLS.iterdir() if d.is_dir()} <= {c.skill for c in CASES}


def test_every_case_has_a_unique_name():
    assert len(BY_NAME) == len(CASES)


def test_loop_start_ignores_the_harness_pr_view_after_a_push():
    base = expected("loop-start")
    view = {"args": ["pr", "view", "--json", "url"], "body": None}
    assert BY_NAME["loop-start"].check(replace(base, gh_calls=[view])) == []
    for args in (["pr", "create"], ["pr", "edit", "1"], ["pr", "merge", "1"]):
        s = replace(base, gh_calls=[view, {"args": args, "body": None}])
        assert any("gh was called" in f for f in BY_NAME["loop-start"].check(s)), args


def test_green_gate_package_that_derives_the_gate_fails():
    body = PACKAGE_BODY.replace("named by the repository (executable `scripts/gate`)", "derived from the CI workflow")
    s = replace(untouched(), gh_calls=[{"args": ["pr", "create"], "body": body}])
    assert any("names its gate" in f for f in BY_NAME["loop-green-gate"].check(s))


def test_green_gate_with_two_pull_requests_fails():
    call = {"args": ["pr", "create"], "body": PACKAGE_BODY}
    assert any("pr create calls" in f for f in BY_NAME["loop-green-gate"].check(replace(untouched(), gh_calls=[call, call])))


@pytest.mark.parametrize("markup", ["## {}", "**{}**", "{}:"])
def test_package_headings_count_whatever_the_markup(markup):
    body = PACKAGE_BODY
    for n in ("Item", "What changes", "Gate", "Review", "Your steps", "Open"):
        body = body.replace(f"## {n}", markup.format(n))
    body = body.replace("`scripts/gate`, named", "**Command**: `scripts/gate`, named")  # a bold sub-label inside Gate
    s = replace(untouched(), gh_calls=[{"args": ["pr", "create"], "body": body}])
    assert BY_NAME["loop-green-gate"].check(s) == []


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


def test_show_jira_that_reads_jira_fails():
    s = replace(expected("next-show-jira"), commands=JIRA_READ)
    assert any("Jira" in f for f in BY_NAME["next-show-jira"].check(s))


def test_show_jira_that_flags_the_done_issue_fails():
    s = replace(expected("next-show-jira"), output=SHOW_JIRA_OUTPUT + "- OPS-041 is Done but still on the board.\n")
    assert any("OPS-041" in f for f in BY_NAME["next-show-jira"].check(s))


def test_put_jira_with_the_pipe_unescaped_fails():
    s = expected("next-put-jira")
    bad = s.board_next[0].replace("\\|", "|")
    assert any("Next" in f for f in BY_NAME["next-put-jira"].check(replace(s, board_next=[bad] + INITIAL_NEXT)))


def test_pull_jira_that_touches_the_repo_fails():
    s = replace(expected("pull-jira"), demo_remote_subjects=["docs(backlog): pull OPS-041"])
    assert any("demo" in f for f in BY_NAME["pull-jira"].check(s))


def test_close_jira_that_reads_jira_fails():
    s = replace(expected("close-jira"), commands=JIRA_READ)
    assert any("Jira" in f for f in BY_NAME["close-jira"].check(s))


def test_show_jira_that_flags_the_done_issue_in_its_cell_fails():
    s = replace(expected("next-show-jira"), output=SHOW_JIRA_OUTPUT.replace("certificates |", "certificates (Done) |"))
    assert any("OPS-041" in f for f in BY_NAME["next-show-jira"].check(s))


def test_show_jira_judges_the_cell_of_an_indented_row():
    indented = "\n".join("  " + line for line in SHOW_JIRA_OUTPUT.splitlines())
    assert BY_NAME["next-show-jira"].check(replace(expected("next-show-jira"), output=indented)) == []


@pytest.mark.parametrize("flag", ["(no item)", "(not in the registry)", "(missing)"])
def test_show_jira_that_calls_the_card_unresolved_fails(flag):
    s = replace(expected("next-show-jira"), output=SHOW_JIRA_OUTPUT.replace("certificates |", f"certificates {flag} |"))
    assert any("OPS-041" in f for f in BY_NAME["next-show-jira"].check(s))


@pytest.mark.parametrize("name", ["pull-jira", "close-jira", "pull-jira-no-card", "pull-unregistered"])
def test_jira_board_move_that_commits_in_the_repo_fails(name):
    s = replace(expected(name), demo_local_subjects=["docs(backlog): pull OPS-041"])
    assert any("committed" in f for f in BY_NAME[name].check(s))


def test_pull_jira_that_moves_a_status_fails():
    s = expected("pull-jira")
    s = replace(s, demo_status=status(s, DEMO_001="In Progress"))
    assert any("status" in f for f in BY_NAME["pull-jira"].check(s))


def test_pull_jira_no_card_that_reads_jira_fails():
    s = replace(expected("pull-jira-no-card"), commands=["uv run /x/scripts/jira_issue.py get OPS-042"])
    assert any("Jira" in f for f in BY_NAME["pull-jira-no-card"].check(s))


def test_pull_jira_no_card_that_makes_a_card_fails():
    s = replace(expected("pull-jira-no-card"), store_commits=board_commit("pull", "ops"))
    assert any("store" in f for f in BY_NAME["pull-jira-no-card"].check(s))


def test_pull_unregistered_that_moves_a_card_fails():
    s = replace(expected("pull-unregistered"), store_commits=board_commit("pull", "foo"))
    assert any("store" in f for f in BY_NAME["pull-unregistered"].check(s))


def test_jira_transition_that_invokes_backlog_ops_fails():
    s = replace(expected("trigger-jira-transition"), skills=["xxthunder-dev-skills:backlog-ops"])
    assert any("backlog-ops" in f for f in BY_NAME["trigger-jira-transition"].check(s))


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


def test_adr_with_an_em_dash_heading_fails():
    s = expected("design-record-adr")
    s = replace(s, demo_files={**s.demo_files, ADR: s.demo_files[ADR].replace("ADR-0002:", "ADR-0002 \u2014", 1)})
    fails = BY_NAME["design-record-adr"].check(s)
    assert any("heading" in f for f in fails) and any("em-dash" in f for f in fails)


def test_needs_adr_without_the_directive_fails():
    s = expected("design-record-adr")
    assert any("directive" in f for f in BY_NAME["design-record-adr-needs"].check(s))


def test_needs_adr_without_the_decision_type_fails():
    s = expected("design-record-adr-needs")
    toml = s.demo_files["ubproject.toml"].replace('directive = "decision"', 'directive = "spec"')
    fails = BY_NAME["design-record-adr-needs"].check(replace(s, demo_files={**s.demo_files, "ubproject.toml": toml}))
    assert any("`decision` type" in f for f in fails)


def test_needs_adr_with_a_changed_id_regex_fails():
    s = expected("design-record-adr-needs")
    toml = s.demo_files["ubproject.toml"].replace("{5,}", "{3,}")
    fails = BY_NAME["design-record-adr-needs"].check(replace(s, demo_files={**s.demo_files, "ubproject.toml": toml}))
    assert any("id_regex" in f for f in fails)


def test_needs_adr_with_adr_one_unconverted_fails():
    s = expected("design-record-adr-needs")
    fails = BY_NAME["design-record-adr-needs"].check(
        replace(s, demo_files={**s.demo_files, ADR_ONE: "# ADR-0001: The sync job runs from cron\n"}))
    assert any("ADR-0001" in f for f in fails)


def test_setup_needs_switch_writes_the_toml_and_the_colon_heading(tmp_path):
    from evals.cases import setup_needs_switch
    from evals.fixture import IDENTITY
    remote, demo = tmp_path / "remote.git", tmp_path / "demo"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    subprocess.run(["git", "clone", "-q", str(remote), str(demo)], check=True, capture_output=True)
    subprocess.run(["git", "checkout", "-q", "-b", "develop"], cwd=demo, check=True)
    adr = demo / ADR_ONE
    adr.parent.mkdir(parents=True)
    adr.write_text("# ADR-0001 \u2014 The sync job runs from cron\n\nbody\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=demo, check=True)
    subprocess.run(["git", *IDENTITY, "commit", "-q", "-m", "init"], cwd=demo, check=True)
    subprocess.run(["git", "push", "-q", "origin", "develop"], cwd=demo, check=True)
    setup_needs_switch(demo)
    assert (demo / "ubproject.toml").read_text(encoding="utf-8") == NEEDS_UBPROJECT
    assert [t["directive"] for t in tomllib.loads(NEEDS_UBPROJECT)["needs"]["types"]] == ["req"]
    assert adr.read_text(encoding="utf-8").startswith("# ADR-0001: The sync job runs from cron\n")
    assert subprocess.run(["git", "status", "--porcelain"], cwd=demo, capture_output=True, text=True).stdout == ""
    assert subprocess.run(["git", "rev-parse", "HEAD"], cwd=demo, capture_output=True, text=True).stdout == \
        subprocess.run(["git", "rev-parse", "origin/develop"], cwd=demo, capture_output=True, text=True).stdout


def with_file(s: State, path: str, text: str) -> State:
    return replace(s, demo_files={**s.demo_files, path: text})


def test_refused_needs_adr_with_a_rewritten_id_regex_fails():
    s = expected("design-record-adr-needs-refused")
    fails = BY_NAME["design-record-adr-needs-refused"].check(
        with_file(s, "ubproject.toml", REFUSING_UBPROJECT.replace("^REQ_", "^ADR-")))
    assert any("ubproject.toml changed" in f for f in fails)


def test_refused_needs_adr_with_a_directive_fails():
    s = expected("design-record-adr-needs-refused")
    fails = BY_NAME["design-record-adr-needs-refused"].check(with_file(s, ADR, "```{decision} T\n:id: ADR-0002\n```\n"))
    assert any("directive" in f for f in fails)


def test_refused_needs_adr_without_the_refusal_in_the_answer_fails():
    s = replace(expected("design-record-adr-needs-refused"), output="Done, ADR-0002 written.")
    assert any("id_regex" in f for f in BY_NAME["design-record-adr-needs-refused"].check(s))


def test_setup_needs_refused_writes_the_rejecting_id_regex(tmp_path, monkeypatch):
    import evals.cases as cases
    seen = []
    monkeypatch.setattr(cases, "setup_needs_switch", lambda demo, ubproject: seen.append(ubproject))
    cases.setup_needs_refused(tmp_path)
    assert seen == [REFUSING_UBPROJECT] and "^REQ_" in REFUSING_UBPROJECT
    # it declares a repository type, so the migration refuses for the id_regex only
    assert [t["directive"] for t in tomllib.loads(REFUSING_UBPROJECT)["needs"]["types"]] == ["req"]


def test_convert_that_writes_a_new_adr_fails():
    s = expected("design-record-convert-needs")
    fails = BY_NAME["design-record-convert-needs"].check(with_file(s, ADR, "# ADR-0002: x\n"))
    assert any("new ADR" in f for f in fails)


def test_convert_with_adr_one_unconverted_fails():
    s = expected("design-record-convert-needs")
    fails = BY_NAME["design-record-convert-needs"].check(with_file(s, ADR_ONE, ADR_ONE_ORIGINAL))
    assert any("ADR-0001 not converted" in f for f in fails)


def test_convert_without_the_declarations_fails():
    s = expected("design-record-convert-needs")
    fails = BY_NAME["design-record-convert-needs"].check(with_file(s, "ubproject.toml", NEEDS_UBPROJECT))
    assert any("`decision` type" in f for f in fails) and any("`constrains` link" in f for f in fails)


NEW_ADR = "docs/adr/0002-the-monthly-full-re-sync-runs-from-a-systemd-timer.md"


@pytest.mark.parametrize("path,old,new,message", [
    (NEW_ADR, "**Narrows**: [ADR-0001]", "**Replaces**: [ADR-0001]", "no `**Narrows**"),
    (NEW_ADR, "ADR-0002: The", "ADR-0002 \u2014 The", "heading"),
    (NEW_ADR, "**Related**: [DEMO-001](../backlog/demo-001.md)\n", "", "not below `**Related**`"),
    (ADR_ONE, "Accepted, narrowed by", "Accepted, see", "ADR-0001 lacks"),
    (ADR_ONE, "## Decision\n\nThe sync job", "## Decision\n\nThe full sync job", "body changed"),
    ("docs/adr/README.md", "Accepted, narrowed by ADR-0002", "Accepted", "index row"),
])
def test_narrow_with_a_broken_end_state_fails(path, old, new, message):
    s = expected("design-record-narrow")
    fails = BY_NAME["design-record-narrow"].check(with_file(s, path, s.demo_files[path].replace(old, new, 1)))
    assert any(message in f for f in fails), fails


def test_narrow_without_the_new_adr_fails():
    s = expected("design-record-narrow")
    s = replace(s, demo_files={k: v for k, v in s.demo_files.items() if k != NEW_ADR})
    assert any("ADR files 0002" in f for f in BY_NAME["design-record-narrow"].check(s))


def test_setup_needs_converted_leaves_a_converted_adr_and_the_declarations(tmp_path):
    from evals.cases import setup_needs_converted
    from evals.fixture import IDENTITY
    remote, demo = tmp_path / "remote.git", tmp_path / "demo"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    subprocess.run(["git", "clone", "-q", str(remote), str(demo)], check=True, capture_output=True)
    subprocess.run(["git", "checkout", "-q", "-b", "develop"], cwd=demo, check=True)
    adr = demo / ADR_ONE
    adr.parent.mkdir(parents=True)
    adr.write_text(ADR_ONE_ORIGINAL, encoding="utf-8", newline="\n")
    (adr.parent / "README.md").write_text(
        "| ADR | Title | Status | Date |\n|---|---|---|---|\n"
        "| [0001](0001-the-sync-job-runs-from-cron.md) | The sync job runs from cron | Accepted | 2026-09-01 |\n\n## Notes\n",
        encoding="utf-8", newline="\n")
    subprocess.run(["git", "add", "."], cwd=demo, check=True)
    subprocess.run(["git", *IDENTITY, "commit", "-q", "-m", "init"], cwd=demo, check=True)
    subprocess.run(["git", "push", "-q", "origin", "develop"], cwd=demo, check=True)
    setup_needs_converted(demo)
    assert adr.read_text(encoding="utf-8") == ADR_ONE_CONVERTED
    assert (demo / ADR_TWO).read_text(encoding="utf-8") == ADR_TWO_STALE
    assert ":status: Proposed" in ADR_TWO_STALE and "**Status**: Accepted" in ADR_TWO_STALE
    index = (demo / "docs/adr/README.md").read_text(encoding="utf-8").splitlines()
    assert index.index(ADR_TWO_ROW.rstrip("\n")) == index.index(next(r for r in index if r.startswith("| [0001]"))) + 1
    needs = tomllib.loads((demo / "ubproject.toml").read_text(encoding="utf-8"))["needs"]
    assert [t["directive"] for t in needs["types"]] == ["req", "decision"]
    assert needs["links"]["constrains"]["outgoing"] == "constrains"
    assert subprocess.run(["git", "status", "--porcelain"], cwd=demo, capture_output=True, text=True).stdout == ""
    assert subprocess.run(["git", "rev-parse", "HEAD"], cwd=demo, capture_output=True, text=True).stdout == \
        subprocess.run(["git", "rev-parse", "origin/develop"], cwd=demo, capture_output=True, text=True).stdout


@pytest.mark.parametrize("path,old,new,message", [
    (ADR_ONE, ":status: Superseded", ":status: Accepted", "still says `:status: Accepted`"),
    (ADR_ONE, ":status: Superseded", ":status: Rejected", "lacks `:status: Superseded`"),
    (ADR_ONE, "**Status**: Superseded by", "**Status**: Replaced by", "ADR-0001 lacks"),
    (ADR_ONE, "```{decision} The sync job runs from cron\n:id: ADR-0001\n", "", "lost its `decision` need"),
    (ADR_ONE, "## Decision\n\nThe sync job", "## Decision\n\nThe full sync job", "body changed"),
    (SUPERSEDING_ADR, ":status: Accepted", ":status: Proposed", "lacks `:status: Accepted`"),
    (SUPERSEDING_ADR, "```{decision} The sync job runs as a long-running worker\n:id: ADR-0003\n:status: Accepted\n```\n\n",
     "", "carries no `decision` need"),
    (SUPERSEDING_ADR, "**Supersedes**: [ADR-0001]", "**Replaces**: [ADR-0001]", "no `**Supersedes**"),
    (SUPERSEDING_ADR, "ADR-0003: The", "ADR-0003 \u2014 The", "heading"),
    (ADR_TWO, ":status: Accepted", ":status: Proposed", "still lacks `:status: Accepted`"),
    (ADR_TWO, ":status: Accepted", ":status: Superseded", "still lacks `:status: Accepted`"),
    (ADR_TWO, "## Decision\n\nA failed", "## Decision\n\nEvery failed", "differs from its stale original"),
    (ADR_TWO, "**Date**: 2026-09-10", "**Date**: 2026-11-09", "differs from its stale original"),
    (ADR_TWO, "\n", "\r\n", "differs from its stale original"),
])
def test_supersede_needs_with_a_broken_end_state_fails(path, old, new, message):
    s = expected("design-record-supersede-needs")
    fails = BY_NAME["design-record-supersede-needs"].check(with_file(s, path, s.demo_files[path].replace(old, new, 1)))
    assert any(message in f for f in fails), fails


def test_supersede_needs_without_the_new_adr_fails():
    s = expected("design-record-supersede-needs")
    s = replace(s, demo_files={k: v for k, v in s.demo_files.items() if k != SUPERSEDING_ADR})
    assert any("ADR files 0003" in f for f in BY_NAME["design-record-supersede-needs"].check(s))


def test_supersede_needs_with_a_changed_id_regex_fails():
    s = expected("design-record-supersede-needs")
    fails = BY_NAME["design-record-supersede-needs"].check(
        with_file(s, "ubproject.toml", NEEDS_UBPROJECT.replace("{5,}", "{3,}")))
    assert any("id_regex" in f for f in fails)


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


def test_new_item_written_by_hand_fails():
    s = replace(expected("refinement-new-item"), commands=["git status"])
    assert any("backlog.py new" in f for f in BY_NAME["refinement-new-item"].check(s))


def test_new_item_with_placeholders_left_fails():
    s = expected("refinement-new-item")
    s = replace(s, demo_files={**s.demo_files, NEW_ITEM: NEW_ITEM_TEXT.replace("Nobody remembers them.",
                                                                              "[Problem statement. Current behavior.]")})
    assert any("placeholder" in f for f in BY_NAME["refinement-new-item"].check(s))


def test_new_item_that_gets_pulled_fails():
    s = expected("refinement-new-item")
    s = replace(s, demo_files={**s.demo_files, NEW_ITEM: NEW_ITEM_TEXT.replace("**Status**: Open", "**Status**: In Progress")})
    assert BY_NAME["refinement-new-item"].check(s)


def test_new_item_that_commits_fails():
    s = replace(expected("refinement-new-item"), demo_local_subjects=["docs(backlog): add DEMO-008"])
    assert any("committed" in f for f in BY_NAME["refinement-new-item"].check(s))


def test_rubric_clean_diff_flagged_under_script_before_prose_fails():
    s = replace(expected("rubric-passes-scripted-allocation"), output="FLAGGED: Script before prose, Evidence")
    assert any("script before prose" in f for f in BY_NAME["rubric-passes-scripted-allocation"].check(s))


def test_rubric_clean_diff_with_other_findings_passes():
    s = replace(expected("rubric-passes-scripted-allocation"), output="**FLAGGED:** `Tests first`")
    assert BY_NAME["rubric-passes-scripted-allocation"].check(s) == []


def test_rubric_takes_the_last_flagged_line():
    out = "The author wrote `FLAGGED: none` in the template.\n\n**FLAGGED:** Script before prose\n"
    s = replace(expected("rubric-flags-hand-allocation"), output=out)
    assert BY_NAME["rubric-flags-hand-allocation"].check(s) == []


def test_flagged_none_with_a_trailing_period_is_empty():
    assert flagged("FLAGGED: none.") == []


def test_flagged_heading_line_parses_like_the_plain_line():
    assert flagged("### FLAGGED: Script before prose") == flagged("FLAGGED: Script before prose") == ["script before prose"]


def test_flagged_strips_a_trailing_period_from_each_name():
    assert flagged("FLAGGED: Script before prose, Evidence.") == ["script before prose", "evidence"]


def test_rubric_without_flagged_line_fails():
    for name in ("rubric-flags-hand-allocation", "rubric-passes-scripted-allocation"):
        s = replace(expected(name), output="Looks fine.")
        assert any("no FLAGGED line" in f for f in BY_NAME[name].check(s))


def changed_files(case: str, tmp_path) -> list[str]:
    build(tmp_path)
    demo = tmp_path / "checkouts" / "demo"
    BY_NAME[case].setup(demo)
    out = subprocess.run(["git", "diff", "develop...HEAD", "--name-only"], cwd=demo, check=True,
                         capture_output=True, text=True).stdout
    assert (demo / "docs" / "rubric.md").read_text(encoding="utf-8") == RUBRIC.read_text(encoding="utf-8")
    return out.split()


def test_hand_allocation_setup_changes_only_the_skill(tmp_path):
    assert changed_files("rubric-flags-hand-allocation", tmp_path) == ["skills/new-item/SKILL.md"]


def test_scripted_allocation_setup_adds_the_script_and_its_test(tmp_path):
    assert sorted(changed_files("rubric-passes-scripted-allocation", tmp_path)) == [
        "scripts/next_id.py", "skills/new-item/SKILL.md", "tests/test_next_id.py"]


@pytest.mark.parametrize("name", ["design-record-adr-needs", "design-record-convert-needs",
                                  "design-record-supersede-needs"])
def test_needs_check_with_an_unparsable_ubproject_fails(name):
    fails = BY_NAME[name].check(with_file(expected(name), "ubproject.toml", "[needs\n"))
    assert any("ubproject.toml does not parse" in f for f in fails), fails
