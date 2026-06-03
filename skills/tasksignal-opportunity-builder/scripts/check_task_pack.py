#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

REQUIRED_SECTIONS = [
    "## Objective",
    "## Suggested MVP",
    "## Evidence Score",
    "## Evidence",
    "## Acceptance Criteria",
    "## Privacy And Safety Constraints",
    "## Recommended Codex Flow",
]


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: check_task_pack.py path/to/task-pack.md", file=sys.stderr)
        return 2

    path = Path(sys.argv[1])
    if not path.exists() or not path.is_file():
        print(f"not found: {path}", file=sys.stderr)
        return 2

    text = path.read_text(encoding="utf-8")
    missing = [section for section in REQUIRED_SECTIONS if section not in text]
    if missing:
        print("missing required sections:")
        for section in missing:
            print(f"- {section}")
        return 1

    print("TaskSignal task pack structure looks usable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
