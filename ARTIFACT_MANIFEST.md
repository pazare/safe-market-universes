# Artifact Manifest

## Flagship Result

- `scripts/export_oversight_allocation.py`: regenerates the flagship oversight-allocation numbers, tables, and figure from committed logs with no model calls.
- `report/oversight_allocation_results.md` / `report/oversight_allocation_results.json`: the flagship result files.
- `report/figures/submission/oversight_allocation.png`: the flagship figure.
- `tests/test_oversight_allocation.py`: invariant checks for the metric (oracle optimality, regret >= 0, utility-free robustness).
- `outputs/benchmark/publication_gpt_5_4_mini_*`: the 18 committed `gpt-5.4-mini` budget x corruption x seed suite cells backing the robustness pooling.
- `report/submission_paper.tex` / `report/submission_paper.pdf`: the preprint (build with `python report/build_latex_pdf.py`).
- `report/submission_claim_audit.md`: a claim-to-evidence map for every empirical and positioning claim in the paper.

## Core Code

- `src/benchmark/`: Safe MarketUniverses environment, episode generation, abstention, oversight, judging, metrics, and runtime.
- `src/main.py`: canonical CLI entrypoint.
- `scripts/`: reviewer summaries, figure/table rendering, publication matrix orchestration, model preflight, progress reporting, smoke benchmark, human-audit utilities, artifact validation, and report consistency checks.

## Publication Metadata

- `README.md`: project overview and commands.
- `DATA_CARD.md`: market-data provenance and limits.
- `MODEL_CARD.md`: model usage and availability policy.
- `REPRODUCIBILITY.md`: setup and rerun instructions.
- `REPRODUCIBILITY_CHECKLIST.md`: venue-style reproducibility checklist.
- `ETHICS.md`: safety, financial-advice, and misuse disclosure.
- `AI_USE_DISCLOSURE.md`: AI-assistance disclosure for the code and manuscript package.
- `metadata/smu_croissant.json`: Croissant-style metadata and RAI pointers for benchmark artifacts.
- `CITATION.cff`: citation metadata.
- `LICENSE`: software license.

## Benchmark Outputs

The canonical headline artifact is `outputs/benchmark/smu_headline_v1/`, with `120` episodes and `480` steps. It validates against `smu-artifact-v2` using `python scripts/validate_artifact_contract.py outputs/benchmark/smu_headline_v1`. Generated outputs are inspection artifacts, not investment recommendations.

The artifact validator requires a completed `progress.json`, matching episode files under `episodes/`, trajectory/summary count consistency, audit-candidate count consistency, ticker consistency, and headline metric consistency for action distribution, total reward, non-HOLD action rate, and utility per intervention.

## Review Artifacts

Human audit tooling writes two blinded reviewer packets, an adjudication file, and an agreement summary under `outputs/human_audit/<run_id>/` by default. The target audit size is `60` prioritized steps selected from the benchmark run's `human_audit_candidates.jsonl`. Existing reviewer and adjudication CSVs are no-clobber by default to protect human labels; overwriting them requires an explicit `--force`. `scripts/attach_human_audit_summary.py --expected-count 60` attaches the audit summary back to a benchmark `summary.json`; readiness remains blocked until both reviewer packets and all adjudication labels are complete.

Reviewer packets include compact JSON evidence columns for market features, tool evidence, committee votes, abstention state, and overseer decisions. The blinded reviewer files intentionally omit automated audit status and failure labels; the adjudication file retains those automated labels only for post-review model-vs-human comparison.

## Readiness Reports

- `outputs/model_preflight.json`: committed model-availability report (regenerate with `python scripts/preflight_models.py`).
- `outputs/benchmark/publication_suite_manifest.json`: committed manifest for the planned 54 live publication runs, of which 18 are complete and committed (regenerate with `python scripts/run_publication_suite.py --dry-run`).
- `outputs/benchmark/publication_suite_summary.json`: committed completion summary for the publication suite. It counts only runs with `progress.json` marked complete and `artifact_validation.status=pass`; invalid or partial runs are reported separately.
- `scripts/show_publication_progress.py`: one-command progress view combining readiness checks, suite completion, human-audit completion, and model preflight state.
- `scripts/check_publication_readiness.py`: reports whether remaining blockers are engineering failures or external blockers.
