from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .config import OUTPUTS_DIR
from .ml_artifact_validation import validate_ml_backtest_payload
from .ml_pipeline import MLBacktestConfig, build_ml_feature_frame, run_ml_backtest_on_frame

DEFAULT_HYPOTHETICAL_TICKERS = ["COST", "HIMS", "SMCI", "JNJ", "TSLA"]
DEFAULT_SCENARIOS = ("orderly_bull", "sideways_noise", "bear_shock", "volatile_reversal")


@dataclass
class PaperDeploymentConfig:
    tickers: list[str] = field(default_factory=lambda: list(DEFAULT_HYPOTHETICAL_TICKERS))
    iterations: int = 4
    seed: int = 20260620
    scenario_days: int = 756
    scenarios: tuple[str, ...] = DEFAULT_SCENARIOS
    train_start: str = "2024-01-02"
    train_end: str = "2024-12-31"
    test_start: str = "2025-01-02"
    test_end: str = "2025-12-31"
    forward_days: int = 20
    rebalance_days: int = 20
    paper_only: bool = True
    max_drawdown_limit: float = 0.12
    cvar_95_loss_limit: float = 0.08
    mean_weighted_regret_limit: float = 0.95
    output_dir: Path = field(default_factory=lambda: OUTPUTS_DIR / "hypothetical_monitor")


def run_hypothetical_monitor(config: PaperDeploymentConfig) -> Path:
    if config.iterations <= 0:
        raise ValueError("iterations must be positive")

    config.output_dir.mkdir(parents=True, exist_ok=True)
    iteration_reports: list[dict[str, Any]] = []
    for iteration in range(config.iterations):
        scenario = config.scenarios[iteration % len(config.scenarios)]
        iteration_dir = config.output_dir / f"iteration_{iteration + 1:03d}_{scenario}"
        iteration_dir.mkdir(parents=True, exist_ok=True)

        feature_frame = build_hypothetical_feature_frame(
            tickers=config.tickers,
            scenario=scenario,
            days=config.scenario_days,
            seed=config.seed + iteration,
            forward_days=config.forward_days,
        )
        ml_config = MLBacktestConfig(
            tickers=config.tickers,
            train_start=config.train_start,
            train_end=config.train_end,
            test_start=config.test_start,
            test_end=config.test_end,
            forward_days=config.forward_days,
            rebalance_days=config.rebalance_days,
            output_path=iteration_dir / "ml_backtest.json",
        )
        payload = run_ml_backtest_on_frame(feature_frame, config=ml_config, write_output=True)
        artifact_validation = validate_ml_backtest_payload(payload)
        deployment_report = evaluate_paper_deployment_safety(
            payload,
            artifact_validation,
            config=config,
            scenario=scenario,
        )
        (iteration_dir / "deployment_decision.json").write_text(
            json.dumps(deployment_report, indent=2),
            encoding="utf-8",
        )
        iteration_reports.append(deployment_report)

    summary = {
        "mode": "paper_only_hypothetical_monitor",
        "paper_only": config.paper_only,
        "iterations": config.iterations,
        "approved_iterations": sum(1 for report in iteration_reports if report["status"] == "paper_approved"),
        "blocked_iterations": sum(1 for report in iteration_reports if report["status"] == "blocked"),
        "safety_limits": {
            "max_drawdown_limit": config.max_drawdown_limit,
            "cvar_95_loss_limit": config.cvar_95_loss_limit,
            "mean_weighted_regret_limit": config.mean_weighted_regret_limit,
        },
        "reports": iteration_reports,
    }
    summary_path = config.output_dir / "monitor_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary_path


def evaluate_paper_deployment_safety(
    payload: dict[str, Any],
    artifact_validation: dict[str, Any],
    *,
    config: PaperDeploymentConfig,
    scenario: str,
) -> dict[str, Any]:
    scorecard = payload["scorecard"]["ridge_return_minimax"]
    verdict = payload["performance_verdict"]
    blockers: list[str] = []
    warnings: list[str] = []

    if not config.paper_only:
        blockers.append("live execution is disabled; paper_only must remain true")
    if artifact_validation["status"] != "pass":
        blockers.append("ml artifact validation failed")
    if not scorecard["life_safety_veto_passed"]:
        blockers.append("life-safety veto failed")
    if not verdict["passes_practical_period_gate"]:
        blockers.append("practical-period performance gate failed")
    if scorecard["max_drawdown"] > config.max_drawdown_limit:
        blockers.append("max drawdown exceeded deployment limit")
    if scorecard["cvar_95_loss"] > config.cvar_95_loss_limit:
        blockers.append("cvar_95_loss exceeded deployment limit")
    if scorecard["mean_weighted_max_goal_regret"] > config.mean_weighted_regret_limit:
        blockers.append("mean weighted regret exceeded deployment limit")
    if not verdict["passes_strict_minimax_gate"]:
        warnings.append("strict minimax gate failed; paper monitoring only")

    return {
        "scenario": scenario,
        "status": "blocked" if blockers else "paper_approved",
        "paper_only": config.paper_only,
        "external_side_effects": "disabled",
        "blockers": blockers,
        "warnings": [*artifact_validation.get("warnings", []), *warnings],
        "metrics": {
            "average_strategy_return": scorecard["average_strategy_return"],
            "cumulative_return": scorecard["cumulative_return"],
            "max_drawdown": scorecard["max_drawdown"],
            "cvar_95_loss": scorecard["cvar_95_loss"],
            "mean_weighted_max_goal_regret": scorecard["mean_weighted_max_goal_regret"],
            "minimax_regret": scorecard["minimax_regret"],
        },
        "selected_model": {
            "family": payload["model"]["family"],
            "policy_family": payload["model"]["selected_policy_family"],
            "rank_count": payload["model"]["selected_rank_count"],
            "alpha": payload["model"]["selected_alpha"],
        },
    }


def build_hypothetical_feature_frame(
    *,
    tickers: list[str],
    scenario: str,
    days: int,
    seed: int,
    forward_days: int,
) -> pd.DataFrame:
    histories = [
        _generate_hypothetical_history(
            ticker=ticker,
            scenario=scenario,
            days=days,
            seed=seed + index * 997,
        )
        for index, ticker in enumerate(tickers)
    ]
    frames = [
        build_ml_feature_frame(
            ticker,
            history,
            forward_days=forward_days,
            hold_band_pct=3.0,
        )
        for ticker, history in zip(tickers, histories, strict=False)
    ]
    return pd.concat(frames, ignore_index=True).sort_values(["date", "ticker"]).reset_index(drop=True)


def _generate_hypothetical_history(
    *,
    ticker: str,
    scenario: str,
    days: int,
    seed: int,
) -> pd.DataFrame:
    if days < 260:
        raise ValueError("hypothetical histories need at least 260 business days")

    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2023-01-02", periods=days)
    drift, volatility = _scenario_parameters(scenario)
    returns = rng.normal(drift, volatility, size=days)

    if scenario == "bear_shock":
        shock_points = np.linspace(220, days - 40, num=4, dtype=int)
        returns[shock_points] -= rng.uniform(0.06, 0.12, size=len(shock_points))
    elif scenario == "volatile_reversal":
        cycle = np.sin(np.linspace(0, 10 * np.pi, days))
        returns += 0.012 * np.sign(cycle)
    elif scenario == "orderly_bull":
        returns += np.linspace(0.0, 0.0008, days)

    returns = np.clip(returns, -0.24, 0.24)
    close = 100.0 * np.cumprod(1.0 + returns)
    open_ = close * (1.0 + rng.normal(0.0, 0.002, size=days))
    high = np.maximum(open_, close) * (1.0 + np.abs(rng.normal(0.004, 0.002, size=days)))
    low = np.minimum(open_, close) * (1.0 - np.abs(rng.normal(0.004, 0.002, size=days)))
    volume_base = rng.integers(800_000, 2_500_000)
    volume = volume_base * (1.0 + np.abs(rng.normal(0.0, 0.2, size=days)))

    return pd.DataFrame(
        {
            "Open": open_,
            "High": high,
            "Low": low,
            "Close": close,
            "Adj Close": close,
            "Volume": volume.astype(int),
        },
        index=dates,
    )


def _scenario_parameters(scenario: str) -> tuple[float, float]:
    parameters = {
        "orderly_bull": (0.0009, 0.012),
        "sideways_noise": (0.0000, 0.015),
        "bear_shock": (-0.00025, 0.019),
        "volatile_reversal": (0.00015, 0.024),
    }
    if scenario not in parameters:
        raise ValueError(f"unknown hypothetical scenario: {scenario}")
    return parameters[scenario]
