from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _value_tokens(value: Any) -> set[str]:
    if isinstance(value, float):
        return {
            str(value),
            f"`{value}`",
            f"{value:g}",
            f"`{value:g}`",
            f"{value:.4f}",
            f"`{value:.4f}`",
            f"{value * 100:.1f}%",
            f"`{value * 100:.1f}%`",
        }
    return {str(value), f"`{value}`"}


def _contains_value(report: str, value: Any) -> bool:
    return any(token in report for token in _value_tokens(value))


def check_report_consistency(
    report_path: Path | str,
    run_dir: Path | str,
    *,
    suite_summary_path: Path | str | None = None,
) -> dict[str, Any]:
    report = Path(report_path).read_text(encoding="utf-8")
    summary = json.loads((Path(run_dir) / "summary.json").read_text(encoding="utf-8"))
    missing_values: list[dict[str, Any]] = []

    for key in [
        "selective_risk",
        "abstention_gain",
        "majority_expected_calibration_error",
        "executed_expected_calibration_error",
        "intervention_rate",
        "review_rate",
        "worst_regime_error",
    ]:
        if key not in summary["headline_metrics"]:
            continue
        value = summary["headline_metrics"][key]
        if not _contains_value(report, value):
            missing_values.append({"field": f"headline_metrics.{key}", "value": value})

    if summary.get("abstention_curve"):
        best = max(summary["abstention_curve"], key=lambda row: row.get("abstention_gain", float("-inf")))
        for key in ["threshold", "abstention_gain"]:
            value = best.get(key)
            if value is not None and not _contains_value(report, value):
                missing_values.append({"field": f"abstention_curve.best.{key}", "value": value})

    for row in summary.get("regime_table", []):
        if row["regime_label"] not in report:
            missing_values.append({"field": "regime_table.regime_label", "value": row["regime_label"]})

    if suite_summary_path is not None and Path(suite_summary_path).exists():
        suite_summary = json.loads(Path(suite_summary_path).read_text(encoding="utf-8"))
        progress_token = f"{suite_summary['completed_run_count']}/{suite_summary['planned_run_count']}"
        if progress_token not in report and f"`{progress_token}`" not in report:
            missing_values.append({"field": "publication_suite.completion", "value": progress_token})

    return {
        "status": "pass" if not missing_values else "fail",
        "report_path": str(report_path),
        "run_dir": str(run_dir),
        "suite_summary_path": str(suite_summary_path) if suite_summary_path is not None else None,
        "missing_values": missing_values,
    }
