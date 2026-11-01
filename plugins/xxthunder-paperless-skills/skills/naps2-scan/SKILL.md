---
name: naps2-scan
description: >
  Scans paperwork with NAPS2 end-to-end: run NAPS2.Console.exe with OCR, chain into
  simplex-merge when scanning a double-sided document on a simplex scanner, and propose a
  content-derived filename. Use for ANY request to scan paperwork or digitize a document,
  including variants like "scan this", "let's scan", "scan another", "scan again",
  "scan the next one", "new scan", "start scanning",
  "digitize this receipt/letter/invoice/bill/statement", or "run NAPS2".
  Also handles batch mode — scanning a whole stack of separate documents in one pass
  ("scan this stack", "batch scan", "these are multiple documents") — by chaining into
  `split-batch`, which splits the bundle into one PDF per document.
  Also triggers when the user already has fresh scan output and wants to continue the
  pipeline (OCR, merge, name, rename) — not for renaming or filing PDFs that did not just
  come from a scan. This is the starting-point skill for scanning; `simplex-merge` is
  post-processing only, never for a new scan.
---

<!-- Source: https://github.com/xxthunder/xxthunder-agentic-skills/tree/develop/plugins/xxthunder-paperless-skills/skills/naps2-scan -->

# NAPS2 Scan Pipeline

Automate document scanning with [NAPS2](https://www.naps2.com/): **scan → OCR → (merge if simplex) → filename proposal**.

## When This Skill Triggers

- "Scan this" / "Start scanning" / "Let's scan" / "Digitize this"
- "Scan another" / "Scan again" / "Scan the next one" / "New scan"
- "Run NAPS2" / "Scan with NAPS2"
- "Scan this receipt/letter/invoice/bill/statement"
- "Scan this stack" / "Batch scan" / "These are multiple documents" (batch mode — chains into `split-batch`)
- Any request to start a new scan or digitize a physical document
- User already has scan output (PDF files) and wants to continue the pipeline (OCR already done, or post-processing only)

This skill is the **entry point** for scanning. `simplex-merge` is a post-processing helper called *from* this pipeline — it should not be picked directly when the user wants to start a new scan.

## Prerequisites

Check once at the start of a scan session; don't re-check every invocation.

- **NAPS2 installed, version 8.0 or later** — the skill relies on `--enableocr` / `--ocrlang` / `-p` flags present in NAPS2 8.x. Tested against 8.2.1. Verify with `NAPS2.Console.exe --version`.
- **`NAPS2.Console.exe` invocable** — just run `NAPS2.Console.exe --version`. If that fails, ask the user for the full path. **Do not guess paths, do not try "common locations", do not list candidates** — just ask. Store the resolved path for the session (and persist it via Config below) so you don't re-ask on every invocation.
- **OCR language data** — installed via the NAPS2 GUI (`Tools → OCR` → download language packs you need; commonly `eng`, `deu`).
- **A scanner profile** — configured in the NAPS2 GUI (`Profiles → New`). The skill does not create or edit profiles.
- **Recommended profile option for mixed stacks**: enable `Profile → Edit → Advanced → Exclude blank pages` so NAPS2 drops blank pages during the scan (essential for simplex double-sided stacks where the last back is blank). This is a profile-only setting — the CLI cannot toggle it per invocation.
- **`uv` on PATH** — the skill's helper scripts under `scripts/` are [PEP 723](https://peps.python.org/pep-0723/) inline-metadata Python scripts run via `uv run`. Verify with `uv --version`. Install with `winget install astral-sh.uv` (Windows) or the installer at <https://docs.astral.sh/uv/>. `uv` handles Python + dependencies (`pypdf`) automatically — no manual `pip install` needed.

If any prerequisite is missing, stop and tell the user what to install/configure. Do not try to scan without a profile.

## Config

The skill persists a small per-user config so it doesn't re-ask the same questions every session.

- **Location**:
  - Windows: `%APPDATA%\naps2-scan\config.json`
  - Linux/macOS: `${XDG_CONFIG_HOME:-~/.config}/naps2-scan/config.json`
- **Schema**:
  ```json
  {
    "exe_path": "C:\\path\\to\\NAPS2.Console.exe",
    "default_profile": "MFC Flachbett",
    "default_ocr_lang": "eng+deu",
    "default_scanner_type": "simplex"
  }
  ```
  `default_scanner_type` is `simplex` or `duplex` — a property of the hardware, not of any single document.
- **Read**: at the start of Step 1, run
  ```bash
  uv run <skill_dir>/scripts/read_config.py --validate-exe
  ```
  where `<skill_dir>` is this skill's base directory (Claude Code provides it at skill load time). Exit codes:
  - `0` → JSON printed to stdout; use as defaults.
  - `1` → no config or unreadable; ask the user for everything.
  - `2` → JSON printed, but `exe_path` no longer exists on disk; keep profile/lang defaults but re-ask for the path.
- **Write**: only after a **successful** scan + rename, run
  ```bash
  uv run <skill_dir>/scripts/write_config.py \
    --exe-path "<resolved exe path>" \
    --profile "<profile name>" \
    --ocr-lang "<lang code>" \
    --scanner-type "<simplex|duplex>"
  ```
  Pass only the flags for values supplied or resolved this session — the script merges into existing config and preserves keys it wasn't told about. `--scanner-type` accepts only `simplex` or `duplex`. Writing only on success avoids persisting typo'd profile names or dead paths.
- **Failure is non-fatal**: if read or write fails for any reason, degrade to "ask every time" and continue. Never fail a scan because of config I/O.
- **User reset**: the user can edit or delete `config.json` to reset any field.

## LLM Consent

Step 4 (OCR text extraction) sends the document's text into the conversation, which transits Anthropic's API for any LLM-based analysis. Before the first such step in a conversation, ask the user:

> Propose filename from OCR text via Claude? This sends the document's text to Anthropic's API. (yes = LLM proposal; no = I'll ask you for date / sender / topic directly)

Cache the answer in-conversation. Reuse it for any subsequent LLM-eligible step in the same conversation — do not re-ask. Do **not** persist the answer to the config file; the next conversation must ask again. This keeps consent fresh without making every scan a modal dialog.

On `deny`, the PDF stays fully local for the remainder of the conversation. **Do not invoke `extract_text.py` or any other command that reads the PDF's contents.** Step 4 is skipped and Step 5 uses the deny path (ask the user for date / sender / topic directly). Re-check the cached answer every time you re-enter the pipeline — including when resuming after `simplex-merge` or any other sub-skill.

## Entry Points

The skill has two entry points; pick based on what the user asks:

- **(A) Fresh scan**: the user wants to scan physical paper now → start at **Step 1**.
- **(B) Post-processing**: the user already has scan files in the working directory → skip to **Step 3**.

If unclear, look at the current directory for existing PDFs matching scan-output patterns (e.g., `scan*.pdf`, `*ungerade*`, `*gerade*`) and ask the user.

## Workflow

### 1. Gather scan parameters

First, read the persisted config (see **Config** section above):

```bash
uv run <skill_dir>/scripts/read_config.py --validate-exe
```

Apply any returned values as defaults. Then ask the user (or infer from conversation) for anything missing or overridden:

- **Profile name** — which NAPS2 profile to use. Use `default_profile` from config if present; otherwise ask. Do not guess.
- **Double-sided?** — ask yes/no **per document**. If yes, determine the scanner type:
  - Use `default_scanner_type` from config if present (it's a property of the hardware, not the document — do not re-ask per document).
  - Otherwise ask **once** per session: **duplex scanner** (both sides in one pass, no merge step) or **simplex scanner** (two passes required; `simplex-merge` chains in at Step 3). Cache the answer for the rest of the session and persist it at Step 7.
- **OCR language(s)** — e.g., `eng`, `deu`, `eng+deu`. Use `default_ocr_lang` from config if present; otherwise default to `eng+deu` and say so. The user can override per-invocation without losing the stored default.

If `read_config.py` exited `2`, the stored `exe_path` is stale — re-ask for the path but keep profile/language defaults.

### 2. Invoke NAPS2.Console.exe

Run from the current working directory so output lands where the user expects. Basic form (single-sided or duplex):

```bash
NAPS2.Console.exe \
  --profile "<PROFILE>" \
  --output "scan.pdf" \
  --force \
  --enableocr \
  --ocrlang "<LANG>" \
  --verbose
```

Relevant flags:
- `--profile "<name>"` — scanner profile (required).
- `--output "<path>"` — output PDF.
- `--force` — **always pass this**. Overwrites the output file without prompting so stale output from a previous run (e.g., an aborted scan) doesn't block the new scan.
- `--enableocr` — enable OCR. (`--ocrlang` alone also implies `--enableocr`.)
- `--ocrlang <code>` — OCR language code (e.g., `eng`, `deu`, `eng+deu`).
- `--verbose` — show progress.

NAPS2 does not provide a CLI flag to list profiles. If the user is unsure which profile to use, direct them to the NAPS2 GUI (`Profiles` menu) to look up the profile name. Do not suggest `--listprofiles` (that flag does not exist). `--listdevices` exists but lists scanners, not profiles.

**Simplex double-sided**: invoke twice with intermediate filenames:

1. First pass → `scan-odd.pdf` (fronts, correct order). Tell the user when to flip the stack.
2. Second pass → `scan-even.pdf` (backs, reverse order — that's fine, `simplex-merge` handles reversal).

NAPS2 runs interactively; the command blocks until scanning is done or cancelled. Relay any NAPS2 error output to the user verbatim and stop — do not retry automatically.

### 3. Merge (simplex only)

If two files were produced from a simplex double-sided scan, invoke the **`simplex-merge`** skill to interleave odd/even pages into a single PDF. Let `simplex-merge` handle naming of the merged output; the current skill continues from there.

For single-sided or duplex scans, the NAPS2 output is already the final PDF — skip the merge and continue.

### 3b. Split (batch mode only)

If the user signalled they scanned a **stack of separate documents** in one pass ("scan this stack", "batch scan", "these are multiple documents"), the single PDF from Step 2/3 actually bundles several documents. Hand it off to the **`split-batch`** skill to detect document boundaries and emit one PDF per document. `split-batch` presents a split map for confirmation and shares this conversation's LLM-consent answer (see **LLM Consent** above) for any boundary escalation.

For a normal single-document scan, skip this step — the merged/scanned PDF is the one final document.

When `split-batch` produces N PDFs, run Step 4–5 **per output file** (loop), proposing a filename for each. Otherwise continue with the single PDF.

### 4. Extract text for filename proposal (consent-gated)

**Consent gate — check before issuing any command in this step:**

1. Recall the cached LLM consent answer from earlier in this conversation.
2. If it was **denied** → STOP. Do not run `extract_text.py` or any other command that reads the PDF's contents. Skip directly to Step 5's deny path.
3. If it has not yet been asked → ask it now (see **LLM Consent** above), cache the answer, then re-evaluate this gate.
4. Only if the cached answer is **allow** → proceed to extraction below.

Re-run this gate every time you re-enter the pipeline (e.g. after returning from `simplex-merge`). Do not treat extraction as a mechanical next step.

**On `allow`** — read the final PDF's OCR text via the helper script:

```bash
uv run <skill_dir>/scripts/extract_text.py "<final_pdf>" --pages 2
```

`uv` resolves `pypdf` automatically from the script's PEP 723 header. The first 1-2 pages are enough for classification — that's where sender, subject, and date typically appear.

**On `deny`** — this step is a no-op; jump to Step 5.

### 5. Propose a filename

Target format:

```
YYYY-MM-DD-<sender>-<topic>.pdf
```

Examples (illustrative — adapt to document language and type):

- `2026-04-18-finanzamt-steuerbescheid.pdf`
- `2026-03-02-stadtwerke-jahresabrechnung.pdf`
- `2026-01-15-kfz-versicherung-police.pdf`
- `2026-04-10-amazon-invoice.pdf`

**Allow path** (OCR text was extracted in Step 4) — propose from the OCR text using these heuristics:

- **Date**: find the document date (letterhead, subject line, first page). If none found, use today's date.
- **Sender**: top of the letter, letterhead, company name. Slugify: lowercase, ASCII, hyphen-separated.
- **Topic**: one or two words describing document type (invoice, contract, statement, tax notice, insurance policy, …). Use the document's language if clear.
- **Length**: aim for under 60 characters total; distinctive but not verbose.

**Deny path** (Step 4 was skipped) — ask the user directly for each component, in plain conversation:

- **Date** (default: today)
- **Sender** as a short slug (e.g. `finanzamt`, `stadtwerke`, `amazon`)
- **Topic** (e.g. `invoice`, `steuerbescheid`, `jahresabrechnung`)

Assemble the filename from the answers. No OCR text is read or transmitted in this path.

Present the proposal to the user. Accept user edits before renaming.

### 6. Rename to the proposed filename

After user confirms, rename the final PDF in place. Do not move it to another directory — that's the job of the `auto-file` skill.

Leave intermediate files (`scan-odd.pdf`, `scan-even.pdf`) for the user to delete — do not delete automatically.

### 7. Persist config

Once the rename has succeeded, write session values back to the config so they become defaults for the next run:

```bash
uv run <skill_dir>/scripts/write_config.py \
  --exe-path "<resolved exe path>" \
  --profile "<profile name>" \
  --ocr-lang "<lang code>" \
  --scanner-type "<simplex|duplex>"
```

Pass only the flags for values that were actually supplied or resolved this session (omit `--scanner-type` if the scan was single-sided and no scanner type was established). If the write fails (permissions, full disk, etc.), report it to the user and move on — the scan already succeeded; config persistence is best-effort.

## Troubleshooting

- **`NAPS2.Console.exe` not found**: NAPS2 isn't on PATH. Ask the user for the full path and invoke via that path for the rest of the session. Do not guess or try candidate paths.
- **"Profile not found"**: NAPS2 has no CLI flag to list profiles. Ask the user to open the NAPS2 GUI and read the profile name from the `Profiles` menu, then retry with the exact name.
- **OCR disabled or wrong language**: OCR language pack not installed. Direct the user to NAPS2 GUI → `Tools → OCR` to install it. Do not try to fetch language data from the CLI.
- **Blank or very short OCR text**: the document may be a photo/form with little text. Ask the user for the filename components directly rather than guessing from empty text.
- **Trailing or interleaved blank pages in output**: the scanner profile is not dropping blanks. Enable `Profile → Edit → Advanced → Exclude blank pages` in the NAPS2 GUI and re-scan. `NAPS2.Console.exe` has no flag for this — it is profile-only.
- **Stale `exe_path` in config**: `read_config.py --validate-exe` exits `2` when the stored NAPS2 path no longer resolves to a file (e.g., NAPS2 was reinstalled elsewhere). Re-ask the user for the path; the next successful scan will overwrite it via `write_config.py`.
- **`uv` not found**: the helper scripts cannot run. Install `uv` (`winget install astral-sh.uv` on Windows, or see <https://docs.astral.sh/uv/>). Do not try to substitute a bare `python` call — the scripts depend on PEP 723 metadata resolution that only `uv run` (and a few other tools) understand.
- **Config read/write failure**: treat as non-fatal. Fall back to asking the user every session; do not fail the scan. If the user wants to debug, the config file lives at `%APPDATA%\naps2-scan\config.json` (Windows) or `${XDG_CONFIG_HOME:-~/.config}/naps2-scan/config.json` (Linux/macOS).

## Notes

- The skill does **not** auto-file (move the result into an archive folder). Filing is handled by the `auto-file` skill.
- The skill does **not** modify NAPS2 profiles. Profile setup is a one-time user action in the NAPS2 GUI.
- Scanner settings beyond profile/OCR (e.g., DPI, paper size, colour) must be baked into the profile — the CLI does not accept per-invocation overrides for most scanner settings.
