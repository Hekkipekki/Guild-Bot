from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any


_REDACTED_KEYS = {
    "access_token",
    "authorization",
    "client_secret",
    "password",
    "refresh_token",
    "secret",
    "token",
}


def build_debug_payload(
    *,
    operation: str,
    request: dict[str, Any],
    response: Any,
) -> dict[str, Any]:
    """Build a serializable, redacted snapshot for development diagnostics."""
    return {
        "operation": str(operation),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "request": _sanitize(request),
        "response": _sanitize(response),
    }


def build_debug_json_bytes(
    *,
    operation: str,
    request: dict[str, Any],
    response: Any,
) -> bytes:
    payload = build_debug_payload(
        operation=operation,
        request=request,
        response=response,
    )
    return json.dumps(
        payload,
        indent=2,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    ).encode("utf-8")


def _sanitize(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        value = asdict(value)

    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, child in value.items():
            clean_key = str(key)
            if clean_key.lower() in _REDACTED_KEYS:
                sanitized[clean_key] = "[REDACTED]"
            else:
                sanitized[clean_key] = _sanitize(child)
        return sanitized

    if isinstance(value, (list, tuple, set, frozenset)):
        return [_sanitize(child) for child in value]

    if isinstance(value, bytes):
        return f"<bytes:{len(value)}>"

    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    return str(value)
