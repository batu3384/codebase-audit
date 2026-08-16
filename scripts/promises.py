#!/usr/bin/env python3
"""Promised paths in CI / package.json / Info.plist vs tree. No NLP backlog."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from paths import require_inside
from walk import bounded_read_text, coverage_json, is_generated, readable_in_tree, walk_tree

PATH_TOKEN = re.compile(
    r"(?:\./)?(?:scripts?|tools|bin|src|app|ci|fastlane)/[\w./+-]+\.[A-Za-z0-9]+"
    r"|\./[\w./+-]+\.[A-Za-z0-9]+"
)

# Distinctive API tokens only. Bare "camera" / "Photos" match copy and false-fire.
PLIST_NEEDLES: dict[str, tuple[str, ...]] = {
    "NSCameraUsageDescription": ("AVCapture", "UIImagePickerController"),
    "NSMicrophoneUsageDescription": ("AVAudioRecorder", "AVCaptureDevice"),
    "NSLocationWhenInUseUsageDescription": ("CLLocationManager",),
    "NSLocationAlwaysAndWhenInUseUsageDescription": ("CLLocationManager",),
    "NSPhotoLibraryUsageDescription": ("PHPhotoLibrary", "PHPickerViewController"),
    "NSFaceIDUsageDescription": ("LAContext",),
    "NSBluetoothAlwaysUsageDescription": ("CBCentralManager",),
    "NSMotionUsageDescription": ("CMMotionManager",),
}

ENTITLEMENT_NEEDLES: dict[str, tuple[str, ...]] = {
    "aps-environment": ("registerForRemoteNotifications", "UNUserNotificationCenter"),
}

SOURCE_SUF = {".swift", ".m", ".mm", ".h", ".ts", ".tsx", ".js", ".kt", ".java"}


def extract_paths(text: str) -> list[str]:
    out: list[str] = []
    for m in PATH_TOKEN.finditer(text):
        spec = m.group(0)
        if spec.startswith("./"):
            spec = spec[2:]
        if spec not in out:
            out.append(spec)
    return out


def collect_haystack(
    root: Path, files: list[Path]
) -> tuple[str, int, bool, int, int]:
    """One pass over source. Cap 400 files."""
    chunks: list[str] = []
    n = 0
    truncated = False
    skipped_large = 0
    skipped_unreadable = 0
    for p in files:
        if not readable_in_tree(p, root) or is_generated(p.name):
            continue
        if p.suffix.lower() not in SOURCE_SUF:
            continue
        n += 1
        if n > 400:
            truncated = True
            break
        read = bounded_read_text(p, root)
        if read.skip_reason == "large":
            skipped_large += 1
            continue
        if read.skip_reason:
            skipped_unreadable += 1
            continue
        if read.text:
            chunks.append(read.text)
    return "\n".join(chunks), min(n, 400), truncated, skipped_large, skipped_unreadable


def main() -> int:
    ap = argparse.ArgumentParser(description="codebase-audit promises")
    ap.add_argument("workspace", type=Path)
    ap.add_argument("root", type=Path)
    args = ap.parse_args()
    _ws, root = require_inside(args.workspace, args.root)

    cover = walk_tree(root)
    files = cover.files
    missing: list[dict] = []
    missing_n = 0
    plist_unused: list[dict] = []
    plist_missing: list[dict] = []
    scanned = 0
    binary_plist = False
    skipped_large = 0
    skipped_unreadable = 0
    package_manifest_skipped = False

    haystack, haystack_files, haystack_truncated, hl, hu = collect_haystack(root, files)
    skipped_large += hl
    skipped_unreadable += hu

    pkg = root / "package.json"
    if readable_in_tree(pkg, root):
        scanned += 1
        read = bounded_read_text(pkg, root)
        if read.skip_reason:
            package_manifest_skipped = True
            if read.skip_reason == "large":
                skipped_large += 1
            else:
                skipped_unreadable += 1
        else:
            try:
                parsed = json.loads(read.text or "")
            except json.JSONDecodeError:
                parsed = None
            scripts = parsed.get("scripts") if isinstance(parsed, dict) else None
            if isinstance(scripts, dict):
                blob = " ".join(str(v) for v in scripts.values())
            elif read.text:
                blob = read.text
            else:
                blob = ""
            for spec in extract_paths(blob):
                if not (root / spec).exists():
                    missing_n += 1
                    if len(missing) < 40:
                        missing.append({"from": "package.json", "path": spec})

    plist_texts: list[tuple[str, str]] = []

    for p in files:
        if not readable_in_tree(p, root) or is_generated(p.name):
            continue
        rel = str(p.relative_to(root)).replace("\\", "/")
        name = p.name
        low = rel.lower()
        if "/.github/workflows/" in f"/{low}/" and name.endswith((".yml", ".yaml")):
            scanned += 1
            read = bounded_read_text(p, root)
            if read.skip_reason == "large":
                skipped_large += 1
                continue
            if read.skip_reason:
                skipped_unreadable += 1
                continue
            for spec in extract_paths(read.text or ""):
                if not (root / spec).exists():
                    missing_n += 1
                    if len(missing) < 40:
                        missing.append({"from": rel, "path": spec})
        if name == "Info.plist" or name.endswith(".entitlements"):
            scanned += 1
            read = bounded_read_text(p, root)
            if read.skip_reason == "large":
                skipped_large += 1
                continue
            if read.skip_reason:
                if read.skip_reason == "binary":
                    binary_plist = True
                else:
                    skipped_unreadable += 1
                continue
            text = read.text
            table = PLIST_NEEDLES if name == "Info.plist" else ENTITLEMENT_NEEDLES
            if name == "Info.plist":
                plist_texts.append((rel, text or ""))
            for key, needles in table.items():
                if key not in (text or ""):
                    continue
                if not any(s in haystack for s in needles):
                    plist_unused.append({"from": rel, "key": key})

    if len(plist_texts) == 1 and not binary_plist:
        _rel, blob = plist_texts[0]
        for key, needles in PLIST_NEEDLES.items():
            if key in blob:
                continue
            if any(s in haystack for s in needles):
                plist_missing.append({"key": key, "needles": list(needles[:2])})

    read_incomplete = skipped_large > 0 or skipped_unreadable > 0
    haystack_truncated = haystack_truncated or read_incomplete
    missing_complete = (
        missing_n <= 40
        and not haystack_truncated
        and not package_manifest_skipped
    )

    out = {
        "root": str(root),
        "files_scanned": scanned,
        "missing_paths": missing[:40],
        "missing_count": missing_n,
        "missing_complete": missing_complete,
        "plist_unused": plist_unused[:20],
        "plist_missing": plist_missing[:20],
        "binary_plist": binary_plist,
        "plist_missing_skipped_multi": len(plist_texts) > 1,
        "package_manifest_skipped": package_manifest_skipped,
        "haystack_files": haystack_files,
        "haystack_truncated": haystack_truncated,
        "skipped_large": skipped_large,
        "skipped_unreadable": skipped_unreadable,
        **coverage_json(cover),
        "note": "CI/package/plist paths and privacy keys vs symbols; no product-feature NLP",
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
