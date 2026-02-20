"""Spec validation and linting rules."""

from __future__ import annotations

from pathlib import Path

from speclord.errors import ParseError
from speclord.parser import discover_specs, parse_file_spec, parse_org_spec, parse_service_spec
from speclord.types import (
    VALID_SPEC_TYPES,
    VALID_STATUSES,
    FileSpec,
    LintFinding,
    OrgSpec,
    ServiceSpec,
)


def validate_file_spec(spec: FileSpec) -> list[LintFinding]:
    """Validate a parsed file spec. Returns a list of findings."""
    findings: list[LintFinding] = []

    if spec.type not in VALID_SPEC_TYPES:
        findings.append(LintFinding(
            file_path=spec.file_path,
            rule="invalid-type",
            message=(
                f"Unknown spec type: '{spec.type}'. "
                f"Must be one of: {', '.join(sorted(VALID_SPEC_TYPES))}"
            ),
        ))

    if spec.status not in VALID_STATUSES:
        findings.append(LintFinding(
            file_path=spec.file_path,
            rule="invalid-status",
            message=(
                f"Unknown status: '{spec.status}'. "
                f"Must be one of: {', '.join(sorted(VALID_STATUSES))}"
            ),
        ))

    if not spec.spec_version:
        findings.append(LintFinding(
            file_path=spec.file_path,
            rule="missing-version",
            message="specVersion is empty",
        ))

    if not spec.inherits:
        findings.append(LintFinding(
            file_path=spec.file_path,
            rule="missing-inherits",
            message="inherits is empty",
        ))

    if not spec.owner:
        findings.append(LintFinding(
            file_path=spec.file_path,
            rule="missing-owner",
            message="owner is empty",
        ))

    if not spec.body.strip():
        findings.append(LintFinding(
            file_path=spec.file_path,
            rule="empty-body",
            message="Spec body is empty — add at least a ## Purpose section",
            severity="warning",
        ))

    return findings


def validate_service_spec(spec: ServiceSpec) -> list[LintFinding]:
    """Validate a parsed service spec. Returns a list of findings."""
    findings: list[LintFinding] = []

    if not spec.spec_version:
        findings.append(LintFinding(
            file_path=spec.file_path,
            rule="missing-version",
            message="specVersion is empty",
        ))

    if not spec.inherits:
        findings.append(LintFinding(
            file_path=spec.file_path,
            rule="missing-inherits",
            message="inherits is empty",
        ))

    if not spec.service:
        findings.append(LintFinding(
            file_path=spec.file_path,
            rule="missing-service",
            message="service name is empty",
        ))

    if not spec.owner:
        findings.append(LintFinding(
            file_path=spec.file_path,
            rule="missing-owner",
            message="owner is empty",
        ))

    return findings


def validate_org_spec(spec: OrgSpec) -> list[LintFinding]:
    """Validate a parsed org spec. Returns a list of findings."""
    findings: list[LintFinding] = []

    if not spec.spec_version:
        findings.append(LintFinding(
            file_path=spec.file_path,
            rule="missing-version",
            message="specVersion is empty",
        ))

    if not spec.organization:
        findings.append(LintFinding(
            file_path=spec.file_path,
            rule="missing-organization",
            message="organization is empty",
        ))

    if not spec.stack:
        findings.append(LintFinding(
            file_path=spec.file_path,
            rule="missing-stack",
            message="stack is empty — define at least runtime and language",
            severity="warning",
        ))

    if not spec.security:
        findings.append(LintFinding(
            file_path=spec.file_path,
            rule="missing-security",
            message="security rules are empty",
            severity="warning",
        ))

    return findings


def lint_all(root: Path) -> list[LintFinding]:
    """Discover and validate all specs under the given root.

    Returns a combined list of findings from all spec files.
    Parse errors are captured as error-severity findings.
    """
    findings: list[LintFinding] = []
    spec_paths = discover_specs(root)

    for path in spec_paths:
        try:
            if path.name == "org.spec.yaml":
                org = parse_org_spec(path)
                findings.extend(validate_org_spec(org))
            elif path.suffix == ".yaml":
                svc = parse_service_spec(path)
                findings.extend(validate_service_spec(svc))
            elif path.suffix == ".md":
                fs = parse_file_spec(path)
                findings.extend(validate_file_spec(fs))
        except ParseError as e:
            findings.append(LintFinding(
                file_path=str(path),
                rule="parse-error",
                message=str(e),
            ))

    return findings
