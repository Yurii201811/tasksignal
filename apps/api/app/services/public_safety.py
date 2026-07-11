"""Fail-closed sanitizers for content that may leave trusted local storage."""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import parse_qsl, unquote, urlencode, urlparse

from app.services.ingestion.normalization import safe_source_url

_IDENTITY_SECRET_PATTERNS = (
    re.compile(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
        re.DOTALL,
    ),
    re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/=-]{12,}"),
    re.compile(r"(?i)\b(?:sk|gh[pousr]|xox[baprs])[-_][a-z0-9_-]{12,}"),
    re.compile(r"(?i)\beyJ[a-z0-9_-]{8,}\.[a-z0-9_-]{8,}\.[a-z0-9_-]{8,}\b"),
    re.compile(
        r"(?i)[\"'`]?\b(?:[a-z0-9]+[_.-])*?(?:access[_ .-]?token|api[_ .-]?key|"
        r"client[_ .-]?secret|secret[_ .-]?access[_ .-]?key|credential|password|"
        r"private[_ .-]?key|secret|signature|token|jwt|session[_ .-]?id)"
        r"[\"'`]?\s*[:=]\s*(?:\"[^\"\r\n]*\"|'[^'\r\n]*'|`[^`\r\n]*`|"
        r"[^\s,;}\"'`]+)"
    ),
    re.compile(r"(?i)\bauthorization\s*[:=]\s*[^\r\n]+"),
    re.compile(r"(?i)\bcookie\s*:\s*[^\r\n]+"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"),
    re.compile(r"(?<!\w)\+\d[\d ()-]{7,}\d(?!\w)"),
    re.compile(r"(?<!\d)\d{10,15}(?!\d)"),
)
_URL_IN_TEXT_PATTERN = re.compile(r"(?i)https?://[^\s<>()\]]+")
_SENSITIVE_TEXT_PATTERNS = (*_IDENTITY_SECRET_PATTERNS, _URL_IN_TEXT_PATTERN)
_MAX_PUBLIC_URL_LENGTH = 4096
_MAX_PERCENT_DECODE_PASSES = 8


def redact_public_text(value: str) -> str:
    """Remove secret-shaped values, raw identities, and embedded URLs."""

    redacted = value
    for pattern in _SENSITIVE_TEXT_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def _decoded_for_inspection(candidate: str) -> str | None:
    decoded = candidate
    for _ in range(_MAX_PERCENT_DECODE_PASSES):
        next_value = unquote(decoded)
        if next_value == decoded:
            return decoded
        decoded = next_value
    # Deeply nested encoding is unusual for public provenance and unsafe to expose.
    return decoded if unquote(decoded) == decoded else None


def safe_public_source_url(value: object) -> str:
    """Return a bounded public evidence URL without identity/credential data."""

    candidate = safe_source_url(value, fallback="")
    if not candidate or len(candidate) > _MAX_PUBLIC_URL_LENGTH:
        return ""
    decoded = _decoded_for_inspection(candidate)
    if decoded is None or any(ord(character) < 32 or ord(character) == 127 for character in decoded):
        return ""
    if any(pattern.search(decoded) for pattern in _IDENTITY_SECRET_PATTERNS):
        return ""
    parsed = urlparse(candidate)
    if parsed.fragment:
        return ""
    if parsed.query:
        pairs = parse_qsl(parsed.query, keep_blank_values=True)
        if not pairs or any(
            re.sub(r"[^a-z0-9]", "", key.casefold()) != "id"
            or not entry.isdecimal()
            or len(entry) > 32
            for key, entry in pairs
        ):
            return ""
        candidate = parsed._replace(query=urlencode(pairs), fragment="").geturl()
        parsed = urlparse(candidate)
    host = (parsed.hostname or "").rstrip(".").casefold()
    if host in {"localhost", "localhost.localdomain"} or host.endswith(
        (".localhost", ".local", ".internal")
    ):
        return ""
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return candidate
    return candidate if address.is_global else ""
