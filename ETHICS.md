# Ethics and Responsible Use

Safe MarketUniverses is a safety-evaluation benchmark. It is not investment advice, not a trading system, and not a claim that any model can produce profitable recommendations.

## Intended Use

- Measure whether model-emitted uncertainty can allocate a finite human-review budget under corrupted evidence (oversight-allocation regret against an oracle).
- Study the supporting diagnostics: calibrated deferral, oversight budgets, corrupted-evidence response, and trajectory auditability.
- Compare agent designs under fixed benchmark conditions.
- Surface failure cases where plausible recommendations are insufficiently safe or reviewable.

## Misuse Risks

- Treating benchmark recommendations as live trading signals.
- Reporting benchmark reward as financial alpha.
- Hiding data-source limitations or model-unavailability exclusions.
- Using generated rationales as factual financial analysis outside the benchmark context.

## Mitigations

- The README, data card, model card, and reports explicitly state that the artifact is not financial advice.
- The artifact validator enforces metric namespaces, regime labels, required files, and ablation coverage.
- The human audit workflow prioritizes high-risk, corrupted, and high-disagreement examples.
- The data card documents the temporary `yfinance` dependency and WRDS/CRSP/Compustat migration path.
