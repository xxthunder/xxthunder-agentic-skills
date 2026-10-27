## Learnings

The contract for the `learnings` skill. A learning is what stays true after the project is
deleted. The skill reads this section and nothing else about this repository; keep it
complete.

- **Where**: `learnings/YYYY-MM-DD_short_claim.md` — the date of the capture, then three to
  six lowercase words of the claim joined by `_`.
- **Template**: `templates/learning.md`. The author writes the **Claim**, in their own words.
  The agent drafts the other sections and marks each one with *(drafted by the agent)* under
  its heading.
- **Hub**: `learnings/README.md`. A new note adds one line at the end of its list:
  `- [<the claim>](<file>) — <repo> <ID>, YYYY-MM-DD`.
- **Tests**: a learning is written only when all five pass:
  1. It outlives the repository.
  2. No repository owns it.
  3. It is new: `recall` finds no note with the same claim.
  4. It would have changed a session.
  5. The author can say it in one sentence.
- **Not ready yet**: when only test 5 fails, the capture goes to `learnings/inbox/`, same file
  name, and not into the hub.
- **Commit**: one commit of the note and the hub, pushed immediately, with the subject
  `docs(learnings): <the claim, shortened> (<ITEM-ID>)`.
- **Language**: English.
