from urllib.parse import quote

from app.services.build_packets import redact_public_text, safe_public_source_url


def test_public_text_redacts_credentials_identities_and_embedded_urls() -> None:
    raw = (
        "Contact user@example.test with token=SUPER-SECRET-VALUE or JWT "
        "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.signaturevalue "
        "at https://example.test/private?session_id=SESSION-SECRET."
    )

    redacted = redact_public_text(raw)

    assert "user@example.test" not in redacted
    assert "SUPER-SECRET-VALUE" not in redacted
    assert "eyJhbGci" not in redacted
    assert "https://" not in redacted
    assert redacted.count("[REDACTED]") >= 3


def test_public_text_redacts_common_labeled_credentials() -> None:
    raw = "\n".join(
        (
            "api_key=AbCdEfGhIjKlMnOp",
            "access_token: AbCdEfGhIjKlMnOp",
            "client_secret='AbCdEfGhIjKlMnOp'",
            "Authorization: Basic dXNlcjpwYXNzd29yZA==",
            "AWS_SECRET_ACCESS_KEY=AbCdEfGhIjKlMnOp",
            "cookie: session=AbCdEfGhIjKlMnOp; theme=dark",
            "X-API-Key: AbCdEfGhIjKlMnOp",
            "refresh_token=AbCdEfGhIjKlMnOp",
            "oauth_client_secret=AbCdEfGhIjKlMnOp",
            "credential=AbCdEfGhIjKlMnOp",
            "private_key=AbCdEfGhIjKlMnOp",
            "Authorization: Digest AbCdEfGhIjKlMnOp",
            "Authorization: token AbCdEfGhIjKlMnOp",
            "Authorization: Signature AbCdEfGhIjKlMnOp",
            '{"api_key":"AbCdEfGhIjKlMnOp"}',
            "{'refresh_token': 'AbCdEfGhIjKlMnOp'}",
            "`client_secret`: `AbCdEfGhIjKlMnOp`",
            '{"password":"correct horse battery staple"}',
            "client_secret='multi word client secret'",
            "`private_key`: `multi word private key`",
        )
    )

    redacted = redact_public_text(raw)

    assert "AbCdEfGhIjKlMnOp" not in redacted
    assert "dXNlcjpwYXNzd29yZA==" not in redacted
    assert "theme=dark" not in redacted
    assert "correct horse battery staple" not in redacted
    assert "multi word client secret" not in redacted
    assert "multi word private key" not in redacted
    assert redacted.count("[REDACTED]") == 20


def test_public_source_url_is_fail_closed_but_keeps_numeric_public_ids() -> None:
    assert safe_public_source_url("https://news.ycombinator.com/item?id=12345") == (
        "https://news.ycombinator.com/item?id=12345"
    )
    for unsafe in (
        "https://example.test/item?session_id=SESSION-SECRET",
        "https://example.test/item?jwt=JWT-SECRET",
        "https://example.test/item?email=user@example.test",
        "https://example.test/item#token=SECRET",
        "https://user@example.test/item",
        "http://127.0.0.1/item",
        "http://service.internal/item",
        "https://example.test/users/user%40example.test",
        "https://example.test/path/token%3DSUPER-SECRET-VALUE",
        "https://example.test/path/token%253DSUPER-SECRET-VALUE",
    ):
        assert safe_public_source_url(unsafe) == ""

    deeply_encoded = "token=DEEP-PERCENT-ENCODED-SECRET"
    for _ in range(12):
        deeply_encoded = quote(deeply_encoded, safe="")
    assert safe_public_source_url(f"https://example.test/path/{deeply_encoded}") == ""
