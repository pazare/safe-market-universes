from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any


RESULT_METRICS = [
    "selective_risk",
    "review_rate",
    "intervention_rate",
    "total_reward",
    "utility_per_intervention",
    "executed_expected_calibration_error",
    "non_hold_action_rate",
]


def _load_json(path: Path | str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def _sum_dicts(rows: list[dict[str, int | float]]) -> dict[str, int | float]:
    totals: dict[str, int | float] = {}
    for row in rows:
        for key, value in row.items():
            if isinstance(value, int):
                totals[key] = int(totals.get(key, 0)) + value
            elif isinstance(value, float):
                totals[key] = float(totals.get(key, 0.0)) + value
    return dict(sorted(totals.items()))


def _fmt(value: Any, *, percent: bool = False) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, int | float):
        if percent:
            return f"{value * 100:.1f}%"
        return f"{value:.4f}" if abs(value) < 10 else f"{value:.2f}"
    return str(value)


def _fmt_action_distribution(distribution: dict[str, int | float]) -> str:
    if not distribution:
        return "n/a"
    return ", ".join(f"{key}: {int(value)}" for key, value in sorted(distribution.items()))


def _pct_count(count: int, total: int) -> str:
    if total <= 0:
        return "n/a"
    return f"{count}/{total} ({count / total * 100:.1f}%)"


def _condition_label(budget: int, corruption_enabled: bool) -> str:
    evidence = "corrupted evidence" if corruption_enabled else "clean evidence"
    return f"Budget {budget}, {evidence}"


def _group_completed_runs(completed_runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[int, bool], list[dict[str, Any]]] = defaultdict(list)
    for run in completed_runs:
        groups[(int(run["budget"]), bool(run["corruption_enabled"]))].append(run)

    rows: list[dict[str, Any]] = []
    for (budget, corruption_enabled), run_rows in sorted(groups.items()):
        metrics_rows = [run["headline_metrics"] for run in run_rows]
        row = {
            "budget": budget,
            "corruption_enabled": corruption_enabled,
            "condition": _condition_label(budget, corruption_enabled),
            "n": len(metrics_rows),
        }
        for metric in RESULT_METRICS:
            values = [
                float(metrics[metric])
                for metrics in metrics_rows
                if isinstance(metrics.get(metric), int | float)
            ]
            row[metric] = _mean(values)
        reward_per_step_values = []
        for run in run_rows:
            metrics = run["headline_metrics"]
            reward = metrics.get("total_reward")
            step_count = run.get("step_count")
            if isinstance(reward, int | float) and isinstance(step_count, int | float) and step_count:
                reward_per_step_values.append(float(reward) / float(step_count))
        row["reward_per_step"] = _mean(reward_per_step_values)
        row["action_distribution"] = _sum_dicts(
            [
                metrics.get("action_distribution", {})
                for metrics in metrics_rows
                if isinstance(metrics.get("action_distribution"), dict)
            ]
        )
        rows.append(row)
    return rows


def _completed_model_note(suite: dict[str, Any]) -> str:
    by_model = suite.get("by_model") or {}
    completed_models = [
        f"{model} {counts.get('completed', 0)}/{counts.get('planned', 0)}"
        for model, counts in sorted(by_model.items())
        if counts.get("completed", 0)
    ]
    if not completed_models:
        return "No model cells are complete yet."
    missing_models = [
        f"{model} {counts.get('completed', 0)}/{counts.get('planned', 0)}"
        for model, counts in sorted(by_model.items())
        if not counts.get("completed", 0)
    ]
    if missing_models:
        return (
            "Completed model coverage: "
            + "; ".join(completed_models)
            + ". Pending model families: "
            + "; ".join(missing_models)
            + "."
        )
    return "Completed model coverage: " + "; ".join(completed_models) + "."


def build_preliminary_results(
    *,
    headline_summary_path: Path | str = "outputs/benchmark/smu_headline_v1/summary.json",
    suite_summary_path: Path | str = "outputs/benchmark/publication_suite_summary.json",
    model_preflight_path: Path | str = "outputs/model_preflight.json",
) -> dict[str, Any]:
    headline = _load_json(headline_summary_path)
    suite = _load_json(suite_summary_path)
    preflight = _load_json(model_preflight_path)
    headline_metrics = headline["headline_metrics"]
    human_audit = headline.get("human_audit_summary") or {}
    audit_completion = human_audit.get("completion", {})
    expected_audit = int(audit_completion.get("expected_count", 60) or 60)
    adjudicated_missing = int(audit_completion.get("adjudicated_missing_count", expected_audit) or 0)
    adjudicated_count = max(expected_audit - adjudicated_missing, 0)
    completed_runs = int(suite.get("completed_run_count", 0) or 0)
    planned_runs = int(suite.get("planned_run_count", 0) or 0)

    return {
        "status": "preliminary",
        "caveats": [
            f"{completed_runs}/{planned_runs} publication-suite runs are validated.",
            _completed_model_note(suite),
            f"Human audit adjudication is {adjudicated_count}/{expected_audit}.",
            f"Live model preflight statuses: {preflight_status_counts(preflight)}.",
        ],
        "headline": {
            "run_id": headline["run_id"],
            "episode_count": headline["episode_count"],
            "step_count": headline["step_count"],
            "executed_coverage": headline_metrics.get("executed_coverage"),
            "action_distribution": headline_metrics.get("action_distribution", {}),
            "non_hold_action_rate": headline_metrics.get("non_hold_action_rate"),
            "selective_risk": headline_metrics.get("selective_risk"),
            "always_act_risk": headline_metrics.get("always_act_risk"),
            "abstention_gain": headline_metrics.get("abstention_gain"),
            "review_rate": headline_metrics.get("review_rate"),
            "intervention_rate": headline_metrics.get("intervention_rate"),
            "majority_expected_calibration_error": headline_metrics.get("majority_expected_calibration_error"),
            "executed_expected_calibration_error": headline_metrics.get("executed_expected_calibration_error"),
            "worst_regime_error": headline_metrics.get("worst_regime_error"),
            "failure_counts": headline_metrics.get("failure_counts", {}),
        },
        "corruption_comparison": headline.get("corruption_comparison", []),
        "regime_table": headline.get("regime_table", []),
        "suite": {
            "planned_run_count": suite.get("planned_run_count", 0),
            "completed_run_count": suite.get("completed_run_count", 0),
            "failed_run_ids": suite.get("failed_run_ids", []),
            "missing_run_count": len(suite.get("missing_run_ids", [])),
            "invalid_run_reasons": suite.get("invalid_run_reasons", {}),
            "condition_table": _group_completed_runs(suite.get("completed_runs", [])),
        },
    }


def preflight_status_counts(preflight: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in preflight.get("results", []):
        status = str(row.get("status", "unknown"))
        counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items()))


def render_preliminary_results(report: dict[str, Any]) -> str:
    headline = report["headline"]
    suite = report["suite"]
    completed = int(suite["completed_run_count"])
    planned = int(suite["planned_run_count"])
    lines = [
        "# Safe MarketUniverses Preliminary Results",
        "",
        "Safe MarketUniverses is a safety benchmark for long-horizon financial recommendation agents. It tests whether an agent remains calibrated, interruptible, and reviewable when evidence is uncertain, corrupted, or expensive to audit. It is not a trading-alpha system and should not be read as financial advice.",
        "",
        f"Evidence status: `{_pct_count(completed, planned)}` publication-suite cells are validated, and the human audit is not complete. These results are therefore an artifact-readiness snapshot, not final paper claims or model rankings.",
        "",
        "## Current Evidence Base",
        "",
        f"- Canonical headline run: `{headline['run_id']}` with `{headline['episode_count']}` episodes and `{headline['step_count']}` decision steps.",
        f"- Publication suite: `{suite['completed_run_count']}/{suite['planned_run_count']}` validated runs.",
        f"- Failed resumable runs: `{len(suite['failed_run_ids'])}`.",
        f"- Not-started runs: `{suite['missing_run_count']}`.",
    ]
    for caveat in report["caveats"]:
        lines.append(f"- Caveat: {caveat}")

    lines.extend(
        [
            "",
            "## Metric Glossary",
            "",
            "- `Realized outcome`: the benchmark's hindsight label for what a good directional recommendation would have been at that step (`BUY`, `HOLD`, or `SELL`).",
            "- `Selective risk`: error rate on covered actions, meaning decisions the system actually executes after abstention and oversight.",
            "- `Always-act risk`: counterfactual error rate if the committee majority were always executed with no deferral.",
            "- `Abstention gain`: always-act risk minus selective risk; positive values mean deferral reduced covered-action error.",
            "- `Review rate`: share of steps routed for extra scrutiny, including cases where the budget may not be spent.",
            "- `Intervention rate`: share of steps where the overseer actually spends finite budget to verify or escalate.",
            "- `ECE`: expected calibration error, a binned gap between stated reliability and empirical correctness.",
            "- `Reward`: benchmark utility for safety behavior; in suite tables, reward is normalized per decision step so rows with different completed-run counts are comparable.",
            "",
            "## Headline Safety Signals",
            "",
            "| Signal | Value | Interpretation |",
            "| --- | ---: | --- |",
            f"| Action distribution | `{_fmt_action_distribution(headline['action_distribution'])}` | Executed recommendations and deferrals; this guards against misreading the benchmark as active trading volume. |",
            f"| Non-HOLD directional action rate | `{_fmt(headline['non_hold_action_rate'], percent=True)}` | Share of steps executing a direct BUY or SELL rather than HOLD/VERIFY/ESCALATE. |",
            f"| Selective risk | `{_fmt(headline['selective_risk'], percent=True)}` | Error rate on decisions the system actually executes. |",
            f"| Always-act risk | `{_fmt(headline['always_act_risk'], percent=True)}` | Counterfactual error rate if the system never deferred. |",
            f"| Abstention gain | `{_fmt(headline['abstention_gain'])}` | Risk reduction from abstention/deferral. |",
            f"| Review rate | `{_fmt(headline['review_rate'], percent=True)}` | Share of steps flagged for extra scrutiny. |",
            f"| Intervention rate | `{_fmt(headline['intervention_rate'], percent=True)}` | Share of steps where finite oversight budget was spent. |",
            f"| Majority-vote ECE | `{_fmt(headline['majority_expected_calibration_error'])}` | Calibration error before abstention/oversight. |",
            f"| Executed-action ECE | `{_fmt(headline['executed_expected_calibration_error'])}` | Calibration error after abstention/oversight. |",
            f"| Worst-regime error | `{_fmt(headline['worst_regime_error'], percent=True)}` | Hardest market-regime slice. |",
            "",
            "## Corruption Stress Test",
            "",
            "Corruption is a first-class benchmark condition: some observations contain stale, contradictory, or warning-bearing evidence. A good safety agent should not merely optimize correctness on clean inputs; it should route questionable evidence toward review.",
            "",
            "| Evidence slice | Steps | Majority error | Executed error | Review rate |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in report["corruption_comparison"]:
        lines.append(
            f"| {row['slice']} | `{row['steps']}` | `{_fmt(row['majority_error_rate'], percent=True)}` | `{_fmt(row['executed_error_rate'], percent=True)}` | `{_fmt(row['review_rate'], percent=True)}` |"
        )

    lines.extend(
        [
            "",
            "## Completed Publication-Suite Conditions",
            "",
            "Each row averages completed runs in that condition. Reward is reported both per decision step and per run; the per-step value is the fairer comparison while the suite is incomplete.",
            "",
            "| Condition | n | Selective risk | Review rate | Intervention rate | Mean reward/step | Mean total reward/run | Utility/intervention | Non-HOLD rate |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in suite["condition_table"]:
        lines.append(
            f"| {row['condition']} | `{row['n']}` | `{_fmt(row['selective_risk'], percent=True)}` | `{_fmt(row['review_rate'], percent=True)}` | `{_fmt(row['intervention_rate'], percent=True)}` | `{_fmt(row['reward_per_step'])}` | `{_fmt(row['total_reward'])}` | `{_fmt(row['utility_per_intervention'])}` | `{_fmt(row['non_hold_action_rate'], percent=True)}` |"
        )

    lines.extend(
        [
            "",
            "## Interpretable Failure Counts",
            "",
            "| Failure label | Count |",
            "| --- | ---: |",
        ]
    )
    for label, count in sorted(headline["failure_counts"].items()):
        lines.append(f"| `{label}` | `{count}` |")

    lines.extend(
        [
            "",
            "## Recruiter-Ready Interpretation",
            "",
            "Current artifacts show the benchmark is measuring the intended safety tradeoff: abstention and finite oversight modestly reduce covered-action error in the headline run, corrupted evidence triggers substantially higher review routing, and additional review budget creates measurable costs rather than automatic improvement. Because the publication suite and human audit are still incomplete, these are preliminary artifact-readiness results, not validated trading or model-ranking claims.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_preliminary_results(
    *,
    output_path: Path | str,
    json_output_path: Path | str | None = None,
    headline_summary_path: Path | str = "outputs/benchmark/smu_headline_v1/summary.json",
    suite_summary_path: Path | str = "outputs/benchmark/publication_suite_summary.json",
    model_preflight_path: Path | str = "outputs/model_preflight.json",
) -> Path:
    report = build_preliminary_results(
        headline_summary_path=headline_summary_path,
        suite_summary_path=suite_summary_path,
        model_preflight_path=model_preflight_path,
    )
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_preliminary_results(report), encoding="utf-8")
    if json_output_path is not None:
        json_output = Path(json_output_path)
        json_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return output
