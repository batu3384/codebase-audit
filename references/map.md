# Phase 0 — Map

Load only during phase 0.

Measurement already ran via one-shot `run.py`. Use JSON keys `root` and `inventory`. Do not re-run `resolve-root.py` / `inventory.py` unless that key is missing. Fallback commands below (no `rtk` → drop `rtk proxy `).

## Scripts (mandatory keys)

Workspace = opened project root. `AUDIT_PATH` = user path or omit.

```bash
rtk proxy python3 "$HOME/.agents/skills/codebase-audit/scripts/resolve-root.py" "$WORKSPACE" ${AUDIT_PATH:+"$AUDIT_PATH"}
```

Exit 2 → STOP. Exit 0 stdout = `ROOT`. If `AUDIT_PATH` is a **file**, ROOT is its parent directory — say so in the report `Kapsam` line.

```bash
rtk proxy python3 "$HOME/.agents/skills/codebase-audit/scripts/inventory.py" "$WORKSPACE" "$ROOT"
```

Always two args: workspace then ROOT. Exit 2 → STOP. Do not replace with `find` / `wc` / ad-hoc `rg`.

- `file_count == 0` → CLEAN, "no files", stop.
- Docs-only (`file_count > 0`, empty `top_by_lines`) → continue.
- Quote: `root`, `file_count`, `profile` (`primary`, `languages`, `test_kinds`), `todo_count`, `todo_by_file` (top), first 5 `top_by_lines` (include `package`), `secret_candidates` (path + `git` only), `workspace_markers`, `entrypoints`. If `docs_truncated` or `complete_todo_list: false`, say so. If `complete_scan: false` or `walk_complete: false`, quote `skipped_special` / `skipped_symlink_dirs` / `skipped_unreadable` / `skipped_walk_errors` / `skipped_symlink_files` / `line_count_truncated` / `todo_skipped_large` — do not claim a full walk.
- Later phases must follow `profile.primary`. Do not demand pytest on a Swift app or package.json on an Xcode tree.
- God files later: group `top_by_lines` by `package`, not one flat list.

`secret_candidates`: existence + git field only. Do not Read those files. Symlink to a secret **or a symlink pointing outside the tree** is a candidate (`git: outside`); do not follow.

## After inventory

Entrypoints in JSON: do not full-read yet. Includes App.swift / MainActivity / cmd/*/main.go when present.

Monorepo: if `workspace_markers` non-empty, later god-files are **per package**.
