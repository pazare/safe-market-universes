from __future__ import annotations

import json
from pathlib import Path

from src.ml_artifact_validation import validate_ml_backtest_payload
from src.paper_deployment import (
    PaperDeploymentConfig,
    evaluate_paper_deployment_safety,
    run_hypothetical_monitor,
)
from tests.test_ml_pipeline import _config, _synthetic_feature_frame
from src.ml_pipeline import run_ml_backtest_on_frame


def test_hypothetical_monitor_writes_paper_only_summary(tmp_path: Path) -> None:
    summary_path = run_hypothetical_monitor(
        PaperDeploymentConfig(
            tickers=["AAA", "BBB"],
            iterations=1,
            seed=123,
            output_dir=tmp_path / "monitor",
        )
    )

    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    assert summary["mode"] == "paper_only_hypothetical_monitor"
    assert summary["paper_only"] is True
    assert summary["iterations"] == 1
    assert summary["approved_iterations"] + summary["blocked_iterations"] == 1
    assert summary["reports"][0]["external_side_effects"] == "disabled"


def test_deployment_gate_blocks_when_paper_only_is_disabled(tmp_path: Path) -> None:
    payload = run_ml_backtest_on_frame(
        _synthetic_feature_frame(),
        config=_config(tmp_path),
        write_output=False,
    )
    artifact_validation = validate_ml_backtest_payload(payload)

    report = evaluate_paper_deployment_safety(
        payload,
        artifact_validation,
        config=PaperDeploymentConfig(paper_only=False),
        scenario="unit_test",
    )

    assert report["status"] == "blocked"
    assert "live execution is disabled" in report["blockers"][0]
