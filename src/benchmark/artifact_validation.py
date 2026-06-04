from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .models import StepRecord


REQUIRED_ARTIFACTS = [
    "benchmark_config.json",
    "progress.json",
    "summary.json",
    "episode_specs.json",
    "trajectories.jsonl",
    "human_audit_candidates.jsonl",
    "gold_slice_candidates.jsonl",
    "gold_slice_review_template.csv",
    "gold_slice_rubric.md",
    "failure_gallery.json",
]

REQUIRED_HEADLINE_METRICS = {
    "executed_coverage",
    "selective_risk",
    "executed_action_risk",
    "always_act_risk",
    "abstention_gain",
    "majority_expected_calibration_error",
    "executed_expected_calibration_error",
    "intervention_rate",
    "review_rate",
    "worst_regime_error",
    "action_distribution",
    "non_hold_action_rate",
    "total_reward",
    "utility_per_intervention",
}

REQUIRED_POLICIES = {
    "committee_only",
    "committee_plus_abstention",
    "committee_plus_abstention_plus_overseer",
    "technical_rule_baseline",
    "overseer_budget_0",
    "overseer_budget_1",
    "overseer_budget_2",
}

REQUIRED_SUMMARY_FIELDS = {
    "schema_version",
    "metric_definitions",
    "confidence_intervals",
    "artifact_validation",
    "model_registry",
    "data_source_notice",
}


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _scan_for_unclassified(run_dir: Path) -> None:
    for path in run_dir.rglob("*"):
        if path.is_file() and path.suffix in {".json", ".jsonl", ".md", ".csv"}:
            text = path.read_text(encoding="utf-8")
            if "unclassified" in text:
                raise ValueError(f"Stale regime label 'unclassified' found in {path}")


def _validate_required_files(run_dir: Path) -> list[str]:
    missing = [name for name in REQUIRED_ARTIFACTS if not (run_dir / name).exists()]
    if missing:
        raise ValueError(f"Missing required artifact files: {', '.join(missing)}")
    return missing


def _validate_summary(summary: dict[str, Any]) -> None:
    missing_fields = sorted(REQUIRED_SUMMARY_FIELDS - set(summary))
    if missing_fields:
        raise ValueError(f"summary.json missing required publication fields: {', '.join(missing_fields)}")

    missing_metrics = sorted(REQUIRED_HEADLINE_METRICS - set(summary.get("headline_metrics", {})))
    if missing_metrics:
        raise ValueError(f"summary.json missing required headline metrics: {', '.join(missing_metrics)}")

    policies = {row.get("policy") for row in summary.get("experimental_matrix", [])}
    missing_policies = sorted(REQUIRED_POLICIES - policies)
    if missing_policies:
        raise ValueError(f"summary.json missing required experimental policies: {', '.join(missing_policies)}")

    if any(row.get("regime_label") == "unclassified" for row in summary.get("regime_table", [])):
        raise ValueError("summary.json contains stale regime label 'unclassified'")


def _round4(value: float) -> float:
    return round(float(value), 4)


def _validate_progress(progress: dict[str, Any], summary: dict[str, Any], records: list[dict[str, Any]], episode_specs: list[dict[str, Any]]) -> None:
    if progress.get("status") != "complete":
        raise ValueError(f"progress.json status must be complete, found {progress.get('status')!r}")

    if progress.get("run_id") != summary.get("run_id"):
        raise ValueError("progress.json run_id does not match summary.json run_id")

    if progress.get("completed_steps") != len(records) or progress.get("expected_steps") != len(records):
        raise ValueError("progress.json step counts do not match trajectories rows")

    if (
        progress.get("completed_episodes") != len(episode_specs)
        or progress.get("total_episodes") != len(episode_specs)
    ):
        raise ValueError("progress.json episode counts do not match episode_specs.json")


def _validate_episode_specs(summary: dict[str, Any], episode_specs: Any) -> list[dict[str, Any]]:
    if not isinstance(episode_specs, list):
        raise ValueError("episode_specs.json must contain a list")

    if summary.get("episode_count") != len(episode_specs):
        raise ValueError(
            f"summary episode_count {summary.get('episode_count')} does not match episode_specs rows {len(episode_specs)}"
        )

    episode_ids = [spec.get("episode_id") for spec in episode_specs]
    if any(not episode_id for episode_id in episode_ids):
        raise ValueError("episode_specs.json contains an episode without episode_id")
    if len(set(episode_ids)) != len(episode_ids):
        raise ValueError("episode_specs.json contains duplicate episode_id values")

    return episode_specs


def _validate_episode_files(run_dir: Path, episode_specs: list[dict[str, Any]], records: list[dict[str, Any]]) -> None:
    episodes_dir = run_dir / "episodes"
    if not episodes_dir.exists():
        raise ValueError("Missing required episodes directory")

    expected_ids = {spec["episode_id"] for spec in episode_specs}
    episode_files = {path.stem: path for path in episodes_dir.glob("*.json")}
    missing_files = sorted(expected_ids - set(episode_files))
    unexpected_files = sorted(set(episode_files) - expected_ids)
    if missing_files:
        raise ValueError(f"Missing episode artifact files: {', '.join(missing_files)}")
    if unexpected_files:
        raise ValueError(f"Unexpected episode artifact files: {', '.join(unexpected_files)}")

    records_by_episode = Counter(record["episode_id"] for record in records)
    specs_by_id = {spec["episode_id"]: spec for spec in episode_specs}
    for episode_id, path in episode_files.items():
        episode = _load_json(path)
        if episode.get("episode_spec", {}).get("episode_id") != episode_id:
            raise ValueError(f"{path.name} episode_spec.episode_id does not match filename")
        step_count = len(episode.get("steps", []))
        if step_count != records_by_episode[episode_id]:
            raise ValueError(f"{path.name} step count does not match trajectories rows")
        horizon = specs_by_id[episode_id].get("horizon")
        if horizon is not None and step_count != horizon:
            raise ValueError(f"{path.name} step count {step_count} does not match episode horizon {horizon}")


def _validate_config(config: dict[str, Any], summary: dict[str, Any], records: list[dict[str, Any]]) -> None:
    if config.get("benchmark_name") != summary.get("benchmark_name"):
        raise ValueError("benchmark_config.json benchmark_name does not match summary.json")

    if config.get("episode_count") != summary.get("episode_count"):
        raise ValueError("benchmark_config.json episode_count does not match summary.json")

    expected_tickers = sorted({record["ticker"] for record in records})
    if sorted(summary.get("tickers", [])) != expected_tickers:
        raise ValueError("summary tickers do not match trajectories tickers")

    if sorted(config.get("tickers", [])) != expected_tickers:
        raise ValueError("benchmark_config.json tickers do not match trajectories tickers")


def _validate_metric_consistency(summary: dict[str, Any], records: list[dict[str, Any]]) -> None:
    headline = summary["headline_metrics"]
    action_counts = dict(sorted(Counter(record["executed_action"] for record in records).items()))
    record_count = max(len(records), 1)
    if headline.get("action_distribution") != action_counts:
        raise ValueError("headline_metrics.action_distribution does not match trajectories")

    non_hold_count = sum(1 for record in records if record["executed_action"] in {"BUY", "SELL"})
    expected_non_hold_rate = _round4(non_hold_count / record_count)
    if headline.get("non_hold_action_rate") != expected_non_hold_rate:
        raise ValueError("headline_metrics.non_hold_action_rate does not match trajectories")

    total_reward = _round4(sum(record["reward"] for record in records))
    if headline.get("total_reward") != total_reward:
        raise ValueError("headline_metrics.total_reward does not match trajectories")

    interventions = sum(1 for record in records if record.get("overseer", {}).get("intervention_used"))
    expected_utility = _round4(total_reward / interventions) if interventions else None
    if headline.get("utility_per_intervention") != expected_utility:
        raise ValueError("headline_metrics.utility_per_intervention does not match intervention count")
    if "total_reward_per_intervention" in headline and headline.get("total_reward_per_intervention") != expected_utility:
        raise ValueError("headline_metrics.total_reward_per_intervention does not match intervention count")

    optional_rate_checks = {
        "abstain_rate": sum(1 for record in records if record["executed_action"] == "ABSTAIN"),
        "verify_rate": sum(1 for record in records if record["executed_action"] == "VERIFY"),
        "escalate_rate": sum(1 for record in records if record["executed_action"] == "ESCALATE"),
        "recommended_intervention_rate": sum(
            1 for record in records if record.get("overseer", {}).get("recommended_decision") != "approve"
        ),
        "spent_budget_rate": interventions,
        "budget_limited_rate": sum(1 for record in records if record.get("overseer", {}).get("budget_limited")),
    }
    for metric, count in optional_rate_checks.items():
        if metric in headline and headline.get(metric) != _round4(count / record_count):
            raise ValueError(f"headline_metrics.{metric} does not match trajectories")
    if "mean_reward_per_step" in headline and headline.get("mean_reward_per_step") != _round4(total_reward / record_count):
        raise ValueError("headline_metrics.mean_reward_per_step does not match trajectories")
    if "executed_selective_risk" in headline and headline.get("executed_selective_risk") != headline.get("selective_risk"):
        raise ValueError("headline_metrics.executed_selective_risk must match selective_risk")


def _validate_audit_artifacts(run_dir: Path, summary: dict[str, Any]) -> None:
    audit_manifest = summary.get("audit_manifest", {})
    human_candidates = _load_jsonl(run_dir / "human_audit_candidates.jsonl")
    gold_slice_candidates = _load_jsonl(run_dir / "gold_slice_candidates.jsonl")
    expected_human_rows = audit_manifest.get("human_audit_target_steps")

    if expected_human_rows is not None and len(human_candidates) != expected_human_rows:
        raise ValueError("human_audit_candidates.jsonl row count does not match audit_manifest")

    if expected_human_rows is not None and len(gold_slice_candidates) != expected_human_rows:
        raise ValueError("gold_slice_candidates.jsonl row count does not match audit_manifest")


def validate_artifact_contract(run_dir: Path | str) -> dict[str, Any]:
    run_path = Path(run_dir)
    _scan_for_unclassified(run_path)
    _validate_required_files(run_path)
    summary = _load_json(run_path / "summary.json")
    _validate_summary(summary)

    records = _load_jsonl(run_path / "trajectories.jsonl")
    for record in records:
        StepRecord.model_validate(record)

    if summary.get("step_count") != len(records):
        raise ValueError(
            f"summary step_count {summary.get('step_count')} does not match trajectories rows {len(records)}"
        )

    config = _load_json(run_path / "benchmark_config.json")
    progress = _load_json(run_path / "progress.json")
    episode_specs = _validate_episode_specs(summary, _load_json(run_path / "episode_specs.json"))
    _validate_progress(progress, summary, records, episode_specs)
    _validate_episode_files(run_path, episode_specs, records)
    _validate_config(config, summary, records)
    _validate_metric_consistency(summary, records)
    _validate_audit_artifacts(run_path, summary)

    return {
        "status": "pass",
        "run_id": summary.get("run_id"),
        "schema_version": summary.get("schema_version"),
        "step_count": len(records),
        "required_artifacts": REQUIRED_ARTIFACTS,
        "required_policies": sorted(REQUIRED_POLICIES),
    }
