"""Tests for the resolve CLI command."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from speclord.cli import main


class TestResolveCLI:
    def test_resolve_full_chain(self, valid_repo: Path) -> None:
        runner = CliRunner()
        spec = valid_repo / "packages" / "auth" / "src" / "handler.spec.md"
        result = runner.invoke(main, ["resolve", str(spec), "--root", str(valid_repo)])
        assert result.exit_code == 0
        assert "test-org" in result.output
        assert "auth" in result.output
        assert "api-endpoint" in result.output

    def test_resolve_shows_chain_path(self, valid_repo: Path) -> None:
        runner = CliRunner()
        spec = valid_repo / "packages" / "auth" / "src" / "handler.spec.md"
        result = runner.invoke(main, ["resolve", str(spec), "--root", str(valid_repo)])
        assert result.exit_code == 0
        assert "→" in result.output

    def test_resolve_file_only(self, tmp_path: Path) -> None:
        """Spec with no resolvable parents shows only file layer."""
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
            "Solo spec.\n"
        )
        runner = CliRunner()
        result = runner.invoke(main, ["resolve", str(spec), "--root", str(tmp_path)])
        assert result.exit_code == 0
        assert "utility" in result.output
        assert "Organization" not in result.output
        assert "Service" not in result.output

    def test_resolve_json_format(self, valid_repo: Path) -> None:
        runner = CliRunner()
        spec = valid_repo / "packages" / "auth" / "src" / "handler.spec.md"
        result = runner.invoke(
            main, ["resolve", str(spec), "--root", str(valid_repo), "--format", "json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "org" in data
        assert data["org"]["organization"] == "test-org"
        assert "service" in data
        assert data["service"]["service"] == "auth"
        assert "file" in data
        assert data["file"]["type"] == "api-endpoint"

    def test_resolve_nonexistent_file_errors(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            main, ["resolve", str(tmp_path / "nope.spec.md"), "--root", str(tmp_path)]
        )
        assert result.exit_code != 0

    def test_resolve_malformed_spec_errors(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.spec.md"
        bad.write_text("not valid frontmatter at all")
        runner = CliRunner()
        result = runner.invoke(main, ["resolve", str(bad), "--root", str(tmp_path)])
        assert result.exit_code != 0
