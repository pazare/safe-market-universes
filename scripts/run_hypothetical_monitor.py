from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.paper_deployment import DEFAULT_HYPOTHETICAL_TICKERS, PaperDeploymentConfig, run_hypothetical_monitor


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run paper-only hypothetical monitoring for the ML minimax-regret pipeline."
    )
    parser.add_argument("tickers", nargs="*", help="Synthetic ticker labels to include.")
    parser.add_argument("--iterations", type=int, default=4)
    parser.add_argument("--seed", type=int, default=20260620)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/hypothetical_monitor"))
    parser.add_argument("--max-drawdown-limit", type=float, default=0.12)
    parser.add_argument("--cvar-95-loss-limit", type=float, default=0.08)
    parser.add_argument("--mean-weighted-regret-limit", type=float, default=0.95)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = PaperDeploymentConfig(
        tickers=[ticker.upper() for ticker in (args.tickers or DEFAULT_HYPOTHETICAL_TICKERS)],
        iterations=args.iterations,
        seed=args.seed,
        output_dir=args.output_dir,
        max_drawdown_limit=args.max_drawdown_limit,
        cvar_95_loss_limit=args.cvar_95_loss_limit,
        mean_weighted_regret_limit=args.mean_weighted_regret_limit,
        paper_only=True,
    )
    summary_path = run_hypothetical_monitor(config)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    print(f"Saved paper-only hypothetical monitor summary at {summary_path}.")
    print(
        f"approved={summary['approved_iterations']} "
        f"blocked={summary['blocked_iterations']} "
        f"iterations={summary['iterations']}"
    )


if __name__ == "__main__":
    main()
