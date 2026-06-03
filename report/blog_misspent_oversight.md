# I built a finance-agent safety benchmark, then caught it grading itself

*A short write-up of Safe MarketUniverses and one uncomfortable finding.*

## The setup

LLM agents are starting to make consequential recommendations — including in finance — under a hard constraint nobody can wish away: **human review is scarce.** You cannot put a person behind every decision. So a deployed agent has to ration oversight: spend its limited budget of "stop and verify / escalate to a human" tokens on the decisions that actually need them, and not waste them on the easy ones.

I built a benchmark, **Safe MarketUniverses**, to study that. It replays historical equity states, injects *corrupted* tool evidence (stale signals, contradictory risk summaries, missing fields, unverified rumors), asks a committee of LLM strategy agents to vote, and routes the decision through a finite-budget overseer. My original headline result looked great: when evidence was corrupted, the system sent **77.5%** of those steps to review, versus **10.8%** on clean steps. A big, clean safety signal.

## The bug that wasn't in the code

Then I read my own overseer. It escalates to a human when it finds the string `"unverified rumor"` in the tool feed — a string **my harness injects** as the corruption. So the headline "the agent routes corrupted evidence to review" was, to a large degree, *my harness detecting its own injection with `grep`.* The LLM under test barely participated in the number I was about to publish.

This is a textbook construct-validity failure — the kind the [Agentic Benchmark Checklist](https://arxiv.org/abs/2507.02825) warns about: a task that's "solvable" without the capability you claim to measure. My calibration metric had the same disease — it scored a hand-tuned reliability *formula I wrote*, not the model's own confidence. I was measuring my scaffolding and calling it a model evaluation.

The honest move wasn't to delete the work. It was to **isolate the model from the harness** and ask a sharper question.

## The fix: measure the model, not the scaffold

New flagship question: **can the model's *own* expressed uncertainty allocate a scarce review budget as well as an oracle?**

For each step I compute, from hindsight utilities the model never sees, the *gain* from spending one review token there — positive only when deferring beats acting on the (possibly corrupted) evidence. An **oracle** spends its budget *K* on the top-gain steps; that's provably optimal under a budget. Then I score allocators by **regret** against that oracle:

- **Model-signal** — rank steps by the committee's *own* stated confidence, verification need, and disagreement. (Never reads the overseer rules or the hidden utilities.)
- **Rule-baseline** — the old hand-coded overseer.
- **Random.**

The model only emits signals it produced for an independent purpose, and it's blind to the utilities the oracle uses — so the measurement is non-circular. It's now about the model.

## The uncomfortable result

![Oversight-allocation regret and corruption recall](figures/submission/oversight_allocation.png)

On 120 episodes / 480 steps:

- **The model's own uncertainty is a poor allocator.** Regret/step at K=1 is **0.176** (95% CI 0.153–0.199) — statistically indistinguishable from **random (0.191)**, and about **twice** the regret of the trivial hand-coded rule (**0.091**). It wastes ~half its tokens and misses **73%** of the review-worthy steps.
- **It under-detects exactly what the benchmark is about.** At the tightest budget, it catches review-worthy *corrupted* steps **less** often than clean ones (recall **22.8%** vs **28.2%**).
- **And yet its confidence is well calibrated.** Committee ECE is **0.102** — *better* than the hand-coded heuristic (0.264) I used to report. 

That last pair is the real finding: **good average calibration does not imply good allocation.** A model can be sensibly calibrated overall and still fail to concentrate its uncertainty on the specific decisions where a human should look. If you were planning to triage human review by thresholding model confidence, this is a caution.

(The hand-coded rule "wins," but only because it has privileged access — it string-matches the injected corruption. That's not intelligence; it's why the model-intrinsic comparison is the one worth reporting.)

The effect is stable across three seeds (regret range 0.004), so it isn't noise.

## What I'm claiming, and what I'm not

I am **not** claiming a trading strategy, alpha, financial advice, or a model leaderboard. The contribution is a **construct**: budgeted oversight allocation, measured as regret against an exact oracle, isolated from the harness, with an honest account of what offline logs can and can't show.

I'm also explicit about the limit: because these trajectories were generated under the old rule-based overseer, this measures the *quality of the model's uncertainty as an allocation signal* — an offline question. The natural next experiment makes the model the **online** allocator (it sees a live, depleting budget and decides in real time). That's designed and scoped; it's deferred only because it adds a prompt-design confound and costs live quota.

## Why I think this is the right kind of result

It would have been easy to ship the 77.5% number. Catching that it was my harness talking to itself — and rebuilding the measurement so the model is actually the thing under test — is the part I'd want a reviewer to see. Negative results that are *clean* are more useful than positive results that are *contaminated*.

Code, paper, and one-command reproduction: see the repository. `python scripts/export_oversight_allocation.py` regenerates every number and the figure above from the logs.
