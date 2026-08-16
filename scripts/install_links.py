#!/usr/bin/env python3
"""Link codebase-audit into tool skill dirs. Skip when the parent is already SSOT."""
from __future__ import annotations

import argparse
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

from paths import home_ok


def real(path: Path) -> Path | None:
    try:
        return path.resolve()
    except OSError:
        return None


def is_our_skill_dir(dest: Path) -> bool:
    skill = dest / "SKILL.md"
    try:
        st = skill.lstat()
    except OSError:
        return False
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
        return False
    try:
        text = skill.read_text(encoding="utf-8", errors="replace")[:4000]
    except OSError:
        return False
    return "name: codebase-audit" in text


def make_link(dest: Path, target: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(dest), str(target)],
            check=True,
            capture_output=True,
            text=True,
        )
        return
    os.symlink(target, dest, target_is_directory=True)


def link_one(parent: Path, agents: Path, label: str) -> str:
    """Return a status line. Never delete the agents tree."""
    agents_real = real(agents)
    if agents_real is None or not agents_real.is_dir():
        return f"fail {label}: missing {agents}"

    parent.mkdir(parents=True, exist_ok=True)
    parent_real = real(parent)
    if parent_real is not None and parent_real == agents_real.parent:
        return f"skip {label}: {parent} already SSOT"

    dest = parent / "codebase-audit"
    if dest.exists() or dest.is_symlink():
        dest_real = real(dest)
        if dest_real is not None and dest_real == agents_real:
            return f"skip {label}: already linked"
        if dest_real is not None and (
            dest_real == agents_real.parent or agents_real in dest_real.parents
        ):
            return f"skip {label}: refuse rm of SSOT {dest}"
        if dest.is_symlink() or dest.is_file():
            dest.unlink()
        elif is_our_skill_dir(dest):
            shutil.rmtree(dest)
        else:
            return f"fail {label}: refuse rm of foreign {dest}"

    make_link(dest, agents_real)
    return f"linked {label}: {dest} -> {agents_real}"


def plan(home: Path) -> list[tuple[Path, str]]:
    rows: list[tuple[Path, str]] = []
    if (home / ".cursor").exists() or (home / ".cursor").is_symlink():
        rows.append((home / ".cursor" / "skills", "Cursor"))
    else:
        print("skip Cursor: no ~/.cursor")
    if (home / ".claude").exists() or (home / ".claude").is_symlink():
        rows.append((home / ".claude" / "skills", "Claude"))
    else:
        print("skip Claude: no ~/.claude")
    if (home / ".gemini" / "config").is_dir() or (home / ".gemini" / "config").is_symlink():
        rows.append((home / ".gemini" / "config" / "skills", "Antigravity"))
    else:
        print("skip Antigravity: no ~/.gemini/config")
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description="Link codebase-audit into tool skill directories")
    ap.add_argument("--home", type=Path, default=Path.home())
    ap.add_argument(
        "--agents",
        type=Path,
        default=None,
        help="Installed skill dir (default: <home>/.agents/skills/codebase-audit)",
    )
    args = ap.parse_args()
    home_err = home_ok(args.home)
    if home_err:
        sys.stderr.write(f"install refuse: {home_err}\n")
        return 2
    home = args.home
    agents = args.agents or (home / ".agents" / "skills" / "codebase-audit")
    if not agents.is_dir():
        sys.stderr.write(f"missing install target {agents}\n")
        return 1
    failed = False
    for parent, label in plan(home):
        line = link_one(parent, agents, label)
        print(line)
        if line.startswith("fail "):
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
