"""Tests for connector edge-case fixtures.

Covers the acceptance criteria from the "Add connector fixture edge cases" issue:

1. Fixture mode stays key-free (works with no API credentials).
2. Raw usernames are not stored (minimized away before persistence).
3. Tests cover at least one malformed or sparse record per source.

The fixtures live in ``data/fixtures/edge_cases`` and are loaded by pointing a
``FixtureConnector`` at that directory. They are intentionally outside the
default (non-recursive) fixture glob so the demo pipeline is unaffected.
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models.all_models import NormalizedItem, RawItem
from app.services.ingestion.connectors import (
    ConnectorError,
    FixtureConnector,
    RedditConnector,
)
from app.services.ingestion.normalization import normalize
from app.workers.scan_pipeline import save_fetched_items

EDGE_DIR = settings.fixture_dir / "edge_cases"

# external_id prefixes used across the edge fixtures, one family per source.
EDGE_ID_PREFIXES = ("gh-edge", "hn-edge", "se-edge", "r-edge")

# external_id -> source, file name. One entry per ingestion source.
EXPECTED_FILES = {
    "github": "github_edge_sample.json",
    "hackernews": "hn_edge_sample.json",
    "stackexchange": "stackexchange_edge_sample.json",
    "reddit": "reddit_edge_sample.json",
}

# Obviously-fake usernames seeded into the fixtures. None of these should ever
# appear in stored raw payloads.
SEEDED_USERNAMES = {
    "edge-octocat",
    "edge_hn_user",
    "edge_se_owner",
    "edge_se_author",
    "edge_reddit_user",
    "edge_reddit_empty",
}

# Keys that would indicate a raw author field leaked into storage.
AUTHOR_KEYS = {"author", "by", "user", "owner", "display_name", "login"}

# Substrings that would indicate a credential leaked into a fixture file.
CREDENTIAL_MARKERS = (
    "api_key",
    "apikey",
    "client_id",
    "client_secret",
    "access_token",
    "secret",
    "password",
    "authorization",
    "bearer",
)


def _load_payload(source: str) -> dict:
    path = EDGE_DIR / EXPECTED_FILES[source]
    return json.loads(path.read_text())


def _all_records() -> list[tuple[str, dict]]:
    records: list[tuple[str, dict]] = []
    for source in EXPECTED_FILES:
        for record in _load_payload(source).get("items", []):
            records.append((source, record))
    return records


def _is_sparse_or_malformed(source: str, record: dict) -> bool:
    """Return True if a record exercises a sparse or malformed edge case."""
    # Sparse: little more than an id and a title.
    if len(set(record) - {"external_id", "id", "title"}) == 0:
        return True
    # A null-valued field is malformed regardless of source.
    if any(value is None for value in record.values()):
        return True
    if source == "github":
        labels = record.get("labels", [])
        if any(not isinstance(label, dict) for label in labels):
            return True
    if source == "hackernews":
        if isinstance(record.get("time"), str):
            return True
    if source == "stackexchange":
        if "owner" in record and not isinstance(record["owner"], dict):
            return True
    if source == "reddit":
        title = record.get("title", "")
        body = (record.get("body") or record.get("selftext") or "").strip()
        if "subreddit" not in record and "selftext" in record:
            return True
        # Title that cleans to nothing with no usable body.
        if title.strip() in {"", "<p></p>"} and not body:
            return True
    return False


def test_edge_fixture_files_exist_and_are_well_labeled() -> None:
    assert EDGE_DIR.is_dir(), f"missing edge fixture directory: {EDGE_DIR}"
    for source, filename in EXPECTED_FILES.items():
        path = EDGE_DIR / filename
        assert path.is_file(), f"missing edge fixture file: {path}"
        payload = json.loads(path.read_text())
        assert payload.get("source") == source
        assert payload.get("items"), f"{filename} has no items"


def test_each_source_has_a_malformed_or_sparse_record() -> None:
    for source in EXPECTED_FILES:
        records = _load_payload(source).get("items", [])
        edge_records = [r for r in records if _is_sparse_or_malformed(source, r)]
        assert edge_records, f"{source} fixtures lack a malformed or sparse record"


def test_fixture_mode_is_key_free() -> None:
    # No credentials are configured in the test environment.
    assert not settings.reddit_client_id
    assert not settings.github_token
    assert not settings.stack_exchange_key

    # A live connector refuses to run without credentials...
    with pytest.raises(ConnectorError):
        RedditConnector().fetch(limit=1)

    # ...but fixture mode loads the same edge cases with no keys at all.
    items = FixtureConnector(fixture_dir=EDGE_DIR).fetch(limit=100)
    assert items, "fixture mode returned no items"
    assert {item.source for item in items} == set(EXPECTED_FILES)


def test_fixture_files_contain_no_credentials() -> None:
    for source in EXPECTED_FILES:
        raw_text = (EDGE_DIR / EXPECTED_FILES[source]).read_text().lower()
        for marker in CREDENTIAL_MARKERS:
            assert marker not in raw_text, f"{source} fixture contains '{marker}'"


def test_every_edge_record_normalizes_without_error() -> None:
    items = FixtureConnector(fixture_dir=EDGE_DIR).fetch(limit=100)
    assert items
    for raw in items:
        normalized = normalize(raw)
        # Normalization must always produce the core fields the pipeline needs.
        for key in ("source", "external_id", "title", "body", "text_hash"):
            assert key in normalized
        assert len(normalized["text_hash"]) == 64
        # The raw username must never survive as the stored author hash.
        if normalized["author_hash"] is not None:
            assert normalized["author_hash"] not in SEEDED_USERNAMES


def test_raw_usernames_are_not_stored(db_session) -> None:
    fetched = FixtureConnector(fixture_dir=EDGE_DIR).fetch(limit=100)
    save_fetched_items(db_session, fetched)
    db_session.flush()

    raw_items = db_session.scalars(select(RawItem)).all()
    assert raw_items, "no raw items were stored"

    for raw_item in raw_items:
        stored_keys = set(raw_item.raw_json)
        leaked = stored_keys & AUTHOR_KEYS
        assert not leaked, f"{raw_item.source} stored author keys: {leaked}"
        serialized = json.dumps(raw_item.raw_json)
        for username in SEEDED_USERNAMES:
            assert username not in serialized, f"{raw_item.source} stored raw username '{username}'"


def test_records_with_authors_are_hashed_not_stored(db_session) -> None:
    fetched = FixtureConnector(fixture_dir=EDGE_DIR).fetch(limit=100)
    save_fetched_items(db_session, fetched)
    db_session.flush()

    hashes = {
        item.external_id: item.author_hash
        for item in db_session.scalars(select(NormalizedItem)).all()
    }

    # These records carry a (fake) username and survive normalization, so they
    # must end up with a non-null author hash that is not the raw username.
    for external_id in (
        "gh-edge-malformed-1",
        "hn-edge-malformed-1",
        "se-edge-malformed-1",
        "r-edge-malformed-1",
    ):
        assert external_id in hashes, f"{external_id} was not normalized"
        author_hash = hashes[external_id]
        assert author_hash is not None
        assert author_hash not in SEEDED_USERNAMES


def test_empty_record_is_skipped_not_normalized(db_session) -> None:
    fetched = FixtureConnector(fixture_dir=EDGE_DIR).fetch(limit=100)
    save_fetched_items(db_session, fetched)
    db_session.flush()

    # The empty Reddit record cleans to no title and no body: the pipeline keeps
    # the minimized raw row but must not create a normalized item from it.
    raw = db_session.scalar(select(RawItem).where(RawItem.external_id == "r-edge-empty-1"))
    assert raw is not None
    normalized = db_session.scalar(
        select(NormalizedItem).where(NormalizedItem.external_id == "r-edge-empty-1")
    )
    assert normalized is None


def test_edge_fixtures_excluded_from_default_demo_run() -> None:
    # The edge cases live in a subdirectory on purpose: the default
    # FixtureConnector glob is non-recursive, so the demo pipeline must never
    # pick them up. This locks in that contract against future glob changes.
    default_items = FixtureConnector().fetch(limit=300)
    leaked = [
        item.external_id for item in default_items if item.external_id.startswith(EDGE_ID_PREFIXES)
    ]
    assert not leaked, f"edge fixtures leaked into the default demo run: {leaked}"
