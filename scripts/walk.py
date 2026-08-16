"""Shared prune/walk/secret/TODO helpers. No secret-file bodies."""
from __future__ import annotations

import os
import re
from pathlib import Path

from paths import inside

PRUNE_ALWAYS = {
    "node_modules",
    ".git",
    "dist",
    "build",
    "__pycache__",
    ".venv",
    "venv",
    "coverage",
    ".next",
    "target",
    "storybook-static",
    "Pods",
    "DerivedData",
    ".build",
    "Carthage",
    "xcuserdata",
    ".gradle",
    ".cxx",
    ".swiftpm",
    ".terraform",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    "bower_components",
    ".yarn",
    ".turbo",
    ".cache",
}

SOURCE_EXT = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".mts",
    ".cts",
    ".vue",
    ".svelte",
    ".go",
    ".rs",
    ".java",
    ".rb",
    ".php",
    ".c",
    ".cc",
    ".cpp",
    ".h",
    ".hpp",
    ".cs",
    ".kt",
    ".kts",
    ".swift",
    ".m",
    ".mm",
    ".sql",
    ".proto",
    ".dart",
    ".scala",
    ".ex",
    ".exs",
    ".lua",
}

TODO_EXT = SOURCE_EXT | {
    ".sh",
    ".bash",
    ".zsh",
    ".fish",
    ".yml",
    ".yaml",
}

TODO_NAMES = {"Makefile", "GNUmakefile", "Dockerfile", "Justfile"}

TODO_RE = re.compile(
    r"\bTODO\b|\bFIXME\b|\bXXX\b|\bHACK\b|\bWIP\b|NotImplementedError|"
    r"unimplemented!|todo!|"
    r"coming soon|not implemented|"
    r"fatalError\(\s*\"(?:TODO|FIXME|unimplemented|not implemented)|"
    r"preconditionFailure\(\s*\"(?:TODO|FIXME|unimplemented)|"
    r"#warning\b|#error\b|"
    r"@available\(\s*\*\s*,\s*unavailable"
)

SECRETISH = re.compile(
    r"(?i)(api[_-]?key|secret|token|password|passwd|bearer|authorization)\s*[:=]\s*\S+"
)

LANG_FROM_EXT = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".swift": "swift",
    ".m": "objc",
    ".mm": "objc",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".java": "java",
    ".dart": "dart",
    ".rb": "ruby",
    ".php": "php",
    ".cs": "csharp",
    ".c": "c",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".vue": "vue",
    ".svelte": "svelte",
    ".sh": "shell",
    ".bash": "shell",
    ".zsh": "shell",
}

SECRET_NAMES = {
    ".env",
    ".envrc",
    ".npmrc",
    ".pypirc",
    ".netrc",
    "credentials.json",
    "id_rsa",
    "id_ed25519",
    "id_ecdsa",
}
SECRET_PREFIXES = (".env.",)
SECRET_SUFFIXES = (".pem", ".p12", ".pfx", ".keystore", ".key")

GENERATED_MARKERS = (
    ".min.js",
    ".min.css",
    ".generated.",
    ".gen.go",
    ".g.dart",
    ".pb.go",
    "_pb2.py",
    "_pb2_grpc.py",
    ".designer.cs",
    ".g.cs",
)

LOCK_NAMES = {
    "package-lock.json",
    "go.sum",
    "Cargo.lock",
    "pnpm-lock.yaml",
    "yarn.lock",
    "composer.lock",
    "Podfile.lock",
    "Package.resolved",
}

PACKAGE_MARKERS = (
    "package.json",
    "go.mod",
    "Cargo.toml",
    "pyproject.toml",
    "Package.swift",
    "pubspec.yaml",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "composer.json",
)

ENTRY_NAMES = {
    "main.py",
    "app.py",
    "wsgi.py",
    "asgi.py",
    "manage.py",
    "index.ts",
    "index.js",
    "index.tsx",
    "index.jsx",
    "main.ts",
    "main.js",
    "main.go",
    "main.rs",
    "main.swift",
    "App.swift",
    "AppDelegate.swift",
    "SceneDelegate.swift",
    "ContentView.swift",
    "Application.kt",
    "MainActivity.kt",
    "MainActivity.java",
    "main.m",
    "main.mm",
}

ENTRY_RELS = {
    "src/index.ts",
    "src/main.ts",
    "src/index.js",
    "src/main.py",
    "src/App.swift",
}

MAX_READ_BYTES = 2_000_000


def redact(s: str) -> str:
    return SECRETISH.sub(lambda m: m.group(1) + "=***", s)[:120]


def is_test_file(rel: str, name: str) -> str | None:
    path = rel.replace("\\", "/").lower()
    n = name.lower()
    if n.endswith("tests.swift") or n.endswith("test.swift"):
        return "xctest"
    if "/tests/" in f"/{path}/" and n.endswith(".swift"):
        return "xctest"
    if n.endswith("_test.go"):
        return "go-test"
    if n.startswith("test_") and n.endswith(".py"):
        return "pytest"
    if n.endswith("_test.py"):
        return "pytest"
    if "/__tests__/" in f"/{path}/" or ".test." in n or ".spec." in n:
        return "jest"
    if n.endswith("_test.rs"):
        return "cargo"
    if n.endswith("test.java") or n.endswith("test.kt"):
        return "junit"
    return None


def test_pair_stem(rel: str, name: str) -> str | None:
    kind = is_test_file(rel, name)
    if not kind:
        return None
    n = name
    if kind == "xctest":
        if n.endswith("Tests.swift"):
            return n[: -len("Tests.swift")]
        if n.endswith("Test.swift"):
            return n[: -len("Test.swift")]
    if kind == "pytest":
        if n.startswith("test_") and n.endswith(".py"):
            return n[5:-3]
        if n.endswith("_test.py"):
            return n[:-8]
    if kind == "jest":
        for sep in (".test.", ".spec."):
            if sep in n:
                return n.split(sep, 1)[0]
    if kind == "go-test" and n.endswith("_test.go"):
        return n[:-8]
    if kind == "cargo" and n.endswith("_test.rs"):
        return n[:-8]
    return None


def find_xcode_bundles(root: Path) -> list[str]:
    """Nested *.xcodeproj / *.xcworkspace, pruned. Do not walk into the bundle."""
    root = root.resolve()
    found: list[str] = []
    for dirpath, dirnames, _filenames in os.walk(root, followlinks=False):
        base = Path(dirpath)
        keep: list[str] = []
        for d in dirnames:
            child = base / d
            if should_prune_dir(child):
                continue
            if d.endswith(".xcodeproj") or d.endswith(".xcworkspace"):
                found.append(str(child.relative_to(root)))
                continue
            if child.is_symlink():
                try:
                    real = child.resolve()
                except OSError:
                    continue
                if not inside(real, root):
                    continue
            keep.append(d)
        dirnames[:] = keep
        if len(found) >= 20:
            break
    return found


def is_secret_name(name: str) -> bool:
    if name in SECRET_NAMES:
        return True
    if name.startswith(SECRET_PREFIXES):
        return True
    if name.endswith(SECRET_SUFFIXES):
        return True
    if "serviceAccount" in name and name.endswith(".json"):
        return True
    return False


def is_secret_path(path: Path) -> bool:
    if is_secret_name(path.name):
        return True
    parts = {p.lower() for p in path.parts}
    if ".aws" in parts and path.name in {"credentials", "config"}:
        return True
    return False


def resolved_is_secret(path: Path, root: Path) -> bool:
    if is_secret_path(path):
        return True
    try:
        real = path.resolve()
    except OSError:
        return True
    if not inside(real, root):
        return True
    return is_secret_path(real)


def is_generated(name: str) -> bool:
    return any(m in name for m in GENERATED_MARKERS) or name in LOCK_NAMES or name.endswith(".lock")


def should_prune_dir(path: Path) -> bool:
    name = path.name
    if name in PRUNE_ALWAYS:
        return True
    if name == "vendor":
        return (path / "modules.txt").is_file() or (path / "composer").is_dir()
    return False


def walk_files(root: Path) -> list[Path]:
    root = root.resolve()
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        base = Path(dirpath)
        keep: list[str] = []
        for d in dirnames:
            child = base / d
            if should_prune_dir(child):
                continue
            if child.is_symlink():
                try:
                    real = child.resolve()
                except OSError:
                    continue
                if not inside(real, root):
                    continue
            keep.append(d)
        dirnames[:] = keep
        for fn in filenames:
            p = base / fn
            if p.is_symlink():
                try:
                    real = p.resolve()
                except OSError:
                    continue
                if not inside(real, root):
                    continue
            out.append(p)
    return out


def line_count(path: Path) -> int:
    try:
        with path.open("rb") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def scan_todo(path: Path, rel: str, nlines: int) -> tuple[int, list[str]]:
    try:
        if path.stat().st_size > MAX_READ_BYTES:
            return 0, []
    except OSError:
        return 0, []
    count = 0
    samples: list[str] = []
    try:
        with path.open(encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f, 1):
                if not TODO_RE.search(line):
                    continue
                count += 1
                take = nlines <= 800 or i <= 80 or i > nlines - 40
                if take and len(samples) < 20:
                    samples.append(f"{rel}:{i}:{redact(line.strip())}")
    except OSError:
        return 0, []
    return count, samples


def todo_scanable(path: Path) -> bool:
    if path.name in TODO_NAMES:
        return True
    return path.suffix.lower() in TODO_EXT


def nearest_package(path: Path, root: Path) -> str:
    root = root.resolve()
    cur = path.parent.resolve()
    try:
        cur.relative_to(root)
    except ValueError:
        return "."
    while True:
        for m in PACKAGE_MARKERS:
            if (cur / m).is_file():
                if cur == root:
                    return "."
                return str(cur.relative_to(root))
        if cur == root:
            return "."
        cur = cur.parent


def is_entrypoint(rel: str, name: str) -> bool:
    if name in ENTRY_NAMES:
        return True
    if rel in ENTRY_RELS:
        return True
    if rel.startswith("cmd/") and name == "main.go":
        return True
    if rel.endswith("/App.swift") or rel.endswith("/main.swift"):
        return True
    return False
