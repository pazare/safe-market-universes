from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = Path(__file__).resolve().parent


def _run(command: list[str], *, cwd: Path = REPO_ROOT) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def main() -> None:
    tectonic = shutil.which("tectonic")
    if tectonic is None:
        raise RuntimeError("Tectonic is required to build report/submission_paper.pdf")

    _run([sys.executable, "scripts/aggregate_publication_suite.py"])
    _run(
        [
            sys.executable,
            "scripts/export_preliminary_results.py",
            "--output",
            "report/preliminary_results.md",
            "--json-output",
            "report/preliminary_results.json",
        ]
    )
    _run([sys.executable, "scripts/export_oversight_allocation.py"])
    _run([sys.executable, "scripts/render_benchmark_figures.py", "outputs/benchmark/smu_headline_v1"])
    _run([sys.executable, "scripts/render_submission_figures.py"])
    _run([sys.executable, "scripts/export_submission_latex_assets.py"])
    _run([tectonic, "submission_paper.tex"], cwd=REPORT_DIR)
    print(f"Wrote {REPORT_DIR / 'submission_paper.pdf'}")


if __name__ == "__main__":
    main()
