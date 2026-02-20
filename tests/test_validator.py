"""Tests for spec validation and linting."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from speclord.cli import main
from speclord.types import FileSpec, OrgSpec, ServiceSpec
from speclord.validator import (
    lint_all,
    validate_file_spec,
    validate_org_spec,
    validate_service_spec,
)


def _file_spec(**overrides: object) -> FileSpec:
    """Create a FileSpec with sensible defaults, overriding as needed."""
    defaults = {
        "file_path": "test.spec.md",
        "spec_version": "0.1.0",
        "inherits": ".spec.yaml",
        "type": "utility",
        "owner": "@team",
        "status": "draft",
        "body": "## Purpose\nDoes something.",
    }
    defaults.update(overrides)
    return FileSpec(**defaults)  # type: ignore[arg-type]


def _service_spec(**overrides: object) -> ServiceSpec:
    defaults = {
        "file_path": ".spec.yaml",
        "spec_version": "0.1.0",
        "inherits": "org.spec.yaml",
        "service": "auth",
        "owner": "@team",
    }
    defaults.update(overrides)
    return ServiceSpec(**defaults)  # type: ignore[arg-type]


def _org_spec(**overrides: object) -> OrgSpec:
    defaults = {
        "file_path": "org.spec.yaml",
        "spec_version": "0.1.0",
        "organization": "acme",
        "stack": {"runtime": "python"},
        "security": ["Validate input"],
    }
    defaults.update(overrides)
    return OrgSpec(**defaults)  # type: ignore[arg-type]


class TestValidateFileSpec:
    def test_valid_spec_no_findings(self) -> None:
        findings = validate_file_spec(_file_spec())
        assert findings == []

    def test_invalid_type(self) -> None:
        findings = validate_file_spec(_file_spec(type="banana"))
        assert len(findings) == 1
        assert findings[0].rule == "invalid-type"
        assert findings[0].severity == "error"

    def test_invalid_status(self) -> None:
        findings = validate_file_spec(_file_spec(status="implemented"))
        assert len(findings) == 1
        assert findings[0].rule == "invalid-status"

    def test_empty_body_warning(self) -> None:
        findings = validate_file_spec(_file_spec(body=""))
        assert len(findings) == 1
        assert findings[0].rule == "empty-body"
        assert findings[0].severity == "warning"

    def test_whitespace_only_body_warning(self) -> None:
        findings = validate_file_spec(_file_spec(body="   \n\n  "))
        assert len(findings) == 1
        assert findings[0].rule == "empty-body"

    def test_empty_owner(self) -> None:
        findings = validate_file_spec(_file_spec(owner=""))
        assert any(f.rule == "missing-owner" for f in findings)

    def test_empty_inherits(self) -> None:
        findings = validate_file_spec(_file_spec(inherits=""))
        assert any(f.rule == "missing-inherits" for f in findings)

    def test_multiple_errors(self) -> None:
        findings = validate_file_spec(_file_spec(type="bad", status="bad"))
        assert len(findings) == 2

    def test_all_valid_types_pass(self) -> None:
        from speclord.types import VALID_SPEC_TYPES

        for t in VALID_SPEC_TYPES:
            findings = validate_file_spec(_file_spec(type=t))
            assert not any(f.rule == "invalid-type" for f in findings)

    def test_all_valid_statuses_pass(self) -> None:
        from speclord.types import VALID_STATUSES

        for s in VALID_STATUSES:
            findings = validate_file_spec(_file_spec(status=s))
            assert not any(f.rule == "invalid-status" for f in findings)


class TestValidateServiceSpec:
    def test_valid_spec_no_findings(self) -> None:
        findings = validate_service_spec(_service_spec())
        assert findings == []

    def test_empty_service(self) -> None:
        findings = validate_service_spec(_service_spec(service=""))
        assert any(f.rule == "missing-service" for f in findings)

    def test_empty_owner(self) -> None:
        findings = validate_service_spec(_service_spec(owner=""))
        assert any(f.rule == "missing-owner" for f in findings)

    def test_empty_inherits(self) -> None:
        findings = validate_service_spec(_service_spec(inherits=""))
        assert any(f.rule == "missing-inherits" for f in findings)


class TestValidateOrgSpec:
    def test_valid_spec_no_findings(self) -> None:
        findings = validate_org_spec(_org_spec())
        assert findings == []

    def test_empty_organization(self) -> None:
        findings = validate_org_spec(_org_spec(organization=""))
        assert any(f.rule == "missing-organization" for f in findings)

    def test_missing_stack_warning(self) -> None:
        findings = validate_org_spec(_org_spec(stack={}))
        assert any(f.rule == "missing-stack" and f.severity == "warning" for f in findings)

    def test_missing_security_warning(self) -> None:
        findings = validate_org_spec(_org_spec(security=[]))
        assert any(f.rule == "missing-security" and f.severity == "warning" for f in findings)


class TestLintAll:
    def test_lint_valid_repo(self, valid_repo: Path) -> None:
        findings = lint_all(valid_repo)
        # Valid repo should have no errors (may have warnings)
        errors = [f for f in findings if f.severity == "error"]
        assert errors == []

    def test_lint_empty_dir(self, tmp_path: Path) -> None:
        findings = lint_all(tmp_path)
        assert findings == []

    def test_lint_catches_parse_errors(self, tmp_path: Path) -> None:
        bad_spec = tmp_path / "broken.spec.md"
        bad_spec.write_text("---\n---\nno frontmatter fields\n")
        findings = lint_all(tmp_path)
        assert any(f.rule == "parse-error" for f in findings)

    def test_lint_catches_invalid_type(self, tmp_path: Path) -> None:
        spec = tmp_path / "bad-type.spec.md"
        spec.write_text(
            '---\nspecVersion: "0.1.0"\ninherits: ".spec.yaml"\n'
            'type: "banana"\nowner: "@team"\nstatus: "draft"\n---\n## Purpose\nStuff.\n'
        )
        findings = lint_all(tmp_path)
        assert any(f.rule == "invalid-type" for f in findings)


class TestLintCLI:
    def test_lint_valid_repo(self, valid_repo: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["lint", "--root", str(valid_repo)])
        assert result.exit_code == 0

    def test_lint_json_output(self, valid_repo: Path) -> None:
        import json

        runner = CliRunner()
        result = runner.invoke(main, ["lint", "--root", str(valid_repo), "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)

    def test_lint_nonexistent_dir(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["lint", "--root", "/nonexistent"])
        assert result.exit_code != 0

    def test_lint_empty_dir(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["lint", "--root", str(tmp_path)])
        assert result.exit_code == 0
        assert "valid" in result.output.lower()
