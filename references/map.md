# Phase 0 — Map

Load `references/flags.md` first (same session). Then this file only.

Measurement = one-shot `run.py` stdout. Use keys `root` and `inventory`. **Do not** run `resolve-root.py` or `inventory.py` unless that key is missing from the bundle (then audit is already EKSİK).

## Inventory (bundle key `inventory`)

- `file_count == 0` → TEMİZ, "no files", stop.
- Docs-only (`file_count > 0`, empty `top_by_lines`) → continue.
- Quote: `root`, `file_count`, `profile` (`primary`, `languages`, `test_kinds`), `todo_count`, `todo_by_file` (top), first 5 `top_by_lines` (include `package`), `secret_candidates` (path + `git` only), `workspace_markers`, `entrypoints`.
- If `docs_truncated`, `complete_todo_list: false`, or any flag in `flags.md` → quote it; do not claim a full walk.
- Later phases follow `profile.primary`. No pytest on Swift-primary; no package.json demand on Xcode-only.
- God files later: group `top_by_lines` by `package`.

`secret_candidates`: path + `git` only. Do not Read bodies. Outside symlink → `git: outside`; do not follow.

## After inventory

Entrypoints in JSON only until a phase hand-reads (max 15 full files per phase). Monorepo: god files **per package** when `workspace_markers` non-empty.
