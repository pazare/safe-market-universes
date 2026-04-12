from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
PROMPTS_DIR = ROOT_DIR / "prompts"
OUTPUTS_DIR = ROOT_DIR / "outputs"
REPORT_DIR = ROOT_DIR / "report"
ENV_FILE = ROOT_DIR / ".env"
DEFAULT_MODEL = "gpt-5.4-mini"


def load_environment() -> None:
    """Load local environment variables once at process start."""
    load_dotenv(ENV_FILE, override=True)


def get_openai_model(explicit_model: str | None = None) -> str:
    return explicit_model or os.getenv("OPENAI_MODEL", DEFAULT_MODEL)


def ensure_openai_api_key() -> str:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Copy .env.example to .env and add your key "
            "before running LLM-powered steps."
        )
    return api_key
