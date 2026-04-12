from __future__ import annotations

from typing import TypeVar

from openai import OpenAI
from pydantic import BaseModel

from .config import ensure_openai_api_key, get_openai_model

T = TypeVar("T", bound=BaseModel)


def call_structured_model(
    *,
    system_prompt: str,
    user_prompt: str,
    schema: type[T],
    model: str | None = None,
) -> T:
    """Call OpenAI with Structured Outputs and return a parsed Pydantic object."""
    ensure_openai_api_key()
    client = OpenAI()
    response = client.responses.parse(
        model=get_openai_model(model),
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        text_format=schema,
    )
    if response.output_parsed is None:
        raise RuntimeError(
            "The model returned no structured payload. "
            f"Raw output: {response.output_text}"
        )
    return response.output_parsed


def verify_openai_call(model: str | None = None) -> str:
    """Make a minimal real API call so setup can be verified before the full run."""
    ensure_openai_api_key()
    client = OpenAI()
    response = client.responses.create(
        model=get_openai_model(model),
        input="Reply with exactly these two words: setup verified",
    )
    return response.output_text.strip()

