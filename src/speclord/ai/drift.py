"""Drift analyzer — AI-powered comparison of specs to source code."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from speclord.ai.adapter import LLMAdapter
from speclord.ai.prompts import build_drift_prompt
from speclord.errors import AIError, ParseError
from speclord.parser import discover_specs, parse_file_spec
from speclord.resolver import resolve_chain
from speclord.types import DriftFinding, DriftReport

# JSON schema the adapter sends to the model
_DRIFT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "spec_section": {"type": "string"},
                    "code_location": {"type": "string"},
                    "description": {"type": "string"},
                    "severity": {
                        "type": "string",
                        "enum": ["error", "warning", "info"],
                    },
                },
            },
        },
    },
}


def analyze_drift(
    spec_path: Path,
    root: Path,
    adapter: LLMAdapter,
) -> DriftReport:
    """Analyze drift between a file spec and its source code.

    Resolves the spec's inheritance chain, reads the code file,
    builds a prompt, and asks the AI to compare them.

    Args:
        spec_path: Path to the .spec.md file.
        root: Project root directory.
        adapter: The LLM adapter to use for analysis.

    Returns:
        A DriftReport with findings.

    Raises:
        AIError: If the code file cannot be found or the AI call fails.
    """
    spec_path = spec_path.resolve()
    root = root.resolve()

    # Parse the file spec
    file_spec = parse_file_spec(spec_path)

    # Find the code file this spec describes
    code_path = _find_code_file(spec_path, file_spec.generates, root)
    if code_path is None or not code_path.exists():
        raise AIError(
            f"Cannot find code file for spec: {spec_path.name}",
            suggestion="Set the 'generates' field in the spec frontmatter.",
        )

    code = code_path.read_text(encoding="utf-8")

    # Resolve the full chain and build the prompt
    chain = resolve_chain(spec_path, root)
    prompt, system = build_drift_prompt(chain, code)

    # Call the AI
    raw = adapter.analyze(prompt, system, root, _DRIFT_SCHEMA)

    # Parse response into DriftReport
    try:
        rel = spec_path.relative_to(root).as_posix()
    except ValueError:
        rel = str(spec_path)

    return _parse_response(rel, raw)


def analyze_all_drift(
    root: Path,
    adapter: LLMAdapter,
) -> list[DriftReport]:
    """Analyze drift for all file specs under root.

    Skips specs whose code file cannot be found (logs a warning).
    """
    root = root.resolve()
    reports: list[DriftReport] = []

    for path in sorted(discover_specs(root)):
        if not path.name.endswith(".spec.md"):
            continue

        try:
            report = analyze_drift(path, root, adapter)
            reports.append(report)
        except (AIError, ParseError):
            # Skip specs that can't be analyzed (no code file, parse error, etc.)
            continue

    return reports


def _find_code_file(
    spec_path: Path,
    generates: str | None,
    root: Path,
) -> Path | None:
    """Locate the source code file for a spec.

    Strategy:
    1. If `generates` is set, resolve relative to root.
    2. Otherwise, strip .spec.md and look for common extensions.
    """
    if generates:
        candidate = root / generates
        if candidate.exists():
            return candidate
        # Also try relative to spec's parent
        candidate = spec_path.parent / generates
        if candidate.exists():
            return candidate

    # Infer from spec path: foo.spec.md -> foo.py, foo.ts, etc.
    stem = spec_path.name
    if stem.endswith(".spec.md"):
        stem = stem[: -len(".spec.md")]

    for ext in (".py", ".ts", ".js", ".tsx", ".jsx", ".go", ".rs", ".rb"):
        candidate = spec_path.parent / f"{stem}{ext}"
        if candidate.exists():
            return candidate

    return None


def _parse_response(spec_path: str, raw: dict[str, Any]) -> DriftReport:
    """Convert the raw AI response dict into a DriftReport."""
    summary = raw.get("summary", "")
    raw_findings = raw.get("findings", [])

    findings: list[DriftFinding] = []
    for f in raw_findings:
        if not isinstance(f, dict):
            continue
        findings.append(
            DriftFinding(
                spec_section=f.get("spec_section", ""),
                code_location=f.get("code_location", ""),
                description=f.get("description", ""),
                severity=f.get("severity", "warning"),
            )
        )

    return DriftReport(
        spec_path=spec_path,
        summary=summary,
        findings=findings,
    )
