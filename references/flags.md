# Coverage flags (load once — phase 0)

One-shot `run.py` stdout is SSOT. **Do not** re-run child scripts. **Do not** substitute `find` / `wc` / `rg`.

If any required bundle key is missing, or `incomplete` / exit 2 → **EKSİK** (no BLOKE/SORUNLU/TEMİZ).

## Bundle keys (all required on success)

`inventory` · `docs-check` · `promises` · `import-sample` · `stub-scan` · `runtime-check`

Top-level: `workspace`, `root`, `mode`, `measurement` (`skill_version`, `fingerprint`, `keys`, `complete`).

Report header **must** quote: `measurement.skill_version`, `measurement.fingerprint`, `root`, `mode`.

## Walk (every child JSON)

| Flag | Meaning |
|------|---------|
| `walk_complete: false` | Prune/symlink/unreadable walk gap — not exhaustive |
| `skipped_symlink_unscanned` | Symlink into pruned dir — content not scanned |

## Completeness — not CLEAN on that evidence

| Flag | Script |
|------|--------|
| `complete_scan: false` | inventory, stub-scan |
| `truncated: true` | docs-check, import-sample, stub-scan |
| `promised_missing_complete: false` | docs-check |
| `missing_complete: false` | promises |
| `haystack_truncated: true` | promises |
| `unresolved_complete: false` | import-sample |
| `orphans_complete: false` | import-sample |
| `cycles_complete: false` | import-sample |
| `entrypoints_truncated: true` | inventory |
| `packages_complete: false` | runtime-check |

Also: any `skipped_large` > 0, `read_skipped_unreadable` > 0, `todo_skipped_unreadable` > 0, `line_count_truncated` > 0, secret/entrypoint caps.

## Import graph limits

Sampled **js/py/go relative imports only**. Swift/Kotlin/Java module graph **out of scope** — never claim repo-wide acyclic or exhaustive dead-code from `import-sample`.

When `truncated: true` or `orphans_complete: false` → **no** orphan/layer/hub findings.

## Runtime

Default `mode: static`. `--runtime` only if user passed `/codebase-audit --runtime` or explicitly asked to run tests.

`runtime-check.sandbox: false` — command-shape allowlist, not OS isolation. Residual: project test config executes.
