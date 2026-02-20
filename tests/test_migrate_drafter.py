"""Tests for the batch spec drafter."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from speclord.ai.adapter import MockAdapter
from speclord.cli import main
from speclord.migrate.drafter import DraftResult, batch_draft

SAMPLE_SPEC = """\
---
specVersion: "0.1.0"
type: "utility"
owner: "@team"
status: "draft"
inherits: ".spec.yaml"
---

## Purpose

Auto-generated spec.
"""


def _setup_project(tmp_path: Path) -> None:
    """Create a minimal project with some code files."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "auth.py").write_text("def login(): pass", encoding="utf-8")
    (tmp_path / "src" / "utils.py").write_text("def helper(): pass", encoding="utf-8")
    (tmp_path / "src" / "__init__.py").write_text("", encoding="utf-8")


def _setup_partial(tmp_path: Path) -> None:
    """Create a project where one file already has a spec."""
    _setup_project(tmp_path)
    # auth already has a spec
    (tmp_path / "src" / "auth.spec.md").write_text(
        "---\nspecVersion: '0.1.0'\ntype: utility\nowner: '@team'\n"
        "status: active\ninherits: .spec.yaml\n---\nAuth spec.",
        encoding="utf-8",
    )


# ── batch_draft ─────────────────────────────────────────────────────


class TestBatchDraft:
    def test_yields_results(self, tmp_path: Path) -> None:
        """batch_draft yields DraftResult for each unspecced file."""
        _setup_project(tmp_path)
        adapter = MockAdapter(generate_response=SAMPLE_SPEC)
        results = list(batch_draft(tmp_path, adapter))
        assert len(results) == 2
        assert all(isinstance(r, DraftResult) for r in results)

    def test_results_are_successful(self, tmp_path: Path) -> None:
        """Successful drafts have success=True."""
        _setup_project(tmp_path)
        adapter = MockAdapter(generate_response=SAMPLE_SPEC)
        results = list(batch_draft(tmp_path, adapter))
        assert all(r.success for r in results)

    def test_spec_files_written(self, tmp_path: Path) -> None:
        """batch_draft writes .spec.md files to disk."""
        _setup_project(tmp_path)
        adapter = MockAdapter(generate_response=SAMPLE_SPEC)
        list(batch_draft(tmp_path, adapter))
        assert (tmp_path / "src" / "auth.spec.md").exists()
        assert (tmp_path / "src" / "utils.spec.md").exists()

    def test_spec_content_matches(self, tmp_path: Path) -> None:
        """Written spec files contain the adapter output."""
        _setup_project(tmp_path)
        adapter = MockAdapter(generate_response=SAMPLE_SPEC)
        list(batch_draft(tmp_path, adapter))
        content = (tmp_path / "src" / "auth.spec.md").read_text(encoding="utf-8")
        assert content == SAMPLE_SPEC

    def test_skips_already_specced(self, tmp_path: Path) -> None:
        """Files that already have specs are skipped."""
        _setup_partial(tmp_path)
        adapter = MockAdapter(generate_response=SAMPLE_SPEC)
        results = list(batch_draft(tmp_path, adapter))
        # Only utils.py should be drafted (auth.py already has a spec)
        assert len(results) == 1
        assert results[0].source_path == "src/utils.py"

    def test_empty_project(self, tmp_path: Path) -> None:
        """No unspecced files yields no results."""
        adapter = MockAdapter(generate_response=SAMPLE_SPEC)
        results = list(batch_draft(tmp_path, adapter))
        assert results == []

    def test_directory_filter(self, tmp_path: Path) -> None:
        """--batch directory filter limits which dirs are processed."""
        _setup_project(tmp_path)
        (tmp_path / "lib").mkdir()
        (tmp_path / "lib" / "core.py").write_text("x = 1", encoding="utf-8")
        adapter = MockAdapter(generate_response=SAMPLE_SPEC)
        results = list(batch_draft(tmp_path, adapter, directory="lib"))
        # Only lib/core.py should be drafted
        assert len(results) == 1
        assert "lib/core.py" in results[0].source_path

    def test_error_captured(self, tmp_path: Path) -> None:
        """Adapter errors are captured as failed results."""
        _setup_project(tmp_path)

        class FailAdapter(MockAdapter):
            def generate(self, prompt, system, cwd):
                raise RuntimeError("API unavailable")

        adapter = FailAdapter(generate_response="")
        results = list(batch_draft(tmp_path, adapter))
        assert len(results) == 2
        assert all(not r.success for r in results)
        assert all(r.error is not None for r in results)

    def test_from_code_used(self, tmp_path: Path) -> None:
        """batch_draft uses --from-code so source content appears in prompt."""
        _setup_project(tmp_path)
        adapter = MockAdapter(generate_response=SAMPLE_SPEC)
        list(batch_draft(tmp_path, adapter))
        # draft_spec is called with from_code=True, so source should be in prompt
        assert len(adapter.generate_calls) == 2
        # At least one call should have the source content in the prompt
        prompts = [c["prompt"] for c in adapter.generate_calls]
        assert any("def login" in p or "def helper" in p for p in prompts)

    def test_result_has_paths(self, tmp_path: Path) -> None:
        """DraftResult carries both source and spec paths."""
        _setup_project(tmp_path)
        adapter = MockAdapter(generate_response=SAMPLE_SPEC)
        results = list(batch_draft(tmp_path, adapter))
        for r in results:
            assert r.source_path.endswith(".py")
            assert r.spec_path.endswith(".spec.md")


# ── CLI migrate draft ───────────────────────────────────────────────


class TestMigrateDraftCLI:
    def test_draft_text_output(self, tmp_path: Path) -> None:
        """Text mode shows drafted specs."""
        _setup_project(tmp_path)
        mock_results = [
            DraftResult(source_path="src/auth.py", spec_path="src/auth.spec.md", success=True),
            DraftResult(source_path="src/utils.py", spec_path="src/utils.spec.md", success=True),
        ]
        runner = CliRunner()
        with patch("speclord.ai.adapter.ClaudeCodeAdapter"), \
             patch("speclord.migrate.drafter.batch_draft", return_value=iter(mock_results)):
            result = runner.invoke(
                main,
                ["migrate", "draft", "--root", str(tmp_path)],
                catch_exceptions=False,
            )
        assert result.exit_code == 0
        assert "auth.spec.md" in result.output
        assert "utils.spec.md" in result.output
        assert "2 drafted" in result.output

    def test_draft_json_output(self, tmp_path: Path) -> None:
        """JSON mode produces valid JSON."""
        _setup_project(tmp_path)
        mock_results = [
            DraftResult(source_path="src/auth.py", spec_path="src/auth.spec.md", success=True),
        ]
        runner = CliRunner()
        with patch("speclord.ai.adapter.ClaudeCodeAdapter"), \
             patch("speclord.migrate.drafter.batch_draft", return_value=iter(mock_results)):
            result = runner.invoke(
                main,
                ["migrate", "draft", "--root", str(tmp_path), "--format", "json"],
                catch_exceptions=False,
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["drafted"] == 1
        assert data["failed"] == 0
        assert len(data["results"]) == 1

    def test_draft_all_specced(self, tmp_path: Path) -> None:
        """When all files have specs, shows clean message."""
        runner = CliRunner()
        with patch("speclord.ai.adapter.ClaudeCodeAdapter"), \
             patch("speclord.migrate.drafter.batch_draft", return_value=iter([])):
            result = runner.invoke(
                main,
                ["migrate", "draft", "--root", str(tmp_path)],
                catch_exceptions=False,
            )
        assert result.exit_code == 0
        assert "already have specs" in result.output

    def test_draft_with_failures(self, tmp_path: Path) -> None:
        """Failed drafts are reported in output."""
        mock_results = [
            DraftResult(
                source_path="src/bad.py",
                spec_path="src/bad.spec.md",
                success=False,
                error="API error",
            ),
        ]
        runner = CliRunner()
        with patch("speclord.ai.adapter.ClaudeCodeAdapter"), \
             patch("speclord.migrate.drafter.batch_draft", return_value=iter(mock_results)):
            result = runner.invoke(
                main,
                ["migrate", "draft", "--root", str(tmp_path)],
                catch_exceptions=False,
            )
        assert result.exit_code == 0
        assert "bad.py" in result.output
        assert "1 failed" in result.output

    def test_draft_help(self) -> None:
        """migrate draft --help works."""
        runner = CliRunner()
        result = runner.invoke(main, ["migrate", "draft", "--help"])
        assert result.exit_code == 0
        assert "--batch" in result.output
        assert "--format" in result.output

    def test_draft_command_registered(self) -> None:
        """migrate draft is registered as a subcommand."""
        runner = CliRunner()
        result = runner.invoke(main, ["migrate", "--help"])
        assert "draft" in result.output

    def test_draft_json_with_error(self, tmp_path: Path) -> None:
        """JSON output includes error details for failures."""
        mock_results = [
            DraftResult(
                source_path="src/fail.py",
                spec_path="src/fail.spec.md",
                success=False,
                error="timeout",
            ),
        ]
        runner = CliRunner()
        with patch("speclord.ai.adapter.ClaudeCodeAdapter"), \
             patch("speclord.migrate.drafter.batch_draft", return_value=iter(mock_results)):
            result = runner.invoke(
                main,
                ["migrate", "draft", "--root", str(tmp_path), "--format", "json"],
                catch_exceptions=False,
            )
        data = json.loads(result.output)
        assert data["results"][0]["error"] == "timeout"
        assert data["results"][0]["success"] is False
