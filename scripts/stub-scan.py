#!/usr/bin/env python3
"""Language stubs / unfinished markers. Sample only. Not a full CFG."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from paths import require_inside
from walk import MAX_READ_BYTES, SOURCE_EXT, coverage_json, is_generated, readable_in_tree, redact, walk_tree

# Each: (regex, tag). Tag is the finding hint, not severity (agent decides entrypoint).
PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"raise\s+NotImplementedError"), "NotImplementedError"),
    (re.compile(r"\bunimplemented!\s*\("), "unimplemented!"),
    (re.compile(r"\btodo!\s*\("), "todo!"),
    (re.compile(r"panic\(\s*\"(?:TODO|FIXME|not implemented|unimplemented)"), "go-panic-stub"),
    (re.compile(r"throw new Error\(\s*['\"](?:TODO|FIXME|not implemented|unimplemented)"), "js-throw-stub"),
    (re.compile(r"fatalError\(\s*\"(?:TODO|FIXME|unimplemented|not implemented)"), "swift-fatalError-stub"),
    (re.compile(r"preconditionFailure\(\s*\"(?:TODO|FIXME|unimplemented)"), "swift-precondition-stub"),
    (re.compile(r"#warning\b"), "swift-warning"),
    (re.compile(r"coming soon", re.I), "coming-soon"),
    (re.compile(r"@available\(\s*\*\s*,\s*unavailable"), "swift-unavailable"),
]

MAX_HITS = 80
SKIP_NAMES = {"stub-scan.py", "self-check.py"}


def main() -> int:
    ap = argparse.ArgumentParser(description="codebase-audit stub-scan")
    ap.add_argument("workspace", type=Path)
    ap.add_argument("root", type=Path)
    args = ap.parse_args()
    _ws, root = require_inside(args.workspace, args.root)

    cover = walk_tree(root)
    hits: list[dict] = []
    by_tag: dict[str, int] = {}
    scanned = 0
    skipped_large = 0

    for p in cover.files:
        if not readable_in_tree(p, root) or is_generated(p.name):
            continue
        if p.name in SKIP_NAMES:
            continue
        if p.suffix.lower() not in SOURCE_EXT:
            continue
        scanned += 1
        try:
            if p.stat().st_size > MAX_READ_BYTES:
                skipped_large += 1
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = str(p.relative_to(root))
        for i, line in enumerate(text.splitlines(), 1):
            s = line.strip()
            if not s or s.startswith("#") and not s.startswith("#warning"):
                continue
            if re.match(r'r["\']', s) or "re.compile(" in line:
                continue
            for rx, tag in PATTERNS:
                if not rx.search(line):
                    continue
                by_tag[tag] = by_tag.get(tag, 0) + 1
                if len(hits) < MAX_HITS:
                    hits.append(
                        {
                            "path": rel,
                            "line": i,
                            "tag": tag,
                            "text": redact(s),
                        }
                    )
                break

    out = {
        "root": str(root),
        "files_scanned": scanned,
        "hit_count": sum(by_tag.values()),
        "by_tag": by_tag,
        "hits": hits,
        "truncated": sum(by_tag.values()) > MAX_HITS,
        "skipped_large": skipped_large,
        "complete_scan": skipped_large == 0 and cover.walk_complete,
        **coverage_json(cover),
        "note": "regex stubs only; empty `pass` bodies not flagged (too noisy)",
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
