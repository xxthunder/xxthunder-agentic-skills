"""The patch target comes from codecov.yml, and eval session code is not measured."""
from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
import yaml

import evals
from evals import gate

REPO_ROOT = Path(evals.__file__).parent.parent


def test_the_repository_patch_target_is_90():
    assert gate.patch_target(REPO_ROOT) == 90.0


def test_patch_target_reads_a_percent_string(tmp_path):
    (tmp_path / "codecov.yml").write_text("coverage:\n  status:\n    patch:\n      default:\n        target: 87.5%\n")
    assert gate.patch_target(tmp_path) == 87.5


def test_patch_target_without_the_key_names_it(tmp_path):
    (tmp_path / "codecov.yml").write_text("coverage: {}\n")
    with pytest.raises(ValueError, match=r"codecov\.yml.*coverage\.status\.patch\.default\.target"):
        gate.patch_target(tmp_path)


def test_patch_target_without_the_file_names_it(tmp_path):
    with pytest.raises(ValueError, match=r"codecov\.yml"):
        gate.patch_target(tmp_path)


def test_project_rule_follows_the_base_with_one_percent():
    project = yaml.safe_load((REPO_ROOT / "codecov.yml").read_text())["coverage"]["status"]["project"]["default"]
    assert project == {"target": "auto", "threshold": "1%"}


def test_eval_session_code_is_not_measured():
    omit = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())["tool"]["coverage"]["run"]["omit"]
    assert sorted(omit) == ["evals/cases.py", "evals/fixture.py"]
