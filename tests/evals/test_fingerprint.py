"""The fingerprint says which version of a case a result belongs to."""
from __future__ import annotations

import shutil
from dataclasses import dataclass, fields, replace
from pathlib import Path

import evals
from evals.cases import CASES, Case
from evals.fingerprint import fingerprint, own, shared

EVALS = Path(evals.__file__).parent


def case_with(check) -> Case:
    return Case("fake", "logbook", "prompt", check)


def check_a(s):
    return []


def check_b(s):
    return ["b"]


def test_own_changes_with_the_prompt():
    c = case_with(check_a)
    assert own(c) != own(replace(c, prompt="other"))


def test_own_changes_with_the_source_of_the_check():
    assert own(case_with(check_a)) != own(case_with(check_b))


def test_own_ignores_the_skill():
    c = case_with(check_a)
    assert own(c) == own(replace(c, skill="x"))


def setup_a(path):
    pass


def setup_b(path):
    path.mkdir()


def changed(value):
    """Another value of the same kind: a flag flipped, a text extended, another function."""
    if isinstance(value, bool):
        return not value
    if isinstance(value, str):
        return value + " again"
    return {check_a: check_b, setup_a: setup_b}[value]


def test_every_field_but_the_skill_changes_own():
    c = replace(case_with(check_a), setup=setup_a)
    for f in fields(Case):
        if f.name != "skill":
            assert own(c) != own(replace(c, **{f.name: changed(getattr(c, f.name))})), f.name


def test_own_reads_a_field_case_gains_later():
    @dataclass(frozen=True)
    class Wider(Case):
        extra: bool = False

    c = Wider("fake", "logbook", "prompt", check_a)
    assert own(c) != own(replace(c, extra=True))


def test_own_reads_flags_an_older_case_may_lack():
    class Old:
        name, prompt, board = "old", "p", True
        check = staticmethod(check_a)

    assert len(own(Old())) == 64


def test_fingerprint_combines_own_and_shared():
    c = case_with(check_a)
    assert fingerprint(c, "x") != fingerprint(c, "y")
    assert fingerprint(c, "x") == fingerprint(c, "x")


def copy_evals(tmp_path: Path) -> Path:
    dest = tmp_path / "evals"
    shutil.copytree(EVALS, dest, ignore=shutil.ignore_patterns("__pycache__"))
    return dest


def test_shared_changes_when_a_helper_changes(tmp_path):
    root = copy_evals(tmp_path)
    before = shared(root, CASES)
    cases = root / "cases.py"
    cases.write_text(cases.read_text(encoding="utf-8").replace("def expect(", "def expect_(", 1), encoding="utf-8")
    assert shared(root, CASES) != before


def test_shared_ignores_the_body_of_a_check(tmp_path):
    root = copy_evals(tmp_path)
    before = shared(root, CASES)
    name = CASES[0].check.__name__
    cases = root / "cases.py"
    cases.write_text(cases.read_text(encoding="utf-8").replace(f"def {name}(s: State) -> list[str]:\n",
                                                                 f"def {name}(s: State) -> list[str]:\n    s = s\n", 1),
                     encoding="utf-8")
    assert f"    s = s\n" in cases.read_text(encoding="utf-8")
    assert shared(root, CASES) == before


def test_shared_ignores_pycache(tmp_path):
    root = copy_evals(tmp_path)
    before = shared(root, CASES)
    (root / "__pycache__").mkdir()
    (root / "__pycache__" / "x.pyc").write_bytes(b"junk")
    assert shared(root, CASES) == before


def test_shared_changes_when_another_file_changes(tmp_path):
    root = copy_evals(tmp_path)
    before = shared(root, CASES)
    (root / "runner.py").write_text("# changed\n", encoding="utf-8")
    assert shared(root, CASES) != before


def test_shared_ignores_line_endings(tmp_path):
    root = copy_evals(tmp_path)
    names = ("cases.py", "runner.py")
    lf = {n: (root / n).read_bytes().replace(b"\r\n", b"\n") for n in names}  # a Windows checkout may be CRLF already
    for n in names:
        (root / n).write_bytes(lf[n])
    before = shared(root, CASES)
    for n in names:
        (root / n).write_bytes(lf[n].replace(b"\n", b"\r\n"))
    assert shared(root, CASES) == before


def test_shared_reads_pycache_only_inside_root(tmp_path):
    root = copy_evals(tmp_path / "__pycache__")
    assert shared(root, CASES) == shared(copy_evals(tmp_path / "plain"), CASES)


def test_shared_ignores_the_tooling_around_the_cases(tmp_path):
    root = copy_evals(tmp_path)
    before = shared(root, CASES)
    for name in ("gate.py", "__main__.py", "fingerprint.py"):
        with (root / name).open("a", encoding="utf-8") as f:
            f.write("# changed\n")
        assert shared(root, CASES) == before, name
    with (root / "runner.py").open("a", encoding="utf-8") as f:
        f.write("# changed\n")
    assert shared(root, CASES) != before


def test_shared_reads_only_the_listed_files(tmp_path):
    root = copy_evals(tmp_path)
    listed = [p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()]
    before = shared(root, CASES, listed)
    assert before == shared(root, CASES)
    (root / "notes.txt").write_text("a stray file\n", encoding="utf-8")
    assert shared(root, CASES, listed) == before
    assert shared(root, CASES) != before


def test_a_field_added_with_its_default_leaves_own_unchanged():
    @dataclass
    class Old:
        name: str
        prompt: str
        check: object

    @dataclass
    class New:
        name: str
        prompt: str
        check: object
        jira: bool = False

    assert own(Old("n", "p", check_a)) == own(New("n", "p", check_a))


def test_a_field_set_off_its_default_changes_own():
    @dataclass
    class New:
        name: str
        prompt: str
        check: object
        jira: bool = False

    assert own(New("n", "p", check_a)) != own(New("n", "p", check_a, jira=True))


def test_a_fields_field_at_its_default_still_enters_own():
    @dataclass
    class Old:
        name: str
        prompt: str
        check: object

    @dataclass
    class New:
        name: str
        prompt: str
        check: object
        board: bool = True

    assert own(Old("n", "p", check_a)) != own(New("n", "p", check_a))
