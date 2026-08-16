# codebase-audit

**Multi-host Agent Skill** for whole-repo (or path-scoped) architecture and maintainability audits — evidence-backed findings, no auto-fixes, no OWASP/SAST pipeline.

Runs on **macOS, Linux, and Windows**. Measurement is **Python 3.10+** scripts; default mode is **static** (no test execution).

## Overview

The skill drives a phased review: map → structure → architecture → security architecture → completeness → report. Measurement is **one-shot** (`scripts/run.py`); the agent cites script stdout (`path:line`, JSON flags) instead of improvising with `find`, `wc`, or ad-hoc `rg`.

| Delivers | Does not |
|----------|----------|
| `docs/codebase-audit/YYYY-MM-DD.md` + JSON sidecar | Apply patches or open PRs |
| Drift vs previous run (`scripts/drift.py`) | Replace `adversarial-reviewer` (git-diff personas) |
| Optional `--runtime` test plans (opt-in) | Replace `security-check` (vuln hunting) |

Reports use Turkish labels in chat/markdown (`BLOKE` / `SORUNLU` / `TEMİZ`); the JSON sidecar keeps English enums.

## Supported hosts

One install targets every Agent Skills–compatible host below. **SSOT** (single copy) lives at:

```text
~/.agents/skills/codebase-audit/     # macOS/Linux
%USERPROFILE%\.agents\skills\codebase-audit\   # Windows
```

`install.sh` / `install.ps1` copy into that path, then link per-host directories when they exist and are not already symlinks to `~/.agents/skills`.

| Host | Invoke | Skills path | Installer |
|------|--------|-------------|-----------|
| [Cursor](https://cursor.com/docs/skills) | `/codebase-audit`, `/codebase-audit src/api`, `--runtime` | `~/.cursor/skills/` → SSOT (or SSOT only if `~/.cursor/skills` already points at `~/.agents/skills`) | link when `~/.cursor` exists |
| [Claude Code](https://code.claude.com/docs/en/skills) | same slash pattern | `~/.claude/skills/codebase-audit/` | link when `~/.claude` exists |
| [Codex](https://learn.chatgpt.com/docs/build-skills) | `$codebase-audit` or `/skills` | reads `~/.agents/skills` directly | copy only — **do not** write `~/.codex/skills` (installer catalog) |
| [Antigravity](https://antigravity.google/docs/skills) | host slash / skills UI | `~/.gemini/config/skills/codebase-audit/` | link when `~/.gemini/config` exists |

**Not this skill:** Gemini CLI (`~/.gemini/skills`), Antigravity CLI flat slash folder (`~/.gemini/antigravity-cli/skills/`). Antigravity’s Agent Skills path is `~/.gemini/config/skills`, not Gemini CLI.

After install, restart or reload the host so it picks up `SKILL.md`.

## Requirements

| Item | Required | Notes |
|------|----------|--------|
| Python 3.10+ | yes | `python3`, `python`, or `py -3` on Windows |
| One supported host above | yes | Agent Skills / slash / `$skill` |
| Git | optional | `tracked` / `ignored` on secret candidates |
| Node, Go, Rust, etc. | optional | only if you pass `--runtime` |
| `rtk` | optional | prefix script commands with `rtk proxy ` when present |

## Install

### macOS / Linux

```bash
git clone https://github.com/batu3384/codebase-audit.git ~/codebase-audit
cd ~/codebase-audit
chmod +x install.sh
./install.sh
```

### Windows (PowerShell)

```powershell
git clone https://github.com/batu3384/codebase-audit.git "$env:USERPROFILE\codebase-audit"
cd "$env:USERPROFILE\codebase-audit"
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

Override SSOT parent: `AGENTS_DIR=/path/to/skills ./install.sh` (directory that will contain `codebase-audit/`).

### Manual

1. Copy the repo (without `.git`) to `~/.agents/skills/codebase-audit/`.
2. If a host’s skills folder is a **real directory** (not already `~/.agents/skills`), symlink:

```text
~/.cursor/skills/codebase-audit           →  ~/.agents/skills/codebase-audit
~/.claude/skills/codebase-audit           →  ~/.agents/skills/codebase-audit
~/.gemini/config/skills/codebase-audit    →  ~/.agents/skills/codebase-audit
```

Package root must contain `SKILL.md`, `references/`, `scripts/`.

## Verify

```bash
python3 scripts/self-check.py          # macOS / Linux
python scripts\self-check.py         # Windows
```

Expected: `ok`

Smoke the bundle (optional):

```bash
python3 scripts/run.py /path/to/your/project
```

Exit `0` and compact JSON with keys `inventory`, `docs-check`, `promises`, `import-sample`, `stub-scan`, `runtime-check`.

## Usage

Default is **static** — scripts measure the tree; they do not run project tests unless you opt in.

| Host | Examples |
|------|----------|
| Cursor / Claude Code | `/codebase-audit` · `/codebase-audit packages/api` · `/codebase-audit --runtime` |
| Codex | `$codebase-audit` · add path or `--runtime` in the skill invocation |

`--runtime` maps to `run.py --run`: every `class: executable` plan (npm / go / cargo / pytest / swift / dart). Never `make`, `curl`, `xcodebuild`, or `gradlew`. `sandbox: false` — command-shape allowlist, not OS isolation. Child env is an allowlist; stdout/stderr are redacted.

### Reports (all hosts)

Every complete run writes:

- `docs/codebase-audit/YYYY-MM-DD.md` — human report  
- `docs/codebase-audit/YYYY-MM-DD.json` — findings sidecar (English severity enums)  
- Drift block from `scripts/drift.py` when a prior sidecar exists  

Same-day collision: `YYYY-MM-DD-HHMM.md` + matching `.json`.

### Optional: Cursor canvas

On **Cursor only**, the agent may also write a `.canvas.tsx` beside the project (full report, same content as markdown). That file is an extra view — **md + json alone are a complete audit** on Claude Code, Codex, Antigravity, and Cursor. Missing canvas is not incomplete.

Canvas path pattern: `~/.cursor/projects/<workspace-slug>/canvases/codebase-audit-YYYY-MM-DD.canvas.tsx`

## Layout

```text
codebase-audit/
├── SKILL.md              # skill contract (hosts load this)
├── references/           # phase guides (on demand)
├── scripts/
│   ├── run.py            # one-shot bundle
│   ├── schema.py         # child JSON contract
│   ├── install.py        # SSOT copy + staging
│   ├── install_links.py  # per-host symlinks
│   ├── self-check.py     # health checks
│   ├── check_extra.py    # extended probes
│   └── …                 # inventory, docs-check, promises, import-sample, stub-scan, runtime-check, drift, walk, paths
├── install.sh
├── install.ps1
└── README.md
```

## Platform notes

- **Static audit:** full support on all listed OSes.
- **Windows `--runtime`:** pytest via `sys.executable` (no hardcoded `python3`); timeout cleanup uses `taskkill /T`.
- **iOS / Xcode:** `xcodebuild` and CocoaPods plans are detected but not executed on any OS.
- **Untrusted trees:** outside symlinks are not followed; manifest bodies are not read across the trust boundary.

## Update

```bash
cd ~/codebase-audit    # or your clone path
git pull
./install.sh           # or install.ps1 on Windows
```

## Changelog

**v1.3.3** — Bounded manifest reads (`bounded_read_text`); promises/inventory/runtime share 2 MB cap; `skipped_symlink_unscanned` fails `walk_complete`; stub truncation fails `complete_scan`; secret candidate cap (200); resolve-root 30s timeout; self-check env probe uses bounded helper.

**v1.3.2** — Manifest shape guards (no child crash on odd JSON); runtime plan bodies redacted; in-tree file symlinks counted once; host-link frontmatter ownership + home containment; self-check timeouts; monotonic `--run` deadline; drift ignores sidecar symlinks.

**v1.3.1** — Fail-closed outside symlink manifests; `WalkCover` on every child JSON; installer symlink guards; schema type checks; Windows `taskkill /T`.

**v1.3.0** — Child JSON schema validation; nested package discovery; `executable` runtime class; expanded redaction; staged install.

Earlier: v1.2 (Turkish report face, one-shot `run.py`, multi-host install), v1.1 (truncation honesty, drift `root` match).

## License

MIT — see [LICENSE](LICENSE).
