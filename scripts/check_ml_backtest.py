from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ml_artifact_validation import validate_ml_backtest_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate an ML backtest JSON artifact.")
    parser.add_argument(
        "artifact",
        nargs="?",
        type=Path,
        default=Path("outputs/ml_backtest.json"),
        help="Path to outputs/ml_backtest.json or another ML backtest artifact.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = validate_ml_backtest_file(args.artifact)
    print(json.dumps(report, indent=2))
    if report["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
