"""Context builder — assembles AI-ready text from the spec chain."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from speclord.resolver import resolve_chain
from speclord.types import FileSpec, OrgSpec, ServiceSpec


def build_context(spec_path: Path, root: Path) -> str:
    """Resolve chain for a file spec and format as AI-ready markdown.

    Walks the inheritance chain (org → service → file) and assembles
    all layers into a single structured markdown string.
    """
    chain = resolve_chain(spec_path, root)
    label = _spec_label(spec_path, root)

    sections: list[str] = [f"# Context: {label}"]

    if chain.org_spec is not None:
        sections.append(_format_org(chain.org_spec))

    if chain.service_spec is not None:
        sections.append(_format_service(chain.service_spec))

    sections.append(_format_file(chain.file_spec))

    return "\n\n".join(sections) + "\n"


def _spec_label(spec_path: Path, root: Path) -> str:
    """Compute a human-readable label from the spec path.

    Returns the path relative to root, without the .spec.md extension.
    """
    try:
        rel = spec_path.resolve().relative_to(root.resolve())
    except ValueError:
        rel = spec_path

    label = str(rel.as_posix())
    if label.endswith(".spec.md"):
        label = label[: -len(".spec.md")]
    return label


def _format_org(org: OrgSpec) -> str:
    """Format the organization constraints section."""
    lines: list[str] = [f"## Organization Constraints ({org.organization})"]

    if org.stack:
        lines.append(f"- **Stack:** {_format_dict(org.stack)}")
    if org.patterns:
        lines.append(f"- **Patterns:** {_format_dict(org.patterns)}")
    if org.security:
        lines.append("- **Security:**")
        for rule in org.security:
            lines.append(f"  - {rule}")

    return "\n".join(lines)


def _format_service(svc: ServiceSpec) -> str:
    """Format the service conventions section."""
    lines: list[str] = [f"## Service Conventions ({svc.service})"]

    lines.append(f"- **Owner:** {svc.owner}")
    if svc.conventions:
        lines.append(f"- **Conventions:** {_format_dict(svc.conventions)}")
    if svc.testing:
        lines.append(f"- **Testing:** {_format_dict(svc.testing)}")
    if svc.security:
        lines.append("- **Security:**")
        for rule in svc.security:
            lines.append(f"  - {rule}")

    return "\n".join(lines)


def _format_file(fs: FileSpec) -> str:
    """Format the file spec section — metadata header + markdown body."""
    lines: list[str] = [f"## File Spec ({fs.type}, {fs.status})"]

    lines.append(f"- **Owner:** {fs.owner}")
    if fs.priority != "normal":
        lines.append(f"- **Priority:** {fs.priority}")
    if fs.generates:
        lines.append(f"- **Generates:** {fs.generates}")
    if fs.dependencies:
        lines.append(f"- **Dependencies:** {', '.join(fs.dependencies)}")

    # Append the markdown body (the spec's actual content)
    body = fs.body.strip()
    if body:
        lines.append("")
        lines.append(body)

    return "\n".join(lines)


def _format_dict(d: dict[str, Any]) -> str:
    """Render a dict as a comma-separated key=value string."""
    return ", ".join(f"{k}={v}" for k, v in d.items())
