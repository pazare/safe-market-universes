from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

STATUS_VALUES = ["pass", "needs_review", "fail"]
SCORE_FIELDS = [
    "review_factual_grounding",
    "review_coherence",
    "review_calibration",
    "review_policy_compliance",
    "review_oversight_necessity",
]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _key(row: dict[str, str]) -> tuple[str, str]:
    return (row["episode_id"], row["step_index"])


def _agreement(a_rows: list[dict[str, str]], b_rows: list[dict[str, str]]) -> dict[str, float | int | None]:
    b_index = {_key(row): row for row in b_rows}
    compared = 0
    agreed = 0
    for a_row in a_rows:
        b_row = b_index.get(_key(a_row))
        if not b_row:
            continue
        a_status = a_row.get("final_reviewer_status", "").strip()
        b_status = b_row.get("final_reviewer_status", "").strip()
        if not a_status or not b_status:
            continue
        compared += 1
        agreed += int(a_status == b_status)
    return {
        "compared": compared,
        "agreed": agreed,
        "raw_agreement": round(agreed / compared, 4) if compared else None,
        "cohen_kappa": _cohen_kappa(a_rows, b_rows, "final_reviewer_status"),
    }


def _status_counts(rows: list[dict[str, str]], field: str) -> dict[str, int]:
    counter = Counter(row.get(field, "").strip() or "missing" for row in rows)
    return dict(sorted(counter.items()))


def _cohen_kappa(a_rows: list[dict[str, str]], b_rows: list[dict[str, str]], field: str) -> float | None:
    b_index = {_key(row): row for row in b_rows}
    pairs: list[tuple[str, str]] = []
    for a_row in a_rows:
        b_row = b_index.get(_key(a_row))
        if not b_row:
            continue
        a_value = a_row.get(field, "").strip()
        b_value = b_row.get(field, "").strip()
        if a_value and b_value:
            pairs.append((a_value, b_value))
    if not pairs:
        return None
    observed = sum(1 for a_value, b_value in pairs if a_value == b_value) / len(pairs)
    a_counts = Counter(a_value for a_value, _ in pairs)
    b_counts = Counter(b_value for _, b_value in pairs)
    categories = sorted(set(STATUS_VALUES) | set(a_counts) | set(b_counts))
    expected = sum((a_counts[category] / len(pairs)) * (b_counts[category] / len(pairs)) for category in categories)
    if expected == 1.0:
        return 1.0 if observed == 1.0 else 0.0
    return round((observed - expected) / (1.0 - expected), 4)


def _confusion_matrix(rows: list[dict[str, str]], *, predicted_field: str, actual_field: str) -> dict[str, dict[str, int]]:
    matrix: dict[str, Counter[str]] = {}
    for row in rows:
        predicted = row.get(predicted_field, "").strip()
        actual = row.get(actual_field, "").strip()
        if not predicted or not actual:
            continue
        matrix.setdefault(actual, Counter())[predicted] += 1
    return {
        actual: dict(sorted(counter.items()))
        for actual, counter in sorted(matrix.items())
    }


def _completion_report(
    reviewer_a: list[dict[str, str]],
    reviewer_b: list[dict[str, str]],
    adjudication: list[dict[str, str]],
    *,
    expected_count: int | None,
) -> dict[str, int | bool]:
    expected = expected_count or max(len(reviewer_a), len(reviewer_b), len(adjudication))
    reviewer_a_missing = sum(1 for row in reviewer_a if not row.get("final_reviewer_status", "").strip())
    reviewer_b_missing = sum(1 for row in reviewer_b if not row.get("final_reviewer_status", "").strip())
    adjudicated_missing = sum(1 for row in adjudication if not row.get("adjudicated_status", "").strip())
    reviewer_a_complete = len(reviewer_a) == expected and reviewer_a_missing == 0
    reviewer_b_complete = len(reviewer_b) == expected and reviewer_b_missing == 0
    adjudication_complete = len(adjudication) == expected and adjudicated_missing == 0
    return {
        "expected_count": expected,
        "reviewer_a_count": len(reviewer_a),
        "reviewer_b_count": len(reviewer_b),
        "adjudication_count": len(adjudication),
        "reviewer_a_missing_count": reviewer_a_missing,
        "reviewer_b_missing_count": reviewer_b_missing,
        "adjudicated_missing_count": adjudicated_missing,
        "reviewer_a_complete": reviewer_a_complete,
        "reviewer_b_complete": reviewer_b_complete,
        "adjudication_complete": adjudication_complete,
        "all_complete": reviewer_a_complete and reviewer_b_complete and adjudication_complete,
    }


def _model_human_comparison(rows: list[dict[str, str]]) -> dict[str, float | int | None | dict[str, dict[str, int]]]:
    compared = 0
    agreed = 0
    for row in rows:
        human = row.get("adjudicated_status", "").strip()
        model = row.get("automated_audit_status", "").strip()
        if not human or not model:
            continue
        compared += 1
        agreed += int(human == model)
    return {
        "compared": compared,
        "agreed": agreed,
        "raw_agreement": round(agreed / compared, 4) if compared else None,
        "confusion_matrix": _confusion_matrix(
            rows,
            predicted_field="automated_audit_status",
            actual_field="adjudicated_status",
        ),
    }


def summarize_audit_directory(audit_dir: Path | str, *, expected_count: int | None = None) -> dict:
    audit_path = Path(audit_dir)
    reviewer_a = _read_csv(audit_path / "reviewer_a.csv")
    reviewer_b = _read_csv(audit_path / "reviewer_b.csv")
    adjudication_path = audit_path / "adjudication.csv"
    adjudication = _read_csv(adjudication_path) if adjudication_path.exists() else []
    completion = _completion_report(
        reviewer_a,
        reviewer_b,
        adjudication,
        expected_count=expected_count,
    )
    model_vs_human = _model_human_comparison(adjudication) if adjudication else {}
    return {
        "audit_dir": str(audit_path),
        "reviewer_a_count": len(reviewer_a),
        "reviewer_b_count": len(reviewer_b),
        "adjudication_count": len(adjudication),
        "expected_count": completion["expected_count"],
        "completion": completion,
        "agreement": _agreement(reviewer_a, reviewer_b),
        "reviewer_a_status_counts": _status_counts(reviewer_a, "final_reviewer_status"),
        "reviewer_b_status_counts": _status_counts(reviewer_b, "final_reviewer_status"),
        "adjudicated_status_counts": _status_counts(adjudication, "adjudicated_status") if adjudication else {},
        "model_vs_human_ready": bool(completion["all_complete"] and model_vs_human.get("compared") == completion["expected_count"]),
        "model_vs_human_agreement": model_vs_human,
    }


def attach_human_audit_summary(
    run_dir: Path | str,
    audit_dir: Path | str,
    *,
    expected_count: int | None = None,
) -> dict:
    run_path = Path(run_dir)
    summary_path = run_path / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["human_audit_summary"] = summarize_audit_directory(audit_dir, expected_count=expected_count)
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
