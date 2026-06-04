from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.benchmark.model_registry import DEFAULT_PREFLIGHT_PATH, write_preflight_report
from src.config import load_environment


def main() -> None:
    load_environment()
    parser = argparse.ArgumentParser(description="Check configured benchmark model availability.")
    parser.add_argument("--config", help="Path to benchmark_models.json.")
    parser.add_argument(
        "--output",
        default=str(DEFAULT_PREFLIGHT_PATH),
        help="Where to write the preflight JSON report.",
    )
    parser.add_argument(
        "--live-response-check",
        action="store_true",
        help="Make one minimal Responses API call per configured model to catch quota/auth failures before a suite run.",
    )
    args = parser.parse_args()

    path = write_preflight_report(
        output_path=Path(args.output),
        registry_path=Path(args.config) if args.config else None,
        live_response_check=args.live_response_check,
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    print(f"Wrote model preflight report to {path}")
    for row in payload["results"]:
        print(f"- {row['model']} ({row['alias']}): {row['status']}")


if __name__ == "__main__":
    main()
