from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.benchmark.report_consistency import check_report_consistency


def main() -> None:
    parser = argparse.ArgumentParser(description="Check report values against a benchmark summary.")
    parser.add_argument("report", nargs="?", default="README.md")
    parser.add_argument("run_dir", nargs="?", default="outputs/benchmark/smu_headline_v1")
    parser.add_argument("--suite-summary", default="outputs/benchmark/publication_suite_summary.json")
    parser.add_argument("--output", help="Optional JSON report path.")
    args = parser.parse_args()

    result = check_report_consistency(args.report, args.run_dir, suite_summary_path=args.suite_summary)
    if args.output:
        Path(args.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    if result["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
