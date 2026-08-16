#!/usr/bin/env python3
"""One-shot static audit JSON. Optional --run. Exit 2 if resolve/sandbox fails."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
PY = sys.executable

ORDER = (
    "inventory.py",
    "docs-check.py",
    "promises.py",
    "import-sample.py",
    "stub-scan.py",
    "runtime-check.py",
)


def run_one(name: str, args: list[str]) -> dict:
    r = subprocess.run(
        [PY, str(SCRIPTS / name), *args],
        capture_output=True,
        text=True,
        cwd=str(SCRIPTS),
    )
    if r.returncode != 0:
        return {
            "error": (r.stderr or r.stdout or "").strip()[:2000],
            "exit": r.returncode,
        }
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"error": "invalid json", "exit": r.returncode, "stdout": r.stdout[:500]}


def main() -> int:
    ap = argparse.ArgumentParser(description="codebase-audit bundle")
    ap.add_argument("workspace", type=Path)
    ap.add_argument("audit_path", nargs="?", default=None)
    ap.add_argument("--run", action="store_true")
    args = ap.parse_args()

    resolve = [PY, str(SCRIPTS / "resolve-root.py"), str(args.workspace)]
    if args.audit_path:
        resolve.append(str(args.audit_path))
    r = subprocess.run(resolve, capture_output=True, text=True, cwd=str(SCRIPTS))
    if r.returncode != 0:
        sys.stderr.write(r.stderr or r.stdout or "resolve-root failed\n")
        return 2
    root = r.stdout.strip()
    pair = [str(args.workspace), root]
    out: dict = {"workspace": str(Path(args.workspace).resolve()), "root": root, "mode": "run" if args.run else "static"}
    for name in ORDER:
        extra = ["--run"] if name == "runtime-check.py" and args.run else []
        out[name.replace(".py", "")] = run_one(name, pair + extra)
        blob = out[name.replace(".py", "")]
        if isinstance(blob, dict) and blob.get("exit") == 2:
            print(json.dumps(out, indent=2))
            return 2
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
