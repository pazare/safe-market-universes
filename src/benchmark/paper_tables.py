from __future__ import annotations

import json
from pathlib import Path
from typing import Any


HEADLINE_LABELS = {
    "executed_coverage": "Executed coverage",
    "non_hold_action_rate": "Non-HOLD action rate",
    "selective_risk": "Selective risk",
    "executed_action_risk": "Executed-action risk",
    "always_act_risk": "Always-act risk",
    "abstention_gain": "Abstention gain",
    "majority_expected_calibration_error": "Majority-vote ECE",
    "executed_expected_calibration_error": "Executed-action ECE",
    "intervention_rate": "Intervention rate",
    "utility_per_intervention": "Utility per intervention",
    "review_rate": "Review rate",
    "worst_regime_error": "Worst-regime error",
}
PERCENT_METRICS = {
    "executed_coverage",
    "non_hold_action_rate",
    "selective_risk",
    "executed_action_risk",
    "always_act_risk",
    "intervention_rate",
    "review_rate",
    "worst_regime_error",
}


def _load_summary(run_dir: Path) -> dict[str, Any]:
    return json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))


def _format_value(value: Any, *, percent: bool = False) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        if percent:
            return f"{value * 100:.1f}%"
        return f"{value:.4f}"
    return str(value)


def _write_headline_metrics(summary: dict[str, Any], output_dir: Path) -> Path:
    metrics = summary["headline_metrics"]
    lines = ["| Metric | Value |", "| --- | ---: |"]
    for key, label in HEADLINE_LABELS.items():
        if key in metrics:
            lines.append(f"| {label} | `{_format_value(metrics[key], percent=key in PERCENT_METRICS)}` |")
    path = output_dir / "headline_metrics.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _write_regime_table(summary: dict[str, Any], output_dir: Path) -> Path:
    lines = [
        "| Regime | Steps | Avg reward | Majority error | Executed error | Review rate |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary.get("regime_table", []):
        lines.append(
            "| {regime_label} | {steps} | {average_reward:.4f} | {majority_error} | {executed_error} | {review_rate} |".format(
                regime_label=row["regime_label"],
                steps=row["steps"],
                average_reward=row["average_reward"],
                majority_error=f"{row['majority_error_rate'] * 100:.1f}%",
                executed_error=f"{row['executed_error_rate'] * 100:.1f}%",
                review_rate=f"{row['review_rate'] * 100:.1f}%",
            )
        )
    path = output_dir / "regime_table.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _write_experimental_matrix(summary: dict[str, Any], output_dir: Path) -> Path:
    lines = [
        "| Policy | Coverage | Error rate | Average reward | FP rate | FN rate |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary.get("experimental_matrix", []):
        lines.append(
            "| {label} | {coverage} | {error_rate} | {average_reward:.4f} | {false_positive_rate} | {false_negative_rate} |".format(
                label=row["label"],
                coverage="n/a" if row.get("coverage") is None else f"{row['coverage'] * 100:.1f}%",
                error_rate="n/a" if row.get("error_rate") is None else f"{row['error_rate'] * 100:.1f}%",
                average_reward=row["average_reward"],
                false_positive_rate="n/a"
                if row.get("false_positive_rate") is None
                else f"{row['false_positive_rate'] * 100:.1f}%",
                false_negative_rate="n/a"
                if row.get("false_negative_rate") is None
                else f"{row['false_negative_rate'] * 100:.1f}%",
            )
        )
    path = output_dir / "experimental_matrix.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def export_paper_tables(run_dir: Path | str, output_dir: Path | str) -> list[Path]:
    run_path = Path(run_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    summary = _load_summary(run_path)
    return [
        _write_headline_metrics(summary, output_path),
        _write_regime_table(summary, output_path),
        _write_experimental_matrix(summary, output_path),
    ]
