"""Tests for the context builder."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from speclord.cli import main
from speclord.context import build_context


class TestBuildContext:
    def test_full_chain_includes_org_section(self, valid_repo: Path) -> None:
        spec = valid_repo / "packages" / "auth" / "src" / "handler.spec.md"
        ctx = build_context(spec, valid_repo)
        assert "## Organization Constraints (test-org)" in ctx

    def test_full_chain_includes_service_section(self, valid_repo: Path) -> None:
        spec = valid_repo / "packages" / "auth" / "src" / "handler.spec.md"
        ctx = build_context(spec, valid_repo)
        assert "## Service Conventions (auth)" in ctx

    def test_full_chain_includes_file_section(self, valid_repo: Path) -> None:
        spec = valid_repo / "packages" / "auth" / "src" / "handler.spec.md"
        ctx = build_context(spec, valid_repo)
        assert "## File Spec (api-endpoint, active)" in ctx

    def test_full_chain_includes_body(self, valid_repo: Path) -> None:
        spec = valid_repo / "packages" / "auth" / "src" / "handler.spec.md"
        ctx = build_context(spec, valid_repo)
        assert "## Purpose" in ctx
        assert "Handles authentication requests" in ctx
        assert "## Interface" in ctx

    def test_file_only_omits_org_and_service(self, tmp_path: Path) -> None:
        """Spec with no resolvable parents has only file section."""
        spec = tmp_path / "solo.spec.md"
        spec.write_text(
            "---\n"
            'specVersion: "0.1.0"\n'
            'inherits: ".spec.yaml"\n'
            'type: "utility"\n'
            'status: "draft"\n'
            'owner: "@dev"\n'
            "---\n"
            "\n"
            "## Purpose\n"
            "A standalone utility.\n"
        )
        ctx = build_context(spec, tmp_path)
        assert "Organization Constraints" not in ctx
        assert "Service Conventions" not in ctx
        assert "## File Spec (utility, draft)" in ctx
        assert "A standalone utility." in ctx

    def test_org_direct_inherits_omits_service(self, tmp_path: Path) -> None:
        """File spec that inherits directly from org spec — no service section."""
        org = tmp_path / "org.spec.yaml"
        org.write_text(
            'specVersion: "0.1.0"\n'
            'organization: "direct-org"\n'
            "stack:\n"
            '  runtime: "node"\n'
        )
        spec = tmp_path / "thing.spec.md"
        spec.write_text(
            "---\n"
            'specVersion: "0.1.0"\n'
            'inherits: "org.spec.yaml"\n'
            'type: "data-model"\n'
            'status: "active"\n'
            'owner: "@team"\n'
            "---\n"
            "\n"
            "## Purpose\n"
            "Direct org child.\n"
        )
        ctx = build_context(spec, tmp_path)
        assert "## Organization Constraints (direct-org)" in ctx
        assert "Service Conventions" not in ctx
        assert "## File Spec (data-model, active)" in ctx

    def test_context_header_uses_relative_path(self, valid_repo: Path) -> None:
        spec = valid_repo / "packages" / "auth" / "src" / "handler.spec.md"
        ctx = build_context(spec, valid_repo)
        assert ctx.startswith("# Context: packages/auth/src/handler\n")

    def test_org_stack_rendered(self, valid_repo: Path) -> None:
        spec = valid_repo / "packages" / "auth" / "src" / "handler.spec.md"
        ctx = build_context(spec, valid_repo)
        assert "runtime=python" in ctx
        assert "language=python" in ctx

    def test_org_patterns_rendered(self, valid_repo: Path) -> None:
        spec = valid_repo / "packages" / "auth" / "src" / "handler.spec.md"
        ctx = build_context(spec, valid_repo)
        assert "naming=snake_case" in ctx
        assert "testing=pytest" in ctx

    def test_org_security_rendered(self, valid_repo: Path) -> None:
        spec = valid_repo / "packages" / "auth" / "src" / "handler.spec.md"
        ctx = build_context(spec, valid_repo)
        assert "Validate all input" in ctx
        assert "Never log credentials" in ctx

    def test_service_conventions_rendered(self, valid_repo: Path) -> None:
        spec = valid_repo / "packages" / "auth" / "src" / "handler.spec.md"
        ctx = build_context(spec, valid_repo)
        assert "naming=snake_case" in ctx
        assert "error_handling=raise exceptions" in ctx

    def test_service_testing_rendered(self, valid_repo: Path) -> None:
        spec = valid_repo / "packages" / "auth" / "src" / "handler.spec.md"
        ctx = build_context(spec, valid_repo)
        assert "framework=pytest" in ctx
        assert "coverage_target=90" in ctx

    def test_file_generates_rendered(self, valid_repo: Path) -> None:
        spec = valid_repo / "packages" / "auth" / "src" / "handler.spec.md"
        ctx = build_context(spec, valid_repo)
        assert "**Generates:** packages/auth/src/handler.py" in ctx

    def test_file_priority_rendered_when_not_normal(self, valid_repo: Path) -> None:
        spec = valid_repo / "packages" / "auth" / "src" / "handler.spec.md"
        ctx = build_context(spec, valid_repo)
        assert "**Priority:** high" in ctx

    def test_file_priority_omitted_when_normal(self, tmp_path: Path) -> None:
        spec = tmp_path / "normal.spec.md"
        spec.write_text(
            "---\n"
            'specVersion: "0.1.0"\n'
            'inherits: ".spec.yaml"\n'
            'type: "utility"\n'
            'status: "draft"\n'
            'owner: "@dev"\n'
            "---\n"
            "\n"
            "Body text.\n"
        )
        ctx = build_context(spec, tmp_path)
        assert "Priority" not in ctx


class TestContextCLI:
    def test_context_single_file(self, valid_repo: Path) -> None:
        runner = CliRunner()
        spec = valid_repo / "packages" / "auth" / "src" / "handler.spec.md"
        result = runner.invoke(main, ["context", str(spec), "--root", str(valid_repo)])
        assert result.exit_code == 0
        assert "# Context:" in result.output
        assert "Organization Constraints" in result.output
        assert "File Spec" in result.output

    def test_context_batch(self, valid_repo: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            main, ["context", "--batch", "**/*.spec.md", "--root", str(valid_repo)]
        )
        assert result.exit_code == 0
        assert "# Context:" in result.output

    def test_context_no_args_errors(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["context"])
        assert result.exit_code != 0

    def test_context_nonexistent_file_errors(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            main, ["context", str(tmp_path / "nope.spec.md"), "--root", str(tmp_path)]
        )
        assert result.exit_code != 0
