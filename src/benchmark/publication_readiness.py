from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _load_json(path: Path | str) -> dict[str, Any] | None:
    p = Path(path)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def _check(status: str, check_id: str, detail: str) -> dict[str, str]:
    return {"id": check_id, "status": status, "detail": detail}


def check_publication_readiness(
    *,
    summary_path: Path | str = "outputs/benchmark/smu_headline_v1/summary.json",
    suite_summary_path: Path | str = "outputs/benchmark/publication_suite_summary.json",
    model_preflight_path: Path | str = "outputs/model_preflight.json",
) -> dict[str, Any]:
    checks: list[dict[str, str]] = []
    summary = _load_json(summary_path)
    suite = _load_json(suite_summary_path)
    preflight = _load_json(model_preflight_path)

    if summary is None:
        checks.append(_check("fail", "canonical_summary_present", f"Missing {summary_path}"))
    else:
        checks.append(_check("pass", "canonical_summary_present", f"Found {summary_path}"))
        artifact_status = summary.get("artifact_validation", {}).get("status")
        checks.append(
            _check(
                "pass" if artifact_status == "pass" else "fail",
                "artifact_contract",
                f"artifact_validation.status={artifact_status}",
            )
        )
        audit = summary.get("human_audit_summary") or {}
        audit_ready = bool(
            audit.get("model_vs_human_ready")
            and audit.get("completion", {}).get("all_complete")
        )
        completion = audit.get("completion", {})
        expected = completion.get("expected_count", 60)
        adjudicated_complete = expected - completion.get("adjudicated_missing_count", expected)
        checks.append(
            _check(
                "pass" if audit_ready else "pending",
                "human_audit_complete",
                (
                    f"adjudicated human labels are attached for {expected}/{expected} rows"
                    if audit_ready
                    else f"human audit awaits complete reviewer/adjudicator labels ({adjudicated_complete}/{expected} adjudicated labels complete)"
                ),
            )
        )

    if suite is None:
        checks.append(_check("pending", "publication_suite_complete", f"Missing {suite_summary_path}"))
    else:
        completed = suite.get("completed_run_count", 0)
        planned = suite.get("planned_run_count", 0)
        invalid_count = len(suite.get("invalid_run_ids", []))
        failed_count = len(suite.get("failed_run_ids", []))
        other_invalid_count = max(invalid_count - failed_count, 0)
        missing_count = len(suite.get("missing_run_ids", []))
        complete = completed == planned and planned > 0
        checks.append(
            _check(
                "pass" if complete else "pending",
                "publication_suite_complete",
                (
                    f"{completed}/{planned} planned runs complete"
                    if complete
                    else (
                        f"{completed}/{planned} planned runs complete; "
                        f"{failed_count} failed, {other_invalid_count} other invalid, "
                        f"{missing_count} not started"
                    )
                ),
            )
        )

    if preflight is None:
        checks.append(_check("pending", "model_preflight", f"Missing {model_preflight_path}"))
    else:
        results = preflight.get("results", [])
        status_counts: dict[str, int] = {}
        for row in results:
            status = str(row.get("status", "unknown"))
            status_counts[status] = status_counts.get(status, 0) + 1
        unavailable = {status: count for status, count in status_counts.items() if status != "available"}
        checks.append(
            _check(
                "pass" if results and not unavailable else "pending",
                "model_preflight",
                (
                    f"all {len(results)} configured models passed live preflight"
                    if results and not unavailable
                    else f"model preflight has unavailable models: {unavailable or {'unknown': 0}}"
                ),
            )
        )

    if any(item["status"] == "fail" for item in checks):
        status = "engineering_blockers"
    elif any(item["status"] == "pending" for item in checks):
        status = "external_blockers"
    else:
        status = "publication_ready"

    return {
        "status": status,
        "checks": checks,
    }
