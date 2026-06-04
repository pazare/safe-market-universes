from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.benchmark.progress import build_publication_progress, render_publication_progress


def main() -> None:
    parser = argparse.ArgumentParser(description="Show Safe MarketUniverses publication progress.")
    parser.add_argument("--summary", default="outputs/benchmark/smu_headline_v1/summary.json")
    parser.add_argument("--suite-summary", default="outputs/benchmark/publication_suite_summary.json")
    parser.add_argument("--audit-summary", default="outputs/human_audit/smu_headline_v1/human_audit_summary.json")
    parser.add_argument("--model-preflight", default="outputs/model_preflight.json")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON instead of Markdown.")
    args = parser.parse_args()

    progress = build_publication_progress(
        summary_path=args.summary,
        suite_summary_path=args.suite_summary,
        audit_summary_path=args.audit_summary,
        model_preflight_path=args.model_preflight,
    )
    if args.json:
        print(json.dumps(progress, indent=2))
    else:
        print(render_publication_progress(progress))


if __name__ == "__main__":
    main()
