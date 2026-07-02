from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import load_environment
from src.ml_pipeline import MLBacktestConfig, run_ml_backtest

DEFAULT_TICKERS = ["COST", "HIMS", "SMCI", "JNJ", "TSLA"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the deterministic ML backtest and multi-goal minimax-regret scorecard."
    )
    parser.add_argument("tickers", nargs="*", help="Tickers to include in the historical universe.")
    parser.add_argument("--train-start", default="2024-01-02")
    parser.add_argument("--train-end", default="2024-12-31")
    parser.add_argument("--test-start", default="2025-01-02")
    parser.add_argument("--test-end", default="2025-12-31")
    parser.add_argument("--forward-days", type=int, default=20)
    parser.add_argument("--rebalance-days", type=int, default=20)
    parser.add_argument("--hold-band-pct", type=float, default=3.0)
    parser.add_argument("--transaction-cost-bps", type=float, default=10.0)
    parser.add_argument("--history-period", default="3y")
    parser.add_argument("--output", type=Path, default=Path("outputs/ml_backtest.json"))
    return parser.parse_args()


def main() -> None:
    load_environment()
    args = parse_args()
    config = MLBacktestConfig(
        tickers=[ticker.upper() for ticker in (args.tickers or DEFAULT_TICKERS)],
        train_start=args.train_start,
        train_end=args.train_end,
        test_start=args.test_start,
        test_end=args.test_end,
        forward_days=args.forward_days,
        rebalance_days=args.rebalance_days,
        hold_band_pct=args.hold_band_pct,
        transaction_cost_bps=args.transaction_cost_bps,
        history_period=args.history_period,
        output_path=args.output,
    )
    output_path = run_ml_backtest(config)
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    ml = payload["scorecard"]["ridge_return_minimax"]
    print(f"Saved ML backtest report at {output_path}.")
    print(
        "ridge_return_minimax: "
        f"avg_return={ml['average_strategy_return']:.4f}, "
        f"cumulative_return={ml['cumulative_return']:.4f}, "
        f"minimax_regret={ml['minimax_regret']:.4f}, "
        f"accuracy={ml['accuracy']:.3f}"
    )
    print(payload["performance_verdict"]["summary"])


if __name__ == "__main__":
    main()
