from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version


def installed_tasksignal_version() -> str:
    """Return the packaged version while supporting the v0.2 distribution name."""

    for distribution in ("tasksignal", "tasksignal-app", "tasksignal-api"):
        try:
            return version(distribution)
        except PackageNotFoundError:
            continue
    return "0.2.0"


TASKSIGNAL_VERSION = installed_tasksignal_version()
