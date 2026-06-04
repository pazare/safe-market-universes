from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.benchmark.artifact_validation import validate_artifact_contract


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a Safe MarketUniverses benchmark artifact folder.")
    parser.add_argument("run_dir", nargs="?", default="outputs/benchmark/smu_headline_v1")
    parser.add_argument("--output", help="Optional JSON report path.")
    args = parser.parse_args()

    report = validate_artifact_contract(args.run_dir)
    if args.output:
        Path(args.output).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
