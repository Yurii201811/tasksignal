from importlib.metadata import PackageNotFoundError

from app.core import version as version_module


def test_source_checkout_version_fallback_matches_alpha_candidate(monkeypatch) -> None:
    def missing_distribution(_distribution: str) -> str:
        raise PackageNotFoundError

    monkeypatch.setattr(version_module, "version", missing_distribution)

    assert version_module.installed_tasksignal_version() == "1.0.0a1"
