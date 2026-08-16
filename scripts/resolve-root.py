#!/usr/bin/env python3
"""Resolve audit ROOT inside workspace. Exit 0 + path, 2 = outside sandbox."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from paths import inside, workspace_ok


def main() -> int:
    p = argparse.ArgumentParser(description="codebase-audit sandbox root")
    p.add_argument("workspace", type=Path, help="opened project root")
    p.add_argument("audit_path", nargs="?", default=None, help="optional subpath")
    args = p.parse_args()

    ws = args.workspace.expanduser().resolve()
    if not ws.is_dir():
        print(f"STOP sandbox: workspace not a directory: {ws}", file=sys.stderr)
        return 2
    msg = workspace_ok(ws)
    if msg:
        print(msg, file=sys.stderr)
        return 2

    if args.audit_path is None:
        root = ws
    else:
        ap = Path(args.audit_path)
        if ap.is_absolute():
            root = ap.expanduser().resolve()
        else:
            root = (ws / ap).resolve()

    if not inside(root, ws):
        print(f"STOP sandbox: {root} not inside {ws}", file=sys.stderr)
        return 2
    if not root.exists():
        print(f"STOP sandbox: path does not exist: {root}", file=sys.stderr)
        return 2
    if root.is_file():
        root = root.parent
        if not inside(root, ws):
            print(f"STOP sandbox: file parent not inside {ws}", file=sys.stderr)
            return 2

    print(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
