# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""A fake Jira for the evals: `get <KEY>` answers from issues.json next to this file."""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[0] != "get":
        print("usage: jira_issue.py get <KEY>", file=sys.stderr)
        return 2
    key = argv[1]
    issues = json.loads((Path(__file__).resolve().parent / "issues.json").read_text(encoding="utf-8"))
    if key not in issues:
        print(f"issue {key} does not exist", file=sys.stderr)
        return 1
    print(json.dumps({"key": key, **issues[key]}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
