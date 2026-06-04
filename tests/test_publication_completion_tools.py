from __future__ import annotations

import csv
import json
from pathlib import Path

from src.benchmark.human_audit import attach_human_audit_summary
from src.benchmark.publication_readiness import check_publication_readiness
from src.benchmark.suite_aggregation import aggregate_publication_suite
from scripts import build_human_audit_packet
from scripts.run_publication_suite import _annotate_run_statuses, _select_runs_for_execution


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _summary(run_id: str, selective_risk: float) -> dict:
    return {
        "run_id": run_id,
        "schema_version": "smu-artifact-v2",
        "artifact_validation": {"status": "pass"},
        "headline_metrics": {
            "selective_risk": selective_risk,
            "abstention_gain": 0.1,
            "review_rate": 0.2,
            "majority_expected_calibration_error": 0.3,
            "executed_expected_calibration_error": 0.4,
        },
    }


def test_aggregate_publication_suite_reports_missing_and_completed_runs(tmp_path: Path) -> None:
    manifest = {
        "planned_run_count": 2,
        "runs": [
            {
                "run_id": "run_a",
                "model": "gpt-5.4-mini",
                "seed": 1,
                "budget": 0,
                "corruption_enabled": False,
            },
            {
                "run_id": "run_b",
                "model": "gpt-5.4-mini",
                "seed": 1,
                "budget": 1,
                "corruption_enabled": True,
            },
        ],
        "unavailable_models": [],
    }
    manifest_path = tmp_path / "manifest.json"
    _write_json(manifest_path, manifest)
    _write_json(tmp_path / "outputs" / "run_a" / "summary.json", _summary("run_a", 0.25))
    _write_json(tmp_path / "outputs" / "run_a" / "progress.json", {"status": "complete"})

    report = aggregate_publication_suite(manifest_path, tmp_path / "outputs")

    assert report["planned_run_count"] == 2
    assert report["completed_run_count"] == 1
    assert report["missing_run_ids"] == ["run_b"]
    assert report["completed_run_metric_means"]["selective_risk"]["mean"] == 0.25
    assert report["completed_run_metric_means"]["selective_risk"]["n"] == 1


def test_aggregate_publication_suite_rejects_unvalidated_or_incomplete_runs(tmp_path: Path) -> None:
    manifest = {
        "planned_run_count": 2,
        "runs": [
            {"run_id": "bad_validation", "model": "m", "budget": 0, "corruption_enabled": False},
            {"run_id": "still_running", "model": "m", "budget": 0, "corruption_enabled": False},
        ],
        "unavailable_models": [],
    }
    manifest_path = tmp_path / "manifest.json"
    _write_json(manifest_path, manifest)
    bad_summary = _summary("bad_validation", 0.25)
    bad_summary["artifact_validation"] = {"status": "fail"}
    _write_json(tmp_path / "outputs" / "bad_validation" / "summary.json", bad_summary)
    _write_json(tmp_path / "outputs" / "bad_validation" / "progress.json", {"status": "complete"})
    _write_json(tmp_path / "outputs" / "still_running" / "summary.json", _summary("still_running", 0.5))
    _write_json(tmp_path / "outputs" / "still_running" / "progress.json", {"status": "running"})

    report = aggregate_publication_suite(manifest_path, tmp_path / "outputs")

    assert report["completed_run_count"] == 0
    assert report["invalid_run_ids"] == ["bad_validation", "still_running"]


def test_aggregate_publication_suite_reports_failed_progress_without_summary_as_invalid(tmp_path: Path) -> None:
    manifest = {
        "planned_run_count": 2,
        "runs": [
            {"run_id": "quota_failed", "model": "m", "budget": 0, "corruption_enabled": False},
            {"run_id": "never_started", "model": "m", "budget": 0, "corruption_enabled": False},
        ],
        "unavailable_models": [],
    }
    manifest_path = tmp_path / "manifest.json"
    _write_json(manifest_path, manifest)
    _write_json(
        tmp_path / "outputs" / "quota_failed" / "progress.json",
        {
            "status": "failed",
            "error_type": "RateLimitError",
            "error": "Error code: 429 - insufficient_quota",
        },
    )

    report = aggregate_publication_suite(manifest_path, tmp_path / "outputs")

    assert report["completed_run_count"] == 0
    assert report["missing_run_ids"] == ["never_started"]
    assert report["invalid_run_ids"] == ["quota_failed"]
    assert report["failed_run_ids"] == ["quota_failed"]
    assert report["invalid_run_reasons"]["quota_failed"] == (
        "progress_status_failed:external_api_insufficient_quota"
    )


def test_attach_human_audit_summary_updates_benchmark_summary(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    audit_dir = tmp_path / "audit"
    _write_json(run_dir / "summary.json", {"run_id": "run", "human_audit_summary": None})
    header = "episode_id,ticker,step_index,automated_audit_status,final_reviewer_status,adjudicated_status\n"
    (audit_dir / "reviewer_a.csv").parent.mkdir(parents=True)
    (audit_dir / "reviewer_a.csv").write_text(header + "e1,T,0,pass,pass,\n", encoding="utf-8")
    (audit_dir / "reviewer_b.csv").write_text(header + "e1,T,0,pass,pass,\n", encoding="utf-8")
    (audit_dir / "adjudication.csv").write_text(header + "e1,T,0,pass,,pass\n", encoding="utf-8")

    summary = attach_human_audit_summary(run_dir, audit_dir)

    assert summary["human_audit_summary"]["agreement"]["raw_agreement"] == 1.0
    persisted = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    assert persisted["human_audit_summary"]["model_vs_human_ready"] is True


def test_human_audit_summary_requires_complete_expected_adjudication(tmp_path: Path) -> None:
    _write_json(tmp_path / "run" / "summary.json", {"run_id": "run", "human_audit_summary": None})
    audit_dir = tmp_path / "audit"
    audit_dir.mkdir()
    header = "episode_id,ticker,step_index,automated_audit_status,final_reviewer_status,adjudicated_status\n"
    (audit_dir / "reviewer_a.csv").write_text(
        header + "e1,T,0,pass,pass,\ne2,T,1,needs_review,fail,\n",
        encoding="utf-8",
    )
    (audit_dir / "reviewer_b.csv").write_text(
        header + "e1,T,0,pass,pass,\ne2,T,1,needs_review,fail,\n",
        encoding="utf-8",
    )
    (audit_dir / "adjudication.csv").write_text(
        header + "e1,T,0,pass,,pass\ne2,T,1,needs_review,,\n",
        encoding="utf-8",
    )

    summary = attach_human_audit_summary(tmp_path / "run", audit_dir, expected_count=2)

    audit = summary["human_audit_summary"]
    assert audit["model_vs_human_ready"] is False
    assert audit["completion"]["reviewer_a_complete"] is True
    assert audit["completion"]["reviewer_b_complete"] is True
    assert audit["completion"]["adjudication_complete"] is False
    assert audit["completion"]["adjudicated_missing_count"] == 1


def _packet_record(episode_id: str, *, priority: int, failure_count: int) -> dict:
    return {
        "episode_id": episode_id,
        "ticker": "T",
        "step_index": 0,
        "as_of_date": "2024-01-02",
        "regime_label": "steady_large_cap",
        "corruption_active": False,
        "executed_action": "HOLD",
        "realized_outcome": "HOLD",
        "failure_labels": [f"failure_{idx}" for idx in range(failure_count)],
        "quality_assessment": {
            "final_audit_status": "pass",
            "human_audit_priority": priority,
        },
        "overseer": {"intervention_used": False},
        "committee_votes": {
            "a": {"confidence": 5},
            "b": {"confidence": 5},
            "c": {"confidence": 5},
        },
    }


def test_human_audit_packet_uses_canonical_candidate_file_order(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_json(run_dir / "summary.json", {"run_id": "run"})
    trajectory_rows = [
        _packet_record("rerank-first", priority=3, failure_count=3),
        _packet_record("candidate-first", priority=1, failure_count=0),
        _packet_record("candidate-second", priority=1, failure_count=0),
    ]
    canonical_candidates = [trajectory_rows[1], trajectory_rows[2]]
    _write_jsonl(run_dir / "trajectories.jsonl", trajectory_rows)
    _write_jsonl(run_dir / "human_audit_candidates.jsonl", canonical_candidates)

    selected = build_human_audit_packet._select_review_records(run_dir, sample_size=2)

    assert [row["episode_id"] for row in selected] == ["candidate-first", "candidate-second"]


def test_human_audit_reviewer_rows_include_blinded_evidence_without_audit_labels() -> None:
    record = _packet_record("review-evidence", priority=3, failure_count=2)
    record["observation"] = {
        "market_features": {"pct_change_30d": -7.5},
        "tool_evidence": {"trend_tool": {"status": "ok"}},
        "mandate": {"allowed_actions": ["BUY", "HOLD", "SELL"]},
        "previous_step_summary": {"executed_action": "HOLD"},
        "visible_events": ["earnings"],
    }
    record["abstention"] = {"reliability_score": 0.42, "recommend_abstain": True}
    record["overseer"] = {
        "decision": "verify",
        "final_action": "VERIFY",
        "rationale": "Low reliability requires review.",
        "intervention_used": True,
    }

    row = build_human_audit_packet._review_row(record)

    assert json.loads(row["market_features_json"]) == {"pct_change_30d": -7.5}
    assert json.loads(row["committee_votes_json"])["a"]["confidence"] == 5
    assert json.loads(row["abstention_json"])["reliability_score"] == 0.42
    assert json.loads(row["overseer_json"])["final_action"] == "VERIFY"
    assert "automated_audit_status" not in row
    assert "failure_labels" not in row


def test_human_audit_reviewer_instructions_define_blinded_protocol() -> None:
    instructions = build_human_audit_packet._reviewer_instructions(sample_size=60)

    assert "60 prioritized benchmark steps" in instructions
    assert "Do not look at adjudication.csv" in instructions
    assert "final_reviewer_status" in instructions
    assert "pass`, `needs_review`, or `fail" in instructions
    assert "automated audit status" in instructions


def test_human_audit_packet_preserves_existing_human_csvs_without_force(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    audit_dir = tmp_path / "audit"
    _write_json(run_dir / "summary.json", {"run_id": "run"})
    _write_jsonl(
        run_dir / "human_audit_candidates.jsonl",
        [_packet_record("preserve-me", priority=3, failure_count=1)],
    )
    audit_dir.mkdir()
    sentinels = {
        "reviewer_a.csv": "reviewer-a-human-labels\n",
        "reviewer_b.csv": "reviewer-b-human-labels\n",
        "adjudication.csv": "adjudicated-human-labels\n",
    }
    for filename, content in sentinels.items():
        (audit_dir / filename).write_text(content, encoding="utf-8")
    (audit_dir / "reviewer_instructions.md").write_text("stale instructions", encoding="utf-8")
    (audit_dir / "audit_packet_manifest.json").write_text("{}", encoding="utf-8")

    build_human_audit_packet.main(
        [str(run_dir), "--sample-size", "1", "--output-dir", str(audit_dir)]
    )

    for filename, content in sentinels.items():
        assert (audit_dir / filename).read_text(encoding="utf-8") == content
    assert "1 prioritized benchmark steps" in (audit_dir / "reviewer_instructions.md").read_text(
        encoding="utf-8"
    )
    manifest = json.loads((audit_dir / "audit_packet_manifest.json").read_text(encoding="utf-8"))
    assert manifest["sample_keys"][0]["episode_id"] == "preserve-me"


def test_human_audit_packet_force_overwrites_existing_human_csvs(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    audit_dir = tmp_path / "audit"
    _write_json(run_dir / "summary.json", {"run_id": "run"})
    _write_jsonl(
        run_dir / "human_audit_candidates.jsonl",
        [_packet_record("overwrite-me", priority=3, failure_count=1)],
    )
    audit_dir.mkdir()
    for filename in ["reviewer_a.csv", "reviewer_b.csv", "adjudication.csv"]:
        (audit_dir / filename).write_text("sentinel\n", encoding="utf-8")

    build_human_audit_packet.main(
        [str(run_dir), "--sample-size", "1", "--output-dir", str(audit_dir), "--force"]
    )

    with (audit_dir / "reviewer_a.csv").open(newline="", encoding="utf-8") as handle:
        reviewer_rows = list(csv.DictReader(handle))
    with (audit_dir / "adjudication.csv").open(newline="", encoding="utf-8") as handle:
        adjudication_rows = list(csv.DictReader(handle))

    assert reviewer_rows[0]["episode_id"] == "overwrite-me"
    assert reviewer_rows[0]["final_reviewer_status"] == ""
    assert "automated_audit_status" not in reviewer_rows[0]
    assert adjudication_rows[0]["episode_id"] == "overwrite-me"
    assert adjudication_rows[0]["automated_audit_status"] == "pass"
    assert adjudication_rows[0]["adjudicated_status"] == ""


def test_publication_readiness_distinguishes_required_and_external_work(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "summary.json",
        {
            "schema_version": "smu-artifact-v2",
            "artifact_validation": {"status": "pass"},
            "human_audit_summary": {"model_vs_human_ready": False},
        },
    )
    _write_json(
        tmp_path / "suite_summary.json",
        {
            "completed_run_count": 0,
            "planned_run_count": 54,
            "completion_rate": 0.0,
            "missing_run_ids": ["run_a"],
        },
    )

    report = check_publication_readiness(
        summary_path=tmp_path / "summary.json",
        suite_summary_path=tmp_path / "suite_summary.json",
        model_preflight_path=tmp_path / "missing_preflight.json",
    )

    assert report["status"] == "external_blockers"
    assert {item["id"]: item["status"] for item in report["checks"]}["artifact_contract"] == "pass"
    assert {item["id"]: item["status"] for item in report["checks"]}["human_audit_complete"] == "pending"
    assert {item["id"]: item["status"] for item in report["checks"]}["model_preflight"] == "pending"


def test_publication_readiness_surfaces_unavailable_models(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "summary.json",
        {
            "schema_version": "smu-artifact-v2",
            "artifact_validation": {"status": "pass"},
            "human_audit_summary": {
                "model_vs_human_ready": True,
                "completion": {"all_complete": True, "expected_count": 60, "adjudicated_missing_count": 0},
            },
        },
    )
    _write_json(
        tmp_path / "suite_summary.json",
        {
            "completed_run_count": 54,
            "planned_run_count": 54,
            "missing_run_ids": [],
            "invalid_run_ids": [],
            "failed_run_ids": [],
        },
    )
    _write_json(
        tmp_path / "model_preflight.json",
        {
            "results": [
                {"model": "gpt-5.4-mini", "status": "available"},
                {"model": "gpt-5.4", "status": "insufficient_quota"},
            ]
        },
    )

    report = check_publication_readiness(
        summary_path=tmp_path / "summary.json",
        suite_summary_path=tmp_path / "suite_summary.json",
        model_preflight_path=tmp_path / "model_preflight.json",
    )

    preflight = {item["id"]: item for item in report["checks"]}["model_preflight"]
    assert report["status"] == "external_blockers"
    assert preflight["status"] == "pending"
    assert "insufficient_quota" in preflight["detail"]


def test_publication_suite_status_marks_complete_failed_and_missing(tmp_path: Path) -> None:
    runs = [
        {"run_id": "complete_run"},
        {"run_id": "failed_run"},
        {"run_id": "missing_run"},
    ]
    _write_json(
        tmp_path / "complete_run" / "summary.json",
        {"artifact_validation": {"status": "pass"}},
    )
    _write_json(
        tmp_path / "failed_run" / "progress.json",
        {"status": "failed", "error": "boom"},
    )

    annotated = _annotate_run_statuses(runs, tmp_path)

    assert [row["status"] for row in annotated] == ["complete", "failed", "missing"]
    assert annotated[0]["summary_path"].endswith("complete_run/summary.json")


def test_publication_suite_resume_and_max_runs_selects_only_needed_batch(tmp_path: Path) -> None:
    runs = [
        {"run_id": "run_1"},
        {"run_id": "run_2"},
        {"run_id": "run_3"},
    ]
    _write_json(tmp_path / "run_1" / "summary.json", {"artifact_validation": {"status": "pass"}})

    selected, skipped = _select_runs_for_execution(
        runs,
        outputs_root=tmp_path,
        resume=True,
        max_runs=1,
        requested_run_ids=[],
    )

    assert [row["run_id"] for row in skipped] == ["run_1"]
    assert [row["run_id"] for row in selected] == ["run_2"]
