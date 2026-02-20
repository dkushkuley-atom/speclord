"""Tests for the migration progress tracker."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from speclord.cli import main
from speclord.config import SpeclordConfig
from speclord.migrate.progress import track_progress


def _write_spec(path: Path, generates: str) -> None:
    content = (
        f"---\nspecVersion: '0.1.0'\ninherits: '.spec.yaml'\n"
        f"type: utility\nstatus: active\nowner: '@dev'\n"
        f"generates: '{generates}'\n---\nBody.\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _write_service_spec(tmp_path: Path) -> None:
    (tmp_path / ".spec.yaml").write_text(
        "specVersion: '0.1.0'\ninherits: 'org.spec.yaml'\n"
        "service: test\nowner: '@dev'\n"
    )


def _write_lock(tmp_path: Path, spec_paths: list[str]) -> None:
    """Write a registry.lock.json with the given spec paths."""
    specs = {}
    for p in spec_paths:
        specs[p] = {
            "hash": "abc123",
            "type": "utility",
            "status": "active",
            "dependencies": [],
        }
    lock = {"version": "0.1.0", "specs": specs, "errors": []}
    (tmp_path / "registry.lock.json").write_text(
        json.dumps(lock, indent=2) + "\n"
    )


class TestTrackProgress:
    def test_no_baseline(self, tmp_path: Path) -> None:
        """Without registry.lock.json, has_baseline is False."""
        _write_service_spec(tmp_path)
        (tmp_path / "app.py").write_text("pass")
        _write_spec(tmp_path / "app.spec.md", "app.py")
        report = track_progress(tmp_path, SpeclordConfig())
        assert report.has_baseline is False
        assert report.baseline_specced == 0
        assert report.current_specced == 1
        assert report.current_total == 1

    def test_with_baseline_no_change(self, tmp_path: Path) -> None:
        """Baseline matches current → delta is 0."""
        _write_service_spec(tmp_path)
        (tmp_path / "app.py").write_text("pass")
        _write_spec(tmp_path / "app.spec.md", "app.py")
        _write_lock(tmp_path, ["app.spec.md"])
        report = track_progress(tmp_path, SpeclordConfig())
        assert report.has_baseline is True
        assert report.delta == 0
        assert report.new_specs == []
        assert report.removed_specs == []

    def test_new_specs_detected(self, tmp_path: Path) -> None:
        """Specs added after compile appear in new_specs."""
        _write_service_spec(tmp_path)
        (tmp_path / "app.py").write_text("pass")
        _write_spec(tmp_path / "app.spec.md", "app.py")
        (tmp_path / "utils.py").write_text("pass")
        _write_spec(tmp_path / "utils.spec.md", "utils.py")
        # Baseline only had app.spec.md
        _write_lock(tmp_path, ["app.spec.md"])
        report = track_progress(tmp_path, SpeclordConfig())
        assert report.delta == 1
        assert "utils.spec.md" in report.new_specs
        assert report.removed_specs == []

    def test_removed_specs_detected(self, tmp_path: Path) -> None:
        """Specs removed since compile appear in removed_specs."""
        _write_service_spec(tmp_path)
        (tmp_path / "app.py").write_text("pass")
        _write_spec(tmp_path / "app.spec.md", "app.py")
        # Baseline had app + utils, but utils.spec.md no longer exists
        _write_lock(tmp_path, ["app.spec.md", "utils.spec.md"])
        report = track_progress(tmp_path, SpeclordConfig())
        assert "utils.spec.md" in report.removed_specs
        assert report.baseline_specced == 2
        assert report.current_specced == 1

    def test_remaining(self, tmp_path: Path) -> None:
        """Remaining is total minus specced."""
        _write_service_spec(tmp_path)
        (tmp_path / "app.py").write_text("pass")
        _write_spec(tmp_path / "app.spec.md", "app.py")
        (tmp_path / "utils.py").write_text("pass")  # unspecced
        report = track_progress(tmp_path, SpeclordConfig())
        assert report.current_total == 2
        assert report.current_specced == 1
        assert report.remaining == 1

    def test_current_pct(self, tmp_path: Path) -> None:
        """current_pct computes correctly."""
        _write_service_spec(tmp_path)
        (tmp_path / "app.py").write_text("pass")
        _write_spec(tmp_path / "app.spec.md", "app.py")
        (tmp_path / "utils.py").write_text("pass")
        report = track_progress(tmp_path, SpeclordConfig())
        assert report.current_pct == 50.0

    def test_empty_repo(self, tmp_path: Path) -> None:
        """No code files → 100% coverage, nothing to do."""
        report = track_progress(tmp_path, SpeclordConfig())
        assert report.current_total == 0
        assert report.current_pct == 100.0
        assert report.remaining == 0

    def test_fully_specced(self, tmp_path: Path) -> None:
        """All files specced → 100%, remaining 0."""
        _write_service_spec(tmp_path)
        (tmp_path / "app.py").write_text("pass")
        _write_spec(tmp_path / "app.spec.md", "app.py")
        _write_lock(tmp_path, ["app.spec.md"])
        report = track_progress(tmp_path, SpeclordConfig())
        assert report.current_pct == 100.0
        assert report.remaining == 0
        assert report.delta == 0

    def test_subdirectory_specs(self, tmp_path: Path) -> None:
        """Specs in subdirectories are tracked with relative paths."""
        _write_service_spec(tmp_path)
        src = tmp_path / "src"
        src.mkdir()
        (src / "handler.py").write_text("pass")
        _write_spec(src / "handler.spec.md", "handler.py")
        _write_lock(tmp_path, [])
        report = track_progress(tmp_path, SpeclordConfig())
        assert "src/handler.spec.md" in report.new_specs
        assert report.delta == 1

    def test_positive_delta(self, tmp_path: Path) -> None:
        """Adding specs after baseline yields positive delta."""
        _write_service_spec(tmp_path)
        (tmp_path / "a.py").write_text("pass")
        _write_spec(tmp_path / "a.spec.md", "a.py")
        (tmp_path / "b.py").write_text("pass")
        _write_spec(tmp_path / "b.spec.md", "b.py")
        (tmp_path / "c.py").write_text("pass")
        _write_spec(tmp_path / "c.spec.md", "c.py")
        _write_lock(tmp_path, ["a.spec.md"])
        report = track_progress(tmp_path, SpeclordConfig())
        assert report.delta == 2
        assert len(report.new_specs) == 2


class TestMigrateProgressCLI:
    def test_text_no_baseline(self, tmp_path: Path) -> None:
        """Text output shows no-baseline message."""
        _write_service_spec(tmp_path)
        (tmp_path / "app.py").write_text("pass")
        _write_spec(tmp_path / "app.spec.md", "app.py")
        runner = CliRunner()
        result = runner.invoke(
            main, ["migrate", "progress", "--root", str(tmp_path)]
        )
        assert result.exit_code == 0
        assert "Migration Progress" in result.output
        assert "No baseline" in result.output

    def test_text_with_baseline(self, tmp_path: Path) -> None:
        """Text output shows delta and baseline info."""
        _write_service_spec(tmp_path)
        (tmp_path / "app.py").write_text("pass")
        _write_spec(tmp_path / "app.spec.md", "app.py")
        (tmp_path / "utils.py").write_text("pass")
        _write_spec(tmp_path / "utils.spec.md", "utils.py")
        _write_lock(tmp_path, ["app.spec.md"])
        runner = CliRunner()
        result = runner.invoke(
            main, ["migrate", "progress", "--root", str(tmp_path)]
        )
        assert result.exit_code == 0
        assert "Baseline" in result.output
        assert "Delta" in result.output
        assert "+1" in result.output

    def test_text_shows_new_specs(self, tmp_path: Path) -> None:
        """Text output lists newly added specs."""
        _write_service_spec(tmp_path)
        (tmp_path / "app.py").write_text("pass")
        _write_spec(tmp_path / "app.spec.md", "app.py")
        (tmp_path / "utils.py").write_text("pass")
        _write_spec(tmp_path / "utils.spec.md", "utils.py")
        _write_lock(tmp_path, ["app.spec.md"])
        runner = CliRunner()
        result = runner.invoke(
            main, ["migrate", "progress", "--root", str(tmp_path)]
        )
        assert result.exit_code == 0
        assert "New specs" in result.output

    def test_json_output(self, tmp_path: Path) -> None:
        """JSON mode returns valid JSON with expected keys."""
        _write_service_spec(tmp_path)
        (tmp_path / "app.py").write_text("pass")
        _write_spec(tmp_path / "app.spec.md", "app.py")
        _write_lock(tmp_path, ["app.spec.md"])
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["migrate", "progress", "--root", str(tmp_path), "--format", "json"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["current_total"] == 1
        assert data["current_specced"] == 1
        assert data["has_baseline"] is True
        assert data["delta"] == 0
        assert "new_specs" in data
        assert "removed_specs" in data

    def test_empty_repo(self, tmp_path: Path) -> None:
        """Empty repo shows 100% progress."""
        runner = CliRunner()
        result = runner.invoke(
            main, ["migrate", "progress", "--root", str(tmp_path)]
        )
        assert result.exit_code == 0
        assert "100.0%" in result.output
