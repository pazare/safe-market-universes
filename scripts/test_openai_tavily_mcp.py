from __future__ import annotations

if __package__ in {None, ""}:
    import sys
    from pathlib import Path

    sys.path.append(str(Path(__file__).resolve().parent.parent))

import argparse
import json
import os
import re

from openai import OpenAI

from src.config import ensure_openai_api_key, get_openai_model, get_openai_timeout_seconds, load_environment

ENV_VAR_NAME = "TAVILY_REMOTE_MCP_URL"
DEFAULT_TOOL_NAME = "tavily-search"


def _redact_url(url: str) -> str:
    from urllib.parse import urlsplit, urlunsplit

    parsed = urlsplit(url)
    if not parsed.scheme or not parsed.netloc:
        return "<redacted-url>"
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def _sanitize_text(text: str, *, tavily_url: str | None = None, openai_api_key: str | None = None) -> str:
    sanitized = text or "unknown_error"
    if tavily_url:
        sanitized = sanitized.replace(tavily_url, _redact_url(tavily_url))
    if openai_api_key:
        sanitized = sanitized.replace(openai_api_key, "OPENAI_API_KEY_REDACTED")
    sanitized = re.sub(r"(tavilyApiKey=)[^&\s]+", r"\1REDACTED", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"\bsk-[A-Za-z0-9_-]+\b", "OPENAI_API_KEY_REDACTED", sanitized)
    sanitized = " ".join(sanitized.split())
    return sanitized[:240]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a minimal OpenAI Responses API smoke test against the Tavily remote MCP server."
    )
    parser.add_argument("--model", help="Optional OpenAI model override.")
    return parser.parse_args()


def main() -> int:
    load_environment()
    args = parse_args()

    tavily_url = os.getenv(ENV_VAR_NAME, "").strip()
    if not tavily_url:
        print(f"FAIL openai_tavily_mcp missing_env {ENV_VAR_NAME}")
        return 1

    try:
        openai_api_key = ensure_openai_api_key()
    except Exception as exc:
        print(f"FAIL openai_tavily_mcp {_sanitize_text(str(exc))}")
        return 1

    model = get_openai_model(args.model)
    client = OpenAI(
        api_key=openai_api_key,
        timeout=min(30.0, get_openai_timeout_seconds()),
        max_retries=1,
    )

    try:
        response = client.responses.create(
            model=model,
            input=(
                "Use the Tavily MCP search tool exactly once to search for the exact phrase "
                "'Tavily MCP smoke test'. After the tool call finishes, reply with exactly: ok"
            ),
            tools=[
                {
                    "type": "mcp",
                    "server_label": "tavily",
                    "server_url": tavily_url,
                    "allowed_tools": [DEFAULT_TOOL_NAME],
                    "require_approval": "never",
                    "headers": {
                        "DEFAULT_PARAMETERS": json.dumps(
                            {
                                "max_results": 1,
                                "include_images": False,
                                "include_raw_content": False,
                                "include_favicon": False,
                            }
                        )
                    },
                }
            ],
            tool_choice={
                "type": "mcp",
                "server_label": "tavily",
                "name": DEFAULT_TOOL_NAME,
            },
            max_output_tokens=16,
            max_tool_calls=1,
            parallel_tool_calls=False,
            reasoning={"effort": "minimal"},
        )
        mcp_lists = [item for item in response.output if getattr(item, "type", "") == "mcp_list_tools"]
        mcp_calls = [item for item in response.output if getattr(item, "type", "") == "mcp_call"]
        if not mcp_lists:
            raise RuntimeError("missing mcp_list_tools output")
        if not mcp_calls:
            raise RuntimeError("missing mcp_call output")
        first_call = mcp_calls[0]
        if getattr(first_call, "error", None):
            raise RuntimeError(f"mcp_call_error {first_call.error}")
        if getattr(first_call, "name", "") != DEFAULT_TOOL_NAME:
            raise RuntimeError(f"unexpected_tool {getattr(first_call, 'name', 'unknown')}")
        final_text = response.output_text.strip()
        if final_text.lower() != "ok":
            raise RuntimeError(f"unexpected_final_text {final_text or '<empty>'}")
    except Exception as exc:
        print(
            "FAIL openai_tavily_mcp "
            f"{_sanitize_text(str(exc), tavily_url=tavily_url, openai_api_key=openai_api_key)}"
        )
        return 1

    print(
        "OK openai_tavily_mcp "
        f"model={model} "
        f"mcp_lists={len(mcp_lists)} "
        f"mcp_calls={len(mcp_calls)} "
        f"final={final_text.lower()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
