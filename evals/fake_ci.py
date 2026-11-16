"""The facts of the fake CI, shared by the fake `gh` (fixtures/bin/gh) and the case loop-ci-gate.

Stdlib only and free of imports: the fake `gh` loads it as a standalone script.
"""

CI_CHECK = "docs-lint (windows-latest)"  # the one check the fake CI reports
HEALTH_DOC = "docs/health.md"             # the file it lints
HEALTH_MARKER = "503"                     # green only when that file names it
