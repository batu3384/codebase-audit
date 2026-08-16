# Phase 5 — Report (project file + canvas)

Load only during phase 5. Analysis is done. Do not rescan. Do not apply fixes.

Model: **writing-plans**. That skill does `docs/superpowers/plans/YYYY-MM-DD-<name>.md` in the opened repo. This skill does the same job for audit reports:

```
$WORKSPACE/docs/codebase-audit/YYYY-MM-DD.md
$WORKSPACE/docs/codebase-audit/YYYY-MM-DD.json
```

`$WORKSPACE` = opened project. Shop açık → `shop/docs/codebase-audit/`. Entegrasyon yalnız entegrasyon taranıyorsa. Skill source stays in `~/.agents/skills/` — do not copy the skill into the repo.

## 1. Project file (required — this is the report)

Path-scoped audit still files at workspace `docs/codebase-audit/`; put the subpath in the header.

If `YYYY-MM-DD.md` exists: `YYYY-MM-DD-HHMM.md` **and** matching `.json`. Do not overwrite. Markdown and JSON share the same stem.

```bash
rtk mkdir -p "$WORKSPACE/docs/codebase-audit"
```

Then Write the markdown. No README, no index, no `audit-report/`.

### Markdown shape

Türkçe. Letters: **ı, ğ, ü, ş, ö, ç, İ**. Path, `CA-001`, severity, verdict English kalır. Secret **değer** yok.

```markdown
# Kod tabanı denetimi — <workspace basename>

- Tarih: YYYY-MM-DD
- Kapsam: <ROOT> (file path given → parent directory)
- Runtime: static | --runtime
- Verdict: BLOCK | CONCERNS | CLEAN
- Envanter: file_count, todo_count (script stdout)

## Özet

| Kod | Seviye | Konu | Yol |
|-----|--------|------|-----|
| CA-001 | Critical | … | path[:line] |

## CA-001 | Critical | Category | path[:line]

**Kanıt:** …
**Neden:** …
**Yön:** …
```

All Critical and all Major. Then ≤40 Minor/Trivial/Info. Incomplete audit: md+json yok.

## Önerilen sıra (required)

After findings, a short backlog. Not new CA-NNN. Rank: all Critical, then Major, then the most useful Minor (max 5 lines).

```markdown
## Önerilen sıra

1. CA-001 — …
2. CA-003 — …
```

Each line: ID + one Turkish sentence (what to do). Same as `Yön`, not a patch.

## Sidecar JSON (required — same stem as markdown)

Write **before** `drift.py`. No Kanıt, no secret values, no finding bodies. `id` is this-run only.

```json
{
  "schema": 1,
  "skill": "codebase-audit",
  "date": "YYYY-MM-DD",
  "root": "<ROOT>",
  "verdict": "BLOCK",
  "runtime": "static",
  "findings": [
    {"id": "CA-001", "severity": "Critical", "category": "Maintainability", "path": "src/foo.py"}
  ]
}
```

`path` may include `:line`; fingerprint strips `:\d+$`. Duplicate fingerprints in one file collapse to one. `date` must match the filename `YYYY-MM-DD`. `root` is required; `drift.py` only compares sidecars with the same canonical root (`skipped_root`).

```bash
rtk proxy python3 "$HOME/.agents/skills/codebase-audit/scripts/drift.py" "$WORKSPACE" "$WORKSPACE/docs/codebase-audit/YYYY-MM-DD.json"
```

Exit 2 (missing/bad **current** sidecar, sandbox, undated filename, date/filename mismatch, missing `root`) → incomplete, not CLEAN. Corrupt **previous** files are skipped (`skipped_corrupt`); different `root` is skipped (`skipped_root`); do not abort.

## Drift (from drift.py stdout)

Do **not** compare CA-NNN across runs. Use `counts` + `added`/`removed`. First run (`previous: null`): omit this section. Else:

```markdown
## Drift

Önceki: <previous filename>
Yeni: N · Gitti: N · Aynı: N
```

Then at most 10 added + 10 removed lines: severity, category, path (not fingerprint, not old CA-NNN). If `counts.added` > 40, say the extra count. Info only — drift does not change verdict.

## 2. Canvas (required, view)

Write **one** `.canvas.tsx`. Do not mkdir canvases/.

```
/Users/<user>/.cursor/projects/<workspace-slug>/canvases/codebase-audit-YYYY-MM-DD.canvas.tsx
```

`<workspace-slug>` = Cursor folder for **this** `$WORKSPACE`. List `~/.cursor/projects/` if unsure. Do not guess entegrasyon.

Same-day canvas collision: suffix `-HHMM` like the markdown.

### File rules (Cursor canvas SDK)

- Import **only** `cursor/canvas`. No relative imports, no npm, no fetch.
- Default-export one React function. Embed **this** run inline. No placeholders.
- No gradients, no emoji, no box-shadow, no hex colors.
- Omit empty sections.

Read `~/.cursor/skills-cursor/canvas/SKILL.md` if needed. Prefer: `Stack`, `H1`, `H2`, `Text`, `Callout`, `Grid`, `Stat`, `Table`, `CollapsibleSection`, `Code`, `Row`.

### Layout

1. `H1`: `Kod tabanı denetimi` + basename.
2. `Text tone="secondary"`: ROOT, tarih, runtime, file_count, todo_count. Secret değer yok.
3. Verdict `Callout`: BLOCK `danger`, CONCERNS `warning`, CLEAN `success`. Incomplete → warning, no verdict.
4. `Grid columns={4}` Stat: Verdict, Critical, Major, dosya.
5. `Table`: `Kod`, `Seviye`, `Konu`, `Yol`. `rowTone`: Critical `danger`, Major `warning`, Info `info`.
6. Tane tane `CollapsibleSection` — Critical `defaultOpen`. Kanıt / Neden / Yön.
7. `H2` `Önerilen sıra` — en fazla 5 satır, CA-NNN + cümle. Tablo veya kısa `Text`.
8. Drift varsa `Text size="small"`: önceki dosya adı + yeni/gitti/aynı **sayıları** (`drift.py` counts). CA-NNN kıyaslama yok.
9. `Text size="small" tone="tertiary"`: `Kaynak: run.py + drift.py sidecar`.

## Chat (after md + json + canvas exist)

Short. No finding dump. Lead with the project path (writing-plans style).

```
Verdict: CONCERNS
Rapor kaydedildi: docs/codebase-audit/YYYY-MM-DD.md (+ .json)
Canvas: Open canvas — absolute path to the `.canvas.tsx` file
Aynı sohbet: düzelt CA-001
```

First canvas in that `canvases/` folder: one sentence — sağda Open canvas.

## Forbidden

- Copying this skill into the scanned repo.
- Writing the archive into entegrasyon / `~/.agents` / `$HOME` unless that **is** `$WORKSPACE`.
- Overwriting yesterday’s or today’s existing dated file.
- Fake findings. Secret file bodies.
- Diffing CA-NNN across old markdown (IDs reset each run).
