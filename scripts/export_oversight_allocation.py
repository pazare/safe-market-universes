"""Export the flagship oversight-allocation results from existing benchmark logs.

Computes, with NO new model runs, the narrowed flagship:
  - allocation regret@K vs an oracle for {model_signal, rule_baseline, random}
  - precision / overreach / miss rates
  - corruption-split recall (does the model catch corrupted high-gain steps?)
  - honest committee-confidence ECE vs the hand-coded heuristic ECE

Primary evidence = the canonical headline run (smu_headline_v1, 120 episodes, with
clean and corrupted steps). Robustness = the 18 validated publication cells, pooled,
plus a per-seed regret breakdown.

Usage:
  python scripts/export_oversight_allocation.py
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.benchmark.oversight_allocation import (
    build_oversight_allocation_report,
    model_signal_score,
    allocator_summary,
)


def load_episodes(run_dir: Path) -> list[dict[str, Any]]:
    episodes_dir = run_dir / "episodes"
    if not episodes_dir.exists():
        return []
    episodes = []
    for path in sorted(episodes_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("steps"):
            episodes.append(data)
    return episodes


def load_cells(benchmark_dir: Path, pattern: str) -> dict[str, list[dict[str, Any]]]:
    cells: dict[str, list[dict[str, Any]]] = {}
    for run_dir in sorted(benchmark_dir.glob(pattern)):
        if not run_dir.is_dir():
            continue
        episodes = load_episodes(run_dir)
        if episodes:
            cells[run_dir.name] = episodes
    return cells


def _seed_of(cell_name: str) -> str:
    match = re.search(r"seed(\d+)", cell_name)
    return match.group(1) if match else "unknown"


def per_seed_model_regret(cells: dict[str, list[dict[str, Any]]], budget: int = 1) -> dict[str, Any]:
    by_seed: dict[str, list[dict[str, Any]]] = {}
    for name, episodes in cells.items():
        by_seed.setdefault(_seed_of(name), []).extend(episodes)
    rows = {}
    for seed, episodes in sorted(by_seed.items()):
        summary = allocator_summary(episodes, model_signal_score, budget)
        rows[seed] = summary["mean_regret_per_step"]
    values = list(rows.values())
    mean = round(sum(values) / len(values), 4) if values else 0.0
    spread = round((max(values) - min(values)), 4) if values else 0.0
    return {"budget": budget, "by_seed": rows, "mean": mean, "range": spread}


# --------------------------------------------------------------------------- #
# Figure
# --------------------------------------------------------------------------- #
def render_figure(report: dict[str, Any], output_path: Path) -> None:
    import matplotlib.pyplot as plt
    import numpy as np

    budgets = report["budgets"]
    allocators = ["model_signal", "rule_baseline", "random"]
    colors = {"model_signal": "#0f766e", "rule_baseline": "#6b7280", "random": "#dc2626"}
    labels = {"model_signal": "Model signal", "rule_baseline": "Rule baseline", "random": "Random"}

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.0, 4.6))

    # Left: regret-per-step vs budget K (lower is better; oracle == 0 reference)
    width = 0.25
    x = np.arange(len(budgets))
    for offset, name in zip((-width, 0.0, width), allocators):
        means = [report["allocators"][name][b]["mean_regret_per_step"] for b in budgets]
        lowers = [report["allocators"][name][b]["regret_ci_lower"] for b in budgets]
        uppers = [report["allocators"][name][b]["regret_ci_upper"] for b in budgets]
        yerr = [[m - lo for m, lo in zip(means, lowers)], [up - m for m, up in zip(means, uppers)]]
        ax1.bar(x + offset, means, width=width, label=labels[name], color=colors[name],
                yerr=yerr, capsize=3, error_kw={"elinewidth": 1, "alpha": 0.6})
    ax1.axhline(0.0, color="#111827", linewidth=1.2, linestyle="--", label="Oracle (regret 0)")
    ax1.set_xticks(x)
    ax1.set_xticklabels([f"K = {b}" for b in budgets])
    ax1.set_ylabel("Oversight allocation regret / step")
    ax1.set_title("Misspent oversight: regret vs. oracle (lower is better)")
    ax1.legend(loc="best", fontsize=8)
    ax1.grid(axis="y", alpha=0.25)

    # Right: model_signal recall on clean vs corrupted high-gain steps
    rec = report["corruption_recall"]["model_signal"]
    clean = [rec[b]["clean"]["recall"] or 0.0 for b in budgets]
    corrupt = [rec[b]["corrupted"]["recall"] or 0.0 for b in budgets]
    ax2.bar(x - width / 2, clean, width=width, label="Clean steps", color="#2563eb")
    ax2.bar(x + width / 2, corrupt, width=width, label="Corrupted steps", color="#b45309")
    ax2.set_xticks(x)
    ax2.set_xticklabels([f"K = {b}" for b in budgets])
    ax2.set_ylim(0, 1)
    ax2.set_yticks(np.linspace(0, 1, 6))
    ax2.set_yticklabels([f"{int(v*100)}%" for v in np.linspace(0, 1, 6)])
    ax2.set_ylabel("Recall of review-worthy steps")
    ax2.set_title("Recall of review-worthy steps: clean vs. corrupted")
    ax2.legend(loc="best", fontsize=8)
    ax2.grid(axis="y", alpha=0.25)

    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=220)
    plt.close(fig)


# --------------------------------------------------------------------------- #
# Markdown
# --------------------------------------------------------------------------- #
def _fmt(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def render_markdown(headline: dict[str, Any], suite: dict[str, Any], per_seed: dict[str, Any]) -> str:
    lines = [
        "# Safe MarketUniverses — Flagship Results: Misspent Oversight",
        "",
        "**Flagship question.** Whether, given a finite budget of human-review tokens per episode, "
        "the model's own expressed uncertainty allocates them to the decisions that actually "
        "warrant review when evidence may be corrupted. We report regret against an oracle that "
        "spends the same budget optimally, computable from hindsight utilities the model never sees.",
        "",
        f"Primary evidence: headline run with {headline['episodes']} episodes / {headline['steps']} steps. "
        f"Robustness: {suite['episodes']} pooled episodes across the 18 validated `gpt-5.4-mini` cells.",
        "",
        "## Calibration (model's own confidence vs. the hand-coded heuristic)",
        "",
        f"- Honest committee-confidence ECE: `{_fmt(headline['calibration']['committee_confidence_ece'])}`",
        f"- Hand-coded reliability-heuristic ECE: `{_fmt(headline['calibration']['heuristic_reliability_ece'])}`",
        "",
        "The heuristic-reliability ECE measures the hand-coded reliability formula, not the model; "
        "committee-confidence ECE is the model-intrinsic calibration measure and is the one reported here.",
        "",
        "## Allocation regret per step (lower is better; the oracle scores zero)",
        "",
        "| Allocator | " + " | ".join(f"K={b} regret" for b in headline["budgets"]) + " | "
        + " | ".join(f"K={b} precision@K" for b in headline["budgets"]) + " |",
        "|" + " --- |" + " ---: |" * (2 * len(headline["budgets"])),
    ]
    for name in ("model_signal", "rule_baseline", "random"):
        regrets = " | ".join(
            f"`{_fmt(headline['allocators'][name][b]['mean_regret_per_step'])}` "
            f"({_fmt(headline['allocators'][name][b]['regret_ci_lower'])}–{_fmt(headline['allocators'][name][b]['regret_ci_upper'])})"
            for b in headline["budgets"]
        )
        precs = " | ".join(f"`{_fmt(headline['allocators'][name][b]['mean_precision_at_k'])}`" for b in headline["budgets"])
        lines.append(f"| {name} | {regrets} | {precs} |")

    lines += [
        "",
        "## Robustness: 0/1 utility-free oracle (review-worthy iff committee majority wrong)",
        "",
        "Binary regret/step (lower is better) under an oracle that ignores utility magnitudes. The ranking changes under this objective: the hand-coded rule becomes the worst allocator, so the graded-oracle ranking reflects the utility weighting, and the objective-independent takeaway is that no fixed signal here approaches the oracle.",
        "",
        "| Allocator | " + " | ".join(f"K={b}" for b in headline["budgets"]) + " |",
        "|" + " --- |" + " ---: |" * len(headline["budgets"]),
    ]
    for name in ("model_signal", "rule_baseline", "random"):
        cells = " | ".join(
            f"`{_fmt(headline['robustness_binary_oracle'][name][b]['mean_binary_regret_per_step'])}`"
            for b in headline["budgets"]
        )
        lines.append(f"| {name} | {cells} |")

    lines += [
        "",
        "## Misspent-oversight decomposition (headline, model_signal)",
        "",
        "| Budget | Tokens spent | Overreach spends | Missed worthwhile | Overreach rate | Miss rate |",
        "| ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for b in headline["budgets"]:
        cell = headline["allocators"]["model_signal"][b]
        lines.append(
            f"| {b} | {cell['total_tokens_spent']} | {cell['total_overreach_spends']} | "
            f"{cell['total_missed_worthwhile']} | `{_fmt(cell['overreach_rate'])}` | `{_fmt(cell['miss_rate'])}` |"
        )

    lines += [
        "",
        "## Corruption split — recall of review-worthy steps (model_signal)",
        "",
        "| Budget | Clean recall | Corrupted recall |",
        "| ---: | ---: | ---: |",
    ]
    for b in headline["budgets"]:
        rec = headline["corruption_recall"]["model_signal"][b]
        lines.append(f"| {b} | `{_fmt(rec['clean']['recall'])}` | `{_fmt(rec['corrupted']['recall'])}` |")

    lines += [
        "",
        "## Robustness: per-seed model_signal regret (pooled cells, one-token budget)",
        "",
        "Per-seed regret per step is "
        + ", ".join(f"`{_fmt(v)}` for seed `{seed}`" for seed, v in per_seed["by_seed"].items())
        + f"; the mean is `{_fmt(per_seed['mean'])}` and the seed-to-seed range is `{_fmt(per_seed['range'])}`.",
        "",
        "## Validity notes",
        "",
    ]
    for note in headline["notes"]:
        lines.append(f"- {note}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Export flagship oversight-allocation results from existing logs.")
    parser.add_argument("--benchmark-dir", default="outputs/benchmark")
    parser.add_argument("--headline-run", default="smu_headline_v1")
    parser.add_argument("--suite-pattern", default="publication_gpt_5_4_mini_*")
    parser.add_argument("--output", default="report/oversight_allocation_results.md")
    parser.add_argument("--json-output", default="report/oversight_allocation_results.json")
    parser.add_argument("--figure", default="report/figures/submission/oversight_allocation.png")
    parser.add_argument("--budgets", default="1,2")
    args = parser.parse_args()

    benchmark_dir = Path(args.benchmark_dir)
    budgets = tuple(int(x) for x in args.budgets.split(","))

    headline_episodes = load_episodes(benchmark_dir / args.headline_run)
    if not headline_episodes:
        raise SystemExit(f"No headline episodes found under {benchmark_dir / args.headline_run}/episodes")
    headline_report = build_oversight_allocation_report(headline_episodes, budgets=budgets)

    cells = load_cells(benchmark_dir, args.suite_pattern)
    pooled = [episode for episodes in cells.values() for episode in episodes]
    suite_report = build_oversight_allocation_report(pooled, budgets=budgets) if pooled else headline_report
    per_seed = per_seed_model_regret(cells, budget=budgets[0]) if cells else {"budget": budgets[0], "by_seed": {}, "mean": 0.0, "range": 0.0}

    combined = {
        "headline_run": args.headline_run,
        "headline": headline_report,
        "suite": {
            "cells": sorted(cells),
            "report": suite_report,
            "per_seed_model_regret": per_seed,
        },
    }

    json_path = Path(args.json_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(combined, indent=2), encoding="utf-8")

    md_path = Path(args.output)
    md_path.write_text(render_markdown(headline_report, suite_report, per_seed), encoding="utf-8")

    render_figure(headline_report, Path(args.figure))

    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"Wrote {args.figure}")
    # quick console sanity line
    ms = headline_report["allocators"]["model_signal"][budgets[0]]["mean_regret_per_step"]
    rb = headline_report["allocators"]["rule_baseline"][budgets[0]]["mean_regret_per_step"]
    rnd = headline_report["allocators"]["random"][budgets[0]]["mean_regret_per_step"]
    print(f"[sanity K={budgets[0]}] regret/step  model_signal={ms}  rule_baseline={rb}  random={rnd}")


if __name__ == "__main__":
    main()
