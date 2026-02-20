"""Migration planner — phased spec adoption based on dependency structure."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path, PurePosixPath

from speclord.config import SpeclordConfig
from speclord.deps import build_dep_graph
from speclord.migrate.scanner import scan_codebase
from speclord.types import MigrationPhase, MigrationPlan


def plan_migration(root: Path, config: SpeclordConfig) -> MigrationPlan:
    """Generate a phased migration plan for unspecced files.

    Uses the dependency graph to classify directories:
    - Phase 1: "Core" — directories containing specs that other specs
      depend on. These are foundational and should be specced first.
    - Phase 2: "Dependent" — directories containing specs that depend
      on core but aren't depended on themselves. Middle tier.
    - Phase 3: "Leaf" — directories with no specs at all, or specs
      with no dependency relationships. Lowest priority.

    Within each phase, files are sorted alphabetically.
    """
    root = root.resolve()

    # Build dependency graph and scan for unspecced files
    graph = build_dep_graph(root)
    scan = scan_codebase(root, config)

    # Compute which directories contain "core" specs (depended-on by others)
    # and which contain "dependent" specs (depend on others but not depended-on)
    dependents: defaultdict[str, int] = defaultdict(int)
    has_deps: set[str] = set()

    for node, deps in graph.adjacency.items():
        if deps:
            has_deps.add(node)
        for dep in deps:
            dependents[dep] += 1

    # Classify directories based on their specs' roles
    core_dirs: set[str] = set()
    dependent_dirs: set[str] = set()

    for node in graph.adjacency:
        dir_key = str(PurePosixPath(node).parent)
        if dir_key == ".":
            dir_key = "."
        if dependents[node] > 0:
            core_dirs.add(dir_key)
        elif node in has_deps:
            dependent_dirs.add(dir_key)

    # Don't double-classify — core wins over dependent
    dependent_dirs -= core_dirs

    # Collect unspecced files into phases
    phase1_files: list[str] = []
    phase2_files: list[str] = []
    phase3_files: list[str] = []

    for entry in scan.by_directory:
        for f in entry.unspecced:
            if entry.directory in core_dirs:
                phase1_files.append(f)
            elif entry.directory in dependent_dirs:
                phase2_files.append(f)
            else:
                phase3_files.append(f)

    phases: list[MigrationPhase] = []

    if phase1_files:
        phases.append(MigrationPhase(
            name="Core",
            description="Foundational modules that other specs depend on",
            files=sorted(phase1_files),
        ))

    if phase2_files:
        phases.append(MigrationPhase(
            name="Dependent",
            description="Modules that depend on core but are not depended on",
            files=sorted(phase2_files),
        ))

    if phase3_files:
        phases.append(MigrationPhase(
            name="Leaf",
            description="Standalone modules with no dependency relationships",
            files=sorted(phase3_files),
        ))

    return MigrationPlan(phases=phases)
