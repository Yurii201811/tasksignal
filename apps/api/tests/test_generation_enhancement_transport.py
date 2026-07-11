from __future__ import annotations

import json

import pytest

from app.services.generation import enhancement


class FakeStreamResponse:
    def __init__(self, chunks: list[bytes], *, content_length: int | None = None) -> None:
        self.chunks = chunks
        self.headers = (
            {"Content-Length": str(content_length)} if content_length is not None else {}
        )

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def raise_for_status(self) -> None:
        return None

    def iter_bytes(self):
        yield from self.chunks


def test_provider_json_transport_streams_with_a_hard_response_limit(monkeypatch) -> None:
    payload = {"response": "enhanced"}
    body = json.dumps(payload).encode()
    monkeypatch.setattr(
        enhancement.httpx,
        "stream",
        lambda *_args, **_kwargs: FakeStreamResponse([body[:3], body[3:]]),
    )
    assert enhancement.bounded_provider_json(
        "https://provider.example/generate",
        payload={"input": "safe"},
        timeout=1,
    ) == payload

    monkeypatch.setattr(
        enhancement.httpx,
        "stream",
        lambda *_args, **_kwargs: FakeStreamResponse(
            [],
            content_length=enhancement.MAX_PROVIDER_RESPONSE_BYTES + 1,
        ),
    )
    with pytest.raises(enhancement.EnhancementUnavailable, match="too large"):
        enhancement.bounded_provider_json(
            "https://provider.example/generate",
            payload={"input": "safe"},
            timeout=1,
        )


def test_provider_json_transport_rejects_invalid_or_oversized_streams(monkeypatch) -> None:
    for chunks in (
        [b"not-json"],
        [b"[]"],
        [b"x" * (enhancement.MAX_PROVIDER_RESPONSE_BYTES + 1)],
    ):
        monkeypatch.setattr(
            enhancement.httpx,
            "stream",
            lambda *_args, _chunks=chunks, **_kwargs: FakeStreamResponse(_chunks),
        )
        with pytest.raises(enhancement.EnhancementUnavailable):
            enhancement.bounded_provider_json(
                "https://provider.example/generate",
                payload={"input": "safe"},
                timeout=1,
            )
