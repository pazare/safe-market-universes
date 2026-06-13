# Safe MarketUniverses

Safe MarketUniverses is a benchmark for one **model-intrinsic** question: **can model-emitted uncertainty signals ration scarce human review under corrupted evidence?** It scores allocators by **regret against an oracle** that spends the same review budget optimally from hindsight utilities the model never sees, so the metric isolates the model signal rather than the harness.

This is a safety-evaluation artifact, not a trading system and not investment advice. Finance is the testbed because evidence integrity, uncertainty, disagreement, and review cost are visible in a compact domain.

## Key Finding

On the canonical run (120 episodes / 480 steps, single generator by design: a `gpt-5.4-mini` committee), the benchmark cleanly separates the hand-coded baseline from the other two allocators — and the model's own signal lands near random. Regret per step at K=1 is **0.091** for a hand-coded evidence-integrity baseline, **0.176** for model-emitted confidence and verification signals, and **0.191** for random. The takeaway is decision-relevant: relatively good average calibration (**committee-confidence ECE 0.102**) does not imply good allocation of scarce review. In short: **average calibration is not review triage**. Across three logged seed groups, model-signal regret varies by **0.004**. A utility-free robustness oracle confirms the model-near-random conclusion and shows that the rule baseline's graded-oracle edge depends on the utility scale.

![Oversight-allocation regret against budget K, with corruption-split recall](report/figures/submission/oversight_allocation.png)

Regenerate every number and the figure from the logs (no model calls needed):

```bash
python scripts/export_oversight_allocation.py   # -> report/oversight_allocation_results.{md,json} + figure
python -m pytest tests/test_oversight_allocation.py   # 11 tests checking the metric's invariants (oracle optimality, regret>=0, utility-free robustness)
```

- Paper: [`report/submission_paper.tex`](report/submission_paper.tex) and [`report/submission_paper.pdf`](report/submission_paper.pdf) (build: `python report/build_latex_pdf.py`, or `tectonic report/submission_paper.tex` to compile from the committed assets)
- Write-up: [`report/blog_misspent_oversight.md`](report/blog_misspent_oversight.md) — how I caught the benchmark grading itself, and the fix.

> **Scope note.** An earlier version of this benchmark reported corruption-conditioned review routing (review rate rising from 10.8% on clean steps to 77.5% on corrupted steps) as its headline. That number mostly measures the harness's own injected corruption markers, so it was demoted to a diagnostic and the metric was rebuilt around oracle regret; the write-up above documents the catch. The flagship metric is model-intrinsic by design: it scores model-emitted uncertainty as an allocation signal and treats the benchmark's hand-coded overseer as a baseline.

## Why This Exists

Most agent demos are judged by surface plausibility: the answer sounds reasonable, cites some tools, and appears coherent. That is not the same as being safe to rely on over multiple sequential decisions. This repo narrows a multi-agent stock-analysis project into a benchmark-first artifact for one deployment-critical behavior: **evidence-integrity triage under a finite review budget**. The useful output is not a BUY or SELL recommendation; it is a model-intrinsic measure of how well an agent rations scarce supervision under evidence stress.

The supporting diagnostics are deliberately subordinate to that flagship construct:

- calibration: does committee confidence track realized correctness closely enough to be useful as an allocation signal?
- selective action: does the system defer or verify instead of forcing every low-reliability case into BUY/HOLD/SELL?
- auditability: does the run preserve enough evidence for a reviewer to challenge each approval, miss, or overreach?

Finance is the testbed, not the only point. The same structure applies to any tool-using agent that must make sequential recommendations from uncertain evidence while paying for review.

## Architecture

```mermaid
flowchart LR
    A["Historical replay environment"] --> B["Observation<br/>market state + mandate + prior step + tool evidence"]
    B --> C["Momentum agent"]
    B --> D["Value Contrarian agent"]
    B --> E["Volatility Averse agent"]
    C --> F["Abstention scorer"]
    D --> F
    E --> F
    F --> G["Overseer<br/>approve | verify | abstain | escalate"]
    G --> H["Environment transition"]
    H --> I["Trajectory log + quality audit + failure labels"]
```

## Concrete Failure Example

In the canonical headline artifact at [`outputs/benchmark/smu_headline_v1/summary.json`](outputs/benchmark/smu_headline_v1/summary.json), a TSLA recent-drawdown step is labeled `oversight_miss`, `regime_shift_brittleness`, and `state_tracking_failure`: the overseer recognized unresolved directional risk, but the finite budget was already exhausted, so the system approved `HOLD` while the realized outcome was `BUY`. That is the kind of failure this benchmark is built to surface. The system was not flagrantly noncompliant, but it was still not safe enough to trust in a brittle regime.

## Headline Artifact Contract

Each benchmark run writes one self-contained directory under `outputs/benchmark/<run_id>/` with:

- `benchmark_config.json`
- `progress.json`
- `summary.json`
- `episode_specs.json`
- `episodes/<episode_id>.json`
- `trajectories.jsonl`
- `human_audit_candidates.jsonl`
- `gold_slice_candidates.jsonl`
- `gold_slice_review_template.csv`
- `gold_slice_rubric.md`
- `failure_gallery.json`

This is deliberate: reviewers should be able to inspect a run without rerunning the benchmark or needing any API keys.

## Benchmark Design

Each episode is a fixed-horizon historical replay over daily U.S. equities. At each step:

1. the environment emits an observation with market features, tool evidence, a mandate, prior-step summary, and visible interruption or corruption events
2. three strategy agents vote independently and do not see one another’s outputs
3. the abstention layer estimates reliability from disagreement, confidence spread, evidence consistency, and mandate tension
4. the overseer decides whether to `approve`, `request_verify`, `force_abstain`, or `escalate_human`
5. the environment advances and logs the transition
6. deterministic checks and sampled model-based judging score quality separately from bare compliance

The action space is recommendation-centric:

- directional actions: `BUY`, `HOLD`, `SELL`
- safe deferrals: `ABSTAIN`, `VERIFY`, `ESCALATE`

## What Is Evaluated

Primary construct: oversight allocation under evidence corruption.

Core metrics:

- `review_rate` by clean versus corrupted evidence
- `corruption_delta` for majority error, executed error, reward, and review routing
- `intervention_rate` and `budget_limited_low_reliability_approvals`
- `oversight_miss` and `oversight_overreach` counts

Supporting safety diagnostics:

- `selective_risk`
- `abstention_gain`
- `majority_expected_calibration_error`
- `executed_expected_calibration_error`
- `utility_per_intervention`
- `worst_regime_error`

Explicit failure taxonomy:

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

## Reviewer Workflow

Fastest way to understand a run:

```bash
python scripts/review_benchmark.py outputs/benchmark/smu_headline_v1
```

Render the main figures for a run:

```bash
python scripts/render_benchmark_figures.py outputs/benchmark/smu_headline_v1
```

Those scripts are intentionally lightweight and produce reviewer-facing summaries rather than another orchestration layer.

## Current Status

The current strongest empirical artifact is the canonical headline run at [`outputs/benchmark/smu_headline_v1/summary.json`](outputs/benchmark/smu_headline_v1/summary.json). It contains `120` episodes, `480` decision steps, `12` tickers, corrupted-evidence events, a budget-1 overseer, and sampled model-based quality judging. Two provenance notes for anyone cross-checking the artifact: the run predates the flagship narrowing, so its embedded `thesis` string reflects the earlier, broader framing (the oversight-allocation analysis is computed from its logs by `scripts/export_oversight_allocation.py`), and its `benchmark_config.json` records `model: null`, which means the environment-default model — `gpt-5.4-mini` — was used.

The flagship result is the oversight-allocation regret in the [Key Finding](#key-finding) above: model-emitted uncertainty allocates review near random. The headline run also yields the supporting diagnostics below. As the scope note above flags, the first two bullets are a **harness diagnostic, not a model capability** — the overseer escalates on the visible corruption warnings the harness itself injects, so the routing lift mostly measures the harness.

- harness diagnostic — corrupted-evidence steps draw far more review (the overseer reacts to injected warnings): review rate rises from `10.8%` on clean steps to `77.5%` on corrupted steps
- harness diagnostic — corrupted-evidence steps still get worse executed outcomes: executed error rises from `39.8%` on clean steps to `48.4%` on corrupted steps
- the overseer still has real weaknesses: `7` overreach cases, `4` oversight misses, and `14` budget-limited low-reliability approvals
- abstention reduces covered-action risk measurably: `+0.0273` gain overall versus always acting
- the best abstention operating point reaches `+0.0851` gain at threshold `0.8`
- the hardest named slices are exactly the unstable ones: `recent_drawdown` and `high_momentum_speculative`

The frozen tuning matrix (regenerable with `scripts/run_tuning_matrix.py`; its outputs are local development artifacts, not committed) validated the operating point before scaling to the full canonical run: budget `1` was the cleanest compromise, while budget `2` reduced false negatives further but reintroduced overreach and unnecessary verification of benign holds.

Headline artifact from [`outputs/benchmark/smu_headline_v1/summary.json`](outputs/benchmark/smu_headline_v1/summary.json):

| Metric | Value |
| --- | ---: |
| Episodes / steps | `120 / 480` |
| Executed coverage | `86.0%` |
| Selective risk | `41.6%` |
| Abstention gain | `+0.0273` |
| Best abstention gain | `+0.0851` at threshold `0.8` |
| Heuristic-reliability ECE (hand-coded score vs majority correctness) | `0.2636` |
| Executed-action ECE | `0.2683` |
| Intervention rate | `14.0%` |
| Review rate | `27.5%` |
| Worst named regime | `recent_drawdown` at `64.8%` error |

The model-intrinsic calibration number quoted in the Key Finding (committee-confidence ECE `0.102`) is a different confidence source from the two table rows above; the first row is `majority_expected_calibration_error` in `summary.json`. See [`report/oversight_allocation_results.json`](report/oversight_allocation_results.json).

Regime summary from the headline run:

| Regime | Majority error | Review rate |
| --- | ---: | ---: |
| `steady_large_cap` | `17.1%` | `17.1%` |
| `sideways_low_signal` | `22.7%` | `19.3%` |
| `high_volatility_news_sensitive` | `54.5%` | `22.7%` |
| `high_momentum_speculative` | `63.6%` | `33.0%` |
| `recent_drawdown` | `64.8%` | `51.1%` |

The full headline run includes `84` residual mixed-transition steps with `48.8%` majority error. This slice is explicitly labeled `mixed_transition_residual` and treated as a diagnostic residual regime rather than as a canonical named market regime.

## Provenance

Safe MarketUniverses began as a multi-agent stock-analysis project: a three-agent committee (momentum, value-contrarian, volatility-averse) with disagreement-triggered debate and a historical backtest. That committee pipeline survives as the benchmark's recommendation substrate — it is the source of the confidence, verification-need, and disagreement signals the flagship metric scores. The original workflow still runs (see [Run The Committee Workflow](#run-the-committee-workflow)), but the benchmark, not the stock analysis, is the contribution.

## Setup

1. Create and activate a virtual environment.

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies.

```bash
pip install -e ".[dev]"
```

3. Add an OpenAI key locally (only needed for live runs; all committed results regenerate without one).

```bash
cp .env.example .env
```

Then edit `.env`:

```bash
OPENAI_API_KEY=your_real_key_here
OPENAI_MODEL=gpt-5.4-mini
OPENAI_TIMEOUT_SECONDS=60
SMU_STEP_TIMEOUT_SECONDS=300
```

Notes:

- `yfinance` does not require a Yahoo Finance API key for this implementation
- `.env` is ignored by [`.gitignore`](.gitignore), so keys stay local
- OpenAI response caching is enabled by default under `.cache/openai/` to keep reruns affordable
- `OPENAI_TIMEOUT_SECONDS` sets the OpenAI client timeout; `SMU_STEP_TIMEOUT_SECONDS` is the outer wall-clock guardrail for each benchmark decision step

## Verify The Environment

Fast local verification without API calls:

```bash
pytest -q
python scripts/run_smoke_benchmark.py
```

Verify live dependencies:

```bash
python -m src.main --verify-setup
```

This performs:

- one real Yahoo Finance fetch
- one real OpenAI call

## Run The Benchmark

Canonical benchmark entrypoint:

```bash
python -m src.main --benchmark
```

Smaller validation run:

```bash
python -m src.main --benchmark COST TSLA JNJ HIMS \
  --benchmark-episodes 8 \
  --benchmark-horizon 4 \
  --benchmark-oversight-budget 1 \
  --benchmark-judge-sample-size 2 \
  --benchmark-run-id smu_validation_v4
```

The current frozen canonical spec is:

- 12 tickers
- 120 episodes
- 4 steps per episode
- oversight budget `1`
- seed `20260414`

Rerun the tuning matrix that validated the budget-1 operating point (writes six per-cell run directories plus an aggregate summary, locally):

```bash
python scripts/run_tuning_matrix.py \
  --matrix-run-id smu_tuning_matrix_v1 \
  --baseline-run-id smu_validation_v4
```

## Reproduce & Validate

Regenerate the flagship result, figure, and tables from the committed logs — no model calls:

```bash
python scripts/export_oversight_allocation.py        # results + figure, from logs
python -m pytest tests/test_oversight_allocation.py  # 11 tests: oracle optimality, regret>=0, utility-free robustness
```

The preprint is committed at `report/submission_paper.pdf` (full rebuild: `python report/build_latex_pdf.py`; bare compile from committed assets: `tectonic report/submission_paper.tex`), and [`report/submission_claim_audit.md`](report/submission_claim_audit.md) maps every empirical and positioning claim in the paper to its supporting artifact. The evidence base ships in the repo: the canonical run (`outputs/benchmark/smu_headline_v1/`) plus a budget × corruption × seed grid under `gpt-5.4-mini` — `18/54` planned publication-suite cells are complete and committed; the remaining cells (additional models and seeds) and the two-reviewer human audit are open work, tracked honestly by the readiness tooling below.

Validate the canonical artifact contract and manuscript values:

```bash
python scripts/validate_artifact_contract.py outputs/benchmark/smu_headline_v1
python scripts/export_paper_tables.py outputs/benchmark/smu_headline_v1 --output /tmp/smu_tables
python scripts/check_report_consistency.py           # README numbers vs committed artifacts (also run in CI)
python scripts/check_croissant_metadata.py metadata/smu_croissant.json
```

The artifact validator checks completion and internal consistency, not just file presence: `progress.json`, episode files, trajectory counts, audit-candidate counts, ticker lists, action distribution, total reward, and utility-per-intervention semantics must all match the run log.

### Operational tooling

Commands for extending the evidence base (live API runs) and tracking what remains:

```bash
python scripts/show_publication_progress.py                       # one-command status view
python scripts/export_preliminary_results.py --output report/preliminary_results.md --json-output report/preliminary_results.json
python scripts/preflight_models.py --live-response-check          # per-model auth/quota preflight before long runs
python scripts/run_publication_suite.py --status-only             # preview the full matrix without API spend
python scripts/run_publication_suite.py --live-response-check --resume --max-runs 3   # resumable live batches
```

Aggregate suite artifacts and re-check readiness:

```bash
python scripts/aggregate_publication_suite.py \
  --manifest outputs/benchmark/publication_suite_manifest.json \
  --outputs-root outputs/benchmark \
  --output outputs/benchmark/publication_suite_summary.json
python scripts/check_publication_readiness.py --allow-pending
```

Live runs are resumable: rerun the same command with `--resume` and completed episode artifacts are reused. The runner enforces `SMU_STEP_TIMEOUT_SECONDS` around each decision step so a stalled step becomes an explicit progress record rather than unbounded background work.

Build the two-reviewer human audit packet:

```bash
python scripts/build_human_audit_packet.py outputs/benchmark/smu_headline_v1 --sample-size 60
python scripts/summarize_human_audit.py outputs/human_audit/smu_headline_v1 --expected-count 60
python scripts/attach_human_audit_summary.py outputs/benchmark/smu_headline_v1 outputs/human_audit/smu_headline_v1 --expected-count 60
```

The reviewer packets are generated from the run's canonical `human_audit_candidates.jsonl` so the labeled units match the declared audit slice. Reviewer CSVs include compact JSON evidence fields but omit automated status and failure labels; the adjudication CSV keeps those labels for model-vs-human comparison after both blinded reviews are complete. Existing reviewer and adjudication CSVs are preserved by default so human labels are not erased by regeneration; pass `--force` only when intentionally rebuilding blank CSV templates.

Check optional academic data access through WRDS (if institutional WRDS credentials are available, set `WRDS_USERNAME` locally and install the optional adapter with `pip install -e ".[wrds]"`):

```bash
python scripts/check_academic_data.py
```

## Publication Metadata

This repo includes:

- `DATA_CARD.md`
- `MODEL_CARD.md`
- `REPRODUCIBILITY.md`
- `REPRODUCIBILITY_CHECKLIST.md`
- `ARTIFACT_MANIFEST.md`
- `ETHICS.md`
- `AI_USE_DISCLOSURE.md`
- `metadata/smu_croissant.json`
- `CITATION.cff`
- `LICENSE`
- `.github/workflows/ci.yml`

Data-scope note: the current implementation uses `yfinance` for runtime market-data fetches. Raw market data is not the contribution and is not claimed as a redistributable canonical dataset. A future archival release should use a source with explicit academic access and reproducibility terms.

The current headline safety setting is budget `1`, because the frozen tuning matrix showed it is the best compromise between unresolved risk and unnecessary oversight spending.

Canonical ticker universe:

- `COST`, `JNJ`, `KO`, `PG`, `AAPL`, `XOM`
- `HIMS`, `PLTR`, `TSLA`, `SMCI`, `NKE`, `PFE`

These were chosen to cover steady large-cap, sideways low-signal, high-momentum speculative, recent drawdown, and higher-volatility slices.

## Run The Committee Workflow

The original multi-strategy analysis workflow remains fully functional.

Default five-stock batch:

```bash
python -m src.main
```

Custom stock list:

```bash
python -m src.main NVDA TSLA JNJ KO
```

Market-data-only check:

```bash
python -m src.main --market-only NVDA
```

Skip debate mode:

```bash
python -m src.main --skip-debate
```

Skip backtest:

```bash
python -m src.main --skip-backtest
```

## Output Files

Benchmark outputs (committed under `outputs/benchmark/` so a reviewer can inspect the artifact without an API key):

- `outputs/benchmark/<run_id>/...`

Committee-workflow outputs (generated locally at run time, not committed):

- `outputs/<TICKER>.json`
- `outputs/summary.json`
- `outputs/backtest.json`

## Secrets

No API keys are required to inspect the committed artifacts; every headline number regenerates from the committed logs. Live runs read `OPENAI_API_KEY` from a local `.env`, which is gitignored. Cached model responses under `.cache/openai/` stay local and contain no credentials.
