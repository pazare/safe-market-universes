# Misspent oversight: whether a model can ration its own review budget

*Safe MarketUniverses: a model-intrinsic benchmark for whether an LLM's own uncertainty can spend a scarce human-review budget where it matters.*

## The problem: scarce human review

LLM agents are starting to make consequential recommendations under a hard constraint nobody can wish away: **human review is scarce.** You can't put a person behind every decision, so a deployed agent has to ration oversight, spending its limited budget of "stop and verify / escalate to a human" tokens on the decisions that actually need them.

I built **Safe MarketUniverses** to measure one precise version of that: *whether a model's own expressed uncertainty can allocate a finite review budget as well as it should.* The environment replays historical equity states, injects corrupted tool evidence (stale signals, contradictory risk summaries, missing fields, unverified rumors), and asks a committee of LLM agents to vote with stated confidence and verification needs.

## A measurement principle: score the model, not the scaffold

Here is the design decision that makes the benchmark trustworthy. It would be easy to report a headline like *"when evidence is corrupted, the system routes 77.5% of those steps to review, versus 10.8% on clean steps."* It looks like a strong safety signal, but in this setup it mostly measures the **harness**: the overseer escalates when it sees the corruption markers the harness itself injected. A number a benchmark can satisfy with a string match tells you little about the model.

So I built the metric the other way around, to isolate the model:

- From hindsight utilities the model never sees, define the **gain** of spending one review token on each step (positive only when deferring beats acting).
- An **oracle** spends its review budget on the top-gain steps, which is provably optimal under a cardinality budget.
- Score any allocator by **regret** against that oracle.

The headline allocator, **model-signal**, ranks steps using *only* the committee's own confidence, verification need, and disagreement, never the harness rules, never the hidden utilities. The corruption-routing number stays in the paper, but as a *harness diagnostic*, not the result. This is the [Agentic Benchmark Checklist](https://arxiv.org/abs/2507.02825) principle of construct validity applied directly: a benchmark should be solvable only by the capability it claims to measure.

## Results

![Oversight-allocation regret and corruption recall](figures/submission/oversight_allocation.png)

On 120 episodes / 480 steps, the model's own signal lands near random, and the benchmark cleanly separates a hand-coded baseline from it. Regret per step at a one-token review budget:

- **0.091**, a hand-coded evidence-integrity rule (a strong reference: a hand-coded heuristic that reacts to the visible corruption warnings and a reliability score, catching under half of the corrupted steps).
- **0.176**, the model's own uncertainty signal.
- **0.191**, random.

The decision-relevant finding: a model that is **comparatively well calibrated on average** (committee ECE **0.102**, versus 0.264 for the hand-coded heuristic) does **not, on its own, concentrate review on the steps that need it.** Good average calibration is not the same as knowing *where* a human should look. That distinction is exactly what a team must measure before triaging scarce human review with model confidence. The result is stable across three seeds, with a seed-to-seed range of 0.004.

## Scope of claims

This is **not** a trading strategy, alpha, financial advice, or a model leaderboard. The contribution is a **construct**: budgeted oversight allocation, measured as regret against an exact oracle, with the model cleanly separated from the harness.

I'm explicit about scope. Because these trajectories were generated under a rule-based overseer, the benchmark measures the *quality of the model's uncertainty as an allocation signal*, an offline question. The natural next experiment makes the model the **online** allocator: it sees a live, depleting budget and decides in real time. That extension is designed and ready; it's deferred here to keep the present measurement clean.

Code, paper, and one-command reproduction are in the repository: `python scripts/export_oversight_allocation.py` regenerates every number and the figure above from the logs.
