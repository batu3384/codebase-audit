#!/usr/bin/env python3
"""v1.3+ self-check probes. Imported by self-check.py."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
PY = sys.executable


def run(args: list[str], timeout: int = 45, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            capture_output=True,
            text=True,
            cwd=str(SCRIPTS),
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired as e:
        return subprocess.CompletedProcess(
            args, 124, e.stdout or "", (e.stderr or "") + "\ntimeout"
        )


def extra_errors() -> list[str]:
    errors: list[str] = []

    with tempfile.TemporaryDirectory() as td:
        proj = Path(td) / "envleak"
        proj.mkdir()
        (proj / "pyproject.toml").write_text("[tool.pytest.ini_options]\n")
        tests = proj / "tests"
        tests.mkdir()
        (tests / "test_a.py").write_text(
            "import os\n"
            "def test_ok():\n"
            "    print('PROBE=' + os.environ.get('CODEX_SECRET_PROBE', 'none'))\n"
            "    assert True\n"
        )
        env = os.environ.copy()
        env["CODEX_SECRET_PROBE"] = "should-not-appear-in-json"
        r = run(
            [PY, str(SCRIPTS / "runtime-check.py"), str(proj), str(proj), "--run"],
            env=env,
        )
        if r.returncode != 0:
            errors.append(f"envleak runtime-check failed: {r.stderr}")
        elif "should-not-appear-in-json" in r.stdout:
            errors.append("runtime --run leaked parent env secret")

    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        agents_root = home / ".agents" / "skills"
        skill = agents_root / "codebase-audit"
        skill.mkdir(parents=True)
        marker = skill / "SKILL.md"
        marker.write_text("keep\n", encoding="utf-8")
        (home / ".cursor").mkdir()
        (home / ".cursor" / "skills").symlink_to(agents_root)
        (home / ".claude").mkdir()
        (home / ".gemini" / "config").mkdir(parents=True)
        r = run(
            [
                PY,
                str(SCRIPTS / "install_links.py"),
                "--home",
                str(home),
                "--agents",
                str(skill),
            ]
        )
        if r.returncode != 0:
            errors.append(f"install_links failed: {r.stderr or r.stdout}")
        if marker.read_text(encoding="utf-8") != "keep\n":
            errors.append("install_links mutated SSOT skill under a Cursor skills symlink")
        if "already SSOT" not in (r.stdout or ""):
            errors.append(f"install_links should skip Cursor SSOT, got {r.stdout!r}")
        claude = home / ".claude" / "skills" / "codebase-audit"
        if realpath := claude.resolve() if claude.exists() else None:
            if realpath != skill.resolve():
                errors.append(f"Claude link should point at skill, got {realpath}")
        else:
            errors.append("install_links should link Claude")
        agy = home / ".gemini" / "config" / "skills" / "codebase-audit"
        if not agy.exists():
            errors.append("install_links should link Antigravity config/skills")
        if (home / ".gemini" / "skills").exists():
            errors.append("install_links must not create Gemini CLI ~/.gemini/skills")
        if (home / ".codex" / "skills").exists():
            errors.append("install_links must not write ~/.codex/skills")

    from paths import home_ok, is_broad_workspace, is_fs_root
    from schema import validate_child
    from walk import MAX_ENTRYPOINTS, MAX_SECRET_CANDIDATES, MAX_READ_BYTES, MAX_LINECOUNT_BYTES, redact_secrets

    if not is_fs_root(Path("/")):
        errors.append("is_fs_root(/) should be true")
    if Path("/Users").is_dir() and not is_broad_workspace(Path("/Users")):
        errors.append("/Users should be a broad workspace")
    if home_ok(Path.home()) is not None:
        errors.append(f"Path.home() should be allowed --home, got {home_ok(Path.home())}")
    if home_ok(Path("/")) is None:
        errors.append("--home / should be refused")
    if validate_child("inventory", {"root": "."}) is None:
        errors.append("schema should reject incomplete inventory")
    if validate_child(
        "runtime-check",
        {
            "root": "/tmp/x",
            "mode": "static",
            "plans": [],
            "sandbox": True,
            "packages_complete": True,
            "skipped_special": 0,
            "skipped_symlink_dirs": 0,
            "skipped_unreadable": 0,
            "skipped_walk_errors": 0,
            "skipped_symlink_files": 0,
            "skipped_symlink_unscanned": 0,
            "walk_complete": True,
        },
        bundle_root="/tmp/x",
    ) is None:
        errors.append("schema should reject sandbox true")
    if validate_child(
        "inventory",
        {
            "root": "/tmp/x",
            "file_count": 0,
            "profile": {},
            "secret_candidates": [],
            "secret_candidates_total": 0,
            "secret_candidates_truncated": False,
            "entrypoints_truncated": False,
            "complete_scan": "false",
            "line_count_truncated": 0,
            "todo_skipped_large": 0,
            "skipped_special": 0,
            "skipped_symlink_dirs": 0,
            "skipped_unreadable": 0,
            "skipped_walk_errors": 0,
            "skipped_symlink_files": 0,
            "skipped_symlink_unscanned": 0,
            "walk_complete": True,
        },
        bundle_root="/tmp/x",
    ) is None:
        errors.append("schema should reject complete_scan string")
    quoted = redact_secrets('"apiKey": "sk-live-abcdef"')
    if "sk-live-abcdef" in quoted:
        errors.append(f"quoted JSON secret not redacted: {quoted}")
    bearer = redact_secrets("Authorization: Bearer eyJhbGciOi.payload.sig")
    if "eyJhbGciOi" in bearer or "payload.sig" in bearer:
        errors.append(f"bearer token not redacted: {bearer}")
    if "supersecret" in redact_secrets("password=supersecret"):
        errors.append("bare password= not redacted")
    for raw in (
        "printed sk-live-abcdef1234",
        "AKIAAAAAAAAAAAAAAAAA",
        "ghp_" + ("a" * 20),
        "xoxb-1234567890-abcdefghij",
    ):
        red = redact_secrets(raw)
        if any(x in red for x in ("sk-live-abcdef1234", "AKIAAAAAAAAAAAAAAAAA", "ghp_aaaa", "xoxb-1234567890")):
            errors.append(f"token shape not redacted: {raw} -> {red}")
    rt_src = (SCRIPTS / "runtime-check.py").read_text(encoding="utf-8")
    if "taskkill" not in rt_src:
        errors.append("Windows kill_group must use taskkill")

    with tempfile.TemporaryDirectory() as td:
        proj = Path(td) / "nestedpkg"
        proj.mkdir()
        api = proj / "packages" / "api"
        api.mkdir(parents=True)
        (api / "package.json").write_text('{"scripts":{"test":"jest"}}')
        r = run([PY, str(SCRIPTS / "runtime-check.py"), str(proj), str(proj)])
        data = json.loads(r.stdout)
        if data.get("sandbox") is not False:
            errors.append(f"runtime-check sandbox should be false, got {data.get('sandbox')}")
        if data.get("walk_complete") is not True:
            errors.append(f"runtime-check missing walk_complete, got {data}")
        manifests = [p.get("manifest", "") for p in data.get("plans") or []]
        if not any(str(api / "package.json") in m or m.endswith("packages/api/package.json") for m in manifests):
            errors.append(f"nested package.json plan missing, plans={data.get('plans')}")

    with tempfile.TemporaryDirectory() as td:
        proj = Path(td) / "docsph"
        proj.mkdir()
        (proj / "README.md").write_text("`docs/codebase-audit/YYYY-MM-DD.md`\n`src/ghost.ts`\n")
        r = run([PY, str(SCRIPTS / "docs-check.py"), str(proj), str(proj)])
        data = json.loads(r.stdout)
        promised = [x.get("path") for x in data.get("promised_missing") or []]
        if any("YYYY-MM-DD" in (p or "") for p in promised):
            errors.append(f"placeholder path should not be promised_missing, got {promised}")
        if "src/ghost.ts" not in promised:
            errors.append(f"docs-check missed src/ghost.ts, got {promised}")
        if "promised_missing_complete" not in data:
            errors.append("docs-check missing promised_missing_complete")
        if "walk_complete" not in data:
            errors.append("docs-check missing walk_complete")

    if os.name != "nt":
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / "fifo"
            proj.mkdir()
            (proj / "ok.py").write_text("x=1\n")
            os.mkfifo(proj / "hang.fifo")
            r = run([PY, str(SCRIPTS / "inventory.py"), str(proj), str(proj)])
            data = json.loads(r.stdout)
            if data.get("skipped_special", 0) < 1:
                errors.append(f"FIFO should set skipped_special, got {data}")
            if data.get("walk_complete") is not False:
                errors.append("FIFO should set walk_complete false")
            if any("hang.fifo" in x.get("path", "") for x in data.get("top_by_lines") or []):
                errors.append("FIFO must not be line-counted")

    with tempfile.TemporaryDirectory() as td:
        repo = Path(td) / "src" / "codebase-audit"
        (repo / "references").mkdir(parents=True)
        (repo / "scripts").mkdir()
        (repo / "SKILL.md").write_text("x\n")
        (repo / "references" / "keep.md").write_text("x\n")
        (repo / "scripts" / "keep.py").write_text("x=1\n")
        (repo / "scripts" / "alias.py").symlink_to(repo / "scripts" / "keep.py")
        dest_parent = Path(td) / "skills"
        r = run(
            [
                PY,
                str(SCRIPTS / "install.py"),
                "--repo",
                str(repo),
                "--agents-dir",
                str(dest_parent),
                "--skip-self-check",
                "--skip-links",
            ]
        )
        if r.returncode != 0:
            errors.append(f"install.py failed: {r.stderr or r.stdout}")
        installed = dest_parent / "codebase-audit" / "SKILL.md"
        if not installed.is_file():
            errors.append("install.py did not copy SKILL.md")
        alias = dest_parent / "codebase-audit" / "scripts" / "alias.py"
        if not alias.is_symlink():
            errors.append("install.py should preserve in-tree symlinks")
        if not (repo / "SKILL.md").is_file():
            errors.append("install.py deleted source")
        if "symlinks_copied=" not in (r.stdout or ""):
            errors.append(f"install.py should report symlink count, got {r.stdout!r}")
        r2 = run(
            [
                PY,
                str(SCRIPTS / "install.py"),
                "--repo",
                str(repo),
                "--agents-dir",
                str(repo.parent),
                "--skip-self-check",
                "--skip-links",
            ]
        )
        if r2.returncode != 0:
            errors.append(f"in-place install failed: {r2.stderr or r2.stdout}")
        if (repo / "SKILL.md").read_text() != "x\n":
            errors.append("in-place install mutated source")
        r3 = run(
            [
                PY,
                str(SCRIPTS / "install.py"),
                "--repo",
                str(repo),
                "--agents-dir",
                "/",
                "--skip-self-check",
                "--skip-links",
            ]
        )
        if r3.returncode != 2:
            errors.append(f"install.py / should exit 2, got {r3.returncode} {r3.stderr}")
        r4 = run(
            [
                PY,
                str(SCRIPTS / "install.py"),
                "--repo",
                str(repo),
                "--agents-dir",
                str(dest_parent),
                "--home",
                "/",
                "--skip-self-check",
                "--skip-links",
            ]
        )
        if r4.returncode != 2:
            errors.append(f"install.py --home / should exit 2, got {r4.returncode}")
        secret = Path(td) / "secret.env"
        secret.write_text("nope\n")
        (repo / "scripts" / "leak.env").symlink_to(secret)
        r5 = run(
            [
                PY,
                str(SCRIPTS / "install.py"),
                "--repo",
                str(repo),
                "--agents-dir",
                str(Path(td) / "skills2"),
                "--skip-self-check",
                "--skip-links",
            ]
        )
        if r5.returncode != 2:
            errors.append(f"outside symlink install should exit 2, got {r5.returncode} {r5.stderr}")

    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        skill = home / ".agents" / "skills" / "codebase-audit"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: codebase-audit\n---\n")
        (home / ".claude").mkdir()
        foreign = home / ".claude" / "skills" / "codebase-audit"
        foreign.mkdir(parents=True)
        (foreign / "SKILL.md").write_text("docs mention name: codebase-audit\nkeep\n")
        r = run(
            [
                PY,
                str(SCRIPTS / "install_links.py"),
                "--home",
                str(home),
                "--agents",
                str(skill),
            ]
        )
        if (foreign / "SKILL.md").read_text() != "docs mention name: codebase-audit\nkeep\n":
            errors.append("install_links deleted foreign skill dir")
        if r.returncode != 1:
            errors.append(f"foreign skill dir should fail install_links, got {r.returncode} {r.stdout}")
        if "refuse rm of foreign" not in (r.stdout or ""):
            errors.append(f"expected refuse rm, got {r.stdout!r}")
        r_home = run(
            [
                PY,
                str(SCRIPTS / "install_links.py"),
                "--home",
                "/",
                "--agents",
                str(skill),
            ]
        )
        if r_home.returncode != 2:
            errors.append(f"install_links --home / should exit 2, got {r_home.returncode}")

    with tempfile.TemporaryDirectory() as td:
        proj = Path(td) / "extpkg"
        proj.mkdir()
        secret = Path(td) / "secret.json"
        secret.write_text('{"scripts":{"test":"jest s3cr3tVALUE"}}')
        (proj / "package.json").symlink_to(secret)
        (proj / "ok.py").write_text("x=1\n")
        r = run([PY, str(SCRIPTS / "runtime-check.py"), str(proj), str(proj)])
        if "s3cr3tVALUE" in r.stdout:
            errors.append("runtime leaked outside package.json body")
        data = json.loads(r.stdout)
        kinds = [p.get("kind") for p in data.get("plans") or []]
        if "npm-test" in kinds:
            errors.append(f"outside package.json must not yield npm-test, plans={data.get('plans')}")
        if data.get("skipped_outside_manifests", 0) < 1:
            errors.append(f"skipped_outside_manifests should be >=1, got {data}")
        r2 = run([PY, str(SCRIPTS / "promises.py"), str(proj), str(proj)])
        if "s3cr3tVALUE" in r2.stdout:
            errors.append("promises leaked outside package.json body")
        pdata = json.loads(r2.stdout)
        if pdata.get("missing_paths"):
            errors.append(f"promises should skip outside package.json, got {pdata.get('missing_paths')}")
        if "walk_complete" not in pdata:
            errors.append("promises missing walk_complete")

    with tempfile.TemporaryDirectory() as td:
        proj = Path(td) / "entryesc"
        proj.mkdir()
        (proj / "outside.js").write_text("console.log(1)\n")
        (proj / "bin.js").write_text("console.log(1)\n")
        (proj / "package.json").write_text('{"bin":"../outside.js"}')
        r = run([PY, str(SCRIPTS / "inventory.py"), str(proj), str(proj)])
        data = json.loads(r.stdout)
        eps = data.get("entrypoints") or []
        if "outside.js" in eps:
            errors.append(f"../outside.js must not become entrypoint, got {eps}")
        (proj / "package.json").write_text('{"bin":"./bin.js"}')
        r2 = run([PY, str(SCRIPTS / "inventory.py"), str(proj), str(proj)])
        eps2 = json.loads(r2.stdout).get("entrypoints") or []
        if "bin.js" not in eps2:
            errors.append(f"./bin.js should still be entrypoint, got {eps2}")

    with tempfile.TemporaryDirectory() as td:
        proj = Path(td) / "hugeline"
        proj.mkdir()
        (proj / "huge.py").write_bytes(b"x" * (MAX_LINECOUNT_BYTES + 1) + b"\n")
        r = run([PY, str(SCRIPTS / "inventory.py"), str(proj), str(proj)])
        data = json.loads(r.stdout)
        if data.get("line_count_truncated", 0) < 1:
            errors.append(f"line cap should set line_count_truncated, got {data}")
        if data.get("complete_scan") is not False:
            errors.append(f"line cap should set complete_scan false, got {data.get('complete_scan')}")

    with tempfile.TemporaryDirectory() as td:
        proj = Path(td) / "bigtodo"
        proj.mkdir()
        (proj / "notes.sh").write_bytes(b"# TODO later\n" + b"x" * (MAX_READ_BYTES + 1))
        r = run([PY, str(SCRIPTS / "inventory.py"), str(proj), str(proj)])
        data = json.loads(r.stdout)
        if data.get("todo_skipped_large", 0) < 1:
            errors.append(f"large TODO file should set todo_skipped_large, got {data}")
        if data.get("complete_scan") is not False:
            errors.append("large TODO file should set complete_scan false")

    with tempfile.TemporaryDirectory() as td:
        proj = Path(td) / "impwalk"
        proj.mkdir()
        (proj / "a.py").write_text("x=1\n")
        r = run([PY, str(SCRIPTS / "import-sample.py"), str(proj), str(proj)])
        data = json.loads(r.stdout)
        if "walk_complete" not in data:
            errors.append("import-sample missing walk_complete")
        r2 = run([PY, str(SCRIPTS / "stub-scan.py"), str(proj), str(proj)])
        data2 = json.loads(r2.stdout)
        if "walk_complete" not in data2:
            errors.append("stub-scan missing walk_complete")

    with tempfile.TemporaryDirectory() as td:
        proj = Path(td) / "secretplan"
        proj.mkdir()
        (proj / "package.json").write_text(
            '{"scripts":{"test":"jest sk-live-abcdef1234"}}'
        )
        r = run([PY, str(SCRIPTS / "runtime-check.py"), str(proj), str(proj)])
        if r.returncode != 0:
            errors.append(f"runtime secret plan failed: {r.stderr}")
        elif "sk-live-abcdef1234" in r.stdout:
            errors.append("runtime plan leaked token-shaped script body")
        else:
            data = json.loads(r.stdout)
            kinds = [p.get("class") for p in data.get("plans") or []]
            if "executable" not in kinds:
                errors.append(f"redacted jest plan should stay executable, plans={data.get('plans')}")

    with tempfile.TemporaryDirectory() as td:
        proj = Path(td) / "shapert"
        proj.mkdir()
        (proj / "package.json").write_text('{"scripts":{"test":{"cmd":"jest"}}}')
        r = run([PY, str(SCRIPTS / "runtime-check.py"), str(proj), str(proj)])
        if r.returncode != 0:
            errors.append(f"dict scripts.test should not crash, {r.stderr}")
        else:
            data = json.loads(r.stdout)
            errs = [p.get("error") for p in data.get("plans") or []]
            if not any(e and "shape" in str(e) for e in errs):
                errors.append(f"dict scripts.test should be invalid shape, plans={data.get('plans')}")
        (proj / "package.json").write_text('{"scripts":["jest"]}')
        r2 = run([PY, str(SCRIPTS / "promises.py"), str(proj), str(proj)])
        if r2.returncode != 0:
            errors.append(f"list scripts should not crash promises, {r2.stderr}")
        r3 = run([PY, str(SCRIPTS / "run.py"), str(proj)])
        if r3.returncode != 0:
            errors.append(f"odd manifest shape should not incomplete bundle, {r3.stderr} {r3.stdout[-200:]}")

    with tempfile.TemporaryDirectory() as td:
        proj = Path(td) / "aliaswalk"
        proj.mkdir()
        (proj / "real.py").write_text("x=1\n# TODO later\n")
        (proj / "alias.py").symlink_to(proj / "real.py")
        r = run([PY, str(SCRIPTS / "inventory.py"), str(proj), str(proj)])
        data = json.loads(r.stdout)
        tops = [x.get("path") for x in data.get("top_by_lines") or []]
        if "alias.py" in tops:
            errors.append(f"in-tree file symlink should not be line-counted, got {tops}")
        if data.get("skipped_symlink_files", 0) < 1:
            errors.append(f"in-tree file symlink should set skipped_symlink_files, got {data}")
        if data.get("todo_count", 0) < 1:
            errors.append("canonical TODO should still be counted")
        if data.get("complete_scan") is not True:
            errors.append(f"alias skip should not fail complete_scan, got {data.get('complete_scan')}")

    with tempfile.TemporaryDirectory() as td:
        home = Path(td) / "home"
        home.mkdir()
        outside = Path(td) / "outside"
        outside.mkdir()
        skill = home / ".agents" / "skills" / "codebase-audit"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: codebase-audit\n---\n")
        (home / ".claude").mkdir()
        (home / ".claude" / "skills").symlink_to(outside)
        r = run(
            [
                PY,
                str(SCRIPTS / "install_links.py"),
                "--home",
                str(home),
                "--agents",
                str(skill),
            ]
        )
        if (outside / "codebase-audit").exists():
            errors.append("install_links wrote through host parent symlink")
        if r.returncode != 1 or "escapes home" not in (r.stdout or ""):
            errors.append(f"parent symlink escape should fail, got {r.returncode} {r.stdout!r}")

    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        skill = home / ".agents" / "skills" / "codebase-audit"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: codebase-audit\n---\n")
        (home / ".claude").mkdir()
        other = home / "other-skill"
        other.mkdir()
        (other / "SKILL.md").write_text("keep\n")
        dest = home / ".claude" / "skills" / "codebase-audit"
        dest.parent.mkdir(parents=True)
        dest.symlink_to(other)
        r = run(
            [
                PY,
                str(SCRIPTS / "install_links.py"),
                "--home",
                str(home),
                "--agents",
                str(skill),
            ]
        )
        if dest.resolve() != other.resolve():
            errors.append(f"foreign symlink pointer should stay, got {dest.resolve() if dest.exists() else None}")
        if r.returncode != 1 or "foreign symlink" not in (r.stdout or ""):
            errors.append(f"foreign symlink should refuse, got {r.returncode} {r.stdout!r}")
        if (other / "SKILL.md").read_text() != "keep\n":
            errors.append("foreign symlink target mutated")

    with tempfile.TemporaryDirectory() as td:
        ws = Path(td) / "driftws"
        folder = ws / "docs" / "codebase-audit"
        folder.mkdir(parents=True)
        payload = {
            "schema": 1,
            "skill": "codebase-audit",
            "date": "2026-08-13",
            "root": str(ws),
            "verdict": "CLEAN",
            "findings": [],
        }
        outside = Path(td) / "outside.json"
        outside.write_text(json.dumps(payload), encoding="utf-8")
        (folder / "2026-08-13.json").symlink_to(outside)
        payload["date"] = "2026-08-16"
        cur = folder / "2026-08-16.json"
        cur.write_text(json.dumps(payload), encoding="utf-8")
        r = run([PY, str(SCRIPTS / "drift.py"), str(ws), str(cur)])
        if r.returncode != 0:
            errors.append(f"drift symlink previous should skip, {r.stderr}")
        else:
            data = json.loads(r.stdout)
            if data.get("previous") is not None:
                errors.append(f"symlink previous sidecar should be ignored, got {data.get('previous')}")

    with tempfile.TemporaryDirectory() as td:
        proj = Path(td) / "bigpkg"
        proj.mkdir()
        bogus = "scripts/missing.js"
        pad = "x" * (MAX_READ_BYTES + 1)
        (proj / "package.json").write_text(
            '{"scripts":{"test":"node ' + bogus + '"},"pad":"' + pad + '"}'
        )
        r = run([PY, str(SCRIPTS / "promises.py"), str(proj), str(proj)])
        pdata = json.loads(r.stdout)
        if pdata.get("missing_complete") is not False:
            errors.append(f"large package.json should set missing_complete false, got {pdata}")
        if pdata.get("package_manifest_skipped") is not True:
            errors.append(f"large package.json should set package_manifest_skipped, got {pdata}")

    with tempfile.TemporaryDirectory() as td:
        proj = Path(td) / "prunesym"
        nm = proj / "node_modules" / "pkg"
        nm.mkdir(parents=True)
        (nm / "real.py").write_text("# TODO pruned\n")
        (proj / "alias.py").symlink_to(nm / "real.py")
        r = run([PY, str(SCRIPTS / "inventory.py"), str(proj), str(proj)])
        data = json.loads(r.stdout)
        if data.get("skipped_symlink_unscanned", 0) < 1:
            errors.append(f"pruned symlink target should set skipped_symlink_unscanned, got {data}")
        if data.get("complete_scan") is not False:
            errors.append(f"pruned symlink should set complete_scan false, got {data}")

    with tempfile.TemporaryDirectory() as td:
        proj = Path(td) / "manystub"
        proj.mkdir()
        for i in range(81):
            (proj / f"s{i}.py").write_text("raise NotImplementedError\n")
        r = run([PY, str(SCRIPTS / "stub-scan.py"), str(proj), str(proj)])
        data = json.loads(r.stdout)
        if data.get("truncated") is not True:
            errors.append(f"81 stubs should set truncated, got {data}")
        if data.get("complete_scan") is not False:
            errors.append(f"stub truncation should set complete_scan false, got {data}")

    with tempfile.TemporaryDirectory() as td:
        proj = Path(td) / "manysecret"
        proj.mkdir()
        for i in range(MAX_SECRET_CANDIDATES + 5):
            (proj / f".env.{i}").write_text("x=1\n")
        r = run([PY, str(SCRIPTS / "inventory.py"), str(proj), str(proj)])
        data = json.loads(r.stdout)
        if data.get("secret_candidates_truncated") is not True:
            errors.append(f"secret cap should set secret_candidates_truncated, got {data}")
        if len(data.get("secret_candidates") or []) > MAX_SECRET_CANDIDATES:
            errors.append("secret_candidates list should be capped")
        if data.get("complete_scan") is not False:
            errors.append(f"secret cap should set complete_scan false, got {data}")

    with tempfile.TemporaryDirectory() as td:
        proj = Path(td) / "implarge"
        proj.mkdir()
        (proj / "ok.py").write_text("x=1\n")
        (proj / "huge.py").write_text("# pad\nfrom .ghost import missing\n" + ("x" * (MAX_READ_BYTES + 1)))
        r = run([PY, str(SCRIPTS / "import-sample.py"), str(proj), str(proj)])
        data = json.loads(r.stdout)
        if data.get("truncated") is not True:
            errors.append(f"oversized import file should set truncated, got {data}")
        if data.get("unresolved_complete") is not False:
            errors.append(f"oversized import file should set unresolved_complete false, got {data}")
        orphans = data.get("orphans") or []
        if any(o.endswith("huge.py") or o == "huge.py" for o in orphans):
            errors.append(f"unread huge.py must not be an orphan, got {orphans}")
        if data.get("skipped_large", 0) < 1:
            errors.append(f"oversized import file should set skipped_large, got {data}")

    with tempfile.TemporaryDirectory() as td:
        proj = Path(td) / "docscap"
        proj.mkdir()
        (proj / "README.md").write_text("`src/never-scanned.ts`\n")
        for i in range(201):
            (proj / f"A{i:03d}.md").write_text("# pad\n")
        r = run([PY, str(SCRIPTS / "docs-check.py"), str(proj), str(proj)])
        data = json.loads(r.stdout)
        promised = [x.get("path") for x in data.get("promised_missing") or []]
        if "src/never-scanned.ts" not in promised:
            errors.append(f"README promised path should survive md cap, got {promised}")
        if data.get("truncated") is not True:
            errors.append("201 extra md files should set truncated")

    with tempfile.TemporaryDirectory() as td:
        proj = Path(td) / "eps"
        proj.mkdir()
        for i in range(MAX_ENTRYPOINTS + 5):
            ddir = proj / f"p{i:02d}"
            ddir.mkdir()
            (ddir / "main.py").write_text("x=1\n")
        r = run([PY, str(SCRIPTS / "inventory.py"), str(proj), str(proj)])
        data = json.loads(r.stdout)
        if data.get("entrypoints_truncated") is not True:
            errors.append(f"entrypoint cap should set entrypoints_truncated, got {data}")
        if len(data.get("entrypoints") or []) > MAX_ENTRYPOINTS:
            errors.append("entrypoints list should be capped")
        if data.get("complete_scan") is not False:
            errors.append(f"entrypoint cap should set complete_scan false, got {data}")

    if os.name != "nt":
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / "chmodstub"
            proj.mkdir()
            locked = proj / "locked.py"
            locked.write_text("raise NotImplementedError\n# TODO hidden\n")
            os.chmod(locked, 0)
            try:
                r = run([PY, str(SCRIPTS / "stub-scan.py"), str(proj), str(proj)])
                data = json.loads(r.stdout)
                if data.get("complete_scan") is not False:
                    errors.append(f"unreadable stub file should set complete_scan false, got {data}")
                if data.get("read_skipped_unreadable", 0) < 1:
                    errors.append(f"unreadable stub file should set read_skipped_unreadable, got {data}")
                r2 = run([PY, str(SCRIPTS / "inventory.py"), str(proj), str(proj)])
                data2 = json.loads(r2.stdout)
                if data2.get("complete_scan") is not False:
                    errors.append(f"unreadable TODO file should set complete_scan false, got {data2}")
            finally:
                os.chmod(locked, 0o644)
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / "chmodts"
            proj.mkdir()
            locked = proj / "app.ts"
            locked.write_text("export const x = 1\n")
            os.chmod(locked, 0)
            try:
                r = run([PY, str(SCRIPTS / "promises.py"), str(proj), str(proj)])
                data = json.loads(r.stdout)
                if data.get("read_skipped_unreadable", 0) < 1:
                    errors.append(f"unreadable haystack file should set read_skipped_unreadable, got {data}")
                if data.get("missing_complete") is not False:
                    errors.append(f"unreadable haystack should set missing_complete false, got {data}")
            finally:
                os.chmod(locked, 0o644)

    walk_src = (SCRIPTS / "walk.py").read_text(encoding="utf-8")
    if "path.read_bytes()" in walk_src:
        errors.append("bounded_read_text must not load the whole file via read_bytes()")
    if "MAX_HAYSTACK_BYTES" not in (SCRIPTS / "promises.py").read_text(encoding="utf-8"):
        errors.append("promises haystack must use MAX_HAYSTACK_BYTES")
    if "deadline = time.monotonic()" not in (SCRIPTS / "run.py").read_text(encoding="utf-8"):
        errors.append("run.py must use a shared monotonic deadline")

    src = (SCRIPTS / "check_extra.py").read_text(encoding="utf-8")
    if "timeout=" not in src.split("def run", 1)[-1][:400]:
        errors.append("check_extra.run must pass subprocess timeout")
    if "deadline = time.monotonic()" not in (SCRIPTS / "runtime-check.py").read_text(
        encoding="utf-8"
    ):
        errors.append("runtime-check must use monotonic deadline")

    return errors


if __name__ == "__main__":
    err = extra_errors()
    if err:
        print("; ".join(err))
        raise SystemExit(1)
    print("ok")
