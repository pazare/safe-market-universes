from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.benchmark import runtime
from src.benchmark.models import EpisodeSpec


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line]


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _make_episode_spec(episode_id: str, ticker: str, *, seed: int) -> EpisodeSpec:
    return EpisodeSpec(
        episode_id=episode_id,
        ticker=ticker,
        start_date="2024-01-02",
        start_index=0,
        horizon=2,
        regime_label="steady_large_cap",
        mandate={
            "allowed_actions": ["BUY", "HOLD", "SELL"],
            "requires_verify_for_buy": False,
            "requires_verify_for_sell": False,
            "max_confidence_without_verify": 8,
            "policy_notes": ["Use only the supplied market snapshot and tool evidence."],
        },
        oversight_budget=1,
        seed=seed,
    )


def _quality_assessment() -> dict:
    return {
        "factual_grounding": 5,
        "coherence": 5,
        "calibration_appropriateness": 5,
        "policy_compliance": 5,
        "oversight_necessity": 5,
        "final_audit_status": "pass",
        "deterministic_findings": [],
        "model_judge_summary": None,
        "model_judge_confidence": None,
        "human_audit_priority": 0,
    }


def _final_state(*, remaining_budget_after: int) -> dict:
    vote = {
        "decision": "HOLD",
        "confidence": 6,
        "justification": (
            "The snapshot is balanced, so a HOLD keeps the action aligned "
            "with the available evidence and avoids overreacting."
        ),
        "cited_signals": ["trend_tool"],
        "risk_flags": ["balanced_setup"],
        "verification_need": "low",
        "mandate_compliance_note": "This recommendation stays inside the active mandate.",
        "name": "Stub Strategy",
        "strategy_key": "strategy_a",
    }
    return {
        "strategy_a": vote,
        "strategy_b": {**vote, "name": "Stub Strategy B", "strategy_key": "strategy_b"},
        "strategy_c": {**vote, "name": "Stub Strategy C", "strategy_key": "strategy_c"},
        "abstention": {
            "agreement_profile": {"agents_agree": True, "decision_counts": {"HOLD": 3}},
            "disagreement_penalty": 0.0,
            "decision_conflict_penalty": 0.0,
            "confidence_spread": 0,
            "evidence_consistency_score": 1.0,
            "corruption_penalty": 0.0,
            "evidence_integrity_penalty": 0.0,
            "mandate_penalty": 0.0,
            "directional_risk_penalty": 0.0,
            "reliability_score": 0.95,
            "recommend_abstain": False,
            "recommend_verify": False,
            "rationale": "Agreement is high and the evidence is internally consistent.",
        },
        "overseer": {
            "recommended_decision": "approve",
            "decision": "approve",
            "final_action": "HOLD",
            "rationale": "Routine approval is appropriate for a consistent committee outcome.",
            "decision_drivers": ["agreement"],
            "intervention_used": False,
            "budget_spent": 0,
            "remaining_budget_after": remaining_budget_after,
            "policy_flags": [],
            "budget_limited": False,
            "intervention_priority": 0.0,
            "counterfactual_majority_action": "HOLD",
        },
    }


def _completed_record(spec: EpisodeSpec, step_index: int) -> dict:
    final_state = _final_state(remaining_budget_after=spec.oversight_budget)
    return {
        "episode_id": spec.episode_id,
        "ticker": spec.ticker,
        "step_index": step_index,
        "as_of_date": f"2024-01-0{step_index + 2}",
        "regime_label": spec.regime_label,
        "observation_hash": f"{spec.episode_id}:{step_index}",
        "observation": {
            "episode_id": spec.episode_id,
            "ticker": spec.ticker,
            "step_index": step_index,
            "episode_horizon": spec.horizon,
            "regime_label": spec.regime_label,
            "as_of_date": f"2024-01-0{step_index + 2}",
            "market_features": {"current_price": 100.0 + step_index},
            "tool_evidence": {"trend_tool": {"status": "ok"}},
            "mandate": dict(spec.mandate),
            "remaining_oversight_budget": spec.oversight_budget,
            "previous_step_summary": None,
            "visible_events": [],
        },
        "committee_votes": {
            "strategy_a": final_state["strategy_a"],
            "strategy_b": final_state["strategy_b"],
            "strategy_c": final_state["strategy_c"],
        },
        "abstention": final_state["abstention"],
        "overseer": final_state["overseer"],
        "executed_action": "HOLD",
        "realized_outcome": "HOLD",
        "reward": 1.0,
        "reward_components": {
            "task_utility": 1.0,
            "policy_penalty": 0.0,
            "oversight_cost": 0.0,
        },
        "action_utilities": {
            "BUY": -0.35,
            "HOLD": 1.0,
            "SELL": -0.35,
            "ABSTAIN": 0.25,
            "VERIFY": -0.2,
            "ESCALATE": -0.25,
        },
        "majority_correct": True,
        "policy_violation": False,
        "corruption_active": False,
        "failure_labels": [],
        "quality_assessment": _quality_assessment(),
        "latent_flags": [],
    }


def _completed_episode_output(spec: EpisodeSpec) -> dict:
    records = [_completed_record(spec, step_index) for step_index in range(spec.horizon)]
    return {
        "episode_spec": spec.model_dump(),
        "steps": records,
        "total_reward": float(len(records)),
        "interventions_used": 0,
        "executed_coverage": 1.0,
        "policy_violations": 0,
        "corruption_steps": 0,
        "failure_counts": {},
    }


class _StubEnv:
    def __init__(self, episode_spec: EpisodeSpec, history) -> None:
        self.episode_spec = episode_spec
        self.history = history
        self._step_index = 0
        self._remaining_budget = episode_spec.oversight_budget
        self._previous_step_summary = None
        self._pending_context: dict | None = None

    def reset(self, *, seed: int | None = None):
        self._step_index = 0
        self._remaining_budget = self.episode_spec.oversight_budget
        self._previous_step_summary = None
        self._pending_context = None
        return self._observation(), {"episode_id": self.episode_spec.episode_id}

    def bind_step_context(self, context: dict) -> None:
        self._pending_context = dict(context)
        self._remaining_budget = int(context["remaining_budget_after"])

    def step(self, action: str):
        info = {
            "realized_outcome": "HOLD",
            "policy_violation": False,
            "corruption_active": False,
            "reward_components": {
                "task_utility": 1.0,
                "policy_penalty": 0.0,
                "oversight_cost": 0.0,
            },
            "action_utilities": {
                "BUY": -0.35,
                "HOLD": 1.0,
                "SELL": -0.35,
                "ABSTAIN": 0.25,
                "VERIFY": -0.2,
                "ESCALATE": -0.25,
            },
            "latent_flags": [],
        }
        self._previous_step_summary = {
            "executed_action": action,
            "realized_outcome": "HOLD",
            "overseer_decision": (self._pending_context or {}).get("decision"),
            "reliability_score": (self._pending_context or {}).get("reliability_score"),
        }
        self._step_index += 1
        terminated = self._step_index >= self.episode_spec.horizon
        next_observation = None if terminated else self._observation()
        self._pending_context = None
        return next_observation, 1.0, terminated, False, info

    def _observation(self) -> dict:
        step_number = self._step_index + 1
        return {
            "episode_id": self.episode_spec.episode_id,
            "ticker": self.episode_spec.ticker,
            "step_index": self._step_index,
            "episode_horizon": self.episode_spec.horizon,
            "regime_label": self.episode_spec.regime_label,
            "as_of_date": f"2024-01-0{step_number}",
            "market_features": {"current_price": 100.0 + self._step_index},
            "tool_evidence": {
                "trend_tool": {"status": "ok"},
                "valuation_tool": {"status": "ok"},
                "risk_tool": {"status": "ok"},
            },
            "mandate": dict(self.episode_spec.mandate),
            "remaining_oversight_budget": self._remaining_budget,
            "previous_step_summary": self._previous_step_summary,
            "visible_events": [],
            "hidden_environment_flags": [],
            "observation_hash": f"{self.episode_spec.episode_id}:{self._step_index}",
        }


class _InspectingStepGraph:
    def __init__(self, *, progress_path: Path, summary_path: Path, first_episode_id: str) -> None:
        self.progress_path = progress_path
        self.summary_path = summary_path
        self.first_episode_id = first_episode_id
        self.calls = 0
        self.saw_early_progress = False

    def invoke(self, state: dict) -> dict:
        self.calls += 1
        if self.calls == 3:
            assert self.progress_path.exists()
            assert not self.summary_path.exists()
            progress = _read_json(self.progress_path)
            assert progress == {
                "status": "running",
                "run_id": "progress-happy",
                "completed_episodes": 1,
                "total_episodes": 2,
                "completed_steps": 2,
                "expected_steps": 4,
                "last_episode_id": self.first_episode_id,
            }
            self.saw_early_progress = True

        observation = state["observation"]
        return _final_state(remaining_budget_after=observation["remaining_oversight_budget"])


class _FailingStepGraph:
    def invoke(self, state: dict) -> dict:
        raise RuntimeError("step graph exploded")


class _NeverEndingEnv(_StubEnv):
    def step(self, action: str):
        next_observation, reward, terminated, truncated, info = super().step(action)
        return self._observation(), reward, False, False, info


def _patch_runtime_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    *,
    output_root: Path,
    episode_specs: list[EpisodeSpec],
    graph,
) -> None:
    histories = {spec.ticker: object() for spec in episode_specs}

    monkeypatch.setattr(runtime, "BENCHMARK_OUTPUTS_DIR", output_root)
    monkeypatch.setattr(runtime, "build_step_graph", lambda: graph)
    monkeypatch.setattr(runtime, "generate_episode_specs", lambda **kwargs: (episode_specs, histories))
    monkeypatch.setattr(runtime, "SafeMarketUniverseEnv", _StubEnv)
    monkeypatch.setattr(runtime, "build_deterministic_quality_assessment", lambda **kwargs: _quality_assessment())
    monkeypatch.setattr(runtime, "_attach_model_judgments", lambda records, sample_size, model: [])
    monkeypatch.setattr(runtime, "_select_records_for_audit", lambda records, sample_size: [])
    monkeypatch.setattr(runtime, "_build_gold_slice_rows", lambda records, sample_size: [])
    monkeypatch.setattr(runtime, "_headline_metrics", lambda records, episodes: {"reward": 1.0})
    monkeypatch.setattr(runtime, "build_experimental_matrix", lambda records, curve: [{"cell_score": 1.0}])
    monkeypatch.setattr(runtime, "build_abstention_curve", lambda records: [{"threshold": 0.5, "coverage": 1.0}])
    monkeypatch.setattr(
        runtime,
        "build_oversight_budget_curve",
        lambda episodes, budgets: [{"budget": 1, "average_reward": 1.0, "utility_per_intervention": None}],
    )
    monkeypatch.setattr(runtime, "summarize_regimes", lambda records: [{"count": 1, "majority_error_rate": 0.0}])
    monkeypatch.setattr(runtime, "summarize_corruption", lambda records: [{"corruption_rate": 0.0}])
    monkeypatch.setattr(runtime, "build_failure_gallery", lambda records, limit: [])


def test_run_writes_early_progress_and_completion_artifacts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    output_root = tmp_path / "benchmark"
    run_dir = output_root / "progress-happy"
    episode_specs = [
        _make_episode_spec("episode-001", "AAA", seed=1),
        _make_episode_spec("episode-002", "BBB", seed=2),
    ]
    graph = _InspectingStepGraph(
        progress_path=run_dir / "progress.json",
        summary_path=run_dir / "summary.json",
        first_episode_id=episode_specs[0].episode_id,
    )
    _patch_runtime_dependencies(
        monkeypatch,
        output_root=output_root,
        episode_specs=episode_specs,
        graph=graph,
    )

    summary_path = runtime.run_safe_market_universes(
        tickers=["AAA", "BBB"],
        episode_count=2,
        horizon=2,
        oversight_budget=1,
        seed=7,
        judge_sample_size=0,
        run_id="progress-happy",
    )

    assert graph.saw_early_progress
    assert summary_path == run_dir / "summary.json"
    assert run_dir.exists()

    progress = _read_json(run_dir / "progress.json")
    assert progress == {
        "status": "complete",
        "run_id": "progress-happy",
        "completed_episodes": 2,
        "total_episodes": 2,
        "completed_steps": 4,
        "expected_steps": 4,
        "summary_json": str(run_dir / "summary.json"),
    }

    trajectories = _read_jsonl(run_dir / "trajectories.jsonl")
    assert len(trajectories) == 4
    assert [(row["episode_id"], row["step_index"]) for row in trajectories] == [
        ("episode-001", 0),
        ("episode-001", 1),
        ("episode-002", 0),
        ("episode-002", 1),
    ]

    assert (run_dir / "episodes" / "episode-001.json").exists()
    assert (run_dir / "episodes" / "episode-002.json").exists()


def test_step_graph_failure_updates_progress_before_reraising(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "benchmark"
    run_dir = output_root / "progress-failure"
    episode_spec = _make_episode_spec("episode-fail", "ERR", seed=9)
    _patch_runtime_dependencies(
        monkeypatch,
        output_root=output_root,
        episode_specs=[episode_spec],
        graph=_FailingStepGraph(),
    )

    with pytest.raises(RuntimeError, match="step graph exploded"):
        runtime.run_safe_market_universes(
            tickers=["ERR"],
            episode_count=1,
            horizon=2,
            oversight_budget=1,
            seed=9,
            judge_sample_size=0,
            run_id="progress-failure",
        )

    progress = _read_json(run_dir / "progress.json")
    assert progress == {
        "status": "failed",
        "run_id": "progress-failure",
        "completed_episodes": 0,
        "completed_steps": 0,
        "expected_steps": 2,
        "current_episode_id": "episode-fail",
        "current_ticker": "ERR",
        "current_step_index": 0,
        "error_type": "RuntimeError",
        "error": "step graph exploded",
    }


def test_episode_step_guard_prevents_unbounded_environment_loop(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "benchmark"
    run_dir = output_root / "progress-guard"
    episode_spec = _make_episode_spec("episode-loop", "LOOP", seed=10)
    _patch_runtime_dependencies(
        monkeypatch,
        output_root=output_root,
        episode_specs=[episode_spec],
        graph=_InspectingStepGraph(
            progress_path=run_dir / "progress.json",
            summary_path=run_dir / "summary.json",
            first_episode_id=episode_spec.episode_id,
        ),
    )
    monkeypatch.setattr(runtime, "SafeMarketUniverseEnv", _NeverEndingEnv)

    with pytest.raises(RuntimeError, match="exceeded configured horizon"):
        runtime.run_safe_market_universes(
            tickers=["LOOP"],
            episode_count=1,
            horizon=2,
            oversight_budget=1,
            seed=10,
            judge_sample_size=0,
            run_id="progress-guard",
        )

    progress = _read_json(run_dir / "progress.json")
    assert progress["status"] == "failed"
    assert progress["error_type"] == "RuntimeError"
    assert "exceeded configured horizon" in progress["error"]


def test_finalization_failure_updates_progress_before_reraising(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "benchmark"
    run_dir = output_root / "progress-finalization-failure"
    episode_spec = _make_episode_spec("episode-finalize", "JDG", seed=11)
    _patch_runtime_dependencies(
        monkeypatch,
        output_root=output_root,
        episode_specs=[episode_spec],
        graph=_InspectingStepGraph(
            progress_path=run_dir / "progress.json",
            summary_path=run_dir / "summary.json",
            first_episode_id=episode_spec.episode_id,
        ),
    )

    def _raise_model_judgments(records: list[dict], sample_size: int, model: str | None) -> list[dict]:
        assert len(records) == 2
        raise RuntimeError("model judgment exploded")

    monkeypatch.setattr(runtime, "_attach_model_judgments", _raise_model_judgments)

    with pytest.raises(RuntimeError, match="model judgment exploded"):
        runtime.run_safe_market_universes(
            tickers=["JDG"],
            episode_count=1,
            horizon=2,
            oversight_budget=1,
            seed=11,
            judge_sample_size=1,
            run_id="progress-finalization-failure",
        )

    progress = _read_json(run_dir / "progress.json")
    assert progress["status"] == "failed"
    assert progress["run_id"] == "progress-finalization-failure"
    assert progress["completed_episodes"] == 1
    assert progress["completed_steps"] == 2
    assert progress["expected_steps"] == 2
    assert progress["phase"] == "finalization"
    assert progress["error_type"] == "RuntimeError"
    assert progress["error"] == "model judgment exploded"


def test_resume_reuses_completed_episode_artifacts_without_replaying_them(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "benchmark"
    run_dir = output_root / "progress-resume"
    episode_specs = [
        _make_episode_spec("episode-001", "AAA", seed=1),
        _make_episode_spec("episode-002", "BBB", seed=2),
    ]
    completed_episode = _completed_episode_output(episode_specs[0])
    _write_json(run_dir / "episodes" / "episode-001.json", completed_episode)
    _write_jsonl(run_dir / "trajectories.jsonl", completed_episode["steps"])
    _write_json(
        run_dir / "progress.json",
        {
            "status": "failed",
            "run_id": "progress-resume",
            "completed_episodes": 1,
            "completed_steps": 2,
            "expected_steps": 4,
            "error_type": "APIConnectionError",
            "error": "Connection error.",
        },
    )
    graph = _InspectingStepGraph(
        progress_path=run_dir / "progress.json",
        summary_path=run_dir / "summary.json",
        first_episode_id=episode_specs[0].episode_id,
    )
    _patch_runtime_dependencies(
        monkeypatch,
        output_root=output_root,
        episode_specs=episode_specs,
        graph=graph,
    )

    summary_path = runtime.run_safe_market_universes(
        tickers=["AAA", "BBB"],
        episode_count=2,
        horizon=2,
        oversight_budget=1,
        seed=7,
        judge_sample_size=0,
        run_id="progress-resume",
        resume=True,
    )

    assert graph.calls == 2
    assert summary_path == run_dir / "summary.json"
    trajectories = _read_jsonl(run_dir / "trajectories.jsonl")
    assert len(trajectories) == 4
    assert [(row["episode_id"], row["step_index"]) for row in trajectories] == [
        ("episode-001", 0),
        ("episode-001", 1),
        ("episode-002", 0),
        ("episode-002", 1),
    ]
    progress = _read_json(run_dir / "progress.json")
    assert progress["status"] == "complete"
    assert progress["completed_steps"] == 4
