"""uv run --group dev python -m evals run --ref <git-ref> [--runs N] [--case NAME]... [--skill NAME]... [-j N]
uv run --group dev python -m evals report --ref <git-ref>
uv run --group dev python -m evals list
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import evals
from evals.cases import CASES
from evals.fingerprint import fingerprint, shared
from evals.runner import PLUGIN, config_dir, dependency_dirs, export_plugin, remove_tree, report, run_one

REPO_ROOT = Path(__file__).resolve().parents[1]


def results_dir(ref: str, base: str | None, repo: Path = REPO_ROOT) -> Path:
    """`<root>/<tree hash of the plugin at ref>`: a result counts for one plugin version, across rebases."""
    r = subprocess.run(["git", "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],
                       cwd=repo, capture_output=True, text=True)
    if r.returncode:
        raise ValueError(f"unknown ref: {ref}")
    tree = subprocess.run(["git", "rev-parse", "--verify", "--quiet", f"{r.stdout.strip()}:{PLUGIN}"],
                          cwd=repo, capture_output=True, text=True)
    if tree.returncode:
        raise ValueError(f"no {PLUGIN} at {ref}")
    # Outside the checkout: a session under it would load this repo's CLAUDE.md.
    root = Path(base) if base else Path(tempfile.gettempdir()) / "xxthunder-evals"
    return root / tree.stdout.strip()


def tracked(repo: Path = REPO_ROOT) -> list[str]:
    """Files git tracks under `evals/`, relative to it: what the gate's `git archive` holds too."""
    out = subprocess.run(["git", "ls-files", "-z", "--", "evals"], cwd=repo, capture_output=True, check=True).stdout
    files = [f.removeprefix("evals/") for f in out.decode("utf-8").split("\0") if f]
    return [f for f in files if (repo / "evals" / f).is_file()]  # a tracked file deleted in the working tree is gone


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m evals", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["run", "report", "list"])
    ap.add_argument("--ref", default="HEAD", help="git ref whose plugin is evaluated (default HEAD)")
    ap.add_argument("--runs", type=int, default=3, help="runs per case (default 3)")
    ap.add_argument("--case", action="append", help="only this case; repeatable")
    ap.add_argument("--skill", action="append", help="every case of this skill; repeatable, adds to --case")
    ap.add_argument("-j", "--jobs", type=int, default=4, help="parallel runs (default 4)")
    ap.add_argument("--out", help="results root (default <tmp>/xxthunder-evals)")
    a = ap.parse_args(argv)

    if a.cmd == "list":
        for c in CASES:
            print(f"{c.name:34} {c.skill or '-':18} {c.prompt}")
        return 0
    try:
        out = results_dir(a.ref, a.out, REPO_ROOT)
    except ValueError as e:
        ap.error(str(e))
    if a.cmd == "run":
        unknown = set(a.case or []) - {c.name for c in CASES}
        if unknown:
            ap.error(f"unknown case: {', '.join(sorted(unknown))}")
        unknown = set(a.skill or []) - {c.skill for c in CASES}
        if unknown:
            ap.error(f"unknown skill: {', '.join(sorted(unknown))}")
        if shutil.which("claude") is None:
            ap.error("`claude` is not on PATH")
        chosen = bool(a.case or a.skill)
        cases = [c for c in CASES if not chosen or c.name in (a.case or []) or c.skill in (a.skill or [])]
        for c in cases:
            own_run = re.compile(rf"{re.escape(c.name)}-\d+")  # not `logbook-started-again-1` for `logbook-started`
            for old in out.glob(f"{c.name}-*"):
                if own_run.fullmatch(old.name):
                    remove_tree(old)
        plugin = export_plugin(REPO_ROOT, a.ref, out / "plugin")
        dirs = dependency_dirs(plugin, config_dir(dict(os.environ))) + [plugin]
        shared_hash = shared(Path(evals.__file__).parent, CASES, tracked(REPO_ROOT))
        jobs = [(c, n) for c in cases for n in range(1, a.runs + 1)]
        print(f"{len(jobs)} runs of {a.ref} → {out}", flush=True)

        def one(job):
            r = run_one(job[0], dirs, job[1], out, fingerprint(job[0], shared_hash))
            print(("PASS " if r["pass"] else "FAIL ") + f"{r['case']}#{r['run']}", flush=True)

        with ThreadPoolExecutor(a.jobs) as ex:
            list(ex.map(one, jobs))
    print("\n".join(report(out)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
