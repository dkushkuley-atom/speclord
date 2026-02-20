"""Spec drafter — AI-powered generation of new spec files."""

from __future__ import annotations

from pathlib import Path

from speclord.ai.adapter import LLMAdapter
from speclord.ai.prompts import build_draft_prompt


def draft_spec(
    description: str,
    path: Path,
    root: Path,
    adapter: LLMAdapter,
    *,
    from_code: bool = False,
    spec_type: str | None = None,
) -> str:
    """Draft a new spec file using AI.

    Args:
        description: What the code file does or should do.
        path: Target path for the spec (relative to root, without .spec.md).
        root: Project root directory.
        adapter: The LLM adapter to use for generation.
        from_code: If True, read the existing source file for context.
        spec_type: Optional spec type override (e.g., "api-endpoint").

    Returns:
        The drafted spec content (YAML frontmatter + markdown body).
    """
    root = root.resolve()

    # Build context from existing code if requested
    context: str | None = None
    if from_code:
        code_path = _find_source(path, root)
        if code_path is not None:
            code = code_path.read_text(encoding="utf-8")
            context = (
                f"### Existing source code ({code_path.name}):\n"
                f"```\n{code}\n```"
            )

    # Find a template to guide format
    template = _find_template(spec_type, root)

    # Enrich description with type hint
    full_description = description
    if spec_type:
        full_description = f"[Spec type: {spec_type}]\n\n{description}"

    prompt, system = build_draft_prompt(full_description, template, context)
    return adapter.generate(prompt, system, root)


def _find_source(path: Path, root: Path) -> Path | None:
    """Find an existing source file at the given path.

    Tries the exact path first, then common extensions.
    """
    # If path is absolute, use it directly
    if path.is_absolute():
        candidate = path
    else:
        candidate = root / path

    if candidate.is_file():
        return candidate

    # Try common extensions
    for ext in (".py", ".ts", ".js", ".tsx", ".jsx", ".go", ".rs", ".java", ".rb"):
        attempt = candidate.with_suffix(ext)
        if attempt.is_file():
            return attempt

    return None


def _find_template(spec_type: str | None, root: Path) -> str | None:
    """Find a template spec to use as a format reference.

    Looks in .spec/templates/ for a matching type template,
    then falls back to bundled templates.
    """
    if spec_type is None:
        spec_type = "utility"

    template_name = f"{spec_type}.spec.md"

    # Check project templates first
    project_template = root / ".spec" / "templates" / template_name
    if project_template.is_file():
        return project_template.read_text(encoding="utf-8")

    # Check bundled templates
    bundled = Path(__file__).parent.parent / "templates" / template_name
    if bundled.is_file():
        return bundled.read_text(encoding="utf-8")

    return None
