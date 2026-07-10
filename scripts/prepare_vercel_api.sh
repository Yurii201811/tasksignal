#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_DIR="$ROOT_DIR/data/fixtures"
API_DIR="$ROOT_DIR/apps/api"
TARGET_DIR="$ROOT_DIR/.vercel-api"

if [[ ! -d "$SOURCE_DIR" ]]; then
  echo "Fixture source is missing: $SOURCE_DIR" >&2
  exit 1
fi

rm -rf "$TARGET_DIR"
mkdir -p "$TARGET_DIR/app" "$TARGET_DIR/data/fixtures"
rsync -a --delete --exclude '__pycache__/' --exclude '*.pyc' \
  "$API_DIR/app/" "$TARGET_DIR/app/"
rsync -a --delete "$SOURCE_DIR/" "$TARGET_DIR/data/fixtures/"

for file in pyproject.toml uv.lock vercel.json .python-version .vercelignore; do
  rsync -a "$API_DIR/$file" "$TARGET_DIR/$file"
done

if [[ -f "$API_DIR/.vercel/project.json" ]]; then
  mkdir -p "$TARGET_DIR/.vercel"
  rsync -a "$API_DIR/.vercel/project.json" "$TARGET_DIR/.vercel/project.json"
fi

echo "Prepared the isolated Vercel API bundle at $TARGET_DIR"
