# ML Backtest Methodology

## Business Problem

The practical problem is not "predict stocks." The practical problem is to choose a supervised, offline alpha policy whose worst hindsight disappointment is small over a declared historical test period, while keeping any action that could affect people, capital, counterparties, or public claims outside the automation boundary.

The pipeline is therefore a multi-goal minimax regret evaluator:

1. Learn a point-in-time return forecast from historical data.
2. Convert the forecast into `BUY`, `HOLD`, or `SELL`.
3. Score the chosen action against the hindsight-best action for the realized return.
4. Report the worst weighted regret across alpha opportunity, tail loss, turnover, and the hard life-safety boundary.

## Formal Definitions

Let `x_t` be the feature vector available at decision date `t`, and let `r_t` be the realized forward return over `H` trading days. The model learns:

```text
hat{r}_t = beta_0 + beta' z_t
```

where `z_t` is the standardized feature vector. Ridge regression solves:

```text
min_beta sum_t (r_t - beta_0 - beta' z_t)^2 + lambda ||beta||_2^2
```

`lambda` is the regularization strength. Regularization means penalizing large coefficients so the model is less likely to overfit noise in a short, unstable market sample.

The first decision rule family is:

```text
BUY  if hat{r}_t > tau
SELL if hat{r}_t < -tau
HOLD otherwise
```

`tau` is the trade threshold. A threshold prevents weak forecasts from becoming unnecessary trades.

The second decision rule family is cross-sectional ranking. At each rebalance date, the policy may buy only the top-ranked forecast, buy the top two forecasts, or run a simple long-short variant that buys top-ranked forecasts and sells bottom-ranked forecasts. This turns a noisy return forecast into a controlled selection problem rather than a blanket market-timing rule.

For transaction cost `c`, action utility is:

```text
u(BUY, r_t)  = r_t - c
u(SELL, r_t) = -r_t - c
u(HOLD, r_t) = 0
```

The hindsight-best utility is:

```text
u*(r_t) = max_a u(a, r_t)
```

Alpha regret is:

```text
R_alpha(a_t, r_t) = u*(r_t) - u(a_t, r_t)
```

Tail-loss regret is:

```text
R_tail(a_t, r_t) = max(0, -u(a_t, r_t))
```

Turnover regret is:

```text
R_turnover(a_t) = c if a_t != HOLD else 0
```

The deployed system is advisory-only, so life-safety regret is zero only because the pipeline does not trade, publish, contact people, or mutate external systems:

```text
R_life = 0
```

The reported strict minimax quantity is:

```text
max_t max_g w_g normalized_R_g(a_t, r_t)
```

This is the worst weighted goal regret seen in the backtested test period.

The practical period gate is separate. It requires positive average and cumulative return, lower mean weighted goal regret than HOLD, lower CVaR loss than always-buy, lower max drawdown than always-buy, and a passed life-safety veto. This prevents the report from pretending that a positive-return alpha policy has defeated a pure no-trade minimax baseline.

## Literature Anchor

- Savage's minimax regret criterion motivates choosing the action with the smallest worst-case hindsight regret: [The Theory of Statistical Decision](https://www.jstor.org/stable/2280094).
- Markowitz's portfolio-selection work makes risk an explicit optimization object rather than an afterthought: [Portfolio Selection](https://www.jstor.org/stable/2975974).
- Rockafellar and Uryasev's CVaR framework motivates reporting tail loss instead of only average return: [Optimization of Conditional Value-at-Risk](https://sites.math.washington.edu/~rtr/papers/rtr179-CVaR1.pdf).
- Modern robust and multiobjective optimization work motivates scoring multiple goals under uncertainty rather than reducing everything to a single profit number: [Multicriteria Adjustable Regret Robust Optimization](https://arxiv.org/abs/2407.17833).
- SR 11-7 model-risk guidance motivates validation, monitoring, and effective challenge before reliance: [Federal Reserve SR 11-7](https://www.federalreserve.gov/supervisionreg/srletters/sr1107.htm).
- NIST AI RMF motivates explicit AI governance around validity, reliability, safety, transparency, accountability, and monitoring: [NIST AI RMF 1.0](https://www.nist.gov/itl/ai-risk-management-framework).
- SEC AI-washing enforcement motivates truthful claims: the report states exactly what the model did, what data period it used, and whether baselines remained competitive: [SEC 2024-36](https://www.sec.gov/newsroom/press-releases/2024-36).

## Implementation Contract

Run:

```bash
python scripts/run_ml_backtest.py COST HIMS SMCI JNJ TSLA \
  --train-start 2024-01-02 \
  --train-end 2024-12-31 \
  --test-start 2025-01-02 \
  --test-end 2025-12-31
```

Output:

```text
outputs/ml_backtest.json
```

The proof fields are:

- `data.train_rows`, `data.validation_rows`, `data.test_rows`
- `model.selected_alpha`, `model.selected_policy_family`, `model.selected_rank_count`, `model.selected_decision_threshold`
- `scorecard.ridge_return_minimax`
- `scorecard.always_hold`
- `scorecard.always_buy`
- `scorecard.technical_trend_rule`
- `performance_verdict`
- `decision_records`

Validation:

```bash
python scripts/check_ml_backtest.py outputs/ml_backtest.json
```

The validator recomputes action utilities, hindsight-best returns, alpha regret, tail-loss regret, turnover regret, weighted max-goal regret, scorecard aggregates, and the declared period gates from the decision records.

## Paper Deployment Boundary

Run:

```bash
python scripts/run_hypothetical_monitor.py --iterations 4
```

This is the only deployment-style loop in the repository. It is intentionally paper-only. It generates hypothetical OHLCV paths, reruns the ML backtest, validates the artifact, and writes a deployment decision for each scenario.

An iteration is blocked unless all of the following are true:

- `paper_only` is true.
- The ML artifact validator passes.
- The life-safety veto passes.
- The practical period gate passes.
- Max drawdown is at or below the configured limit.
- CVaR 95 loss is at or below the configured limit.
- Mean weighted max-goal regret is at or below the configured limit.

The strict minimax gate is still reported. When strict minimax fails but the practical gate passes, the monitor may approve paper monitoring, but it keeps the warning visible and does not authorize live execution.

The scorecard is evidence for offline research only. It is not investment advice and it does not authorize execution.
