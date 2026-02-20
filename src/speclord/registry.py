"""Compile specs into a registry lock file."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from speclord.errors import ParseError
from speclord.hasher import hash_content
from speclord.parser import discover_specs, parse_file_spec
from speclord.types import RegistryEntry


def compile_registry(root: Path) -> dict[str, Any]:
    """Discover all specs, parse them, and compile a registry.

    Returns the registry dict and writes registry.lock.json.
    """
    root = root.resolve()
    spec_paths = discover_specs(root)

    entries: list[RegistryEntry] = []
    errors: list[str] = []

    for path in spec_paths:
        # Only index file specs (.spec.md) in the registry
        if path.suffix != ".md":
            continue

        try:
            spec = parse_file_spec(path)
        except ParseError as e:
            errors.append(f"{path}: {e}")
            continue

        content = path.read_text(encoding="utf-8")
        rel_path = path.relative_to(root).as_posix()

        entries.append(RegistryEntry(
            path=rel_path,
            hash=hash_content(content),
            type=spec.type,
            status=spec.status,
            dependencies=spec.dependencies,
            generates=spec.generates,
        ))

    registry: dict[str, Any] = {
        "version": "0.1.0",
        "specs": {e.path: _entry_to_dict(e) for e in entries},
        "errors": errors,
    }

    # Write lock file
    lock_path = root / "registry.lock.json"
    lock_path.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")

    return registry


def _entry_to_dict(entry: RegistryEntry) -> dict[str, Any]:
    """Convert a RegistryEntry to a JSON-serializable dict."""
    d: dict[str, Any] = {
        "hash": entry.hash,
        "type": entry.type,
        "status": entry.status,
        "dependencies": entry.dependencies,
    }
    if entry.generates:
        d["generates"] = entry.generates
    return d
