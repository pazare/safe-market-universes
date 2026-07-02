# Reproducibility Guide

## Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Set `OPENAI_API_KEY` only for LLM-powered benchmark runs. Unit tests and the local smoke benchmark run without an API key.

## Verify

```bash
pytest -q
python scripts/run_smoke_benchmark.py
python scripts/review_benchmark.py outputs/benchmark/smu_headline_v1
python scripts/render_benchmark_figures.py outputs/benchmark/smu_headline_v1
python scripts/validate_artifact_contract.py outputs/benchmark/smu_headline_v1
python scripts/check_academic_data.py
```

## Publication Runs

Show the current publication progress from local artifact JSON:

```bash
python scripts/show_publication_progress.py
```

Preview the deterministic publication matrix without spending API or data-fetch budget:

```bash
python scripts/run_publication_suite.py --status-only
python scripts/run_publication_suite.py --dry-run --resume --max-runs 3
```

Run the model availability preflight:

```bash
python scripts/preflight_models.py
python scripts/preflight_models.py --live-response-check
```

The first command checks registry/model availability. The second command also makes one minimal Responses API call per configured model, so it catches quota and authentication failures before a long benchmark cell starts.

Run the full publication matrix only after confirming API access, cost, and runtime:

```bash
SMU_STEP_TIMEOUT_SECONDS=300 OPENAI_TIMEOUT_SECONDS=180 \
python scripts/run_publication_suite.py --live-response-check
```

`OPENAI_TIMEOUT_SECONDS` controls the OpenAI client timeout. `SMU_STEP_TIMEOUT_SECONDS` is an outer wall-clock timeout for each benchmark decision step, so a stuck API request is recorded as a failed resumable cell instead of running indefinitely.

## Expected Artifact Classes

- `outputs/benchmark/<run_id>/summary.json`
- `outputs/benchmark/<run_id>/trajectories.jsonl`
- `outputs/benchmark/<run_id>/episode_specs.json`
- `outputs/benchmark/<run_id>/human_audit_candidates.jsonl`
- `outputs/benchmark/<run_id>/gold_slice_candidates.jsonl`
- `report/figures/<run_id>/`
- paper table exports from `scripts/export_paper_tables.py`
- `outputs/human_audit/<run_id>/human_audit_summary.json`

Human-audit packets must be generated from `human_audit_candidates.jsonl`, not reranked independently from `trajectories.jsonl`. Existing reviewer and adjudication CSVs are preserved by default; use `scripts/build_human_audit_packet.py --force` only when intentionally replacing blank templates. A run becomes human-audit ready only when both reviewer CSVs and all `60` adjudicated labels are complete.

## Known Non-Determinism

Market data is fetched through `yfinance`, and model APIs may change over time. The benchmark caches market-data fetches under `.cache/market_data/`, records observation hashes, model names, run IDs, and seeds so deviations can be diagnosed. Set `SMU_MARKET_DATA_CACHE_DISABLED=1` to force fresh market-data downloads.

## Publication Consistency Gates

Before freezing a paper or artifact release, run:

```bash
python scripts/validate_artifact_contract.py outputs/benchmark/smu_headline_v1
python scripts/export_paper_tables.py outputs/benchmark/smu_headline_v1 --output /tmp/smu_tables
python scripts/export_preliminary_results.py --output report/preliminary_results.md --json-output report/preliminary_results.json
python scripts/check_croissant_metadata.py metadata/smu_croissant.json
python scripts/run_publication_suite.py --status-only --manifest /tmp/smu_publication_manifest.json
python scripts/check_publication_readiness.py --allow-pending
```

The strict readiness gate (without `--allow-pending`) is expected to exit nonzero with `external_blockers` until the full live suite and the two-reviewer human audit are complete.

The validator fails on stale regime labels, missing metric namespaces, absent ablations, missing required files, or trajectory records that no longer satisfy the Pydantic artifact schema.
