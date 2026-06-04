# Submission and GitHub Safety Guide

This file is the short operational checklist for the final pass now that the OpenAI key has been added and the full workflow has already been run.

## 1. Current Status

- setup verification completed successfully
- canonical full run completed successfully
- generated outputs currently present:
  - `outputs/COST.json`
  - `outputs/HIMS.json`
  - `outputs/SMCI.json`
  - `outputs/JNJ.json`
  - `outputs/TSLA.json`
  - `outputs/summary.json`
  - `outputs/backtest.json`
- report drafts are updated with actual evidence and analysis

## 2. Idempotence Rules

- rerunning `python -m src.main` overwrites the same stock JSON files instead of creating duplicates
- rerunning the batch also overwrites `outputs/summary.json` and `outputs/backtest.json`
- this keeps the repository tidy, but it also means you should not treat old outputs as preserved unless you copy them elsewhere first

## 3. What Is On Disk

- source code, prompts, reports, outputs, and `.env` are local files in this workspace
- the Codex app's local conversation mode is not automatically a tracked repository artifact
- there is still no Git repository here until you explicitly run `git init`

## 4. GitHub Safety Checklist

- confirm [`.gitignore`](../.gitignore) still includes `.env`
- after `git init`, run `git status --short` and confirm `.env` does not appear
- commit source code, prompts, outputs, README, and report assets
- do not commit `.venv/` or `__pycache__/`
- export the Markdown reports to PDF before the final upload if the course requires PDFs rather than Markdown

## 5. Recommended Final Commands

```bash
python -m src.main --verify-setup
python -m src.main
```

Run those again only if you intentionally want to refresh the market snapshot and overwrite the current outputs.

## 6. Final Quality Checks

- Confirm there is at least one agreement and at least one disagreement.
- Confirm the justifications cite actual numbers from the market data.
- Confirm the evaluator explains *why* the strategies diverged or converged.
- Confirm the debate section reports whether any positions actually changed.
- Confirm the backtest section cites `outputs/backtest.json` and explains the methodology.
- Confirm the failure case is real and not sanitized away.
- Confirm every claim in the report is consistent with the saved JSON outputs.
