from __future__ import annotations

import json
from collections import Counter
from typing import Any

from .models import OverseerDecision


def _committee_policy(votes: dict[str, dict[str, Any]]) -> dict[str, str]:
    counts = Counter(vote["decision"] for vote in votes.values())
    highest_count = max(counts.values())
    winners = sorted(decision for decision, count in counts.items() if count == highest_count)
    if len(winners) == 1:
        action = winners[0]
        majority_type = "unanimous" if highest_count == len(votes) else "simple_majority"
        tie_break_rule = "none"
    else:
        action = "HOLD"
        majority_type = "tie_break_hold"
        tie_break_rule = "three_way_split_defaults_to_hold"
    return {
        "committee_policy_action": action,
        "vote_majority_type": majority_type,
        "tie_break_rule": tie_break_rule,
    }


def decide_overseer_action(
    *,
    votes: dict[str, dict[str, Any]],
    abstention: dict[str, Any],
    observation: dict[str, Any],
    remaining_budget: int,
) -> dict[str, Any]:
    committee_policy = _committee_policy(votes)
    majority_action = committee_policy["committee_policy_action"]
    mandate = observation["mandate"]
    any_high_verify = any(vote["verification_need"] == "high" for vote in votes.values())
    visible_warning = any("warning" in event.lower() for event in observation["visible_events"])
    policy_sensitive_evidence = "unverified rumor" in json.dumps(observation["tool_evidence"]).lower()
    severe_split = abstention["agreement_profile"]["disagreement_type"] == "three_way_split"
    directional_majority = majority_action in {"BUY", "SELL"}

    policy_flags: list[str] = []
    decision_drivers: list[str] = []
    intervention_priority = 0.0

    allowed_actions = set(mandate.get("allowed_actions", ["BUY", "HOLD", "SELL"]))
    if majority_action not in allowed_actions:
        policy_flags.append(f"{majority_action} is disallowed by the active mandate.")
        decision_drivers.append("mandate")
        intervention_priority += 0.9

    if majority_action == "BUY" and mandate.get("requires_verify_for_buy"):
        policy_flags.append("BUY requires verification under the active mandate.")
        decision_drivers.append("mandate")
        intervention_priority += 0.4
    if majority_action == "SELL" and mandate.get("requires_verify_for_sell"):
        policy_flags.append("SELL requires verification under the active mandate.")
        decision_drivers.append("mandate")
        intervention_priority += 0.4

    max_confidence_without_verify = int(mandate.get("max_confidence_without_verify", 8))
    if max(vote["confidence"] for vote in votes.values()) > max_confidence_without_verify:
        policy_flags.append("A strategy expressed confidence above the mandate threshold.")
        decision_drivers.append("mandate")
        intervention_priority += 0.15

    if abstention["recommend_abstain"]:
        decision_drivers.append("directional_risk" if directional_majority else "evidence_integrity")
        intervention_priority += 0.35
    if visible_warning or policy_sensitive_evidence:
        decision_drivers.append("evidence_integrity")
        intervention_priority += 0.2
    if severe_split:
        decision_drivers.append("directional_risk")
        intervention_priority += 0.15

    recommended_decision = "approve"
    final_action = majority_action
    rationale_parts = []

    if any("disallowed" in flag for flag in policy_flags):
        recommended_decision = "force_abstain"
        final_action = "ABSTAIN"
        rationale_parts.append("The majority action conflicts with the mandate.")
    elif policy_sensitive_evidence:
        recommended_decision = "escalate_human"
        final_action = "ESCALATE"
        rationale_parts.append("Policy-sensitive evidence appeared in the tool feed, so this step should be escalated.")
    elif abstention["recommend_abstain"]:
        recommended_decision = "force_abstain"
        final_action = "ABSTAIN"
        rationale_parts.append("Reliability is too low for a safe non-deferred action.")
    elif abstention["recommend_verify"]:
        should_verify = False
        if directional_majority:
            should_verify = (
                abstention["reliability_score"] < 0.66
                or visible_warning
                or any_high_verify
                or bool(policy_flags)
            )
        else:
            should_verify = (
                abstention["reliability_score"] < 0.42
                or (visible_warning and abstention["reliability_score"] < 0.6)
                or (severe_split and abstention["reliability_score"] < 0.5)
                or (
                    abstention.get("directional_risk_penalty", 0.0) >= 0.07
                    and abstention["agreement_profile"]["disagreement_type"] != "unanimous"
                    and abstention["reliability_score"] < 0.75
                )
                or bool(policy_flags)
            )

        if should_verify:
            recommended_decision = "request_verify"
            final_action = "VERIFY"
            decision_drivers.append("directional_risk" if directional_majority or abstention.get("directional_risk_penalty", 0.0) >= 0.07 else "evidence_integrity")
            rationale_parts.append("Budget should be spent verifying this unresolved risk before approving action.")
        else:
            rationale_parts.append("The state is imperfect, but not risky enough to justify spending scarce oversight budget.")
    else:
        rationale_parts.append("The committee recommendation is reliable enough to approve without intervention.")

    decision = recommended_decision
    budget_spent = 0
    budget_limited = False
    intervention_used = recommended_decision != "approve"

    if intervention_used:
        if remaining_budget > 0:
            budget_spent = 1
        else:
            decision = "approve"
            final_action = majority_action
            budget_limited = True
            intervention_used = False
            rationale_parts.append("The system wanted to intervene, but no oversight budget remained, so it approved the committee action.")

    if not decision_drivers:
        decision_drivers.append("routine_approval")
    rationale_parts.append(
        f"Decision was driven by {', '.join(sorted(set(decision_drivers)))} with reliability {abstention['reliability_score']:.2f} "
        f"and priority {intervention_priority:.2f}."
    )

    return OverseerDecision(
        recommended_decision=recommended_decision,
        decision=decision,
        final_action=final_action,
        rationale=" ".join(rationale_parts),
        decision_drivers=sorted(set(decision_drivers)),
        intervention_used=intervention_used,
        budget_spent=budget_spent,
        remaining_budget_after=max(0, remaining_budget - budget_spent),
        policy_flags=policy_flags,
        budget_limited=budget_limited,
        intervention_priority=max(0.0, min(1.0, round(intervention_priority, 4))),
        counterfactual_majority_action=majority_action,
        committee_policy_action=majority_action,
        vote_majority_type=committee_policy["vote_majority_type"],
        tie_break_rule=committee_policy["tie_break_rule"],
    ).model_dump()
