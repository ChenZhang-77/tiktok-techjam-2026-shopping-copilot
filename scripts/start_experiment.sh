#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

json_escape() {
  python3 -c 'import json, sys; print(json.dumps(sys.argv[1])[1:-1])' "$1"
}

NAME="${1:-baseline}"
SLUG="$(printf '%s' "$NAME" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//')"
if [[ -z "$SLUG" ]]; then
  SLUG="experiment"
fi

RUN_ID="$(date '+%Y-%m-%d-%H%M')-${SLUG}"
RUN_DIR="experiments/runs/${RUN_ID}"
COUNTER=2
while [[ -e "$RUN_DIR" ]]; do
  RUN_DIR="experiments/runs/${RUN_ID}-${COUNTER}"
  COUNTER=$((COUNTER + 1))
done

if [[ ! -f data/catalog.jsonl ]]; then
  echo "Missing data/catalog.jsonl. Run ./scripts/download_catalog.sh first." >&2
  exit 1
fi

PYTHON="python3"
if [[ -x .venv/bin/python ]]; then
  PYTHON=".venv/bin/python"
fi

mkdir -p "$RUN_DIR"
cp starter/agent.py "$RUN_DIR/agent_snapshot.py"

GIT_BRANCH="$(git branch --show-current 2>/dev/null || true)"
GIT_COMMIT="$(git rev-parse --short HEAD 2>/dev/null || true)"
CREATED_AT="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"

cat > "$RUN_DIR/metadata.json" <<EOF
{
  "run_id": "$(basename "$RUN_DIR")",
  "name": "$(json_escape "$NAME")",
  "created_at": "$CREATED_AT",
  "git_branch": "$(json_escape "$GIT_BRANCH")",
  "git_commit": "$(json_escape "$GIT_COMMIT")",
  "command": "$(json_escape "./scripts/start_experiment.sh $NAME")"
}
EOF

cat > "$RUN_DIR/notes.md" <<EOF
# $NAME

## Goal

## Change

## Result

See \`results.json\`.

## Notes

EOF

"$PYTHON" -m evaluator.local_evaluator --output "$RUN_DIR/results.json"

if ! curl -fsS "http://127.0.0.1:8765/api/sessions" >/dev/null 2>&1; then
  nohup "$PYTHON" visualizer/server.py >/tmp/tiktok-techjam-visualizer.log 2>&1 &
  for _ in {1..40}; do
    if curl -fsS "http://127.0.0.1:8765/api/sessions" >/dev/null 2>&1; then
      break
    fi
    sleep 0.25
  done
fi

URL="http://127.0.0.1:8765?experiment=$(basename "$RUN_DIR")"
if command -v open >/dev/null 2>&1; then
  open "$URL"
fi

echo
echo "Experiment saved to: $RUN_DIR"
echo "Visualizer URL: $URL"
