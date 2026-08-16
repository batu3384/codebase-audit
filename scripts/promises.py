#!/usr/bin/env python3
"""Promised paths in CI / package.json / Info.plist vs tree. No NLP backlog."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from paths import require_inside
from walk import MAX_READ_BYTES, is_generated, resolved_is_secret, walk_files

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


def read_text(path: Path) -> str | None:
    try:
        if path.stat().st_size > MAX_READ_BYTES:
            return None
        raw = path.read_bytes()[:8]
        if raw.startswith(b"bplist"):
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def collect_haystack(root: Path) -> tuple[str, int, bool]:
    """One pass over source. Cap 400 files."""
    chunks: list[str] = []
    n = 0
    truncated = False
    for p in walk_files(root):
        if resolved_is_secret(p, root) or is_generated(p.name):
            continue
        if p.suffix.lower() not in SOURCE_SUF:
            continue
        n += 1
        if n > 400:
            truncated = True
            break
        text = read_text(p)
        if text:
            chunks.append(text)
    return "\n".join(chunks), min(n, 400), truncated


def main() -> int:
    ap = argparse.ArgumentParser(description="codebase-audit promises")
    ap.add_argument("workspace", type=Path)
    ap.add_argument("root", type=Path)
    args = ap.parse_args()
    _ws, root = require_inside(args.workspace, args.root)

    missing: list[dict] = []
    missing_n = 0
    plist_unused: list[dict] = []
    plist_missing: list[dict] = []
    scanned = 0
    binary_plist = False
    haystack, haystack_files, haystack_truncated = collect_haystack(root)

    pkg = root / "package.json"
    if pkg.is_file():
        scanned += 1
        text = read_text(pkg) or ""
        try:
            scripts = (json.loads(text).get("scripts") or {}) if text else {}
            blob = " ".join(str(v) for v in scripts.values())
        except json.JSONDecodeError:
            blob = text
        for spec in extract_paths(blob):
            if not (root / spec).exists():
                missing_n += 1
                if len(missing) < 40:
                    missing.append({"from": "package.json", "path": spec})

    plist_texts: list[tuple[str, str]] = []

    for p in walk_files(root):
        if resolved_is_secret(p, root) or is_generated(p.name):
            continue
        rel = str(p.relative_to(root)).replace("\\", "/")
        name = p.name
        low = rel.lower()
        if "/.github/workflows/" in f"/{low}/" and name.endswith((".yml", ".yaml")):
            scanned += 1
            text = read_text(p) or ""
            for spec in extract_paths(text):
                if not (root / spec).exists():
                    missing_n += 1
                    if len(missing) < 40:
                        missing.append({"from": rel, "path": spec})
        if name == "Info.plist" or name.endswith(".entitlements"):
            scanned += 1
            text = read_text(p)
            if text is None:
                try:
                    head = p.read_bytes()[:8]
                except OSError:
                    head = b""
                if head.startswith(b"bplist"):
                    binary_plist = True
                continue
            table = PLIST_NEEDLES if name == "Info.plist" else ENTITLEMENT_NEEDLES
            if name == "Info.plist":
                plist_texts.append((rel, text))
            for key, needles in table.items():
                if key not in text:
                    continue
                if not any(s in haystack for s in needles):
                    plist_unused.append({"from": rel, "key": key})

    # Reverse privacy string: only when a single XML Info.plist exists.
    # Multiple targets share one haystack; merged blob lies. Skip rather than guess.
    if len(plist_texts) == 1 and not binary_plist:
        _rel, blob = plist_texts[0]
        for key, needles in PLIST_NEEDLES.items():
            if key in blob:
                continue
            if any(s in haystack for s in needles):
                plist_missing.append({"key": key, "needles": list(needles[:2])})

    out = {
        "root": str(root),
        "files_scanned": scanned,
        "missing_paths": missing[:40],
        "missing_count": missing_n,
        "missing_complete": missing_n <= 40,
        "plist_unused": plist_unused[:20],
        "plist_missing": plist_missing[:20],
        "binary_plist": binary_plist,
        "plist_missing_skipped_multi": len(plist_texts) > 1,
        "haystack_files": haystack_files,
        "haystack_truncated": haystack_truncated,
        "note": "CI/package/plist paths and privacy keys vs symbols; no product-feature NLP",
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
