from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import pytest

from app.models.all_models import Source
from app.services.discourse_sources.service import (
    FAILURE_CODES,
    MAX_RETRY_AFTER,
    ImmutableDiscourseOrigin,
    InvalidDiscourseOrigin,
    InvalidDiscourseSource,
    TermsConfirmationRequired,
    authorize_discourse_source,
    canonicalize_discourse_origin,
    discourse_readiness,
    parse_retry_after,
    record_discourse_failure,
    record_discourse_success,
    revoke_discourse_source,
    runtime_state_snapshot,
)


def discourse_source(db_session, *, enabled: bool = True) -> Source:
    source = Source(
        name="Example forum",
        type="discourse",
        config_json={},
        enabled=enabled,
    )
    db_session.add(source)
    db_session.flush()
    return source


def test_canonical_origin_normalizes_idna_case_root_and_port() -> None:
    default_port = canonicalize_discourse_origin(" HTTPS://BÜCHER.Example.:443/ ")
    assert default_port.scheme == "https"
    assert default_port.host == "xn--bcher-kva.example"
    assert default_port.port == 443
    assert default_port.origin == "https://xn--bcher-kva.example"

    custom_port = canonicalize_discourse_origin("https://community.example:8443")
    assert custom_port.origin == "https://community.example:8443"


@pytest.mark.parametrize(
    "origin",
    [
        "http://forum.example",
        "https://user:password@forum.example",
        "https://forum.example/latest",
        "https://forum.example?category=1",
        "https://forum.example#latest",
        "https://127.0.0.1",
        "https://[::1]",
        "https://2130706433",
        "https://localhost",
        "https://bad_host.example",
        "https://forum.example:0",
    ],
)
def test_canonical_origin_rejects_non_exact_public_https_hosts(origin: str) -> None:
    with pytest.raises(InvalidDiscourseOrigin):
        canonicalize_discourse_origin(origin)


def test_authorization_requires_terms_and_origin_is_immutable(db_session) -> None:
    source = discourse_source(db_session)
    authorized_at = datetime(2026, 7, 11, 12, tzinfo=UTC)

    with pytest.raises(TermsConfirmationRequired):
        authorize_discourse_source(
            db_session,
            source=source,
            origin="https://forum.example",
            terms_confirmed=False,
            now=authorized_at,
        )

    state = authorize_discourse_source(
        db_session,
        source=source,
        origin="https://Forum.Example/",
        terms_confirmed=True,
        now=authorized_at,
    )
    assert state.origin == "https://forum.example"
    assert state.authorized_at == state.terms_confirmed_at == authorized_at

    repeated = authorize_discourse_source(
        db_session,
        source=source,
        origin="https://forum.example",
        terms_confirmed=True,
        now=authorized_at + timedelta(hours=1),
    )
    assert repeated is state
    assert repeated.authorized_at == authorized_at

    with pytest.raises(ImmutableDiscourseOrigin):
        authorize_discourse_source(
            db_session,
            source=source,
            origin="https://other.example",
            terms_confirmed=True,
            now=authorized_at,
        )

    revoke_discourse_source(state, now=authorized_at + timedelta(hours=2))
    assert state.authorized_at is None
    assert state.terms_confirmed_at is None
    with pytest.raises(ImmutableDiscourseOrigin):
        authorize_discourse_source(
            db_session,
            source=source,
            origin="https://other.example",
            terms_confirmed=True,
            now=authorized_at,
        )


def test_authorization_rejects_non_discourse_sources(db_session) -> None:
    source = Source(
        name="GitHub Issues",
        type="github",
        config_json={},
        enabled=True,
    )
    db_session.add(source)
    db_session.flush()
    with pytest.raises(InvalidDiscourseSource):
        authorize_discourse_source(
            db_session,
            source=source,
            origin="https://forum.example",
            terms_confirmed=True,
        )


def test_readiness_tracks_authorization_retry_failure_and_success(db_session) -> None:
    now = datetime(2026, 7, 11, 12, tzinfo=UTC)
    source = discourse_source(db_session)
    assert discourse_readiness(source, None, now=now).status == "terms_required"

    state = authorize_discourse_source(
        db_session,
        source=source,
        origin="https://forum.example",
        terms_confirmed=True,
        now=now,
    )
    never_run = discourse_readiness(source, state, now=now)
    assert (never_run.status, never_run.can_run) == ("never_run", True)

    record_discourse_failure(
        state,
        code="rate_limited",
        message="HTTP 429",
        http_status=429,
        retry_after="120",
        at=now,
    )
    retry_later = discourse_readiness(source, state, now=now + timedelta(seconds=30))
    assert (retry_later.status, retry_later.can_run) == ("retry_later", False)

    after_retry = discourse_readiness(source, state, now=now + timedelta(minutes=3))
    assert (after_retry.status, after_retry.can_run) == ("failed", True)

    record_discourse_success(state, at=now + timedelta(minutes=4))
    ready = discourse_readiness(source, state, now=now + timedelta(minutes=4))
    assert (ready.status, ready.can_run) == ("ready", True)
    assert state.retry_after_at is None

    record_discourse_success(
        state,
        at=now + timedelta(minutes=5),
        retry_after="60",
    )
    paced = discourse_readiness(source, state, now=now + timedelta(minutes=5))
    assert (paced.status, paced.can_run) == ("retry_later", False)
    assert state.retry_after_at == now + timedelta(minutes=6)

    source.enabled = False
    assert discourse_readiness(source, state, now=now).status == "disabled"


def test_retry_after_supports_seconds_http_dates_and_safe_bounds() -> None:
    now = datetime(2026, 7, 11, 12, tzinfo=UTC)
    assert parse_retry_after("120", now=now) == now + timedelta(seconds=120)
    later = now + timedelta(hours=1)
    assert parse_retry_after(format_datetime(later, usegmt=True), now=now) == later
    assert parse_retry_after("not-a-date", now=now) is None
    assert parse_retry_after(format_datetime(now - timedelta(seconds=1), usegmt=True), now=now) is None
    assert parse_retry_after("999999999", now=now) == now + MAX_RETRY_AFTER


def test_failure_persistence_uses_controlled_codes_and_sanitized_messages(db_session) -> None:
    now = datetime(2026, 7, 11, 12, tzinfo=UTC)
    source = discourse_source(db_session)
    state = authorize_discourse_source(
        db_session,
        source=source,
        origin="https://forum.example",
        terms_confirmed=True,
        now=now,
    )
    secret = "DO-NOT-PERSIST"
    record_discourse_failure(
        state,
        code="rate_limited",
        message=f"Authorization: Bearer {secret}\naccess_token={secret} " + "x" * 600,
        http_status=429,
        retry_after="60",
        at=now,
    )
    assert state.last_failure_code in FAILURE_CODES
    assert state.last_failure_message is not None
    assert secret not in state.last_failure_message
    assert len(state.last_failure_message) <= 500
    assert state.last_http_status == 429
    assert state.retry_after_at == now + timedelta(seconds=60)

    snapshot = runtime_state_snapshot(source, state, now=now)
    assert snapshot.origin == "https://forum.example"
    assert snapshot.readiness == "retry_later"
    assert snapshot.last_failure_message == state.last_failure_message

    with pytest.raises(ValueError):
        record_discourse_failure(state, code="raw_exception", message="bad", at=now)
    with pytest.raises(ValueError):
        record_discourse_failure(
            state,
            code="http_error",
            message="bad",
            http_status=700,
            at=now,
        )
