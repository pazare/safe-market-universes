# Reproducibility Checklist

## Environment

- Python version: `>=3.11`.
- Install command: `pip install -e ".[dev]"`.
- Optional WRDS adapter: `pip install -e ".[wrds]"`.
- Unit and smoke tests run without API keys.
- LLM-powered benchmark reruns require `OPENAI_API_KEY`.

## Determinism And Parameters

- Canonical run ID: `smu_headline_v1`.
- Canonical seed: `20260414`.
- Canonical tickers: `COST`, `JNJ`, `KO`, `PG`, `AAPL`, `XOM`, `HIMS`, `PLTR`, `TSLA`, `SMCI`, `NKE`, `PFE`.
- Canonical horizon: `4`.
- Canonical oversight budget: `1`.
- Human audit target: `60` prioritized steps plus adjudication.

## Required Checks

```bash
pytest -q
python scripts/run_smoke_benchmark.py
python scripts/validate_artifact_contract.py outputs/benchmark/smu_headline_v1
python scripts/check_report_consistency.py README.md outputs/benchmark/smu_headline_v1
python scripts/show_publication_progress.py
python scripts/run_publication_suite.py --status-only --manifest /tmp/smu_publication_manifest.json
python scripts/check_publication_readiness.py --allow-pending
```

The strict gate (`check_publication_readiness.py` without `--allow-pending`) is expected to exit nonzero with `external_blockers` until the live suite and human audit are complete.

## Known Limits

- Raw market data currently comes from `yfinance` and is not claimed as a redistributable canonical dataset.
- Model APIs can change after the run date; model preflight records unavailable models instead of silently substituting.
- Full publication claims require rerunning the multi-model, multi-seed suite and completing the two-reviewer human audit.
- `external_blockers` from `scripts/check_publication_readiness.py` is expected until the live suite and human audit are complete.
