from __future__ import annotations

if __package__ in {None, ""}:
    import sys
    from pathlib import Path

    sys.path.append(str(Path(__file__).resolve().parent.parent))

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from src.config import load_environment

DEFAULT_PROTOCOL_VERSION = "2025-03-26"
DEFAULT_TIMEOUT_SECONDS = 20
ENV_VAR_NAME = "TAVILY_REMOTE_MCP_URL"


def _redact_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    if not parsed.scheme or not parsed.netloc:
        return "<redacted-url>"
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def _sanitize_text(text: str, *, url: str | None = None) -> str:
    sanitized = text or "unknown_error"
    if url:
        sanitized = sanitized.replace(url, _redact_url(url))
    sanitized = re.sub(r"(tavilyApiKey=)[^&\s]+", r"\1REDACTED", sanitized, flags=re.IGNORECASE)
    sanitized = " ".join(sanitized.split())
    return sanitized[:240]


def _sse_json_objects(payload: bytes) -> list[dict[str, Any]]:
    text = payload.decode("utf-8", errors="replace")
    events: list[str] = []
    current_data: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.rstrip("\r")
        if not line:
            if current_data:
                events.append("\n".join(current_data))
                current_data = []
            continue
        if line.startswith("data:"):
            current_data.append(line[5:].lstrip())
    if current_data:
        events.append("\n".join(current_data))

    parsed_objects: list[dict[str, Any]] = []
    for event_data in events:
        if not event_data.strip():
            continue
        try:
            parsed = json.loads(event_data)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            parsed_objects.append(parsed)
    return parsed_objects


@dataclass
class JsonRpcResponse:
    body: dict[str, Any] | None
    session_id: str | None


class StreamableHttpMcpClient:
    def __init__(self, *, server_url: str, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> None:
        self.server_url = server_url
        self.timeout_seconds = timeout_seconds
        self.protocol_version = DEFAULT_PROTOCOL_VERSION
        self.session_id: str | None = None
        self._next_id = 1

    def initialize(self) -> dict[str, Any]:
        request_id = self._next_request_id()
        response = self._post(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "initialize",
                "params": {
                    "protocolVersion": DEFAULT_PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {
                        "name": "trading-simulation-smoke-test",
                        "version": "1.0.0",
                    },
                },
            },
            include_protocol_header=False,
        )
        body = self._require_jsonrpc_success(response.body, request_id=request_id, method="initialize")
        result = body["result"]
        protocol_version = result.get("protocolVersion")
        if isinstance(protocol_version, str) and protocol_version:
            self.protocol_version = protocol_version
        if response.session_id:
            self.session_id = response.session_id
        self._notify_initialized()
        return result

    def list_tools(self) -> list[dict[str, Any]]:
        request_id = self._next_request_id()
        response = self._post(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "tools/list",
                "params": {},
            }
        )
        body = self._require_jsonrpc_success(response.body, request_id=request_id, method="tools/list")
        result = body["result"]
        tools = result.get("tools")
        if not isinstance(tools, list):
            raise RuntimeError("tools/list returned no tools array")
        parsed_tools: list[dict[str, Any]] = []
        for tool in tools:
            if isinstance(tool, dict):
                parsed_tools.append(tool)
        return parsed_tools

    def _notify_initialized(self) -> None:
        self._post(
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
            }
        )

    def _post(self, message: dict[str, Any], *, include_protocol_header: bool = True) -> JsonRpcResponse:
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        if include_protocol_header and self.protocol_version:
            headers["MCP-Protocol-Version"] = self.protocol_version
        if self.session_id:
            headers["MCP-Session-Id"] = self.session_id

        request = urllib.request.Request(
            self.server_url,
            data=json.dumps(message).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                content_type = response.headers.get_content_type()
                payload = response.read()
                session_id = response.headers.get("MCP-Session-Id") or response.headers.get("Mcp-Session-Id")
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"http_{exc.code} {_sanitize_text(error_body, url=self.server_url)}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"transport_error {_sanitize_text(str(exc.reason), url=self.server_url)}") from exc

        if not payload:
            return JsonRpcResponse(body=None, session_id=session_id)

        if content_type == "application/json":
            parsed = json.loads(payload.decode("utf-8"))
            if not isinstance(parsed, dict):
                raise RuntimeError("server returned non-object JSON-RPC payload")
            return JsonRpcResponse(body=parsed, session_id=session_id)

        if content_type == "text/event-stream":
            objects = _sse_json_objects(payload)
            for item in objects:
                if "result" in item or "error" in item:
                    return JsonRpcResponse(body=item, session_id=session_id)
            raise RuntimeError("server returned SSE without a JSON-RPC response")

        raise RuntimeError(f"unexpected_content_type {content_type}")

    def _next_request_id(self) -> int:
        request_id = self._next_id
        self._next_id += 1
        return request_id

    @staticmethod
    def _require_jsonrpc_success(
        body: dict[str, Any] | None,
        *,
        request_id: int,
        method: str,
    ) -> dict[str, Any]:
        if body is None:
            raise RuntimeError(f"{method} returned no JSON-RPC body")
        if body.get("id") != request_id:
            raise RuntimeError(f"{method} returned mismatched request id")
        error = body.get("error")
        if isinstance(error, dict):
            message = error.get("message") or "jsonrpc_error"
            raise RuntimeError(f"{method} {message}")
        result = body.get("result")
        if not isinstance(result, dict):
            raise RuntimeError(f"{method} returned no result object")
        return body


def main() -> int:
    load_environment()
    server_url = os.getenv(ENV_VAR_NAME, "").strip()
    if not server_url:
        print(f"FAIL tavily_mcp missing_env {ENV_VAR_NAME}")
        return 1

    try:
        client = StreamableHttpMcpClient(server_url=server_url)
        initialize_result = client.initialize()
        tools = client.list_tools()
        tool_names = [tool.get("name", "?") for tool in tools if isinstance(tool.get("name"), str)]
        server_info = initialize_result.get("serverInfo")
        server_name = server_info.get("name", "unknown") if isinstance(server_info, dict) else "unknown"
        if not tool_names:
            raise RuntimeError("no tools discovered")
    except Exception as exc:
        print(f"FAIL tavily_mcp {_sanitize_text(str(exc), url=server_url)}")
        return 1

    names_preview = ",".join(tool_names[:4])
    print(
        "OK tavily_mcp "
        f"protocol={client.protocol_version} "
        f"server={server_name} "
        f"tools={len(tool_names)} "
        f"names={names_preview}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
