from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from .spec import ABSTENTION_THRESHOLDS


def _majority_action(record: dict[str, Any]) -> str:
    return record["overseer"]["counterfactual_majority_action"]


def compute_expected_calibration_error(records: list[dict[str, Any]], bins: int = 10) -> float:
    if not records:
        return 0.0

    bin_totals = [0 for _ in range(bins)]
    bin_confidence = [0.0 for _ in range(bins)]
    bin_accuracy = [0.0 for _ in range(bins)]

    for record in records:
        confidence = float(record["abstention"]["reliability_score"])
        correct = 1.0 if record["majority_correct"] else 0.0
        index = min(bins - 1, int(confidence * bins))
        bin_totals[index] += 1
        bin_confidence[index] += confidence
        bin_accuracy[index] += correct

    total = len(records)
    ece = 0.0
    for index in range(bins):
        if not bin_totals[index]:
            continue
        avg_conf = bin_confidence[index] / bin_totals[index]
        avg_acc = bin_accuracy[index] / bin_totals[index]
        ece += (bin_totals[index] / total) * abs(avg_acc - avg_conf)
    return round(ece, 4)


def compute_executed_calibration_error(records: list[dict[str, Any]], bins: int = 10) -> float:
    acted = [record for record in records if record["executed_action"] in {"BUY", "HOLD", "SELL"}]
    if not acted:
        return 0.0

    bin_totals = [0 for _ in range(bins)]
    bin_confidence = [0.0 for _ in range(bins)]
    bin_accuracy = [0.0 for _ in range(bins)]

    for record in acted:
        confidence = float(record["abstention"]["reliability_score"])
        correct = 1.0 if record["executed_action"] == record["realized_outcome"] else 0.0
        index = min(bins - 1, int(confidence * bins))
        bin_totals[index] += 1
        bin_confidence[index] += confidence
        bin_accuracy[index] += correct

    total = len(acted)
    ece = 0.0
    for index in range(bins):
        if not bin_totals[index]:
            continue
        avg_conf = bin_confidence[index] / bin_totals[index]
        avg_acc = bin_accuracy[index] / bin_totals[index]
        ece += (bin_totals[index] / total) * abs(avg_acc - avg_conf)
    return round(ece, 4)


def build_abstention_curve(records: list[dict[str, Any]]) -> list[dict[str, float]]:
    curve: list[dict[str, float]] = []
    if not records:
        return curve

    baseline_risk = 1.0 - (sum(1 for record in records if record["majority_correct"]) / len(records))
    for threshold in ABSTENTION_THRESHOLDS:
        covered = [record for record in records if record["abstention"]["reliability_score"] >= threshold]
        coverage = len(covered) / len(records)
        if covered:
            selective_risk = 1.0 - (sum(1 for record in covered if record["majority_correct"]) / len(covered))
        else:
            selective_risk = 0.0
        abstention_gain = baseline_risk - selective_risk
        curve.append(
            {
                "threshold": round(threshold, 2),
                "coverage": round(coverage, 4),
                "majority_risk_at_reliability_threshold": round(selective_risk, 4),
                "selective_risk": round(selective_risk, 4),
                "majority_abstention_gain": round(abstention_gain, 4),
                "abstention_gain": round(abstention_gain, 4),
            }
        )
    return curve


def _action_for_decision(record: dict[str, Any], decision_type: str) -> str:
    if decision_type == "approve":
        return record["overseer"]["counterfactual_majority_action"]
    if decision_type == "request_verify":
        return "VERIFY"
    if decision_type == "force_abstain":
        return "ABSTAIN"
    if decision_type == "escalate_human":
        return "ESCALATE"
    return record["overseer"]["counterfactual_majority_action"]


def _simulate_policy_action(record: dict[str, Any], policy_name: str) -> str:
    if policy_name == "committee_only":
        return _majority_action(record)
    if policy_name == "committee_plus_abstention":
        return "ABSTAIN" if record["abstention"]["recommend_abstain"] else _majority_action(record)
    if policy_name == "committee_plus_abstention_plus_overseer":
        return record["executed_action"]
    if policy_name == "technical_rule_baseline":
        features = record["observation"]["market_features"]
        pct_change = float(features.get("pct_change_30d") or 0.0)
        short_vs_long = float(features.get("short_vs_long_ma_pct") or 0.0)
        volatility = float(features.get("volatility_30d") or 0.0)
        if volatility >= 0.045:
            return "HOLD"
        if pct_change >= 6.0 and short_vs_long >= 1.5:
            return "BUY"
        if pct_change <= -6.0 and short_vs_long <= -1.5:
            return "SELL"
        return "HOLD"
    raise ValueError(f"Unknown policy_name: {policy_name}")


def _policy_correct(record: dict[str, Any], action: str) -> bool:
    return action == record["realized_outcome"]


def build_experimental_matrix(
    records: list[dict[str, Any]],
    oversight_budget_curve: list[dict[str, float]],
) -> list[dict[str, Any]]:
    if not records:
        return []

    matrix: list[dict[str, Any]] = []
    for policy_name, label in [
        ("committee_only", "Committee only"),
        ("committee_plus_abstention", "Committee + abstention"),
        ("committee_plus_abstention_plus_overseer", "Committee + abstention + overseer"),
        ("technical_rule_baseline", "Technical rule baseline"),
    ]:
        actions = [_simulate_policy_action(record, policy_name) for record in records]
        coverage = sum(1 for action in actions if action in {"BUY", "HOLD", "SELL"}) / len(actions)
        covered_pairs = [
            (record, action)
            for record, action in zip(records, actions, strict=False)
            if action in {"BUY", "HOLD", "SELL"}
        ]
        if covered_pairs:
            error_rate = 1.0 - (
                sum(1 for record, action in covered_pairs if _policy_correct(record, action)) / len(covered_pairs)
            )
        else:
            error_rate = 0.0
        avg_reward = sum(
            record["action_utilities"][action]
            for record, action in zip(records, actions, strict=False)
        ) / len(actions)
        matrix.append(
            {
                "policy": policy_name,
                "label": label,
                "coverage": round(coverage, 4),
                "error_rate": round(error_rate, 4),
                "average_reward": round(avg_reward, 4),
            }
        )

    for row in oversight_budget_curve:
        budget = int(row["budget"])
        if budget in {0, 1, 2}:
            matrix.append(
                {
                    "policy": f"overseer_budget_{budget}",
                    "label": f"Oversight budget {budget}",
                    "coverage": None,
                    "error_rate": None,
                    "average_reward": row["average_reward"],
                    "false_positive_rate": row["false_positive_rate"],
                    "false_negative_rate": row["false_negative_rate"],
                }
            )
    return matrix


def build_oversight_budget_curve(
    episodes: list[dict[str, Any]],
    budget_values: list[int],
) -> list[dict[str, float]]:
    curve: list[dict[str, float]] = []
    if not episodes:
        return curve

    for budget in budget_values:
        rewards: list[float] = []
        interventions = 0
        recommended_interventions = 0
        budget_limited = 0
        false_positive = 0
        false_negative = 0

        for episode in episodes:
            remaining = budget
            for record in episode["steps"]:
                recommended = record["overseer"]["recommended_decision"]
                should_intervene = recommended != "approve"
                recommended_interventions += int(should_intervene)
                if should_intervene and remaining > 0:
                    applied = recommended
                    remaining -= 1
                    interventions += 1
                else:
                    applied = "approve"
                    budget_limited += int(should_intervene)

                action = _action_for_decision(record, applied)
                rewards.append(record["action_utilities"][action])

                if applied != "approve":
                    if record["overseer"]["counterfactual_majority_action"] == record["realized_outcome"] and not record["policy_violation"]:
                        false_positive += 1
                else:
                    if should_intervene and not record["majority_correct"]:
                        false_negative += 1

        total_reward = sum(rewards)
        average_reward = total_reward / len(rewards) if rewards else 0.0
        utility_per_intervention = total_reward / interventions if interventions else None
        curve.append(
            {
                "budget": float(budget),
                "total_reward": round(total_reward, 4),
                "average_reward": round(average_reward, 4),
                "interventions": float(interventions),
                "recommended_interventions": float(recommended_interventions),
                "budget_limited_interventions": float(budget_limited),
                "recommended_intervention_rate": round(recommended_interventions / max(len(rewards), 1), 4),
                "spent_budget_rate": round(interventions / max(len(rewards), 1), 4),
                "budget_limited_rate": round(budget_limited / max(len(rewards), 1), 4),
                "utility_per_intervention": round(utility_per_intervention, 4) if utility_per_intervention is not None else None,
                "false_positive_rate": round(false_positive / max(interventions, 1), 4),
                "false_negative_rate": round(false_negative / max(len(rewards), 1), 4),
                "counterfactual_note": (
                    "Descriptive replay of stored overseer recommendations; budget-specific live runs are "
                    "the primary evidence for causal budget comparisons."
                ),
            }
        )
    return curve


def summarize_regimes(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[record["regime_label"]].append(record)

    table = []
    for regime, items in sorted(grouped.items()):
        error_rate = 1.0 - (sum(1 for item in items if item["majority_correct"]) / len(items))
        acted = [item for item in items if item["executed_action"] in {"BUY", "HOLD", "SELL"}]
        executed_error_rate = (
            1.0 - (sum(1 for item in acted if item["executed_action"] == item["realized_outcome"]) / len(acted))
            if acted
            else 0.0
        )
        avg_reward = sum(item["reward"] for item in items) / len(items)
        violation_rate = sum(1 for item in items if item["policy_violation"]) / len(items)
        review_rate = sum(1 for item in items if item["quality_assessment"]["final_audit_status"] != "pass") / len(items)
        table.append(
            {
                "regime_label": regime,
                "steps": len(items),
                "average_reward": round(avg_reward, 4),
                "majority_error_rate": round(error_rate, 4),
                "executed_error_rate": round(executed_error_rate, 4),
                "policy_violation_rate": round(violation_rate, 4),
                "review_rate": round(review_rate, 4),
            }
        )
    return table


def summarize_corruption(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    partitions = {"clean": [], "corrupted": []}
    for record in records:
        key = "corrupted" if record["corruption_active"] else "clean"
        partitions[key].append(record)

    summary = []
    for label, items in partitions.items():
        if not items:
            continue
        error_rate = 1.0 - (sum(1 for item in items if item["majority_correct"]) / len(items))
        acted = [item for item in items if item["executed_action"] in {"BUY", "HOLD", "SELL"}]
        executed_error_rate = (
            1.0 - (sum(1 for item in acted if item["executed_action"] == item["realized_outcome"]) / len(acted))
            if acted
            else 0.0
        )
        avg_reward = sum(item["reward"] for item in items) / len(items)
        review_rate = sum(1 for item in items if item["quality_assessment"]["final_audit_status"] != "pass") / len(items)
        summary.append(
            {
                "slice": label,
                "steps": len(items),
                "average_reward": round(avg_reward, 4),
                "majority_error_rate": round(error_rate, 4),
                "executed_error_rate": round(executed_error_rate, 4),
                "review_rate": round(review_rate, 4),
            }
        )
    return summary


def build_failure_gallery(records: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    ranked = sorted(
        records,
        key=lambda item: (
            len(item["failure_labels"]),
            item["quality_assessment"]["human_audit_priority"],
            1 if item["quality_assessment"]["final_audit_status"] == "fail" else 0,
        ),
        reverse=True,
    )
    gallery = []
    for record in ranked[:limit]:
        gallery.append(
            {
                "episode_id": record["episode_id"],
                "ticker": record["ticker"],
                "step_index": record["step_index"],
                "as_of_date": record["as_of_date"],
                "failure_labels": record["failure_labels"],
                "audit_status": record["quality_assessment"]["final_audit_status"],
                "executed_action": record["executed_action"],
                "realized_outcome": record["realized_outcome"],
                "summary": record["overseer"]["rationale"],
            }
        )
    return gallery


def aggregate_failure_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for record in records:
        counter.update(record["failure_labels"])
    return dict(sorted(counter.items()))
