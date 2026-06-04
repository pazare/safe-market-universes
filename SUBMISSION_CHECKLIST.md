# Submission Checklist

## Before Public Release

- [ ] `pytest -q` passes.
- [ ] `python scripts/run_smoke_benchmark.py` passes.
- [ ] `python scripts/validate_artifact_contract.py outputs/benchmark/smu_headline_v1` passes.
- [ ] `python scripts/check_report_consistency.py report/safe_market_universes_note.md outputs/benchmark/smu_headline_v1` passes.
- [ ] `python scripts/check_croissant_metadata.py metadata/smu_croissant.json` passes.
- [ ] `python scripts/show_publication_progress.py` summarizes suite, audit, and model-preflight progress.
- [ ] `python scripts/export_preliminary_results.py` regenerates the recruiter/paper-facing preliminary-results snapshot from artifacts.
- [ ] `python scripts/preflight_models.py --live-response-check` records model availability and live quota/authentication state.
- [ ] `python scripts/run_publication_suite.py --status-only --manifest /tmp/smu_publication_manifest.json` writes the planned matrix with statuses.
- [ ] Live publication runs are executed in resumable batches after live preflight passes, for example `python scripts/run_publication_suite.py --live-response-check --resume --max-runs 3`.
- [ ] `python scripts/aggregate_publication_suite.py` summarizes all completed live suite runs.
- [ ] `python scripts/check_publication_readiness.py` reports `publication_ready`.
- [ ] Human audit packets are generated for `60` prioritized steps without clobbering filled reviewer/adjudication CSVs.
- [ ] Two reviewer CSVs and adjudication labels are summarized.
- [ ] The paper states that the benchmark is not investment advice and does not claim trading alpha.
- [ ] Data limitations and the WRDS/CRSP/Compustat migration path are disclosed.

## Submission Claims To Keep

- Safety benchmark for calibrated deferral, finite oversight, corrupted evidence, and auditability.
- Diagnostic failure taxonomy and trajectory-level artifact contract.
- Current empirical claims are bounded by the frozen run, model availability, and unfinished data-source migration.

## Claims To Avoid

- Profitable trading performance.
- Canonical redistribution rights for raw market data.
- Fully solved agent safety.
- Replacement of human financial judgment.
