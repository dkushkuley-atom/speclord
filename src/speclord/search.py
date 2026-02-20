"""Spec-aware search — text query with field filtering."""

from __future__ import annotations

from pathlib import Path

from speclord.errors import ParseError
from speclord.parser import discover_specs, parse_file_spec
from speclord.types import FileSpec


def search_specs(
    root: Path,
    query: str,
    *,
    type_filter: str | None = None,
    owner_filter: str | None = None,
    status_filter: str | None = None,
) -> list[FileSpec]:
    """Search file specs by text query and optional field filters.

    The query is matched case-insensitively against body text and
    all frontmatter fields. Filters are exact-match constraints
    applied before the text search.
    """
    root = root.resolve()
    results: list[FileSpec] = []

    for path in discover_specs(root):
        if not path.name.endswith(".spec.md"):
            continue
        try:
            spec = parse_file_spec(path)
        except ParseError:
            continue

        # Apply exact-match filters first (cheap)
        if type_filter is not None and spec.type != type_filter:
            continue
        if owner_filter is not None and spec.owner != owner_filter:
            continue
        if status_filter is not None and spec.status != status_filter:
            continue

        # Text search across all fields
        if query and not _matches(spec, query):
            continue

        results.append(spec)

    return results


def _matches(spec: FileSpec, query: str) -> bool:
    """Check if any spec field contains the query (case-insensitive)."""
    q = query.lower()
    searchable = [
        spec.body,
        spec.type,
        spec.owner,
        spec.status,
        spec.generates or "",
        " ".join(spec.dependencies),
        spec.file_path,
    ]
    return any(q in field.lower() for field in searchable)
