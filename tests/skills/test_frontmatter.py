"""The frontmatter of every `SKILL.md` in the repository, checked mechanically (XAS-057).

Claude Code ignores a frontmatter key it does not know, without a word: a typo
such as `user_invocable` for `user-invocable` silently does nothing. These tests
catch that, and the limits of the Agent Skills spec, before a skill ships.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from skill_frontmatter import KNOWN_KEYS, load, problems

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_FILES = sorted(REPO_ROOT.glob("plugins/*/skills/*/SKILL.md"))


def skill(**fields: str) -> str:
    lines = [f"{k}: {v}" for k, v in fields.items()]
    return "---\n" + "\n".join(lines) + "\n---\n\n# Body\n"


def test_a_minimal_skill_has_no_problems():
    assert problems(skill(name="my-skill", description="Does a thing.")) == []


def test_every_key_claude_code_knows_is_accepted():
    fields = {k: "x" for k in KNOWN_KEYS}
    fields.update(name="my-skill", description="Does a thing.")
    assert problems(skill(**fields)) == []


def test_an_unknown_key_is_named():
    assert problems(skill(name="my-skill", description="Does a thing.", user_invocable="true")) == [
        "unknown frontmatter key 'user_invocable'"
    ]


def test_a_missing_name_and_description_are_named():
    assert problems(skill(license="MIT")) == ["no 'name'", "no 'description'"]


@pytest.mark.parametrize("name", ["My-Skill", "my_skill", "-skill", "skill-", "my--skill", "a" * 65])
def test_a_name_that_is_not_short_kebab_case_is_named(name):
    assert [p for p in problems(skill(name=name, description="Does a thing.")) if "name" in p]


def test_a_description_longer_than_1024_characters_is_named():
    assert problems(skill(name="my-skill", description="x" * 1025)) == [
        "description has 1025 characters; at most 1024"
    ]
    assert problems(skill(name="my-skill", description="x" * 1024)) == []


def test_a_description_with_angle_brackets_is_named():
    assert problems(skill(name="my-skill", description='"Takes a <path>."')) == [
        "description contains '<' or '>'"
    ]


def test_a_file_without_frontmatter_is_named():
    assert problems("# Just a body\n") == ["no frontmatter between '---' lines at the top"]


def test_frontmatter_that_is_not_yaml_is_named():
    assert problems("---\nname: [unclosed\n---\n")[0].startswith("frontmatter is not YAML")


def test_crlf_line_endings_are_read():
    assert problems(skill(name="my-skill", description="Does a thing.").replace("\n", "\r\n")) == []


def test_the_repository_has_skills():
    assert len(SKILL_FILES) >= 10


@pytest.mark.parametrize("path", SKILL_FILES, ids=lambda p: f"{p.parts[-4]}/{p.parts[-2]}")
def test_every_skill_in_the_repository_passes(path):
    assert problems(path.read_text(encoding="utf-8")) == []
    assert path.parent.name == load(path.read_text(encoding="utf-8"))["name"]
