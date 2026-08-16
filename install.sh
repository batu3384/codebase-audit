#!/usr/bin/env bash
# Install codebase-audit into ~/.agents/skills, then link Cursor / Claude / Antigravity.
# Skip a link when that skills dir is already the agents SSOT (symlink farm).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
AGENTS="${AGENTS_DIR:-$HOME/.agents/skills}/codebase-audit"

mkdir -p "$(dirname "$AGENTS")"

if [[ -e "$AGENTS" ]]; then
  rm -rf "$AGENTS"
fi
mkdir -p "$AGENTS"
cp -R "$REPO_ROOT/." "$AGENTS/"
rm -rf "$AGENTS/.git"

PY="${PYTHON:-python3}"
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "WARN: python3 not found — skip self-check and tool links" >&2
  echo "Installed: $AGENTS"
  exit 0
fi

"$PY" "$AGENTS/scripts/install_links.py" --agents "$AGENTS"
"$PY" "$AGENTS/scripts/self-check.py"

echo "Installed: $AGENTS"
echo "Codex reads ~/.agents/skills (no extra link)."
echo "Skipped on purpose: ~/.gemini/skills (Gemini CLI), ~/.codex/skills (catalog)."
