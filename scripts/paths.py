"""Shared sandbox helper for codebase-audit scripts."""
from __future__ import annotations

import sys
from pathlib import Path


def inside(child: Path, parent: Path) -> bool:
    child = child.resolve()
    parent = parent.resolve()
    return child == parent or parent in child.parents


def workspace_ok(ws: Path) -> str | None:
    ws = ws.resolve()
    if ws == Path("/") or ws == Path.home():
        return f"STOP sandbox: workspace too broad: {ws}"
    if ws.parent == Path("/") and ws.name in {"Users", "home", "private", "Volumes"}:
        return f"STOP sandbox: workspace too broad: {ws}"
    return None


def require_inside(workspace: Path, root: Path) -> tuple[Path, Path]:
    ws = workspace.expanduser().resolve()
    r = root.expanduser().resolve()
    if not ws.is_dir():
        print(f"STOP sandbox: workspace not a directory: {ws}", file=sys.stderr)
        sys.exit(2)
    msg = workspace_ok(ws)
    if msg:
        print(msg, file=sys.stderr)
        sys.exit(2)
    if not r.exists():
        print(f"STOP sandbox: path does not exist: {r}", file=sys.stderr)
        sys.exit(2)
    if r.is_file():
        r = r.parent
    if not inside(r, ws):
        print(f"STOP sandbox: {r} not inside {ws}", file=sys.stderr)
        sys.exit(2)
    if not r.is_dir():
        print(f"STOP sandbox: root not a directory: {r}", file=sys.stderr)
        sys.exit(2)
    return ws, r
