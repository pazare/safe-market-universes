from __future__ import annotations

import json
from pathlib import Path

from src.benchmark.preliminary_results import build_preliminary_results, write_preliminary_results


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_preliminary_results_groups_conditions_and_writes_markdown(tmp_path: Path) -> None:
    headline = {
        "run_id": "smu_headline_v1",
        "episode_count": 2,
        "step_count": 8,
        "headline_metrics": {
            "executed_coverage": 0.75,
            "selective_risk": 0.25,
            "always_act_risk": 0.5,
            "abstention_gain": 0.25,
            "review_rate": 0.4,
            "intervention_rate": 0.2,
            "worst_regime_error": 0.6,
            "failure_counts": {"oversight_miss": 2},
        },
        "corruption_comparison": [
            {
                "slice": "clean",
                "steps": 4,
                "majority_error_rate": 0.25,
                "executed_error_rate": 0.2,
                "review_rate": 0.1,
            }
        ],
        "regime_table": [],
        "human_audit_summary": {
            "completion": {"expected_count": 60, "adjudicated_missing_count": 60}
        },
    }
    suite = {
        "planned_run_count": 54,
        "completed_run_count": 2,
        "missing_run_ids": ["missing"],
        "failed_run_ids": ["failed"],
        "invalid_run_reasons": {"failed": "progress_status_failed:external_api_insufficient_quota"},
        "completed_runs": [
            {
                "run_id": "run_a",
                "budget": 1,
                "corruption_enabled": False,
                "step_count": 8,
                "headline_metrics": {
                    "selective_risk": 0.2,
                    "review_rate": 0.1,
                    "intervention_rate": 0.05,
                    "total_reward": 10.0,
                    "utility_per_intervention": 2.0,
                    "executed_expected_calibration_error": 0.3,
                    "non_hold_action_rate": 0.0,
                    "action_distribution": {"HOLD": 8},
                },
            },
            {
                "run_id": "run_b",
                "budget": 1,
                "corruption_enabled": False,
                "step_count": 8,
                "headline_metrics": {
                    "selective_risk": 0.4,
                    "review_rate": 0.3,
                    "intervention_rate": 0.15,
                    "total_reward": 14.0,
                    "utility_per_intervention": 4.0,
                    "executed_expected_calibration_error": 0.5,
                    "non_hold_action_rate": 0.25,
                    "action_distribution": {"BUY": 2, "HOLD": 6},
                },
            },
        ],
    }
    preflight = {"results": [{"status": "available"}, {"status": "insufficient_quota"}]}
    headline_path = tmp_path / "summary.json"
    suite_path = tmp_path / "suite.json"
    preflight_path = tmp_path / "preflight.json"
    output_path = tmp_path / "preliminary.md"
    json_output_path = tmp_path / "preliminary.json"
    _write_json(headline_path, headline)
    _write_json(suite_path, suite)
    _write_json(preflight_path, preflight)

    report = build_preliminary_results(
        headline_summary_path=headline_path,
        suite_summary_path=suite_path,
        model_preflight_path=preflight_path,
    )
    written = write_preliminary_results(
        output_path=output_path,
        json_output_path=json_output_path,
        headline_summary_path=headline_path,
        suite_summary_path=suite_path,
        model_preflight_path=preflight_path,
    )

    assert written == output_path
    assert report["suite"]["condition_table"] == [
        {
            "budget": 1,
            "corruption_enabled": False,
            "condition": "Budget 1, clean evidence",
            "n": 2,
            "selective_risk": 0.3,
            "review_rate": 0.2,
            "intervention_rate": 0.1,
            "total_reward": 12.0,
            "utility_per_intervention": 3.0,
            "executed_expected_calibration_error": 0.4,
            "non_hold_action_rate": 0.125,
            "reward_per_step": 1.5,
            "action_distribution": {"BUY": 2, "HOLD": 14},
        }
    ]
    markdown = output_path.read_text(encoding="utf-8")
    assert "Safe MarketUniverses Preliminary Results" in markdown
    assert "Budget 1, clean evidence" in markdown
    assert "30.0%" in markdown
    assert json.loads(json_output_path.read_text(encoding="utf-8"))["status"] == "preliminary"
