"""
Redaction helpers for recorded events, network metadata, and AI payloads.
"""

import re
from copy import deepcopy
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

SENSITIVE_KEYS = {
    "access_token",
    "api_key",
    "authorization",
    "cookie",
    "id_token",
    "password",
    "refresh_token",
    "secret",
    "set-cookie",
    "token",
}

SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]+", re.IGNORECASE),
    re.compile(r"(?i)(password|token|secret|api[_-]?key)=([^&\s]+)"),
]


def redact_text(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    redacted = value
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub(lambda m: f"{m.group(1)}=[REDACTED]" if m.groups() else "[REDACTED]", redacted)
    return redacted


def redact_url(url: Any) -> Any:
    if not isinstance(url, str) or "?" not in url:
        return redact_text(url)
    try:
        parts = urlsplit(url)
        query = []
        for key, value in parse_qsl(parts.query, keep_blank_values=True):
            if _is_sensitive_key(key):
                query.append((key, "[REDACTED]"))
            else:
                query.append((key, redact_text(value)))
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
    except Exception:
        return redact_text(url)


def redact_data(value: Any) -> Any:
    if isinstance(value, dict):
        clean = {}
        for key, item in value.items():
            if _is_sensitive_key(str(key)):
                clean[key] = "[REDACTED]"
            elif str(key).lower() == "url":
                clean[key] = redact_url(item)
            else:
                clean[key] = redact_data(item)
        return clean
    if isinstance(value, list):
        return [redact_data(item) for item in value]
    return redact_text(value)


def redact_dom_snapshot(snapshot: Any) -> Any:
    if not isinstance(snapshot, str):
        return snapshot
    snapshot = re.sub(
        r'(<input[^>]+type=["\']?password["\']?[^>]*value=["\'])([^"\']*)(["\'])',
        r"\1[REDACTED]\3",
        snapshot,
        flags=re.IGNORECASE,
    )
    return redact_text(snapshot)


def redact_event_payload(event: Any) -> dict:
    data = event.model_dump() if hasattr(event, "model_dump") else deepcopy(dict(event))
    data["url"] = redact_url(data.get("url"))
    data["value"] = redact_text(data.get("value"))
    data["dom_snapshot"] = redact_dom_snapshot(data.get("dom_snapshot"))
    data["network_data"] = redact_data(data.get("network_data"))
    data["meta"] = redact_data(data.get("meta"))
    return data


def _is_sensitive_key(key: str) -> bool:
    normalised = key.strip().lower().replace("-", "_")
    return any(token in normalised for token in SENSITIVE_KEYS)
