from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.benchmark.oversight_allocation import (
    allocate_top_k,
    build_oversight_allocation_report,
    committee_confidence_ece,
    episode_allocation_record,
    episode_utility,
    model_signal_score,
    oracle_score,
    oversight_utility,
    rule_baseline_score,
    step_gain,
)

# Utility scales mirroring the real environment: oversight pays off only on corrupted steps.
CLEAN_UTILS = {"BUY": -0.35, "HOLD": 1.0, "SELL": -0.35, "ABSTAIN": 0.25, "VERIFY": -0.2, "ESCALATE": -0.25}
CORRUPT_UTILS = {"BUY": -0.35, "HOLD": 1.0, "SELL": -0.35, "ABSTAIN": 0.25, "VERIFY": 0.15, "ESCALATE": 0.05}


def _votes(confidences: list[int], verification_need: str, decisions: list[str]) -> dict[str, dict]:
    keys = ["strategy_a", "strategy_b", "strategy_c"]
    return {
        key: {"confidence": conf, "verification_need": verification_need, "decision": decision}
        for key, conf, decision in zip(keys, confidences, decisions, strict=True)
    }


def _step(
    *,
    majority: str,
    realized: str,
    corrupted: bool,
    confidences: list[int],
    verification_need: str,
    decisions: list[str],
    recommended: str = "approve",
    priority: float = 0.0,
    reliability: float = 0.7,
) -> dict:
    utils = CORRUPT_UTILS if corrupted else CLEAN_UTILS
    return {
        "overseer": {
            "counterfactual_majority_action": majority,
            "recommended_decision": recommended,
            "intervention_priority": priority,
        },
        "action_utilities": dict(utils),
        "committee_votes": _votes(confidences, verification_need, decisions),
        "corruption_active": corrupted,
        "majority_correct": majority == realized,
        "realized_outcome": realized,
        "abstention": {"reliability_score": reliability},
    }


def _toy_episode() -> dict:
    return {
        "steps": [
            # step 0: committee correct HOLD, confident -> oversight wasteful (gain < 0)
            _step(majority="HOLD", realized="HOLD", corrupted=False,
                  confidences=[9, 9, 9], verification_need="low", decisions=["HOLD", "HOLD", "HOLD"]),
            # step 1: committee WRONG, corrupted, uncertain -> high gain, model should flag it
            _step(majority="BUY", realized="HOLD", corrupted=True,
                  confidences=[3, 4, 3], verification_need="high", decisions=["BUY", "BUY", "HOLD"],
                  recommended="escalate_human", priority=0.6),
            # step 2: committee WRONG, clean, medium uncertainty -> small positive gain
            _step(majority="SELL", realized="HOLD", corrupted=False,
                  confidences=[6, 6, 5], verification_need="medium", decisions=["SELL", "SELL", "HOLD"],
                  recommended="request_verify", priority=0.3),
        ]
    }


def test_step_gain_sign_matches_intuition():
    steps = _toy_episode()["steps"]
    assert step_gain(steps[0]) < 0      # spending on a correct, confident HOLD is wasteful
    assert step_gain(steps[1]) > 0      # wrong + corrupted -> worth reviewing
    assert step_gain(steps[2]) > 0      # wrong + clean -> mildly worth reviewing
    assert step_gain(steps[1]) > step_gain(steps[2])  # corruption raises the payoff


def test_oversight_utility_is_better_of_verify_escalate():
    steps = _toy_episode()["steps"]
    assert oversight_utility(steps[1]) == 0.15   # max(VERIFY=0.15, ESCALATE=0.05)
    assert oversight_utility(steps[0]) == -0.2   # max(VERIFY=-0.2, ESCALATE=-0.25)


def test_oracle_never_spends_on_nonpositive_gain():
    steps = _toy_episode()["steps"]
    # budget 3 but only 2 steps have positive gain -> oracle spends on exactly those 2
    choice = allocate_top_k(steps, oracle_score, budget=3, oracle=True)
    assert choice == {1, 2}


def test_oracle_is_optimal_and_regret_nonnegative():
    steps = _toy_episode()["steps"]
    for budget in (1, 2, 3):
        oracle_choice = allocate_top_k(steps, oracle_score, budget, oracle=True)
        oracle_util = episode_utility(steps, oracle_choice)
        for score_fn in (model_signal_score, rule_baseline_score):
            alloc_util = episode_utility(steps, allocate_top_k(steps, score_fn, budget))
            assert oracle_util >= alloc_util - 1e-9
            record = episode_allocation_record(steps, score_fn, budget)
            assert record["regret"] >= -1e-9
            if record["precision_at_k"] is not None:
                assert 0.0 <= record["precision_at_k"] <= 1.0


def test_model_signal_beats_random_on_the_planted_episode():
    episodes = [_toy_episode()]
    report = build_oversight_allocation_report(episodes, budgets=(1,))
    model_regret = report["allocators"]["model_signal"][1]["mean_regret_per_step"]
    random_regret = report["allocators"]["random"][1]["mean_regret_per_step"]
    oracle_should_be_zero = report["allocators"]["model_signal"][1]["mean_regret_per_step"]
    assert model_regret < random_regret          # the model's uncertainty finds the risky step
    assert oracle_should_be_zero == 0.0           # model matches oracle here at K=1


def test_model_signal_flags_the_corrupted_risky_step_at_k1():
    steps = _toy_episode()["steps"]
    choice = allocate_top_k(steps, model_signal_score, budget=1)
    assert choice == {1}                          # the uncertain, corrupted, wrong step


def test_corruption_recall_distinguishes_clean_and_corrupted():
    report = build_oversight_allocation_report([_toy_episode()], budgets=(1,))
    rec = report["corruption_recall"]["model_signal"][1]
    assert rec["corrupted"]["worth_spending"] == 1
    assert rec["corrupted"]["caught"] == 1        # at K=1 the model catches the corrupted risky step


def test_committee_confidence_ece_matches_hand_computation():
    records = [
        _step(majority="HOLD", realized="HOLD", corrupted=False,
              confidences=[10, 10, 10], verification_need="low", decisions=["HOLD", "HOLD", "HOLD"]),
        _step(majority="BUY", realized="HOLD", corrupted=False,
              confidences=[2, 2, 2], verification_need="high", decisions=["BUY", "BUY", "BUY"]),
    ]
    # bins=1: avg_conf = (1.0 + 0.2)/2 = 0.6 ; avg_acc = (1 + 0)/2 = 0.5 ; ECE = 0.1
    assert committee_confidence_ece(records, bins=1) == 0.1


def test_report_structure_is_complete():
    report = build_oversight_allocation_report([_toy_episode()], budgets=(1, 2))
    assert report["schema"] == "oversight_allocation_v1"
    assert set(report["allocators"]) == {"model_signal", "rule_baseline", "random"}
    assert "committee_confidence_ece" in report["calibration"]
    assert "heuristic_reliability_ece" in report["calibration"]
    for name in ("model_signal", "rule_baseline", "random"):
        for budget in (1, 2):
            cell = report["allocators"][name][budget]
            assert cell["regret_ci_lower"] <= cell["mean_regret_per_step"] <= cell["regret_ci_upper"] + 1e-9
