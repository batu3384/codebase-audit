# codebase-audit

Agent Skill — whole-repo (or path-scoped) **architecture and maintainability** audit with evidence-backed findings. No patches, no OWASP/SAST pipeline.

Works on **macOS, Linux, and Windows** (Python 3 only for scripts; default mode is static).

## What you get

- Phased audit: map → structure → architecture → security architecture → completeness → report
- One-shot measurement (`scripts/run.py`) plus drift
- Project report: `docs/codebase-audit/YYYY-MM-DD.md` + JSON sidecar
- Cursor extra: Open canvas (same full report). Other tools: md+json is complete
- Drift across runs via fingerprint (`severity|category|path`), not `CA-NNN` (IDs reset every run)

**Not for:** git-diff persona review (`adversarial-reviewer`), vulnerability hunting (`security-check`), or auto-fixes.

## Requirements

| Need | Required | Notes |
|------|----------|--------|
| Python 3.10+ | yes | `python3`, `python`, or `py -3` |
| One host below | yes | Agent Skills / `$skill` / slash |
| Git | optional | secret `tracked` / `ignored` severity |
| Node / Go / etc. | optional | only for `/codebase-audit --runtime` |
| `rtk` | optional | if present, prefix script commands with `rtk proxy ` |

### Hosts (user-level install)

`~` = home directory (`%USERPROFILE%` on Windows).

| Host | Official user path | `install.sh` / `install.ps1` |
|------|--------------------|------------------------------|
| [Cursor](https://cursor.com/docs/skills) | `~/.agents/skills/` and `~/.cursor/skills/` | copy to agents; link Cursor if `~/.cursor` exists |
| [Claude Code](https://code.claude.com/docs/en/skills) | `~/.claude/skills/<name>/` | link if `~/.claude` exists |
| [Codex](https://learn.chatgpt.com/docs/build-skills) | `$HOME/.agents/skills` | copy only — do **not** write `~/.codex/skills` (installer catalog) |
| [Antigravity](https://antigravity.google/docs/skills) | `~/.gemini/config/skills/<name>/` | link if `~/.gemini/config` exists |

If a host skills directory is already a symlink to `~/.agents/skills`, the extra per-skill link is skipped (does not delete the skill).

**Not installed:** Gemini CLI (`~/.gemini/skills`). Antigravity’s global path lives under `~/.gemini/config/skills` — that folder is Antigravity, not Gemini CLI. Do not put this skill in `~/.gemini/antigravity-cli/skills/` (flat markdown slash files, not Agent Skills folders).

## Install

### Windows (PowerShell)

```powershell
git clone https://github.com/batu3384/codebase-audit.git "$env:USERPROFILE\codebase-audit"
cd "$env:USERPROFILE\codebase-audit"
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

### macOS / Linux

```bash
git clone https://github.com/batu3384/codebase-audit.git ~/codebase-audit
cd ~/codebase-audit
chmod +x install.sh
./install.sh
```

Restart the host (or reload the window).

### Manual

Copy the repo (minus `.git`) to `~/.agents/skills/codebase-audit/` so Cursor and Codex see it. Then, only if that host’s skills dir is a **real directory** (not already a symlink to `~/.agents/skills`):

```text
~/.cursor/skills/codebase-audit      →  ~/.agents/skills/codebase-audit
~/.claude/skills/codebase-audit      →  ~/.agents/skills/codebase-audit
~/.gemini/config/skills/codebase-audit → ~/.agents/skills/codebase-audit
```

Repo root must contain `SKILL.md`, `references/`, `scripts/`.

## Verify

```bash
python3 scripts/self-check.py          # macOS/Linux
python scripts\self-check.py         # Windows
```

Expected output: `ok`

## Usage

```
/codebase-audit
/codebase-audit src/api
/codebase-audit --runtime
```

Codex: `$codebase-audit` or `/skills`. Default is **static**. `--runtime` runs allowlisted `class: executable` test plans (never `make`, `curl`, `xcodebuild`, `gradlew`; no OS sandbox).

Chat: `Sonuç:` + path to `docs/codebase-audit/<date>.md` (+ `.json`). Canvas link only on Cursor after a canvas is written.

## Layout

```text
codebase-audit/
├── SKILL.md
├── references/          # phase guides (loaded on demand)
├── scripts/             # measurement + drift + install_links (Python 3)
├── install.sh
├── install.ps1
└── README.md
```

## Windows notes

- Static audit: full support.
- `--runtime`: uses `sys.executable` for pytest (no hardcoded `python3`). Child process gets an env allowlist (no inherited API keys); stdout/stderr are redacted (JSON/YAML/quoted/bearer). `class: executable` is not an OS sandbox.
- `xcodebuild` / Swift / iOS plans are detected but not executed (same on all OS).
- Canvas files (Cursor): `%USERPROFILE%\.cursor\projects\<workspace-slug>\canvases\`

## v1.3.0

Measurement contract: `run.py` validates child JSON schema (exit 2 on missing keys). Walk skips special files (FIFO) and records skip coverage. Runtime class is `executable` (command allowlist, `sandbox: false`); nested package manifests are discovered. Installer stages + swaps and refuses to delete its source. Redaction covers JSON/YAML quoted keys, bearer tokens, and common token shapes (`sk-`, `AKIA`, `ghp_`, `xox`).

## v1.2.0

User-facing report labels in Turkish; JSON sidecar stays English. One-shot compact `run.py`. Canvas is Cursor-only and is not required for a complete audit. Installer links Claude + Antigravity and refuses to delete a skills dir that is already the agents SSOT.

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
