"""AI prompt builders — structured prompts for analysis and generation."""

from __future__ import annotations

from speclord.types import FileSpec, OrgSpec, ResolvedChain, ServiceSpec

# ---------------------------------------------------------------------------
# System prompts (role + constraints)
# ---------------------------------------------------------------------------

_DRIFT_SYSTEM = """\
You are a code compliance auditor for a software project that uses spec files \
to define contracts for each source file. Your job is to compare the spec \
(the intended contract) with the actual code and identify any drift — places \
where the code no longer matches what the spec says it should do.

Rules:
- Focus on behavioral drift, not cosmetic style differences.
- Report each finding with a severity (error, warning, info).
- Be specific: reference function names, line ranges, and spec sections.
- If the code fully satisfies the spec, say so explicitly.
- Return your analysis as structured JSON.\
"""

_REVIEW_SYSTEM = """\
You are a specification quality reviewer. Your job is to evaluate a spec file \
and assess whether it is clear, complete, and useful as a contract for AI-assisted \
development.

Rules:
- Evaluate clarity: could an AI or new developer understand the intended behavior?
- Evaluate completeness: are edge cases, error handling, and interfaces covered?
- Evaluate actionability: does the spec give enough detail to implement or verify?
- Provide a quality score from 0–100.
- Suggest specific improvements.
- Return your review as structured JSON.\
"""

_DRAFT_SYSTEM = """\
You are a technical specification writer. Your job is to produce a high-quality \
spec file in markdown with YAML frontmatter that describes what a code file \
should do.

Rules:
- Follow the spec format: YAML frontmatter (spec_version, type, owner, status, \
inherits, dependencies, generates) followed by a markdown body.
- The body should cover: purpose, interface/API, behavior, edge cases, and \
testing notes.
- Be specific and actionable — the spec is a contract an AI will use to write \
and verify code.
- Do not include implementation details or actual code.
- Output ONLY the spec file content (frontmatter + markdown), nothing else.\
"""


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------


def build_drift_prompt(chain: ResolvedChain, code: str) -> tuple[str, str]:
    """Build a prompt for drift analysis between a spec and its code.

    Args:
        chain: The resolved inheritance chain for the file spec.
        code: The source code content of the file the spec describes.

    Returns:
        A (prompt, system) tuple ready to pass to an LLM adapter.
    """
    sections: list[str] = ["# Drift Analysis Request"]

    # Spec context from the chain
    sections.append(_format_chain(chain))

    # The actual code
    sections.append("## Source Code")
    sections.append(f"```\n{code}\n```")

    # Instructions
    sections.append("## Task")
    sections.append(
        "Compare the spec above with the source code. Identify any drift — "
        "places where the code does not match the spec's contract. For each "
        "finding, provide: the spec section violated, the code location, "
        "a description of the drift, and a severity (error, warning, or info)."
    )

    prompt = "\n\n".join(sections)
    return prompt, _DRIFT_SYSTEM


def build_review_prompt(spec: FileSpec) -> tuple[str, str]:
    """Build a prompt for spec quality review.

    Args:
        spec: The parsed file spec to review.

    Returns:
        A (prompt, system) tuple ready to pass to an LLM adapter.
    """
    sections: list[str] = ["# Spec Review Request"]

    # Spec metadata
    sections.append("## Spec Metadata")
    meta_lines = [
        f"- **File:** {spec.file_path}",
        f"- **Type:** {spec.type}",
        f"- **Status:** {spec.status}",
        f"- **Owner:** {spec.owner}",
        f"- **Priority:** {spec.priority}",
    ]
    if spec.dependencies:
        meta_lines.append(f"- **Dependencies:** {', '.join(spec.dependencies)}")
    if spec.generates:
        meta_lines.append(f"- **Generates:** {spec.generates}")
    sections.append("\n".join(meta_lines))

    # Spec body
    sections.append("## Spec Body")
    body = spec.body.strip()
    if body:
        sections.append(body)
    else:
        sections.append("*(empty — no spec body provided)*")

    # Instructions
    sections.append("## Task")
    sections.append(
        "Review the spec above for quality. Evaluate clarity, completeness, "
        "and actionability. Provide a score from 0–100 and list specific "
        "suggestions for improvement."
    )

    prompt = "\n\n".join(sections)
    return prompt, _REVIEW_SYSTEM


def build_draft_prompt(
    description: str,
    template: str | None = None,
    context: str | None = None,
) -> tuple[str, str]:
    """Build a prompt for drafting a new spec.

    Args:
        description: What the code file does or should do.
        template: Optional example spec to follow as a format reference.
        context: Optional additional context (e.g., related specs, code snippets).

    Returns:
        A (prompt, system) tuple ready to pass to an LLM adapter.
    """
    sections: list[str] = ["# Spec Draft Request"]

    # Description of the target
    sections.append("## Description")
    sections.append(description)

    # Optional template
    if template:
        sections.append("## Template (follow this format)")
        sections.append(f"```markdown\n{template}\n```")

    # Optional context
    if context:
        sections.append("## Additional Context")
        sections.append(context)

    # Instructions
    sections.append("## Task")
    sections.append(
        "Write a complete spec file for the described code file. Include "
        "YAML frontmatter and a detailed markdown body covering purpose, "
        "interface, behavior, edge cases, and testing notes."
    )

    prompt = "\n\n".join(sections)
    return prompt, _DRAFT_SYSTEM


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _format_chain(chain: ResolvedChain) -> str:
    """Format a resolved chain into markdown sections for prompt context."""
    parts: list[str] = []

    if chain.org_spec is not None:
        parts.append(_format_org(chain.org_spec))

    if chain.service_spec is not None:
        parts.append(_format_service(chain.service_spec))

    parts.append(_format_file_spec(chain.file_spec))

    return "\n\n".join(parts)


def _format_org(org: OrgSpec) -> str:
    """Format org spec constraints for prompt context."""
    lines = [f"## Organization Constraints ({org.organization})"]
    if org.stack:
        lines.append(f"- **Stack:** {_kv(org.stack)}")
    if org.patterns:
        lines.append(f"- **Patterns:** {_kv(org.patterns)}")
    if org.security:
        lines.append("- **Security:**")
        for rule in org.security:
            lines.append(f"  - {rule}")
    return "\n".join(lines)


def _format_service(svc: ServiceSpec) -> str:
    """Format service spec conventions for prompt context."""
    lines = [f"## Service Conventions ({svc.service})"]
    lines.append(f"- **Owner:** {svc.owner}")
    if svc.conventions:
        lines.append(f"- **Conventions:** {_kv(svc.conventions)}")
    if svc.testing:
        lines.append(f"- **Testing:** {_kv(svc.testing)}")
    if svc.security:
        lines.append("- **Security:**")
        for rule in svc.security:
            lines.append(f"  - {rule}")
    return "\n".join(lines)


def _format_file_spec(fs: FileSpec) -> str:
    """Format file spec for prompt context."""
    lines = [f"## File Spec ({fs.type}, {fs.status})"]
    lines.append(f"- **Owner:** {fs.owner}")
    lines.append(f"- **Priority:** {fs.priority}")
    if fs.generates:
        lines.append(f"- **Generates:** {fs.generates}")
    if fs.dependencies:
        lines.append(f"- **Dependencies:** {', '.join(fs.dependencies)}")
    body = fs.body.strip()
    if body:
        lines.append("")
        lines.append(body)
    return "\n".join(lines)


def _kv(d: dict[str, object]) -> str:
    """Render dict as comma-separated key=value."""
    return ", ".join(f"{k}={v}" for k, v in d.items())
