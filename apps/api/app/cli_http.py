"""Bounded HTTP command adapter for the packaged TaskSignal CLI.

The public methods intentionally map one-to-one to the documented ``/api/v1``
surface.  There is no generic request method: callers can invoke only the
known noun-first CLI operations defined here.
"""

from __future__ import annotations

import os
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Self
from urllib.parse import quote
from uuid import UUID

import httpx

DEFAULT_API_URL = "http://127.0.0.1:8000"
API_URL_ENV = "TASKSIGNAL_API_URL"
LEGACY_API_BASE_ENV = "TASKSIGNAL_API_BASE"
OPERATOR_TOKEN_ENV = "TASKSIGNAL_OPERATOR_TOKEN"
OPERATOR_TOKEN_HEADER = "X-Operator-Scan-Token"
DEFAULT_TIMEOUT_SECONDS = 20.0
MAX_TIMEOUT_SECONDS = 60.0
DEFAULT_MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024
MAX_DOWNLOAD_BYTES = 512 * 1024 * 1024

_UNSET = object()
_BEARER_RE = re.compile(r"(?i)\bbearer\s+[^\s,;]+")
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(?:api[_-]?key|authorization|cookie|credential|password|secret|token)"
    r"\s*[:=]\s*[^\s,;]+"
)
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")
_SAFE_ERROR_CODE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


def _normalize_api_root(value: str) -> str:
    candidate = value.strip()
    if not candidate:
        raise ValueError("TaskSignal API URL cannot be empty.")
    try:
        url = httpx.URL(candidate)
    except (TypeError, ValueError) as exc:
        raise ValueError("TaskSignal API URL is invalid.") from exc
    if url.scheme not in {"http", "https"} or not url.host:
        raise ValueError("TaskSignal API URL must use HTTP or HTTPS.")
    if url.scheme == "http" and url.host.casefold() not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("TaskSignal API URL must use HTTPS unless it targets explicit loopback.")
    if url.username or url.password or url.query or url.fragment:
        raise ValueError("TaskSignal API URL cannot contain credentials, a query, or a fragment.")
    path = url.path.rstrip("/")
    if not path.endswith("/api/v1"):
        path = f"{path}/api/v1"
    normalized = url.copy_with(path=f"{path}/", query=None, fragment=None)
    return str(normalized).rstrip("/")


def _bounded_timeout(value: float) -> float:
    if isinstance(value, bool) or not 0.1 <= value <= MAX_TIMEOUT_SECONDS:
        raise ValueError(
            f"TaskSignal request timeout must be between 0.1 and {MAX_TIMEOUT_SECONDS:g} seconds."
        )
    return float(value)


def _bounded_download_size(value: int) -> int:
    if isinstance(value, bool) or not 1 <= value <= MAX_DOWNLOAD_BYTES:
        raise ValueError(
            f"TaskSignal download limit must be between 1 and {MAX_DOWNLOAD_BYTES} bytes."
        )
    return value


def _path_identifier(value: UUID | str) -> str:
    try:
        identifier = UUID(str(value))
    except (AttributeError, TypeError, ValueError):
        # Keep malformed identifiers out of paths and, consequently, out of
        # returned error metadata. The API will reject this inert sentinel.
        return "invalid"
    return quote(str(identifier), safe="")


def _json_identifier(value: UUID | str | None) -> str | None:
    return None if value is None else str(value)


def _without_none(values: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}


def _absolute_output_path(value: str | os.PathLike[str]) -> Path:
    expanded = Path(value).expanduser()
    absolute = expanded if expanded.is_absolute() else Path.cwd() / expanded
    # Resolve only the parent. Resolving the final component would follow a
    # pre-existing symlink before the explicit no-overwrite check below.
    return absolute.parent.resolve() / absolute.name


class TaskSignalHttpClient:
    """Composable, synchronous client for TaskSignal's local REST API."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        operator_token: str | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_download_bytes: int = DEFAULT_MAX_DOWNLOAD_BYTES,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if base_url is not None:
            configured_url = base_url
        elif API_URL_ENV in os.environ:
            configured_url = os.environ[API_URL_ENV]
        elif LEGACY_API_BASE_ENV in os.environ:
            configured_url = os.environ[LEGACY_API_BASE_ENV]
        else:
            configured_url = DEFAULT_API_URL
        self._api_root = _normalize_api_root(configured_url)
        self._health_url = str(httpx.URL(self._api_root).copy_with(path="/health"))
        configured_token = (
            operator_token if operator_token is not None else os.getenv(OPERATOR_TOKEN_ENV)
        )
        self._operator_token = configured_token.strip() if configured_token else None
        self._max_download_bytes = _bounded_download_size(max_download_bytes)
        headers = {
            "Accept": "application/json",
            "User-Agent": "TaskSignal-CLI",
        }
        self._client = httpx.Client(
            base_url=f"{self._api_root}/",
            headers=headers,
            timeout=httpx.Timeout(_bounded_timeout(timeout_seconds)),
            follow_redirects=False,
            transport=transport,
        )

    @classmethod
    def from_environment(cls, **overrides: Any) -> Self:
        """Create a client from the canonical URL, legacy fallback, and optional token."""

        return cls(**overrides)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"TaskSignalHttpClient(base_url={self._api_root!r})"

    def close(self) -> None:
        self._client.close()
        self._operator_token = None

    def health(self) -> dict[str, Any]:
        """Read the server-root health endpoint used by ``tasksignal doctor``."""

        return self._request_json(
            "GET",
            "/health",
            absolute_url=self._health_url,
            include_operator_token=False,
        )

    # Projects

    def projects_list(self) -> dict[str, Any]:
        return self._request_json("GET", "/research-projects")

    def projects_get(self, project_id: UUID | str) -> dict[str, Any]:
        return self._request_json(
            "GET",
            f"/research-projects/{_path_identifier(project_id)}",
        )

    def projects_create(
        self,
        *,
        name: str,
        description: str | None = None,
        source_type: str = "hackernews",
        source_id: UUID | str | None = None,
        query: str = "",
        limit: int = 30,
        cadence: str = "manual",
        schedule_interval_hours: int | None = None,
        labels: Sequence[str] = (),
        enabled: bool = True,
    ) -> dict[str, Any]:
        return self._request_json(
            "POST",
            "/research-projects",
            json_body={
                "name": name,
                "description": description,
                "source_type": source_type,
                "source_id": _json_identifier(source_id),
                "query": query,
                "limit": limit,
                "cadence": cadence,
                "schedule_interval_hours": schedule_interval_hours,
                "labels": list(labels),
                "enabled": enabled,
            },
        )

    def projects_update(
        self,
        project_id: UUID | str,
        *,
        expected_version: int | None,
        name: Any = _UNSET,
        description: Any = _UNSET,
        source_type: Any = _UNSET,
        source_id: Any = _UNSET,
        query: Any = _UNSET,
        limit: Any = _UNSET,
        cadence: Any = _UNSET,
        schedule_interval_hours: Any = _UNSET,
        labels: Any = _UNSET,
        enabled: Any = _UNSET,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"expected_version": expected_version}
        updates = {
            "name": name,
            "description": description,
            "source_type": source_type,
            "source_id": source_id,
            "query": query,
            "limit": limit,
            "cadence": cadence,
            "schedule_interval_hours": schedule_interval_hours,
            "labels": labels,
            "enabled": enabled,
        }
        for field, value in updates.items():
            if value is _UNSET:
                continue
            if field == "source_id":
                value = _json_identifier(value)
            elif field == "labels" and value is not None:
                value = list(value)
            payload[field] = value
        return self._request_json(
            "PATCH",
            f"/research-projects/{_path_identifier(project_id)}",
            json_body=payload,
        )

    def projects_run(self, project_id: UUID | str) -> dict[str, Any]:
        return self._request_json(
            "POST",
            f"/research-projects/{_path_identifier(project_id)}/run",
        )

    # Runs

    def runs_list(self, project_id: UUID | str) -> dict[str, Any]:
        return self._request_json(
            "GET",
            f"/research-projects/{_path_identifier(project_id)}/runs",
        )

    def runs_delta(
        self,
        project_id: UUID | str,
        run_id: UUID | str,
    ) -> dict[str, Any]:
        return self._request_json(
            "GET",
            (
                f"/research-projects/{_path_identifier(project_id)}/runs/"
                f"{_path_identifier(run_id)}/delta"
            ),
        )

    # Opportunity threads and search

    def opportunities_list(
        self,
        *,
        project_id: UUID | str | None = None,
        review_state: str | None = None,
    ) -> dict[str, Any]:
        return self._request_json(
            "GET",
            "/opportunity-threads",
            params=_without_none(
                {
                    "project_id": _json_identifier(project_id),
                    "review_state": review_state,
                }
            ),
        )

    def opportunities_get(self, thread_id: UUID | str) -> dict[str, Any]:
        return self._request_json(
            "GET",
            f"/opportunity-threads/{_path_identifier(thread_id)}",
        )

    def opportunities_search(
        self,
        *,
        query: str,
        limit: int = 10,
        project_id: UUID | str | None = None,
        source: str | None = None,
        signal_type: str | None = None,
        review_state: str | None = None,
    ) -> dict[str, Any]:
        payload = _without_none(
            {
                "query": query,
                "limit": limit,
                "project_id": _json_identifier(project_id),
                "source": source,
                "signal_type": signal_type,
                "review_state": review_state,
            }
        )
        return self._request_json("POST", "/search", json_body=payload)

    def opportunities_decision(
        self,
        thread_id: UUID | str,
        *,
        review_state: str,
        expected_version: int,
        review_note: str | None = None,
    ) -> dict[str, Any]:
        return self._request_json(
            "PATCH",
            f"/opportunity-threads/{_path_identifier(thread_id)}/decision",
            json_body={
                "review_state": review_state,
                "review_note": review_note,
                "expected_version": expected_version,
            },
        )

    def opportunities_detach(
        self,
        thread_id: UUID | str,
        snapshot_id: UUID | str,
        *,
        expected_version: int,
    ) -> dict[str, Any]:
        return self._request_json(
            "POST",
            (
                f"/opportunity-threads/{_path_identifier(thread_id)}/snapshots/"
                f"{_path_identifier(snapshot_id)}/detach"
            ),
            json_body={"expected_version": expected_version},
        )

    # Evidence labels

    def evidence_label(
        self,
        item_id: UUID | str,
        *,
        label: str,
        user_note: str | None = None,
        expected_version: int | None = None,
    ) -> dict[str, Any]:
        return self._request_json(
            "POST",
            "/labels",
            json_body={
                "item_id": str(item_id),
                "label": label,
                "user_note": user_note,
                "expected_version": expected_version,
            },
        )

    # Build packets

    def packets_list(
        self,
        thread_id: UUID | str,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        return self._request_json(
            "GET",
            f"/opportunity-threads/{_path_identifier(thread_id)}/build-packets",
            params={"limit": limit, "offset": offset},
        )

    def packets_get(self, packet_id: UUID | str) -> dict[str, Any]:
        return self._request_json(
            "GET",
            f"/build-packets/{_path_identifier(packet_id)}",
        )

    def packets_create(
        self,
        thread_id: UUID | str,
        *,
        expected_version: int | None = None,
        use_configured_ai: bool = False,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"use_configured_ai": use_configured_ai}
        if expected_version is not None:
            payload["expected_version"] = expected_version
        return self._request_json(
            "POST",
            f"/opportunity-threads/{_path_identifier(thread_id)}/build-packets",
            json_body=payload,
        )

    def packets_verify(self, packet_id: UUID | str) -> dict[str, Any]:
        return self._request_json(
            "GET",
            f"/build-packets/{_path_identifier(packet_id)}/verify",
        )

    def packets_download(
        self,
        packet_id: UUID | str,
        *,
        output_path: str | os.PathLike[str],
    ) -> dict[str, Any]:
        path = f"/build-packets/{_path_identifier(packet_id)}/download"
        output = _absolute_output_path(output_path)
        if output.exists() or output.is_symlink():
            return self._error_envelope(
                "GET",
                path,
                code="output_exists",
                message="The requested output path already exists.",
            )
        if not output.parent.is_dir():
            return self._error_envelope(
                "GET",
                path,
                code="output_parent_missing",
                message="The output directory does not exist.",
            )

        response = self._download_response(path)
        if isinstance(response, dict):
            return response
        content, status_code = response
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        flags |= getattr(os, "O_NOFOLLOW", 0)
        flags |= getattr(os, "O_BINARY", 0)
        try:
            descriptor = os.open(output, flags, 0o600)
            try:
                with os.fdopen(descriptor, "wb") as destination:
                    destination.write(content)
            except BaseException:
                output.unlink(missing_ok=True)
                raise
        except FileExistsError:
            return self._error_envelope(
                "GET",
                path,
                code="output_exists",
                message="The requested output path already exists.",
                status=status_code,
            )
        except OSError:
            output.unlink(missing_ok=True)
            return self._error_envelope(
                "GET",
                path,
                code="write_failed",
                message="TaskSignal could not write the build-packet archive.",
                status=status_code,
            )
        return self._success_envelope(
            "GET",
            path,
            {"path": str(output), "bytes": len(content)},
            status_code,
        )

    # Agent sessions

    def sessions_list(self) -> dict[str, Any]:
        return self._request_json("GET", "/agent-sessions")

    def sessions_get(self, session_id: UUID | str) -> dict[str, Any]:
        return self._request_json(
            "GET",
            f"/agent-sessions/{_path_identifier(session_id)}",
        )

    def sessions_approve(
        self,
        session_id: UUID | str,
        *,
        expected_version: int,
        use_configured_ai: bool = False,
    ) -> dict[str, Any]:
        return self._request_json(
            "POST",
            f"/agent-sessions/{_path_identifier(session_id)}/approve",
            json_body={
                "expected_version": expected_version,
                "use_configured_ai": use_configured_ai,
            },
        )

    def sessions_revoke(
        self,
        session_id: UUID | str,
        *,
        expected_version: int,
    ) -> dict[str, Any]:
        return self._request_json(
            "POST",
            f"/agent-sessions/{_path_identifier(session_id)}/revoke",
            json_body={"expected_version": expected_version},
        )

    def sessions_actions(
        self,
        session_id: UUID | str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        return self._request_json(
            "GET",
            f"/agent-sessions/{_path_identifier(session_id)}/actions",
            params={"limit": limit, "offset": offset},
        )

    # Transport helpers

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        absolute_url: str | None = None,
        include_operator_token: bool = True,
    ) -> dict[str, Any]:
        request_kwargs: dict[str, Any] = {}
        if params:
            request_kwargs["params"] = params
        if json_body is not None:
            request_kwargs["json"] = json_body
        if include_operator_token and self._operator_token:
            request_kwargs["headers"] = {OPERATOR_TOKEN_HEADER: self._operator_token}
        try:
            response = self._client.request(
                method,
                absolute_url or path.lstrip("/"),
                **request_kwargs,
            )
        except httpx.TimeoutException:
            return self._error_envelope(
                method,
                path,
                code="timeout",
                message="TaskSignal did not respond before the request timeout.",
            )
        except httpx.RequestError:
            return self._error_envelope(
                method,
                path,
                code="connection_error",
                message="TaskSignal could not be reached.",
            )
        if not response.is_success:
            return self._http_error_envelope(method, path, response)
        if response.status_code == 204 or not response.content:
            data: Any = None
        else:
            try:
                data = response.json()
            except ValueError:
                return self._error_envelope(
                    method,
                    path,
                    code="invalid_response",
                    message="TaskSignal returned an invalid JSON response.",
                    status=response.status_code,
                )
        return self._success_envelope(method, path, data, response.status_code)

    def _download_response(
        self,
        path: str,
    ) -> tuple[bytes, int] | dict[str, Any]:
        try:
            with self._client.stream(
                "GET",
                path.lstrip("/"),
                headers={
                    "Accept": "application/zip",
                    **(
                        {OPERATOR_TOKEN_HEADER: self._operator_token}
                        if self._operator_token
                        else {}
                    ),
                },
            ) as response:
                if not response.is_success:
                    response.read()
                    return self._http_error_envelope("GET", path, response)
                declared_size = response.headers.get("Content-Length")
                if declared_size:
                    try:
                        if int(declared_size) > self._max_download_bytes:
                            return self._download_too_large(path, response.status_code)
                    except ValueError:
                        return self._invalid_archive(path, response.status_code)
                content = bytearray()
                for chunk in response.iter_bytes():
                    content.extend(chunk)
                    if len(content) > self._max_download_bytes:
                        return self._download_too_large(path, response.status_code)
                media_type = response.headers.get("Content-Type", "").partition(";")[0].lower()
                if media_type != "application/zip" or not content.startswith(b"PK"):
                    return self._invalid_archive(path, response.status_code)
                return bytes(content), response.status_code
        except httpx.TimeoutException:
            return self._error_envelope(
                "GET",
                path,
                code="timeout",
                message="TaskSignal did not respond before the request timeout.",
            )
        except httpx.RequestError:
            return self._error_envelope(
                "GET",
                path,
                code="connection_error",
                message="TaskSignal could not be reached.",
            )

    def _download_too_large(self, path: str, status: int) -> dict[str, Any]:
        return self._error_envelope(
            "GET",
            path,
            code="response_too_large",
            message="The build-packet archive exceeds the configured download limit.",
            status=status,
        )

    def _invalid_archive(self, path: str, status: int) -> dict[str, Any]:
        return self._error_envelope(
            "GET",
            path,
            code="invalid_response",
            message="TaskSignal returned an invalid build-packet archive.",
            status=status,
        )

    def _http_error_envelope(
        self,
        method: str,
        path: str,
        response: httpx.Response,
    ) -> dict[str, Any]:
        code = f"http_{response.status_code}"
        message = f"TaskSignal returned HTTP {response.status_code}."
        try:
            payload = response.json()
        except ValueError:
            payload = None
        if isinstance(payload, dict):
            detail = payload.get("detail")
            if isinstance(detail, str):
                message = self._redacted_message(detail)
            elif isinstance(detail, dict):
                detail_code = detail.get("code")
                detail_message = detail.get("message")
                if isinstance(detail_code, str) and _SAFE_ERROR_CODE_RE.fullmatch(detail_code):
                    code = detail_code
                if isinstance(detail_message, str):
                    message = self._redacted_message(detail_message)
        return self._error_envelope(
            method,
            path,
            code=code,
            message=message,
            status=response.status_code,
        )

    def _redacted_message(self, message: str) -> str:
        redacted = message
        if self._operator_token:
            redacted = redacted.replace(self._operator_token, "[REDACTED]")
        redacted = _BEARER_RE.sub("Bearer [REDACTED]", redacted)
        redacted = _SECRET_ASSIGNMENT_RE.sub("[REDACTED]", redacted)
        redacted = _JWT_RE.sub("[REDACTED]", redacted)
        normalized = " ".join(redacted.split())
        if not normalized:
            return "TaskSignal rejected the request."
        return normalized[:500]

    @staticmethod
    def _success_envelope(
        method: str,
        path: str,
        data: Any,
        status: int,
    ) -> dict[str, Any]:
        return {
            "ok": True,
            "data": data,
            "error": None,
            "meta": {"method": method, "path": path, "status": status},
        }

    @staticmethod
    def _error_envelope(
        method: str,
        path: str,
        *,
        code: str,
        message: str,
        status: int | None = None,
    ) -> dict[str, Any]:
        return {
            "ok": False,
            "data": None,
            "error": {"code": code, "message": message, "status": status},
            "meta": {"method": method, "path": path, "status": status},
        }
