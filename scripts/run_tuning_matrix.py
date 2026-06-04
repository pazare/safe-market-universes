from __future__ import annotations

if __package__ in {None, ""}:
    import sys
    from pathlib import Path

    sys.path.append(str(Path(__file__).resolve().parent.parent))

import argparse

from src.benchmark.tuning import run_validation_matrix
from src.config import load_environment


def main() -> None:
    load_environment()
    parser = argparse.ArgumentParser(description="Run the frozen Safe MarketUniverses tuning matrix.")
    parser.add_argument("--model", help="Optional model override for benchmark strategy and judge calls.")
    parser.add_argument(
        "--matrix-run-id",
        help="Optional override for the matrix output directory.",
    )
    parser.add_argument(
        "--baseline-run-id",
        default="smu_validation_v4",
        help="Baseline benchmark run id used for before/after comparison.",
    )
    parser.add_argument("--tickers", nargs="*", help="Optional override ticker list for smoke-testing the matrix.")
    parser.add_argument("--episodes", type=int, help="Optional override episode count.")
    parser.add_argument("--horizon", type=int, help="Optional override horizon.")
    parser.add_argument("--budgets", nargs="*", type=int, help="Optional override oversight budgets.")
    parser.add_argument(
        "--corruption-settings",
        nargs="*",
        choices=["on", "off"],
        help="Optional override corruption settings.",
    )
    parser.add_argument("--judge-sample-size", type=int, help="Optional override judge sample size.")
    args = parser.parse_args()

    matrix_summary_path = run_validation_matrix(
        matrix_run_id=args.matrix_run_id or "smu_tuning_matrix_v1",
        model=args.model,
        baseline_run_id=args.baseline_run_id,
        tickers=args.tickers,
        episode_count=args.episodes or 8,
        horizon=args.horizon or 4,
        budgets=args.budgets,
        corruption_settings=[value == "on" for value in args.corruption_settings] if args.corruption_settings else None,
        judge_sample_size=args.judge_sample_size or 2,
    )
    print(f"Saved tuning matrix summary at {matrix_summary_path}.")


if __name__ == "__main__":
    main()
