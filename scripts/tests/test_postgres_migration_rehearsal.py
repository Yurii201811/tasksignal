from __future__ import annotations

import unittest

from sqlalchemy import make_url

from scripts.postgres_migration_rehearsal import (
    _case_database_url,
    _normalized_postgresql_url,
    _safe_failure_message,
    _validate_identifier,
)


class PostgresMigrationRehearsalUnitTests(unittest.TestCase):
    def test_case_url_uses_psycopg_and_isolated_database(self) -> None:
        base = _normalized_postgresql_url(
            "postgresql://tasksignal:secret@127.0.0.1:5432/tasksignal?sslmode=disable"
        )

        scoped = make_url(_case_database_url(base, "ts_rehearsal_123_fresh"))

        self.assertEqual(scoped.drivername, "postgresql+psycopg")
        self.assertEqual(scoped.query["sslmode"], "disable")
        self.assertEqual(scoped.database, "ts_rehearsal_123_fresh")

    def test_unsafe_database_identifiers_are_rejected(self) -> None:
        for value in ("Public", "bad-name", "public; DROP SCHEMA public", "a" * 64):
            with self.subTest(value=value), self.assertRaises(ValueError):
                _validate_identifier(value)

    def test_error_redaction_removes_plain_and_encoded_passwords(self) -> None:
        base = _normalized_postgresql_url(
            "postgresql://tasksignal:p%40ssword@127.0.0.1:5432/tasksignal"
        )
        error = RuntimeError(
            "failed at postgresql+psycopg://tasksignal:p%40ssword@127.0.0.1/tasksignal "
            "password=p@ssword"
        )

        message = _safe_failure_message(error, base)

        self.assertNotIn("p@ssword", message)
        self.assertNotIn("p%40ssword", message)
        self.assertIn("<redacted>", message)

    def test_non_postgresql_or_non_psycopg_urls_are_rejected(self) -> None:
        for value in (
            "sqlite:////tmp/tasksignal.db",
            "postgresql+psycopg2://tasksignal:secret@localhost/tasksignal",
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                _normalized_postgresql_url(value)


if __name__ == "__main__":
    unittest.main()
