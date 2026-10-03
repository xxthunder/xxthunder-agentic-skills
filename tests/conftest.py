"""Pytest harness for plugin helper scripts.

Each plugin's `scripts/` directory is prepended to `sys.path` so tests can
`import read_config`, `import merge`, etc. directly. Scripts remain PEP 723
inline-metadata files invokable via `uv run`; this harness only borrows
their importable top-level functions.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PAPERLESS_SKILLS = REPO_ROOT / "plugins" / "xxthunder-paperless-skills" / "skills"
DEV_SCRIPTS = REPO_ROOT / "plugins" / "xxthunder-dev-skills" / "scripts"

for skill_dir in sorted(PAPERLESS_SKILLS.iterdir()):
    scripts_dir = skill_dir / "scripts"
    if scripts_dir.is_dir():
        sys.path.insert(0, str(scripts_dir))

sys.path.insert(0, str(DEV_SCRIPTS))


@pytest.fixture
def make_pdf(tmp_path):
    """Return a factory: `make_pdf(name, pages)` where `pages` is a list of str.

    Produces a real, text-bearing PDF on disk via reportlab (one page per
    string). Use for any test that exercises OCR/text extraction paths.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    def _make(name: str, pages: list[str]) -> Path:
        path = tmp_path / name
        c = canvas.Canvas(str(path), pagesize=A4)
        for text in pages:
            c.drawString(72, 800, text)
            c.showPage()
        c.save()
        return path

    return _make
