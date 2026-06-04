# Safe MarketUniverses — Flagship Results: Misspent Oversight

**Flagship question.** Given a finite budget of K human-review tokens per episode, does the model's own expressed uncertainty allocate them to the decisions that actually warrant review when evidence may be corrupted? We report regret against an oracle that spends the same K optimally (computable from hindsight utilities the model never sees).

Primary evidence: headline run with 120 episodes / 480 steps. Robustness: 2160 pooled episodes across the 18 validated `gpt-5.4-mini` cells.

## Calibration (model's own confidence vs. the hand-coded heuristic)

- Honest committee-confidence ECE: `0.1018`
- Hand-coded reliability-heuristic ECE: `0.2636`

The prior paper reported only the heuristic ECE, which measures the author's formula, not the model.

## Allocation regret per step (lower is better; oracle = 0)

| Allocator | K=1 regret | K=2 regret | K=1 precision@K | K=2 precision@K |
| --- | ---: | ---: | ---: | ---: |
| model_signal | `0.1759` (0.1529–0.1994) | `0.3250` (0.2857–0.3625) | `0.4750` | `0.4500` |
| rule_baseline | `0.0911` (0.0726–0.1106) | `0.1143` (0.0909–0.1402) | `0.5522` | `0.5597` |
| random | `0.1911` (0.1770–0.2058) | `0.3361` (0.3044–0.3681) | `0.4333` | `0.4375` |

## Robustness: 0/1 utility-free oracle (review-worthy iff committee majority wrong)

Binary regret/step (lower is better) under an oracle that ignores utility magnitudes — confirms the ranking is not an artifact of the utility scale.

| Allocator | K=1 | K=2 |
| --- | ---: | ---: |
| model_signal | `0.0563` | `0.0938` |
| rule_baseline | `0.0979` | `0.2000` |
| random | `0.0646` | `0.0961` |

## Misspent-oversight decomposition (headline, model_signal)

| Budget | Tokens spent | Overreach spends | Missed worthwhile | Overreach rate | Miss rate |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 120 | 63 | 156 | `0.5250` | `0.7324` |
| 2 | 240 | 132 | 105 | `0.5500` | `0.4930` |

## Corruption split — recall of review-worthy steps (model_signal)

| Budget | Clean recall | Corrupted recall |
| ---: | ---: | ---: |
| 1 | `0.2821` | `0.2281` |
| 2 | `0.4744` | `0.5965` |

## Robustness: per-seed model_signal regret (pooled cells, K=1)

Per-seed regret/step: `20260414`=0.1742, `20260415`=0.1771, `20260416`=0.1735 (mean `0.1749`, range `0.0036`).

## Validity notes

- Oracle is greedy-optimal under a cardinality budget; regret >= 0 by construction.
- model_signal uses only committee confidence/verification_need/disagreement; it never reads overseer rules or action_utilities.
- Model is blind to action_utilities (hindsight), so the measurement is non-circular.
- Trajectories were generated under a rule-based overseer (scaffold-conditioned); this measures the quality of the model's uncertainty as an allocation signal, not online agency.
- The model_signal risk function is fixed a priori and not tuned to the result.
