"""Bundle contract for run.py. Coverage flags stay in child JSON (not exit 2)."""
from __future__ import annotations

REQUIRED: dict[str, frozenset[str]] = {
    "inventory": frozenset(
        {
            "root",
            "file_count",
            "profile",
            "secret_candidates",
            "skipped_special",
            "skipped_symlink_dirs",
            "complete_scan",
        }
    ),
    "docs-check": frozenset(
        {
            "root",
            "broken_links",
            "promised_missing",
            "truncated",
            "promised_missing_complete",
            "skipped_large",
            "unreadable",
        }
    ),
    "promises": frozenset({"root", "missing_paths", "haystack_truncated", "missing_complete"}),
    "import-sample": frozenset(
        {"root", "unresolved", "orphans", "unresolved_complete", "orphans_complete", "truncated"}
    ),
    "stub-scan": frozenset({"root", "hit_count", "complete_scan", "skipped_large"}),
    "runtime-check": frozenset({"root", "mode", "plans", "sandbox"}),
}


def validate_child(stem: str, blob: object) -> str | None:
    if not isinstance(blob, dict):
        return f"{stem}: result is not an object"
    if blob.get("error"):
        return f"{stem}: {blob.get('error')}"
    code = blob.get("exit")
    if code not in (None, 0):
        return f"{stem}: exit {code}"
    need = REQUIRED.get(stem)
    if not need:
        return None
    missing = sorted(need - blob.keys())
    if missing:
        return f"{stem}: missing keys {missing}"
    return None
