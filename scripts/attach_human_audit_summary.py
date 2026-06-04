from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.benchmark.human_audit import attach_human_audit_summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Attach a human audit summary to a benchmark summary.json.")
    parser.add_argument("run_dir", nargs="?", default="outputs/benchmark/smu_headline_v1")
    parser.add_argument("audit_dir", nargs="?", default="outputs/human_audit/smu_headline_v1")
    parser.add_argument("--expected-count", type=int, default=60)
    args = parser.parse_args()

    summary = attach_human_audit_summary(args.run_dir, args.audit_dir, expected_count=args.expected_count)
    print(json.dumps(summary["human_audit_summary"], indent=2))


if __name__ == "__main__":
    main()
