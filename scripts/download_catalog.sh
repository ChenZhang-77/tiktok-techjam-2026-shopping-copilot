#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="$ROOT_DIR/data"
CATALOG_GZ="$DATA_DIR/catalog.jsonl.gz"
CATALOG_JSONL="$DATA_DIR/catalog.jsonl"
SUMS_FILE="$DATA_DIR/SHA256SUMS"

RELEASE_BASE="https://github.com/TechJam2026/techjam-conversational-search/releases/download/participant-kit"

mkdir -p "$DATA_DIR"

if [[ ! -f "$CATALOG_GZ" ]]; then
  echo "Downloading catalog.jsonl.gz..."
  curl -L "$RELEASE_BASE/catalog.jsonl.gz" -o "$CATALOG_GZ"
else
  echo "Using existing $CATALOG_GZ"
fi

if [[ ! -f "$SUMS_FILE" ]]; then
  echo "Downloading SHA256SUMS..."
  curl -L "$RELEASE_BASE/SHA256SUMS" -o "$SUMS_FILE"
fi

echo "Verifying checksum..."
(
  cd "$DATA_DIR"
  LC_ALL=C LANG=C shasum -a 256 -c SHA256SUMS --ignore-missing
)

if [[ ! -f "$CATALOG_JSONL" ]]; then
  echo "Decompressing catalog..."
  gzip -dk "$CATALOG_GZ"
else
  echo "Using existing $CATALOG_JSONL"
fi

echo "Catalog ready at $CATALOG_JSONL"
