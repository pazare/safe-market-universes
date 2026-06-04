from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _render_abstention_curve(summary: dict, output_dir: Path) -> None:
    curve = summary.get("abstention_curve", [])
    if not curve:
        return

    thresholds = [row["threshold"] for row in curve]
    coverage = [row["coverage"] for row in curve]
    risk = [row["selective_risk"] for row in curve]

    plt.figure(figsize=(7, 4.5))
    plt.plot(coverage, risk, marker="o", linewidth=2, color="#0f766e")
    baseline = summary.get("headline_metrics", {}).get("always_act_risk")
    if isinstance(baseline, int | float):
        plt.axhline(baseline, color="#6b7280", linestyle="--", linewidth=1.4, label="Always-act risk")
    for threshold, x_val, y_val in zip(thresholds, coverage, risk, strict=False):
        plt.annotate(f"{threshold:.1f}", (x_val, y_val), textcoords="offset points", xytext=(5, 7), fontsize=8)
    plt.xlabel("Coverage")
    plt.ylabel("Majority risk at reliability threshold")
    plt.title("Abstention Risk-Coverage Curve")
    if isinstance(baseline, int | float):
        plt.legend(loc="best")
    plt.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(output_dir / "abstention_curve.png", dpi=200)
    plt.close()


def _render_oversight_budget_curve(summary: dict, output_dir: Path) -> None:
    rows = summary.get("oversight_budget_curve", [])
    if not rows:
        return

    budgets = [int(row["budget"]) for row in rows]
    rewards = [row["average_reward"] for row in rows]
    false_positive = [row["false_positive_rate"] for row in rows]
    false_negative = [row["false_negative_rate"] for row in rows]

    fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))
    axes[0].plot(budgets, rewards, marker="o", linewidth=2, color="#1d4ed8")
    axes[0].set_xlabel("Oversight budget")
    axes[0].set_ylabel("Average reward per step")
    axes[0].set_title("Reward")
    axes[0].grid(alpha=0.25)

    axes[1].plot(budgets, false_positive, marker="s", linestyle="--", color="#b91c1c", label="False positive")
    axes[1].plot(budgets, false_negative, marker="^", linestyle=":", color="#a16207", label="False negative")
    axes[1].set_xlabel("Oversight budget")
    axes[1].set_ylabel("Rate")
    axes[1].set_title("Oversight errors")
    axes[1].legend(loc="best")
    axes[1].grid(alpha=0.25)

    fig.suptitle("Oversight Budget Tradeoff (Descriptive Replay)")

    plt.tight_layout()
    plt.savefig(output_dir / "oversight_budget_curve.png", dpi=200)
    plt.close()


def _render_corruption_comparison(summary: dict, output_dir: Path) -> None:
    rows = summary.get("corruption_comparison", [])
    if not rows:
        return

    labels = [row["slice"] for row in rows]
    rewards = [row["average_reward"] for row in rows]
    majority_errors = [row["majority_error_rate"] for row in rows]
    executed_errors = [row.get("executed_error_rate", row["majority_error_rate"]) for row in rows]
    review_rates = [row["review_rate"] for row in rows]

    fig, axes = plt.subplots(1, 3, figsize=(12, 4.2))
    axes[0].bar(labels, rewards, color=["#2563eb", "#dc2626"])
    axes[0].set_title("Average Reward")
    axes[0].grid(axis="y", alpha=0.25)

    width = 0.35
    x_pos = range(len(labels))
    axes[1].bar([x - width / 2 for x in x_pos], majority_errors, width=width, color="#2563eb", label="Majority")
    axes[1].bar([x + width / 2 for x in x_pos], executed_errors, width=width, color="#dc2626", label="Executed")
    axes[1].set_xticks(list(x_pos), labels)
    axes[1].set_title("Error Rate")
    axes[1].legend(loc="best")
    axes[1].grid(axis="y", alpha=0.25)

    axes[2].bar(labels, review_rates, color=["#2563eb", "#dc2626"])
    axes[2].set_title("Review Rate")
    axes[2].grid(axis="y", alpha=0.25)

    fig.suptitle("Corruption Comparison")
    plt.tight_layout()
    plt.savefig(output_dir / "corruption_comparison.png", dpi=200)
    plt.close()


def _write_regime_table(summary: dict, output_dir: Path) -> None:
    rows = summary.get("regime_table", [])
    if not rows:
        return

    lines = [
        "| Regime | Steps | Avg reward | Majority error | Executed error | Review rate |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        row_payload = dict(row)
        row_payload["executed_error_rate"] = row.get("executed_error_rate", row["majority_error_rate"])
        lines.append(
            "| {regime_label} | {steps} | {average_reward:.4f} | {majority_error_rate:.4f} | {executed_error_rate:.4f} | {review_rate:.4f} |".format(
                **row_payload,
            )
        )
    (output_dir / "regime_table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Render benchmark figures from summary.json.")
    parser.add_argument(
        "run_dir",
        nargs="?",
        default="outputs/benchmark/smu_headline_v1",
        help="Benchmark run directory containing summary.json.",
    )
    parser.add_argument(
        "--output-dir",
        help="Optional override for the figure output directory.",
    )
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    output_dir = Path(args.output_dir) if args.output_dir else Path("report/figures") / run_dir.name
    output_dir.mkdir(parents=True, exist_ok=True)

    summary = _load_json(run_dir / "summary.json")
    _render_abstention_curve(summary, output_dir)
    _render_oversight_budget_curve(summary, output_dir)
    _render_corruption_comparison(summary, output_dir)
    _write_regime_table(summary, output_dir)

    print(f"Rendered figures in {output_dir}")


if __name__ == "__main__":
    main()
