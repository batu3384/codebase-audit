#!/usr/bin/env python3
"""Static + optional safe runtime checks. Never runs make, curl, npx, or unknown scripts."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from paths import require_inside
from walk import find_xcode_bundles

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


def classify_script(body: str) -> str:
    b = " ".join(body.strip().split())
    if not b or b in ("exit 1", "echo not implemented", "false"):
        return "placeholder"
    if UNSAFE_SHELL.search(b):
        return "unsafe"
    if SAFE_NPM_TEST.match(b) or SAFE_PYTEST.match(b):
        return "safe"
    if re.match(r"^go\s+test\b", b, re.I):
        return "safe"
    if re.match(r"^cargo\s+test\b", b, re.I):
        return "safe"
    return "review"


def python_project(root: Path) -> bool:
    for n in (
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "Pipfile",
        "requirements.txt",
        "requirements-dev.txt",
        "environment.yml",
    ):
        if (root / n).is_file():
            return True
    if any(p.is_file() for p in root.glob("*.py")):
        return True
    src = root / "src"
    if src.is_dir() and any(src.glob("*.py")):
        return True
    return False


def pytest_evidence(root: Path) -> bool:
    if (root / "pytest.ini").is_file() or (root / "conftest.py").is_file():
        return True
    pyproject = root / "pyproject.toml"
    if pyproject.is_file() and "[tool.pytest" in pyproject.read_text(
        encoding="utf-8", errors="replace"
    ):
        return True
    tests = root / "tests"
    if tests.is_dir() and any(tests.rglob("*.py")):
        return True
    if any(root.glob("test_*.py")) or any(root.glob("*_test.py")):
        return True
    return False


def read_make_recipe(makefile: Path, target: str) -> str | None:
    if not makefile.is_file():
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


def pytest_cmd() -> list[str]:
    return [sys.executable, "-m", "pytest", "-q"]


def run_cmd(cmd: list[str], cwd: Path, timeout: int) -> dict:
    env = os.environ.copy()
    env["CI"] = "1"
    try:
        r = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        return {
            "cmd": cmd,
            "exit": r.returncode,
            "stdout_tail": (r.stdout or "")[-2000:],
            "stderr_tail": (r.stderr or "")[-2000:],
        }
    except subprocess.TimeoutExpired:
        return {"cmd": cmd, "exit": 124, "error": "timeout"}
    except FileNotFoundError:
        return {"cmd": cmd, "exit": 127, "error": "tooling missing"}


def detect(root: Path) -> list[dict]:
    plans: list[dict] = []
    pkg = root / "package.json"
    if pkg.is_file():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
            test = (data.get("scripts") or {}).get("test")
            if test:
                plans.append(
                    {
                        "kind": "npm-test",
                        "manifest": str(pkg),
                        "body": test,
                        "class": classify_script(test),
                    }
                )
        except json.JSONDecodeError:
            plans.append(
                {
                    "kind": "npm-test",
                    "manifest": str(pkg),
                    "error": "invalid json",
                    "class": "review",
                }
            )

    if (root / "go.mod").is_file():
        plans.append({"kind": "go-test", "body": "go test ./...", "class": "safe"})

    if (root / "Cargo.toml").is_file():
        plans.append({"kind": "cargo-test", "body": "cargo test", "class": "safe"})

    if python_project(root) and pytest_evidence(root):
        plans.append(
            {
                "kind": "pytest",
                "body": "python3 -m pytest -q",
                "class": "safe",
            }
        )

    makefile = root / "Makefile"
    if makefile.is_file():
        for target in ("test", "lint", "check"):
            body = read_make_recipe(makefile, target)
            if body:
                plans.append(
                    {
                        "kind": f"make-{target}",
                        "manifest": str(makefile),
                        "body": body,
                        "class": classify_script(body),
                    }
                )

    if (root / "Package.swift").is_file():
        plans.append({"kind": "swift-test", "body": "swift test", "class": "safe"})

    if (root / "pubspec.yaml").is_file():
        plans.append({"kind": "dart-test", "body": "dart test", "class": "safe"})

    xcode = find_xcode_bundles(root)
    if xcode:
        plans.append(
            {
                "kind": "xcodebuild-test",
                "manifest": str(root / xcode[0]),
                "body": "xcodebuild test",
                "class": "review",
                "note": "simulator/signing; not executed even with --run",
            }
        )

    if (root / "Podfile").is_file():
        plans.append(
            {
                "kind": "pod-install",
                "manifest": str(root / "Podfile"),
                "body": "pod install",
                "class": "review",
                "note": "CocoaPods network; not executed",
            }
        )

    gradlew = root / "gradlew"
    if gradlew.is_file():
        plans.append(
            {
                "kind": "gradle-test",
                "manifest": str(gradlew),
                "body": "./gradlew test",
                "class": "review",
                "note": "wrapper is project code; not executed",
            }
        )

    return plans


def execute_plan(plan: dict, root: Path, timeout: int) -> dict:
    if plan.get("class") != "safe":
        return {"skipped": True, "reason": f"class={plan.get('class')}"}

    kind = plan["kind"]
    if kind.startswith("make-"):
        # Never invoke make (includes / overrides). Map recipe to a direct binary if exact.
        body = " ".join((plan.get("body") or "").split())
        if re.match(r"^go\s+test\b", body, re.I):
            return run_cmd(["go", "test", "./..."], root, timeout)
        if SAFE_PYTEST.match(body):
            return run_cmd(pytest_cmd(), root, timeout)
        if re.match(r"^cargo\s+test\b", body, re.I):
            return run_cmd(["cargo", "test", "--offline"], root, timeout)
        return {"skipped": True, "reason": "make never executed"}

    if kind == "npm-test":
        if (root / "pnpm-lock.yaml").is_file():
            cmd = ["pnpm", "test", "--ignore-scripts"]
        elif (root / "yarn.lock").is_file():
            cmd = ["yarn", "test", "--ignore-scripts"]
        else:
            cmd = ["npm", "test", "--ignore-scripts"]
        return run_cmd(cmd, root, timeout)
    if kind == "go-test":
        return run_cmd(["go", "test", "./..."], root, timeout)
    if kind == "cargo-test":
        return run_cmd(["cargo", "test", "--offline"], root, timeout)
    if kind == "pytest":
        return run_cmd(pytest_cmd(), root, timeout)
    if kind == "swift-test":
        return run_cmd(["swift", "test"], root, timeout)
    if kind == "dart-test":
        return run_cmd(["dart", "test"], root, timeout)
    return {"skipped": True, "reason": "unknown kind"}


def main() -> int:
    p = argparse.ArgumentParser(description="codebase-audit runtime (static default)")
    p.add_argument("workspace", type=Path)
    p.add_argument("root", type=Path)
    p.add_argument("--run", action="store_true", help="execute all class=safe plans (never make)")
    p.add_argument("--timeout", type=int, default=120)
    args = p.parse_args()
    _ws, root = require_inside(args.workspace, args.root)

    plans = detect(root)
    out: dict = {
        "root": str(root),
        "mode": "run" if args.run else "static",
        "runtime_note": (
            "--run executes the project's test runner (jest.config, conftest.py, "
            "TestMain). Opt-in only."
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
            if pl.get("class") == "safe" and not str(pl.get("kind", "")).startswith("make-")
        ]
        have = {pl.get("kind") for pl in queue}
        for pl in plans:
            if pl.get("class") != "safe" or not str(pl.get("kind", "")).startswith("make-"):
                continue
            body = " ".join((pl.get("body") or "").split())
            if re.match(r"^go\s+test\b", body, re.I) and "go-test" in have:
                continue
            if SAFE_PYTEST.match(body) and "pytest" in have:
                continue
            if re.match(r"^cargo\s+test\b", body, re.I) and "cargo-test" in have:
                continue
            queue.append(pl)
        executed: list[dict] = []
        remaining = args.timeout
        for pl in queue:
            if remaining <= 0:
                executed.append({"skipped": True, "reason": "timeout budget", "kind": pl.get("kind")})
                continue
            t0 = time.monotonic()
            executed.append(execute_plan(pl, root, remaining))
            remaining = max(0, remaining - int(time.monotonic() - t0))
        out["executed"] = executed
        if not queue:
            out["executed"] = [{"skipped": True, "reason": "no safe plan"}]
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
