# AI Use Disclosure

AI assistance was used to help implement and edit portions of the code, tests, documentation, and report scaffolding for this repository.

Human responsibility remains with the repository maintainer. All AI-assisted changes should be reviewed through:

```bash
pytest -q
python scripts/run_smoke_benchmark.py
python scripts/validate_artifact_contract.py outputs/benchmark/smu_headline_v1
python scripts/check_report_consistency.py report/safe_market_universes_note.md outputs/benchmark/smu_headline_v1
```

AI assistance was not used to create or modify raw market data. The current market-data source remains `yfinance`, with limitations described in `DATA_CARD.md`.
