#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_DIR="$ROOT_DIR/data/fixtures"
TARGET_DIR="$ROOT_DIR/apps/api/data/fixtures"

if [[ ! -d "$SOURCE_DIR" ]]; then
  echo "Fixture source is missing: $SOURCE_DIR" >&2
  exit 1
fi

mkdir -p "$TARGET_DIR"
rsync -a --delete "$SOURCE_DIR/" "$TARGET_DIR/"

echo "Prepared the isolated Vercel API bundle at $ROOT_DIR/apps/api"
