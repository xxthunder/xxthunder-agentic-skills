"""uv run --group dev python -m evals run --ref <git-ref> [--runs N] [--case NAME]... [-j N]
uv run --group dev python -m evals report --ref <git-ref>
uv run --group dev python -m evals list
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from evals.cases import CASES
from evals.runner import config_dir, dependency_dirs, export_plugin, report, run_one

REPO_ROOT = Path(__file__).resolve().parents[1]


def results_dir(ref: str, base: str | None) -> Path:
    # Outside the checkout: a session under it would load this repo's CLAUDE.md.
    root = Path(base) if base else Path(tempfile.gettempdir()) / "xxthunder-evals"
    return root / re.sub(r"[^A-Za-z0-9._-]", "_", ref)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m evals", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["run", "report", "list"])
    ap.add_argument("--ref", default="HEAD", help="git ref whose plugin is evaluated (default HEAD)")
    ap.add_argument("--runs", type=int, default=3, help="runs per case (default 3)")
    ap.add_argument("--case", action="append", help="only this case; repeatable")
    ap.add_argument("-j", "--jobs", type=int, default=4, help="parallel runs (default 4)")
    ap.add_argument("--out", help="results root (default <tmp>/xxthunder-evals)")
    a = ap.parse_args(argv)

    if a.cmd == "list":
        for c in CASES:
            print(f"{c.name:24} {c.prompt}")
        return 0
    out = results_dir(a.ref, a.out)
    if a.cmd == "run":
        unknown = set(a.case or []) - {c.name for c in CASES}
        if unknown:
            ap.error(f"unknown case: {', '.join(sorted(unknown))}")
        if shutil.which("claude") is None:
            ap.error("`claude` is not on PATH")
        cases = [c for c in CASES if not a.case or c.name in a.case]
        for c in cases:
            for old in out.glob(f"{c.name}-*"):
                shutil.rmtree(old)
        plugin = export_plugin(REPO_ROOT, a.ref, out / "plugin")
        dirs = dependency_dirs(plugin, config_dir(dict(os.environ))) + [plugin]
        jobs = [(c, n) for c in cases for n in range(1, a.runs + 1)]
        print(f"{len(jobs)} runs of {a.ref} → {out}", flush=True)

        def one(job):
            r = run_one(job[0], dirs, job[1], out)
            print(("PASS " if r["pass"] else "FAIL ") + f"{r['case']}#{r['run']}", flush=True)

        with ThreadPoolExecutor(a.jobs) as ex:
            list(ex.map(one, jobs))
    print("\n".join(report(out)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
