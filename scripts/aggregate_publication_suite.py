from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.benchmark.suite_aggregation import aggregate_publication_suite, write_publication_suite_summary
from src.config import OUTPUTS_DIR


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate completed Safe MarketUniverses publication-suite runs.")
    parser.add_argument(
        "--manifest",
        default=str(OUTPUTS_DIR / "benchmark" / "publication_suite_manifest.json"),
        help="Publication suite manifest from scripts/run_publication_suite.py.",
    )
    parser.add_argument(
        "--outputs-root",
        default=str(OUTPUTS_DIR / "benchmark"),
        help="Directory containing per-run benchmark output folders.",
    )
    parser.add_argument(
        "--output",
        default=str(OUTPUTS_DIR / "benchmark" / "publication_suite_summary.json"),
        help="Where to write aggregate suite summary JSON.",
    )
    args = parser.parse_args()

    output_path = write_publication_suite_summary(args.manifest, args.outputs_root, args.output)
    payload = aggregate_publication_suite(args.manifest, args.outputs_root)
    print(f"Wrote publication suite summary to {output_path}")
    print(
        json.dumps(
            {
                key: payload[key]
                for key in [
                    "planned_run_count",
                    "completed_run_count",
                    "completion_rate",
                    "missing_run_ids",
                    "invalid_run_ids",
                    "failed_run_ids",
                    "invalid_run_reasons",
                ]
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
