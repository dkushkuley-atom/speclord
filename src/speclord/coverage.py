"""Spec coverage checker — finds code files without corresponding specs."""

from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path

from speclord.config import SpeclordConfig
from speclord.parser import IGNORE_DIRS
from speclord.types import CoverageReport


def check_coverage(root: Path, config: SpeclordConfig) -> CoverageReport:
    """Find code files under root that lack a corresponding .spec.md.

    A file ``src/foo/bar.py`` is considered "specced" if
    ``src/foo/bar.spec.md`` exists as a sibling.

    Respects ``config.coverage_extensions`` for which file extensions to
    scan and ``config.coverage_ignore`` for glob patterns to exclude.
    """
    extensions = set(config.coverage_extensions)
    ignore_patterns = config.coverage_ignore

    total = 0
    specced = 0
    unspecced: list[str] = []

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue

        # Skip ignored directories
        if any(part in IGNORE_DIRS for part in path.relative_to(root).parts):
            continue

        # Only count files with matching extensions
        if path.suffix not in extensions:
            continue

        # Skip __init__.py
        if path.name == "__init__.py":
            continue

        # Check ignore patterns
        rel = path.relative_to(root).as_posix()
        if any(fnmatch(rel, pat) for pat in ignore_patterns):
            continue

        total += 1

        # Check for corresponding spec
        spec_path = path.parent / f"{path.stem}.spec.md"
        if spec_path.exists():
            specced += 1
        else:
            unspecced.append(rel)

    return CoverageReport(
        total_files=total,
        specced_files=specced,
        unspecced=unspecced,
    )
