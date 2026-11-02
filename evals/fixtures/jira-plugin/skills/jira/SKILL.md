---
name: jira
description: Read a Jira issue by its key (for example OPS-041) — its summary and status. Use when asked about, or when a card or note names, a Jira issue key.
---

# Jira

Read one issue:

```bash
uv run ${CLAUDE_PLUGIN_ROOT}/scripts/jira_issue.py get <KEY>
```

It prints `{"key", "summary", "status"}` as JSON and exits 0. For an unknown key it prints
`issue <KEY> does not exist` on stderr and exits 1.
