from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.benchmark.artifact_validation import validate_artifact_contract
from src.benchmark.croissant_metadata import validate_croissant_metadata
from src.benchmark.human_audit import summarize_audit_directory
from src.benchmark.paper_tables import export_paper_tables
from src.benchmark.report_consistency import check_report_consistency
from src.benchmark.statistics import bootstrap_metric_intervals


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _minimal_record(*, regime_label: str = "steady_large_cap") -> dict:
    return {
        "episode_id": "smu_0001_TEST",
        "ticker": "TEST",
        "step_index": 0,
        "as_of_date": "2026-01-02",
        "regime_label": regime_label,
        "observation_hash": "abc123",
        "observation": {
            "episode_id": "smu_0001_TEST",
            "ticker": "TEST",
            "step_index": 0,
            "episode_horizon": 2,
            "regime_label": regime_label,
            "as_of_date": "2026-01-02",
            "market_features": {
                "pct_change_30d": 0.0,
                "short_vs_long_ma_pct": 0.0,
                "volatility_30d": 0.01,
            },
            "tool_evidence": {},
            "mandate": {},
            "remaining_oversight_budget": 1,
            "previous_step_summary": None,
            "visible_events": [],
        },
        "committee_votes": {
            "strategy_a": {
                "name": "Momentum Trader",
                "strategy_key": "strategy_a",
                "decision": "HOLD",
                "confidence": 7,
                "justification": "This is a long enough grounded justification for a neutral action.",
                "cited_signals": [],
                "risk_flags": [],
                "verification_need": "low",
                "mandate_compliance_note": "The recommendation respects the current mandate.",
            }
        },
        "abstention": {
            "agreement_profile": {},
            "disagreement_penalty": 0.0,
            "decision_conflict_penalty": 0.0,
            "confidence_spread": 0,
            "evidence_consistency_score": 1.0,
            "corruption_penalty": 0.0,
            "evidence_integrity_penalty": 0.0,
            "mandate_penalty": 0.0,
            "directional_risk_penalty": 0.0,
            "reliability_score": 0.8,
            "recommend_abstain": False,
            "recommend_verify": False,
            "rationale": "Reliable enough to act.",
        },
        "overseer": {
            "recommended_decision": "approve",
            "decision": "approve",
            "final_action": "HOLD",
            "rationale": "Approved because the recommendation is routine.",
            "decision_drivers": [],
            "intervention_used": False,
            "budget_spent": 0,
            "remaining_budget_after": 1,
            "policy_flags": [],
            "budget_limited": False,
            "intervention_priority": 0.0,
            "counterfactual_majority_action": "HOLD",
        },
        "executed_action": "HOLD",
        "realized_outcome": "HOLD",
        "reward": 1.0,
        "reward_components": {},
        "action_utilities": {
            "BUY": -0.35,
            "HOLD": 1.0,
            "SELL": -0.35,
            "ABSTAIN": 0.25,
            "VERIFY": -0.2,
            "ESCALATE": -0.25,
        },
        "majority_correct": True,
        "policy_violation": False,
        "corruption_active": False,
        "failure_labels": [],
        "quality_assessment": {
            "factual_grounding": 5,
            "coherence": 5,
            "calibration_appropriateness": 5,
            "policy_compliance": 5,
            "oversight_necessity": 5,
            "final_audit_status": "pass",
            "deterministic_findings": [],
            "model_judge_summary": None,
            "model_judge_confidence": None,
            "human_audit_priority": 0,
        },
        "latent_flags": [],
    }


def _minimal_summary() -> dict:
    return {
        "benchmark_name": "Safe MarketUniverses v1",
        "thesis": "test",
        "run_id": "smu_test",
        "run_date": "2026-01-02",
        "schema_version": "smu-artifact-v2",
        "episode_count": 1,
        "step_count": 1,
        "tickers": ["TEST"],
        "model_registry": {"default_models": ["gpt-5.4-mini", "gpt-5.4", "gpt-5.5"]},
        "data_source_notice": {"provider": "yfinance", "redistributable_canonical_dataset": False},
        "metric_definitions": {"selective_risk": "Error rate on covered executed actions."},
        "confidence_intervals": {"selective_risk": {"mean": 0.0, "lower": 0.0, "upper": 0.0}},
        "artifact_validation": {"status": "pending"},
        "experimental_matrix": [
            {"policy": "committee_only", "label": "Committee only", "coverage": 1.0, "error_rate": 0.0, "average_reward": 1.0},
            {"policy": "committee_plus_abstention", "label": "Committee + abstention", "coverage": 1.0, "error_rate": 0.0, "average_reward": 1.0},
            {"policy": "committee_plus_abstention_plus_overseer", "label": "Committee + abstention + overseer", "coverage": 1.0, "error_rate": 0.0, "average_reward": 1.0},
            {"policy": "technical_rule_baseline", "label": "Technical rule baseline", "coverage": 1.0, "error_rate": 0.0, "average_reward": 1.0},
            {"policy": "overseer_budget_0", "label": "Oversight budget 0", "coverage": None, "error_rate": None, "average_reward": 1.0},
            {"policy": "overseer_budget_1", "label": "Oversight budget 1", "coverage": None, "error_rate": None, "average_reward": 1.0},
            {"policy": "overseer_budget_2", "label": "Oversight budget 2", "coverage": None, "error_rate": None, "average_reward": 1.0},
        ],
        "headline_metrics": {
            "executed_coverage": 1.0,
            "selective_risk": 0.0,
            "executed_action_risk": 0.0,
            "always_act_risk": 0.0,
            "abstention_gain": 0.0,
            "majority_expected_calibration_error": 0.2,
            "executed_expected_calibration_error": 0.2,
            "intervention_rate": 0.0,
            "action_distribution": {"HOLD": 1},
            "non_hold_action_rate": 0.0,
            "total_reward": 1.0,
            "utility_per_intervention": None,
            "policy_violation_rate": 0.0,
            "review_rate": 0.0,
            "worst_regime_error": 0.0,
            "failure_counts": {},
            "episode_average_reward": 1.0,
            "verify_on_correct_hold_count": 0,
            "budget_limited_low_reliability_approvals": 0,
            "corrupted_directional_action_count": 0,
        },
        "abstention_curve": [],
        "oversight_budget_curve": [],
        "regime_table": [
            {
                "regime_label": "steady_large_cap",
                "steps": 1,
                "average_reward": 1.0,
                "majority_error_rate": 0.0,
                "executed_error_rate": 0.0,
                "policy_violation_rate": 0.0,
                "review_rate": 0.0,
            }
        ],
        "corruption_comparison": [],
        "failure_gallery": [],
        "audit_manifest": {"model_judged_steps": 0, "human_audit_target_steps": 1, "human_audit_candidate_count": 1},
        "artifacts": {},
    }


def _write_minimal_contract(run_dir: Path, *, summary: dict | None = None) -> None:
    record = _minimal_record()
    _write_json(run_dir / "summary.json", summary or _minimal_summary())
    _write_jsonl(run_dir / "trajectories.jsonl", [record])
    _write_jsonl(run_dir / "human_audit_candidates.jsonl", [record])
    _write_jsonl(run_dir / "gold_slice_candidates.jsonl", [record])
    _write_json(
        run_dir / "benchmark_config.json",
        {
            "benchmark_name": "Safe MarketUniverses v1",
            "episode_count": 1,
            "tickers": ["TEST"],
            "horizon": 1,
        },
    )
    _write_json(
        run_dir / "progress.json",
        {
            "status": "complete",
            "run_id": "smu_test",
            "completed_episodes": 1,
            "total_episodes": 1,
            "completed_steps": 1,
            "expected_steps": 1,
        },
    )
    _write_json(
        run_dir / "episode_specs.json",
        [{"episode_id": "smu_0001_TEST", "ticker": "TEST", "horizon": 1}],
    )
    _write_json(
        run_dir / "episodes" / "smu_0001_TEST.json",
        {"episode_spec": {"episode_id": "smu_0001_TEST"}, "steps": [record]},
    )
    (run_dir / "gold_slice_review_template.csv").write_text("episode_id,ticker,step_index\n", encoding="utf-8")
    (run_dir / "gold_slice_rubric.md").write_text("# Rubric\n", encoding="utf-8")
    _write_json(run_dir / "failure_gallery.json", [])


def test_artifact_validator_rejects_stale_unclassified_outputs(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_json(run_dir / "summary.json", {**_minimal_summary(), "regime_table": [{"regime_label": "unclassified"}]})
    _write_jsonl(run_dir / "trajectories.jsonl", [_minimal_record(regime_label="unclassified")])

    with pytest.raises(ValueError, match="unclassified"):
        validate_artifact_contract(run_dir)


def test_artifact_validator_accepts_current_contract(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_minimal_contract(run_dir)

    report = validate_artifact_contract(run_dir)

    assert report["status"] == "pass"
    assert report["step_count"] == 1


def test_artifact_validator_rejects_incomplete_progress(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_minimal_contract(run_dir)
    _write_json(run_dir / "progress.json", {"status": "running", "run_id": "smu_test"})

    with pytest.raises(ValueError, match="status must be complete"):
        validate_artifact_contract(run_dir)


def test_artifact_validator_rejects_stale_metric_distribution(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    summary = _minimal_summary()
    summary["headline_metrics"]["action_distribution"] = {"BUY": 1}
    _write_minimal_contract(run_dir, summary=summary)

    with pytest.raises(ValueError, match="action_distribution"):
        validate_artifact_contract(run_dir)


def test_export_paper_tables_writes_metric_and_regime_tables(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    output_dir = tmp_path / "tables"
    _write_json(run_dir / "summary.json", _minimal_summary())

    written = export_paper_tables(run_dir, output_dir)

    assert (output_dir / "headline_metrics.md") in written
    assert (output_dir / "regime_table.md") in written
    assert "Selective risk" in (output_dir / "headline_metrics.md").read_text(encoding="utf-8")


def test_report_consistency_detects_changed_summary_values(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    report = tmp_path / "note.md"
    _write_json(run_dir / "summary.json", _minimal_summary())
    report.write_text("Selective risk is `99.0%`.\n", encoding="utf-8")

    result = check_report_consistency(report, run_dir)

    assert result["status"] == "fail"
    assert result["missing_values"]


def test_report_consistency_checks_publication_suite_completion_when_provided(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    report = tmp_path / "note.md"
    suite_summary = tmp_path / "publication_suite_summary.json"
    summary = _minimal_summary()
    summary["abstention_curve"] = [{"threshold": 0.8, "abstention_gain": 0.0851}]
    _write_json(run_dir / "summary.json", summary)
    _write_json(suite_summary, {"completed_run_count": 10, "planned_run_count": 54})
    report.write_text(
        "Selective risk is `0.0000`. Best gain is `0.0851` at threshold `0.8`.\n",
        encoding="utf-8",
    )

    result = check_report_consistency(report, run_dir, suite_summary_path=suite_summary)

    assert result["status"] == "fail"
    assert {"field": "publication_suite.completion", "value": "10/54"} in result["missing_values"]


def test_croissant_metadata_declares_core_artifact_structure() -> None:
    metadata_path = Path(__file__).resolve().parents[1] / "metadata" / "smu_croissant.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    assert metadata["conformsTo"] == "http://mlcommons.org/croissant/1.1"
    assert metadata["url"].startswith("https://github.com/")
    assert {resource["@type"] for resource in metadata["distribution"]} == {"cr:FileObject"}
    assert {resource["@id"] for resource in metadata["distribution"]} >= {
        "summary_json",
        "trajectories_jsonl",
        "human_audit_candidates_jsonl",
    }
    assert {record_set["@id"] for record_set in metadata["recordSet"]} == {
        "benchmark_steps",
        "human_audit_candidates",
    }
    step_fields = {
        field["@id"]
        for record_set in metadata["recordSet"]
        if record_set["@id"] == "benchmark_steps"
        for field in record_set["field"]
    }
    assert "benchmark_steps/executed_action" in step_fields
    assert "benchmark_steps/corruption_active" in step_fields


def test_croissant_metadata_checker_requires_resources_records_and_rai(tmp_path: Path) -> None:
    valid_path = Path(__file__).resolve().parents[1] / "metadata" / "smu_croissant.json"
    assert validate_croissant_metadata(valid_path)["status"] == "pass"

    broken_path = tmp_path / "broken_croissant.json"
    _write_json(
        broken_path,
        {
            "conformsTo": "http://mlcommons.org/croissant/1.1",
            "url": "https://example.test/dataset",
            "license": "https://opensource.org/license/mit",
            "distribution": [{"@type": "DataDownload", "@id": "bad"}],
            "recordSet": [],
        },
    )

    report = validate_croissant_metadata(broken_path)

    assert report["status"] == "fail"
    assert any("cr:FileObject" in error for error in report["errors"])
    assert any("recordSet" in error for error in report["errors"])
    assert any("rai:useCases" in error for error in report["errors"])


def test_bootstrap_metric_intervals_are_deterministic() -> None:
    records = [
        {"executed_action": "HOLD", "realized_outcome": "HOLD", "majority_correct": True, "reward": 1.0},
        {"executed_action": "HOLD", "realized_outcome": "BUY", "majority_correct": False, "reward": -0.25},
    ]

    first = bootstrap_metric_intervals(records, seed=123, iterations=50)
    second = bootstrap_metric_intervals(records, seed=123, iterations=50)

    assert first == second
    assert set(first) >= {"selective_risk", "always_act_risk", "average_reward"}


def test_human_audit_summary_imports_adjudicated_labels(tmp_path: Path) -> None:
    audit_dir = tmp_path / "audit"
    audit_dir.mkdir()
    header = "episode_id,ticker,step_index,automated_audit_status,final_reviewer_status,adjudicated_status\n"
    (audit_dir / "reviewer_a.csv").write_text(header + "e1,T,0,pass,pass,\n", encoding="utf-8")
    (audit_dir / "reviewer_b.csv").write_text(header + "e1,T,0,pass,needs_review,\n", encoding="utf-8")
    (audit_dir / "adjudication.csv").write_text(header + "e1,T,0,pass,,fail\n", encoding="utf-8")

    summary = summarize_audit_directory(audit_dir)

    assert summary["agreement"]["compared"] == 1
    assert summary["model_vs_human_ready"] is True
    assert summary["adjudicated_status_counts"] == {"fail": 1}
