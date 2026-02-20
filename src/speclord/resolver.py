"""Hierarchical spec chain resolution."""

from __future__ import annotations

from pathlib import Path

from speclord.errors import ParseError, ResolutionError
from speclord.parser import parse_file_spec, parse_org_spec, parse_service_spec
from speclord.types import ResolvedChain


def resolve_chain(spec_path: Path, root: Path) -> ResolvedChain:
    """Resolve the full inheritance chain for a file spec.

    Walks: file spec → (optional) service spec → (optional) org spec.
    The inherits field in each spec is a relative path from the spec's
    location to its parent spec.

    Raises ResolutionError if the chain cannot be resolved.
    """
    spec_path = spec_path.resolve()
    root = root.resolve()

    try:
        file_spec = parse_file_spec(spec_path)
    except ParseError as e:
        raise ResolutionError(
            f"Cannot parse file spec: {e}",
            filepath=str(spec_path),
        ) from e

    # Resolve inherits to find parent spec
    inherits_path = (spec_path.parent / file_spec.inherits).resolve()

    service_spec = None
    org_spec = None

    # If inherits points to a .spec.yaml (not org.spec.yaml), it's a service spec
    if inherits_path.exists():
        if inherits_path.name == "org.spec.yaml":
            try:
                org_spec = parse_org_spec(inherits_path)
            except ParseError as e:
                raise ResolutionError(
                    f"Cannot parse org spec: {e}",
                    filepath=str(inherits_path),
                ) from e
        elif inherits_path.suffix == ".yaml":
            try:
                service_spec = parse_service_spec(inherits_path)
            except ParseError as e:
                raise ResolutionError(
                    f"Cannot parse service spec: {e}",
                    filepath=str(inherits_path),
                ) from e

            # Service spec may also have an inherits pointing to org spec
            if service_spec.inherits:
                org_path = (inherits_path.parent / service_spec.inherits).resolve()
                if org_path.exists() and org_path.name == "org.spec.yaml":
                    try:
                        org_spec = parse_org_spec(org_path)
                    except ParseError as e:
                        raise ResolutionError(
                            f"Cannot parse org spec: {e}",
                            filepath=str(org_path),
                        ) from e

    return ResolvedChain(
        file_spec=file_spec,
        service_spec=service_spec,
        org_spec=org_spec,
    )
