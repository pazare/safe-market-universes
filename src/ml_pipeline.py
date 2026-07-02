from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .config import OUTPUTS_DIR
from .market_data import download_price_history

ACTIONS = ("BUY", "HOLD", "SELL")
FEATURE_COLUMNS = [
    "return_1d",
    "return_5d",
    "return_21d",
    "return_63d",
    "volatility_21d",
    "volatility_63d",
    "ma_gap_10_50",
    "ma_gap_20_200",
    "rsi_14",
    "atr_pct_14",
    "volume_ratio_21d",
    "drawdown_63d",
    "zscore_21d",
]


@dataclass
class MLBacktestConfig:
    tickers: list[str]
    train_start: str = "2024-01-02"
    train_end: str = "2024-12-31"
    test_start: str = "2025-01-02"
    test_end: str = "2025-12-31"
    forward_days: int = 20
    rebalance_days: int = 20
    hold_band_pct: float = 3.0
    transaction_cost_bps: float = 10.0
    history_period: str = "3y"
    validation_fraction: float = 0.25
    ridge_alphas: tuple[float, ...] = (0.001, 0.01, 0.1, 1.0, 10.0)
    rank_top_counts: tuple[int, ...] = (1, 2)
    decision_threshold_grid: tuple[float, ...] = (
        0.0,
        0.0025,
        0.005,
        0.0075,
        0.01,
        0.015,
        0.02,
        0.03,
        0.04,
        0.06,
    )
    goal_weights: dict[str, float] = field(
        default_factory=lambda: {"alpha": 1.0, "tail_loss": 1.5, "turnover": 0.25}
    )
    output_path: Path = field(default_factory=lambda: OUTPUTS_DIR / "ml_backtest.json")


@dataclass(frozen=True)
class RidgeReturnModel:
    feature_columns: list[str]
    feature_means: dict[str, float]
    feature_stds: dict[str, float]
    intercept: float
    coefficients: dict[str, float]
    alpha: float
    decision_threshold: float

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        x_matrix = _standardized_matrix(
            frame,
            self.feature_columns,
            self.feature_means,
            self.feature_stds,
        )
        beta = np.array([self.coefficients[column] for column in self.feature_columns])
        return self.intercept + x_matrix @ beta


def realized_outcome_from_return(forward_return: float, hold_band_pct: float) -> str:
    hold_band_return = hold_band_pct / 100.0
    if forward_return > hold_band_return:
        return "BUY"
    if forward_return < -hold_band_return:
        return "SELL"
    return "HOLD"


def build_ml_feature_frame(
    ticker: str,
    history: pd.DataFrame,
    *,
    forward_days: int,
    hold_band_pct: float,
) -> pd.DataFrame:
    """Build point-in-time features and future labels from one price history."""
    if history.empty:
        raise ValueError(f"{ticker} has no history.")

    history = history.sort_index().copy()
    history.index = pd.to_datetime(history.index).tz_localize(None)
    close = history["Close"].astype(float)
    high = history["High"].astype(float)
    low = history["Low"].astype(float)
    volume = history["Volume"].astype(float).replace(0, np.nan)
    daily_return = close.pct_change()

    true_range = pd.concat(
        [
            high - low,
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs(),
        ],
        axis=1,
    ).max(axis=1)
    avg_gain = daily_return.clip(lower=0).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    avg_loss = (-daily_return.clip(upper=0)).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)

    frame = pd.DataFrame(index=history.index)
    frame["date"] = frame.index
    frame["ticker"] = ticker.upper()
    frame["return_1d"] = close.pct_change(1)
    frame["return_5d"] = close.pct_change(5)
    frame["return_21d"] = close.pct_change(21)
    frame["return_63d"] = close.pct_change(63)
    frame["volatility_21d"] = daily_return.rolling(21, min_periods=21).std()
    frame["volatility_63d"] = daily_return.rolling(63, min_periods=63).std()
    frame["ma_gap_10_50"] = (close.rolling(10, min_periods=10).mean() / close.rolling(50, min_periods=50).mean()) - 1
    frame["ma_gap_20_200"] = (close.rolling(20, min_periods=20).mean() / close.rolling(200, min_periods=200).mean()) - 1
    frame["rsi_14"] = (100 - (100 / (1 + rs))).fillna(50) / 100.0
    frame["atr_pct_14"] = true_range.rolling(14, min_periods=14).mean() / close
    frame["volume_ratio_21d"] = volume / volume.rolling(21, min_periods=21).mean()
    frame["drawdown_63d"] = (close / close.rolling(63, min_periods=63).max()) - 1
    rolling_mean_21d = close.rolling(21, min_periods=21).mean()
    rolling_std_21d = close.rolling(21, min_periods=21).std().replace(0, np.nan)
    frame["zscore_21d"] = (close - rolling_mean_21d) / rolling_std_21d
    frame["forward_return"] = (close.shift(-forward_days) / close) - 1
    frame["realized_outcome"] = frame["forward_return"].map(
        lambda value: realized_outcome_from_return(float(value), hold_band_pct)
        if pd.notna(value)
        else None
    )
    return frame.dropna(subset=[*FEATURE_COLUMNS, "forward_return", "realized_outcome"]).reset_index(drop=True)


def load_ml_backtest_frame(config: MLBacktestConfig) -> pd.DataFrame:
    frames = []
    for ticker in config.tickers:
        history = download_price_history(ticker, period=config.history_period)
        frames.append(
            build_ml_feature_frame(
                ticker,
                history,
                forward_days=config.forward_days,
                hold_band_pct=config.hold_band_pct,
            )
        )
    if not frames:
        raise ValueError("At least one ticker is required.")
    return pd.concat(frames, ignore_index=True).sort_values(["date", "ticker"]).reset_index(drop=True)


def fit_ridge_return_model(
    frame: pd.DataFrame,
    *,
    feature_columns: list[str] = FEATURE_COLUMNS,
    alpha: float,
    decision_threshold: float,
) -> RidgeReturnModel:
    if frame.empty:
        raise ValueError("Cannot fit a model with an empty training frame.")

    means = {column: float(frame[column].mean()) for column in feature_columns}
    stds = {
        column: float(frame[column].std(ddof=0)) if float(frame[column].std(ddof=0)) > 0 else 1.0
        for column in feature_columns
    }
    x_matrix = _standardized_matrix(frame, feature_columns, means, stds)
    y = frame["forward_return"].astype(float).to_numpy()
    design = np.column_stack([np.ones(len(x_matrix)), x_matrix])
    penalty = np.eye(design.shape[1])
    penalty[0, 0] = 0.0
    beta = np.linalg.pinv(design.T @ design + alpha * penalty) @ design.T @ y
    return RidgeReturnModel(
        feature_columns=list(feature_columns),
        feature_means=means,
        feature_stds=stds,
        intercept=float(beta[0]),
        coefficients={column: float(value) for column, value in zip(feature_columns, beta[1:], strict=False)},
        alpha=float(alpha),
        decision_threshold=float(decision_threshold),
    )


def choose_actions_from_predictions(predictions: np.ndarray, threshold: float) -> list[str]:
    actions = []
    for prediction in predictions:
        if prediction > threshold:
            actions.append("BUY")
        elif prediction < -threshold:
            actions.append("SELL")
        else:
            actions.append("HOLD")
    return actions


def run_ml_backtest(config: MLBacktestConfig) -> Path:
    frame = load_ml_backtest_frame(config)
    run_ml_backtest_on_frame(frame, config=config, write_output=True)
    return config.output_path


def run_ml_backtest_on_frame(
    frame: pd.DataFrame,
    *,
    config: MLBacktestConfig,
    write_output: bool = True,
) -> dict[str, Any]:
    frame = _validate_frame(frame)
    train_frame, test_frame = _split_train_test(frame, config)
    fit_frame, validation_frame = _chronological_validation_split(
        train_frame,
        validation_fraction=config.validation_fraction,
    )
    selected = select_model_hyperparameters(fit_frame, validation_frame, config)
    model = fit_ridge_return_model(
        train_frame,
        alpha=selected["alpha"],
        decision_threshold=selected["decision_threshold"],
    )

    ml_predictions = model.predict(test_frame)
    ml_actions = choose_actions_for_policy(test_frame, ml_predictions, selected)
    ml_metrics, ml_decisions = evaluate_policy_decisions(
        test_frame,
        ml_actions,
        predictions=ml_predictions,
        config=config,
        policy_name="ridge_return_minimax",
    )

    baseline_scorecard: dict[str, Any] = {"ridge_return_minimax": ml_metrics}
    baseline_decisions: dict[str, pd.DataFrame] = {"ridge_return_minimax": ml_decisions}
    for policy_name, actions in _baseline_actions(test_frame, config).items():
        metrics, decisions = evaluate_policy_decisions(
            test_frame,
            actions,
            predictions=np.zeros(len(test_frame)),
            config=config,
            policy_name=policy_name,
        )
        baseline_scorecard[policy_name] = metrics
        baseline_decisions[policy_name] = decisions

    payload = {
        "methodology": _methodology_payload(config),
        "config": _config_payload(config),
        "data": {
            "tickers": [ticker.upper() for ticker in config.tickers],
            "feature_columns": FEATURE_COLUMNS,
            "rows_total": int(len(frame)),
            "train_rows": int(len(train_frame)),
            "validation_rows": int(len(validation_frame)),
            "test_rows": int(len(test_frame)),
            "first_feature_date": _date_string(frame["date"].min()),
            "last_feature_date": _date_string(frame["date"].max()),
            "test_decision_dates": int(test_frame["date"].nunique()),
        },
        "model": {
            "family": "closed_form_ridge_return_forecaster",
            "target": "forward_return",
            "selected_policy_family": selected["policy_family"],
            "selected_rank_count": selected.get("rank_count"),
            "selected_alpha": selected["alpha"],
            "selected_decision_threshold": selected["decision_threshold"],
            "validation_selection": selected,
            "intercept": round(model.intercept, 8),
            "coefficients": {
                column: round(model.coefficients[column], 8)
                for column in model.feature_columns
            },
        },
        "scorecard": baseline_scorecard,
        "performance_verdict": _performance_verdict(baseline_scorecard),
        "decision_records": _records_for_json(ml_decisions),
    }
    if write_output:
        config.output_path.parent.mkdir(parents=True, exist_ok=True)
        config.output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def select_model_hyperparameters(
    fit_frame: pd.DataFrame,
    validation_frame: pd.DataFrame,
    config: MLBacktestConfig,
) -> dict[str, Any]:
    if validation_frame.empty:
        validation_frame = fit_frame

    candidates = []
    for alpha in config.ridge_alphas:
        base_model = fit_ridge_return_model(
            fit_frame,
            alpha=alpha,
            decision_threshold=0.0,
        )
        predictions = base_model.predict(validation_frame)
        for threshold in config.decision_threshold_grid:
            actions = choose_actions_for_policy(
                validation_frame,
                predictions,
                {
                    "policy_family": "absolute_threshold",
                    "decision_threshold": threshold,
                    "rank_count": None,
                },
            )
            metrics, _ = evaluate_policy_decisions(
                validation_frame,
                actions,
                predictions=predictions,
                config=config,
                policy_name="validation_candidate",
            )
            candidates.append(
                {
                    "policy_family": "absolute_threshold",
                    "rank_count": None,
                    "alpha": float(alpha),
                    "decision_threshold": float(threshold),
                    "validation_average_strategy_return": metrics["average_strategy_return"],
                    "validation_cumulative_return": metrics["cumulative_return"],
                    "validation_minimax_regret": metrics["minimax_regret"],
                    "validation_mean_weighted_regret": metrics["mean_weighted_max_goal_regret"],
                    "validation_turnover_rate": metrics["turnover_rate"],
                    "validation_accuracy": metrics["accuracy"],
                    "validation_cvar_95_loss": metrics["cvar_95_loss"],
                }
            )
        for policy_family in ("long_top_rank", "long_short_rank"):
            for rank_count in config.rank_top_counts:
                actions = choose_actions_for_policy(
                    validation_frame,
                    predictions,
                    {
                        "policy_family": policy_family,
                        "decision_threshold": 0.0,
                        "rank_count": rank_count,
                    },
                )
                metrics, _ = evaluate_policy_decisions(
                    validation_frame,
                    actions,
                    predictions=predictions,
                    config=config,
                    policy_name="validation_candidate",
                )
                candidates.append(
                    {
                        "policy_family": policy_family,
                        "rank_count": int(rank_count),
                        "alpha": float(alpha),
                        "decision_threshold": 0.0,
                        "validation_average_strategy_return": metrics["average_strategy_return"],
                        "validation_cumulative_return": metrics["cumulative_return"],
                        "validation_minimax_regret": metrics["minimax_regret"],
                        "validation_mean_weighted_regret": metrics["mean_weighted_max_goal_regret"],
                        "validation_turnover_rate": metrics["turnover_rate"],
                        "validation_accuracy": metrics["accuracy"],
                        "validation_cvar_95_loss": metrics["cvar_95_loss"],
                    }
                )

    candidates.sort(
        key=lambda row: (
            row["validation_mean_weighted_regret"],
            row["validation_cvar_95_loss"],
            -row["validation_average_strategy_return"],
            row["validation_turnover_rate"],
            row["validation_minimax_regret"],
        )
    )
    best = candidates[0]
    best["candidate_count"] = len(candidates)
    return best


def choose_actions_for_policy(
    frame: pd.DataFrame,
    predictions: np.ndarray,
    policy: dict[str, Any],
) -> list[str]:
    policy_family = policy["policy_family"]
    if policy_family == "absolute_threshold":
        return choose_actions_from_predictions(predictions, float(policy["decision_threshold"]))
    if policy_family == "long_top_rank":
        return _ranked_actions(frame, predictions, top_count=int(policy["rank_count"]), include_short=False)
    if policy_family == "long_short_rank":
        return _ranked_actions(frame, predictions, top_count=int(policy["rank_count"]), include_short=True)
    raise ValueError(f"Unknown policy_family: {policy_family}")


def evaluate_policy_decisions(
    frame: pd.DataFrame,
    actions: list[str],
    *,
    predictions: np.ndarray,
    config: MLBacktestConfig,
    policy_name: str,
) -> tuple[dict[str, Any], pd.DataFrame]:
    if len(actions) != len(frame):
        raise ValueError("Action count must match frame length.")

    decisions = frame[["date", "ticker", "forward_return", "realized_outcome"]].copy()
    decisions["policy"] = policy_name
    decisions["prediction"] = predictions.astype(float)
    decisions["action"] = actions
    decisions = _attach_return_and_regret_columns(decisions, config)

    by_date = decisions.groupby("date", sort=True)["strategy_return"].mean()
    curve = (1.0 + by_date).cumprod()
    cumulative_return = float(curve.iloc[-1] - 1.0) if len(curve) else 0.0
    running_peak = curve.cummax() if len(curve) else pd.Series(dtype=float)
    max_drawdown = float(((curve / running_peak) - 1.0).min()) if len(curve) else 0.0
    period_std = float(by_date.std(ddof=0)) if len(by_date) else 0.0
    annualization = np.sqrt(252.0 / max(config.forward_days, 1))
    sharpe = float(by_date.mean() / period_std * annualization) if period_std > 1e-12 else 0.0

    metrics = {
        "decisions": int(len(decisions)),
        "decision_dates": int(decisions["date"].nunique()),
        "accuracy": _round(float((decisions["action"] == decisions["realized_outcome"]).mean())),
        "average_strategy_return": _round(float(decisions["strategy_return"].mean())),
        "cumulative_return": _round(cumulative_return),
        "period_mean_return": _round(float(by_date.mean()) if len(by_date) else 0.0),
        "period_volatility": _round(period_std),
        "sharpe_like_ratio": _round(sharpe),
        "max_drawdown": _round(abs(max_drawdown)),
        "cvar_95_loss": _round(_cvar_loss(by_date.tolist(), tail_fraction=0.05)),
        "turnover_rate": _round(float((decisions["action"] != "HOLD").mean())),
        "mean_alpha_regret": _round(float(decisions["alpha_regret"].mean())),
        "max_alpha_regret": _round(float(decisions["alpha_regret"].max())),
        "mean_weighted_max_goal_regret": _round(float(decisions["weighted_max_goal_regret"].mean())),
        "minimax_regret": _round(float(decisions["weighted_max_goal_regret"].max())),
        "life_safety_veto_passed": bool(decisions["life_safety_regret"].max() == 0.0),
    }
    return metrics, decisions


def _standardized_matrix(
    frame: pd.DataFrame,
    feature_columns: list[str],
    means: dict[str, float],
    stds: dict[str, float],
) -> np.ndarray:
    values = frame[feature_columns].astype(float).copy()
    for column in feature_columns:
        values[column] = (values[column] - means[column]) / stds[column]
    return values.to_numpy()


def _validate_frame(frame: pd.DataFrame) -> pd.DataFrame:
    required_columns = {"date", "ticker", "forward_return", "realized_outcome", *FEATURE_COLUMNS}
    missing = sorted(required_columns - set(frame.columns))
    if missing:
        raise ValueError(f"ML backtest frame is missing columns: {missing}")
    cleaned = frame.copy()
    cleaned["date"] = pd.to_datetime(cleaned["date"]).dt.tz_localize(None).dt.normalize()
    cleaned["ticker"] = cleaned["ticker"].astype(str).str.upper()
    cleaned = cleaned.dropna(subset=[*FEATURE_COLUMNS, "forward_return", "realized_outcome"])
    return cleaned.sort_values(["date", "ticker"]).reset_index(drop=True)


def _split_train_test(
    frame: pd.DataFrame,
    config: MLBacktestConfig,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    train_start = pd.Timestamp(config.train_start)
    train_end = pd.Timestamp(config.train_end)
    test_start = pd.Timestamp(config.test_start)
    test_end = pd.Timestamp(config.test_end)
    tickers = {ticker.upper() for ticker in config.tickers}
    scoped = frame[frame["ticker"].isin(tickers)].copy()
    train = scoped[(scoped["date"] >= train_start) & (scoped["date"] <= train_end)].copy()
    test = scoped[(scoped["date"] >= test_start) & (scoped["date"] <= test_end)].copy()
    test = _apply_rebalance_spacing(test, config.rebalance_days)
    if train.empty:
        raise ValueError("No training rows found for the requested train period.")
    if test.empty:
        raise ValueError("No test rows found for the requested test period.")
    if train["date"].max() >= test["date"].min():
        raise ValueError("Training period must end before the test period starts.")
    return train.reset_index(drop=True), test.reset_index(drop=True)


def _chronological_validation_split(
    train_frame: pd.DataFrame,
    *,
    validation_fraction: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = sorted(train_frame["date"].unique())
    if len(dates) < 4:
        return train_frame, train_frame.iloc[0:0].copy()
    split_index = int(round(len(dates) * (1.0 - validation_fraction)))
    split_index = min(max(split_index, 1), len(dates) - 1)
    fit_dates = set(dates[:split_index])
    validation_dates = set(dates[split_index:])
    fit = train_frame[train_frame["date"].isin(fit_dates)].copy()
    validation = train_frame[train_frame["date"].isin(validation_dates)].copy()
    return fit.reset_index(drop=True), validation.reset_index(drop=True)


def _apply_rebalance_spacing(frame: pd.DataFrame, rebalance_days: int) -> pd.DataFrame:
    if rebalance_days <= 1 or frame.empty:
        return frame
    dates = sorted(frame["date"].unique())
    selected_dates = set(dates[::rebalance_days])
    return frame[frame["date"].isin(selected_dates)].copy()


def _attach_return_and_regret_columns(
    decisions: pd.DataFrame,
    config: MLBacktestConfig,
) -> pd.DataFrame:
    cost = config.transaction_cost_bps / 10000.0
    forward = decisions["forward_return"].astype(float).to_numpy()
    actions = decisions["action"].to_numpy()
    buy_utility = forward - cost
    sell_utility = -forward - cost
    hold_utility = np.zeros(len(decisions))
    strategy_return = np.where(actions == "BUY", buy_utility, np.where(actions == "SELL", sell_utility, hold_utility))
    best_utility = np.maximum.reduce([buy_utility, hold_utility, sell_utility])

    decisions["strategy_return"] = strategy_return
    decisions["best_hindsight_return"] = best_utility
    decisions["alpha_regret"] = np.maximum(best_utility - strategy_return, 0.0)
    decisions["tail_loss_regret"] = np.maximum(-strategy_return, 0.0)
    decisions["turnover_regret"] = np.where(actions == "HOLD", 0.0, cost)
    decisions["life_safety_regret"] = 0.0

    hold_band = config.hold_band_pct / 100.0
    normalizer = np.maximum.reduce(
        [
            np.abs(forward),
            np.abs(best_utility),
            np.full(len(decisions), max(hold_band, cost, 1e-6)),
        ]
    )
    alpha_component = config.goal_weights["alpha"] * decisions["alpha_regret"].to_numpy() / normalizer
    tail_component = config.goal_weights["tail_loss"] * decisions["tail_loss_regret"].to_numpy() / normalizer
    turnover_component = config.goal_weights["turnover"] * np.where(actions == "HOLD", 0.0, 1.0)
    life_safety_component = decisions["life_safety_regret"].to_numpy()
    decisions["weighted_alpha_regret"] = alpha_component
    decisions["weighted_tail_loss_regret"] = tail_component
    decisions["weighted_turnover_regret"] = turnover_component
    decisions["weighted_max_goal_regret"] = np.maximum.reduce(
        [
            alpha_component,
            tail_component,
            turnover_component,
            life_safety_component,
        ]
    )
    return decisions


def _baseline_actions(frame: pd.DataFrame, config: MLBacktestConfig) -> dict[str, list[str]]:
    return {
        "always_hold": ["HOLD"] * len(frame),
        "always_buy": ["BUY"] * len(frame),
        "technical_trend_rule": _technical_trend_actions(frame, config),
    }


def _ranked_actions(
    frame: pd.DataFrame,
    predictions: np.ndarray,
    *,
    top_count: int,
    include_short: bool,
) -> list[str]:
    ranked = frame[["date", "ticker"]].copy()
    ranked["_prediction"] = predictions
    ranked["_position"] = np.arange(len(ranked))
    actions = ["HOLD"] * len(ranked)
    for _, date_frame in ranked.groupby("date", sort=True):
        count = min(top_count, len(date_frame))
        ordered = date_frame.sort_values(["_prediction", "ticker"])
        if include_short:
            for position in ordered.head(count)["_position"]:
                actions[int(position)] = "SELL"
        for position in ordered.tail(count)["_position"]:
            actions[int(position)] = "BUY"
    return actions


def _technical_trend_actions(frame: pd.DataFrame, config: MLBacktestConfig) -> list[str]:
    threshold = config.hold_band_pct / 100.0
    actions = []
    for _, row in frame.iterrows():
        if row["return_21d"] > threshold / 2 and row["ma_gap_20_200"] > 0:
            actions.append("BUY")
        elif row["return_21d"] < -threshold / 2 and row["ma_gap_20_200"] < 0:
            actions.append("SELL")
        else:
            actions.append("HOLD")
    return actions


def _performance_verdict(scorecard: dict[str, Any]) -> dict[str, Any]:
    ml = scorecard["ridge_return_minimax"]
    competitors = {name: metrics for name, metrics in scorecard.items() if name != "ridge_return_minimax"}
    best_competitor_regret = min(metrics["minimax_regret"] for metrics in competitors.values())
    best_competitor_return = max(metrics["average_strategy_return"] for metrics in competitors.values())
    hold = scorecard["always_hold"]
    always_buy = scorecard["always_buy"]
    practical_period_gate = (
        ml["average_strategy_return"] > 0
        and ml["cumulative_return"] > 0
        and ml["mean_weighted_max_goal_regret"] < hold["mean_weighted_max_goal_regret"]
        and ml["cvar_95_loss"] < always_buy["cvar_95_loss"]
        and ml["max_drawdown"] < always_buy["max_drawdown"]
        and ml["life_safety_veto_passed"]
    )
    strict_minimax_gate = ml["minimax_regret"] <= best_competitor_regret
    return_leader_gate = ml["average_strategy_return"] >= best_competitor_return
    if practical_period_gate and not strict_minimax_gate:
        summary = (
            "ML policy performed well on the practical period gate, but strict worst-case minimax regret "
            "still favors a no-trade HOLD baseline; treat this as research evidence rather than deployment approval."
        )
    elif practical_period_gate and strict_minimax_gate:
        summary = "ML policy passed both the practical period gate and the strict minimax-regret gate."
    else:
        summary = (
            "ML policy is reportable, but at least one practical gate remains weak; require further validation before deployment."
        )
    return {
        "passes_practical_period_gate": practical_period_gate,
        "passes_strict_minimax_gate": strict_minimax_gate,
        "passes_return_leader_gate": return_leader_gate,
        "strict_minimax_reference": (
            "A pure minimax regret objective can prefer HOLD because HOLD has zero one-period loss, "
            "even when an alpha policy has positive return and lower mean regret."
        ),
        "summary": summary,
    }


def _methodology_payload(config: MLBacktestConfig) -> dict[str, Any]:
    cost = config.transaction_cost_bps / 10000.0
    return {
        "task_type": "prediction + optimization + evaluation",
        "prediction_target": "future close-to-close return over forward_days",
        "training_rule": "fit ridge regression on train rows only; select alpha and threshold/rank policy on a later validation slice",
        "decision_rule": "absolute threshold or cross-sectional rank policy over predicted forward returns",
        "utility_math": {
            "BUY": "forward_return - transaction_cost",
            "SELL": "-forward_return - transaction_cost",
            "HOLD": "0",
            "transaction_cost": cost,
        },
        "regret_math": {
            "hindsight_best": "max(BUY_utility, HOLD_utility, SELL_utility)",
            "alpha_regret": "hindsight_best - chosen_utility",
            "tail_loss_regret": "max(0, -chosen_utility)",
            "turnover_regret": "transaction_cost if action != HOLD else 0",
            "weighted_max_goal_regret": "max(weighted normalized alpha, tail-loss, turnover, life-safety regrets)",
            "minimax_regret": "max weighted_max_goal_regret over the backtested test period",
        },
        "safety_boundary": (
            "This pipeline emits offline advisory decisions only. It never places orders, contacts counterparties, "
            "publishes recommendations, or mutates external systems."
        ),
    }


def _config_payload(config: MLBacktestConfig) -> dict[str, Any]:
    return {
        "train_start": config.train_start,
        "train_end": config.train_end,
        "test_start": config.test_start,
        "test_end": config.test_end,
        "forward_days": config.forward_days,
        "rebalance_days": config.rebalance_days,
        "hold_band_pct": config.hold_band_pct,
        "transaction_cost_bps": config.transaction_cost_bps,
        "history_period": config.history_period,
        "validation_fraction": config.validation_fraction,
        "goal_weights": config.goal_weights,
    }


def _cvar_loss(returns: list[float], *, tail_fraction: float) -> float:
    if not returns:
        return 0.0
    losses = sorted([-value for value in returns], reverse=True)
    tail_count = max(1, int(np.ceil(len(losses) * tail_fraction)))
    return float(sum(losses[:tail_count]) / tail_count)


def _records_for_json(frame: pd.DataFrame) -> list[dict[str, Any]]:
    records = []
    for record in frame.sort_values(["date", "ticker"]).to_dict(orient="records"):
        clean_record = {}
        for key, value in record.items():
            if isinstance(value, pd.Timestamp):
                clean_record[key] = value.date().isoformat()
            elif isinstance(value, (float, np.floating)):
                clean_record[key] = round(float(value), 8)
            else:
                clean_record[key] = value
        records.append(clean_record)
    return records


def _date_string(value: Any) -> str:
    return pd.Timestamp(value).date().isoformat()


def _round(value: float, digits: int = 6) -> float:
    return round(float(value), digits)
