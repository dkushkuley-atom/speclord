"""Tests for the spec coverage checker."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from speclord.cli import main
from speclord.config import SpeclordConfig
from speclord.coverage import check_coverage


class TestCheckCoverage:
    def test_full_coverage(self, tmp_path: Path) -> None:
        """All code files have specs → 100%."""
        (tmp_path / "foo.py").write_text("pass")
        (tmp_path / "foo.spec.md").write_text(
            "---\nspecVersion: '0.1.0'\ninherits: '.spec.yaml'\n"
            "type: utility\nstatus: draft\nowner: '@dev'\n---\nBody.\n"
        )
        report = check_coverage(tmp_path, SpeclordConfig())
        assert report.total_files == 1
        assert report.specced_files == 1
        assert report.coverage_pct == 100.0
        assert report.unspecced == []

    def test_partial_coverage(self, tmp_path: Path) -> None:
        """Some files missing specs."""
        (tmp_path / "foo.py").write_text("pass")
        (tmp_path / "foo.spec.md").write_text(
            "---\nspecVersion: '0.1.0'\ninherits: '.spec.yaml'\n"
            "type: utility\nstatus: draft\nowner: '@dev'\n---\nBody.\n"
        )
        (tmp_path / "bar.py").write_text("pass")
        report = check_coverage(tmp_path, SpeclordConfig())
        assert report.total_files == 2
        assert report.specced_files == 1
        assert report.coverage_pct == 50.0
        assert "bar.py" in report.unspecced

    def test_ignores_init_py(self, tmp_path: Path) -> None:
        """__init__.py is not counted."""
        (tmp_path / "__init__.py").write_text("")
        (tmp_path / "foo.py").write_text("pass")
        report = check_coverage(tmp_path, SpeclordConfig())
        assert report.total_files == 1  # only foo.py

    def test_respects_extensions_config(self, tmp_path: Path) -> None:
        """Only counts configured extensions."""
        (tmp_path / "foo.py").write_text("pass")
        (tmp_path / "bar.ts").write_text("export default {}")
        # Default config only includes .py
        report = check_coverage(tmp_path, SpeclordConfig())
        assert report.total_files == 1

        # Custom config includes .ts
        cfg = SpeclordConfig(coverage_extensions=[".py", ".ts"])
        report = check_coverage(tmp_path, cfg)
        assert report.total_files == 2

    def test_respects_ignore_config(self, tmp_path: Path) -> None:
        """Files matching ignore patterns are excluded."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("pass")
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_app.py").write_text("pass")

        cfg = SpeclordConfig(coverage_ignore=["tests/*"])
        report = check_coverage(tmp_path, cfg)
        assert report.total_files == 1
        assert "src/app.py" in report.unspecced

    def test_empty_dir(self, tmp_path: Path) -> None:
        """No code files → 100%."""
        report = check_coverage(tmp_path, SpeclordConfig())
        assert report.total_files == 0
        assert report.coverage_pct == 100.0

    def test_skips_ignored_dirs(self, tmp_path: Path) -> None:
        """Files in IGNORE_DIRS like __pycache__ are skipped."""
        cache = tmp_path / "__pycache__"
        cache.mkdir()
        (cache / "foo.py").write_text("pass")
        (tmp_path / "real.py").write_text("pass")
        report = check_coverage(tmp_path, SpeclordConfig())
        assert report.total_files == 1


class TestCoverageCLI:
    def test_coverage_text_output(self, tmp_path: Path) -> None:
        (tmp_path / "foo.py").write_text("pass")
        runner = CliRunner()
        result = runner.invoke(main, ["coverage", "--root", str(tmp_path)])
        assert result.exit_code == 0
        assert "0%" in result.output or "0.0%" in result.output
        assert "foo.py" in result.output

    def test_coverage_json_output(self, tmp_path: Path) -> None:
        (tmp_path / "foo.py").write_text("pass")
        runner = CliRunner()
        result = runner.invoke(
            main, ["coverage", "--root", str(tmp_path), "--format", "json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "total_files" in data
        assert "coverage_pct" in data
        assert "unspecced" in data
        assert data["total_files"] == 1

    def test_coverage_min_passes(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            main, ["coverage", "--root", str(tmp_path), "--min", "0"]
        )
        assert result.exit_code == 0

    def test_coverage_min_fails(self, tmp_path: Path) -> None:
        (tmp_path / "foo.py").write_text("pass")
        runner = CliRunner()
        result = runner.invoke(
            main, ["coverage", "--root", str(tmp_path), "--min", "100"]
        )
        assert result.exit_code != 0
