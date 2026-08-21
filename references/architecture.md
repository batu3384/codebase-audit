# Phase 2 — Architecture

Load only during phase 2. Full-file reads: at most 15. Do not skip to save tokens.

**Sampled graph** — not LSP, not repo-wide. Bundle key: `import-sample` only. **Do not** hand-roll `rg`.

JSON: `n`, `files`, `sample`, `unresolved`, `unresolved_complete`, `cycles`, `cycles_complete`, `orphans`, `orphans_complete`, `layer_hints`, `hubs`, `complete_graph: false`, `orphan_scope`.

Kanıt must include `sample: N edges, M files`.

## Findings

- `cycles` non-empty → Major ("cycle in relative js/py/go graph"). Never "repo has no cycles".
- `unresolved` → Major on entrypoint path; else Minor. Respect `unresolved_complete`.
- `orphans` → Maintainability, Minor when `orphans_complete: true` and not `truncated`. **Swift/Kotlin/Java: no orphan findings** (`orphan_scope`).
- `layer_hints` UI→data/db → Architecture, Major.
- `hubs` (in_edges ≥ 3) → one Maintainability finding.
- Bare `import UIKit` / `import os` skipped.

When `truncated` or `orphans_complete: false` → **no** orphan, layer, or hub findings.

## Layers (hand-read if JSON empty)

- Worker duplicating HTTP handler logic.
- Config parsed in many places.

## SPOF (only if visible in code)

- Single privileged process, no logging at trust boundary, global mutable singleton.

## Not this phase

C4 diagrams, new database choice, microservices sermon, full call graph.
