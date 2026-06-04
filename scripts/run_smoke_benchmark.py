from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    test_path = Path("tests/test_runtime_progress.py")
    raise_code = pytest.main([str(test_path), "-q"])
    if raise_code:
        raise SystemExit(raise_code)
    print("Mocked Safe MarketUniverses smoke benchmark passed.")


if __name__ == "__main__":
    main()
