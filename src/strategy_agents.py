from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import PROMPTS_DIR
from .llm import call_structured_model
from .models import StrategyDebatePayload, StrategyDebateResult, StrategyPayload, StrategyResult

STRATEGY_CONFIGS = {
    "strategy_a": {"name": "Momentum Trader", "prompt_file": "strategy_a.txt"},
    "strategy_b": {"name": "Value Contrarian", "prompt_file": "strategy_b.txt"},
    "strategy_c": {"name": "Volatility Averse", "prompt_file": "strategy_c.txt"},
}


def _load_prompt(filename: str) -> str:
    return Path(PROMPTS_DIR / filename).read_text(encoding="utf-8").strip()


def _build_strategy_user_prompt(*, ticker: str, market_data: dict[str, object]) -> str:
    return (
        f"Ticker: {ticker}\n"
        "Analyze the stock using only the market data below.\n"
        "Reference specific numbers in your justification.\n\n"
        f"{json.dumps(market_data, indent=2)}"
    )


def _build_debate_user_prompt(
    *,
    ticker: str,
    market_data: dict[str, Any],
    initial_result: dict[str, Any],
    peer_results: dict[str, dict[str, Any]],
) -> str:
    return (
        f"Ticker: {ticker}\n"
        "This is a second-round debate.\n"
        "Review the market data, your initial position, and the peer strategies' reasoning.\n"
        "You may keep or revise your decision and confidence, but you must explain why.\n\n"
        "Market data summary:\n"
        f"{json.dumps(market_data, indent=2)}\n\n"
        "Your initial output:\n"
        f"{json.dumps(initial_result, indent=2)}\n\n"
        "Peer outputs:\n"
        f"{json.dumps(peer_results, indent=2)}"
    )


def run_strategy(strategy_key: str, ticker: str, market_data: dict[str, object], model: str | None = None) -> dict[str, object]:
    config = STRATEGY_CONFIGS[strategy_key]
    payload = call_structured_model(
        system_prompt=_load_prompt(config["prompt_file"]),
        user_prompt=_build_strategy_user_prompt(ticker=ticker, market_data=market_data),
        schema=StrategyPayload,
        model=model,
    )
    return StrategyResult(name=config["name"], **payload.model_dump()).model_dump()


def run_strategy_debate(
    strategy_key: str,
    ticker: str,
    market_data: dict[str, Any],
    initial_result: dict[str, Any],
    peer_results: dict[str, dict[str, Any]],
    model: str | None = None,
) -> dict[str, Any]:
    config = STRATEGY_CONFIGS[strategy_key]
    payload = call_structured_model(
        system_prompt=f"{_load_prompt(config['prompt_file'])}\n\n{_load_prompt('debate.txt')}",
        user_prompt=_build_debate_user_prompt(
            ticker=ticker,
            market_data=market_data,
            initial_result=initial_result,
            peer_results=peer_results,
        ),
        schema=StrategyDebatePayload,
        model=model,
    )
    return StrategyDebateResult(
        name=config["name"],
        initial_decision=initial_result["decision"],
        initial_confidence=initial_result["confidence"],
        updated_decision=payload.decision,
        updated_confidence=payload.confidence,
        changed_position=payload.decision != initial_result["decision"],
        confidence_changed=payload.confidence != initial_result["confidence"],
        response_to_peers=payload.response_to_peers,
    ).model_dump()


def run_strategy_a(ticker: str, market_data: dict[str, object], model: str | None = None) -> dict[str, object]:
    return run_strategy("strategy_a", ticker, market_data, model=model)


def run_strategy_b(ticker: str, market_data: dict[str, object], model: str | None = None) -> dict[str, object]:
    return run_strategy("strategy_b", ticker, market_data, model=model)


def run_strategy_c(ticker: str, market_data: dict[str, object], model: str | None = None) -> dict[str, object]:
    return run_strategy("strategy_c", ticker, market_data, model=model)
