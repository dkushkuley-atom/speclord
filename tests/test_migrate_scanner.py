"""Tests for the migration scanner."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from speclord.cli import main
from speclord.config import SpeclordConfig
from speclord.migrate.scanner import scan_codebase


def _write_spec(path: Path, generates: str) -> None:
    content = (
        f"---\nspecVersion: '0.1.0'\ninherits: '.spec.yaml'\n"
        f"type: utility\nstatus: active\nowner: '@dev'\n"
        f"generates: '{generates}'\n---\nBody.\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _setup_repo(tmp_path: Path) -> None:
    """Create a repo with mixed coverage across directories."""
    # Root service spec
    (tmp_path / ".spec.yaml").write_text(
        "specVersion: '0.1.0'\ninherits: 'org.spec.yaml'\n"
        "service: test\nowner: '@dev'\n"
    )
    # Root-level files: 1 specced, 1 unspecced
    (tmp_path / "app.py").write_text("pass")
    _write_spec(tmp_path / "app.spec.md", "app.py")
    (tmp_path / "main.py").write_text("pass")

    # src/ directory: 2 specced, 1 unspecced
    src = tmp_path / "src"
    src.mkdir()
    (src / "handler.py").write_text("pass")
    _write_spec(src / "handler.spec.md", "handler.py")
    (src / "models.py").write_text("pass")
    _write_spec(src / "models.spec.md", "models.py")
    (src / "utils.py").write_text("pass")

    # lib/ directory: fully unspecced
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "helpers.py").write_text("pass")


class TestScanCodebase:
    def test_totals(self, tmp_path: Path) -> None:
        """Scan counts total, specced, and unspecced correctly."""
        _setup_repo(tmp_path)
        scan = scan_codebase(tmp_path, SpeclordConfig())
        # 6 .py files: app, main (root), handler, models, utils (src), helpers (lib)
        assert scan.total_files == 6
        assert scan.specced_files == 3
        assert scan.unspecced_files == 3

    def test_by_directory(self, tmp_path: Path) -> None:
        """Results are grouped by directory."""
        _setup_repo(tmp_path)
        scan = scan_codebase(tmp_path, SpeclordConfig())
        dirs = {e.directory: e for e in scan.by_directory}
        assert "." in dirs
        assert "src" in dirs
        assert "lib" in dirs

    def test_root_dir_counts(self, tmp_path: Path) -> None:
        """Root directory has correct counts."""
        _setup_repo(tmp_path)
        scan = scan_codebase(tmp_path, SpeclordConfig())
        root_entry = next(e for e in scan.by_directory if e.directory == ".")
        assert root_entry.total_files == 2
        assert root_entry.specced_files == 1

    def test_src_dir_counts(self, tmp_path: Path) -> None:
        """src/ directory has correct counts."""
        _setup_repo(tmp_path)
        scan = scan_codebase(tmp_path, SpeclordConfig())
        src_entry = next(e for e in scan.by_directory if e.directory == "src")
        assert src_entry.total_files == 3
        assert src_entry.specced_files == 2

    def test_unspecced_lists(self, tmp_path: Path) -> None:
        """Unspecced file paths are correctly listed per directory."""
        _setup_repo(tmp_path)
        scan = scan_codebase(tmp_path, SpeclordConfig())
        root_entry = next(e for e in scan.by_directory if e.directory == ".")
        assert "main.py" in root_entry.unspecced
        lib_entry = next(e for e in scan.by_directory if e.directory == "lib")
        assert "lib/helpers.py" in lib_entry.unspecced

    def test_empty_repo(self, tmp_path: Path) -> None:
        """Empty repo → zero totals, no directories."""
        scan = scan_codebase(tmp_path, SpeclordConfig())
        assert scan.total_files == 0
        assert scan.by_directory == []

    def test_respects_extensions(self, tmp_path: Path) -> None:
        """Only configured extensions are scanned."""
        (tmp_path / "code.py").write_text("pass")
        (tmp_path / "readme.md").write_text("hello")
        scan = scan_codebase(tmp_path, SpeclordConfig())
        assert scan.total_files == 1

    def test_ignores_init(self, tmp_path: Path) -> None:
        """__init__.py is skipped."""
        (tmp_path / "__init__.py").write_text("")
        (tmp_path / "real.py").write_text("pass")
        scan = scan_codebase(tmp_path, SpeclordConfig())
        assert scan.total_files == 1

    def test_respects_ignore_patterns(self, tmp_path: Path) -> None:
        """Config ignore patterns exclude files."""
        (tmp_path / "keep.py").write_text("pass")
        (tmp_path / "skip_me.py").write_text("pass")
        cfg = SpeclordConfig(coverage_ignore=["skip_*"])
        scan = scan_codebase(tmp_path, cfg)
        assert scan.total_files == 1

    def test_directories_sorted(self, tmp_path: Path) -> None:
        """Directory entries are sorted alphabetically."""
        _setup_repo(tmp_path)
        scan = scan_codebase(tmp_path, SpeclordConfig())
        dirs = [e.directory for e in scan.by_directory]
        assert dirs == sorted(dirs)


class TestMigrateScanCLI:
    def test_text_output(self, tmp_path: Path) -> None:
        """Text mode shows summary and table."""
        _setup_repo(tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["migrate", "scan", "--root", str(tmp_path)])
        assert result.exit_code == 0
        assert "Migration Scan" in result.output
        assert "Coverage by Directory" in result.output

    def test_json_output(self, tmp_path: Path) -> None:
        """JSON mode returns valid JSON with expected keys."""
        _setup_repo(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            main, ["migrate", "scan", "--root", str(tmp_path), "--format", "json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["total_files"] == 6
        assert data["specced_files"] == 3
        assert "by_directory" in data

    def test_empty_repo(self, tmp_path: Path) -> None:
        """Empty repo shows informative message."""
        runner = CliRunner()
        result = runner.invoke(main, ["migrate", "scan", "--root", str(tmp_path)])
        assert result.exit_code == 0
        assert "No code files" in result.output

    def test_shows_unspecced_count(self, tmp_path: Path) -> None:
        """Shows how many files need specs."""
        _setup_repo(tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["migrate", "scan", "--root", str(tmp_path)])
        assert "3 file(s) need specs" in result.output

    def test_fully_specced_no_warning(self, tmp_path: Path) -> None:
        """Fully specced repo doesn't show 'need specs' message."""
        (tmp_path / ".spec.yaml").write_text(
            "specVersion: '0.1.0'\ninherits: 'org.spec.yaml'\n"
            "service: test\nowner: '@dev'\n"
        )
        (tmp_path / "foo.py").write_text("pass")
        _write_spec(tmp_path / "foo.spec.md", "foo.py")
        runner = CliRunner()
        result = runner.invoke(main, ["migrate", "scan", "--root", str(tmp_path)])
        assert result.exit_code == 0
        assert "need specs" not in result.output
