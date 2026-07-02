from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.ml_pipeline import (
    FEATURE_COLUMNS,
    MLBacktestConfig,
    evaluate_policy_decisions,
    realized_outcome_from_return,
    run_ml_backtest_on_frame,
)
from src.ml_artifact_validation import validate_ml_backtest_payload


def _synthetic_feature_frame() -> pd.DataFrame:
    rows = []
    dates = pd.bdate_range("2024-01-02", periods=180)
    for ticker_index, ticker in enumerate(["AAA", "BBB"]):
        for index, date in enumerate(dates):
            signal = 1.0 if ((index + ticker_index) // 5) % 2 == 0 else -1.0
            forward_return = 0.045 * signal
            row = {
                "date": date,
                "ticker": ticker,
                "forward_return": forward_return,
                "realized_outcome": realized_outcome_from_return(forward_return, 3.0),
            }
            for column in FEATURE_COLUMNS:
                row[column] = 0.0
            row["return_21d"] = signal
            row["return_63d"] = 0.5 * signal
            row["ma_gap_20_200"] = 0.25 * signal
            row["rsi_14"] = 0.75 if signal > 0 else 0.25
            rows.append(row)
    return pd.DataFrame(rows)


def _config(tmp_path: Path) -> MLBacktestConfig:
    return MLBacktestConfig(
        tickers=["AAA", "BBB"],
        train_start="2024-01-02",
        train_end="2024-06-28",
        test_start="2024-07-01",
        test_end="2024-09-06",
        forward_days=20,
        rebalance_days=1,
        hold_band_pct=3.0,
        transaction_cost_bps=10.0,
        ridge_alphas=(0.001, 0.01),
        decision_threshold_grid=(0.0, 0.01, 0.02, 0.03),
        output_path=tmp_path / "ml_backtest.json",
    )


def test_ml_backtest_learns_signal_and_beats_hold_on_synthetic_data(tmp_path: Path) -> None:
    payload = run_ml_backtest_on_frame(
        _synthetic_feature_frame(),
        config=_config(tmp_path),
        write_output=True,
    )

    assert (tmp_path / "ml_backtest.json").exists()
    ml = payload["scorecard"]["ridge_return_minimax"]
    hold = payload["scorecard"]["always_hold"]

    assert ml["accuracy"] >= 0.95
    assert ml["average_strategy_return"] > hold["average_strategy_return"]
    assert ml["minimax_regret"] < hold["minimax_regret"]
    assert ml["life_safety_veto_passed"] is True


def test_regret_math_is_nonnegative_and_uses_hindsight_best(tmp_path: Path) -> None:
    frame = _synthetic_feature_frame().head(3).copy()
    frame["forward_return"] = [0.05, -0.06, 0.01]
    frame["realized_outcome"] = [
        realized_outcome_from_return(value, 3.0)
        for value in frame["forward_return"]
    ]
    actions = ["HOLD", "BUY", "SELL"]

    metrics, decisions = evaluate_policy_decisions(
        frame,
        actions,
        predictions=np.zeros(len(frame)),
        config=_config(tmp_path),
        policy_name="unit_test_policy",
    )

    assert metrics["life_safety_veto_passed"] is True
    assert (decisions["alpha_regret"] >= 0).all()
    assert (decisions["weighted_max_goal_regret"] >= 0).all()
    assert decisions.iloc[0]["best_hindsight_return"] == pytest.approx(0.049)
    assert decisions.iloc[0]["alpha_regret"] == pytest.approx(0.049)
    assert metrics["minimax_regret"] == round(float(decisions["weighted_max_goal_regret"].max()), 6)


def test_ml_artifact_validator_accepts_generated_payload(tmp_path: Path) -> None:
    payload = run_ml_backtest_on_frame(
        _synthetic_feature_frame(),
        config=_config(tmp_path),
        write_output=False,
    )

    report = validate_ml_backtest_payload(payload)

    assert report["status"] == "pass"
    assert report["issues"] == []


def test_ml_artifact_validator_rejects_tampered_regret(tmp_path: Path) -> None:
    payload = run_ml_backtest_on_frame(
        _synthetic_feature_frame(),
        config=_config(tmp_path),
        write_output=False,
    )
    payload["decision_records"][0]["alpha_regret"] += 1.0

    report = validate_ml_backtest_payload(payload)

    assert report["status"] == "fail"
    assert any("alpha_regret" in issue for issue in report["issues"])
