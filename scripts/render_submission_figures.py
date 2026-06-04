from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np


def _load_json(path: Path | str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _percent_axis(ax) -> None:
    ax.set_ylim(0, 1)
    ax.set_yticks(np.linspace(0, 1, 6))
    ax.set_yticklabels([f"{int(value * 100)}%" for value in np.linspace(0, 1, 6)])


def _render_action_distribution(summary: dict[str, Any], output_dir: Path) -> None:
    counts = summary["headline_metrics"]["action_distribution"]
    labels = list(counts)
    values = [counts[label] for label in labels]
    colors = ["#2563eb" if label in {"BUY", "SELL"} else "#0f766e" if label == "HOLD" else "#7c3aed" for label in labels]

    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    bars = ax.bar(labels, values, color=colors)
    ax.set_title("Headline Run Action Distribution")
    ax.set_ylabel("Decision steps")
    ax.grid(axis="y", alpha=0.25)
    for bar, value in zip(bars, values, strict=False):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 4, str(value), ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    fig.savefig(output_dir / "action_distribution.png", dpi=220)
    plt.close(fig)


def _render_risk_coverage(summary: dict[str, Any], output_dir: Path) -> None:
    curve = summary.get("abstention_curve", [])
    coverage = [row["coverage"] for row in curve]
    risk = [row.get("majority_risk_at_reliability_threshold", row["selective_risk"]) for row in curve]
    thresholds = [row["threshold"] for row in curve]
    baseline = summary["headline_metrics"]["always_act_risk"]

    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    ax.plot(coverage, risk, marker="o", linewidth=2.2, color="#0f766e", label="Reliability threshold")
    ax.axhline(baseline, color="#6b7280", linestyle="--", linewidth=1.4, label="Always-act risk")
    for threshold, x_value, y_value in zip(thresholds, coverage, risk, strict=False):
        ax.annotate(f"{threshold:.1f}", (x_value, y_value), xytext=(5, 7), textcoords="offset points", fontsize=8)
    ax.set_xlabel("Coverage")
    ax.set_ylabel("Majority risk")
    ax.set_title("Risk-Coverage Diagnostic")
    _percent_axis(ax)
    ax.legend(loc="best")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_dir / "risk_coverage.png", dpi=220)
    plt.close(fig)


def _render_corruption_comparison(summary: dict[str, Any], output_dir: Path) -> None:
    rows = summary.get("corruption_comparison", [])
    labels = [row["slice"].title() for row in rows]
    majority = [row["majority_error_rate"] for row in rows]
    executed = [row["executed_error_rate"] for row in rows]
    review = [row["review_rate"] for row in rows]
    x_positions = np.arange(len(labels))
    width = 0.25

    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    ax.bar(x_positions - width, majority, width=width, label="Majority error", color="#1d4ed8")
    ax.bar(x_positions, executed, width=width, label="Executed error", color="#dc2626")
    ax.bar(x_positions + width, review, width=width, label="Review rate", color="#7c3aed")
    ax.set_xticks(x_positions, labels)
    ax.set_title("Corruption Stress Test")
    ax.set_ylabel("Rate")
    _percent_axis(ax)
    ax.legend(loc="best")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_dir / "corruption_error_review.png", dpi=220)
    plt.close(fig)


def _group_suite_conditions(suite: dict[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[tuple[int, bool], list[dict[str, Any]]] = defaultdict(list)
    for run in suite.get("completed_runs", []):
        grouped[(int(run["budget"]), bool(run["corruption_enabled"]))].append(run)

    rows: list[dict[str, Any]] = []
    for (budget, corrupted), runs in sorted(grouped.items()):
        metrics = [run["headline_metrics"] for run in runs]
        step_rewards = []
        for run in runs:
            step_count = run.get("step_count") or 0
            total_reward = run["headline_metrics"].get("total_reward")
            if step_count and isinstance(total_reward, int | float):
                step_rewards.append(float(total_reward) / float(step_count))
        rows.append(
            {
                "budget": budget,
                "corrupted": corrupted,
                "n": len(runs),
                "selective_risk": float(np.mean([row["selective_risk"] for row in metrics])),
                "review_rate": float(np.mean([row["review_rate"] for row in metrics])),
                "reward_per_step": float(np.mean(step_rewards)) if step_rewards else 0.0,
            }
        )
    return rows


def _render_suite_budget_grid(suite: dict[str, Any], output_dir: Path) -> None:
    rows = _group_suite_conditions(suite)
    budgets = sorted({row["budget"] for row in rows})
    clean = {row["budget"]: row for row in rows if not row["corrupted"]}
    corrupted = {row["budget"]: row for row in rows if row["corrupted"]}

    fig, axes = plt.subplots(1, 3, figsize=(12, 4.4))
    metrics = [
        ("selective_risk", "Selective risk", True),
        ("review_rate", "Review rate", True),
        ("reward_per_step", "Mean reward/step", False),
    ]
    x_positions = np.arange(len(budgets))
    width = 0.36

    for ax, (metric, title, percent) in zip(axes, metrics, strict=False):
        clean_values = [clean[budget][metric] for budget in budgets]
        corrupted_values = [corrupted[budget][metric] for budget in budgets]
        ax.bar(x_positions - width / 2, clean_values, width=width, label="Clean", color="#2563eb")
        ax.bar(x_positions + width / 2, corrupted_values, width=width, label="Corrupted", color="#dc2626")
        ax.set_xticks(x_positions, [str(budget) for budget in budgets])
        ax.set_xlabel("Oversight budget")
        ax.set_title(title)
        if percent:
            _percent_axis(ax)
        ax.grid(axis="y", alpha=0.25)
    axes[0].legend(loc="best")
    fig.suptitle("Completed gpt-5.4-mini Publication Cells (18/18)")
    fig.tight_layout()
    fig.savefig(output_dir / "suite_budget_grid.png", dpi=220)
    plt.close(fig)


def _render_regime_diagnostics(summary: dict[str, Any], output_dir: Path) -> None:
    rows = sorted(summary.get("regime_table", []), key=lambda row: row["majority_error_rate"], reverse=True)
    labels = [row["regime_label"].replace("_", "\n") for row in rows]
    majority = [row["majority_error_rate"] for row in rows]
    executed = [row["executed_error_rate"] for row in rows]
    review = [row["review_rate"] for row in rows]
    x_positions = np.arange(len(labels))
    width = 0.26

    fig, ax = plt.subplots(figsize=(10.5, 4.8))
    ax.bar(x_positions - width, majority, width=width, label="Majority error", color="#1d4ed8")
    ax.bar(x_positions, executed, width=width, label="Executed error", color="#dc2626")
    ax.bar(x_positions + width, review, width=width, label="Review rate", color="#7c3aed")
    ax.set_xticks(x_positions, labels)
    ax.set_title("Regime-Stratified Safety Diagnostics")
    ax.set_ylabel("Rate")
    _percent_axis(ax)
    ax.legend(loc="upper right")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_dir / "regime_diagnostics.png", dpi=220)
    plt.close(fig)


def _render_failure_taxonomy(summary: dict[str, Any], output_dir: Path) -> None:
    counts = summary["headline_metrics"].get("failure_counts", {})
    labels = [label.replace("_", "\n") for label in counts]
    values = [counts[label] for label in counts]

    fig, ax = plt.subplots(figsize=(8.4, 4.4))
    bars = ax.bar(labels, values, color="#b45309")
    ax.set_title("Interpretable Failure Taxonomy")
    ax.set_ylabel("Flagged steps")
    ax.grid(axis="y", alpha=0.25)
    for bar, value in zip(bars, values, strict=False):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.5, str(value), ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    fig.savefig(output_dir / "failure_taxonomy.png", dpi=220)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render submission-grade Safe MarketUniverses figures.")
    parser.add_argument("--headline-summary", default="outputs/benchmark/smu_headline_v1/summary.json")
    parser.add_argument("--suite-summary", default="outputs/benchmark/publication_suite_summary.json")
    parser.add_argument("--output-dir", default="report/figures/submission")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    headline = _load_json(args.headline_summary)
    suite = _load_json(args.suite_summary)
    _render_action_distribution(headline, output_dir)
    _render_risk_coverage(headline, output_dir)
    _render_corruption_comparison(headline, output_dir)
    _render_suite_budget_grid(suite, output_dir)
    _render_regime_diagnostics(headline, output_dir)
    _render_failure_taxonomy(headline, output_dir)
    print(f"Rendered submission figures in {output_dir}")


if __name__ == "__main__":
    main()
