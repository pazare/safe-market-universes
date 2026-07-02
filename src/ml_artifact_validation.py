from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from .ml_pipeline import ACTIONS

REQUIRED_TOP_LEVEL_KEYS = {
    "methodology",
    "config",
    "data",
    "model",
    "scorecard",
    "performance_verdict",
    "decision_records",
}
REQUIRED_SCORECARDS = {
    "ridge_return_minimax",
    "always_hold",
    "always_buy",
    "technical_trend_rule",
}
VALID_POLICY_FAMILIES = {"absolute_threshold", "long_top_rank", "long_short_rank"}
FLOAT_TOLERANCE = 1e-6


def validate_ml_backtest_file(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    report = validate_ml_backtest_payload(payload)
    report["artifact_path"] = str(path)
    return report


def validate_ml_backtest_payload(payload: dict[str, Any]) -> dict[str, Any]:
    issues: list[str] = []
    warnings: list[str] = []

    _check_required_keys(payload, issues)
    if issues:
        return _report(issues, warnings)

    config = payload["config"]
    data = payload["data"]
    model = payload["model"]
    scorecard = payload["scorecard"]
    verdict = payload["performance_verdict"]
    records = payload["decision_records"]

    _check_config(config, issues)
    _check_data(data, records, scorecard, issues)
    _check_model(model, issues)
    _check_scorecards(scorecard, issues)

    if not issues:
        _check_decision_math(config, records, issues)
        _check_scorecard_recomputes(records, scorecard["ridge_return_minimax"], issues)
        _check_verdict(scorecard, verdict, issues)
        _check_period_claim(scorecard, verdict, warnings)

    return _report(issues, warnings)


def _check_required_keys(payload: dict[str, Any], issues: list[str]) -> None:
    missing = sorted(REQUIRED_TOP_LEVEL_KEYS - set(payload))
    if missing:
        issues.append(f"missing top-level keys: {missing}")


def _check_config(config: dict[str, Any], issues: list[str]) -> None:
    for key in [
        "train_start",
        "train_end",
        "test_start",
        "test_end",
        "forward_days",
        "rebalance_days",
        "hold_band_pct",
        "transaction_cost_bps",
        "goal_weights",
    ]:
        if key not in config:
            issues.append(f"config missing {key}")
    if issues:
        return

    train_start = pd.Timestamp(config["train_start"])
    train_end = pd.Timestamp(config["train_end"])
    test_start = pd.Timestamp(config["test_start"])
    test_end = pd.Timestamp(config["test_end"])
    if not train_start <= train_end < test_start <= test_end:
        issues.append("train/test dates must satisfy train_start <= train_end < test_start <= test_end")
    if int(config["forward_days"]) <= 0:
        issues.append("forward_days must be positive")
    if int(config["rebalance_days"]) <= 0:
        issues.append("rebalance_days must be positive")
    weights = config["goal_weights"]
    for key in ["alpha", "tail_loss", "turnover"]:
        if key not in weights or float(weights[key]) < 0:
            issues.append(f"goal_weights.{key} must exist and be nonnegative")


def _check_data(
    data: dict[str, Any],
    records: list[dict[str, Any]],
    scorecard: dict[str, Any],
    issues: list[str],
) -> None:
    for key in ["tickers", "feature_columns", "train_rows", "validation_rows", "test_rows", "test_decision_dates"]:
        if key not in data:
            issues.append(f"data missing {key}")
    if issues:
        return

    if int(data["train_rows"]) <= 0:
        issues.append("train_rows must be positive")
    if int(data["validation_rows"]) <= 0:
        issues.append("validation_rows must be positive")
    if int(data["test_rows"]) <= 0:
        issues.append("test_rows must be positive")
    if len(records) != int(data["test_rows"]):
        issues.append("decision_records length must equal data.test_rows")
    if "ridge_return_minimax" in scorecard:
        if int(scorecard["ridge_return_minimax"].get("decisions", -1)) != len(records):
            issues.append("ridge_return_minimax decisions must equal decision_records length")


def _check_model(model: dict[str, Any], issues: list[str]) -> None:
    policy_family = model.get("selected_policy_family")
    if policy_family not in VALID_POLICY_FAMILIES:
        issues.append(f"selected_policy_family must be one of {sorted(VALID_POLICY_FAMILIES)}")
    if policy_family in {"long_top_rank", "long_short_rank"} and int(model.get("selected_rank_count") or 0) <= 0:
        issues.append("rank policies require positive selected_rank_count")
    if float(model.get("selected_alpha", -1.0)) < 0:
        issues.append("selected_alpha must be nonnegative")


def _check_scorecards(scorecard: dict[str, Any], issues: list[str]) -> None:
    missing = sorted(REQUIRED_SCORECARDS - set(scorecard))
    if missing:
        issues.append(f"missing scorecards: {missing}")
        return
    for name in REQUIRED_SCORECARDS:
        row = scorecard[name]
        for key in [
            "average_strategy_return",
            "cumulative_return",
            "max_drawdown",
            "cvar_95_loss",
            "mean_weighted_max_goal_regret",
            "minimax_regret",
            "life_safety_veto_passed",
        ]:
            if key not in row:
                issues.append(f"{name} scorecard missing {key}")


def _check_decision_math(
    config: dict[str, Any],
    records: list[dict[str, Any]],
    issues: list[str],
) -> None:
    cost = float(config["transaction_cost_bps"]) / 10000.0
    hold_band = float(config["hold_band_pct"]) / 100.0
    weights = config["goal_weights"]
    for index, record in enumerate(records):
        action = record.get("action")
        if action not in ACTIONS:
            issues.append(f"record {index} action must be one of {ACTIONS}")
            continue

        forward_return = float(record["forward_return"])
        buy_utility = forward_return - cost
        sell_utility = -forward_return - cost
        hold_utility = 0.0
        chosen = {
            "BUY": buy_utility,
            "SELL": sell_utility,
            "HOLD": hold_utility,
        }[action]
        best = max(buy_utility, sell_utility, hold_utility)
        alpha_regret = max(best - chosen, 0.0)
        tail_loss_regret = max(-chosen, 0.0)
        turnover_regret = 0.0 if action == "HOLD" else cost
        normalizer = max(abs(forward_return), abs(best), max(hold_band, cost, 1e-6))
        weighted_alpha = float(weights["alpha"]) * alpha_regret / normalizer
        weighted_tail = float(weights["tail_loss"]) * tail_loss_regret / normalizer
        weighted_turnover = float(weights["turnover"]) * (0.0 if action == "HOLD" else 1.0)
        weighted_max = max(weighted_alpha, weighted_tail, weighted_turnover, 0.0)

        expected_values = {
            "strategy_return": chosen,
            "best_hindsight_return": best,
            "alpha_regret": alpha_regret,
            "tail_loss_regret": tail_loss_regret,
            "turnover_regret": turnover_regret,
            "life_safety_regret": 0.0,
            "weighted_alpha_regret": weighted_alpha,
            "weighted_tail_loss_regret": weighted_tail,
            "weighted_turnover_regret": weighted_turnover,
            "weighted_max_goal_regret": weighted_max,
        }
        for key, expected in expected_values.items():
            if not _close(float(record[key]), expected):
                issues.append(f"record {index} {key} does not match recomputed value")


def _check_scorecard_recomputes(
    records: list[dict[str, Any]],
    ml_scorecard: dict[str, Any],
    issues: list[str],
) -> None:
    frame = pd.DataFrame(records)
    frame["date"] = pd.to_datetime(frame["date"])
    by_date = frame.groupby("date", sort=True)["strategy_return"].mean()
    curve = (1.0 + by_date).cumprod()
    running_peak = curve.cummax()
    recomputed = {
        "decisions": len(frame),
        "decision_dates": int(frame["date"].nunique()),
        "average_strategy_return": float(frame["strategy_return"].mean()),
        "cumulative_return": float(curve.iloc[-1] - 1.0),
        "max_drawdown": abs(float(((curve / running_peak) - 1.0).min())),
        "cvar_95_loss": _cvar_loss(by_date.tolist(), tail_fraction=0.05),
        "mean_alpha_regret": float(frame["alpha_regret"].mean()),
        "max_alpha_regret": float(frame["alpha_regret"].max()),
        "mean_weighted_max_goal_regret": float(frame["weighted_max_goal_regret"].mean()),
        "minimax_regret": float(frame["weighted_max_goal_regret"].max()),
        "life_safety_veto_passed": bool(frame["life_safety_regret"].max() == 0.0),
    }
    for key, expected in recomputed.items():
        actual = ml_scorecard[key]
        if isinstance(expected, bool):
            if bool(actual) != expected:
                issues.append(f"scorecard {key} does not match recomputed value")
        elif isinstance(expected, int):
            if int(actual) != expected:
                issues.append(f"scorecard {key} does not match recomputed value")
        elif not _close(float(actual), expected, tolerance=5e-6):
            issues.append(f"scorecard {key} does not match recomputed value")


def _check_verdict(
    scorecard: dict[str, Any],
    verdict: dict[str, Any],
    issues: list[str],
) -> None:
    ml = scorecard["ridge_return_minimax"]
    hold = scorecard["always_hold"]
    always_buy = scorecard["always_buy"]
    competitors = {name: metrics for name, metrics in scorecard.items() if name != "ridge_return_minimax"}
    expected_practical = (
        ml["average_strategy_return"] > 0
        and ml["cumulative_return"] > 0
        and ml["mean_weighted_max_goal_regret"] < hold["mean_weighted_max_goal_regret"]
        and ml["cvar_95_loss"] < always_buy["cvar_95_loss"]
        and ml["max_drawdown"] < always_buy["max_drawdown"]
        and ml["life_safety_veto_passed"]
    )
    expected_strict = ml["minimax_regret"] <= min(row["minimax_regret"] for row in competitors.values())
    expected_return_leader = ml["average_strategy_return"] >= max(
        row["average_strategy_return"] for row in competitors.values()
    )
    expected = {
        "passes_practical_period_gate": expected_practical,
        "passes_strict_minimax_gate": expected_strict,
        "passes_return_leader_gate": expected_return_leader,
    }
    for key, expected_value in expected.items():
        if bool(verdict.get(key)) != bool(expected_value):
            issues.append(f"performance_verdict.{key} does not match recomputed gate")


def _check_period_claim(
    scorecard: dict[str, Any],
    verdict: dict[str, Any],
    warnings: list[str],
) -> None:
    if verdict["passes_practical_period_gate"] and not verdict["passes_strict_minimax_gate"]:
        warnings.append(
            "practical-period performance passed, but strict minimax regret did not; treat as research evidence only"
        )
    if not scorecard["ridge_return_minimax"]["life_safety_veto_passed"]:
        warnings.append("life-safety veto failed")


def _cvar_loss(returns: list[float], *, tail_fraction: float) -> float:
    if not returns:
        return 0.0
    losses = sorted([-float(value) for value in returns], reverse=True)
    tail_count = max(1, int(len(losses) * tail_fraction + 0.999999))
    return float(sum(losses[:tail_count]) / tail_count)


def _close(left: float, right: float, *, tolerance: float = FLOAT_TOLERANCE) -> bool:
    return abs(left - right) <= tolerance


def _report(issues: list[str], warnings: list[str]) -> dict[str, Any]:
    return {
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "warnings": warnings,
        "checked_contract": "ml_backtest_v1",
    }
