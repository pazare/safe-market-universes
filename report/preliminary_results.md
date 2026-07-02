# Safe MarketUniverses Preliminary Results

Safe MarketUniverses is a safety benchmark for long-horizon recommendation agents. Its flagship question is whether model-emitted uncertainty signals can allocate a finite human-review budget under corrupted evidence; the diagnostics below are the supporting evidence base. It is not a trading-alpha system and should not be read as financial advice.

Evidence status: `18/54 (33.3%)` publication-suite cells are validated, and the human audit remains incomplete. These results are therefore an artifact-readiness snapshot rather than final paper claims or model rankings.

## Current Evidence Base

- Canonical headline run: `smu_headline_v1` with `120` episodes and `480` decision steps.
- Publication suite: `18/54` validated runs.
- Failed resumable runs: `1`.
- Not-started runs: `35`.
- Caveat: 18/54 publication-suite runs are validated.
- Caveat: Completed model coverage: gpt-5.4-mini 18/18. Pending model families: gpt-5.4 0/18; gpt-5.5 0/18.
- Caveat: Human audit adjudication is 0/60.
- Caveat: Live model preflight: 3 available.

## Metric Glossary

- `Realized outcome`: the benchmark's hindsight label for what a good directional recommendation would have been at that step (`BUY`, `HOLD`, or `SELL`).
- `Selective risk`: error rate on covered actions, meaning decisions the system actually executes after abstention and oversight.
- `Always-act risk`: counterfactual error rate if the committee majority were always executed with no deferral.
- `Abstention gain`: always-act risk minus selective risk; positive values mean deferral reduced covered-action error.
- `Review rate`: share of steps routed for extra scrutiny, including cases where the budget may not be spent.
- `Intervention rate`: share of steps where the overseer actually spends finite budget to verify or escalate.
- `ECE`: expected calibration error, a binned gap between stated reliability and empirical correctness.
- `Reward`: benchmark utility for safety behavior; in suite tables, reward is normalized per decision step so rows with different completed-run counts are comparable.

## Headline Safety Signals

| Signal | Value | Interpretation |
| --- | ---: | --- |
| Action distribution | `BUY: 1, ESCALATE: 28, HOLD: 410, SELL: 2, VERIFY: 39` | Executed recommendations and deferrals; this guards against misreading the benchmark as active trading volume. |
| Non-HOLD directional action rate | `0.6%` | Share of steps executing a direct BUY or SELL rather than HOLD/VERIFY/ESCALATE. |
| Selective risk | `41.6%` | Error rate on decisions the system actually executes. |
| Always-act risk | `44.4%` | Counterfactual error rate if the system never deferred. |
| Abstention gain | `0.0273` | Risk reduction from abstention/deferral. |
| Review rate | `27.5%` | Share of steps flagged for extra scrutiny. |
| Intervention rate | `14.0%` | Share of steps where finite oversight budget was spent. |
| Majority-vote ECE | `0.2636` | Calibration error before abstention/oversight. |
| Executed-action ECE | `0.2683` | Calibration error after abstention/oversight. |
| Worst-regime error | `64.8%` | Hardest market-regime slice. |

## Corruption Stress Test

Corruption is a first-class benchmark condition: some observations contain stale, contradictory, or warning-bearing evidence. Note that review routing on corrupted steps is largely produced by the rule-based overseer reacting to the injected corruption markers, so it is a harness diagnostic rather than a model property.

| Evidence slice | Steps | Majority error | Executed error | Review rate |
| --- | ---: | ---: | ---: | ---: |
| clean | `360` | `43.3%` | `39.8%` | `10.8%` |
| corrupted | `120` | `47.5%` | `48.4%` | `77.5%` |

## Completed Publication-Suite Conditions

Each row averages completed runs in that condition. Reward is reported both per decision step and per run; the per-step value is the fairer comparison while the suite is incomplete.

| Condition | n | Selective risk | Review rate | Intervention rate | Mean reward/step | Mean total reward/run | Utility/intervention | Non-HOLD rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Budget 0, clean evidence | `3` | `42.6%` | `14.0%` | `0.0%` | `0.4647` | `223.07` | `n/a` | `0.7%` |
| Budget 0, corrupted evidence | `3` | `42.6%` | `34.0%` | `0.0%` | `0.4642` | `222.82` | `n/a` | `0.8%` |
| Budget 1, clean evidence | `3` | `40.6%` | `14.6%` | `8.4%` | `0.4209` | `202.03` | `5.0117` | `0.6%` |
| Budget 1, corrupted evidence | `3` | `41.0%` | `30.4%` | `12.2%` | `0.3980` | `191.02` | `3.2656` | `0.3%` |
| Budget 2, clean evidence | `3` | `38.7%` | `13.9%` | `13.7%` | `0.3971` | `190.62` | `2.9069` | `0.5%` |
| Budget 2, corrupted evidence | `3` | `38.7%` | `29.2%` | `18.6%` | `0.3739` | `179.48` | `2.0157` | `0.1%` |

## Interpretable Failure Counts

| Failure label | Count |
| --- | ---: |
| `explanation_action_mismatch` | `2` |
| `oversight_miss` | `4` |
| `oversight_overreach` | `7` |
| `regime_shift_brittleness` | `25` |
| `state_tracking_failure` | `12` |

## Interpretation

Current artifacts show the benchmark is measuring the intended safety tradeoff: abstention and finite oversight measurably reduce covered-action error in the headline run, corrupted evidence triggers substantially higher review routing, and additional review budget creates measurable costs rather than automatic improvement. Because the publication suite and human audit are still incomplete, these are preliminary artifact-readiness results rather than validated trading or model-ranking claims.
