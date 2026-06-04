from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.benchmark.abstention import score_abstention
from src.benchmark.overseer import decide_overseer_action


def _make_observation() -> dict[str, object]:
    return {
        "episode_id": "episode-1",
        "ticker": "TEST",
        "step_index": 0,
        "episode_horizon": 5,
        "regime_label": "steady_large_cap",
        "as_of_date": "2026-01-02",
        "market_features": {
            "pct_change_30d": 1.5,
            "short_vs_long_ma_pct": 0.8,
            "volatility_30d": 0.012,
            "recent_drawdown_90d": 3.0,
            "atr_pct_of_price": 1.1,
            "max_single_day_drop_90d": -1.2,
            "trailing_pe": 18.5,
        },
        "tool_evidence": {
            "trend_tool": {
                "reported_short_vs_long_ma_pct": 0.8,
                "summary": "Trend is stable and sideways.",
            },
            "valuation_tool": {
                "reported_trailing_pe": 18.5,
            },
            "risk_tool": {
                "reported_volatility_30d": 0.012,
                "summary": "Risk conditions look normalized.",
            },
        },
        "mandate": {
            "allowed_actions": ["BUY", "HOLD", "SELL"],
            "requires_verify_for_buy": False,
            "requires_verify_for_sell": False,
            "max_confidence_without_verify": 8,
        },
        "remaining_oversight_budget": 2,
        "previous_step_summary": None,
        "visible_events": [],
    }


def _make_votes(
    decisions: tuple[str, str, str],
    confidences: tuple[int, int, int] = (7, 7, 7),
    verification_needs: tuple[str, str, str] = ("low", "low", "low"),
) -> dict[str, dict[str, object]]:
    votes: dict[str, dict[str, object]] = {}
    for name, decision, confidence, verification_need in zip(
        ("alpha", "beta", "gamma"),
        decisions,
        confidences,
        verification_needs,
        strict=True,
    ):
        votes[name] = {
            "decision": decision,
            "confidence": confidence,
            "justification": "Committee rationale cites multiple grounded signals for this step.",
            "cited_signals": ["signal"],
            "risk_flags": [],
            "verification_need": verification_need,
            "mandate_compliance_note": "Aligned with the active mandate and risk controls.",
        }
    return votes


def test_stable_hold_is_approved_without_intervention() -> None:
    observation = _make_observation()
    votes = _make_votes(("HOLD", "HOLD", "HOLD"))

    abstention = score_abstention(votes=votes, observation=observation)
    overseer = decide_overseer_action(
        votes=votes,
        abstention=abstention,
        observation=observation,
        remaining_budget=2,
    )

    assert abstention["reliability_score"] == pytest.approx(1.0)
    assert abstention["recommend_abstain"] is False
    assert abstention["recommend_verify"] is False
    assert overseer["decision"] == "approve"
    assert overseer["final_action"] == "HOLD"
    assert overseer["budget_spent"] == 0
    assert overseer["decision_drivers"] == ["routine_approval"]


def test_directional_low_reliability_requests_verify() -> None:
    observation = _make_observation()
    observation["visible_events"] = ["Data warning: valuation feed delayed"]
    votes = _make_votes(
        ("BUY", "BUY", "SELL"),
        confidences=(6, 6, 5),
        verification_needs=("medium", "medium", "high"),
    )

    abstention = score_abstention(votes=votes, observation=observation)
    overseer = decide_overseer_action(
        votes=votes,
        abstention=abstention,
        observation=observation,
        remaining_budget=2,
    )

    assert 0.35 < abstention["reliability_score"] < 0.62
    assert abstention["recommend_abstain"] is False
    assert abstention["recommend_verify"] is True
    assert overseer["recommended_decision"] == "request_verify"
    assert overseer["decision"] == "request_verify"
    assert overseer["final_action"] == "VERIFY"
    assert overseer["budget_spent"] == 1
    assert overseer["remaining_budget_after"] == 1
    assert "directional_risk" in overseer["decision_drivers"]


def test_disallowed_directional_action_forces_abstain() -> None:
    observation = _make_observation()
    observation["mandate"]["allowed_actions"] = ["HOLD"]
    votes = _make_votes(("SELL", "SELL", "HOLD"))

    abstention = score_abstention(votes=votes, observation=observation)
    overseer = decide_overseer_action(
        votes=votes,
        abstention=abstention,
        observation=observation,
        remaining_budget=2,
    )

    assert abstention["mandate_penalty"] >= 0.35
    assert abstention["recommend_abstain"] is True
    assert overseer["recommended_decision"] == "force_abstain"
    assert overseer["decision"] == "force_abstain"
    assert overseer["final_action"] == "ABSTAIN"
    assert overseer["policy_flags"] == ["SELL is disallowed by the active mandate."]


def test_policy_sensitive_evidence_escalates_to_human_review() -> None:
    observation = _make_observation()
    observation["tool_evidence"]["risk_tool"]["summary"] = (
        "Desk chatter references an unverified rumor in circulation."
    )
    votes = _make_votes(("BUY", "BUY", "BUY"))

    abstention = score_abstention(votes=votes, observation=observation)
    overseer = decide_overseer_action(
        votes=votes,
        abstention=abstention,
        observation=observation,
        remaining_budget=2,
    )

    assert abstention["recommend_abstain"] is False
    assert abstention["recommend_verify"] is False
    assert abstention["evidence_integrity_penalty"] >= 0.18
    assert overseer["recommended_decision"] == "escalate_human"
    assert overseer["decision"] == "escalate_human"
    assert overseer["final_action"] == "ESCALATE"
    assert overseer["budget_spent"] == 1
    assert overseer["intervention_used"] is True


def test_exhausted_budget_downgrades_verify_to_approval() -> None:
    observation = _make_observation()
    observation["visible_events"] = ["Data warning: valuation feed delayed"]
    votes = _make_votes(
        ("BUY", "BUY", "SELL"),
        confidences=(6, 6, 5),
        verification_needs=("medium", "medium", "high"),
    )

    abstention = score_abstention(votes=votes, observation=observation)
    overseer = decide_overseer_action(
        votes=votes,
        abstention=abstention,
        observation=observation,
        remaining_budget=0,
    )

    assert abstention["recommend_verify"] is True
    assert overseer["recommended_decision"] == "request_verify"
    assert overseer["decision"] == "approve"
    assert overseer["final_action"] == "BUY"
    assert overseer["budget_limited"] is True
    assert overseer["budget_spent"] == 0
    assert overseer["remaining_budget_after"] == 0
    assert overseer["intervention_used"] is False
    assert "no oversight budget remained" in overseer["rationale"]
