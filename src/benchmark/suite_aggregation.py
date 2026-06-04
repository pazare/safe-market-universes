from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from .artifact_paths import portable_path


METRICS_TO_AGGREGATE = [
    "selective_risk",
    "abstention_gain",
    "review_rate",
    "majority_expected_calibration_error",
    "executed_expected_calibration_error",
]


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def _metric_summary(values: list[float]) -> dict[str, float | int | None]:
    return {"mean": _mean(values), "n": len(values)}


def _load_summary(outputs_root: Path, run_id: str) -> dict[str, Any] | None:
    path = outputs_root / run_id / "summary.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _load_progress(outputs_root: Path, run_id: str) -> dict[str, Any] | None:
    path = outputs_root / run_id / "progress.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _progress_invalid_reason(progress: dict[str, Any]) -> str:
    status = str(progress.get("status", "unknown"))
    if status == "failed":
        error = str(progress.get("error") or "")
        error_type = str(progress.get("error_type") or "unknown_error")
        if "insufficient_quota" in error:
            return "progress_status_failed:external_api_insufficient_quota"
        return f"progress_status_failed:{error_type}"
    return f"progress_status_{status}"


def _validated_completion_status(outputs_root: Path, run: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    run_id = run["run_id"]
    summary = _load_summary(outputs_root, run_id)
    if summary is None:
        progress = _load_progress(outputs_root, run_id)
        if progress is None:
            return None, "missing_summary"
        return None, _progress_invalid_reason(progress)
    if summary.get("run_id") != run_id:
        return None, "run_id_mismatch"
    if summary.get("schema_version") != "smu-artifact-v2":
        return None, "schema_version_mismatch"
    if summary.get("artifact_validation", {}).get("status") != "pass":
        return None, "artifact_validation_not_pass"
    progress = _load_progress(outputs_root, run_id)
    if progress is None:
        return None, "missing_progress"
    if progress.get("status") != "complete":
        return None, f"progress_status_{progress.get('status', 'unknown')}"
    return summary, None


def aggregate_publication_suite(manifest_path: Path | str, outputs_root: Path | str) -> dict[str, Any]:
    manifest_file = Path(manifest_path)
    output_path = Path(outputs_root)
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    completed: list[dict[str, Any]] = []
    missing_run_ids: list[str] = []
    invalid_run_ids: list[str] = []
    failed_run_ids: list[str] = []
    invalid_run_reasons: dict[str, str] = {}
    metric_values: dict[str, list[float]] = defaultdict(list)
    by_model: dict[str, dict[str, int]] = defaultdict(lambda: {"planned": 0, "completed": 0})
    by_budget: dict[str, dict[str, int]] = defaultdict(lambda: {"planned": 0, "completed": 0})
    by_corruption: dict[str, dict[str, int]] = defaultdict(lambda: {"planned": 0, "completed": 0})

    for run in manifest.get("runs", []):
        run_id = run["run_id"]
        model = run.get("model", "unknown")
        budget = str(run.get("budget", "unknown"))
        corruption = "corrupt_on" if run.get("corruption_enabled") else "corrupt_off"
        by_model[model]["planned"] += 1
        by_budget[budget]["planned"] += 1
        by_corruption[corruption]["planned"] += 1

        summary, invalid_reason = _validated_completion_status(output_path, run)
        if summary is None and invalid_reason == "missing_summary":
            missing_run_ids.append(run_id)
            continue
        if summary is None:
            invalid_run_ids.append(run_id)
            invalid_run_reasons[run_id] = invalid_reason or "invalid"
            if invalid_run_reasons[run_id].startswith("progress_status_failed"):
                failed_run_ids.append(run_id)
            continue

        by_model[model]["completed"] += 1
        by_budget[budget]["completed"] += 1
        by_corruption[corruption]["completed"] += 1
        completed.append(
            {
                "run_id": run_id,
                "model": model,
                "seed": run.get("seed"),
                "budget": run.get("budget"),
                "corruption_enabled": run.get("corruption_enabled"),
                "episode_count": summary.get("episode_count"),
                "step_count": summary.get("step_count"),
                "headline_metrics": summary.get("headline_metrics", {}),
            }
        )
        for metric in METRICS_TO_AGGREGATE:
            value = summary.get("headline_metrics", {}).get(metric)
            if isinstance(value, int | float):
                metric_values[metric].append(float(value))

    planned_count = int(manifest.get("planned_run_count", len(manifest.get("runs", []))))
    completed_count = len(completed)
    return {
        "manifest_path": portable_path(manifest_file),
        "outputs_root": portable_path(output_path),
        "planned_run_count": planned_count,
        "completed_run_count": completed_count,
        "completion_rate": round(completed_count / planned_count, 4) if planned_count else 0.0,
        "missing_run_ids": missing_run_ids,
        "invalid_run_ids": invalid_run_ids,
        "failed_run_ids": failed_run_ids,
        "invalid_run_reasons": invalid_run_reasons,
        "unavailable_models": manifest.get("unavailable_models", []),
        "completed_run_metric_means": {
            metric: _metric_summary(values)
            for metric, values in sorted(metric_values.items())
        },
        "metric_means": {metric: _mean(values) for metric, values in sorted(metric_values.items())},
        "by_model": dict(sorted(by_model.items())),
        "by_budget": dict(sorted(by_budget.items())),
        "by_corruption": dict(sorted(by_corruption.items())),
        "completed_runs": completed,
    }


def write_publication_suite_summary(
    manifest_path: Path | str,
    outputs_root: Path | str,
    output_path: Path | str,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = aggregate_publication_suite(manifest_path, outputs_root)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path
