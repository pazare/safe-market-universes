from __future__ import annotations

import time

import pytest

from src.benchmark.runtime import StepTimeoutError, _wall_clock_timeout
from src.config import get_benchmark_step_timeout_seconds


def test_wall_clock_timeout_interrupts_stale_step() -> None:
    with pytest.raises(StepTimeoutError, match="unit-test step exceeded"):
        with _wall_clock_timeout(0.05, "unit-test step"):
            time.sleep(1)


def test_benchmark_step_timeout_env_floor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMU_STEP_TIMEOUT_SECONDS", "5")

    assert get_benchmark_step_timeout_seconds() == 30.0
