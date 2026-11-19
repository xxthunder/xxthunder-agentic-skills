"""Tests for the criticmark-review skill script, run through its command line as the skill calls it.

Usage: `criticmark.py list notes.md` prints one line per mark; the number in `#N` is the ID that
`reply`, `accept` and `reject` take.
"""

from pathlib import Path

import pytest
from criticmark import main

SAMPLE = 'This is {==important==}{author="Max" date="2026-11-02">>Why?<<} {>>Claude: legacy<<}\nWe {++really ++}like it.{>>ok?<<}\n```\n{>>not a comment in a fence<<}\n```\n'


EOL = "\n"


@pytest.fixture(autouse=True, params=["\n", "\r\n"], ids=["lf", "crlf"])
def eol(request: pytest.FixtureRequest) -> None:
    """Every test runs on an LF and a CRLF file, so Linux catches what a Windows checkout sees."""
    global EOL
    EOL = request.param


def run(tmp_path: Path, text: str, *args: str, name: str = "note.md") -> tuple[int, str]:
    """Write *text* with this run's line ending, call the script, and read the result back in LF.

    Expectations stay written in LF; a result that mixes line endings fails here.
    """
    path = tmp_path / name
    path.write_bytes(text.replace("\n", EOL).encode("utf-8"))
    code = main([args[0], str(path), *args[1:]])
    out = path.read_bytes().decode("utf-8")
    if EOL == "\r\n":
        assert "\n" not in out.replace("\r\n", ""), f"mixed line endings: {out!r}"
        out = out.replace("\r\n", "\n")
    return code, out


def test_list_finds_tagged_and_plain_comments_but_not_code(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run(tmp_path, SAMPLE, "list")
    out = capsys.readouterr().out.splitlines()
    assert out == [
        "#1 L1 highlight: important",
        "#2 L1 comment thread=#2 Max 2026-11-02: Why?",
        "#3 L1 comment thread=#2 Claude: legacy",
        "#4 L2 addition: really",
        "#5 L2 comment thread=#5: ok?",
    ]


def test_reply_goes_after_the_last_comment_of_the_thread(tmp_path: Path) -> None:
    code, text = run(tmp_path, SAMPLE, "reply", "2", "Because.", "--date", "2026-11-12")
    assert code == 0
    assert '{>>Claude: legacy<<}{author="Claude" date="2026-11-12">>Because.<<}\n' in text


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (("--quote", "like it"), '{==like it==}{author="Claude" date="2026-11-12">>Say more.<<}'),
        (("--line", "1"), '<<}{author="Claude" date="2026-11-12">>Say more.<<}\nWe'),
    ],
)
def test_comment_on_quote_or_line(tmp_path: Path, args: tuple[str, str], expected: str) -> None:
    code, text = run(tmp_path, SAMPLE, "comment", *args, "Say more.", "--date", "2026-11-12")
    assert code == 0
    assert expected in text


@pytest.mark.parametrize("quote", ["missing", "important", "is"])
def test_comment_refuses_a_quote_that_is_absent_inside_a_mark_or_repeated(tmp_path: Path, quote: str) -> None:
    code, text = run(tmp_path, SAMPLE, "comment", "--quote", quote, "x")
    assert (code, text) == (1, SAMPLE)


@pytest.mark.parametrize(
    ("command", "source", "expected"),
    [
        ("accept", "a {++b ++}c", "a b c"),
        ("reject", "a {++b ++}c", "a c"),
        ("accept", "a {--b --}c", "a c"),
        ("reject", "a {--b --}c", "a b c"),
        ("accept", "a {~~b~>B~~}{>>why<<}{>>ok<<} c", "a B c"),
        ("reject", "a {~~b~>B~~} c", "a b c"),
    ],
)
def test_accept_and_reject_suggestions_with_their_thread(tmp_path: Path, command: str, source: str, expected: str) -> None:
    assert run(tmp_path, source, command, "1") == (0, expected)


def test_clean_waits_for_open_suggestions_then_strips_all_markup(tmp_path: Path) -> None:
    assert run(tmp_path, SAMPLE, "clean") == (1, SAMPLE)
    code, text = run(tmp_path, SAMPLE.replace("{++really ++}", "really "), "clean")
    assert code == 0
    assert text.startswith("This is important \nWe really like it.\n")
    assert "{>>not a comment in a fence<<}" in text


def test_sidecar_takes_replies_only(tmp_path: Path) -> None:
    sidecar = '{line="3">>check this<<}\n'
    assert run(tmp_path, sidecar, "clean", name="main.c.review") == (1, sidecar)
    code, text = run(tmp_path, sidecar, "reply", "1", "done", "--date", "2026-11-12", name="main.c.review")
    assert code == 0
    assert text == '{line="3">>check this<<}{author="Claude" date="2026-11-12">>done<<}\n'


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            'A {==b==}{author="Max" date="2026-11-02">>Why?<<}{author="Claude">>Done.<<}\n',
            'A {==b==}{author="Max" date="2026-11-02" status="resolved">>Why?<<}{author="Claude">>Done.<<}\n',
        ),
        ("A {>>Max: legacy<<}\n", 'A {status="resolved">>Max: legacy<<}\n'),
        ('A {author="Max" status="open">>x<<}\n', 'A {author="Max" status="resolved">>x<<}\n'),
    ],
)
def test_resolve_marks_the_thread_root(tmp_path: Path, source: str, expected: str) -> None:
    assert run(tmp_path, source, "resolve", "2" if "{==" in source else "1") == (0, expected)


def test_reply_keeps_crlf_line_endings_byte_for_byte(tmp_path: Path) -> None:
    path = tmp_path / "note.md"
    path.write_bytes(b"a {>>q?<<}\r\nb\r\n")
    assert main(["reply", str(path), "1", "ok", "--date", "2026-11-18"]) == 0
    assert path.read_bytes() == b'a {>>q?<<}{author="Claude" date="2026-11-18">>ok<<}\r\nb\r\n'


def test_missing_file_is_an_error_not_a_traceback(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["list", str(tmp_path / "absent.md")]) == 1
    assert capsys.readouterr().err.startswith("error: ")


def test_list_open_skips_the_highlight_of_a_resolved_thread(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run(tmp_path, 'A {==b==}{status="resolved">>Why?<<} c {==d==}{>>open<<}\n', "list", "--open")
    assert capsys.readouterr().out.splitlines() == ["#3 L1 highlight: d", "#4 L1 comment thread=#4: open"]


@pytest.mark.parametrize(
    "source",
    [
        "a\n\n    {>>in code<<}\n",  # an indented block up to the end of the file
        "a\n\n    {>>in code<<}\nb\n",  # an indented block that a paragraph ends
        "a\n\n    {>>in code<<}\n```\n{>>in a fence<<}\n```\n",  # an indented block that a fence ends
    ],
)
def test_list_skips_comments_in_indented_code(tmp_path: Path, capsys: pytest.CaptureFixture[str], source: str) -> None:
    assert run(tmp_path, source, "list") == (0, source)
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (("--kind", "addition"), ["#4 L2 addition: really"]),
        (("--author", "max"), ["#2 L1 comment thread=#2 Max 2026-11-02: Why?"]),
        (("--grep", "LEGACY"), ["#3 L1 comment thread=#2 Claude: legacy"]),
    ],
)
def test_list_filters_by_kind_author_and_text(tmp_path: Path, capsys: pytest.CaptureFixture[str], args: tuple[str, str], expected: list[str]) -> None:
    run(tmp_path, SAMPLE, "list", *args)
    assert capsys.readouterr().out.splitlines() == expected


def test_list_open_keeps_a_highlight_without_a_thread(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert run(tmp_path, "a {==b==} c\n", "list", "--open")[0] == 0
    assert capsys.readouterr().out.splitlines() == ["#1 L1 highlight: b"]


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("reply", "9", "x"), "No mark #9"),
        (("reply", "2", "a <<} b"), "closing marker"),
        (("reply", "4", "x"), "not part of a comment thread"),
        (("accept", "2"), "not a suggestion"),
        (("comment", "--line", "99", "x"), "Line 99 does not exist"),
        (("comment", "--quote", "not a comment in a fence", "x"), "inside code"),
        (("comment", "--quote", "it.\nWe", "x"), "one line"),
        (("comment", "--quote", "end==}", "x"), "cannot contain ==}"),
    ],
)
def test_refusals_leave_the_file_unchanged(tmp_path: Path, capsys: pytest.CaptureFixture[str], args: tuple[str, ...], message: str) -> None:
    source = SAMPLE + "it.\nWe end==} now.\n"
    assert run(tmp_path, source, *args) == (1, source)
    assert message in capsys.readouterr().err


def test_runs_as_a_script(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    import runpy

    import criticmark

    path = tmp_path / "note.md"
    path.write_text("a {>>q?<<}\n", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["criticmark.py", "list", str(path)])
    with pytest.raises(SystemExit) as done:
        runpy.run_path(criticmark.__file__, run_name="__main__")
    assert done.value.code == 0
    assert capsys.readouterr().out == "#1 L1 comment thread=#1: q?\n"


def test_clean_fails_when_unwrapping_a_highlight_forms_a_new_mark(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = "a {{==>>x==}<<} b\n"  # the highlight's text, unwrapped, closes into a comment
    assert run(tmp_path, source, "clean") == (1, source)
    assert "marks are left after cleaning" in capsys.readouterr().err
