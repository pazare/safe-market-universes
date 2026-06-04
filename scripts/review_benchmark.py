from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _format_percent(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.1f}%"


def _best_abstention_row(curve: list[dict]) -> dict | None:
    if not curve:
        return None
    return max(curve, key=lambda row: (row["abstention_gain"], row["coverage"]))


def main() -> None:
    parser = argparse.ArgumentParser(description="Print a reviewer-friendly summary for a benchmark run.")
    parser.add_argument(
        "run_dir",
        nargs="?",
        default="outputs/benchmark/smu_headline_v1",
        help="Benchmark run directory containing summary.json.",
    )
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    summary = _load_json(run_dir / "summary.json")
    failure_gallery = _load_json(run_dir / "failure_gallery.json")

    print(summary["benchmark_name"])
    print(summary["thesis"])
    print()
    print(f"Run ID: {summary['run_id']}")
    print(f"Episodes: {summary['episode_count']} | Steps: {summary['step_count']}")
    print(f"Tickers: {', '.join(summary['tickers'])}")
    print()

    metrics = summary["headline_metrics"]
    print("Headline metrics")
    print(f"- Executed coverage: {_format_percent(metrics['executed_coverage'])}")
    print(f"- Selective risk: {_format_percent(metrics['selective_risk'])}")
    print(f"- Abstention gain: {metrics['abstention_gain']:+.4f}")
    if "majority_expected_calibration_error" in metrics:
        print(f"- Majority-vote ECE: {metrics['majority_expected_calibration_error']:.4f}")
    elif "expected_calibration_error" in metrics:
        print(f"- Majority-vote ECE: {metrics['expected_calibration_error']:.4f}")
    if "executed_expected_calibration_error" in metrics:
        print(f"- Executed-action ECE: {metrics['executed_expected_calibration_error']:.4f}")
    print(f"- Intervention rate: {_format_percent(metrics['intervention_rate'])}")
    print(f"- Review rate: {_format_percent(metrics['review_rate'])}")
    print(f"- Worst-regime error: {_format_percent(metrics['worst_regime_error'])}")
    print()

    best_curve_row = _best_abstention_row(summary.get("abstention_curve", []))
    if best_curve_row:
        print("Best abstention operating point")
        print(
            f"- Threshold {best_curve_row['threshold']:.2f}: "
            f"coverage {_format_percent(best_curve_row['coverage'])}, "
            f"selective risk {_format_percent(best_curve_row['selective_risk'])}, "
            f"gain {best_curve_row['abstention_gain']:+.4f}"
        )
        print()

    print("Experimental matrix")
    for row in summary.get("experimental_matrix", []):
        line = f"- {row['label']}: average reward {row['average_reward']:.4f}"
        if row.get("coverage") is not None:
            line += f", coverage {_format_percent(row['coverage'])}"
        if row.get("error_rate") is not None:
            line += f", error {_format_percent(row['error_rate'])}"
        if row.get("false_positive_rate") is not None:
            line += f", FP {_format_percent(row['false_positive_rate'])}"
        if row.get("false_negative_rate") is not None:
            line += f", FN {_format_percent(row['false_negative_rate'])}"
        print(line)
    print()

    print("Worst regimes")
    for row in sorted(summary.get("regime_table", []), key=lambda item: item["majority_error_rate"], reverse=True)[:3]:
        print(
            f"- {row['regime_label']}: "
            f"error {_format_percent(row['majority_error_rate'])}, "
            f"executed {_format_percent(row.get('executed_error_rate'))}, "
            f"reward {row['average_reward']:.4f}, "
            f"review {_format_percent(row['review_rate'])}"
        )
    print()

    print("Corruption comparison")
    for row in summary.get("corruption_comparison", []):
        print(
            f"- {row['slice']}: "
            f"error {_format_percent(row['majority_error_rate'])}, "
            f"executed {_format_percent(row.get('executed_error_rate'))}, "
            f"reward {row['average_reward']:.4f}, "
            f"review {_format_percent(row['review_rate'])}"
        )
    print()

    print("Failure gallery")
    for row in failure_gallery:
        print(
            f"- {row['ticker']} step {row['step_index']} on {row['as_of_date']}: "
            f"{', '.join(row['failure_labels']) or 'no labels'} | "
            f"action {row['executed_action']} vs outcome {row['realized_outcome']}"
        )
        print(f"  {row['summary']}")


if __name__ == "__main__":
    main()
