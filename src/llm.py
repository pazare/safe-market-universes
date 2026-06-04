from __future__ import annotations

import hashlib
import json
from typing import TypeVar

from openai import OpenAI
from pydantic import BaseModel

from .config import (
    OPENAI_CACHE_DIR,
    ensure_openai_api_key,
    get_openai_model,
    get_openai_timeout_seconds,
    openai_cache_enabled,
)

T = TypeVar("T", bound=BaseModel)
_CLIENT: OpenAI | None = None


def _get_client() -> OpenAI:
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = OpenAI(timeout=get_openai_timeout_seconds(), max_retries=2)
    return _CLIENT


def _cache_key(*, model: str, system_prompt: str, user_prompt: str, schema: type[BaseModel]) -> str:
    payload = {
        "version": "structured-v1",
        "model": model,
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "schema_name": schema.__name__,
        "schema_json": schema.model_json_schema(),
    }
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _cache_path(key: str) -> str:
    OPENAI_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return str(OPENAI_CACHE_DIR / f"{key}.json")


def call_structured_model(
    *,
    system_prompt: str,
    user_prompt: str,
    schema: type[T],
    model: str | None = None,
) -> T:
    """Call OpenAI with Structured Outputs and return a parsed Pydantic object."""
    ensure_openai_api_key()
    resolved_model = get_openai_model(model)
    cache_key = _cache_key(
        model=resolved_model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        schema=schema,
    )
    cache_file = _cache_path(cache_key)

    if openai_cache_enabled():
        from pathlib import Path

        path = Path(cache_file)
        if path.exists():
            cached_payload = json.loads(path.read_text(encoding="utf-8"))
            return schema.model_validate(cached_payload)

    client = _get_client()
    response = client.responses.parse(
        model=resolved_model,
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
    if openai_cache_enabled():
        from pathlib import Path

        Path(cache_file).write_text(
            json.dumps(response.output_parsed.model_dump(), indent=2),
            encoding="utf-8",
        )
    return response.output_parsed


def verify_openai_call(model: str | None = None) -> str:
    """Make a minimal real API call so setup can be verified before the full run."""
    ensure_openai_api_key()
    client = _get_client()
    response = client.responses.create(
        model=get_openai_model(model),
        input="Reply with exactly these two words: setup verified",
    )
    return response.output_text.strip()
