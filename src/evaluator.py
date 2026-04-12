from __future__ import annotations

import json
from collections import Counter
from itertools import combinations
from pathlib import Path
from typing import Any

from .config import PROMPTS_DIR
from .llm import call_structured_model
from .models import AgreementProfile, EvaluatorPayload, EvaluatorResult


def _load_prompt(filename: str) -> str:
    return Path(PROMPTS_DIR / filename).read_text(encoding="utf-8").strip()


def build_agreement_profile(strategies: dict[str, dict[str, Any]]) -> dict[str, Any]:
    decisions = {key: value["decision"] for key, value in strategies.items()}
    decision_counts = Counter(decisions.values())
    pairwise_agreements = {
        f"{left}_vs_{right}": decisions[left] == decisions[right]
        for left, right in combinations(sorted(decisions), 2)
    }
    agents_agree = len(decision_counts) == 1
    majority_decision = None
    disagreement_type = "unanimous"

    if not agents_agree:
        highest_count = max(decision_counts.values())
        if highest_count >= 2:
            majority_decision = next(
                decision for decision, count in decision_counts.items() if count == highest_count
            )
            disagreement_type = "two_vs_one_split"
        else:
            disagreement_type = "three_way_split"

    return AgreementProfile(
        agents_agree=agents_agree,
        disagreement_type=disagreement_type,
        majority_decision=majority_decision,
        decision_counts=dict(decision_counts),
        pairwise_agreements=pairwise_agreements,
        pairwise_agreement_count=sum(1 for agree in pairwise_agreements.values() if agree),
    ).model_dump()


def run_evaluator(
    *,
    ticker: str,
    market_data: dict[str, Any],
    strategies: dict[str, dict[str, Any]],
    agreement_profile: dict[str, Any],
    model: str | None = None,
) -> dict[str, Any]:
    mode = "CONSENSUS" if agreement_profile["agents_agree"] else agreement_profile["disagreement_type"].upper()
    user_prompt = (
        f"Mode: {mode}\n"
        f"Ticker: {ticker}\n\n"
        "Market data summary:\n"
        f"{json.dumps(market_data, indent=2)}\n\n"
        "Agreement profile:\n"
        f"{json.dumps(agreement_profile, indent=2)}\n\n"
        "Strategy outputs:\n"
        f"{json.dumps(strategies, indent=2)}"
    )
    payload = call_structured_model(
        system_prompt=_load_prompt("evaluator.txt"),
        user_prompt=user_prompt,
        schema=EvaluatorPayload,
        model=model,
    )
    return EvaluatorResult(
        agents_agree=agreement_profile["agents_agree"],
        agreement_profile=agreement_profile,
        **payload.model_dump(),
    ).model_dump()
