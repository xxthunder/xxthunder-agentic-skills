"""The fake Jira the evals load: a script that answers from a JSON file."""
from __future__ import annotations

import json
import subprocess
import sys

from evals.fixture import JIRA_ISSUES, JIRA_PLUGIN

SCRIPT = JIRA_PLUGIN / "scripts" / "jira_issue.py"


def get(key: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), "get", key], capture_output=True, text=True, encoding="utf-8")


def test_get_prints_the_issue():
    r = get("OPS-041")
    assert r.returncode == 0
    assert json.loads(r.stdout) == {"key": "OPS-041", "summary": "Rotate the build agents' certificates", "status": "Done"}


def test_get_of_an_unknown_key_fails():
    r = get("OPS-999")
    assert r.returncode == 1
    assert "issue OPS-999 does not exist" in r.stderr


def test_issues_json_matches_jira_issues():
    data = json.loads((JIRA_PLUGIN / "scripts" / "issues.json").read_text(encoding="utf-8"))
    assert {k: (v["summary"], v["status"]) for k, v in data.items()} == JIRA_ISSUES
