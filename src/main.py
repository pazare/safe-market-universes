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
from src.config import REPORT_DIR, load_environment
from src.llm import verify_openai_call
from src.market_data import verify_yfinance_fetch
from src.orchestration import build_graph, export_graph_mermaid, write_summary

DEFAULT_TICKERS = ["COST", "HIMS", "SMCI", "JNJ", "TSLA"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the StockTrader LangGraph workflow.")
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
        help="Skip saving the Mermaid graph text used in the report.",
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
    tickers = [ticker.upper() for ticker in (args.tickers or DEFAULT_TICKERS)]

    if args.verify_setup:
        verify_setup(args.model)
        return

    if args.market_only:
        market_only_run(tickers)
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
