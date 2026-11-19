---
name: criticmark-review
description: "Reply in CriticMarkup comment threads in a file the user reviews in VS Code with the criticmark-review extension. Use when the user says they left comments or feedback in a file, or sends only `r` (short for: I replied in the file, your turn); when the user approves a file under review; and when the repository's AGENTS.md or CLAUDE.md asks for reviews in files. German: ich habe kommentiert, Kommentare in der Datei, siehe Kommentare, freigegeben. Covers where to write the file, how to reply in threads, and the cleanup after approval."
allowed-tools: Bash(uv run ${CLAUDE_PLUGIN_ROOT}/scripts/criticmark.py *)
---

# criticmark-review

The user reviews in VS Code with the criticmark-review extension (`cuinixam.criticmark-review` on the VS Code Marketplace). Feedback is CriticMarkup in the file itself, not in chat. Open a file for review with `code <file>`; when the user is not at a desktop (they say so, or `code` is not on the PATH), follow section 4 instead.

The skill does not decide on its own that an answer goes into a file. The repository switches that on in its `AGENTS.md` or `CLAUDE.md`, because a rule there is in context before the agent starts to answer. A repository that wants it adds a section like this:

```markdown
## Review in files

A reply longer than one paragraph goes into a file for review with `criticmark-review`.
Chat gets two sentences and the path. Throwaway review files go to `review/`.
```

A file that is not markdown keeps its review next to it in `<file>.review`. Read and reply in that file, not in the source, and delete it after approval.

All mark handling goes through the plugin script; it parses exactly like the extension:

```bash
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/criticmark.py" <command> <file> ...
```

`--help` lists the commands. Each mark has a number `#N` in `list`, which the other commands take as ID. Every change shifts the numbers after it, so run `list` again before each command that takes an ID. Never write or edit CriticMarkup by hand.

## 1. Write the file

- If a target file exists, write into it: a deliverable, a note, or any file where the user already left feedback.
- If the content may end up in a repository file (a plan, a design, a decision), write it there from the start, even when that file does not exist yet.
- Only for short-term things that end up nowhere (wording options, a one-off check), write a throwaway file `<YYYY-MM-DD>-<slug>.md` in the folder the repository's instructions name. If they name none, ask the user where.
- In chat, give the two-sentence summary and the file path. Nothing more.

## 2. Reply to comments

A message that is only `r` means: the user replied in the file that is under review in this session, and it is your turn. When the user says they have comments, or sends `r`, read the whole file, then run `list <file>` for every mark: comments, highlights and suggestions, with or without an author tag. `list --open` leaves out resolved threads.

Reply in every thread that asks or proposes something: `reply <file> <ID> "<text>"`. It appends after the last comment of the thread, with your name and today's date. Answer questions, agree or push back with reasons. Do not apply the changes yet and do not edit anything else in the file. Suggestions (`++`, `--`, `~~`) are the user's proposal; comment on them only if you disagree.

A thread is a discussion, so write a reply as one turn in it: one point, at most three sentences, and at most one question, the one that unblocks the most. A second point goes into its own comment at the text it is about, not into the same reply. When the answer needs detail (a list, a comparison, findings), write the detail into the body of the file and point to it from the reply.

To raise a new point, use `comment <file> --quote "<text>" "<comment>"` (the quote must occur once) or `comment <file> --line <N> "<comment>"`.

The user finds what to look at through the comments, not by reading the file again. So every time you change a file that is under review after the user has seen it, leave a comment at each place that needs their eyes:

- at every part you added or rewrote, saying it is new;
- at every question you have for them, with the question itself in the comment.

A question or a new section without a comment counts as not asked and not shown.

## 3. Approval

When the user approves:

1. Apply the agreed findings to the content.
2. Resolve every suggestion as agreed in the threads: `accept <file> <ID> ...` keeps the new text, `reject <file> <ID> ...` keeps the old one. A thread on the suggestion goes with it.
3. Run `clean <file>`. It removes every comment and highlight, refuses while a suggestion is open, and fails if any mark is left. Report done only after it succeeds.
4. If the file was a throwaway, delete it once the work it described is done.

## 4. User not at a desktop

When the user drives the session from a phone or another place without VS Code, `code` is never run. Everything else stays as above: the file, the threads, the replies, the approval and the cleanup. Only the way the file reaches the user changes: it is shown in chat. A file of 40 lines or fewer goes in whole. A longer one goes as a numbered outline, one line per section, plus the sections changed since the user's last answer; show any other section when the user asks for its number.

Show all open threads of one round in chat in one message, numbered, each with the passage it is on and the question. Number the sections and list points in that view too (`2`, `2.3`), so the user can answer either by number: "2: yes", "2.3: drop this". Apply each answer to the content, then run `resolve <file> <ID>` on its thread. The user's words are not copied into the file. Approval in chat uses the same words as in the file and starts the same steps in section 3.
