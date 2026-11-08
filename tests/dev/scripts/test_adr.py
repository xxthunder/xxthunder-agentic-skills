"""The ADR script's `migrate`, exercised against small ADR logs under `tmp_path`.

`scripts/adr.py migrate` turns every ADR header of a repository with a root
`ubproject.toml` into a sphinx-needs `decision` need (XAS-044b) and declares the
need type and the link type the needs use. Expectations here are literal text,
written by hand, never computed by the script under test.
"""
from __future__ import annotations

import runpy
import sys
import tomllib
from pathlib import Path

import pytest

import adr

ID_REGEX = "^[A-Za-z0-9_-]{6,}"
ID_REGEX_LINE = f'id_regex = "{ID_REGEX}"'
REQ_TYPE = '[[needs.types]]\ndirective = "req"\ntitle = "Requirement"\nprefix = "REQ_"\n'
# The repository declares a need type of its own: sphinx-needs' default types are then replaced, and
# migrate adds `decision` to the repository's list instead of to the defaults.
TOML = f'[project]\nname = "x"\n\n[needs]\n{ID_REGEX_LINE}\n\n{REQ_TYPE}'
TOML_NO_TYPES = f'[project]\nname = "x"\n\n[needs]\n{ID_REGEX_LINE}\n'
DECISION_TYPE = '[[needs.types]]\ndirective = "decision"\ntitle = "Decision"\nprefix = "ADR-"\n'
CONSTRAINS_LINK = '[needs.links.constrains]\nincoming = "is constrained by"\noutgoing = "constrains"\n'
# What migrate leaves behind: tomlkit appends a following array-of-tables entry without a blank line.
TOML_DECLARED = f"{TOML}{DECISION_TYPE}\n{CONSTRAINS_LINK}"

OLD_ONE = (
    "# ADR-0001: Keep the log\n"
    "\n"
    "**Status**: Accepted\n"
    "**Date**: 2026-11-08\n"
    "**Related**: [X-1](../backlog/x-1.md)\n"
    "\n"
    "## Context\n"
    "\n"
    "We need to remember why.\n"
)

NEW_ONE = (
    "# ADR-0001: Keep the log\n"
    "\n"
    "```{decision} Keep the log\n"
    ":id: ADR-0001\n"
    ":status: Accepted\n"
    "```\n"
    "\n"
    "**Status**: Accepted\n"
    "**Date**: 2026-11-08\n"
    "**Related**: [X-1](../backlog/x-1.md)\n"
    "\n"
    "## Context\n"
    "\n"
    "We need to remember why.\n"
)

OLD_TWO = (
    "# ADR-0002: Split the store\n"
    "\n"
    "**Status**: Proposed\n"
    "**Date**: 2026-11-09\n"
    "\n"
    "## Context\n"
    "\n"
    "One store is too big.\n"
)

NEW_TWO = (
    "# ADR-0002: Split the store\n"
    "\n"
    "```{decision} Split the store\n"
    ":id: ADR-0002\n"
    ":status: Proposed\n"
    "```\n"
    "\n"
    "**Status**: Proposed\n"
    "**Date**: 2026-11-09\n"
    "\n"
    "## Context\n"
    "\n"
    "One store is too big.\n"
)

OLD_THREE = (
    "# ADR-0003: Third thing\n"
    "\n"
    "**Status**: Accepted\n"
    "**Date**: 2026-11-10\n"
    "\n"
    "## Context\n"
    "\n"
    "Third.\n"
)

ONE = "0001-keep-the-log.md"
TWO = "0002-split-the-store.md"
THREE = "0003-third-thing.md"


def write(path: Path, text: str) -> Path:
    """Write *text* with its line endings untouched."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path


def make_repo(tmp_path: Path, adrs: dict[str, str], toml: str | None = TOML, adr_dir: str = "docs/adr") -> Path:
    """A repository with the given ADRs under *adr_dir* and, unless *toml* is None, a root ubproject.toml."""
    for name, text in adrs.items():
        write(tmp_path / adr_dir / name, text)
    if toml is not None:
        write(tmp_path / "ubproject.toml", toml)
    return tmp_path


def snapshot(root: Path) -> dict[str, bytes]:
    """Every file under *root* with its exact bytes."""
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def run(repo: Path, capsys) -> tuple[int, list[str], str]:
    """Run `adr.main(["migrate", "--repo", repo])`; return exit code, stdout lines and stderr."""
    code = adr.main(["migrate", "--repo", str(repo)])
    captured = capsys.readouterr()
    return code, captured.out.splitlines(), captured.err


def read_bytes(repo: Path, name: str, adr_dir: str = "docs/adr") -> bytes:
    return (repo / adr_dir / name).read_bytes()


def assert_id_regex_kept(repo: Path) -> None:
    """The migration never writes or changes an `id_regex`: the accepting one is still there, as written."""
    result = (repo / "ubproject.toml").read_text(encoding="utf-8")
    assert ID_REGEX_LINE in result.splitlines()
    assert tomllib.loads(result)["needs"]["id_regex"] == ID_REGEX


def test_converts_a_template_header(tmp_path, capsys):
    repo = make_repo(tmp_path, {ONE: OLD_ONE})

    code, out, err = run(repo, capsys)

    assert code == 0
    assert err == ""
    assert read_bytes(repo, ONE) == NEW_ONE.encode("utf-8")
    assert "converted: docs/adr/0001-keep-the-log.md" in out
    assert_id_regex_kept(repo)


def test_need_title_equals_the_heading_text(tmp_path, capsys):
    old = "# ADR-0004: Use X: a plan\n\n**Status**: Accepted\n**Date**: 2026-11-11\n\n## Context\n\nBody.\n"
    new = (
        "# ADR-0004: Use X: a plan\n"
        "\n"
        "```{decision} Use X: a plan\n"
        ":id: ADR-0004\n"
        ":status: Accepted\n"
        "```\n"
        "\n"
        "**Status**: Accepted\n"
        "**Date**: 2026-11-11\n"
        "\n"
        "## Context\n"
        "\n"
        "Body.\n"
    )
    repo = make_repo(tmp_path, {"0004-use-x.md": old})

    code, _, _ = run(repo, capsys)

    assert code == 0
    assert read_bytes(repo, "0004-use-x.md") == new.encode("utf-8")
    assert_id_regex_kept(repo)


def test_title_drops_trailing_spaces(tmp_path, capsys):
    old = OLD_ONE.replace("# ADR-0001: Keep the log\n", "# ADR-0001: Keep the log   \n")
    new = NEW_ONE.replace("# ADR-0001: Keep the log\n", "# ADR-0001: Keep the log   \n", 1)
    repo = make_repo(tmp_path, {ONE: old})

    code, _, _ = run(repo, capsys)

    assert code == 0
    result = read_bytes(repo, ONE)
    assert result == new.encode("utf-8")
    assert result.startswith(b"# ADR-0001: Keep the log   \n\n```{decision} Keep the log\n:id: ADR-0001\n")
    assert_id_regex_kept(repo)


@pytest.mark.parametrize(
    ("status_line", "word"),
    [
        ("Accepted, narrowed by [ADR-0002](0002-x.md)", "Accepted"),
        ("Superseded by [ADR-0003](0003-x.md)", "Superseded"),
        ("Rejected", "Rejected"),
        ("Proposed", "Proposed"),
    ],
)
def test_status_word_drops_links_and_tail(tmp_path, capsys, status_line, word):
    old = f"# ADR-0005: Some choice\n\n**Status**: {status_line}\n**Date**: 2026-11-12\n\n## Context\n\nBody.\n"
    new = (
        "# ADR-0005: Some choice\n"
        "\n"
        "```{decision} Some choice\n"
        ":id: ADR-0005\n"
        f":status: {word}\n"
        "```\n"
        "\n"
        f"**Status**: {status_line}\n"
        "**Date**: 2026-11-12\n"
        "\n"
        "## Context\n"
        "\n"
        "Body.\n"
    )
    repo = make_repo(tmp_path, {"0005-some-choice.md": old})

    code, _, _ = run(repo, capsys)

    assert code == 0
    assert read_bytes(repo, "0005-some-choice.md") == new.encode("utf-8")
    assert_id_regex_kept(repo)


def test_accepts_supersedes_and_narrows_fields(tmp_path, capsys):
    old = (
        "# ADR-0006: Later choice\n"
        "\n"
        "**Status**: Accepted\n"
        "**Date**: 2026-11-13\n"
        "**Related**: [X-2](../backlog/x-2.md)\n"
        "**Supersedes**: [ADR-0003](0003-third-thing.md)\n"
        "**Narrows**: [ADR-0001](0001-keep-the-log.md)\n"
        "\n"
        "## Context\n"
        "\n"
        "Body.\n"
    )
    new = (
        "# ADR-0006: Later choice\n"
        "\n"
        "```{decision} Later choice\n"
        ":id: ADR-0006\n"
        ":status: Accepted\n"
        "```\n"
        "\n"
        "**Status**: Accepted\n"
        "**Date**: 2026-11-13\n"
        "**Related**: [X-2](../backlog/x-2.md)\n"
        "**Supersedes**: [ADR-0003](0003-third-thing.md)\n"
        "**Narrows**: [ADR-0001](0001-keep-the-log.md)\n"
        "\n"
        "## Context\n"
        "\n"
        "Body.\n"
    )
    repo = make_repo(tmp_path, {"0006-later-choice.md": old})

    code, _, _ = run(repo, capsys)

    assert code == 0
    assert read_bytes(repo, "0006-later-choice.md") == new.encode("utf-8")
    assert_id_regex_kept(repo)


def test_declares_type_and_link(tmp_path, capsys):
    repo = make_repo(tmp_path, {ONE: OLD_ONE})

    code, out, _ = run(repo, capsys)

    assert code == 0
    assert "declared: need type decision" in out
    assert "declared: link type constrains" in out
    data = tomllib.loads((repo / "ubproject.toml").read_text(encoding="utf-8"))
    assert data["project"] == {"name": "x"}
    assert [t["directive"] for t in data["needs"]["types"]] == ["req", "decision"]
    types = [t for t in data["needs"]["types"] if t["directive"] == "decision"]
    assert len(types) == 1
    assert types[0]["title"] == "Decision"
    assert types[0]["prefix"] == "ADR-"
    constrains = data["needs"]["links"]["constrains"]
    assert constrains["incoming"] == "is constrained by"
    assert constrains["outgoing"] == "constrains"
    assert_id_regex_kept(repo)


def test_decision_follows_the_repository_type(tmp_path, capsys):
    repo = make_repo(tmp_path, {ONE: OLD_ONE})

    code, _, _ = run(repo, capsys)

    assert code == 0
    assert (repo / "ubproject.toml").read_text(encoding="utf-8") == TOML_DECLARED


def test_keeps_toml_comments_and_order(tmp_path, capsys):
    toml = (
        "# Project settings\n"
        "[project]\n"
        'name = "x"  # the name\n'
        "\n"
        "# Needs\n"
        "[needs]\n"
        'id_regex = "^[A-Za-z0-9_-]{6,}"  # six or more\n'
        "\n"
        "[[needs.types]]\n"
        'directive = "requirement"\n'
        'title = "Requirement"\n'
        'prefix = "REQ-"\n'
        "\n"
        "# How tests relate\n"
        "[needs.links.tests]\n"
        'incoming = "is tested by"\n'
        'outgoing = "tests"\n'
    )
    repo = make_repo(tmp_path, {ONE: OLD_ONE}, toml=toml)

    code, _, _ = run(repo, capsys)

    assert code == 0
    result = (repo / "ubproject.toml").read_text(encoding="utf-8")
    result_lines = result.splitlines()
    position = 0
    for line in toml.splitlines():
        assert line in result_lines[position:], f"line lost or moved: {line!r}"
        position = result_lines.index(line, position) + 1
    tests_table = result_lines.index("[needs.links.tests]")
    assert result_lines[tests_table - 1] == "# How tests relate"
    data = tomllib.loads(result)
    assert data["needs"]["id_regex"] == ID_REGEX
    assert [t["directive"] for t in data["needs"]["types"]] == ["requirement", "decision"]
    assert data["needs"]["links"]["tests"] == {"incoming": "is tested by", "outgoing": "tests"}


def test_second_run_changes_nothing(tmp_path, capsys):
    repo = make_repo(tmp_path, {ONE: OLD_ONE, TWO: OLD_TWO})
    run(repo, capsys)
    after_first = snapshot(repo)

    code, out, err = run(repo, capsys)

    assert code == 0
    assert err == ""
    assert sorted(out) == [
        "unchanged: docs/adr/0001-keep-the-log.md",
        "unchanged: docs/adr/0002-split-the-store.md",
    ]
    assert snapshot(repo) == after_first
    assert_id_regex_kept(repo)


def test_partly_converted_log(tmp_path, capsys):
    repo = make_repo(tmp_path, {ONE: NEW_ONE, TWO: OLD_TWO})

    code, out, _ = run(repo, capsys)

    assert code == 0
    assert read_bytes(repo, ONE) == NEW_ONE.encode("utf-8")
    assert read_bytes(repo, TWO) == NEW_TWO.encode("utf-8")
    assert "unchanged: docs/adr/0001-keep-the-log.md" in out
    assert "converted: docs/adr/0002-split-the-store.md" in out
    assert "converted: docs/adr/0001-keep-the-log.md" not in out
    assert "unchanged: docs/adr/0002-split-the-store.md" not in out
    assert_id_regex_kept(repo)


def test_crlf_is_kept(tmp_path, capsys):
    repo = make_repo(tmp_path, {ONE: OLD_ONE.replace("\n", "\r\n")})

    code, _, _ = run(repo, capsys)

    assert code == 0
    result = read_bytes(repo, ONE)
    assert result == NEW_ONE.replace("\n", "\r\n").encode("utf-8")
    assert b"\n" not in result.replace(b"\r\n", b"")
    assert_id_regex_kept(repo)


EM_DASH_HEADING = "# ADR-0002 \N{EM DASH} Old heading\n\n**Status**: Accepted\n**Date**: 2026-11-09\n\n## Context\n\nOld.\n"
UNKNOWN_FIELD = (
    "# ADR-0002: Split the store\n\n**Status**: Accepted\n**Date**: 2026-11-09\n"
    "**Context item**: [X-3](../backlog/x-3.md)\n\n## Context\n\nOld.\n"
)
NO_STATUS = "# ADR-0002: Split the store\n\n**Date**: 2026-11-09\n\n## Context\n\nOld.\n"
DEPRECATED = "# ADR-0002: Split the store\n\n**Status**: Deprecated\n**Date**: 2026-11-09\n\n## Context\n\nOld.\n"
NOT_A_FIELD = "# ADR-0002: Split the store\n\n**Status**: Accepted\nDecided in the weekly.\n\n## Context\n\nOld.\n"
NEED = "# ADR-0002: Split the store\n\n```{decision} Split the store\n:id: ADR-0002\n"
NEED_NOT_CLOSED = NEED + ":status: Accepted\n\n**Status**: Accepted\n\n## Context\n\nOld.\n"
NEED_WITHOUT_STATUS = NEED + "```\n\n**Status**: Accepted\n\n## Context\n\nOld.\n"
NEED_WITHOUT_STATUS_LINE = NEED + ":status: Accepted\n```\n\n**Date**: 2026-11-09\n\n## Context\n\nOld.\n"


@pytest.mark.parametrize(
    "bad",
    [EM_DASH_HEADING, UNKNOWN_FIELD, NO_STATUS, DEPRECATED, NOT_A_FIELD,
     NEED_NOT_CLOSED, NEED_WITHOUT_STATUS, NEED_WITHOUT_STATUS_LINE],
    ids=["em-dash-heading", "unknown-field", "no-status", "status-word-deprecated", "not-a-field-line",
         "need-not-closed", "need-without-status", "need-without-status-line"],
)
def test_refuses_whole_log(tmp_path, capsys, bad):
    repo = make_repo(tmp_path, {ONE: OLD_ONE, TWO: bad, THREE: OLD_THREE})
    before = snapshot(repo)

    code, _, err = run(repo, capsys)

    assert code == 1
    assert "0002" in err
    assert snapshot(repo) == before


@pytest.mark.parametrize(
    "toml",
    [
        TOML + '\n[[needs.types]]\ndirective = "decision"\ntitle = "Decision"\nprefix = "DEC_"\n',
        TOML + '\n[needs.links.constrains]\nincoming = "is limited by"\noutgoing = "restricts"\n',
    ],
    ids=["type-with-other-prefix", "link-with-other-outgoing"],
)
def test_refuses_conflicting_declarations(tmp_path, capsys, toml):
    repo = make_repo(tmp_path, {ONE: OLD_ONE}, toml=toml)
    before = snapshot(repo)

    code, _, err = run(repo, capsys)

    assert code == 1
    assert err != ""
    assert snapshot(repo) == before


def test_refuses_rejecting_id_regex(tmp_path, capsys):
    repo = make_repo(tmp_path, {ONE: OLD_ONE}, toml=f'[needs]\nid_regex = "^REQ_"\n\n{REQ_TYPE}')
    before = snapshot(repo)

    code, _, err = run(repo, capsys)

    assert code == 1
    assert "id_regex" in err
    assert snapshot(repo) == before


@pytest.mark.parametrize(
    "toml",
    [
        f'[project]\nname = "x"\n\n{REQ_TYPE}',
        '[project]\nname = "x"\n\n[needs]\n\n[[needs.types]]\ndirective = "requirement"\ntitle = "Requirement"\nprefix = "REQ-"\n',
    ],
    ids=["types-without-needs-header", "needs-table-without-id-regex"],
)
def test_refuses_missing_id_regex(tmp_path, capsys, toml):
    """Without `id_regex` sphinx-needs uses `^[A-Z0-9_]{5,}`, which rejects `ADR-0001`; the migration never writes one."""
    repo = make_repo(tmp_path, {ONE: OLD_ONE}, toml=toml)
    before = snapshot(repo)

    code, _, err = run(repo, capsys)

    assert code == 1
    assert "id_regex" in err
    assert snapshot(repo) == before


@pytest.mark.parametrize(
    ("toml", "named"),
    [
        (TOML + '\n[needs.links]\nconstrains = "x"\n', "constrains"),
        (f'[needs]\nid_regex = 5\n\n{REQ_TYPE}', "id_regex"),
        (f'[needs]\nid_regex = "["\n\n{REQ_TYPE}', "id_regex"),
        ('needs = 5\n', "needs"),
        (f'[needs]\n{ID_REGEX_LINE}\nlinks = 5\n\n{REQ_TYPE}', "links"),
    ],
    ids=["link-type-is-not-a-table", "id-regex-is-not-a-string", "id-regex-is-not-a-regex",
         "needs-is-not-a-table", "links-is-not-a-table"],
)
def test_refuses_malformed_config(tmp_path, capsys, toml, named):
    repo = make_repo(tmp_path, {ONE: OLD_ONE}, toml=toml)
    before = snapshot(repo)

    code, _, err = run(repo, capsys)  # an exception raised by adr.main fails the test here

    assert code == 1
    assert named in err
    assert "Traceback" not in err
    assert snapshot(repo) == before


def test_refuses_unparsable_toml(tmp_path, capsys):
    repo = make_repo(tmp_path, {ONE: OLD_ONE}, toml='[project\nname = "x"\n')
    before = snapshot(repo)

    code, _, err = run(repo, capsys)

    assert code == 1
    assert "ubproject.toml" in err
    assert snapshot(repo) == before


def test_refuses_without_adr_directory(tmp_path, capsys):
    repo = make_repo(tmp_path, {})
    before = snapshot(repo)

    code, _, err = run(repo, capsys)

    assert code == 1
    assert err != ""
    assert snapshot(repo) == before


def test_accepts_accepting_id_regex_and_leaves_it(tmp_path, capsys):
    toml = f'[needs]\nid_regex = "^[A-Za-z0-9_-]{{6,}}"\n\n{REQ_TYPE}'
    repo = make_repo(tmp_path, {ONE: OLD_ONE}, toml=toml)

    code, _, _ = run(repo, capsys)

    assert code == 0
    assert read_bytes(repo, ONE) == NEW_ONE.encode("utf-8")
    result = (repo / "ubproject.toml").read_text(encoding="utf-8")
    assert 'id_regex = "^[A-Za-z0-9_-]{6,}"' in result.splitlines()
    assert tomllib.loads(result)["needs"]["id_regex"] == "^[A-Za-z0-9_-]{6,}"


def test_switch_off(tmp_path, capsys):
    repo = make_repo(tmp_path, {ONE: OLD_ONE}, toml=None)
    before = snapshot(repo)

    code, _, err = run(repo, capsys)

    assert code == 1
    assert "switch is off" in err.lower()
    assert snapshot(repo) == before
    assert not (repo / "ubproject.toml").exists()


def test_finds_architecture_adr_dir(tmp_path, capsys):
    repo = make_repo(tmp_path, {ONE: OLD_ONE}, adr_dir="docs/architecture/adr")

    code, out, _ = run(repo, capsys)

    assert code == 0
    assert read_bytes(repo, ONE, adr_dir="docs/architecture/adr") == NEW_ONE.encode("utf-8")
    assert "converted: docs/architecture/adr/0001-keep-the-log.md" in out
    assert_id_regex_kept(repo)


def test_refuses_heading_number_that_differs_from_file_name(tmp_path, capsys):
    mismatched = OLD_TWO.replace("# ADR-0002: Split the store", "# ADR-0003: Split the store")
    repo = make_repo(tmp_path, {ONE: OLD_ONE, TWO: mismatched})
    before = snapshot(repo)

    code, _, err = run(repo, capsys)

    assert code == 1
    assert "0002-split-the-store.md" in err
    assert snapshot(repo) == before


def test_refuses_two_adrs_with_the_same_id(tmp_path, capsys):
    first = OLD_ONE
    second = OLD_ONE.replace("Keep the log", "Keep another log")
    repo = make_repo(tmp_path, {"0001-a.md": first, "0001-b.md": second})
    before = snapshot(repo)

    code, _, err = run(repo, capsys)

    assert code == 1
    assert "0001-b.md" in err
    assert "ADR-0001" in err
    assert snapshot(repo) == before


@pytest.mark.parametrize(
    "toml",
    [TOML_NO_TYPES, f"{TOML_NO_TYPES}types = []\n"],
    ids=["no-needs-types", "empty-types-list"],
)
def test_refuses_missing_needs_types(tmp_path, capsys, toml):
    """A `decision` entry would replace sphinx-needs' default types (req, spec, impl, test, need) when the
    repository declares none: the migration refuses and names `needs.types`; it never writes the defaults."""
    repo = make_repo(tmp_path, {ONE: OLD_ONE}, toml=toml)
    before = snapshot(repo)

    code, _, err = run(repo, capsys)

    assert code == 1
    assert "needs.types" in err
    assert "Traceback" not in err
    assert snapshot(repo) == before


def test_accepts_a_repository_that_declares_only_decision(tmp_path, capsys):
    toml = f"{TOML_NO_TYPES}\n{DECISION_TYPE}"
    repo = make_repo(tmp_path, {ONE: OLD_ONE}, toml=toml)

    code, out, _ = run(repo, capsys)

    assert code == 0
    assert read_bytes(repo, ONE) == NEW_ONE.encode("utf-8")
    assert "declared: need type decision" not in out
    data = tomllib.loads((repo / "ubproject.toml").read_text(encoding="utf-8"))
    assert [t["directive"] for t in data["needs"]["types"]] == ["decision"]


def converted(need_word: str, status_line: str) -> str:
    """ADR-0001 in the migrated layout, its need saying *need_word*, its Status line *status_line*."""
    return (
        "# ADR-0001: Keep the log\n"
        "\n"
        "```{decision} Keep the log\n"
        ":id: ADR-0001\n"
        f":status: {need_word}\n"
        "```\n"
        "\n"
        f"**Status**: {status_line}\n"
        "**Date**: 2026-11-08\n"
        "\n"
        "## Context\n"
        "\n"
        "We need to remember why.\n"
    )


SUPERSEDED_BY = "Superseded by [ADR-0002](0002-split-the-store.md)"
RESYNC_ONE = "updated: docs/adr/0001-keep-the-log.md"
UNCHANGED_ONE = "unchanged: docs/adr/0001-keep-the-log.md"


@pytest.mark.parametrize(
    ("need_word", "status_line", "result_word", "updated"),
    [
        ("Accepted", SUPERSEDED_BY, "Superseded", True),
        ("Proposed", "Accepted", "Accepted", True),
        ("Accepted", "Accepted, narrowed by [ADR-0002](0002-split-the-store.md)", "Accepted", False),
    ],
    ids=["superseded", "proposed-to-accepted", "narrowed-stays-accepted"],
)
def test_need_status_follows_the_status_line(tmp_path, capsys, need_word, status_line, result_word, updated):
    repo = make_repo(tmp_path, {ONE: converted(need_word, status_line)}, toml=TOML_DECLARED)

    code, out, err = run(repo, capsys)

    assert code == 0
    assert err == ""
    assert read_bytes(repo, ONE) == converted(result_word, status_line).encode("utf-8")
    assert (repo / "ubproject.toml").read_bytes() == TOML_DECLARED.encode("utf-8")
    assert out == [RESYNC_ONE if updated else UNCHANGED_ONE]
    after_first = snapshot(repo)

    code, out, err = run(repo, capsys)

    assert code == 0
    assert err == ""
    assert out == [UNCHANGED_ONE]
    assert snapshot(repo) == after_first


def test_status_resync_keeps_crlf(tmp_path, capsys):
    stale = converted("Accepted", SUPERSEDED_BY).replace("\n", "\r\n")
    repo = make_repo(tmp_path, {ONE: stale}, toml=TOML_DECLARED)

    code, out, _ = run(repo, capsys)

    assert code == 0
    assert out == [RESYNC_ONE]
    assert read_bytes(repo, ONE) == converted("Superseded", SUPERSEDED_BY).replace("\n", "\r\n").encode("utf-8")


def test_status_resync_next_to_a_conversion(tmp_path, capsys):
    repo = make_repo(tmp_path, {ONE: converted("Accepted", SUPERSEDED_BY), TWO: OLD_TWO}, toml=TOML_DECLARED)

    code, out, _ = run(repo, capsys)

    assert code == 0
    assert sorted(out) == ["converted: docs/adr/0002-split-the-store.md", RESYNC_ONE]
    assert read_bytes(repo, ONE) == converted("Superseded", SUPERSEDED_BY).encode("utf-8")
    assert read_bytes(repo, TWO) == NEW_TWO.encode("utf-8")


def test_refused_log_does_not_resync_either(tmp_path, capsys):
    repo = make_repo(tmp_path, {ONE: converted("Accepted", SUPERSEDED_BY), TWO: NO_STATUS}, toml=TOML_DECLARED)
    before = snapshot(repo)

    code, _, err = run(repo, capsys)

    assert code == 1
    assert "0002" in err
    assert snapshot(repo) == before


def test_runs_as_a_script(tmp_path, monkeypatch):
    repo = make_repo(tmp_path, {ONE: OLD_ONE})
    monkeypatch.setattr(sys, "argv", ["adr.py", "migrate", "--repo", str(repo)])

    with pytest.raises(SystemExit) as done:
        runpy.run_path(adr.__file__, run_name="__main__")

    assert done.value.code == 0
    assert read_bytes(repo, ONE).decode("utf-8").replace("\r\n", "\n") == NEW_ONE
