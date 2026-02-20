"""Structural integrity checker — non-AI drift detection for specs."""

from __future__ import annotations

from pathlib import Path

from speclord.errors import ParseError
from speclord.parser import discover_specs, parse_file_spec
from speclord.types import LintFinding


def check_spec(spec_path: Path, root: Path) -> list[LintFinding]:
    """Run structural checks on a single file spec.

    Validates that the things a spec *references* actually exist:
    generates targets, dependency specs, inherits paths.
    Also flags inconsistent status (e.g., active with empty body).
    """
    spec_path = spec_path.resolve()
    root = root.resolve()

    spec = parse_file_spec(spec_path)
    findings: list[LintFinding] = []

    # 1. Does the generates target actually exist?
    if spec.generates is not None:
        target = root / spec.generates
        if not target.exists():
            findings.append(LintFinding(
                file_path=spec.file_path,
                rule="missing-generates-target",
                message=f"generates target does not exist: {spec.generates}",
            ))

    # 2. Do declared dependencies reference real specs?
    for dep in spec.dependencies:
        dep_path = Path(dep)
        if not dep_path.suffix:
            # Bare name like "types" → sibling "types.spec.md"
            resolved = spec_path.parent / f"{dep_path}.spec.md"
        elif dep_path.suffix == ".md":
            # Already has .md extension
            resolved = spec_path.parent / dep_path
        else:
            # Relative path without .spec.md, e.g. "../config"
            resolved = spec_path.parent / f"{dep_path}.spec.md"

        if not resolved.resolve().exists():
            findings.append(LintFinding(
                file_path=spec.file_path,
                rule="broken-dependency",
                message=f"dependency spec not found: {dep}",
            ))

    # 3. Is the spec status consistent?
    if spec.status == "active" and not spec.body.strip():
        findings.append(LintFinding(
            file_path=spec.file_path,
            rule="active-empty-body",
            message="spec is 'active' but has an empty body",
            severity="warning",
        ))

    # 4. Does the inherits path resolve to a real file?
    inherits_target = (spec_path.parent / spec.inherits).resolve()
    if not inherits_target.exists():
        findings.append(LintFinding(
            file_path=spec.file_path,
            rule="missing-inherits-target",
            message=f"inherits target does not exist: {spec.inherits}",
        ))

    return findings


def check_all(root: Path) -> list[LintFinding]:
    """Discover and check all file specs under root.

    Aggregates findings from all file specs. Parse errors are
    captured as error-severity findings rather than raising.
    """
    root = root.resolve()
    findings: list[LintFinding] = []

    for path in discover_specs(root):
        if not path.name.endswith(".spec.md"):
            continue
        try:
            findings.extend(check_spec(path, root))
        except ParseError as e:
            findings.append(LintFinding(
                file_path=str(path),
                rule="parse-error",
                message=str(e),
            ))

    return findings
