# Safe MarketUniverses v1

## Abstract

Safe MarketUniverses is a benchmark for long-horizon, tool-using recommendation agents operating under uncertainty, interruption, and partial oversight. Rather than asking whether a single stock recommendation sounds plausible, the benchmark evaluates whether a committee-based agent system remains calibrated, defers appropriately, and produces reviewable trajectories over multi-step historical replay episodes. Each episode combines real market data, explicit mandate constraints, finite oversight budgets, and first-class corrupted-evidence events. The benchmark measures selective risk, abstention gain, expected calibration error, intervention efficiency, worst-regime performance, and corruption sensitivity, while also logging explicit failure labels such as unsafe non-abstention, oversight miss, and regime-shift brittleness. In the frozen tuning matrix used for this note, the tuned budget-1 overseer reduced oversight overreach by four cases relative to the earlier validation baseline, improved expected calibration error by 0.1509, and preserved elevated review on corrupted-evidence steps, while still revealing that recent-drawdown states remain the hardest named slice. The value of the benchmark is therefore diagnostic, not flattering. It provides a compact environment for studying calibrated deferral, interruption handling, and hybrid audit design in long-horizon agents without requiring a full trading simulator.

## 30-Second Verbal Explanation

This project is a safety benchmark disguised as stock analysis. A few specialized agents analyze the same market state, an abstention layer decides whether the system is reliable enough to act, and an overseer uses a limited review budget to interrupt risky decisions. The benchmark is useful because it logs not just what the agent said, but when it should have deferred, when oversight helped, and where the system still failed under regime shifts or corrupted evidence.

## 1. Problem And Motivation

Many current agent evaluations collapse two separate questions into one:

- did the system comply with the requested task?
- was the resulting output actually trustworthy?

Those are not the same. A system can comply with instructions, maintain a clean schema, and still produce poor or fragile output. This becomes more important in long-horizon settings because errors compound across steps, while human review becomes increasingly expensive and expertise-intensive.

Safe MarketUniverses is motivated by four concrete gaps:

1. single-turn benchmarks often overestimate trustworthiness because they judge surface plausibility rather than multi-step behavior
2. many demos implicitly force action even when the system should defer or abstain
3. human oversight is usually modeled as free or unlimited, which is unrealistic
4. corrupted or stale evidence is often treated as a side stress test rather than a first-class benchmark condition

The finance setting is useful because identical evidence naturally supports multiple reasonable policies. A momentum-oriented system, a value-oriented system, and a volatility-sensitive system can see the same numbers and still disagree. That makes disagreement, abstention, and oversight observable rather than artificial.

### 1.1 Relation To Existing Benchmarks

Safe MarketUniverses sits between three benchmark families.

Agent benchmarks such as WebArena, AgentBench, tau-bench, and SWE-bench motivate realistic multi-step evaluation, tool use, and outcome-grounded tasks. Financial LLM benchmarks such as FinanceBench, FinBen, InvestorBench, and TradingAgents motivate domain-specific financial reasoning and decision-making. Agent safety benchmarks such as AgentHarm, Agent-SafetyBench, and tool-risk evaluations motivate explicit safety measurement.

The gap addressed here is narrower: calibrated deferral and finite-budget oversight in sequential recommendation agents. The benchmark is not a broad finance leaderboard and not a trading-performance claim. Its contribution is a compact setting where acting, verifying, abstaining, and escalating are all first-class behaviors measured through trajectory artifacts.

The artifact contract is aligned with current benchmark-submission norms: executable code for benchmark environments, documented metadata, clear data provenance, and enough scripts and parameters for another team to rerun the evaluation. The current package includes Croissant metadata and reproducibility documents, while still treating the missing archival release, incomplete human audit, and incomplete multi-model run matrix as open blockers.

## 2. Benchmark Design

### 2.1 Environment

Each episode is a historical replay over daily U.S. equities. The environment emits an observation at each step containing:

- market features derived from real Yahoo Finance data
- tool evidence summaries
- the current mandate and policy constraints
- the previous-step summary
- remaining oversight budget
- visible interruption or corruption events

The action space is recommendation-centric rather than brokerage-centric:

- directional actions: `BUY`, `HOLD`, `SELL`
- safe deferrals: `ABSTAIN`, `VERIFY`, `ESCALATE`

This keeps the benchmark focused on safe decision quality rather than portfolio engineering.

### 2.2 Committee, Abstention, And Oversight

Three strategy agents vote independently:

- Momentum Trader
- Value Contrarian
- Volatility Averse

These agents do not see one another’s outputs before the oversight stage. Their votes are passed into an abstention module that estimates reliability from:

- disagreement structure
- confidence spread
- evidence consistency checks
- verification need
- mandate tension

An overseer then decides whether to:

- approve the committee majority
- request verification
- force abstention
- escalate to a human

The overseer operates under a finite oversight budget, which allows the benchmark to study the economics of intervention rather than pretending review is free.

### 2.3 Corrupted Evidence And Interruptions

Safe MarketUniverses treats corrupted evidence and interruptions as first-class events. In v1 these include cases such as:

- stale or contradictory tool fields
- misleading summaries
- mandate changes
- warning-bearing observations

This matters because many real failures occur not within a perfectly clean task, but when multiple imperfect components interact.

## 3. Failure Taxonomy

The benchmark encodes failure labels directly in the trajectory logs:

- `state_tracking_failure`
- `overconfident_action`
- `unsafe_non_abstention`
- `policy_violation`
- `oversight_miss`
- `oversight_overreach`
- `corrupted_evidence_susceptibility`
- `regime_shift_brittleness`
- `explanation_action_mismatch`
- `recovery_failure_after_interruption`

This taxonomy is intentionally behavioral rather than purely financial. The goal is not only to ask whether a recommendation was correct, but to ask what kind of unsafe or unhelpful reasoning pattern produced it.

## 4. Experimental Setup

### 4.1 Frozen v1 Specification

The canonical benchmark configuration is:

- 12 tickers
- 120 episodes
- 4 steps per episode
- oversight budget `1`
- random seed `20260414`
- corrupted evidence enabled
- sampled model judging on a small audit slice

Metrics are reported in two namespaces. Majority-vote metrics evaluate the committee's counterfactual recommendation before abstention and oversight. Executed-action metrics evaluate the action actually taken after abstention and oversight. This separation prevents a deferred or verified step from being misread as if it were an ordinary directional recommendation.

The ticker universe is chosen to cover several benchmark slices:

- steady large-cap
- sideways low-signal
- high-momentum speculative
- recent drawdown
- higher-volatility or corruption-sensitive cases

### 4.2 Frozen Tuning Matrix Used In This Note

The frozen tuning matrix is the policy-selection artifact rather than the main empirical artifact:

- tickers: `COST`, `JNJ`, `HIMS`, `TSLA`
- horizons: `4`
- oversight budgets: `0`, `1`, `2`
- corruption: on and off
- judge sample size: `2`
- seed: `20260414`

This matrix is useful because it isolates the oversight and abstention policy question directly: when should the system spend scarce review budget, and when should it approve, defer, or escalate under imperfect evidence?

### 4.3 Primary Evaluation Suite

The primary metrics are:

- selective risk
- abstention gain
- expected calibration error
- intervention rate
- utility per intervention
- worst-regime error
- corruption comparison
- review rate

Three definitions matter in particular.

Selective risk:

\[
\text{Selective Risk} = 1 - \frac{\text{correct covered actions}}{\text{covered actions}}
\]

Abstention gain:

\[
\text{Abstention Gain} = \text{Always-Act Risk} - \text{Selective Risk}
\]

Expected calibration error:

\[
\text{ECE} = \sum_{b=1}^{B} \frac{|S_b|}{n}\left|\mathrm{acc}(S_b) - \mathrm{conf}(S_b)\right|
\]

where \(S_b\) is a confidence bin, \(\mathrm{acc}\) is empirical correctness, and \(\mathrm{conf}\) is mean stated reliability in that bin.

Two interpretation guardrails are important. First, the abstention curve is a reliability-threshold diagnostic over committee-majority correctness, while headline selective risk is measured on the final executed action after abstention and oversight. Second, oversight-budget curves derived from stored recommendations are descriptive replay diagnostics; the primary budget evidence comes from separately executed budget-specific runs in the publication suite.

### 4.4 Artifact Contract

Each run writes a self-contained folder:

- `benchmark_config.json`
- `progress.json`
- `summary.json`
- `episode_specs.json`
- `episodes/*.json`
- `trajectories.jsonl`
- `human_audit_candidates.jsonl`
- `gold_slice_candidates.jsonl`
- `gold_slice_review_template.csv`
- `gold_slice_rubric.md`
- `failure_gallery.json`

The validator checks more than file presence: it verifies that the run is complete, trajectory counts match summary counts, episode files match episode specs, audit-candidate row counts match the declared audit target, and headline metrics such as action distribution, total reward, and utility per intervention are consistent with the trajectory log. This supports both automated analysis and a compact human gold-slice workflow.

## 5. Main Results

### 5.1 Canonical Headline Run

The canonical headline run at `outputs/benchmark/smu_headline_v1/summary.json` is the current main empirical artifact. It contains `120` episodes, `480` steps, `12` tickers, corrupted-evidence events, a budget-1 overseer, and sampled model-based quality judging. It does not present the system as solved. It shows a modest but real selective-risk benefit, clear corruption review pressure, and persistent brittleness in the hardest regimes.

| Metric | Value | Interpretation |
| --- | ---: | --- |
| Episodes / steps | `120 / 480` | Large enough for an application-grade v1, still cheap enough to inspect |
| Executed coverage | `86.0%` | The system acts most of the time rather than deferring constantly |
| Selective risk | `41.6%` | Error rate on covered actions |
| Always-act risk | `44.4%` | Baseline risk if the committee always acts |
| Abstention gain | `+0.0273` | Abstention helps modestly overall |
| Best abstention gain | `+0.0851` at threshold `0.8` | A stricter operating point improves risk at lower coverage |
| Majority-vote ECE | `0.2636` | Reliability is still imperfect for committee-majority correctness |
| Executed-action ECE | `0.2683` | Calibration remains imperfect after abstention and oversight |
| Intervention rate | `14.0%` | Oversight is selective rather than constant |
| Review rate | `27.5%` | More than one quarter of steps are flagged for audit |
| Worst named regime | `recent_drawdown` at `64.8%` error | The hardest slice is a market-regime problem, not a formatting problem |

### 5.2 Frozen Matrix Outcome

The frozen tuning matrix at `outputs/benchmark/smu_tuning_matrix_v1/matrix_summary.json` remains the policy-selection artifact. It sweeps budgets `0`, `1`, and `2` across clean and corrupted conditions for `COST`, `JNJ`, `HIMS`, and `TSLA`, then compares the tuned policy against the older baseline `smu_validation_v4`.

Relative to `smu_validation_v4`, the tuned matrix showed:

- `oversight_overreach` reduced by `4`
- unnecessary `VERIFY` on correct `HOLD` states reduced by `3`
- expected calibration error improved by `0.1509`
- abstention gain improved by `0.0603`
- corrupted-evidence steps still pushed into elevated review rather than being silently approved
- no severe-failure cases receiving a clean `pass`

All frozen-matrix acceptance gates now pass. The matrix also makes an important negative result legible: recent-drawdown remains the hardest named benchmark slice across every budget/corruption cell.

### 5.3 Budget Tradeoff

The most useful comparison in the matrix is not “best reward wins,” but how much extra safety budget buys before it turns into overreach.

On the corrupted slice:

| Budget | Selective risk | Intervention rate | Overreach failures | Verify on correct hold | Reading |
| --- | ---: | ---: | ---: | ---: | --- |
| `0` | `40.6%` | `0.0%` | `0` | `0` | No review spend, but more unresolved risk passes through |
| `1` | `35.7%` | `12.5%` | `0` | `0` | Best compromise between catches and restraint |
| `2` | `32.0%` | `21.9%` | `1` | `1` | Slightly safer on raw error, but renewed overreach appears |

This is why budget `1` is the current headline setting. Budget `2` does reduce false negatives further, but it also makes the overseer more trigger-happy and less interpretable.

### 5.4 Regime And Corruption Results

The full headline run confirms that the benchmark is measuring difficulty, not only compliance.

| Regime | Steps | Majority error | Review rate |
| --- | ---: | ---: | ---: |
| `steady_large_cap` | `88` | `17.1%` | `17.1%` |
| `sideways_low_signal` | `88` | `22.7%` | `19.3%` |
| `high_volatility_news_sensitive` | `44` | `54.5%` | `22.7%` |
| `high_momentum_speculative` | `88` | `63.6%` | `33.0%` |
| `recent_drawdown` | `88` | `64.8%` | `51.1%` |
| `mixed_transition_residual` | `84` | `48.8%` | `19.0%` |

Corrupted evidence has the expected qualitative effect: it raises review pressure and lowers reward.

| Slice | Steps | Majority error | Review rate | Average reward |
| --- | ---: | ---: | ---: | ---: |
| Clean | `360` | `43.3%` | `10.8%` | `0.4128` |
| Corrupted | `120` | `47.5%` | `77.5%` | `0.2767` |

### 5.5 Figures And Tables

The application-grade note includes four core visual artifacts:

1. abstention risk-coverage curve
2. oversight-budget tradeoff curve
3. worst-regime performance table
4. corruption comparison figure

The repo now includes a figure renderer:

```bash
python scripts/render_benchmark_figures.py outputs/benchmark/smu_headline_v1
```

The current headline figure set is written under `report/figures/smu_headline_v1/`.

The current headline table exports are written by:

```bash
python scripts/export_paper_tables.py outputs/benchmark/smu_headline_v1 --output report/tables
```

## 6. Failure Cases

### Failure Case A: Regime-Shift Brittleness

In the canonical headline run, a TSLA recent-drawdown step is labeled `oversight_miss`, `regime_shift_brittleness`, and `state_tracking_failure`. The system wanted to verify the unresolved risk, but no oversight budget remained, so it approved `HOLD` while the realized outcome was `BUY`. This is not a trivial miss. It shows that the benchmark is catching failures that arise from the interaction between calibration, finite oversight, and regime shift rather than from a simple one-step misclassification.

### Failure Case B: Oversight Overreach

The tuning pass substantially reduced `oversight_overreach` on the frozen matrix, but the full canonical run still contains `7` overreach cases and `10` verifications on correct holds. This is informative because it demonstrates a classic safety tradeoff: more review and stronger caution can reduce false negatives while still causing unnecessary friction.

### Failure Case C: Explanation-Action Mismatch

The benchmark also catches `explanation_action_mismatch`, where a rationale appears superficially coherent but fails deterministic consistency checks against the action or evidence. This helps separate schema compliance from actual reasoning quality.

## 7. Hybrid Audit And Human Review

A core design choice in Safe MarketUniverses is separating compliance from trustworthiness.

The audit stack combines:

- deterministic checks for obvious contradictions, policy issues, and mismatch patterns
- sampled model-based quality judgments
- a compact human gold slice emphasizing disagreements, escalations, corrupted-evidence cases, and high-confidence steps

The repo includes:

- `gold_slice_candidates.jsonl`
- `gold_slice_review_template.csv`
- `gold_slice_rubric.md`
- `scripts/build_human_audit_packet.py`
- `scripts/summarize_human_audit.py`

The publication validation target is two independent reviewers over `60` prioritized steps, followed by adjudication. The summary script reports raw reviewer agreement, adjudicated status counts, and model-vs-human agreement against the automated audit status.

Reviewer packets are blinded to the automated audit status and failure labels. The adjudication packet preserves those automated labels only for post-review comparison, so the final model-vs-human table is not contaminated by the initial reviewer interface.

## 8. Limitations

This benchmark is intentionally narrow in several ways:

- it uses daily U.S. equities only
- the current default data path uses `yfinance`; WRDS/CRSP/Compustat access is the preferred academic-data upgrade path, but entitlement must be configured by the researcher
- it studies recommendations, not portfolio execution
- it uses heuristic abstention and oversight rather than learned policies
- it samples model judging rather than exhaustively auditing every step
- it does not yet model richer tool ecosystems or adversarial market narratives
- the current frozen matrix still contains a residual mixed-transition regime bucket with high error, now treated as an explicit diagnostic residual slice rather than as an accidental benchmark class

These are reasonable v1 constraints. They keep the project compact enough to run and inspect while still being rich enough to surface long-horizon safety failures.

## 9. Why This Matters Beyond Finance

The underlying research claim is not “finance is special.” The claim is that long-horizon agents should be evaluated on whether they remain calibrated, interruptible, and reviewable under uncertainty. Finance is simply a convenient domain because disagreement is natural, uncertainty is real, and error costs are easy to reason about.

The same benchmark ideas transfer to:

- policy assistants that summarize uncertain evidence
- research agents that must decide when to defer
- coding agents that must request review under ambiguous requirements
- enterprise agents operating under limited human oversight budgets

## 10. Next Steps

The next iteration should prioritize:

1. completing the remaining publication-suite cells beyond the current `18/54` validated runs
2. completing the two-reviewer, `60`-step human audit and adjudication
3. comparing automated judgments against adjudicated human labels
4. tuning the budget-limited failure mode where the system identifies risk but cannot spend another intervention
5. stress-testing richer corrupted-evidence modes once the benchmark core is stable

## References

- Yao et al. WebArena: A Realistic Web Environment for Building Autonomous Agents, 2023.
- Liu et al. AgentBench: Evaluating LLMs as Agents, 2023.
- Jimenez et al. SWE-bench: Can Language Models Resolve Real-World GitHub Issues?, 2023.
- Islam et al. FinanceBench: A New Benchmark for Financial Question Answering, 2023.
- Xie et al. FinBen: A Holistic Financial Benchmark for Large Language Models, NeurIPS Datasets and Benchmarks, 2024.
- Wang et al. InvestorBench: A Benchmark for Financial Decision-Making Agents, 2024.
- Xiao et al. TradingAgents: Multi-Agents LLM Financial Trading Framework, 2024.
- Andriushchenko et al. AgentHarm: A Benchmark for Measuring Harmfulness of LLM Agents, 2024.
- Zhang et al. Agent-SafetyBench: Evaluating the Safety of LLM Agents, 2024.
- Geifman and El-Yaniv. Selective Classification for Deep Neural Networks, NeurIPS, 2017.
- Guo et al. On Calibration of Modern Neural Networks, ICML, 2017.
- Brier. Verification of Forecasts Expressed in Terms of Probability, Monthly Weather Review, 1950.
- Federal Reserve and OCC. SR 11-7: Guidance on Model Risk Management, 2011.
- NIST. Artificial Intelligence Risk Management Framework 1.0, 2023.
- Gebru et al. Datasheets for Datasets, 2021.

## Appendix: Commands

Verify the environment:

```bash
python -m src.main --verify-setup
```

Run the benchmark:

```bash
python -m src.main --benchmark
```

Review a run:

```bash
python scripts/review_benchmark.py outputs/benchmark/<run_id>
```

Render figures:

```bash
python scripts/render_benchmark_figures.py outputs/benchmark/<run_id>
```
