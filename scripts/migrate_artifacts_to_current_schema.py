from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.benchmark.artifact_validation import validate_artifact_contract
from src.benchmark.artifact_paths import portable_path
from src.benchmark.metrics import (
    build_abstention_curve,
    build_experimental_matrix,
    build_failure_gallery,
    build_oversight_budget_curve,
    summarize_corruption,
    summarize_regimes,
)
from src.benchmark.model_registry import load_model_registry
from src.benchmark.runtime import (
    _build_gold_slice_rows,
    _gold_slice_rubric,
    _gold_slice_template_csv,
    _headline_metrics,
    _select_records_for_audit,
)
from src.benchmark.spec import (
    ARTIFACT_SCHEMA_VERSION,
    BENCHMARK_NAME,
    BENCHMARK_THESIS,
    DATA_SOURCE_NOTICE,
    FAILURE_GALLERY_LIMIT,
    GOLD_SLICE_TARGET,
    METRIC_DEFINITIONS,
    OVERSIGHT_BUDGETS,
)
from src.benchmark.statistics import bootstrap_metric_intervals


def _replace_legacy_labels(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _replace_legacy_labels(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_legacy_labels(item) for item in value]
    if value == "unclassified":
        return "mixed_transition_residual"
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(_replace_legacy_labels(json.loads(line)))
    return rows


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _rewrite_progress_file(run_path: Path) -> None:
    progress_path = run_path / "progress.json"
    if not progress_path.exists():
        return
    progress = json.loads(progress_path.read_text(encoding="utf-8"))
    if "summary_json" in progress:
        progress["summary_json"] = portable_path(run_path / "summary.json")
    _write_json(progress_path, progress)


def _rewrite_structured_files(run_dir: Path) -> None:
    for path in run_dir.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix == ".json":
            _write_json(path, _replace_legacy_labels(json.loads(path.read_text(encoding="utf-8"))))
        elif path.suffix == ".jsonl":
            _write_jsonl(path, _read_jsonl(path))
        elif path.suffix in {".md", ".csv"}:
            text = path.read_text(encoding="utf-8").replace("unclassified", "mixed_transition_residual")
            path.write_text(text, encoding="utf-8")


def _model_registry_summary() -> dict[str, Any]:
    try:
        registry = load_model_registry()
    except Exception as exc:
        return {"status": "unavailable", "reason": f"{type(exc).__name__}: {exc}"}
    return {
        "status": "configured",
        "default_models": [item["model"] for item in registry["default_models"]],
        "policy": registry.get("policy", {}),
    }


def migrate_run_dir(run_dir: Path | str) -> dict[str, Any]:
    run_path = Path(run_dir)
    _rewrite_structured_files(run_path)
    _rewrite_progress_file(run_path)

    old_summary = json.loads((run_path / "summary.json").read_text(encoding="utf-8"))
    records = _read_jsonl(run_path / "trajectories.jsonl")
    episode_paths = sorted((run_path / "episodes").glob("*.json"))
    episodes = [
        _replace_legacy_labels(json.loads(path.read_text(encoding="utf-8")))
        for path in episode_paths
    ]
    oversight_budget_curve = build_oversight_budget_curve(episodes, OVERSIGHT_BUDGETS)
    audit_candidates = _select_records_for_audit(records, GOLD_SLICE_TARGET)
    gold_slice_rows = _build_gold_slice_rows(records, GOLD_SLICE_TARGET)
    failure_gallery = build_failure_gallery(records, limit=FAILURE_GALLERY_LIMIT)

    summary = {
        **old_summary,
        "benchmark_name": old_summary.get("benchmark_name", BENCHMARK_NAME),
        "thesis": old_summary.get("thesis", BENCHMARK_THESIS),
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "episode_count": len(episodes),
        "step_count": len(records),
        "tickers": sorted({record["ticker"] for record in records}),
        "model_registry": _model_registry_summary(),
        "data_source_notice": DATA_SOURCE_NOTICE,
        "metric_definitions": METRIC_DEFINITIONS,
        "confidence_intervals": bootstrap_metric_intervals(records),
        "artifact_validation": {"status": "not_run"},
        "experimental_matrix": build_experimental_matrix(records, oversight_budget_curve),
        "headline_metrics": _headline_metrics(records, episodes),
        "abstention_curve": build_abstention_curve(records),
        "oversight_budget_curve": oversight_budget_curve,
        "regime_table": summarize_regimes(records),
        "corruption_comparison": summarize_corruption(records),
        "failure_gallery": failure_gallery,
        "audit_manifest": {
            "model_judged_steps": old_summary.get("audit_manifest", {}).get("model_judged_steps", 0),
            "human_audit_target_steps": len(audit_candidates),
            "human_audit_candidate_count": len(audit_candidates),
        },
        "artifacts": {
            "run_dir": portable_path(run_path),
            "summary_json": portable_path(run_path / "summary.json"),
            "progress_json": portable_path(run_path / "progress.json"),
            "episode_specs_json": portable_path(run_path / "episode_specs.json"),
            "trajectories_jsonl": portable_path(run_path / "trajectories.jsonl"),
            "human_audit_candidates_jsonl": portable_path(run_path / "human_audit_candidates.jsonl"),
            "gold_slice_jsonl": portable_path(run_path / "gold_slice_candidates.jsonl"),
            "gold_slice_template_csv": portable_path(run_path / "gold_slice_review_template.csv"),
            "gold_slice_rubric_md": portable_path(run_path / "gold_slice_rubric.md"),
            "failure_gallery_json": portable_path(run_path / "failure_gallery.json"),
        },
    }

    _write_json(run_path / "failure_gallery.json", failure_gallery)
    _write_jsonl(run_path / "human_audit_candidates.jsonl", audit_candidates)
    _write_jsonl(run_path / "gold_slice_candidates.jsonl", gold_slice_rows)
    (run_path / "gold_slice_review_template.csv").write_text(
        _gold_slice_template_csv(gold_slice_rows),
        encoding="utf-8",
    )
    (run_path / "gold_slice_rubric.md").write_text(_gold_slice_rubric(), encoding="utf-8")
    _write_json(run_path / "summary.json", summary)
    summary["artifact_validation"] = validate_artifact_contract(run_path)
    _write_json(run_path / "summary.json", summary)
    return summary["artifact_validation"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate generated benchmark artifacts to the current schema.")
    parser.add_argument("run_dir", nargs="?", default="outputs/benchmark/smu_headline_v1")
    args = parser.parse_args()

    print(json.dumps(migrate_run_dir(args.run_dir), indent=2))


if __name__ == "__main__":
    main()
