"""Tests for the CLI entry point."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from speclord import __version__
from speclord.cli import main


def test_version_flag() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_help_flag() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "spec layer" in result.output.lower()


def test_no_args_shows_help() -> None:
    runner = CliRunner()
    result = runner.invoke(main, [])
    assert result.exit_code == 0
    assert "Usage" in result.output


class TestCLIConfigMerge:
    def test_lint_works_without_config_file(self, tmp_path: Path) -> None:
        """Lint still works with no config file (defaults apply)."""
        runner = CliRunner()
        result = runner.invoke(main, ["lint", "--root", str(tmp_path)])
        assert result.exit_code == 0

    def test_lint_cli_root_overrides_config(self, tmp_path: Path) -> None:
        """CLI --root flag takes precedence over config root."""
        target = tmp_path / "target"
        target.mkdir()
        (tmp_path / ".speclordrc.yaml").write_text("root: /nonexistent\n")
        runner = CliRunner()
        result = runner.invoke(main, ["lint", "--root", str(target)])
        assert result.exit_code == 0

    def test_compile_works_without_config_file(self, tmp_path: Path) -> None:
        """Compile still works with no config file (defaults apply)."""
        runner = CliRunner()
        result = runner.invoke(main, ["compile", "--root", str(tmp_path)])
        assert result.exit_code == 0
