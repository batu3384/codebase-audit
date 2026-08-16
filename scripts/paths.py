"""Shared sandbox helper for codebase-audit scripts."""
from __future__ import annotations

import sys
from pathlib import Path

POSIX_TOP = frozenset({"Users", "home", "private", "Volumes", "etc", "tmp", "var", "root"})
WIN_TOP = frozenset({"users", "windows", "program files", "program files (x86)"})


def inside(child: Path, parent: Path) -> bool:
    child = child.resolve()
    parent = parent.resolve()
    return child == parent or parent in child.parents


def is_fs_root(path: Path) -> bool:
    """True for POSIX `/`, Windows drive roots (`C:\\`), and UNC share roots."""
    try:
        p = path.expanduser().resolve()
    except OSError:
        return False
    return p.parent == p


def is_broad_workspace(ws: Path) -> bool:
    try:
        ws = ws.expanduser().resolve()
    except OSError:
        return True
    if is_fs_root(ws) or ws == Path.home():
        return True
    parent = ws.parent
    if is_fs_root(parent) and (ws.name in POSIX_TOP or ws.name.lower() in WIN_TOP):
        return True
    return False


def workspace_ok(ws: Path) -> str | None:
    try:
        ws = ws.expanduser().resolve()
    except OSError as e:
        return f"STOP sandbox: workspace unreadable: {ws} ({e})"
    if is_broad_workspace(ws):
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
