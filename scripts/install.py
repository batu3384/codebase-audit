#!/usr/bin/env python3
"""Copy skill into agents SSOT, then link hosts. Staging + swap; never rm source."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from paths import is_broad_workspace, is_fs_root

if sys.version_info < (3, 10):
    sys.stderr.write("codebase-audit needs Python 3.10+\n")
    raise SystemExit(1)

MARKERS = ("SKILL.md", "references", "scripts")


def real(path: Path) -> Path:
    return path.expanduser().resolve()


def overlap_error(repo: Path, dest: Path) -> str | None:
    if dest == repo:
        return None
    try:
        dest.relative_to(repo)
        return f"dest inside repo: {dest}"
    except ValueError:
        pass
    try:
        repo.relative_to(dest)
        return f"repo inside dest (refusing rm of source): {dest}"
    except ValueError:
        pass
    return None


def parent_ok(parent: Path, repo: Path) -> str | None:
    if is_fs_root(parent) or is_broad_workspace(parent):
        return f"AGENTS_DIR too broad: {parent}"
    dest = parent / "codebase-audit"
    try:
        d = real(dest) if dest.exists() else parent.resolve() / "codebase-audit"
    except OSError as e:
        return str(e)
    return overlap_error(repo, d)


def require_markers(root: Path) -> None:
    for name in MARKERS:
        p = root / name
        if name.endswith(".md"):
            ok = p.is_file()
        else:
            ok = p.is_dir()
        if not ok:
            raise SystemExit(f"missing marker {p}")


def copy_tree(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(
        src,
        dest,
        ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc", ".pytest_cache"),
    )


def swap_in(staged: Path, dest: Path) -> None:
    parent = dest.parent
    parent.mkdir(parents=True, exist_ok=True)
    new = parent / (dest.name + ".__new__")
    old = parent / (dest.name + ".__old__")
    if new.exists():
        shutil.rmtree(new)
    shutil.move(str(staged), str(new))
    if dest.exists() or dest.is_symlink():
        if old.exists() or old.is_symlink():
            if old.is_symlink() or old.is_file():
                old.unlink()
            else:
                shutil.rmtree(old)
        dest.rename(old)
    new.rename(dest)
    if old.exists() or old.is_symlink():
        if old.is_symlink() or old.is_file():
            old.unlink()
        else:
            shutil.rmtree(old)


def run_py(script: Path, args: list[str]) -> None:
    r = subprocess.run([sys.executable, str(script), *args], cwd=str(script.parent))
    if r.returncode != 0:
        raise SystemExit(r.returncode)


def main() -> int:
    ap = argparse.ArgumentParser(description="Install codebase-audit into ~/.agents/skills")
    ap.add_argument("--repo", type=Path, required=True)
    ap.add_argument("--agents-dir", type=Path, default=None, help="Parent of codebase-audit/")
    ap.add_argument("--home", type=Path, default=Path.home())
    ap.add_argument("--skip-self-check", action="store_true")
    ap.add_argument("--skip-links", action="store_true")
    args = ap.parse_args()

    repo = real(args.repo)
    require_markers(repo)
    parent = real(args.agents_dir) if args.agents_dir else real(args.home / ".agents" / "skills")
    err = parent_ok(parent, repo)
    if err:
        sys.stderr.write(f"install refuse: {err}\n")
        return 2
    dest = parent / "codebase-audit"
    dest_real = real(dest) if dest.exists() else dest

    if dest.exists() and dest_real == repo:
        print(f"in-place SSOT: {dest_real}")
        if not args.skip_links:
            run_py(repo / "scripts" / "install_links.py", ["--home", str(args.home), "--agents", str(repo)])
        if not args.skip_self_check:
            run_py(repo / "scripts" / "self-check.py", [])
        print(f"Installed: {repo}")
        return 0

    with tempfile.TemporaryDirectory() as td:
        staged = Path(td) / "codebase-audit"
        copy_tree(repo, staged)
        require_markers(staged)
        if not args.skip_self_check:
            run_py(staged / "scripts" / "self-check.py", [])
        keep = Path(td) / "keep"
        shutil.move(str(staged), str(keep))
        swap_in(keep, dest)

    if not args.skip_links:
        run_py(dest / "scripts" / "install_links.py", ["--home", str(args.home), "--agents", str(dest)])
    print(f"Installed: {dest}")
    print("Codex reads ~/.agents/skills (no extra link).")
    print("Skipped on purpose: ~/.gemini/skills (Gemini CLI), ~/.codex/skills (catalog).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
