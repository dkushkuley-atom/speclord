"""Migration progress — track spec adoption over time."""

from __future__ import annotations

import json
from pathlib import Path

from speclord.config import SpeclordConfig
from speclord.migrate.scanner import scan_codebase
from speclord.parser import discover_specs
from speclord.types import ProgressReport


def track_progress(root: Path, config: SpeclordConfig) -> ProgressReport:
    """Compare current spec coverage against the compiled baseline.

    The baseline comes from registry.lock.json (written by ``speclord compile``).
    If no lock file exists, has_baseline is False and baseline_specced is 0.
    """
    root = root.resolve()

    # Current state from scanner
    scan = scan_codebase(root, config)

    # Current spec paths (relative posix)
    current_specs: set[str] = set()
    for path in discover_specs(root):
        if path.name.endswith(".spec.md"):
            try:
                current_specs.add(path.relative_to(root).as_posix())
            except ValueError:
                continue

    # Baseline from registry.lock.json
    lock_path = root / "registry.lock.json"
    has_baseline = lock_path.exists()
    baseline_specs: set[str] = set()

    if has_baseline:
        lock_data = json.loads(lock_path.read_text(encoding="utf-8"))
        baseline_specs = set(lock_data.get("specs", {}).keys())

    # Compare
    new_specs = sorted(current_specs - baseline_specs)
    removed_specs = sorted(baseline_specs - current_specs)

    return ProgressReport(
        current_total=scan.total_files,
        current_specced=scan.specced_files,
        baseline_specced=len(baseline_specs),
        has_baseline=has_baseline,
        new_specs=new_specs,
        removed_specs=removed_specs,
    )
