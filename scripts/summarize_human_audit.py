from __future__ import annotations

import argparse
import json
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.benchmark.human_audit import summarize_audit_directory


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize two-reviewer and adjudicated human audit labels.")
    parser.add_argument(
        "audit_dir",
        nargs="?",
        default="outputs/human_audit/smu_headline_v1",
        help="Directory containing reviewer_a.csv, reviewer_b.csv, and optionally adjudication.csv.",
    )
    parser.add_argument("--expected-count", type=int, default=60)
    parser.add_argument("--output", help="Defaults to <audit_dir>/human_audit_summary.json.")
    args = parser.parse_args()

    audit_dir = Path(args.audit_dir)
    summary = summarize_audit_directory(audit_dir, expected_count=args.expected_count)
    output = Path(args.output) if args.output else audit_dir / "human_audit_summary.json"
    output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
