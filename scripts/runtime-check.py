#!/usr/bin/env python3
"""Static + optional executable runtime checks. Command-shape allowlist; no OS sandbox."""
from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

from paths import require_inside
from walk import (
    PACKAGE_MARKERS,
    coverage_json,
    find_xcode_bundles,
    readable_in_tree,
    redact_secrets,
    redact_tail,
    walk_tree,
)

UNSAFE_SHELL = re.compile(
    r"[|&;`$(){}><]|"
    r"\bcurl\b|\bwget\b|\beval\b|\bexec\b|\bnpx\b|\bpnpm\s+d?lx\b|\byarn\s+dlx\b|"
    r"\brm\s+-|\bsudo\b|\bchmod\b|\bchown\b|\bdd\b|\bmkfs\b|"
    r"https?://",
    re.I,
)

SAFE_NPM_TEST = re.compile(
    r"^(node\s+)?(jest|vitest|mocha|ava|tap|playwright\s+test|"
    r"ng\s+test|react-scripts\s+test|vue-cli-service\s+test|"
    r"node\s+--test)([\s].*)?$",
    re.I,
)

SAFE_PYTEST = re.compile(r"^(python3?\s+-m\s+)?pytest([\s].*)?$", re.I)

MAX_PACKAGES = 40
EXECUTABLE = "executable"

CHILD_ENV_KEEP = (
    "PATH",
    "HOME",
    "USER",
    "LOGNAME",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "TERM",
    "TMPDIR",
    "TEMP",
    "TMP",
    "SystemRoot",
    "WINDIR",
    "COMSPEC",
    "PATHEXT",
    "PROGRAMFILES",
    "PROGRAMDATA",
)


def classify_script(body: object) -> str:
    if not isinstance(body, str):
        return "review"
    b = " ".join(body.strip().split())
    if not b or b in ("exit 1", "echo not implemented", "false"):
        return "placeholder"
    if UNSAFE_SHELL.search(b):
        return "unsafe"
    if SAFE_NPM_TEST.match(b) or SAFE_PYTEST.match(b):
        return EXECUTABLE
    if re.match(r"^go\s+test\b", b, re.I):
        return EXECUTABLE
    if re.match(r"^cargo\s+test\b", b, re.I):
        return EXECUTABLE
    return "review"


def python_project(pkg: Path, tree: Path) -> bool:
    for n in (
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "Pipfile",
        "requirements.txt",
        "requirements-dev.txt",
        "environment.yml",
    ):
        if readable_in_tree(pkg / n, tree):
            return True
    if any(readable_in_tree(p, tree) for p in pkg.glob("*.py")):
        return True
    src = pkg / "src"
    if src.is_dir() and any(readable_in_tree(p, tree) for p in src.glob("*.py")):
        return True
    return False


def pytest_evidence(pkg: Path, tree: Path) -> bool:
    if readable_in_tree(pkg / "pytest.ini", tree) or readable_in_tree(pkg / "conftest.py", tree):
        return True
    pyproject = pkg / "pyproject.toml"
    if readable_in_tree(pyproject, tree) and "[tool.pytest" in pyproject.read_text(
        encoding="utf-8", errors="replace"
    ):
        return True
    tests = pkg / "tests"
    if tests.is_dir() and any(readable_in_tree(p, tree) for p in tests.rglob("*.py")):
        return True
    if any(readable_in_tree(p, tree) for p in pkg.glob("test_*.py")) or any(
        readable_in_tree(p, tree) for p in pkg.glob("*_test.py")
    ):
        return True
    return False


def read_make_recipe(makefile: Path, target: str, tree: Path) -> str | None:
    if not readable_in_tree(makefile, tree):
        return None
    lines = makefile.read_text(encoding="utf-8", errors="replace").splitlines()
    collecting = False
    recipe: list[str] = []
    for line in lines:
        if re.match(rf"^{re.escape(target)}\s*:", line):
            collecting = True
            continue
        if collecting:
            if line.startswith("\t"):
                recipe.append(line.lstrip("\t").strip())
            elif line.strip() == "":
                continue
            else:
                break
    return " && ".join(recipe) if recipe else None


def child_env() -> dict[str, str]:
    env = {k: os.environ[k] for k in CHILD_ENV_KEEP if k in os.environ}
    env["CI"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def pytest_cmd() -> list[str]:
    return [sys.executable, "-m", "pytest", "-q"]


def kill_group(proc: subprocess.Popen[str]) -> None:
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                capture_output=True,
                timeout=15,
                check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass
        try:
            proc.kill()
        except OSError:
            pass
        return
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.kill()
        except OSError:
            pass


def run_cmd(cmd: list[str], cwd: Path, timeout: float) -> dict:
    kwargs: dict = {
        "cwd": cwd,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
        "env": child_env(),
    }
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    try:
        proc = subprocess.Popen(cmd, **kwargs)
    except FileNotFoundError:
        return {"cmd": cmd, "exit": 127, "error": "tooling missing", "cwd": str(cwd)}
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        kill_group(proc)
        try:
            stdout, stderr = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            stdout, stderr = "", ""
        return {
            "cmd": cmd,
            "cwd": str(cwd),
            "exit": 124,
            "error": "timeout",
            "stdout_tail": redact_tail(stdout or "", 2000),
            "stderr_tail": redact_tail(stderr or "", 2000),
        }
    return {
        "cmd": cmd,
        "cwd": str(cwd),
        "exit": proc.returncode,
        "stdout_tail": redact_tail(stdout or "", 2000),
        "stderr_tail": redact_tail(stderr or "", 2000),
    }


def package_roots(root: Path, files: list[Path]) -> tuple[list[Path], bool, int]:
    found = [root]
    seen = {root.resolve()}
    complete = True
    skipped_outside = 0
    for p in files:
        if p.name not in PACKAGE_MARKERS:
            continue
        if not readable_in_tree(p, root):
            skipped_outside += 1
            continue
        d = p.parent
        rd = d.resolve()
        if rd in seen:
            continue
        if len(found) >= MAX_PACKAGES:
            complete = False
            break
        seen.add(rd)
        found.append(d)
    return found, complete, skipped_outside


def pkg_rel(pkg: Path, root: Path) -> str:
    if pkg.resolve() == root.resolve():
        return "."
    return str(pkg.relative_to(root))


def detect_at(pkg: Path, root: Path) -> list[dict]:
    plans: list[dict] = []
    rel = pkg_rel(pkg, root)
    pkg_json = pkg / "package.json"
    if readable_in_tree(pkg_json, root):
        try:
            data = json.loads(pkg_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = None
        if not isinstance(data, dict):
            plans.append(
                {
                    "kind": "npm-test",
                    "manifest": str(pkg_json),
                    "error": "invalid manifest",
                    "class": "review",
                    "package": rel,
                    "cwd": str(pkg),
                }
            )
        else:
            scripts = data.get("scripts")
            if scripts is None:
                pass
            elif not isinstance(scripts, dict):
                plans.append(
                    {
                        "kind": "npm-test",
                        "manifest": str(pkg_json),
                        "error": "invalid scripts shape",
                        "class": "review",
                        "package": rel,
                        "cwd": str(pkg),
                    }
                )
            else:
                test = scripts.get("test")
                if test is None:
                    pass
                elif not isinstance(test, str):
                    plans.append(
                        {
                            "kind": "npm-test",
                            "manifest": str(pkg_json),
                            "error": "invalid scripts.test shape",
                            "class": "review",
                            "package": rel,
                            "cwd": str(pkg),
                        }
                    )
                elif test:
                    plans.append(
                        {
                            "kind": "npm-test",
                            "manifest": str(pkg_json),
                            "body": redact_secrets(test)[:200],
                            "class": classify_script(test),
                            "package": rel,
                            "cwd": str(pkg),
                        }
                    )

    if readable_in_tree(pkg / "go.mod", root):
        plans.append(
            {
                "kind": "go-test",
                "manifest": str(pkg / "go.mod"),
                "body": "go test ./...",
                "class": EXECUTABLE,
                "package": rel,
                "cwd": str(pkg),
            }
        )

    if readable_in_tree(pkg / "Cargo.toml", root):
        plans.append(
            {
                "kind": "cargo-test",
                "manifest": str(pkg / "Cargo.toml"),
                "body": "cargo test",
                "class": EXECUTABLE,
                "package": rel,
                "cwd": str(pkg),
            }
        )

    if python_project(pkg, root) and pytest_evidence(pkg, root):
        plans.append(
            {
                "kind": "pytest",
                "manifest": str(pkg),
                "body": "python3 -m pytest -q",
                "class": EXECUTABLE,
                "package": rel,
                "cwd": str(pkg),
            }
        )

    makefile = pkg / "Makefile"
    if readable_in_tree(makefile, root):
        for target in ("test", "lint", "check"):
            body = read_make_recipe(makefile, target, root)
            if body:
                plans.append(
                    {
                        "kind": f"make-{target}",
                        "manifest": str(makefile),
                        "body": redact_secrets(body)[:200],
                        "class": classify_script(body),
                        "package": rel,
                        "cwd": str(pkg),
                    }
                )

    if readable_in_tree(pkg / "Package.swift", root):
        plans.append(
            {
                "kind": "swift-test",
                "manifest": str(pkg / "Package.swift"),
                "body": "swift test",
                "class": EXECUTABLE,
                "package": rel,
                "cwd": str(pkg),
            }
        )

    if readable_in_tree(pkg / "pubspec.yaml", root):
        plans.append(
            {
                "kind": "dart-test",
                "manifest": str(pkg / "pubspec.yaml"),
                "body": "dart test",
                "class": EXECUTABLE,
                "package": rel,
                "cwd": str(pkg),
            }
        )

    if pkg.resolve() == root.resolve():
        xcode = find_xcode_bundles(root)
        if xcode:
            plans.append(
                {
                    "kind": "xcodebuild-test",
                    "manifest": str(root / xcode[0]),
                    "body": "xcodebuild test",
                    "class": "review",
                    "note": "simulator/signing; not executed even with --run",
                    "package": ".",
                    "cwd": str(root),
                }
            )

        if readable_in_tree(root / "Podfile", root):
            plans.append(
                {
                    "kind": "pod-install",
                    "manifest": str(root / "Podfile"),
                    "body": "pod install",
                    "class": "review",
                    "note": "CocoaPods network; not executed",
                    "package": ".",
                    "cwd": str(root),
                }
            )

        gradlew = root / "gradlew"
        if readable_in_tree(gradlew, root):
            plans.append(
                {
                    "kind": "gradle-test",
                    "manifest": str(gradlew),
                    "body": "./gradlew test",
                    "class": "review",
                    "note": "wrapper is project code; not executed",
                    "package": ".",
                    "cwd": str(root),
                }
            )

    return plans


def detect(root: Path) -> tuple[list[dict], bool, object, int]:
    cover = walk_tree(root)
    roots, complete, skipped_outside = package_roots(root, cover.files)
    plans: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for pkg in roots:
        for pl in detect_at(pkg, root):
            key = (str(pl.get("kind")), str(pl.get("manifest") or pl.get("cwd")))
            if key in seen:
                continue
            seen.add(key)
            plans.append(pl)
    return plans, complete, cover, skipped_outside


def execute_plan(plan: dict, timeout: float) -> dict:
    cwd = Path(plan.get("cwd") or plan.get("manifest") or ".")
    if plan.get("class") != EXECUTABLE:
        return {"skipped": True, "reason": f"class={plan.get('class')}", "cwd": str(cwd)}

    kind = plan["kind"]
    if kind.startswith("make-"):
        body = " ".join((plan.get("body") or "").split())
        if re.match(r"^go\s+test\b", body, re.I):
            return run_cmd(["go", "test", "./..."], cwd, timeout)
        if SAFE_PYTEST.match(body):
            return run_cmd(pytest_cmd(), cwd, timeout)
        if re.match(r"^cargo\s+test\b", body, re.I):
            return run_cmd(["cargo", "test", "--offline"], cwd, timeout)
        return {"skipped": True, "reason": "make never executed", "cwd": str(cwd)}

    if kind == "npm-test":
        if (cwd / "pnpm-lock.yaml").is_file():
            cmd = ["pnpm", "test", "--ignore-scripts"]
        elif (cwd / "yarn.lock").is_file():
            cmd = ["yarn", "test", "--ignore-scripts"]
        else:
            cmd = ["npm", "test", "--ignore-scripts"]
        return run_cmd(cmd, cwd, timeout)
    if kind == "go-test":
        return run_cmd(["go", "test", "./..."], cwd, timeout)
    if kind == "cargo-test":
        return run_cmd(["cargo", "test", "--offline"], cwd, timeout)
    if kind == "pytest":
        return run_cmd(pytest_cmd(), cwd, timeout)
    if kind == "swift-test":
        return run_cmd(["swift", "test"], cwd, timeout)
    if kind == "dart-test":
        return run_cmd(["dart", "test"], cwd, timeout)
    return {"skipped": True, "reason": "unknown kind", "cwd": str(cwd)}


def main() -> int:
    p = argparse.ArgumentParser(description="codebase-audit runtime (static default)")
    p.add_argument("workspace", type=Path)
    p.add_argument("root", type=Path)
    p.add_argument("--run", action="store_true", help="execute all class=executable plans (never make)")
    p.add_argument("--timeout", type=int, default=120)
    args = p.parse_args()
    _ws, root = require_inside(args.workspace, args.root)

    plans, packages_complete, cover, skipped_outside = detect(root)
    out: dict = {
        "root": str(root),
        "mode": "run" if args.run else "static",
        "sandbox": False,
        "packages_complete": packages_complete,
        "skipped_outside_manifests": skipped_outside,
        **coverage_json(cover),
        "runtime_note": (
            "class=executable is a command-shape allowlist, not an OS sandbox "
            "(no network/filesystem isolation). --run executes the project's test "
            "runner (jest.config, conftest.py, TestMain). Child env is an allowlist. "
            "stdout/stderr are redacted (JSON/YAML/bearer). Opt-in only."
        ),
        "plans": plans,
    }

    unsafe = [pl for pl in plans if pl.get("class") in ("unsafe", "placeholder")]
    review = [pl for pl in plans if pl.get("class") == "review"]

    if unsafe:
        out["findings_hint"] = [
            {
                "severity": "Major",
                "category": "Functional correctness",
                "reason": "unsafe or placeholder test script",
                "manifest": pl.get("manifest"),
                "body": pl.get("body"),
            }
            for pl in unsafe
        ]

    if not plans:
        out["runtime"] = "none"
    elif args.run:
        queue = [
            pl
            for pl in plans
            if pl.get("class") == EXECUTABLE and not str(pl.get("kind", "")).startswith("make-")
        ]
        have = {(pl.get("kind"), pl.get("cwd")) for pl in queue}
        for pl in plans:
            if pl.get("class") != EXECUTABLE or not str(pl.get("kind", "")).startswith("make-"):
                continue
            body = " ".join((pl.get("body") or "").split())
            cwd = pl.get("cwd")
            if re.match(r"^go\s+test\b", body, re.I) and ("go-test", cwd) in have:
                continue
            if SAFE_PYTEST.match(body) and ("pytest", cwd) in have:
                continue
            if re.match(r"^cargo\s+test\b", body, re.I) and ("cargo-test", cwd) in have:
                continue
            queue.append(pl)
        executed: list[dict] = []
        deadline = time.monotonic() + args.timeout
        for pl in queue:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                executed.append(
                    {"skipped": True, "reason": "timeout budget", "kind": pl.get("kind")}
                )
                continue
            executed.append(execute_plan(pl, remaining))
        out["executed"] = executed
        if not queue:
            out["executed"] = [{"skipped": True, "reason": "no executable plan"}]
            if review:
                out["executed"][0]["reason"] = "only review-class scripts; not executed"
    else:
        out["runtime"] = "static-only"
        if review:
            out["note"] = "review-class scripts are not executed"

    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
