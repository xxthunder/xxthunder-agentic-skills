"""The patch target comes from codecov.yml, and eval session code is not measured."""
from __future__ import annotations

import os
import subprocess
import sys
import xml.etree.ElementTree as ET
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


_CHILD = """
import sys
import coverage

cov = coverage.Coverage(config_file=sys.argv[3], data_file=sys.argv[1])
cov.start()
import evals.cases, evals.fixture, evals.gate  # noqa: F401, E401
cov.stop()
cov.xml_report(outfile=sys.argv[2])
"""


def test_eval_session_code_is_not_measured(tmp_path):
    xml_path = tmp_path / "c.xml"
    env = {k: v for k, v in os.environ.items() if k != "COVERAGE_PROCESS_START"}
    env["PYTHONPATH"] = str(REPO_ROOT)
    # Run from outside the repository: the tests run scripts from sandbox directories, and a
    # relative omit pattern must still match there (XAS-026f).
    subprocess.run(
        [sys.executable, "-c", _CHILD, str(tmp_path / ".coverage"), str(xml_path), str(REPO_ROOT / "pyproject.toml")],
        cwd=tmp_path, env=env, check=True, capture_output=True, text=True,
    )
    root = ET.parse(xml_path).getroot()
    listed = {Path(c.get("filename")).name for c in root.iter("class")}
    assert "gate.py" in listed
    assert "cases.py" not in listed
    assert "fixture.py" not in listed
