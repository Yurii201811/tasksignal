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


def required_section_spans(text: str) -> dict[str, tuple[int, int]]:
    lines = text.splitlines()
    headings: list[tuple[str, int]] = [
        (line.strip(), index)
        for index, line in enumerate(lines)
        if line.strip().startswith("## ")
    ]

    spans: dict[str, tuple[int, int]] = {}
    for index, (heading, line_index) in enumerate(headings):
        if heading not in REQUIRED_SECTIONS or heading in spans:
            continue
        next_heading_index = headings[index + 1][1] if index + 1 < len(headings) else len(lines)
        spans[heading] = (line_index, next_heading_index)
    return spans


def missing_required_sections(text: str) -> list[str]:
    spans = required_section_spans(text)
    return [section for section in REQUIRED_SECTIONS if section not in spans]


def misordered_required_sections(text: str) -> list[str]:
    spans = required_section_spans(text)
    previous_line = -1
    misordered: list[str] = []
    for section in REQUIRED_SECTIONS:
        if section not in spans:
            continue
        line_index = spans[section][0]
        if line_index < previous_line:
            misordered.append(section)
        previous_line = max(previous_line, line_index)
    return misordered


def empty_required_sections(text: str) -> list[str]:
    lines = text.splitlines()
    spans = required_section_spans(text)
    empty: list[str] = []
    for section in REQUIRED_SECTIONS:
        if section not in spans:
            continue
        start, end = spans[section]
        content_lines = lines[start + 1 : end]
        if not any(line.strip() for line in content_lines):
            empty.append(section)
    return empty


def task_pack_structure_errors(text: str) -> list[str]:
    errors: list[str] = []
    missing = missing_required_sections(text)
    if missing:
        errors.append("missing required section(s): " + ", ".join(missing))

    misordered = misordered_required_sections(text)
    if misordered:
        errors.append("misordered required section(s): " + ", ".join(misordered))

    empty = empty_required_sections(text)
    if empty:
        errors.append("empty required section(s): " + ", ".join(empty))

    return errors


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: check_task_pack.py path/to/task-pack.md", file=sys.stderr)
        return 2

    path = Path(sys.argv[1])
    if not path.exists() or not path.is_file():
        print(f"not found: {path}", file=sys.stderr)
        return 2

    text = path.read_text(encoding="utf-8")
    errors = task_pack_structure_errors(text)
    if errors:
        print("task pack structure errors:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("TaskSignal task pack structure looks usable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
