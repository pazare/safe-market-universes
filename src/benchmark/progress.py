from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .publication_readiness import check_publication_readiness


def _load_json(path: Path | str) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _suite_progress(suite: dict[str, Any]) -> dict[str, Any]:
    planned = int(suite.get("planned_run_count", 0))
    completed = int(suite.get("completed_run_count", 0))
    failed = len(suite.get("failed_run_ids", []))
    invalid = len(suite.get("invalid_run_ids", []))
    not_started = len(suite.get("missing_run_ids", []))
    return {
        "planned": planned,
        "completed": completed,
        "failed": failed,
        "other_invalid": max(invalid - failed, 0),
        "not_started": not_started,
        "completion_rate": round(completed / planned, 4) if planned else 0.0,
        "completion_label": f"{completed}/{planned}",
        "failed_run_ids": suite.get("failed_run_ids", []),
        "invalid_run_reasons": suite.get("invalid_run_reasons", {}),
    }


def _audit_progress(audit: dict[str, Any]) -> dict[str, Any]:
    completion = audit.get("completion", {})
    expected = int(completion.get("expected_count", audit.get("expected_count", 0)) or 0)
    reviewer_a_missing = int(completion.get("reviewer_a_missing_count", expected) or 0)
    reviewer_b_missing = int(completion.get("reviewer_b_missing_count", expected) or 0)
    adjudicated_missing = int(completion.get("adjudicated_missing_count", expected) or 0)
    return {
        "expected": expected,
        "reviewer_a_completed": max(expected - reviewer_a_missing, 0),
        "reviewer_b_completed": max(expected - reviewer_b_missing, 0),
        "adjudicated_completed": max(expected - adjudicated_missing, 0),
        "all_complete": bool(completion.get("all_complete")),
        "model_vs_human_ready": bool(audit.get("model_vs_human_ready")),
    }


def _preflight_progress(preflight: dict[str, Any]) -> dict[str, Any]:
    results = preflight.get("results", [])
    status_counts = dict(sorted(Counter(row.get("status", "unknown") for row in results).items()))
    return {
        "live_response_check": bool(preflight.get("live_response_check")),
        "status_counts": status_counts,
        "quota_blocked": any(row.get("status") == "insufficient_quota" for row in results),
        "unavailable_models": [
            {
                "model": row.get("model"),
                "status": row.get("status"),
                "reason": row.get("reason"),
            }
            for row in results
            if row.get("status") != "available"
        ],
    }


def _next_actions(
    *,
    suite: dict[str, Any],
    human_audit: dict[str, Any],
    model_preflight: dict[str, Any],
) -> list[str]:
    actions: list[str] = []
    if model_preflight["quota_blocked"] or any(
        "insufficient_quota" in reason
        for reason in suite.get("invalid_run_reasons", {}).values()
    ):
        actions.append("Restore OpenAI quota or billing, then resume failed publication-suite cells.")
    if not human_audit["all_complete"]:
        actions.append("Complete reviewer_a.csv, reviewer_b.csv, and adjudication.csv for the 60-row human audit.")
    if suite["completed"] < suite["planned"]:
        actions.append("Resume the remaining publication suite with --resume once live preflight passes.")
    if not actions:
        actions.append("Run final paper/report checks and prepare the artifact release.")
    return actions


def build_publication_progress(
    *,
    summary_path: Path | str = "outputs/benchmark/smu_headline_v1/summary.json",
    suite_summary_path: Path | str = "outputs/benchmark/publication_suite_summary.json",
    audit_summary_path: Path | str = "outputs/human_audit/smu_headline_v1/human_audit_summary.json",
    model_preflight_path: Path | str = "outputs/model_preflight.json",
) -> dict[str, Any]:
    suite = _suite_progress(_load_json(suite_summary_path))
    human_audit = _audit_progress(_load_json(audit_summary_path))
    model_preflight = _preflight_progress(_load_json(model_preflight_path))
    readiness = check_publication_readiness(
        summary_path=summary_path,
        suite_summary_path=suite_summary_path,
        model_preflight_path=model_preflight_path,
    )
    return {
        "overall_status": readiness["status"],
        "readiness_checks": readiness["checks"],
        "suite": suite,
        "human_audit": human_audit,
        "model_preflight": model_preflight,
        "next_actions": _next_actions(
            suite=suite,
            human_audit=human_audit,
            model_preflight=model_preflight,
        ),
    }


def render_publication_progress(progress: dict[str, Any]) -> str:
    suite = progress["suite"]
    audit = progress["human_audit"]
    preflight = progress["model_preflight"]
    lines = [
        "# Safe MarketUniverses Publication Progress",
        "",
        f"- Overall status: `{progress['overall_status']}`",
        (
            "- Suite: "
            f"`{suite['completion_label']}` complete, "
            f"`{suite['failed']}` failed, "
            f"`{suite['other_invalid']}` other invalid, "
            f"`{suite['not_started']}` not started"
        ),
        (
            "- Human audit: "
            f"reviewer A `{audit['reviewer_a_completed']}/{audit['expected']}`, "
            f"reviewer B `{audit['reviewer_b_completed']}/{audit['expected']}`, "
            f"adjudicated `{audit['adjudicated_completed']}/{audit['expected']}`"
        ),
        f"- Model preflight: `{preflight['status_counts']}`",
    ]
    if suite["failed_run_ids"]:
        shown = suite["failed_run_ids"][:3]
        suffix = "" if len(suite["failed_run_ids"]) <= 3 else f" (+{len(suite['failed_run_ids']) - 3} more)"
        lines.append("- Failed runs: " + ", ".join(f"`{run_id}`" for run_id in shown) + suffix)
    lines.extend(["", "## Next Actions"])
    lines.extend(f"{index}. {action}" for index, action in enumerate(progress["next_actions"], start=1))
    return "\n".join(lines)
