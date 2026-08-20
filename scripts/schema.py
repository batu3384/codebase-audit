"""Bundle contract for run.py. Coverage flags stay in child JSON (not exit 2)."""
from __future__ import annotations

WALK_KEYS = frozenset(
    {
        "skipped_special",
        "skipped_symlink_dirs",
        "skipped_unreadable",
        "skipped_walk_errors",
        "skipped_symlink_files",
        "skipped_symlink_unscanned",
        "walk_complete",
    }
)

REQUIRED: dict[str, frozenset[str]] = {
    "inventory": frozenset(
        {
            "root",
            "file_count",
            "profile",
            "secret_candidates",
            "secret_candidates_total",
            "secret_candidates_truncated",
            "complete_scan",
            "line_count_truncated",
            "todo_skipped_large",
            "todo_skipped_unreadable",
            "entrypoints_truncated",
        }
    )
    | WALK_KEYS,
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
    )
    | WALK_KEYS,
    "promises": frozenset(
        {
            "root",
            "missing_paths",
            "haystack_truncated",
            "missing_complete",
            "skipped_large",
            "read_skipped_unreadable",
            "package_manifest_skipped",
        }
    )
    | WALK_KEYS,
    "import-sample": frozenset(
        {"root", "unresolved", "orphans", "unresolved_complete", "orphans_complete", "truncated", "skipped_large", "read_skipped_unreadable"}
    )
    | WALK_KEYS,
    "stub-scan": frozenset(
        {"root", "hit_count", "complete_scan", "skipped_large", "truncated", "read_skipped_unreadable"}
    )
    | WALK_KEYS,
    "runtime-check": frozenset({"root", "mode", "plans", "sandbox", "packages_complete"})
    | WALK_KEYS,
}

BOOL_KEYS = frozenset(
    {
        "complete_scan",
        "walk_complete",
        "truncated",
        "sandbox",
        "packages_complete",
        "haystack_truncated",
        "promised_missing_complete",
        "missing_complete",
        "unresolved_complete",
        "orphans_complete",
        "docs_truncated",
        "complete_todo_list",
        "complete_graph",
        "cycles_complete",
        "binary_plist",
        "plist_missing_skipped_multi",
        "generated_excluded_from_top",
        "sample_truncated",
        "package_manifest_skipped",
        "secret_candidates_truncated",
        "entrypoints_truncated",
    }
)

LIST_KEYS = frozenset(
    {
        "plans",
        "broken_links",
        "promised_missing",
        "missing_paths",
        "secret_candidates",
        "unresolved",
        "orphans",
        "hits",
        "todo_samples",
        "entrypoints",
        "docs",
    }
)

INT_NONNEG = frozenset(
    {
        "file_count",
        "skipped_special",
        "skipped_symlink_dirs",
        "skipped_unreadable",
        "skipped_walk_errors",
        "skipped_symlink_files",
        "skipped_symlink_unscanned",
        "skipped_large",
        "skipped_unreadable",
        "line_count_truncated",
        "todo_skipped_large",
        "todo_skipped_unreadable",
        "hit_count",
        "todo_count",
        "unreadable",
        "files_scanned",
        "md_files_seen",
        "md_files_scanned",
        "link_count",
        "haystack_files",
        "missing_count",
        "n",
        "files",
        "skipped_outside_manifests",
        "secret_candidates_total",
        "entrypoints_total",
        "read_skipped_unreadable",
    }
)


def _types(stem: str, blob: dict) -> str | None:
    for k, v in blob.items():
        if k in BOOL_KEYS and not isinstance(v, bool):
            return f"{stem}: {k} must be bool"
        if k in LIST_KEYS and not isinstance(v, list):
            return f"{stem}: {k} must be list"
        if k in INT_NONNEG:
            if type(v) is not int or v < 0:
                return f"{stem}: {k} must be non-negative int"
    if stem == "runtime-check" and blob.get("sandbox") is not False:
        return f"{stem}: sandbox must be false"
    return None


def validate_child(stem: str, blob: object, bundle_root: str | None = None) -> str | None:
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
    typed = _types(stem, blob)
    if typed:
        return typed
    if bundle_root is not None and str(blob.get("root")) != str(bundle_root):
        return f"{stem}: root mismatch"
    return None
