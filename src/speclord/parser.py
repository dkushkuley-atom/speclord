"""Spec file parsing — YAML frontmatter + markdown body."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import frontmatter
import yaml

from speclord.errors import ParseError
from speclord.types import FileSpec, OrgSpec, ServiceSpec

# Directories to skip when discovering specs
IGNORE_DIRS = {
    "node_modules",
    ".git",
    "dist",
    "build",
    "coverage",
    ".next",
    "__pycache__",
    ".venv",
    "venv",
    ".eggs",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".spec",
}


def parse_file_spec(path: Path) -> FileSpec:
    """Parse a .spec.md file into a FileSpec.

    Reads the file, extracts YAML frontmatter and markdown body.
    Raises ParseError if the file cannot be parsed or is missing required fields.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        raise ParseError(
            f"Cannot read file: {e}",
            filepath=str(path),
            suggestion="Check the file exists and is readable",
        ) from e

    try:
        post = frontmatter.loads(text)
    except Exception as e:
        raise ParseError(
            f"Invalid frontmatter: {e}",
            filepath=str(path),
            suggestion="Ensure the file has valid YAML between --- delimiters",
        ) from e

    meta: dict[str, Any] = dict(post.metadata)

    # Required fields
    for field in ("specVersion", "inherits", "type", "owner", "status"):
        if field not in meta:
            raise ParseError(
                f"Missing required field: {field}",
                filepath=str(path),
                suggestion=f"Add '{field}' to the YAML frontmatter",
            )

    return FileSpec(
        file_path=_posix(path),
        spec_version=str(meta["specVersion"]),
        inherits=str(meta["inherits"]),
        type=str(meta["type"]),
        owner=str(meta["owner"]),
        status=str(meta["status"]),
        body=post.content,
        priority=str(meta.get("priority", "normal")),
        dependencies=_str_list(meta.get("dependencies", [])),
        generates=str(meta["generates"]) if "generates" in meta else None,
    )


def parse_service_spec(path: Path) -> ServiceSpec:
    """Parse a .spec.yaml service file into a ServiceSpec.

    Raises ParseError if the file cannot be parsed or is missing required fields.
    """
    data = _load_yaml(path)

    for field in ("specVersion", "inherits", "service", "owner"):
        if field not in data:
            raise ParseError(
                f"Missing required field: {field}",
                filepath=str(path),
                suggestion=f"Add '{field}' to the YAML file",
            )

    return ServiceSpec(
        file_path=_posix(path),
        spec_version=str(data["specVersion"]),
        inherits=str(data["inherits"]),
        service=str(data["service"]),
        owner=str(data["owner"]),
        conventions=data.get("conventions", {}),
        dependencies=data.get("dependencies", {}),
        testing=data.get("testing", {}),
        security=_str_list(data.get("security", [])),
        infrastructure=data.get("infrastructure", {}),
    )


def parse_org_spec(path: Path) -> OrgSpec:
    """Parse an org.spec.yaml file into an OrgSpec.

    Raises ParseError if the file cannot be parsed or is missing required fields.
    """
    data = _load_yaml(path)

    for field in ("specVersion", "organization"):
        if field not in data:
            raise ParseError(
                f"Missing required field: {field}",
                filepath=str(path),
                suggestion=f"Add '{field}' to the YAML file",
            )

    return OrgSpec(
        file_path=_posix(path),
        spec_version=str(data["specVersion"]),
        organization=str(data["organization"]),
        stack=data.get("stack", {}),
        patterns=data.get("patterns", {}),
        security=_str_list(data.get("security", [])),
    )


def discover_specs(root: Path) -> list[Path]:
    """Find all spec files under the given root directory.

    Returns sorted list of paths to .spec.md and .spec.yaml files,
    skipping common non-source directories.
    """
    specs: list[Path] = []
    for path in sorted(root.rglob("*")):
        # Skip ignored directories
        if any(part in IGNORE_DIRS for part in path.parts):
            continue
        if path.suffix == ".md" and path.stem.endswith(".spec"):
            specs.append(path)
        elif path.suffix == ".yaml" and path.stem.endswith(".spec"):
            specs.append(path)
        elif path.name == "org.spec.yaml":
            specs.append(path)
    return specs


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load and parse a YAML file."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        raise ParseError(
            f"Cannot read file: {e}",
            filepath=str(path),
            suggestion="Check the file exists and is readable",
        ) from e

    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise ParseError(
            f"Invalid YAML: {e}",
            filepath=str(path),
            suggestion="Fix the YAML syntax",
        ) from e

    if not isinstance(data, dict):
        raise ParseError(
            "Expected a YAML mapping at the top level",
            filepath=str(path),
            suggestion="Ensure the file contains key-value pairs",
        )

    return data


def _posix(path: Path) -> str:
    """Convert a path to POSIX-style string."""
    return path.as_posix()


def _str_list(val: Any) -> list[str]:
    """Coerce a value to a list of strings."""
    if val is None:
        return []
    if isinstance(val, list):
        return [str(v) for v in val]
    return [str(val)]
