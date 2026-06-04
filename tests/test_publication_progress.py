from __future__ import annotations

import json
from pathlib import Path

from src.benchmark.progress import build_publication_progress


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_publication_progress_summarizes_suite_audit_preflight_and_next_actions(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "canonical_summary.json",
        {
            "schema_version": "smu-artifact-v2",
            "artifact_validation": {"status": "pass"},
            "human_audit_summary": {
                "model_vs_human_ready": False,
                "completion": {
                    "expected_count": 60,
                    "adjudicated_missing_count": 60,
                    "all_complete": False,
                },
            },
        },
    )
    _write_json(
        tmp_path / "suite_summary.json",
        {
            "planned_run_count": 54,
            "completed_run_count": 6,
            "completion_rate": 0.1111,
            "missing_run_ids": ["run_missing"],
            "failed_run_ids": ["run_quota"],
            "invalid_run_reasons": {
                "run_quota": "progress_status_failed:external_api_insufficient_quota",
            },
        },
    )
    _write_json(
        tmp_path / "audit_summary.json",
        {
            "completion": {
                "expected_count": 60,
                "reviewer_a_missing_count": 60,
                "reviewer_b_missing_count": 60,
                "adjudicated_missing_count": 60,
                "all_complete": False,
            },
            "model_vs_human_ready": False,
        },
    )
    _write_json(
        tmp_path / "model_preflight.json",
        {
            "live_response_check": True,
            "results": [
                {"model": "gpt-5.4-mini", "status": "insufficient_quota", "available": False},
                {"model": "gpt-5.4", "status": "insufficient_quota", "available": False},
                {"model": "gpt-5.5", "status": "available", "available": True},
            ],
        },
    )

    progress = build_publication_progress(
        summary_path=tmp_path / "canonical_summary.json",
        suite_summary_path=tmp_path / "suite_summary.json",
        audit_summary_path=tmp_path / "audit_summary.json",
        model_preflight_path=tmp_path / "model_preflight.json",
    )

    assert progress["overall_status"] == "external_blockers"
    assert progress["suite"]["completed"] == 6
    assert progress["suite"]["failed"] == 1
    assert progress["suite"]["not_started"] == 1
    assert progress["suite"]["completion_label"] == "6/54"
    assert progress["human_audit"]["adjudicated_completed"] == 0
    assert progress["model_preflight"]["status_counts"] == {
        "available": 1,
        "insufficient_quota": 2,
    }
    assert progress["model_preflight"]["quota_blocked"] is True
    assert progress["next_actions"] == [
        "Restore OpenAI quota or billing, then resume failed publication-suite cells.",
        "Complete reviewer_a.csv, reviewer_b.csv, and adjudication.csv for the 60-row human audit.",
        "Resume the remaining publication suite with --resume once live preflight passes.",
    ]
