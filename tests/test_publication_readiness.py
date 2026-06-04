from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src import market_data
from src.benchmark.academic_data import check_wrds_configuration
from src.benchmark.episodes import classify_regime
from src.benchmark.metrics import (
    build_experimental_matrix,
    compute_expected_calibration_error,
    compute_executed_calibration_error,
    summarize_corruption,
    summarize_regimes,
)
from src.benchmark.model_registry import configured_model_names, preflight_models


def _record(
    *,
    reliability: float,
    majority_correct: bool,
    executed_action: str,
    realized_outcome: str,
    regime_label: str = "steady_large_cap",
    corruption_active: bool = False,
) -> dict:
    return {
        "regime_label": regime_label,
        "majority_correct": majority_correct,
        "executed_action": executed_action,
        "realized_outcome": realized_outcome,
        "reward": 1.0 if executed_action == realized_outcome else -0.25,
        "policy_violation": False,
        "corruption_active": corruption_active,
        "observation": {
            "market_features": {
                "pct_change_30d": 0.0,
                "short_vs_long_ma_pct": 0.0,
                "volatility_30d": 0.01,
            }
        },
        "abstention": {
            "reliability_score": reliability,
            "recommend_abstain": executed_action == "ABSTAIN",
        },
        "overseer": {
            "counterfactual_majority_action": realized_outcome if majority_correct else "SELL",
        },
        "quality_assessment": {
            "final_audit_status": "needs_review" if corruption_active else "pass",
        },
        "action_utilities": {
            "BUY": 1.0 if realized_outcome == "BUY" else -1.0,
            "HOLD": 1.0 if realized_outcome == "HOLD" else -0.25,
            "SELL": 1.0 if realized_outcome == "SELL" else -1.0,
            "ABSTAIN": 0.25,
            "VERIFY": -0.2,
            "ESCALATE": -0.25,
        },
    }


def test_model_registry_requires_exact_three_models() -> None:
    assert configured_model_names() == ["gpt-5.4-mini", "gpt-5.4", "gpt-5.5"]


def test_model_preflight_records_missing_key_without_substitution(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    report = preflight_models()

    assert [row["status"] for row in report["results"]] == ["not_checked", "not_checked", "not_checked"]
    assert report["policy"]["substitution"] == "no_silent_substitution"


def test_model_preflight_live_response_check_catches_insufficient_quota(monkeypatch) -> None:
    class FakeModels:
        def retrieve(self, model: str) -> dict:
            return {"id": model}

    class FakeResponses:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def create(self, *, model: str, input: str) -> None:
            self.calls.append(model)
            raise RuntimeError("Error code: 429 - insufficient_quota")

    class FakeClient:
        def __init__(self) -> None:
            self.models = FakeModels()
            self.responses = FakeResponses()

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    client = FakeClient()

    report = preflight_models(client=client, live_response_check=True)

    assert [row["status"] for row in report["results"]] == [
        "insufficient_quota",
        "insufficient_quota",
        "insufficient_quota",
    ]
    assert [row["available"] for row in report["results"]] == [False, False, False]
    assert client.responses.calls == ["gpt-5.4-mini", "gpt-5.4", "gpt-5.5"]


def test_wrds_check_is_safe_without_credentials(monkeypatch) -> None:
    monkeypatch.delenv("WRDS_USERNAME", raising=False)

    status = check_wrds_configuration()

    assert status.provider == "wrds"
    assert status.configured is False
    assert status.status == "missing_credentials"


def test_regime_classifier_uses_named_residual_bucket() -> None:
    snapshot = {
        "pct_change_30d": 8.5,
        "short_vs_long_ma_pct": 2.0,
        "volatility_30d": 0.023,
        "atr_pct_of_price": 2.0,
        "recent_drawdown_90d": -5.0,
    }

    assert classify_regime(snapshot) == "mixed_transition_residual"


def test_metric_names_separate_majority_and_executed_correctness() -> None:
    records = [
        _record(reliability=0.8, majority_correct=True, executed_action="HOLD", realized_outcome="HOLD"),
        _record(reliability=0.2, majority_correct=False, executed_action="ABSTAIN", realized_outcome="BUY"),
        _record(
            reliability=0.7,
            majority_correct=False,
            executed_action="HOLD",
            realized_outcome="SELL",
            regime_label="recent_drawdown",
            corruption_active=True,
        ),
    ]

    assert compute_expected_calibration_error(records) >= 0.0
    assert compute_executed_calibration_error(records) >= 0.0
    regime_rows = summarize_regimes(records)
    assert all("majority_error_rate" in row and "executed_error_rate" in row for row in regime_rows)
    corruption_rows = summarize_corruption(records)
    assert all("majority_error_rate" in row and "executed_error_rate" in row for row in corruption_rows)


def test_experimental_matrix_includes_named_ablations() -> None:
    records = [
        _record(reliability=0.9, majority_correct=True, executed_action="HOLD", realized_outcome="HOLD"),
    ]
    matrix = build_experimental_matrix(
        records,
        [
            {
                "budget": 0.0,
                "average_reward": 1.0,
                "false_positive_rate": 0.0,
                "false_negative_rate": 0.0,
            }
        ],
    )
    policies = {row["policy"] for row in matrix}

    assert {
        "committee_only",
        "committee_plus_abstention",
        "committee_plus_abstention_plus_overseer",
        "technical_rule_baseline",
        "overseer_budget_0",
    }.issubset(policies)


def test_market_data_download_writes_and_reuses_cache(monkeypatch, tmp_path: Path) -> None:
    calls = {"count": 0}
    history = pd.DataFrame(
        {
            "Open": [99.0, 100.0],
            "High": [101.0, 102.0],
            "Low": [98.0, 99.0],
            "Close": [100.0, 101.0],
            "Adj Close": [100.0, 101.0],
            "Volume": [1000, 1100],
        },
        index=pd.to_datetime(["2026-01-02", "2026-01-03"]),
    )

    def fake_download(**kwargs):
        calls["count"] += 1
        return history

    monkeypatch.setattr(market_data, "MARKET_DATA_CACHE_DIR", tmp_path)
    monkeypatch.setattr(market_data.yf, "download", fake_download)

    first = market_data.download_price_history("TEST", period="5d")
    second = market_data.download_price_history("TEST", period="5d")

    assert calls["count"] == 1
    assert len(first) == len(second) == 2
    assert list(tmp_path.glob("*.json"))
    assert list(tmp_path.glob("*.csv"))
