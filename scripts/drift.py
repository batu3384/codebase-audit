#!/usr/bin/env python3
"""Compare this-run sidecar JSON to the previous dated sidecar.

Identity is fingerprint = severity|category|path without :line.
CA-NNN is per-run and must not be compared.
"""
from __future__ import annotations

import argparse
import json
import re
import stat
import sys
from pathlib import Path

from paths import inside, require_inside

SCHEMA = 1
SKILL = "codebase-audit"
LINE_SUFFIX = re.compile(r":\d+$")
STEM = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:-(\d{4}))?$")
SEVERITIES = {"Critical", "Major", "Minor", "Trivial", "Info"}
VERDICTS = {"BLOCK", "CONCERNS", "CLEAN", "incomplete"}
CAP = 40


def norm_path(raw: str) -> str:
    p = (raw or "").replace("\\", "/").strip()
    return LINE_SUFFIX.sub("", p)


def fingerprint(item: dict) -> str:
    sev = str(item.get("severity") or "")
    cat = str(item.get("category") or "")
    path = norm_path(str(item.get("path") or ""))
    return f"{sev}|{cat}|{path}"


def stem_key(path: Path) -> tuple[str, int] | None:
    m = STEM.fullmatch(path.stem)
    if not m:
        return None
    hhmm = m.group(2)
    return (m.group(1), int(hhmm) if hhmm else 0)


def public_item(item: dict) -> dict:
    return {
        "id": item["id"],
        "severity": item["severity"],
        "category": item["category"],
        "path": item["path"],
        "fingerprint": item["fingerprint"],
    }


def is_regular_file(path: Path) -> bool:
    try:
        st = path.lstat()
    except OSError:
        return False
    return stat.S_ISREG(st.st_mode)


def load_sidecar(path: Path) -> dict:
    if not is_regular_file(path):
        raise ValueError("sidecar must be a regular file")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ValueError(f"sidecar unreadable: {e}") from e
    if not isinstance(data, dict):
        raise ValueError("sidecar must be an object")
    if data.get("schema") != SCHEMA:
        raise ValueError(f"schema must be {SCHEMA}")
    if data.get("skill") != SKILL:
        raise ValueError("skill must be codebase-audit")
    if data.get("verdict") not in VERDICTS:
        raise ValueError("verdict must be BLOCK|CONCERNS|CLEAN|incomplete")
    date = str(data.get("date") or "")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        raise ValueError("date must be YYYY-MM-DD")
    key = stem_key(path)
    if key is None:
        raise ValueError("sidecar name must be YYYY-MM-DD.json or YYYY-MM-DD-HHMM.json")
    if date != key[0]:
        raise ValueError("date must match filename YYYY-MM-DD")
    root = str(data.get("root") or "").strip()
    if not root:
        raise ValueError("root required")
    data["root"] = root
    findings = data.get("findings")
    if not isinstance(findings, list):
        raise ValueError("findings must be a list")
    clean: list[dict] = []
    seen: set[str] = set()
    for item in findings:
        if not isinstance(item, dict):
            raise ValueError("finding must be an object")
        ident = str(item.get("id") or "")
        sev = str(item.get("severity") or "")
        cat = str(item.get("category") or "").strip()
        path = str(item.get("path") or "").strip()
        if not ident.startswith("CA-") or sev not in SEVERITIES or not cat or not path:
            raise ValueError("finding needs CA-* id, severity, category, path")
        fp = fingerprint({"severity": sev, "category": cat, "path": path})
        if fp in seen:
            continue
        seen.add(fp)
        clean.append(
            {
                "id": ident,
                "severity": sev,
                "category": cat,
                "path": path,
                "fingerprint": fp,
            }
        )
    data["findings"] = clean
    return data


def older_sidecars(folder: Path, current: Path) -> list[Path]:
    cur_key = stem_key(current)
    if cur_key is None:
        raise ValueError("sidecar name must be YYYY-MM-DD.json or YYYY-MM-DD-HHMM.json")
    rows: list[tuple[tuple[str, int], Path]] = []
    cur_res = current.resolve()
    for p in folder.glob("*.json"):
        if not is_regular_file(p) or p.resolve() == cur_res:
            continue
        key = stem_key(p)
        if key is None or key >= cur_key:
            continue
        rows.append((key, p))
    rows.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in rows]


def canon_root(raw: str) -> str:
    return str(Path(raw).expanduser().resolve())


def pick_previous(
    folder: Path, current: Path, cur_root: str
) -> tuple[Path | None, dict | None, list[str], list[str]]:
    skipped: list[str] = []
    skipped_root: list[str] = []
    want = canon_root(cur_root)
    for p in older_sidecars(folder, current):
        try:
            prev = load_sidecar(p)
        except ValueError:
            skipped.append(p.name)
            if len(skipped) >= 8:
                break
            continue
        if canon_root(str(prev.get("root") or "")) != want:
            skipped_root.append(p.name)
            continue
        return p, prev, skipped, skipped_root
    return None, None, skipped, skipped_root


def main() -> int:
    ap = argparse.ArgumentParser(description="codebase-audit drift")
    ap.add_argument("workspace", type=Path)
    ap.add_argument("sidecar", type=Path, help="this run's YYYY-MM-DD.json")
    args = ap.parse_args()
    ws, _root = require_inside(args.workspace, args.workspace)
    sidecar = args.sidecar.expanduser().resolve()
    if not is_regular_file(args.sidecar.expanduser()):
        print(f"STOP sidecar missing or not a regular file: {args.sidecar}", file=sys.stderr)
        return 2
    if not sidecar.is_file():
        print(f"STOP sidecar missing: {sidecar}", file=sys.stderr)
        return 2
    if not inside(sidecar, ws):
        print(f"STOP sandbox: {sidecar} not inside {ws}", file=sys.stderr)
        return 2
    if stem_key(sidecar) is None:
        print("STOP sidecar name must be YYYY-MM-DD.json or YYYY-MM-DD-HHMM.json", file=sys.stderr)
        return 2
    try:
        cur = load_sidecar(sidecar)
        prev_path, prev, skipped, skipped_root = pick_previous(
            sidecar.parent, sidecar, cur["root"]
        )
    except ValueError as e:
        print(f"STOP sidecar: {e}", file=sys.stderr)
        return 2

    prev_by_fp: dict[str, dict] = {}
    if prev:
        for item in prev["findings"]:
            prev_by_fp[item["fingerprint"]] = item
    cur_by_fp = {item["fingerprint"]: item for item in cur["findings"]}
    cur_fps = set(cur_by_fp)
    prev_fps = set(prev_by_fp)
    added_fps = sorted(cur_fps - prev_fps)
    removed_fps = sorted(prev_fps - cur_fps)
    still_fps = sorted(cur_fps & prev_fps)

    out = {
        "schema": SCHEMA,
        "current": sidecar.name,
        "previous": prev_path.name if prev_path else None,
        "skipped_corrupt": skipped[:8],
        "skipped_root": skipped_root[:8],
        "added": [public_item(cur_by_fp[fp]) for fp in added_fps[:CAP]],
        "removed": [public_item(prev_by_fp[fp]) for fp in removed_fps[:CAP]],
        "still": [public_item(cur_by_fp[fp]) for fp in still_fps[:CAP]],
        "counts": {
            "added": len(added_fps),
            "removed": len(removed_fps),
            "still": len(still_fps),
        },
        "note": "fingerprint = severity|category|path without :line; CA-NNN is per-run",
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
