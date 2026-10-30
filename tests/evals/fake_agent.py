"""A stand-in for `claude -p`: prints a stream-json transcript and acts on the prompt.

    report  narrate, call a skill and run `git status`, answer with what the session sees
    pull    move DEMO-007 to In Progress in the working tree, answer "Pulled DEMO-007."
    sleep   narrate, then hang until the runner gives up
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path


def emit(event: dict) -> None:
    print(json.dumps(event), flush=True)


def say(text: str) -> None:
    emit({"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}})


def main() -> None:
    prompt = sys.argv[1]
    say("Now the board check.")
    if prompt == "sleep":
        time.sleep(60)
    if prompt == "pull":
        item = Path("docs/backlog/demo-007.md")
        item.write_text(re.sub(r"(?m)^\*\*Status\*\*: .*$", "**Status**: In Progress",
                               item.read_text(encoding="utf-8")), encoding="utf-8")
        answer = "Pulled DEMO-007."
    else:
        emit({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Skill", "input": {"skill": "xxthunder-dev-skills:next"}},
            {"type": "tool_use", "name": "Bash", "input": {"command": "git status"}}]}})
        answer = json.dumps({"cwd": os.getcwd(),
                             **{k: os.environ.get(k) for k in ("BOARD_PATH", "LOGBOOK_PATH", "CLAUDECODE")}})
    print("a warning on stderr", file=sys.stderr)
    emit({"type": "result", "subtype": "success", "result": answer})


if __name__ == "__main__":
    main()
