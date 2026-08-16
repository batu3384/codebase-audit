#!/usr/bin/env python3
"""Broken in-repo markdown links + promised backtick paths. No network."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from paths import require_inside
from walk import MAX_READ_BYTES, is_generated, resolved_is_secret, walk_files

MD_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
BACKTICK_PATH = re.compile(
    r"`((?:[A-Za-z0-9_.-]+/)+\.?[A-Za-z0-9_.-]+\.[A-Za-z0-9]+)`"
)
SKIP_LINK = re.compile(r"^(https?://|mailto:|tel:|#|\{)")


def clean_href(raw: str) -> str:
    href = raw.strip().split()[0].strip("<>")
    href = href.split("#", 1)[0]
    href = href.split("?", 1)[0]
    return href


def main() -> int:
    ap = argparse.ArgumentParser(description="codebase-audit docs-check")
    ap.add_argument("workspace", type=Path)
    ap.add_argument("root", type=Path)
    args = ap.parse_args()
    _ws, root = require_inside(args.workspace, args.root)

    broken: list[dict] = []
    promised_missing: list[dict] = []
    md_count = 0
    link_count = 0

    for p in walk_files(root):
        if resolved_is_secret(p, root) or is_generated(p.name):
            continue
        if not (p.name.startswith("README") or p.suffix.lower() == ".md"):
            continue
        md_count += 1
        if md_count > 200:
            break
        try:
            if p.stat().st_size > MAX_READ_BYTES:
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = str(p.relative_to(root))
        for m in MD_LINK.finditer(text):
            raw = m.group(1).strip()
            if raw.startswith("<") and "://" not in raw:
                continue
            href = clean_href(raw)
            if not href or SKIP_LINK.search(href):
                continue
            if href.startswith("//") or href.startswith("http"):
                continue
            link_count += 1
            target = (p.parent / href).resolve()
            try:
                target.relative_to(root.resolve())
            except ValueError:
                continue
            if not target.exists():
                broken.append({"from": rel, "href": href})
                if len(broken) >= 40:
                    break
        if len(broken) >= 40:
            break
        if p.name.upper().startswith("README"):
            for m in BACKTICK_PATH.finditer(text):
                spec = m.group(1)
                if "://" in spec or spec.startswith("www."):
                    continue
                if not (root / spec).exists():
                    promised_missing.append({"from": rel, "path": spec})
                    if len(promised_missing) >= 20:
                        break

    out = {
        "root": str(root),
        "md_files_scanned": md_count,
        "link_count": link_count,
        "broken_links": broken,
        "promised_missing": promised_missing,
        "truncated": md_count > 200 or len(broken) >= 40,
        "note": "in-repo relative links + README backtick paths; no NLP feature list",
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
