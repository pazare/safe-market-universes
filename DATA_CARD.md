# Data Card

## Dataset Status

Safe MarketUniverses v1 is an evaluation environment and generated benchmark artifact, not a redistributable raw market-data dataset. The current implementation uses `yfinance` to fetch daily U.S. equity OHLCV data at runtime and derives compact market features for benchmark episodes.

## Source And Access

- Source: Yahoo Finance data accessed through `yfinance`.
- Scope: daily U.S. equities used in the configured ticker universe.
- Canonical v1 tickers: `COST`, `JNJ`, `KO`, `PG`, `AAPL`, `XOM`, `HIMS`, `PLTR`, `TSLA`, `SMCI`, `NKE`, `PFE`.
- Current limitation: raw historical market data is not claimed as newly collected data and is not redistributed as the central contribution.

## Academic Data Upgrade Path

WRDS is the preferred upgrade path for a stronger publication release because it can provide CRSP/Compustat-style academic market data through institutional access. The repository includes `scripts/check_academic_data.py` and an optional `wrds` dependency group. In this environment, the public WRDS website was reachable, but no local `WRDS_USERNAME` credential was configured; therefore entitlement and data extraction were not verified.

## Reproducibility Policy

The benchmark records episode specs, observation hashes, generated trajectories, quality assessments, and artifact manifests. Runtime `yfinance` fetches are cached under `.cache/market_data/` with sidecar metadata and SHA-256 hashes unless `SMU_MARKET_DATA_CACHE_DISABLED=1` is set. For this release, reproducibility depends on rerunning the data fetch against `yfinance`, using the local cache, or inspecting the included generated benchmark outputs. A future release should migrate to a source with explicit archival and redistribution terms.

The repository includes Croissant JSON-LD metadata at `metadata/smu_croissant.json`. Because the current contribution is an executable benchmark and generated artifact rather than a redistributable raw market dataset, the metadata describes files, record sets, intended use, RAI limitations, and provenance pointers rather than claiming ownership of raw Yahoo Finance market data.

## Intended Use

The benchmark is intended for safety evaluation of long-horizon recommendation agents: calibrated deferral, finite-budget oversight, interruption handling, corrupted-evidence response, and auditability.

## Out Of Scope

This artifact is not investment advice, not a live trading system, and not a claim of profitable trading performance.
