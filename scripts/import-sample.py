#!/usr/bin/env python3
"""Bounded import-edge sample. Cycles/unresolved only inside the sample. Not a full call graph."""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

from paths import require_inside
from walk import (
    MAX_READ_BYTES,
    is_entrypoint,
    is_generated,
    is_test_file,
    resolved_is_secret,
    walk_files,
)

# Relative / same-tree imports only. Bare `import UIKit` / `import os` skipped.
REL_FROM = re.compile(
    r"""(?:from|import)\s+['\"](\.\.?/[^'\"]+)['\"]"""
)
REL_REQUIRE = re.compile(r"""require\(\s*['\"](\.\.?/[^'\"]+)['\"]""")
REL_DYNAMIC = re.compile(r"""import\(\s*['\"](\.\.?/[^'\"]+)['\"]""")
PY_FROM_REL = re.compile(r"^from\s+(\.+)([\w.]*)\s+import\s+(.+)")

def dest_kind(dest: Path | None, spec: str, root: Path, *, dir_ok: bool = False) -> tuple[str, str]:
    if dest is None:
        return spec, "outside"
    try:
        dest_rel = str(dest.resolve().relative_to(root.resolve()))
    except ValueError:
        return spec, "outside"
    if dest.is_file() or (dir_ok and dest.is_dir()):
        return dest_rel, "ok"
    return dest_rel, "missing"


JS_EXT = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts"}
PY_EXT = {".py"}
GO_EXT = {".go"}

MAX_PARSE_FILES = 2000
SAMPLE_EDGES = 80

UI_MARK = ("/views/", "/view/", "/ui/", "/components/", "/screens/", "/swiftui/")
DATA_MARK = ("/models/", "/db/", "/persistence/", "/coredata/", "/repository/", "/data/")


def resolve_js(src: Path, spec: str, root: Path) -> Path | None:
    raw = spec.split("?", 1)[0].split("#", 1)[0]
    base = (src.parent / raw).resolve()
    try:
        base.relative_to(root.resolve())
    except ValueError:
        return None
    candidates = [base]
    if not base.suffix:
        for ext in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts"):
            candidates.append(Path(str(base) + ext))
        candidates.append(base / "index.ts")
        candidates.append(base / "index.js")
        candidates.append(base / "index.tsx")
    for c in candidates:
        if c.is_file():
            return c
    return base


def resolve_py_rel(src: Path, dots: str, rest: str, names: str, root: Path) -> list[Path]:
    up = len(dots)
    cur = src.parent
    for _ in range(up - 1):
        cur = cur.parent
    out: list[Path] = []
    parts = [p for p in rest.split(".") if p]
    if parts:
        target = cur.joinpath(*parts)
        out.extend((target.with_suffix(".py"), target / "__init__.py"))
    else:
        for raw in names.split(","):
            n = raw.strip().split(" as ", 1)[0].strip()
            if not n or n == "(" or n.startswith("("):
                continue
            n = n.strip("()")
            if not re.match(r"^\w+$", n):
                continue
            out.append(cur / f"{n}.py")
            out.append(cur / n / "__init__.py")
    filtered: list[Path] = []
    for target in out:
        try:
            target.resolve().relative_to(root.resolve())
        except ValueError:
            continue
        filtered.append(target)
    return filtered


def file_edges(path: Path, root: Path) -> list[tuple[str, str, int, str]]:
    rel = str(path.relative_to(root))
    ext = path.suffix.lower()
    try:
        if path.stat().st_size > MAX_READ_BYTES:
            return []
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    out: list[tuple[str, str, int, str]] = []
    lines = text.splitlines()
    if ext in JS_EXT:
        for i, line in enumerate(lines, 1):
            for spec in REL_FROM.findall(line) + REL_REQUIRE.findall(line) + REL_DYNAMIC.findall(line):
                dest = resolve_js(path, spec, root)
                dest_rel, kind = dest_kind(dest, spec, root)
                out.append((rel, dest_rel, i, kind))
    elif ext in PY_EXT:
        for i, line in enumerate(lines, 1):
            m = PY_FROM_REL.match(line)
            if not m:
                continue
            spec = m.group(2) or m.group(3).split(",")[0].strip()
            cands = resolve_py_rel(path, m.group(1), m.group(2), m.group(3), root)
            if not cands:
                out.append((rel, spec, i, "outside"))
                continue
            hit = next((c for c in cands if c.is_file()), None)
            dest = hit or cands[0]
            dest_rel, kind = dest_kind(dest, spec, root)
            out.append((rel, dest_rel, i, kind))
    elif ext in GO_EXT:
        for i, line in enumerate(lines, 1):
            for spec in re.findall(r'"(\.\.?/[^"]+)"', line):
                dest = (path.parent / spec).resolve()
                if dest.with_suffix(".go").is_file():
                    dest = dest.with_suffix(".go")
                dest_rel, kind = dest_kind(dest, spec, root, dir_ok=True)
                out.append((rel, dest_rel, i, kind))
    return out


def cycles_in(edges: list[tuple[str, str, int, str]]) -> list[list[str]]:
    graph: dict[str, set[str]] = defaultdict(set)
    for frm, to, _i, kind in edges:
        if kind != "ok":
            continue
        if frm == to:
            continue
        graph[frm].add(to)
    found: list[list[str]] = []
    visiting: set[str] = set()
    seen: set[str] = set()
    stack: list[str] = []

    def dfs(n: str) -> None:
        if n in seen or len(found) >= 8:
            return
        visiting.add(n)
        stack.append(n)
        for nxt in graph.get(n, ()):
            if nxt in visiting:
                i = stack.index(nxt)
                found.append(stack[i:] + [nxt])
            else:
                dfs(nxt)
        stack.pop()
        visiting.discard(n)
        seen.add(n)

    for node in list(graph):
        dfs(node)
    # unique by frozenset of nodes
    uniq = []
    seen_c: set[frozenset[str]] = set()
    for c in found:
        key = frozenset(c)
        if key in seen_c:
            continue
        seen_c.add(key)
        uniq.append(c)
    return uniq[:8]


def folder_kind(rel: str) -> str | None:
    p = "/" + rel.replace("\\", "/").lower() + "/"
    if any(m in p for m in UI_MARK):
        return "ui"
    if any(m in p for m in DATA_MARK):
        return "data"
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="codebase-audit import sample")
    ap.add_argument("workspace", type=Path)
    ap.add_argument("root", type=Path)
    args = ap.parse_args()
    _ws, root = require_inside(args.workspace, args.root)

    parse_ext = JS_EXT | PY_EXT | GO_EXT
    edges: list[tuple[str, str, int, str]] = []
    srcs: list[str] = []
    parsed = 0
    truncated = False
    for p in walk_files(root):
        if resolved_is_secret(p, root):
            continue
        if p.suffix.lower() not in parse_ext or is_generated(p.name):
            continue
        parsed += 1
        if parsed > MAX_PARSE_FILES:
            truncated = True
            break
        rel = str(p.relative_to(root))
        srcs.append(rel)
        edges.extend(file_edges(p, root))

    missing = [
        {"from": a, "to": b, "line": ln}
        for a, b, ln, k in edges
        if k == "missing"
    ]
    sample = [
        {"from": a, "to": b, "line": ln, "kind": k}
        for a, b, ln, k in edges[:SAMPLE_EDGES]
    ]
    cyc = cycles_in(edges)
    dests = {b for _a, b, _i, k in edges if k == "ok"}
    files = set(srcs) | dests
    orphans: list[str] = []
    layer_hints: list[dict] = []
    hubs: list[dict] = []
    if not truncated:
        for rel in srcs:
            name = Path(rel).name
            if is_entrypoint(rel, name) or is_test_file(rel, name):
                continue
            if name == "__init__.py":
                continue
            if rel in dests:
                continue
            orphans.append(rel)
            if len(orphans) >= 40:
                break
        for a, b, ln, k in edges:
            if k != "ok":
                continue
            if folder_kind(a) == "ui" and folder_kind(b) == "data":
                layer_hints.append({"from": a, "to": b, "line": ln})
                if len(layer_hints) >= 20:
                    break
        in_count: dict[str, int] = defaultdict(int)
        for _a, b, _i, k in edges:
            if k == "ok":
                in_count[b] += 1
        hubs = [
            {"path": path, "in_edges": n}
            for path, n in sorted(in_count.items(), key=lambda x: -x[1])[:5]
            if n >= 3
        ]
    out = {
        "root": str(root),
        "n": len(edges),
        "files": len(files),
        "sample": sample,
        "unresolved": missing[:40],
        "cycles": cyc,
        "orphans": orphans,
        "orphans_complete": not truncated,
        "orphan_scope": "js/py/go relative only; Swift modules excluded",
        "layer_hints": layer_hints,
        "hubs": hubs,
        "engine": "walk-parse",
        "complete_graph": False,
        "note": "relative imports only among js/py/go; do not claim repo-wide acyclic",
        "truncated": truncated,
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
