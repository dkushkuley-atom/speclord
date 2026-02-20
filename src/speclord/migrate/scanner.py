"""Migration scanner — per-directory spec coverage analysis."""

from __future__ import annotations

from collections import defaultdict
from fnmatch import fnmatch
from pathlib import Path

from speclord.config import SpeclordConfig
from speclord.parser import IGNORE_DIRS
from speclord.types import DirScanEntry, MigrationScan


def scan_codebase(root: Path, config: SpeclordConfig) -> MigrationScan:
    """Scan the codebase for spec coverage grouped by directory.

    Uses the same file-discovery rules as coverage (extensions,
    ignore patterns, __init__.py skip) but groups results by
    parent directory for migration planning.
    """
    root = root.resolve()
    extensions = set(config.coverage_extensions)
    ignore_patterns = config.coverage_ignore

    # Accumulate per-directory stats
    dir_total: defaultdict[str, int] = defaultdict(int)
    dir_specced: defaultdict[str, int] = defaultdict(int)
    dir_unspecced: defaultdict[str, list[str]] = defaultdict(list)

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue

        rel = path.relative_to(root)

        if any(part in IGNORE_DIRS for part in rel.parts):
            continue
        if path.suffix not in extensions:
            continue
        if path.name == "__init__.py":
            continue
        if any(fnmatch(rel.as_posix(), pat) for pat in ignore_patterns):
            continue

        dir_key = rel.parent.as_posix() if rel.parent != Path(".") else "."
        dir_total[dir_key] += 1

        spec_path = path.parent / f"{path.stem}.spec.md"
        if spec_path.exists():
            dir_specced[dir_key] += 1
        else:
            dir_unspecced[dir_key].append(rel.as_posix())

    # Build directory entries sorted by directory name
    all_dirs = sorted(dir_total)
    entries = [
        DirScanEntry(
            directory=d,
            total_files=dir_total[d],
            specced_files=dir_specced.get(d, 0),
            unspecced=dir_unspecced.get(d, []),
        )
        for d in all_dirs
    ]

    total = sum(e.total_files for e in entries)
    specced = sum(e.specced_files for e in entries)

    return MigrationScan(
        total_files=total,
        specced_files=specced,
        unspecced_files=total - specced,
        by_directory=entries,
    )
