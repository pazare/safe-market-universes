from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openai import OpenAI

from ..config import OUTPUTS_DIR, ROOT_DIR, ensure_openai_api_key
from .artifact_paths import portable_path

DEFAULT_MODEL_REGISTRY_PATH = ROOT_DIR / "benchmark_models.json"
DEFAULT_PREFLIGHT_PATH = OUTPUTS_DIR / "model_preflight.json"


def load_model_registry(path: Path | str | None = None) -> dict[str, Any]:
    registry_path = Path(path) if path else DEFAULT_MODEL_REGISTRY_PATH
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    models = payload.get("default_models", [])
    if not isinstance(models, list) or len(models) != 3:
        raise ValueError("benchmark_models.json must define exactly three default_models.")
    seen: set[str] = set()
    for item in models:
        model = item.get("model")
        alias = item.get("alias")
        if not model or not alias:
            raise ValueError("Each default model must include alias and model fields.")
        if model in seen:
            raise ValueError(f"Duplicate model in benchmark_models.json: {model}")
        seen.add(model)
    return payload


def configured_model_names(path: Path | str | None = None) -> list[str]:
    registry = load_model_registry(path)
    return [item["model"] for item in registry["default_models"]]


def _classify_openai_exception(exc: Exception, *, default_status: str) -> str:
    message = str(exc)
    if "insufficient_quota" in message:
        return "insufficient_quota"
    return default_status


def _check_single_model(model: str, client: Any, *, live_response_check: bool = False) -> dict[str, Any]:
    try:
        client.models.retrieve(model)
    except Exception as exc:  # pragma: no cover - exact SDK exception varies
        return {
            "model": model,
            "status": _classify_openai_exception(exc, default_status="model_unavailable"),
            "available": False,
            "reason": f"{type(exc).__name__}: {exc}",
            "live_response_check": live_response_check,
        }
    if live_response_check:
        try:
            client.responses.create(
                model=model,
                input="Reply with exactly this token: smu_preflight_ok",
            )
        except Exception as exc:  # pragma: no cover - exact SDK exception varies
            return {
                "model": model,
                "status": _classify_openai_exception(exc, default_status="live_response_check_failed"),
                "available": False,
                "reason": f"{type(exc).__name__}: {exc}",
                "live_response_check": True,
            }
    return {
        "model": model,
        "status": "available",
        "available": True,
        "reason": None,
        "live_response_check": live_response_check,
    }


def preflight_models(
    *,
    registry_path: Path | str | None = None,
    client: Any | None = None,
    live_response_check: bool = False,
) -> dict[str, Any]:
    registry = load_model_registry(registry_path)
    try:
        ensure_openai_api_key()
    except RuntimeError as exc:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "registry_path": portable_path(Path(registry_path) if registry_path else DEFAULT_MODEL_REGISTRY_PATH),
            "policy": registry.get("policy", {}),
            "live_response_check": live_response_check,
            "results": [
                {
                    "alias": item["alias"],
                    "model": item["model"],
                    "role": item.get("role"),
                    "status": "not_checked",
                    "available": False,
                    "reason": str(exc),
                    "live_response_check": live_response_check,
                }
                for item in registry["default_models"]
            ],
        }

    openai_client = client or OpenAI()
    results = []
    for item in registry["default_models"]:
        result = _check_single_model(
            item["model"],
            openai_client,
            live_response_check=live_response_check,
        )
        result["alias"] = item["alias"]
        result["role"] = item.get("role")
        results.append(result)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "registry_path": portable_path(Path(registry_path) if registry_path else DEFAULT_MODEL_REGISTRY_PATH),
        "policy": registry.get("policy", {}),
        "live_response_check": live_response_check,
        "results": results,
    }


def write_preflight_report(
    *,
    output_path: Path | str | None = None,
    registry_path: Path | str | None = None,
    client: Any | None = None,
    live_response_check: bool = False,
) -> Path:
    path = Path(output_path) if output_path else DEFAULT_PREFLIGHT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = preflight_models(
        registry_path=registry_path,
        client=client,
        live_response_check=live_response_check,
    )
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path
