"""Tests for the status dashboard command."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from speclord.cli import main


def _write_spec(
    path: Path,
    *,
    spec_type: str = "utility",
    status: str = "active",
    body: str = "Body.",
) -> None:
    content = (
        f"---\nspecVersion: '0.1.0'\ninherits: '.spec.yaml'\n"
        f"type: {spec_type}\nstatus: {status}\nowner: '@dev'\n"
        f"generates: '{path.stem}.py'\n---\n{body}\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _setup_repo(tmp_path: Path) -> None:
    """Create a small repo with specs and code files."""
    # Service spec
    (tmp_path / ".spec.yaml").write_text(
        "specVersion: '0.1.0'\ninherits: 'org.spec.yaml'\n"
        "service: test\nowner: '@dev'\n"
    )
    # Org spec
    (tmp_path / "org.spec.yaml").write_text(
        "specVersion: '0.1.0'\norganization: test-org\n"
        "stack:\n  runtime: python\nsecurity:\n  - 'validate input'\n"
    )
    # Code files + specs
    (tmp_path / "foo.py").write_text("pass")
    _write_spec(tmp_path / "foo.spec.md")
    (tmp_path / "bar.py").write_text("pass")
    _write_spec(tmp_path / "bar.spec.md", spec_type="data-model", status="draft")
    # Unspecced file
    (tmp_path / "baz.py").write_text("pass")


class TestStatusCLI:
    def test_shows_spec_counts(self, tmp_path: Path) -> None:
        _setup_repo(tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["status", "--root", str(tmp_path)])
        assert result.exit_code == 0
        assert "2 file spec(s)" in result.output

    def test_shows_by_type(self, tmp_path: Path) -> None:
        _setup_repo(tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["status", "--root", str(tmp_path)])
        assert "utility" in result.output
        assert "data-model" in result.output

    def test_shows_by_status(self, tmp_path: Path) -> None:
        _setup_repo(tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["status", "--root", str(tmp_path)])
        assert "active" in result.output
        assert "draft" in result.output

    def test_shows_coverage(self, tmp_path: Path) -> None:
        _setup_repo(tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["status", "--root", str(tmp_path)])
        # 2 specced out of 3 code files = 66.7%
        assert "66.7%" in result.output
        assert "2/3" in result.output

    def test_shows_last_compile_never(self, tmp_path: Path) -> None:
        _setup_repo(tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["status", "--root", str(tmp_path)])
        assert "never" in result.output

    def test_shows_last_compile_time(self, tmp_path: Path) -> None:
        _setup_repo(tmp_path)
        lock = tmp_path / "registry.lock.json"
        lock.write_text(json.dumps({"version": "0.1.0", "specs": {}}))
        runner = CliRunner()
        result = runner.invoke(main, ["status", "--root", str(tmp_path)])
        # Should show a date instead of "never"
        assert "never" not in result.output
        assert "Last compile" in result.output

    def test_shows_lint_clean(self, tmp_path: Path) -> None:
        _setup_repo(tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["status", "--root", str(tmp_path)])
        assert "Lint" in result.output
        assert "All specs valid" in result.output

    def test_shows_check_section(self, tmp_path: Path) -> None:
        _setup_repo(tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["status", "--root", str(tmp_path)])
        assert "Check" in result.output

    def test_empty_repo(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["status", "--root", str(tmp_path)])
        assert result.exit_code == 0
        assert "0 file spec(s)" in result.output
        assert "100.0%" in result.output

    def test_shows_lint_findings(self, tmp_path: Path) -> None:
        """Lint findings appear in status when specs have issues."""
        # Write a spec with invalid type to trigger a lint error
        spec = tmp_path / "bad.spec.md"
        spec.write_text(
            "---\nspecVersion: '0.1.0'\ninherits: '.spec.yaml'\n"
            "type: invalid-type\nstatus: active\nowner: '@dev'\n"
            "---\nBody.\n"
        )
        runner = CliRunner()
        result = runner.invoke(main, ["status", "--root", str(tmp_path)])
        assert "error" in result.output.lower()
