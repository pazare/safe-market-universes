from __future__ import annotations

if __package__ in {None, ""}:
    import sys
    from pathlib import Path

    sys.path.append(str(Path(__file__).resolve().parent.parent))

import argparse
import json
from datetime import date

from src.backtest import (
    DEFAULT_BACKTEST_CHECKPOINTS,
    DEFAULT_BACKTEST_FORWARD_DAYS,
    DEFAULT_BACKTEST_HOLD_BAND_PCT,
    run_backtest,
)
from src.benchmark.runtime import run_safe_market_universes
from src.benchmark.spec import (
    CANONICAL_EPISODES,
    CANONICAL_HORIZON,
    CANONICAL_JUDGE_SAMPLE_SIZE,
    CANONICAL_OVERSIGHT_BUDGET,
    CANONICAL_RUN_ID,
    CANONICAL_SEED,
    CANONICAL_TICKERS,
)
from src.config import REPORT_DIR, load_environment
from src.llm import verify_openai_call
from src.market_data import verify_yfinance_fetch
from src.orchestration import build_graph, export_graph_mermaid, write_summary

DEFAULT_ANALYSIS_TICKERS = ["COST", "HIMS", "SMCI", "JNJ", "TSLA"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Safe MarketUniverses workflows (committee analysis and oversight-allocation benchmark)."
    )
    parser.add_argument("tickers", nargs="*", help="One or more stock tickers to analyze.")
    parser.add_argument("--model", help="Override OPENAI_MODEL for this run.")
    parser.add_argument(
        "--verify-setup",
        action="store_true",
        help="Verify one real yfinance fetch and one real OpenAI call before a full run.",
    )
    parser.add_argument(
        "--market-only",
        action="store_true",
        help="Fetch and print live market data without calling the LLM.",
    )
    parser.add_argument(
        "--skip-graph-export",
        action="store_true",
        help="Skip saving the Mermaid graph text export.",
    )
    parser.add_argument(
        "--skip-debate",
        action="store_true",
        help="Skip the disagreement-only second-round debate extension.",
    )
    parser.add_argument(
        "--skip-backtest",
        action="store_true",
        help="Skip generating outputs/backtest.json.",
    )
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Run the Safe MarketUniverses benchmark instead of the multi-strategy analysis workflow.",
    )
    parser.add_argument(
        "--benchmark-episodes",
        type=int,
        default=CANONICAL_EPISODES,
        help="Number of benchmark episodes to generate in Safe MarketUniverses mode.",
    )
    parser.add_argument(
        "--benchmark-horizon",
        type=int,
        default=CANONICAL_HORIZON,
        help="Trading-day horizon per benchmark episode.",
    )
    parser.add_argument(
        "--benchmark-oversight-budget",
        type=int,
        default=CANONICAL_OVERSIGHT_BUDGET,
        help="Oversight interventions available per episode in benchmark mode.",
    )
    parser.add_argument(
        "--benchmark-seed",
        type=int,
        default=CANONICAL_SEED,
        help="Random seed for deterministic Safe MarketUniverses episode generation.",
    )
    parser.add_argument(
        "--benchmark-disable-corruption",
        action="store_true",
        help="Disable ToolPoisonBench-style corruption events in benchmark mode.",
    )
    parser.add_argument(
        "--benchmark-judge-sample-size",
        type=int,
        default=CANONICAL_JUDGE_SAMPLE_SIZE,
        help="Number of benchmark steps to send to the model-based quality judge.",
    )
    parser.add_argument(
        "--benchmark-run-id",
        default=CANONICAL_RUN_ID,
        help="Optional output folder name for benchmark mode.",
    )
    parser.add_argument(
        "--backtest-checkpoints",
        type=int,
        default=DEFAULT_BACKTEST_CHECKPOINTS,
        help="Number of historical checkpoints per stock for the backtest extension.",
    )
    parser.add_argument(
        "--backtest-forward-days",
        type=int,
        default=DEFAULT_BACKTEST_FORWARD_DAYS,
        help="Forward trading-day horizon for the backtest extension.",
    )
    parser.add_argument(
        "--backtest-hold-band",
        type=float,
        default=DEFAULT_BACKTEST_HOLD_BAND_PCT,
        help="Absolute forward-return band treated as HOLD in the backtest scorecard.",
    )
    return parser.parse_args()


def verify_setup(model: str | None) -> None:
    market_snapshot = verify_yfinance_fetch("MSFT")
    print("yfinance verification succeeded:")
    print(json.dumps(market_snapshot, indent=2))
    llm_response = verify_openai_call(model=model)
    print("\nOpenAI verification succeeded:")
    print(llm_response)


def market_only_run(tickers: list[str]) -> None:
    for ticker in tickers:
        snapshot = verify_yfinance_fetch(ticker)
        print(f"\n=== {ticker} ===")
        print(json.dumps(snapshot, indent=2))


def benchmark_run(
    tickers: list[str] | None,
    model: str | None,
    *,
    benchmark_episodes: int,
    benchmark_horizon: int,
    benchmark_oversight_budget: int,
    benchmark_seed: int,
    benchmark_disable_corruption: bool,
    benchmark_judge_sample_size: int,
    benchmark_run_id: str | None,
) -> None:
    summary_path = run_safe_market_universes(
        tickers=tickers,
        episode_count=benchmark_episodes,
        horizon=benchmark_horizon,
        oversight_budget=benchmark_oversight_budget,
        seed=benchmark_seed,
        model=model,
        enable_corruption=not benchmark_disable_corruption,
        judge_sample_size=benchmark_judge_sample_size,
        run_id=benchmark_run_id,
    )
    print(f"Saved Safe MarketUniverses benchmark outputs at {summary_path}.")


def full_run(
    tickers: list[str],
    model: str | None,
    *,
    skip_graph_export: bool,
    skip_debate: bool,
    skip_backtest: bool,
    backtest_checkpoints: int,
    backtest_forward_days: int,
    backtest_hold_band: float,
) -> None:
    workflow = build_graph()
    if not skip_graph_export:
        export_graph_mermaid(workflow, REPORT_DIR / "langgraph_workflow.mmd")

    records: list[dict[str, object]] = []
    run_date = date.today().isoformat()
    for ticker in tickers:
        final_state = workflow.invoke(
            {
                "ticker": ticker,
                "run_date": run_date,
                "model": model,
                "enable_debate": not skip_debate,
            }
        )
        records.append(final_state["output_record"])
        decisions = (
            final_state["strategy_a"]["decision"],
            final_state["strategy_b"]["decision"],
            final_state["strategy_c"]["decision"],
        )
        print(
            f"{ticker}: "
            f"A={decisions[0]} | B={decisions[1]} | C={decisions[2]} | "
            f"mode={final_state['evaluator']['agreement_profile']['disagreement_type']}"
        )

    summary_path = write_summary(records)
    print(f"\nSaved {len(records)} stock files and summary at {summary_path}.")

    if not skip_backtest:
        backtest_path = run_backtest(
            tickers=tickers,
            model=model,
            checkpoint_count=backtest_checkpoints,
            forward_days=backtest_forward_days,
            hold_band_pct=backtest_hold_band,
        )
        print(f"Saved historical backtest scorecard at {backtest_path}.")


def main() -> None:
    load_environment()
    args = parse_args()
    if args.benchmark:
        tickers = [ticker.upper() for ticker in args.tickers] if args.tickers else CANONICAL_TICKERS
    else:
        tickers = [ticker.upper() for ticker in (args.tickers or DEFAULT_ANALYSIS_TICKERS)]

    if args.verify_setup:
        verify_setup(args.model)
        return

    if args.market_only:
        market_only_run(tickers)
        return

    if args.benchmark:
        benchmark_run(
            tickers,
            args.model,
            benchmark_episodes=args.benchmark_episodes,
            benchmark_horizon=args.benchmark_horizon,
            benchmark_oversight_budget=args.benchmark_oversight_budget,
            benchmark_seed=args.benchmark_seed,
            benchmark_disable_corruption=args.benchmark_disable_corruption,
            benchmark_judge_sample_size=args.benchmark_judge_sample_size,
            benchmark_run_id=args.benchmark_run_id,
        )
        return

    full_run(
        tickers,
        args.model,
        skip_graph_export=args.skip_graph_export,
        skip_debate=args.skip_debate,
        skip_backtest=args.skip_backtest,
        backtest_checkpoints=args.backtest_checkpoints,
        backtest_forward_days=args.backtest_forward_days,
        backtest_hold_band=args.backtest_hold_band,
    )


if __name__ == "__main__":
    main()
