#!/usr/bin/env python3
"""Pruned inventory. Never reads secret-file bodies (name or symlink target)."""
from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from pathlib import Path

from paths import inside, require_inside
from walk import (
    LANG_FROM_EXT,
    SOURCE_EXT,
    coverage_json,
    find_xcode_bundles,
    is_entrypoint,
    is_generated,
    is_test_file,
    line_count_ex,
    nearest_package,
    readable_in_tree,
    resolved_is_secret,
    scan_todo,
    test_pair_stem,
    todo_scanable,
    walk_tree,
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
    try:
        rel = str(path.resolve().relative_to(ws.resolve()))
    except ValueError:
        return "outside"
    if not has_git:
        return "no-git"
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


def manifest_entrypoints(root: Path) -> list[str]:
    """package.json main/bin paths that exist on disk, inside root."""
    pkg = root / "package.json"
    if not readable_in_tree(pkg, root):
        return []
    try:
        data = json.loads(pkg.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    specs: list[str] = []
    main = data.get("main")
    if isinstance(main, str) and main.strip():
        specs.append(main)
    b = data.get("bin")
    if isinstance(b, str) and b.strip():
        specs.append(b)
    elif isinstance(b, dict):
        specs.extend(v for v in b.values() if isinstance(v, str) and v.strip())
    out: list[str] = []
    seen: set[str] = set()
    root_res = root.resolve()
    for spec in specs:
        raw = spec.replace("\\", "/")
        if raw.startswith("/") or (len(raw) > 1 and raw[1] == ":"):
            continue
        try:
            resolved = (root / raw).resolve()
        except OSError:
            continue
        if not inside(resolved, root_res) or not resolved.is_file():
            continue
        rel = str(resolved.relative_to(root_res)).replace("\\", "/")
        if rel in seen:
            continue
        seen.add(rel)
        out.append(rel)
    return out


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
        if readable_in_tree(root / name, root):
            markers.append(name)
    return markers


def main() -> int:
    ap = argparse.ArgumentParser(description="codebase-audit inventory")
    ap.add_argument("workspace", type=Path)
    ap.add_argument("root", type=Path)
    args = ap.parse_args()
    ws, root = require_inside(args.workspace, args.root)

    has_git = git_probe(ws)
    cover = walk_tree(root)
    files = cover.files
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
    line_count_truncated = 0
    todo_skipped_large = 0

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
        want_src = ext in SOURCE_EXT and not is_generated(name)
        want_todo = todo_scanable(p) and not is_generated(name)
        if want_src or want_todo:
            n, trunc = line_count_ex(p)
            if trunc:
                line_count_truncated += 1
        if want_src:
            pkg = nearest_package(p, root)
            sources.append((n, rel, pkg))
        if want_todo:
            c, samp, skipped_large = scan_todo(p, rel, n)
            if skipped_large:
                todo_skipped_large += 1
            todo_count += c
            if c:
                todo_per_file[rel] += c
            for s in samp:
                if len(todo_samples) < 40:
                    todo_samples.append(s)

    seen_ep = set(entrypoints)
    for spec in manifest_entrypoints(root):
        if spec not in seen_ep:
            entrypoints.append(spec)
            seen_ep.add(spec)

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
        **coverage_json(cover),
        "line_count_truncated": line_count_truncated,
        "todo_skipped_large": todo_skipped_large,
        "complete_scan": (
            cover.walk_complete
            and line_count_truncated == 0
            and todo_skipped_large == 0
        ),
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
