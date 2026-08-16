#!/usr/bin/env bash
# Install codebase-audit into ~/.agents/skills and link ~/.cursor/skills (macOS/Linux).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
AGENTS="${AGENTS_DIR:-$HOME/.agents/skills}/codebase-audit"
CURSOR="${CURSOR_SKILLS_DIR:-$HOME/.cursor/skills}/codebase-audit"

mkdir -p "$(dirname "$AGENTS")" "$(dirname "$CURSOR")"

if [[ -e "$AGENTS" ]]; then
  rm -rf "$AGENTS"
fi
mkdir -p "$AGENTS"
cp -R "$REPO_ROOT/." "$AGENTS/"
rm -rf "$AGENTS/.git"

if [[ -e "$CURSOR" ]]; then
  rm -rf "$CURSOR"
fi
ln -s "$AGENTS" "$CURSOR"

if command -v python3 >/dev/null 2>&1; then
  python3 "$AGENTS/scripts/self-check.py"
else
  echo "WARN: python3 not found — skip self-check"
fi

echo "Installed: $AGENTS"
echo "Cursor:    $CURSOR"
