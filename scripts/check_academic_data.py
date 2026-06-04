from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.benchmark.academic_data import check_wrds_configuration
from src.config import OUTPUTS_DIR, load_environment


def main() -> None:
    load_environment()
    parser = argparse.ArgumentParser(description="Check optional academic market-data access.")
    parser.add_argument(
        "--output",
        default=str(OUTPUTS_DIR / "academic_data_status.json"),
        help="Path to write status JSON.",
    )
    args = parser.parse_args()

    status = check_wrds_configuration().as_dict()
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()
