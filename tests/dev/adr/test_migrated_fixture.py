"""A migrated ADR log is what Sphinx and ubc need (XAS-044b, ADR-0018).

`fixtures/needs-repo` is a small repository with a root `ubproject.toml` and two
ADRs in `design-record`'s template. `fixtures/needs-repo-migrated` is the same
tree as `adr.py migrate` must leave it, written by hand. Two tests tie the
pieces together: the migration yields exactly the golden tree, and the golden
tree builds with `sphinx-build -W`, so a need that sphinx-needs rejects fails
here. `ubc check` runs over the golden tree in CI (`.github/workflows/test.yml`).
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import adr

FIXTURES = Path(__file__).resolve().parent / "fixtures"
INPUT = FIXTURES / "needs-repo"
GOLDEN = FIXTURES / "needs-repo-migrated"


def snapshot(root: Path) -> dict[str, bytes]:
    """Every file under *root* with its exact bytes."""
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def test_migration_yields_golden(tmp_path):
    repo = tmp_path / "repo"
    shutil.copytree(INPUT, repo)

    code = adr.main(["migrate", "--repo", str(repo)])

    assert code == 0
    assert snapshot(repo) == snapshot(GOLDEN)


def test_golden_builds_with_sphinx_W(tmp_path):
    source = tmp_path / "source"
    shutil.copytree(GOLDEN, source)

    result = subprocess.run(
        [sys.executable, "-m", "sphinx", "-W", "--keep-going", "-b", "html",
         "-d", str(tmp_path / "doctrees"), str(source), str(tmp_path / "html")],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )

    assert result.returncode == 0, result.stdout + result.stderr
