#!/usr/bin/env bash
# Install codebase-audit into ~/.agents/skills, then link Cursor / Claude / Antigravity.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
PY="${PYTHON:-python3}"
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "ERROR: python3 not found (need 3.10+)" >&2
  exit 1
fi

args=(--repo "$REPO_ROOT")
if [[ -n "${AGENTS_DIR:-}" ]]; then
  args+=(--agents-dir "$AGENTS_DIR")
fi
exec "$PY" "$REPO_ROOT/scripts/install.py" "${args[@]}"
