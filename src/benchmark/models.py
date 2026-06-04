from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Decision = Literal["BUY", "HOLD", "SELL"]
SystemAction = Literal["BUY", "HOLD", "SELL", "ABSTAIN", "VERIFY", "ESCALATE"]
VerificationNeed = Literal["low", "medium", "high"]
OverseerDecisionType = Literal["approve", "block", "request_verify", "force_abstain", "escalate_human"]
AuditStatus = Literal["pass", "needs_review", "fail"]
VoteMajorityType = Literal["unanimous", "simple_majority", "tie_break_hold"]
RegimeLabel = Literal[
    "steady_large_cap",
    "high_momentum_speculative",
    "recent_drawdown",
    "sideways_low_signal",
    "high_volatility_news_sensitive",
    "mixed_transition_residual",
]


class InterruptionEvent(BaseModel):
    step_index: int = Field(ge=0)
    event_type: str
    description: str
    mandate_updates: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class CorruptionEvent(BaseModel):
    step_index: int = Field(ge=0)
    event_type: str
    description: str
    target_field: str
    visible_warning: bool = False
    warning_message: str | None = None

    model_config = ConfigDict(extra="forbid")


class EpisodeSpec(BaseModel):
    episode_id: str
    ticker: str
    start_date: str
    start_index: int = Field(ge=0)
    horizon: int = Field(ge=2)
    evaluation_window: int = Field(default=5, ge=1)
    regime_label: RegimeLabel
    mandate: dict[str, Any]
    interruption_schedule: list[InterruptionEvent] = Field(default_factory=list)
    corruption_schedule: list[CorruptionEvent] = Field(default_factory=list)
    oversight_budget: int = Field(ge=0)
    seed: int

    model_config = ConfigDict(extra="forbid")


class ObservationModel(BaseModel):
    episode_id: str
    ticker: str
    step_index: int = Field(ge=0)
    episode_horizon: int = Field(ge=1)
    regime_label: RegimeLabel
    as_of_date: str
    market_features: dict[str, Any]
    tool_evidence: dict[str, Any]
    mandate: dict[str, Any]
    remaining_oversight_budget: int = Field(ge=0)
    previous_step_summary: dict[str, Any] | None = None
    visible_events: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class BenchmarkStrategyPayload(BaseModel):
    decision: Decision
    confidence: int = Field(ge=1, le=10)
    justification: str = Field(min_length=40)
    cited_signals: list[str] = Field(default_factory=list, max_length=6)
    risk_flags: list[str] = Field(default_factory=list, max_length=6)
    verification_need: VerificationNeed
    mandate_compliance_note: str = Field(min_length=15)

    model_config = ConfigDict(extra="forbid")


class CommitteeVote(BenchmarkStrategyPayload):
    name: str
    strategy_key: str

    model_config = ConfigDict(extra="forbid")


class AbstentionAssessment(BaseModel):
    agreement_profile: dict[str, Any]
    disagreement_penalty: float = Field(ge=0.0, le=1.0)
    decision_conflict_penalty: float = Field(ge=0.0, le=1.0)
    confidence_spread: int = Field(ge=0, le=9)
    evidence_consistency_score: float = Field(ge=0.0, le=1.0)
    corruption_penalty: float = Field(ge=0.0, le=1.0)
    evidence_integrity_penalty: float = Field(ge=0.0, le=1.0)
    mandate_penalty: float = Field(ge=0.0, le=1.0)
    directional_risk_penalty: float = Field(ge=0.0, le=1.0)
    reliability_score: float = Field(ge=0.0, le=1.0)
    recommend_abstain: bool
    recommend_verify: bool
    rationale: str

    model_config = ConfigDict(extra="forbid")


class OverseerDecision(BaseModel):
    recommended_decision: OverseerDecisionType
    decision: OverseerDecisionType
    final_action: SystemAction
    rationale: str
    decision_drivers: list[str] = Field(default_factory=list)
    intervention_used: bool
    budget_spent: int = Field(ge=0)
    remaining_budget_after: int = Field(ge=0)
    policy_flags: list[str] = Field(default_factory=list)
    budget_limited: bool = False
    intervention_priority: float = Field(ge=0.0, le=1.0)
    counterfactual_majority_action: Decision
    committee_policy_action: Decision | None = None
    vote_majority_type: VoteMajorityType | None = None
    tie_break_rule: str | None = None

    model_config = ConfigDict(extra="forbid")


class QualityAssessment(BaseModel):
    factual_grounding: int = Field(ge=1, le=5)
    coherence: int = Field(ge=1, le=5)
    calibration_appropriateness: int = Field(ge=1, le=5)
    policy_compliance: int = Field(ge=1, le=5)
    oversight_necessity: int = Field(ge=1, le=5)
    final_audit_status: AuditStatus
    deterministic_findings: list[str] = Field(default_factory=list)
    model_judge_summary: str | None = None
    model_judge_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    human_audit_priority: int = Field(ge=0, le=3)

    model_config = ConfigDict(extra="forbid")


class QualityJudgePayload(BaseModel):
    factual_grounding: int = Field(ge=1, le=5)
    coherence: int = Field(ge=1, le=5)
    calibration_appropriateness: int = Field(ge=1, le=5)
    policy_compliance: int = Field(ge=1, le=5)
    oversight_necessity: int = Field(ge=1, le=5)
    final_audit_status: AuditStatus
    summary: str = Field(min_length=40)
    confidence: float = Field(ge=0.0, le=1.0)

    model_config = ConfigDict(extra="forbid")


class StepRecord(BaseModel):
    episode_id: str
    ticker: str
    step_index: int = Field(ge=0)
    as_of_date: str
    regime_label: RegimeLabel
    observation_hash: str
    observation: ObservationModel
    committee_votes: dict[str, CommitteeVote]
    abstention: AbstentionAssessment
    overseer: OverseerDecision
    executed_action: SystemAction
    realized_outcome: Decision
    reward: float
    reward_components: dict[str, float]
    action_utilities: dict[str, float]
    majority_correct: bool
    policy_violation: bool
    corruption_active: bool
    failure_labels: list[str] = Field(default_factory=list)
    quality_assessment: QualityAssessment
    latent_flags: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class EpisodeRunOutput(BaseModel):
    episode_spec: EpisodeSpec
    steps: list[StepRecord]
    total_reward: float
    interventions_used: int
    executed_coverage: float = Field(ge=0.0, le=1.0)
    policy_violations: int = Field(ge=0)
    corruption_steps: int = Field(ge=0)
    failure_counts: dict[str, int]

    model_config = ConfigDict(extra="forbid")


class BenchmarkSummary(BaseModel):
    benchmark_name: str
    thesis: str
    run_id: str
    run_date: str
    schema_version: str
    episode_count: int = Field(ge=0)
    step_count: int = Field(ge=0)
    tickers: list[str]
    model_registry: dict[str, Any]
    data_source_notice: dict[str, Any]
    metric_definitions: dict[str, str]
    confidence_intervals: dict[str, Any]
    artifact_validation: dict[str, Any]
    human_audit_summary: dict[str, Any] | None = None
    experimental_matrix: list[dict[str, Any]]
    headline_metrics: dict[str, Any]
    abstention_curve: list[dict[str, float]]
    oversight_budget_curve: list[dict[str, Any]]
    regime_table: list[dict[str, Any]]
    corruption_comparison: list[dict[str, Any]]
    failure_gallery: list[dict[str, Any]]
    audit_manifest: dict[str, Any]
    artifacts: dict[str, str]

    model_config = ConfigDict(extra="forbid")
