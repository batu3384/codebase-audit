"""Shared prune/walk/secret/TODO helpers. No secret-file bodies."""
from __future__ import annotations

import os
import re
import stat
from pathlib import Path
from typing import NamedTuple

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

_SECRET_KEY = r"api[_-]?key|secret|token|password|passwd|bearer|authorization"
_QUOTED_KV = re.compile(
    rf'(?i)(["\']?)({_SECRET_KEY})\1\s*[:=]\s*(["\'])(?:\\.|(?!\3).)*\3'
)
_AUTH = re.compile(rf"(?i)\b(authorization)\s*[:=]\s*\S+(?:\s+\S+)?")
_BEARER = re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._\-+/=]+")
_BARE_KV = re.compile(rf"(?i)\b({_SECRET_KEY})\b\s*[:=]\s*\S+")
_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9._\-+/=-]+\b")
_TOKEN_SHAPE = re.compile(
    r"(?:"
    r"\bsk-[A-Za-z0-9_-]{10,}"
    r"|AKIA[0-9A-Z]{16}"
    r"|ghp_[A-Za-z0-9]{20,}"
    r"|github_pat_[A-Za-z0-9_]{20,}"
    r"|xox[baprs]-[\w-]{10,}"
    r")"
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
    "__main__.py",
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
MAX_LINECOUNT_BYTES = 8_000_000
MAX_LINECOUNT_LINES = 500_000
MAX_SECRET_CANDIDATES = 200
MAX_ENTRYPOINTS = 40
MAX_HAYSTACK_BYTES = 8_000_000


class BoundedRead(NamedTuple):
    text: str | None
    skip_reason: str | None  # None = ok; else large|unreadable|binary


def bounded_read_text(path: Path, root: Path) -> BoundedRead:
    """Bounded UTF-8 read for untrusted tree files. Never follows outside secrets."""
    if not readable_in_tree(path, root):
        return BoundedRead(None, "unreadable")
    try:
        st = path.lstat()
        if stat.S_ISLNK(st.st_mode):
            path = path.resolve()
            st = path.stat()
        if st.st_size > MAX_READ_BYTES:
            return BoundedRead(None, "large")
        with path.open("rb") as f:
            magic = f.read(8)
            if magic.startswith(b"bplist"):
                return BoundedRead(None, "binary")
            raw = magic + f.read(MAX_READ_BYTES + 1 - len(magic))
        if len(raw) > MAX_READ_BYTES:
            return BoundedRead(None, "large")
        return BoundedRead(raw.decode("utf-8", errors="replace"), None)
    except OSError:
        return BoundedRead(None, "unreadable")


def is_under_pruned_dir(path: Path, root: Path) -> bool:
    try:
        resolved = path.resolve()
        root_res = root.resolve()
        if not inside(resolved, root_res):
            return False
        rel = resolved.relative_to(root_res)
    except (OSError, ValueError):
        return False
    cur = root_res
    for part in rel.parts[:-1]:
        cur = cur / part
        if should_prune_dir(cur):
            return True
    return False


def redact_secrets(s: str) -> str:
    """Mask JSON/YAML quoted keys, bearer headers, bare key=value, and known token shapes."""
    if not s:
        return ""

    def quoted(m: re.Match[str]) -> str:
        raw = m.group(0)
        sep = "=" if re.search(r"=\s*[\"']", raw) else ":"
        qk, key, qv = m.group(1), m.group(2), m.group(3)
        return f"{qk}{key}{qk}{sep}{qv}***{qv}"

    s = _QUOTED_KV.sub(quoted, s)
    s = _AUTH.sub("authorization=***", s)
    s = _BEARER.sub(r"\1 ***", s)
    s = _BARE_KV.sub(lambda m: m.group(1) + "=***", s)
    s = _JWT.sub("***", s)
    return _TOKEN_SHAPE.sub("***", s)


def redact(s: str, *, limit: int = 120) -> str:
    return redact_secrets(s)[:limit]


def redact_tail(s: str, n: int = 2000) -> str:
    return redact_secrets(s or "")[-n:]


class WalkCover(NamedTuple):
    files: list[Path]
    skipped_special: int
    skipped_symlink_dirs: int
    skipped_unreadable: int
    skipped_walk_errors: int
    skipped_symlink_files: int
    skipped_symlink_unscanned: int

    @property
    def walk_complete(self) -> bool:
        return (
            self.skipped_special == 0
            and self.skipped_unreadable == 0
            and self.skipped_symlink_dirs == 0
            and self.skipped_walk_errors == 0
            and self.skipped_symlink_unscanned == 0
        )


def coverage_json(cover: WalkCover) -> dict:
    return {
        "skipped_special": cover.skipped_special,
        "skipped_symlink_dirs": cover.skipped_symlink_dirs,
        "skipped_unreadable": cover.skipped_unreadable,
        "skipped_walk_errors": cover.skipped_walk_errors,
        "skipped_symlink_files": cover.skipped_symlink_files,
        "skipped_symlink_unscanned": cover.skipped_symlink_unscanned,
        "walk_complete": cover.walk_complete,
    }


def readable_in_tree(path: Path, root: Path) -> bool:
    """False for secrets, outside/broken symlinks, and non-regular files."""
    if resolved_is_secret(path, root):
        return False
    try:
        st = path.lstat()
    except OSError:
        return False
    if stat.S_ISLNK(st.st_mode):
        try:
            resolved = path.resolve()
        except OSError:
            return False
        if not inside(resolved, root):
            return False
        try:
            return stat.S_ISREG(resolved.stat().st_mode)
        except OSError:
            return False
    return stat.S_ISREG(st.st_mode)


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
        for d in sorted(dirnames):
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


def walk_tree(root: Path) -> WalkCover:
    """Pruned file list. Special files skipped. Inside symlink dirs not followed."""
    root = root.resolve()
    out: list[Path] = []
    skipped_special = 0
    skipped_symlink_dirs = 0
    skipped_unreadable = 0
    skipped_walk_errors = 0
    skipped_symlink_files = 0
    skipped_symlink_unscanned = 0

    def onerror(_err: OSError) -> None:
        nonlocal skipped_walk_errors
        skipped_walk_errors += 1

    for dirpath, dirnames, filenames in os.walk(root, followlinks=False, onerror=onerror):
        base = Path(dirpath)
        keep: list[str] = []
        for d in sorted(dirnames):
            child = base / d
            if should_prune_dir(child):
                continue
            try:
                st = child.lstat()
            except OSError:
                skipped_unreadable += 1
                continue
            if stat.S_ISLNK(st.st_mode):
                try:
                    resolved = child.resolve()
                except OSError:
                    out.append(child)
                    continue
                if not inside(resolved, root):
                    out.append(child)
                    continue
                skipped_symlink_dirs += 1
                continue
            keep.append(d)
        dirnames[:] = keep
        for fn in sorted(filenames):
            p = base / fn
            try:
                st = p.lstat()
            except OSError:
                skipped_unreadable += 1
                continue
            if stat.S_ISLNK(st.st_mode):
                try:
                    resolved = p.resolve()
                except OSError:
                    out.append(p)
                    continue
                if not inside(resolved, root):
                    out.append(p)
                    continue
                try:
                    rst = resolved.stat()
                except OSError:
                    skipped_unreadable += 1
                    continue
                if stat.S_ISREG(rst.st_mode):
                    if resolved_is_secret(p, root):
                        out.append(p)
                    elif is_under_pruned_dir(resolved, root):
                        skipped_symlink_unscanned += 1
                    else:
                        skipped_symlink_files += 1
                    continue
            if stat.S_ISREG(st.st_mode):
                out.append(p)
            else:
                skipped_special += 1
    return WalkCover(
        out,
        skipped_special,
        skipped_symlink_dirs,
        skipped_unreadable,
        skipped_walk_errors,
        skipped_symlink_files,
        skipped_symlink_unscanned,
    )


def walk_files(root: Path) -> list[Path]:
    return walk_tree(root).files


def line_count_ex(path: Path) -> tuple[int, bool]:
    try:
        st = path.lstat()
    except OSError:
        return 0, False
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
        return 0, False
    n = 0
    read = 0
    try:
        with path.open("rb") as f:
            for line in f:
                read += len(line)
                n += 1
                if read > MAX_LINECOUNT_BYTES or n > MAX_LINECOUNT_LINES:
                    return n, True
    except OSError:
        return 0, False
    return n, False


def line_count(path: Path) -> int:
    n, _trunc = line_count_ex(path)
    return n


def scan_todo(path: Path, rel: str, nlines: int, root: Path) -> tuple[int, list[str], bool]:
    read = bounded_read_text(path, root)
    if read.skip_reason:
        return 0, [], True
    count = 0
    samples: list[str] = []
    lines = (read.text or "").splitlines()
    total = nlines if nlines else len(lines)
    for i, line in enumerate(lines, 1):
        if not TODO_RE.search(line):
            continue
        count += 1
        take = total <= 800 or i <= 80 or i > total - 40
        if take and len(samples) < 20:
            samples.append(f"{rel}:{i}:{redact(line.strip())}")
    return count, samples, False


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
