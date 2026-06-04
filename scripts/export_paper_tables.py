from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.benchmark.paper_tables import export_paper_tables


def main() -> None:
    parser = argparse.ArgumentParser(description="Export paper-ready markdown tables from summary.json.")
    parser.add_argument("run_dir", nargs="?", default="outputs/benchmark/smu_headline_v1")
    parser.add_argument("--output", default="report/tables")
    args = parser.parse_args()

    for path in export_paper_tables(args.run_dir, args.output):
        print(path)


if __name__ == "__main__":
    main()
