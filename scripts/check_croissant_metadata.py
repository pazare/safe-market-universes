from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.benchmark.croissant_metadata import validate_croissant_metadata


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate required Croissant/RAI metadata fields.")
    parser.add_argument("path", nargs="?", default="metadata/smu_croissant.json")
    args = parser.parse_args()

    report = validate_croissant_metadata(args.path)
    print(json.dumps(report, indent=2))
    if report["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
