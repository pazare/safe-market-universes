from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.benchmark.preliminary_results import write_preliminary_results


def main() -> None:
    parser = argparse.ArgumentParser(description="Export the preliminary-results snapshot from committed artifacts.")
    parser.add_argument("--headline-summary", default="outputs/benchmark/smu_headline_v1/summary.json")
    parser.add_argument("--suite-summary", default="outputs/benchmark/publication_suite_summary.json")
    parser.add_argument("--model-preflight", default="outputs/model_preflight.json")
    parser.add_argument("--output", default="report/preliminary_results.md")
    parser.add_argument("--json-output", default="report/preliminary_results.json")
    args = parser.parse_args()

    path = write_preliminary_results(
        output_path=args.output,
        json_output_path=args.json_output,
        headline_summary_path=args.headline_summary,
        suite_summary_path=args.suite_summary,
        model_preflight_path=args.model_preflight,
    )
    print(path)


if __name__ == "__main__":
    main()
