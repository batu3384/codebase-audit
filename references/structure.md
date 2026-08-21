# Phase 1 — Structure

Load only during phase 1. Full-file reads: at most 15 this phase. Do not skip to save tokens.

Bundle keys: `docs-check`, `promises`, plus `inventory` (`top_by_lines`, `entrypoints`). **Do not** re-run scripts.

## Docs links (`docs-check`)

- `broken_links[]` → Docs. Minor. Major if root README **and** install/getting-started href.
- `promised_missing[]` (README backtick paths, including root files like `SKILL.md`) → Docs. Major if main entry; else Minor.
- See `flags.md` for `promised_missing_complete` / `truncated`.

## Promises (`promises`)

- `missing_paths` (CI / package.json script path missing) → Docs or Functional correctness. Major if advertised start/test. Dedup with `promised_missing`.
- `plist_unused` → Docs, Minor. `plist_missing` → Security architecture, Major (single XML Info.plist only).
- See `flags.md` for `missing_complete` / `haystack_truncated`.

## God files

- Source **>800 lines** → Major candidate (Maintainability). Skip generated/minified (`top_by_lines` already excludes).
- Doubt generated → Info only. Hand-read: first 80 + last 40 + defs. `Yön:` split direction, no patch.
- Monorepo: per `package` field.

## Layout

- Entrypoint vs domain vs infra vs UI (`inventory.entrypoints`).
- Duplicate folders, `utils/` dumping ground, missing test pattern → Minor/Info.

## Docs hygiene

- README module with no code path (not in `promised_missing`) → Docs.
- Core package absent from README → Docs, Info.
