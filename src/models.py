from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Decision = Literal["BUY", "HOLD", "SELL"]


class StrategyPayload(BaseModel):
    decision: Decision
    confidence: int = Field(ge=1, le=10)
    justification: str = Field(min_length=40)

    model_config = ConfigDict(extra="forbid")


class StrategyResult(StrategyPayload):
    name: str


class StrategyDebatePayload(BaseModel):
    decision: Decision
    confidence: int = Field(ge=1, le=10)
    response_to_peers: str = Field(min_length=40)

    model_config = ConfigDict(extra="forbid")


class StrategyDebateResult(BaseModel):
    name: str
    initial_decision: Decision
    initial_confidence: int = Field(ge=1, le=10)
    updated_decision: Decision
    updated_confidence: int = Field(ge=1, le=10)
    changed_position: bool
    confidence_changed: bool
    response_to_peers: str = Field(min_length=40)

    model_config = ConfigDict(extra="forbid")


class AgreementProfile(BaseModel):
    agents_agree: bool
    disagreement_type: str
    majority_decision: Decision | None = None
    decision_counts: dict[str, int]
    pairwise_agreements: dict[str, bool]
    pairwise_agreement_count: int

    model_config = ConfigDict(extra="forbid")


class EvaluatorPayload(BaseModel):
    analysis: str = Field(min_length=40)

    model_config = ConfigDict(extra="forbid")


class EvaluatorResult(EvaluatorPayload):
    agents_agree: bool
    agreement_profile: AgreementProfile


class DebateSummary(BaseModel):
    triggered: bool
    any_position_changed: bool
    any_confidence_changed: bool
    changed_strategies: list[str]
    post_debate_agreement_profile: AgreementProfile
    participants: dict[str, StrategyDebateResult]

    model_config = ConfigDict(extra="forbid")


class StockRunOutput(BaseModel):
    ticker: str
    run_date: str
    market_data_summary: dict[str, Any]
    strategy_a: StrategyResult
    strategy_b: StrategyResult
    strategy_c: StrategyResult
    evaluator: EvaluatorResult
    debate: DebateSummary | None = None


class BatchSummary(BaseModel):
    strategies: list[str]
    stocks_analyzed: list[str]
    total_agreements: int
    total_disagreements: int
    two_vs_one_splits: int
    three_way_splits: int
    debates_triggered: int
    debates_with_position_change: int
    results: list[dict[str, Any]]

