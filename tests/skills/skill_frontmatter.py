"""Check the frontmatter of a `SKILL.md` against what Claude Code reads (XAS-057)."""
from __future__ import annotations

import re

import yaml

# The keys Claude Code 2.1.312 reads from a skill's frontmatter, plus `license`,
# `metadata` and `compatibility` from the Agent Skills spec. Claude Code ignores
# any other key without a word.
KNOWN_KEYS = frozenset({
    "name", "description", "when_to_use", "argument-hint", "allowed-tools", "model", "effort",
    "disable-model-invocation", "user-invocable", "shell", "paths", "hooks", "context", "agent",
    "version", "license", "metadata", "compatibility",
})
NAME_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---(?:\n|\Z)", re.S)
MAX_NAME = 64
MAX_DESCRIPTION = 1024


class FrontmatterError(Exception):
    pass


def load(text: str) -> dict:
    """The frontmatter of *text* as a mapping."""
    m = FRONTMATTER_RE.match(text.replace("\r\n", "\n"))
    if m is None:
        raise FrontmatterError("no frontmatter between '---' lines at the top")
    try:
        data = yaml.safe_load(m.group(1))
    except yaml.YAMLError as e:
        raise FrontmatterError(f"frontmatter is not YAML: {e}".splitlines()[0]) from None
    if not isinstance(data, dict):
        raise FrontmatterError("frontmatter is not a mapping")
    return data


def problems(text: str) -> list[str]:
    """Every problem with the frontmatter of *text*, one line each; empty when clean."""
    try:
        data = load(text)
    except FrontmatterError as e:
        return [str(e)]
    out = [f"unknown frontmatter key {k!r}" for k in data if k not in KNOWN_KEYS]
    name, description = data.get("name"), data.get("description")
    if name is None:
        out.append("no 'name'")
    elif not isinstance(name, str) or not NAME_RE.fullmatch(name) or len(name) > MAX_NAME:
        out.append(f"name {name!r} is not kebab-case of at most {MAX_NAME} characters")
    if description is None:
        out.append("no 'description'")
    elif not isinstance(description, str):
        out.append("description is not a string")
    else:
        if len(description) > MAX_DESCRIPTION:
            out.append(f"description has {len(description)} characters; at most {MAX_DESCRIPTION}")
        if "<" in description or ">" in description:
            out.append("description contains '<' or '>'")
    return out
