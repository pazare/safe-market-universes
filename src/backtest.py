from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from .config import OUTPUTS_DIR
from .market_data import build_market_data_from_history, download_price_history
from .strategy_agents import run_strategy_a, run_strategy_b, run_strategy_c

DEFAULT_BACKTEST_CHECKPOINTS = 3
DEFAULT_BACKTEST_FORWARD_DAYS = 20
DEFAULT_BACKTEST_HOLD_BAND_PCT = 3.0
DEFAULT_BACKTEST_SPACING_DAYS = 21
WARMUP_TRADING_DAYS = 200


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _select_checkpoint_positions(
    history: pd.DataFrame,
    *,
    checkpoint_count: int,
    forward_days: int,
    spacing_days: int,
) -> list[int]:
    max_position = len(history) - forward_days - 1
    min_position = WARMUP_TRADING_DAYS
    if max_position <= min_position:
        raise ValueError("Not enough history to build the requested backtest checkpoints.")

    positions: list[int] = []
    cursor = max_position
    while cursor >= min_position and len(positions) < checkpoint_count:
        positions.append(cursor)
        cursor -= spacing_days
    return sorted(positions)


def _decision_for_forward_return(forward_return_pct: float, hold_band_pct: float) -> str:
    if forward_return_pct > hold_band_pct:
        return "BUY"
    if forward_return_pct < -hold_band_pct:
        return "SELL"
    return "HOLD"


def _simulated_return(decision: str, forward_return_pct: float) -> float:
    if decision == "BUY":
        return forward_return_pct
    if decision == "SELL":
        return -forward_return_pct
    return 0.0


def run_backtest(
    *,
    tickers: list[str],
    model: str | None = None,
    checkpoint_count: int = DEFAULT_BACKTEST_CHECKPOINTS,
    forward_days: int = DEFAULT_BACKTEST_FORWARD_DAYS,
    hold_band_pct: float = DEFAULT_BACKTEST_HOLD_BAND_PCT,
    spacing_days: int = DEFAULT_BACKTEST_SPACING_DAYS,
) -> Path:
    strategy_runners = {
        "Momentum Trader": run_strategy_a,
        "Value Contrarian": run_strategy_b,
        "Volatility Averse": run_strategy_c,
    }

    checkpoint_records: list[dict[str, Any]] = []
    strategy_totals = {
        name: {"correct": 0, "total": 0, "simulated_return_sum": 0.0}
        for name in strategy_runners
    }

    for ticker in tickers:
        history = download_price_history(ticker, period="3y")
        positions = _select_checkpoint_positions(
            history,
            checkpoint_count=checkpoint_count,
            forward_days=forward_days,
            spacing_days=spacing_days,
        )
        for position in positions:
            checkpoint_ts = history.index[position]
            forward_ts = history.index[position + forward_days]
            snapshot = build_market_data_from_history(
                ticker,
                history,
                info={},
                as_of_date=checkpoint_ts,
                allow_live_info_fields=False,
            )
            forward_return_pct = ((history["Close"].iloc[position + forward_days] / history["Close"].iloc[position]) - 1) * 100
            realized_outcome = _decision_for_forward_return(forward_return_pct, hold_band_pct)

            strategy_results: dict[str, Any] = {}
            for strategy_name, runner in strategy_runners.items():
                result = runner(ticker, snapshot, model=model)
                exact_match = result["decision"] == realized_outcome
                simulated_return_pct = _simulated_return(result["decision"], forward_return_pct)
                strategy_results[strategy_name] = {
                    "decision": result["decision"],
                    "confidence": result["confidence"],
                    "justification": result["justification"],
                    "exact_match": exact_match,
                    "simulated_return_pct": round(simulated_return_pct, 2),
                }
                strategy_totals[strategy_name]["correct"] += int(exact_match)
                strategy_totals[strategy_name]["total"] += 1
                strategy_totals[strategy_name]["simulated_return_sum"] += simulated_return_pct

            checkpoint_records.append(
                {
                    "ticker": ticker,
                    "as_of_date": checkpoint_ts.date().isoformat(),
                    "forward_end_date": forward_ts.date().isoformat(),
                    "forward_return_pct": round(float(forward_return_pct), 2),
                    "realized_outcome": realized_outcome,
                    "market_data_summary": snapshot,
                    "strategy_results": strategy_results,
                }
            )

    scorecard = {
        strategy_name: {
            "exact_matches": totals["correct"],
            "total_predictions": totals["total"],
            "accuracy": round(totals["correct"] / totals["total"], 3) if totals["total"] else 0.0,
            "average_simulated_return_pct": round(
                totals["simulated_return_sum"] / totals["total"], 2
            )
            if totals["total"]
            else 0.0,
        }
        for strategy_name, totals in strategy_totals.items()
    }

    payload = {
        "methodology": {
            "checkpoint_count_per_stock": checkpoint_count,
            "checkpoint_spacing_trading_days": spacing_days,
            "forward_window_trading_days": forward_days,
            "hold_band_pct": hold_band_pct,
            "historical_valuation_policy": (
                "Historical snapshots omit live trailing P/E values to avoid lookahead bias, "
                "because yfinance.info exposes live metadata rather than historical valuation snapshots."
            ),
        },
        "stocks_analyzed": tickers,
        "strategies": list(strategy_runners),
        "checkpoints": checkpoint_records,
        "scorecard": scorecard,
    }

    output_path = OUTPUTS_DIR / "backtest.json"
    _write_json(output_path, payload)
    return output_path
