from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.all_models import DiscourseSourceState, Source, now_utc
from app.services.ingestion.connectors import sanitize_error_message

FAILURE_CODES = frozenset(
    {
        "timeout",
        "connection",
        "dns_rejected",
        "redirect_rejected",
        "http_error",
        "rate_limited",
        "response_too_large",
        "invalid_response",
    }
)
MAX_RETRY_AFTER = timedelta(days=7)
_HOST_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")
_NONSTANDARD_NUMERIC_HOST = re.compile(r"(?:0[xX][0-9a-fA-F]+|[0-9.]+)\Z")


class DiscourseSourceError(ValueError):
    pass


class InvalidDiscourseOrigin(DiscourseSourceError):
    pass


class InvalidDiscourseSource(DiscourseSourceError):
    pass


class TermsConfirmationRequired(DiscourseSourceError):
    pass


class ImmutableDiscourseOrigin(DiscourseSourceError):
    pass


@dataclass(frozen=True)
class CanonicalDiscourseOrigin:
    scheme: str
    host: str
    port: int

    @property
    def origin(self) -> str:
        suffix = "" if self.port == 443 else f":{self.port}"
        return f"https://{self.host}{suffix}"


@dataclass(frozen=True)
class DiscourseReadiness:
    status: str
    can_run: bool


@dataclass(frozen=True)
class DiscourseRuntimeStateSnapshot:
    source_id: UUID
    origin: str | None
    readiness: str
    can_run: bool
    last_success_at: datetime | None
    last_failure_at: datetime | None
    last_failure_code: str | None
    last_failure_message: str | None
    last_http_status: int | None
    retry_after_at: datetime | None


def _utc(value: datetime | None = None) -> datetime:
    result = value or now_utc()
    if result.tzinfo is None:
        return result.replace(tzinfo=UTC)
    return result.astimezone(UTC)


def _optional_utc(value: datetime | None) -> datetime | None:
    return _utc(value) if value is not None else None


def canonicalize_discourse_origin(value: str) -> CanonicalDiscourseOrigin:
    if not isinstance(value, str) or not value.strip():
        raise InvalidDiscourseOrigin("A public HTTPS origin is required.")
    if any(character in value for character in "\x00\r\n\t"):
        raise InvalidDiscourseOrigin("Origin must not contain control characters.")

    candidate = value.strip()
    try:
        parsed = urlsplit(candidate)
        port = parsed.port
    except ValueError as exc:
        raise InvalidDiscourseOrigin("Origin has an invalid host or port.") from exc

    if parsed.scheme.lower() != "https":
        raise InvalidDiscourseOrigin("Discourse origins must use HTTPS.")
    if parsed.username is not None or parsed.password is not None:
        raise InvalidDiscourseOrigin("Origin credentials are not allowed.")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise InvalidDiscourseOrigin("Origin must not include a path, query, or fragment.")
    if not parsed.hostname:
        raise InvalidDiscourseOrigin("Origin host is required.")

    host_value = parsed.hostname.rstrip(".")
    if not host_value:
        raise InvalidDiscourseOrigin("Origin host is required.")
    try:
        ipaddress.ip_address(host_value)
    except ValueError:
        pass
    else:
        raise InvalidDiscourseOrigin("IP-literal origins are not allowed.")
    if _NONSTANDARD_NUMERIC_HOST.fullmatch(host_value):
        raise InvalidDiscourseOrigin("Numeric IP-literal origins are not allowed.")
    if host_value.casefold() == "localhost" or host_value.casefold().endswith(".localhost"):
        raise InvalidDiscourseOrigin("Localhost origins are not allowed.")

    try:
        host = host_value.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise InvalidDiscourseOrigin("Origin host is not valid IDNA.") from exc
    if len(host) > 253 or any(not _HOST_LABEL.fullmatch(label) for label in host.split(".")):
        raise InvalidDiscourseOrigin("Origin host is not a valid public hostname.")

    canonical_port = 443 if port is None else port
    if canonical_port < 1 or canonical_port > 65535:
        raise InvalidDiscourseOrigin("Origin port is outside the valid range.")
    return CanonicalDiscourseOrigin(scheme="https", host=host, port=canonical_port)


def authorize_discourse_source(
    db: Session,
    *,
    source: Source,
    origin: str,
    terms_confirmed: bool,
    now: datetime | None = None,
) -> DiscourseSourceState:
    if source.type.strip().lower() != "discourse" or source.id is None:
        raise InvalidDiscourseSource("Only persisted Discourse sources can be authorized.")
    if terms_confirmed is not True:
        raise TermsConfirmationRequired("Discourse terms must be explicitly confirmed.")

    canonical = canonicalize_discourse_origin(origin)
    timestamp = _utc(now)
    state = db.get(DiscourseSourceState, source.id)
    if state is not None:
        if state.host != canonical.host or state.port != canonical.port:
            raise ImmutableDiscourseOrigin(
                "An authorized Discourse source origin cannot be changed."
            )
        if state.authorized_at is None:
            state.authorized_at = timestamp
            state.terms_confirmed_at = timestamp
            state.updated_at = timestamp
        return state

    state = DiscourseSourceState(
        source_id=source.id,
        scheme="https",
        host=canonical.host,
        port=canonical.port,
        authorized_at=timestamp,
        terms_confirmed_at=timestamp,
        created_at=timestamp,
        updated_at=timestamp,
    )
    db.add(state)
    db.flush()
    return state


def revoke_discourse_source(
    state: DiscourseSourceState,
    *,
    now: datetime | None = None,
) -> DiscourseSourceState:
    state.authorized_at = None
    state.terms_confirmed_at = None
    state.updated_at = _utc(now)
    return state


def discourse_readiness(
    source: Source,
    state: DiscourseSourceState | None,
    *,
    now: datetime | None = None,
) -> DiscourseReadiness:
    timestamp = _utc(now)
    if not source.enabled:
        return DiscourseReadiness(status="disabled", can_run=False)
    if state is None or state.authorized_at is None or state.terms_confirmed_at is None:
        return DiscourseReadiness(status="terms_required", can_run=False)
    retry_after = _optional_utc(state.retry_after_at)
    if retry_after is not None and retry_after > timestamp:
        return DiscourseReadiness(status="retry_later", can_run=False)

    last_success = _optional_utc(state.last_success_at)
    last_failure = _optional_utc(state.last_failure_at)
    if last_success is None and last_failure is None:
        return DiscourseReadiness(status="never_run", can_run=True)
    if last_failure is not None and (last_success is None or last_failure > last_success):
        return DiscourseReadiness(status="failed", can_run=True)
    return DiscourseReadiness(status="ready", can_run=True)


def parse_retry_after(
    value: str | None,
    *,
    now: datetime | None = None,
) -> datetime | None:
    if value is None:
        return None
    raw = value.strip()
    if not raw:
        return None
    timestamp = _utc(now)
    if raw.isascii() and raw.isdigit():
        seconds = min(int(raw), int(MAX_RETRY_AFTER.total_seconds()))
        return timestamp + timedelta(seconds=seconds)

    try:
        parsed = parsedate_to_datetime(raw)
    except (TypeError, ValueError, OverflowError):
        return None
    candidate = _utc(parsed)
    if candidate <= timestamp:
        return None
    return min(candidate, timestamp + MAX_RETRY_AFTER)


def record_discourse_failure(
    state: DiscourseSourceState,
    *,
    code: str,
    message: object,
    http_status: int | None = None,
    retry_after: str | None = None,
    at: datetime | None = None,
) -> DiscourseSourceState:
    if code not in FAILURE_CODES:
        raise ValueError("Unsupported Discourse failure code.")
    if http_status is not None and not 100 <= http_status <= 599:
        raise ValueError("HTTP status must be between 100 and 599.")
    timestamp = _utc(at)
    sanitized = sanitize_error_message(message) or code.replace("_", " ")
    state.last_failure_at = timestamp
    state.last_failure_code = code
    state.last_failure_message = sanitized[:500]
    state.last_http_status = http_status
    state.retry_after_at = parse_retry_after(retry_after, now=timestamp)
    state.updated_at = timestamp
    return state


def record_discourse_success(
    state: DiscourseSourceState,
    *,
    at: datetime | None = None,
    retry_after: str | None = None,
) -> DiscourseSourceState:
    timestamp = _utc(at)
    state.last_success_at = timestamp
    state.retry_after_at = parse_retry_after(retry_after, now=timestamp)
    state.updated_at = timestamp
    return state


def runtime_state_snapshot(
    source: Source,
    state: DiscourseSourceState | None,
    *,
    now: datetime | None = None,
) -> DiscourseRuntimeStateSnapshot:
    readiness = discourse_readiness(source, state, now=now)
    return DiscourseRuntimeStateSnapshot(
        source_id=source.id,
        origin=state.origin if state is not None else None,
        readiness=readiness.status,
        can_run=readiness.can_run,
        last_success_at=(
            _optional_utc(state.last_success_at) if state is not None else None
        ),
        last_failure_at=(
            _optional_utc(state.last_failure_at) if state is not None else None
        ),
        last_failure_code=state.last_failure_code if state is not None else None,
        last_failure_message=state.last_failure_message if state is not None else None,
        last_http_status=state.last_http_status if state is not None else None,
        retry_after_at=(
            _optional_utc(state.retry_after_at) if state is not None else None
        ),
    )
