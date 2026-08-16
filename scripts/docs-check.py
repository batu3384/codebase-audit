#!/usr/bin/env python3
"""Broken in-repo markdown links + promised backtick paths. No network."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from paths import require_inside
from walk import MAX_READ_BYTES, coverage_json, is_generated, readable_in_tree, walk_tree

MD_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
BACKTICK_PATH = re.compile(
    r"`((?:[A-Za-z0-9_.-]+/)+\.?[A-Za-z0-9_.-]+\.[A-Za-z0-9]+)`"
)
SKIP_LINK = re.compile(r"^(https?://|mailto:|tel:|#|\{)")
PLACEHOLDER_PATH = re.compile(r"YYYY|MM-DD|<[^>]+>|\{[^}]+\}")


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

    cover = walk_tree(root)
    broken: list[dict] = []
    promised_missing: list[dict] = []
    md_seen = 0
    md_scanned = 0
    link_count = 0
    skipped_large = 0
    unreadable = 0
    md_cap = False
    promised_cap = False

    for p in cover.files:
        if not readable_in_tree(p, root) or is_generated(p.name):
            continue
        if not (p.name.startswith("README") or p.suffix.lower() == ".md"):
            continue
        md_seen += 1
        if md_seen > 200:
            md_cap = True
            break
        try:
            if p.stat().st_size > MAX_READ_BYTES:
                skipped_large += 1
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            unreadable += 1
            continue
        md_scanned += 1
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
                if PLACEHOLDER_PATH.search(spec):
                    continue
                if not (root / spec).exists():
                    promised_missing.append({"from": rel, "path": spec})
                    if len(promised_missing) >= 20:
                        promised_cap = True
                        break

    promised_complete = (
        (not promised_cap)
        and skipped_large == 0
        and unreadable == 0
        and cover.walk_complete
    )
    out = {
        "root": str(root),
        "md_files_seen": md_seen,
        "md_files_scanned": md_scanned,
        "link_count": link_count,
        "broken_links": broken,
        "promised_missing": promised_missing,
        "promised_missing_count": len(promised_missing),
        "promised_missing_complete": promised_complete,
        "skipped_large": skipped_large,
        "unreadable": unreadable,
        "truncated": md_cap or len(broken) >= 40 or promised_cap or skipped_large > 0 or not cover.walk_complete,
        **coverage_json(cover),
        "note": "in-repo relative links + README backtick paths; no NLP feature list",
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
