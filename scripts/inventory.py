#!/usr/bin/env python3
"""Pruned inventory. Never reads secret-file bodies (name or symlink target)."""
from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from pathlib import Path

from paths import require_inside
from walk import (
    LANG_FROM_EXT,
    SOURCE_EXT,
    find_xcode_bundles,
    is_entrypoint,
    is_generated,
    is_test_file,
    line_count,
    nearest_package,
    resolved_is_secret,
    scan_todo,
    test_pair_stem,
    todo_scanable,
    walk_files,
)


def git_probe(ws: Path) -> bool:
    try:
        probe = subprocess.run(
            ["git", "-C", str(ws), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    return probe.returncode == 0 and probe.stdout.strip() == "true"


def git_status(ws: Path, path: Path, *, has_git: bool) -> str:
    if not has_git:
        return "no-git"
    try:
        rel = str(path.resolve().relative_to(ws.resolve()))
    except ValueError:
        return "outside"
    try:
        ign = subprocess.run(
            ["git", "-C", str(ws), "check-ignore", "-q", "--", rel],
            capture_output=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return "no-git"
    if ign.returncode == 0:
        return "ignored"
    try:
        tracked = subprocess.run(
            ["git", "-C", str(ws), "ls-files", "--error-unmatch", "--", rel],
            capture_output=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return "no-git"
    if tracked.returncode == 0:
        return "tracked"
    return "untracked"


def detect_packages(root: Path) -> list[str]:
    markers = []
    for name in (
        "pnpm-workspace.yaml",
        "lerna.json",
        "nx.json",
        "go.work",
        "Cargo.toml",
        "package.json",
        "Package.swift",
        "pubspec.yaml",
        "settings.gradle",
        "settings.gradle.kts",
        "Podfile",
        "pyproject.toml",
    ):
        if (root / name).is_file():
            markers.append(name)
    return markers


def main() -> int:
    ap = argparse.ArgumentParser(description="codebase-audit inventory")
    ap.add_argument("workspace", type=Path)
    ap.add_argument("root", type=Path)
    args = ap.parse_args()
    ws, root = require_inside(args.workspace, args.root)

    has_git = git_probe(ws)
    files = walk_files(root)
    secrets: list[dict] = []
    docs: list[str] = []
    sources: list[tuple[int, str, str]] = []
    todo_count = 0
    todo_samples: list[str] = []
    todo_per_file: Counter[str] = Counter()
    entrypoints: list[str] = []
    lang_counts: Counter[str] = Counter()
    test_kinds: Counter[str] = Counter()
    test_files: list[str] = []

    for p in files:
        rel = str(p.relative_to(root))
        name = p.name
        secret = resolved_is_secret(p, root)
        if secret:
            secrets.append({"path": rel, "git": git_status(ws, p, has_git=has_git)})
            continue
        if name.startswith("README") or name.endswith(".md"):
            docs.append(rel)
        if is_entrypoint(rel, name):
            entrypoints.append(rel)
        ext = p.suffix.lower()
        lang = LANG_FROM_EXT.get(ext)
        if lang and not is_generated(name):
            lang_counts[lang] += 1
        kind = is_test_file(rel, name)
        if kind:
            test_kinds[kind] += 1
            if len(test_files) < 30:
                test_files.append(rel)
        n = 0
        if ext in SOURCE_EXT and not is_generated(name):
            n = line_count(p)
            pkg = nearest_package(p, root)
            sources.append((n, rel, pkg))
        if todo_scanable(p) and not is_generated(name):
            if n == 0:
                n = line_count(p)
            c, samp = scan_todo(p, rel, n)
            todo_count += c
            if c:
                todo_per_file[rel] += c
            for s in samp:
                if len(todo_samples) < 40:
                    todo_samples.append(s)

    sources.sort(reverse=True)
    top = [{"path": rel, "lines": n, "package": pkg} for n, rel, pkg in sources[:30]]
    docs_count = len(docs)
    todo_by_file = [
        {"path": path, "count": n} for path, n in todo_per_file.most_common(20)
    ]
    markers = detect_packages(root)
    for bundle in find_xcode_bundles(root):
        if bundle.endswith(".xcodeproj") and "xcodeproj" not in markers:
            markers.append("xcodeproj")
        if bundle.endswith(".xcworkspace") and "xcworkspace" not in markers:
            markers.append("xcworkspace")
    primary = lang_counts.most_common(1)[0][0] if lang_counts else None
    stems = {
        Path(rel).stem.lower()
        for _n, rel, _p in sources
        if not is_test_file(rel, Path(rel).name)
    }
    orphan_tests: list[dict] = []
    for rel in test_files:
        stem = test_pair_stem(rel, Path(rel).name)
        if stem and stem.lower() not in stems:
            orphan_tests.append({"path": rel, "expected_stem": stem})
            if len(orphan_tests) >= 20:
                break
    profile = {
        "languages": dict(lang_counts.most_common(12)),
        "primary": primary,
        "ecosystem": markers,
        "test_kinds": dict(test_kinds),
        "test_files": test_files,
        "orphan_tests": orphan_tests,
    }

    out = {
        "root": str(root),
        "workspace": str(ws),
        "file_count": len(files),
        "profile": profile,
        "top_by_lines": top,
        "todo_count": todo_count,
        "todo_samples": todo_samples,
        "todo_by_file": todo_by_file,
        "docs_count": docs_count,
        "docs": docs[:80],
        "docs_truncated": docs_count > 80,
        "workspace_markers": markers,
        "secret_candidates": secrets,
        "entrypoints": entrypoints[:40],
        "generated_excluded_from_top": True,
        "complete_todo_list": False,
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
