from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version


def installed_tasksignal_version() -> str:
    """Return the packaged version while supporting legacy distribution names."""

    for distribution in ("tasksignal", "tasksignal-app", "tasksignal-api"):
        try:
            return version(distribution)
        except PackageNotFoundError:
            continue
    return "1.0.0a1"


TASKSIGNAL_VERSION = installed_tasksignal_version()
