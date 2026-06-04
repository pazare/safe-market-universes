from __future__ import annotations

from src.benchmark.human_audit import summarize_audit_directory
from src.benchmark.metrics import build_oversight_budget_curve
from src.benchmark.overseer import decide_overseer_action


def test_oversight_budget_curve_uses_total_reward_per_intervention() -> None:
    record = {
        "overseer": {
            "recommended_decision": "request_verify",
            "counterfactual_majority_action": "HOLD",
        },
        "realized_outcome": "HOLD",
        "policy_violation": False,
        "majority_correct": True,
        "action_utilities": {
            "BUY": -0.35,
            "HOLD": 1.0,
            "SELL": -0.35,
            "ABSTAIN": 0.25,
            "VERIFY": -0.2,
            "ESCALATE": -0.25,
        },
    }

    rows = build_oversight_budget_curve([{"steps": [record, record]}], [1])

    assert rows[0]["total_reward"] == 0.8
    assert rows[0]["average_reward"] == 0.4
    assert rows[0]["interventions"] == 1.0
    assert rows[0]["utility_per_intervention"] == 0.8
    assert rows[0]["recommended_intervention_rate"] == 1.0
    assert rows[0]["budget_limited_rate"] == 0.5


def test_overseer_persists_three_way_tie_policy_metadata() -> None:
    votes = {
        "momentum": {"decision": "BUY", "confidence": 5, "verification_need": "low"},
        "value": {"decision": "SELL", "confidence": 5, "verification_need": "low"},
        "volatility": {"decision": "HOLD", "confidence": 5, "verification_need": "low"},
    }
    abstention = {
        "recommend_abstain": False,
        "recommend_verify": False,
        "reliability_score": 0.7,
        "agreement_profile": {"disagreement_type": "three_way_split"},
        "directional_risk_penalty": 0.0,
    }
    observation = {
        "mandate": {"allowed_actions": ["BUY", "HOLD", "SELL"], "max_confidence_without_verify": 8},
        "visible_events": [],
        "tool_evidence": {},
    }

    decision = decide_overseer_action(
        votes=votes,
        abstention=abstention,
        observation=observation,
        remaining_budget=1,
    )

    assert decision["counterfactual_majority_action"] == "HOLD"
    assert decision["committee_policy_action"] == "HOLD"
    assert decision["vote_majority_type"] == "tie_break_hold"
    assert decision["tie_break_rule"] == "three_way_split_defaults_to_hold"


def test_human_audit_empty_agreement_is_not_reported_as_zero(tmp_path) -> None:
    header = "episode_id,ticker,step_index,automated_audit_status,final_reviewer_status,adjudicated_status\n"
    (tmp_path / "reviewer_a.csv").write_text(header + "e1,T,0,pass,,\n", encoding="utf-8")
    (tmp_path / "reviewer_b.csv").write_text(header + "e1,T,0,pass,,\n", encoding="utf-8")
    (tmp_path / "adjudication.csv").write_text(header + "e1,T,0,pass,,\n", encoding="utf-8")

    summary = summarize_audit_directory(tmp_path, expected_count=1)

    assert summary["agreement"]["compared"] == 0
    assert summary["agreement"]["raw_agreement"] is None
    assert summary["model_vs_human_agreement"]["raw_agreement"] is None
