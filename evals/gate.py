"""uv run --group dev python -m evals.gate [--head REF] [--out DIR] [--pre-push]

Runs pytest, then checks that every case a change asks for has its eval results:
3 of 3 green at the pushed commit, and for a new or changed case of a touched
skill at least one failing run at the base commit. It never runs an eval.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

from evals.__main__ import REPO_ROOT, results_dir
from evals.runner import PLUGIN

BASE = "origin/develop"
FINGERPRINT = Path(__file__).with_name("fingerprint.py")
SCRIPT = """\
import json, sys
from pathlib import Path
from evals.cases import CASES
from evals.fingerprint import fingerprint, own, shared
h = shared(Path(sys.argv[1]), CASES)
print(json.dumps({c.name: [getattr(c, "skill", None), own(c), fingerprint(c, h)] for c in CASES}))
"""


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True)


def changed_paths(repo: Path, base: str, head: str) -> list[str]:
    # No rename detection: a moved file touches the skill it leaves too. `-z` leaves non-ASCII names unquoted.
    out = git(repo, "diff", "--name-only", "--no-renames", "-z", base, head).stdout.decode("utf-8")
    return [p for p in out.split("\0") if p]


def touched_skills(paths: list[str]) -> set[str]:
    """Skill folders of the covered plugin that *paths* fall into."""
    prefix = f"{PLUGIN}/skills/"
    return {p[len(prefix):].split("/", 1)[0] for p in paths if p.startswith(prefix) and "/" in p[len(prefix):]}


def case_table(repo: Path, sha: str) -> dict[str, tuple[str | None, str, str]]:
    """name → (skill, own, full fingerprint) of the cases as they are at *sha*."""
    if not git(repo, "ls-tree", "-d", sha, "evals").stdout.strip():
        return {}
    archive = git(repo, "archive", "--format=tar", sha, "evals")
    archive.check_returncode()
    with tempfile.TemporaryDirectory() as tmp:
        with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tar:
            tar.extractall(tmp, filter="data")
        # The current helper reads an older `Case` too; the archived one may be missing.
        shutil.copyfile(FINGERPRINT, Path(tmp) / "evals" / "fingerprint.py")
        r = subprocess.run([sys.executable, "-c", f"import sys; sys.path.insert(0, {tmp!r})\n" + SCRIPT,
                            str(Path(tmp) / "evals")],
                           cwd=tmp, capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        raise RuntimeError(f"cannot load the cases at {sha}:\n{r.stderr}")
    return {name: (skill, own, full) for name, (skill, own, full) in json.loads(r.stdout).items()}


def runs(out: Path, case: str) -> list[dict]:
    """Each `result.json` of *case* in *out*, whatever version of the case it belongs to."""
    found = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(out.glob(f"{case}-*/result.json"))]
    # `logbook-started-*` also matches `logbook-started-again-1`, so the name inside decides.
    return [r for r in found if r.get("case") == case]


def results(out: Path, case: str, fp: str) -> list[bool]:
    """`pass` of each run of *case* in *out* that belongs to the version *fp*."""
    return [r["pass"] for r in runs(out, case) if r.get("fingerprint") == fp]


def counts(out: Path, case: str, passes: list[bool]) -> str:
    stale = not passes and runs(out, case)
    return f"{case} {sum(passes)}/{len(passes)}" + (
        " (results exist but none match the current version of the case)" if stale else "")


def command(sha: str, out_root: str | None, names: list[str], runs: int | None = None) -> str:
    args = ["uv run --group dev python -m evals run", f"--ref {sha}"]
    args += [f"--out {out_root}"] if out_root else []
    args += [f"--runs {runs}"] if runs else []
    return "  " + " ".join(args + [f"--case {n}" for n in names])


def check(repo: Path, head: str, out_root: str | None = None) -> list[str]:
    """Problem lines for pushing *head*; empty means green."""
    r = git(repo, "rev-parse", "--verify", "--quiet", f"{head}^{{commit}}")
    if r.returncode:
        return [f"unknown ref: {head}"]
    head_sha = r.stdout.decode().strip()
    r = git(repo, "merge-base", BASE, head_sha)
    if r.returncode:
        return [f"no merge base with {BASE}: run `git fetch origin develop` (and `git fetch --unshallow` in a shallow clone)"]
    base_sha = r.stdout.decode().strip()

    touched = touched_skills(changed_paths(repo, base_sha, head_sha))
    # A skill deleted on the branch asks for nothing.
    touched = {s for s in touched if git(repo, "ls-tree", "-d", head_sha, f"{PLUGIN}/skills/{s}").stdout.strip()}
    now, then = case_table(repo, head_sha), case_table(repo, base_sha)
    problems = [f"skill {s} has no eval case" for s in sorted(touched - {skill for skill, _, _ in now.values()})]

    required = [n for n, (skill, _, full) in now.items() if skill in touched or n not in then or then[n][2] != full]
    if not required:
        return problems
    try:
        head_out, base_out = results_dir(head_sha, out_root, repo), results_dir(base_sha, out_root, repo)
    except ValueError as e:  # a commit without the plugin has no results dir
        return problems + [str(e)]

    green = {n: results(head_out, n, now[n][2]) for n in required}
    missing = [n for n in required if len(green[n]) < 3 or not all(green[n])]
    if missing:
        problems.append(f"no green 3 of 3 at {head_sha} for: " + ", ".join(counts(head_out, n, green[n]) for n in missing))
        problems.append(command(head_sha, out_root, missing))

    # Base runs come from this branch's cases against the base plugin, so they carry the head fingerprint.
    red = {n: results(base_out, n, now[n][2]) for n in required
           if now[n][0] in touched and (n not in then or then[n][1] != now[n][1])}
    no_red = [n for n, passes in red.items() if all(passes)]
    if no_red:
        problems.append(f"no failing run at the base {base_sha} for new or changed cases: "
                        + ", ".join(counts(base_out, n, red[n]) for n in no_red))
        problems.append(command(base_sha, out_root, no_red, runs=1))
    return problems


def tests_pass() -> bool:
    # No stdin: it holds the pre-push hook's ref lines, which the gate reads after pytest.
    # No GIT_* variables: git exports GIT_DIR to hooks, absolute from a worktree, and the tests'
    # own git calls would then act on the pushing repository instead of their tmp_path ones (XAS-079).
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=REPO_ROOT, stdin=subprocess.DEVNULL,
                          env=env).returncode == 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m evals.gate", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--head", default="HEAD", help="commit to check (default HEAD)")
    ap.add_argument("--out", help="results root (default <tmp>/xxthunder-evals)")
    ap.add_argument("--pre-push", action="store_true", help="check each pushed commit read from stdin, as git's pre-push hook passes them")
    a = ap.parse_args(argv)

    problems = [] if tests_pass() else ["pytest is red"]
    if a.pre_push:
        # Each line: <local ref> <local sha> <remote ref> <remote sha>; an all-zero local SHA deletes a branch.
        heads = [f[1] for f in (line.split() for line in sys.stdin) if len(f) == 4 and f[1].strip("0")]
    else:
        heads = [a.head]
    for head in heads:
        problems += check(REPO_ROOT, head, a.out)
    print("\n".join(problems + ["gate: red" if problems else "gate: green"]))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
