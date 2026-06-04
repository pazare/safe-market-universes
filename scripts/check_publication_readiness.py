from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.benchmark.publication_readiness import check_publication_readiness


def main() -> None:
    parser = argparse.ArgumentParser(description="Report publication readiness and remaining blockers.")
    parser.add_argument("--summary", default="outputs/benchmark/smu_headline_v1/summary.json")
    parser.add_argument("--suite-summary", default="outputs/benchmark/publication_suite_summary.json")
    parser.add_argument("--model-preflight", default="outputs/model_preflight.json")
    parser.add_argument(
        "--allow-pending",
        action="store_true",
        help="Exit 0 for pending external blockers. By default this is a strict publication gate.",
    )
    args = parser.parse_args()

    report = check_publication_readiness(
        summary_path=args.summary,
        suite_summary_path=args.suite_summary,
        model_preflight_path=args.model_preflight,
    )
    print(json.dumps(report, indent=2))
    if report["status"] == "engineering_blockers" or (report["status"] != "publication_ready" and not args.allow_pending):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
