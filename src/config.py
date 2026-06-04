from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
PROMPTS_DIR = ROOT_DIR / "prompts"
OUTPUTS_DIR = ROOT_DIR / "outputs"
REPORT_DIR = ROOT_DIR / "report"
SCRIPTS_DIR = ROOT_DIR / "scripts"
CACHE_DIR = ROOT_DIR / ".cache"
OPENAI_CACHE_DIR = CACHE_DIR / "openai"
MARKET_DATA_CACHE_DIR = CACHE_DIR / "market_data"
REPORT_FIGURES_DIR = REPORT_DIR / "figures"
ENV_FILE = ROOT_DIR / ".env"
DEFAULT_MODEL = "gpt-5.4-mini"
DEFAULT_OPENAI_TIMEOUT_SECONDS = 60.0
DEFAULT_BENCHMARK_STEP_TIMEOUT_SECONDS = 300.0


def load_environment() -> None:
    """Load local environment variables once at process start."""
    load_dotenv(ENV_FILE, override=True)


def get_openai_model(explicit_model: str | None = None) -> str:
    return explicit_model or os.getenv("OPENAI_MODEL", DEFAULT_MODEL)


def openai_cache_enabled() -> bool:
    return os.getenv("OPENAI_CACHE_DISABLED", "").strip().lower() not in {"1", "true", "yes"}


def get_openai_timeout_seconds() -> float:
    raw_value = os.getenv("OPENAI_TIMEOUT_SECONDS", "").strip()
    if not raw_value:
        return DEFAULT_OPENAI_TIMEOUT_SECONDS
    try:
        return max(5.0, float(raw_value))
    except ValueError:
        return DEFAULT_OPENAI_TIMEOUT_SECONDS


def get_benchmark_step_timeout_seconds() -> float:
    raw_value = (
        os.getenv("SMU_STEP_TIMEOUT_SECONDS", "").strip()
        or os.getenv("BENCHMARK_STEP_TIMEOUT_SECONDS", "").strip()
    )
    if not raw_value:
        return DEFAULT_BENCHMARK_STEP_TIMEOUT_SECONDS
    try:
        return max(30.0, float(raw_value))
    except ValueError:
        return DEFAULT_BENCHMARK_STEP_TIMEOUT_SECONDS


def ensure_openai_api_key() -> str:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Copy .env.example to .env and add your key "
            "before running LLM-powered steps."
        )
    return api_key
