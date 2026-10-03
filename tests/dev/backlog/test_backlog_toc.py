"""This repository's backlog at `docs/backlog/` passes the backlog script's check.

The item files are the truth and the README's table of contents is derived
from them (ADR-0009). The checks live in `scripts/backlog.py`, where
`tests/dev/scripts/test_backlog.py` proves each of them fires on a broken
fixture. This module only runs them against the real backlog.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import backlog

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKLOG = REPO_ROOT / "docs" / "backlog"

pytestmark = pytest.mark.skipif(
    not BACKLOG.is_dir(), reason="no docs/backlog/ in this repository"
)


def test_real_backlog_passes_check():
    assert backlog.check(BACKLOG) == []


def test_real_backlog_is_not_empty():
    """Guard against the check passing vacuously."""
    assert backlog.item_files(BACKLOG), "no items found; the check would pass vacuously"
