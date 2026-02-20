"""Tests for core data types."""

from __future__ import annotations

from speclord.types import (
    VALID_SPEC_TYPES,
    VALID_STATUSES,
    CoverageReport,
    FileSpec,
    LintFinding,
    OrgSpec,
    RegistryEntry,
    ResolvedChain,
    ServiceSpec,
)


class TestFileSpec:
    def test_required_fields(self) -> None:
        spec = FileSpec(
            file_path="src/auth/login.spec.md",
            spec_version="0.1.0",
            inherits="../.spec.yaml",
            type="api-endpoint",
            owner="@auth-team",
            status="active",
            body="## Purpose\nHandles login requests.",
        )
        assert spec.file_path == "src/auth/login.spec.md"
        assert spec.spec_version == "0.1.0"
        assert spec.type == "api-endpoint"
        assert spec.status == "active"

    def test_defaults(self) -> None:
        spec = FileSpec(
            file_path="x.spec.md",
            spec_version="0.1.0",
            inherits=".spec.yaml",
            type="utility",
            owner="@team",
            status="draft",
            body="",
        )
        assert spec.priority == "normal"
        assert spec.dependencies == []
        assert spec.generates is None

    def test_optional_fields(self) -> None:
        spec = FileSpec(
            file_path="x.spec.md",
            spec_version="0.1.0",
            inherits=".spec.yaml",
            type="utility",
            owner="@team",
            status="draft",
            body="body text",
            priority="high",
            dependencies=["other.spec.md"],
            generates="src/x.py",
        )
        assert spec.priority == "high"
        assert spec.dependencies == ["other.spec.md"]
        assert spec.generates == "src/x.py"


class TestServiceSpec:
    def test_required_fields(self) -> None:
        spec = ServiceSpec(
            file_path="packages/auth/.spec.yaml",
            spec_version="0.1.0",
            inherits="../../org.spec.yaml",
            service="auth",
            owner="@auth-team",
        )
        assert spec.service == "auth"
        assert spec.conventions == {}
        assert spec.testing == {}

    def test_with_conventions(self) -> None:
        spec = ServiceSpec(
            file_path="pkg/.spec.yaml",
            spec_version="0.1.0",
            inherits="org.spec.yaml",
            service="core",
            owner="@team",
            conventions={"naming": "snake_case"},
            testing={"coverage": 90},
        )
        assert spec.conventions["naming"] == "snake_case"
        assert spec.testing["coverage"] == 90


class TestOrgSpec:
    def test_required_fields(self) -> None:
        spec = OrgSpec(
            file_path="org.spec.yaml",
            spec_version="0.1.0",
            organization="acme",
        )
        assert spec.organization == "acme"
        assert spec.stack == {}
        assert spec.patterns == {}
        assert spec.security == []

    def test_full(self) -> None:
        spec = OrgSpec(
            file_path="org.spec.yaml",
            spec_version="0.1.0",
            organization="acme",
            stack={"runtime": "python", "language": "python"},
            patterns={"naming": "snake_case"},
            security=["Validate all input"],
        )
        assert spec.stack["runtime"] == "python"
        assert len(spec.security) == 1


class TestLintFinding:
    def test_default_severity(self) -> None:
        finding = LintFinding(
            file_path="x.spec.md",
            rule="missing-field",
            message="Missing specVersion",
        )
        assert finding.severity == "error"

    def test_custom_severity(self) -> None:
        finding = LintFinding(
            file_path="x.spec.md",
            rule="naming",
            message="Non-standard name",
            severity="warning",
        )
        assert finding.severity == "warning"


class TestRegistryEntry:
    def test_basic(self) -> None:
        entry = RegistryEntry(
            path="src/auth/login.spec.md",
            hash="abc123",
            type="api-endpoint",
            status="active",
        )
        assert entry.path == "src/auth/login.spec.md"
        assert entry.dependencies == []
        assert entry.generates is None


class TestResolvedChain:
    def test_file_only(self) -> None:
        file_spec = FileSpec(
            file_path="x.spec.md",
            spec_version="0.1.0",
            inherits=".spec.yaml",
            type="utility",
            owner="@team",
            status="draft",
            body="",
        )
        chain = ResolvedChain(file_spec=file_spec)
        assert chain.file_spec == file_spec
        assert chain.service_spec is None
        assert chain.org_spec is None

    def test_full_chain(self) -> None:
        org = OrgSpec(file_path="org.spec.yaml", spec_version="0.1.0", organization="acme")
        svc = ServiceSpec(
            file_path=".spec.yaml",
            spec_version="0.1.0",
            inherits="org.spec.yaml",
            service="auth",
            owner="@team",
        )
        f = FileSpec(
            file_path="x.spec.md",
            spec_version="0.1.0",
            inherits=".spec.yaml",
            type="utility",
            owner="@team",
            status="draft",
            body="",
        )
        chain = ResolvedChain(file_spec=f, service_spec=svc, org_spec=org)
        assert chain.org_spec is not None
        assert chain.service_spec is not None


class TestCoverageReport:
    def test_full_coverage(self) -> None:
        report = CoverageReport(total_files=10, specced_files=10)
        assert report.coverage_pct == 100.0

    def test_partial_coverage(self) -> None:
        report = CoverageReport(total_files=10, specced_files=7, unspecced=["a", "b", "c"])
        assert report.coverage_pct == 70.0

    def test_zero_files(self) -> None:
        report = CoverageReport(total_files=0, specced_files=0)
        assert report.coverage_pct == 100.0

    def test_no_coverage(self) -> None:
        report = CoverageReport(total_files=5, specced_files=0, unspecced=["a", "b", "c", "d", "e"])
        assert report.coverage_pct == 0.0


class TestConstants:
    def test_valid_spec_types(self) -> None:
        assert "api-endpoint" in VALID_SPEC_TYPES
        assert "data-model" in VALID_SPEC_TYPES
        assert "utility" in VALID_SPEC_TYPES
        assert len(VALID_SPEC_TYPES) == 15

    def test_valid_statuses(self) -> None:
        assert "draft" in VALID_STATUSES
        assert "active" in VALID_STATUSES
        assert "deprecated" in VALID_STATUSES
        assert "archived" in VALID_STATUSES
        assert len(VALID_STATUSES) == 4
