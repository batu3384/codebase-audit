# Phase 2 — Architecture

Load only during phase 2. Full-file reads this phase: at most 15.

This is a **sampled graph**, not a complete program-analysis.

## Import edges (mandatory script)

Do not hand-roll `rg`.

```bash
rtk proxy python3 "$HOME/.agents/skills/codebase-audit/scripts/import-sample.py" "$WORKSPACE" "$ROOT"
```

JSON: `n`, `files`, `sample`, `unresolved`, `cycles`, `orphans`, `orphans_complete`, `layer_hints`, `hubs`, `complete_graph: false`. Kanıt must include `sample: N edges, M files`.

- `cycles` non-empty → Major. Wording: "cycle in relative js/py/go graph", never "repo has no cycles".
- `unresolved` → Major if on an entrypoint path, else Minor.
- `orphans` (js/py/go never imported, not entrypoint/test/`__init__.py`) → Maintainability, Minor. Swift: ignore, `orphan_scope` says so.
- **`orphans_complete: false` / `truncated: true` → do not emit orphan, layer_hints, or hub findings.** Partial graph would invent dead files.
- `layer_hints` UI folder importing data/db folder → Architecture, Major.
- `hubs` (in_edges ≥ 3) → one Maintainability finding, no double-count with god file.
- Bare `import UIKit` / `import os` skipped.
- `truncated: true` → parse file cap; do not pretend completeness.

## Layers

Prefer `layer_hints` from the script. Hand-read only if JSON empty and UI/data folders exist.

- Worker duplicating HTTP handler logic.
- Config parsed in 10 places.

## SPOF / quality attributes (only if visible in code)

- Single process holding all privileges.
- No logging around a trust or money boundary.
- Global mutable singleton everyone writes.

## Not this phase

- C4 diagrams as deliverable.
- Picking a new database.
- "Should have microservices."
- Full call-graph / LSP project index.
