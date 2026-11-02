"""Which version of a case a result belongs to.

Stdlib only and no import from `evals` at module level: the gate copies this file
beside an older `evals/` package, whose `Case` may lack newer fields.
"""
from __future__ import annotations

import ast
import dataclasses
import hashlib
import inspect
from pathlib import Path

FIELDS = ("name", "prompt", "board", "logbook", "board_contract", "learnings")  # for a case that is no dataclass
BY_SOURCE = {"skill", "check", "setup"}  # not by value: the skill names no version, check and setup enter by source
TOOLING = {"__main__.py", "fingerprint.py", "gate.py"}  # top-level files no case imports: changing them changes no result


def digest(*parts: bytes) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(len(p).to_bytes(8, "big") + p)  # length-prefixed, so parts cannot run together
    return h.hexdigest()


def own(case) -> str:
    """Hash of what only this case holds: prompt, flags, and the source of its check and setup."""
    setup = getattr(case, "setup", None)
    # a dataclass field outside FIELDS enters only off its default: a new flag leaves old cases' hashes alone
    names = ([f.name for f in dataclasses.fields(case) if f.name not in BY_SOURCE
              and (f.name in FIELDS or f.default is dataclasses.MISSING or getattr(case, f.name) != f.default)]
             if dataclasses.is_dataclass(case) else FIELDS)
    values = [repr(getattr(case, f, None)) for f in names]
    values += [inspect.getsource(case.check), inspect.getsource(setup) if setup else ""]
    return digest(*(v.encode("utf-8") for v in values))


def stripped_cases(source: str, cases) -> str:
    """`cases.py` without the cases' own check and setup functions and the `CASES` table."""
    own_names = {f.__name__ for c in cases for f in (c.check, getattr(c, "setup", None)) if f}
    tree = ast.parse(source)
    tree.body = [n for n in tree.body
                 if not (isinstance(n, ast.FunctionDef) and n.name in own_names)
                 and not (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "CASES" for t in n.targets))]
    return ast.unparse(tree)


def shared(root: Path, cases, files: list[str] | None = None) -> str:
    """Hash of everything under *root* (the `evals/` folder) that every case depends on.

    *files*, `/`-separated and relative to *root*, limits it to those files: the ones git tracks.
    """
    if files is None:
        files = [p.relative_to(root).as_posix() for p in root.rglob("*")
                 if p.is_file() and "__pycache__" not in p.relative_to(root).parts]
    parts = []
    for rel in sorted(files):
        if rel in TOOLING:
            continue
        data = (root / rel).read_bytes().replace(b"\r\n", b"\n")  # a CRLF checkout (core.autocrlf) hashes like its LF archive
        if rel == "cases.py":
            data = stripped_cases(data.decode("utf-8"), cases).encode("utf-8")
        parts += [rel.encode("utf-8"), data]
    return digest(*parts)


def fingerprint(case, shared_hash: str) -> str:
    return hashlib.sha256((own(case) + shared_hash).encode("utf-8")).hexdigest()
