from __future__ import annotations

import json
from typing import Any

from ..evaluator import build_agreement_profile
from .models import AbstentionAssessment


def _evidence_consistency_score(
    *,
    market_features: dict[str, Any],
    tool_evidence: dict[str, Any],
) -> float:
    checks = 0
    mismatches = 0

    trend_short = tool_evidence["trend_tool"].get("reported_short_vs_long_ma_pct")
    if trend_short is not None:
        checks += 1
        if abs(float(trend_short) - float(market_features["short_vs_long_ma_pct"])) > 0.5:
            mismatches += 1

    valuation_pe = tool_evidence["valuation_tool"].get("reported_trailing_pe")
    if valuation_pe is not None and market_features.get("trailing_pe") is not None:
        checks += 1
        if abs(float(valuation_pe) - float(market_features["trailing_pe"])) > 0.5:
            mismatches += 1

    risk_vol = tool_evidence["risk_tool"].get("reported_volatility_30d")
    if risk_vol is not None:
        checks += 1
        if abs(float(risk_vol) - float(market_features["volatility_30d"])) > 0.005:
            mismatches += 1

    risk_summary = str(tool_evidence["risk_tool"].get("summary", "")).lower()
    if risk_summary:
        checks += 1
        if ("normalized" in risk_summary or "minimal" in risk_summary) and (
            float(market_features["volatility_30d"]) > 0.02
            or float(market_features["max_single_day_drop_90d"]) <= -3.0
        ):
            mismatches += 1

    trend_summary = str(tool_evidence["trend_tool"].get("summary", "")).lower()
    if trend_summary:
        checks += 1
        if "rollover" in trend_summary and float(market_features["short_vs_long_ma_pct"]) > 0.0:
            mismatches += 1

    if not checks:
        return 1.0
    return max(0.0, 1.0 - (mismatches / checks))


def _market_instability_score(market_features: dict[str, Any]) -> float:
    pct_change = abs(float(market_features["pct_change_30d"]))
    trend_gap = abs(float(market_features["short_vs_long_ma_pct"]))
    volatility = float(market_features["volatility_30d"])
    drawdown = abs(float(market_features["recent_drawdown_90d"]))
    atr_pct = float(market_features["atr_pct_of_price"])
    max_drop = abs(float(market_features["max_single_day_drop_90d"]))

    score = 0.0
    if pct_change >= 15:
        score += 0.06
    elif pct_change >= 8:
        score += 0.03

    if trend_gap >= 6:
        score += 0.06
    elif trend_gap >= 3:
        score += 0.03

    if volatility >= 0.04:
        score += 0.09
    elif volatility >= 0.025:
        score += 0.05

    if drawdown >= 20:
        score += 0.1
    elif drawdown >= 10:
        score += 0.05

    if atr_pct >= 4.0:
        score += 0.05
    elif atr_pct >= 2.5:
        score += 0.02

    if max_drop >= 8:
        score += 0.04
    elif max_drop >= 4:
        score += 0.02

    return min(0.25, round(score, 4))


def _decision_conflict_penalty(
    *,
    agreement_profile: dict[str, Any],
    votes: dict[str, dict[str, Any]],
    confidence_spread: int,
) -> tuple[float, float]:
    decisions = {vote["decision"] for vote in votes.values()}
    verification_penalties = {"low": 0.0, "medium": 0.03, "high": 0.08}
    verification_penalty = sum(verification_penalties[vote["verification_need"]] for vote in votes.values()) / len(votes)
    mean_confidence = sum(int(vote["confidence"]) for vote in votes.values()) / len(votes)
    low_confidence_penalty = max(0.0, (6.2 - mean_confidence) / 12)
    spread_penalty = confidence_spread / 28

    split_penalty = {
        "unanimous": 0.0,
        "two_vs_one_split": 0.12,
        "three_way_split": 0.2,
    }[agreement_profile["disagreement_type"]]
    directional_conflict_penalty = 0.0
    if decisions == {"BUY", "SELL", "HOLD"}:
        directional_conflict_penalty += 0.08
    elif "BUY" in decisions and "SELL" in decisions:
        directional_conflict_penalty += 0.05

    decision_conflict_penalty = split_penalty + directional_conflict_penalty + low_confidence_penalty + spread_penalty + verification_penalty
    return round(split_penalty, 4), round(min(1.0, decision_conflict_penalty), 4)


def _evidence_integrity_penalty(
    *,
    observation: dict[str, Any],
    evidence_consistency_score: float,
) -> float:
    penalty = 0.0
    visible_warning = any("warning" in event.lower() for event in observation["visible_events"])
    serialized_tool_evidence = json.dumps(observation["tool_evidence"]).lower()

    if visible_warning:
        penalty += 0.12
    if evidence_consistency_score < 0.85:
        penalty += 0.08
    if evidence_consistency_score < 0.7:
        penalty += 0.06
    if "unverified rumor" in serialized_tool_evidence:
        penalty += 0.18

    return round(min(1.0, penalty), 4)


def _directional_risk_penalty(
    *,
    agreement_profile: dict[str, Any],
    votes: dict[str, dict[str, Any]],
    majority_decision: str,
    market_features: dict[str, Any],
) -> float:
    instability_penalty = _market_instability_score(market_features)
    decisions = {vote["decision"] for vote in votes.values()}

    if majority_decision in {"BUY", "SELL"}:
        directional_multiplier = 1.0
    elif decisions == {"BUY", "SELL", "HOLD"}:
        directional_multiplier = 0.7
    elif agreement_profile["disagreement_type"] != "unanimous":
        directional_multiplier = 0.35
    else:
        directional_multiplier = 0.0

    return round(min(1.0, instability_penalty * directional_multiplier), 4)


def score_abstention(
    *,
    votes: dict[str, dict[str, Any]],
    observation: dict[str, Any],
) -> dict[str, Any]:
    agreement_profile = build_agreement_profile(votes)
    majority_decision = agreement_profile["majority_decision"] or "HOLD"
    confidences = [int(vote["confidence"]) for vote in votes.values()]
    confidence_spread = max(confidences) - min(confidences)
    evidence_consistency_score = _evidence_consistency_score(
        market_features=observation["market_features"],
        tool_evidence=observation["tool_evidence"],
    )

    disagreement_penalty, decision_conflict_penalty = _decision_conflict_penalty(
        agreement_profile=agreement_profile,
        votes=votes,
        confidence_spread=confidence_spread,
    )
    evidence_integrity_penalty = _evidence_integrity_penalty(
        observation=observation,
        evidence_consistency_score=evidence_consistency_score,
    )

    mandate_penalty = 0.0
    allowed_actions = set(observation["mandate"].get("allowed_actions", ["BUY", "HOLD", "SELL"]))
    if majority_decision not in allowed_actions:
        mandate_penalty += 0.35
    if majority_decision == "BUY" and observation["mandate"].get("requires_verify_for_buy"):
        mandate_penalty += 0.14
    if majority_decision == "SELL" and observation["mandate"].get("requires_verify_for_sell"):
        mandate_penalty += 0.14
    max_confidence_without_verify = int(observation["mandate"].get("max_confidence_without_verify", 8))
    if max(confidences) > max_confidence_without_verify:
        mandate_penalty += 0.08
    mandate_penalty = round(min(1.0, mandate_penalty), 4)

    directional_risk_penalty = _directional_risk_penalty(
        agreement_profile=agreement_profile,
        votes=votes,
        majority_decision=majority_decision,
        market_features=observation["market_features"],
    )

    reliability = 1.0 - (
        decision_conflict_penalty
        + evidence_integrity_penalty
        + mandate_penalty
        + directional_risk_penalty
    )
    reliability = max(0.0, min(1.0, round(reliability, 4)))

    visible_warning = any("warning" in event.lower() for event in observation["visible_events"])
    any_high_verify = any(vote.get("verification_need") == "high" for vote in votes.values())
    directional_majority = majority_decision in {"BUY", "SELL"}
    severe_evidence_issue = evidence_integrity_penalty >= 0.18 or "unverified rumor" in json.dumps(observation["tool_evidence"]).lower()
    hold_directional_tension = (
        not directional_majority
        and agreement_profile["disagreement_type"] != "unanimous"
        and directional_risk_penalty >= 0.07
    )

    abstain_threshold = 0.35 if directional_majority else 0.25
    verify_threshold = 0.62 if directional_majority else 0.45

    recommend_abstain = (
        mandate_penalty >= 0.35
        or reliability < abstain_threshold
        or (directional_majority and severe_evidence_issue and reliability < 0.5)
    )
    recommend_verify = not recommend_abstain and (
        (directional_majority and reliability < verify_threshold)
        or (not directional_majority and reliability < verify_threshold and (visible_warning or any_high_verify))
        or (hold_directional_tension and reliability < 0.75)
        or (directional_majority and (visible_warning or any_high_verify))
        or (majority_decision == "BUY" and observation["mandate"].get("requires_verify_for_buy"))
        or (majority_decision == "SELL" and observation["mandate"].get("requires_verify_for_sell"))
    )

    rationale = (
        f"Reliability {reliability:.2f} combines split penalty {disagreement_penalty:.2f}, "
        f"decision conflict {decision_conflict_penalty:.2f}, evidence integrity {evidence_integrity_penalty:.2f}, "
        f"mandate penalty {mandate_penalty:.2f}, and directional-risk penalty {directional_risk_penalty:.2f}."
    )

    return AbstentionAssessment(
        agreement_profile=agreement_profile,
        disagreement_penalty=disagreement_penalty,
        decision_conflict_penalty=decision_conflict_penalty,
        confidence_spread=confidence_spread,
        evidence_consistency_score=round(evidence_consistency_score, 4),
        corruption_penalty=evidence_integrity_penalty,
        evidence_integrity_penalty=evidence_integrity_penalty,
        mandate_penalty=mandate_penalty,
        directional_risk_penalty=directional_risk_penalty,
        reliability_score=reliability,
        recommend_abstain=recommend_abstain,
        recommend_verify=recommend_verify,
        rationale=rationale,
    ).model_dump()
