#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f data/catalog.jsonl ]]; then
  echo "Missing data/catalog.jsonl. Run ./scripts/download_catalog.sh first." >&2
  exit 1
fi

python3 -m evaluator.local_evaluator
