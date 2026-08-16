# codebase-audit

Cursor Agent Skill — whole-repo (or path-scoped) **architecture and maintainability** audit with evidence-backed findings. No patches, no OWASP/SAST pipeline.

Works on **macOS, Linux, and Windows** (Python 3 only for scripts; default mode is static).

## What you get

- Phased audit: map → structure → architecture → security architecture → completeness → report
- Bundled measurement scripts (`inventory`, `docs-check`, `promises`, `import-sample`, `stub-scan`, `runtime-check`, `drift`)
- Project report: `docs/codebase-audit/YYYY-MM-DD.md` + JSON sidecar + Open canvas
- Drift across runs via fingerprint (`severity|category|path`), not `CA-NNN` (IDs reset every run)

**Not for:** git-diff persona review (`adversarial-reviewer`), vulnerability hunting (`security-check`), or auto-fixes.

## Requirements

| Tool | Required | Notes |
|------|----------|--------|
| [Cursor](https://cursor.com) | yes | Agent Skills enabled |
| Python 3.10+ | yes | `python` or `py -3` on Windows |
| Git | optional | secret `tracked` / `ignored` severity |
| Node / Go / etc. | optional | only for `/codebase-audit --runtime` |

## Install

### Windows (PowerShell)

```powershell
git clone https://github.com/batu3384/codebase-audit.git "$env:USERPROFILE\codebase-audit"
cd "$env:USERPROFILE\codebase-audit"
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

Restart Cursor (or reload window). Skill path:

- `%USERPROFILE%\.agents\skills\codebase-audit`
- `%USERPROFILE%\.cursor\skills\codebase-audit` (junction → agents)

### macOS / Linux

```bash
git clone https://github.com/batu3384/codebase-audit.git ~/codebase-audit
cd ~/codebase-audit
chmod +x install.sh
./install.sh
```

### Manual (any OS)

Clone into Cursor skills directory:

```text
~/.cursor/skills/codebase-audit/     # macOS/Linux
%USERPROFILE%\.cursor\skills\codebase-audit\   # Windows
```

Repo root must contain `SKILL.md`, `references/`, `scripts/`.

## Verify

```bash
python3 scripts/self-check.py          # macOS/Linux
python scripts\self-check.py         # Windows
```

Expected output: `ok`

## Usage in Cursor

```
/codebase-audit
/codebase-audit src/api
/codebase-audit --runtime
```

Default is **static** (scripts only). `--runtime` runs allowlisted safe test plans (never `make`, `curl`, `xcodebuild`, `gradlew`).

Chat output: verdict + path to `docs/codebase-audit/<date>.md` (+ `.json`) + canvas link.

## Layout

```text
codebase-audit/
├── SKILL.md
├── references/          # phase guides (loaded on demand)
├── scripts/             # measurement + drift (Python 3)
├── install.sh
├── install.ps1
└── README.md
```

## Windows notes

- Static audit: full support.
- `--runtime`: uses `sys.executable` for pytest (no hardcoded `python3`). Child process gets an env allowlist (no inherited API keys); stdout/stderr are redacted.
- `xcodebuild` / Swift / iOS plans are detected but not executed (same on all OS).
- Canvas files: `%USERPROFILE%\.cursor\projects\<workspace-slug>\canvases\`

## v1.1.0

Measurement honesty: list/parse caps now set `*_complete: false` instead of silent truncation. Outside-tree symlinks are secret **candidates** (body unread). `run.py` fails closed on unexpected script errors. Drift matches `root` + filename date. `--runtime` env allowlist + output redaction.

## Update

```bash
cd ~/codebase-audit   # or your clone path
git pull
./install.sh          # or install.ps1 on Windows
```

## License

MIT — see [LICENSE](LICENSE).
