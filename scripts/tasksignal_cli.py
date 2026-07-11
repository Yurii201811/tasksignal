#!/usr/bin/env python3
"""Source-checkout shim for the installable ``tasksignal`` command."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
