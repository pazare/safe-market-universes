# Model Card

## Evaluation Models

The default publication matrix uses three OpenAI models configured in `benchmark_models.json` (registry aliases in parentheses):

- `gpt-5.4-mini` (`cost_efficient_default`): primary cost-efficient model.
- `gpt-5.4` (`strong_generalist`): strong general-purpose baseline.
- `gpt-5.5` (`frontier_reference`): frontier reference model.

**Completed coverage in this release.** Only `gpt-5.4-mini` has committed runs, covering 18 of its 18 grid cells. The `gpt-5.4` and `gpt-5.5` arms are at 0 of 18: the first `gpt-5.4` cell failed on `external_api_insufficient_quota` and the remaining cells were not run. All headline results derive from the single `gpt-5.4-mini` generator by design. The three-model matrix described here and below is the planned suite rather than completed coverage, and a preflight reporting a model as `available` means it was reachable, not that its cells were evaluated.

A preflight checks model availability before expensive runs. If a model is unavailable to the executing account, the run records `model_unavailable` and never silently substitutes another model.

## Model Role

Models are used as structured-output strategy agents and sampled quality judges. The benchmark evaluates the agent system's behavior under uncertainty and oversight constraints; it does not claim model training, fine-tuning, or financial advice.

## Availability Preflight

Run:

```bash
python scripts/preflight_models.py
python scripts/preflight_models.py --live-response-check
```

The report is written to `outputs/model_preflight.json`. The plain preflight checks configured model availability. The live response check additionally makes one minimal Responses API call per configured model, so it catches authentication and quota failures before a long benchmark cell starts. Unavailable or quota-blocked models are recorded and excluded from aggregate publication claims unless explicitly replaced and disclosed.

The canonical publication suite is a planned `3 x 3 x 3 x 2` grid: three configured models, three seeds, oversight budgets `0/1/2`, and corruption off/on. The planned matrix and its per-cell status fields can be regenerated without API calls:

```bash
python scripts/run_publication_suite.py --dry-run
```

The committed `outputs/benchmark/publication_suite_manifest.json` is a live-run provenance record that carries the real preflight results, whereas `--dry-run` records the planned cells with a `not_checked` status in place of live availability.

## Known Limitations

- Model outputs may vary across backend updates even with fixed prompts and seeds.
- Structured outputs constrain schema shape without guaranteeing factual quality.
- API availability, latency, and model access can affect rerun completeness.
