from __future__ import annotations

import random
from typing import Any, Callable


def _percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * quantile)))
    return ordered[index]


def _covered_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [record for record in records if record.get("executed_action") in {"BUY", "HOLD", "SELL"}]


def _selective_risk(records: list[dict[str, Any]]) -> float:
    covered = _covered_records(records)
    if not covered:
        return 0.0
    correct = sum(1 for record in covered if record.get("executed_action") == record.get("realized_outcome"))
    return 1.0 - (correct / len(covered))


def _always_act_risk(records: list[dict[str, Any]]) -> float:
    if not records:
        return 0.0
    correct = sum(1 for record in records if record.get("majority_correct"))
    return 1.0 - (correct / len(records))


def _average_reward(records: list[dict[str, Any]]) -> float:
    if not records:
        return 0.0
    return sum(float(record.get("reward", 0.0)) for record in records) / len(records)


def _review_rate(records: list[dict[str, Any]]) -> float:
    if not records:
        return 0.0
    reviews = sum(
        1
        for record in records
        if record.get("quality_assessment", {}).get("final_audit_status") != "pass"
    )
    return reviews / len(records)


BOOTSTRAP_METRICS: dict[str, Callable[[list[dict[str, Any]]], float]] = {
    "selective_risk": _selective_risk,
    "always_act_risk": _always_act_risk,
    "average_reward": _average_reward,
    "review_rate": _review_rate,
}


def bootstrap_metric_intervals(
    records: list[dict[str, Any]],
    *,
    seed: int = 20260414,
    iterations: int = 1000,
) -> dict[str, dict[str, float]]:
    rng = random.Random(seed)
    if not records:
        return {
            name: {"mean": 0.0, "lower": 0.0, "upper": 0.0, "iterations": iterations}
            for name in BOOTSTRAP_METRICS
        }

    distributions: dict[str, list[float]] = {name: [] for name in BOOTSTRAP_METRICS}
    for _ in range(iterations):
        sample = [records[rng.randrange(len(records))] for _ in records]
        for name, fn in BOOTSTRAP_METRICS.items():
            distributions[name].append(fn(sample))

    intervals: dict[str, dict[str, float]] = {}
    for name, values in distributions.items():
        intervals[name] = {
            "mean": round(sum(values) / len(values), 4),
            "lower": round(_percentile(values, 0.025), 4),
            "upper": round(_percentile(values, 0.975), 4),
            "iterations": iterations,
        }
    return intervals
