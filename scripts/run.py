#!/usr/bin/env python3
"""One-shot static audit JSON. Optional --run. Exit 2 if resolve/sandbox/schema fails."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from schema import validate_child

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


def run_one(name: str, args: list[str], timeout: int) -> dict:
    try:
        r = subprocess.run(
            [PY, str(SCRIPTS / name), *args],
            capture_output=True,
            text=True,
            cwd=str(SCRIPTS),
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"error": "timeout", "exit": 124}
    if r.returncode != 0:
        return {
            "error": (r.stderr or r.stdout or "").strip()[:2000],
            "exit": r.returncode,
        }
    try:
        blob = json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"error": "invalid json", "exit": r.returncode, "stdout": r.stdout[:500]}
    if not isinstance(blob, dict):
        return {"error": "result is not an object", "exit": 2}
    return blob


def main() -> int:
    ap = argparse.ArgumentParser(description="codebase-audit bundle")
    ap.add_argument("workspace", type=Path)
    ap.add_argument("audit_path", nargs="?", default=None)
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--timeout", type=int, default=180)
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
    out: dict = {
        "workspace": str(Path(args.workspace).resolve()),
        "root": root,
        "mode": "run" if args.run else "static",
    }
    for name in ORDER:
        extra = ["--run"] if name == "runtime-check.py" and args.run else []
        stem = name.replace(".py", "")
        blob = run_one(name, pair + extra, args.timeout)
        out[stem] = blob
        err = validate_child(stem, blob)
        if err:
            out["incomplete"] = True
            out["incomplete_reason"] = err
            print(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
            return 2
    print(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
