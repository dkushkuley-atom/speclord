"""Tests for the spec drafter."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

from click.testing import CliRunner

from speclord.ai.adapter import MockAdapter
from speclord.ai.draft import draft_spec
from speclord.cli import main

SAMPLE_SPEC = """\
---
specVersion: "0.1.0"
type: "utility"
owner: "@team"
status: "draft"
inherits: ".spec.yaml"
---

## Purpose

Validates user input against defined rules.

## Interface

- `validate(data: dict) -> list[str]` — returns list of error messages

## Behavior

- Returns empty list when all validations pass.
- Returns one message per failed rule.

## Edge Cases

- Empty data dict: returns ["No data provided"].

## Testing Notes

- Test with valid and invalid inputs.
"""


def _write_spec(path: Path, body: str = "Spec body.", **frontmatter: Any) -> Path:
    """Write a minimal .spec.md file."""
    defaults = {
        "specVersion": "0.1.0",
        "type": "utility",
        "owner": "@team",
        "status": "active",
        "inherits": ".spec.yaml",
    }
    defaults.update(frontmatter)
    fm_lines = [f"{k}: {json.dumps(v)}" for k, v in defaults.items()]
    content = "---\n" + "\n".join(fm_lines) + "\n---\n\n" + body
    path.write_text(content, encoding="utf-8")
    return path


# ── draft_spec ──────────────────────────────────────────────────────


class TestDraftSpec:
    def test_returns_string(self, tmp_path: Path) -> None:
        """draft_spec returns a string."""
        adapter = MockAdapter(generate_response=SAMPLE_SPEC)
        result = draft_spec("A validator", Path("src/validate"), tmp_path, adapter)
        assert isinstance(result, str)

    def test_returns_adapter_output(self, tmp_path: Path) -> None:
        """draft_spec returns the adapter's generate output verbatim."""
        adapter = MockAdapter(generate_response=SAMPLE_SPEC)
        result = draft_spec("A validator", Path("src/validate"), tmp_path, adapter)
        assert result == SAMPLE_SPEC

    def test_adapter_receives_description(self, tmp_path: Path) -> None:
        """The prompt sent to the adapter includes the description."""
        adapter = MockAdapter(generate_response="spec")
        draft_spec("Handles user authentication", Path("src/auth"), tmp_path, adapter)
        call = adapter.generate_calls[0]
        assert "Handles user authentication" in call["prompt"]

    def test_adapter_receives_system_prompt(self, tmp_path: Path) -> None:
        """The system prompt is the draft system prompt."""
        adapter = MockAdapter(generate_response="spec")
        draft_spec("A utility", Path("src/util"), tmp_path, adapter)
        call = adapter.generate_calls[0]
        assert "technical specification writer" in call["system"]

    def test_adapter_cwd_is_root(self, tmp_path: Path) -> None:
        """The adapter cwd is the resolved root."""
        adapter = MockAdapter(generate_response="spec")
        draft_spec("A utility", Path("src/util"), tmp_path, adapter)
        call = adapter.generate_calls[0]
        assert call["cwd"] == tmp_path.resolve()

    def test_from_code_reads_source(self, tmp_path: Path) -> None:
        """--from-code reads the existing source file into context."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "auth.py").write_text("def login(): pass", encoding="utf-8")
        adapter = MockAdapter(generate_response="spec")
        draft_spec(
            "Auth module",
            Path("src/auth"),
            tmp_path,
            adapter,
            from_code=True,
        )
        call = adapter.generate_calls[0]
        assert "def login(): pass" in call["prompt"]

    def test_from_code_missing_source(self, tmp_path: Path) -> None:
        """--from-code with no source file still works (no context)."""
        adapter = MockAdapter(generate_response="spec")
        draft_spec(
            "Auth module",
            Path("src/auth"),
            tmp_path,
            adapter,
            from_code=True,
        )
        call = adapter.generate_calls[0]
        # Should still have been called, just without code context
        assert "Auth module" in call["prompt"]

    def test_from_code_exact_file(self, tmp_path: Path) -> None:
        """--from-code works with an exact file path (with extension)."""
        (tmp_path / "util.py").write_text("x = 1", encoding="utf-8")
        adapter = MockAdapter(generate_response="spec")
        draft_spec("A util", Path("util.py"), tmp_path, adapter, from_code=True)
        call = adapter.generate_calls[0]
        assert "x = 1" in call["prompt"]

    def test_type_override_in_prompt(self, tmp_path: Path) -> None:
        """--type adds the spec type to the description."""
        adapter = MockAdapter(generate_response="spec")
        draft_spec(
            "An endpoint",
            Path("src/api"),
            tmp_path,
            adapter,
            spec_type="api-endpoint",
        )
        call = adapter.generate_calls[0]
        assert "api-endpoint" in call["prompt"]

    def test_template_found(self, tmp_path: Path) -> None:
        """When a matching template exists, it's included in the prompt."""
        adapter = MockAdapter(generate_response="spec")
        draft_spec(
            "A utility function",
            Path("src/util"),
            tmp_path,
            adapter,
            spec_type="utility",
        )
        call = adapter.generate_calls[0]
        # The bundled utility template should be found and included
        assert "Template" in call["prompt"] or "template" in call["prompt"].lower()

    def test_project_template_preferred(self, tmp_path: Path) -> None:
        """Project templates in .spec/templates/ take priority."""
        templates_dir = tmp_path / ".spec" / "templates"
        templates_dir.mkdir(parents=True)
        (templates_dir / "utility.spec.md").write_text(
            "---\ncustom: true\n---\nProject template.", encoding="utf-8"
        )
        adapter = MockAdapter(generate_response="spec")
        draft_spec("A util", Path("src/util"), tmp_path, adapter, spec_type="utility")
        call = adapter.generate_calls[0]
        assert "Project template." in call["prompt"]

    def test_no_template_for_unknown_type(self, tmp_path: Path) -> None:
        """Unknown spec types don't cause an error even without a template."""
        adapter = MockAdapter(generate_response="spec")
        result = draft_spec(
            "Something",
            Path("src/thing"),
            tmp_path,
            adapter,
            spec_type="unknown-type",
        )
        assert result == "spec"

    def test_generate_called_once(self, tmp_path: Path) -> None:
        """The adapter's generate method is called exactly once."""
        adapter = MockAdapter(generate_response="spec")
        draft_spec("A utility", Path("src/util"), tmp_path, adapter)
        assert len(adapter.generate_calls) == 1
        assert len(adapter.analyze_calls) == 0


# ── CLI draft command ───────────────────────────────────────────────


class TestDraftCLI:
    def test_draft_writes_file(self, tmp_path: Path) -> None:
        """draft command writes the spec to disk."""
        runner = CliRunner()
        with patch("speclord.ai.adapter.ClaudeCodeAdapter"), \
             patch("speclord.ai.draft.draft_spec", return_value=SAMPLE_SPEC):
            result = runner.invoke(
                main,
                ["draft", "A validator", "src/validate", "--root", str(tmp_path)],
                catch_exceptions=False,
            )
        assert result.exit_code == 0
        output_file = tmp_path / "src" / "validate.spec.md"
        assert output_file.exists()
        assert output_file.read_text(encoding="utf-8") == SAMPLE_SPEC

    def test_draft_output_message(self, tmp_path: Path) -> None:
        """draft command prints a confirmation message."""
        runner = CliRunner()
        with patch("speclord.ai.adapter.ClaudeCodeAdapter"), \
             patch("speclord.ai.draft.draft_spec", return_value=SAMPLE_SPEC):
            result = runner.invoke(
                main,
                ["draft", "A validator", "src/validate", "--root", str(tmp_path)],
                catch_exceptions=False,
            )
        assert "Drafted" in result.output
        assert "validate.spec.md" in result.output

    def test_draft_existing_spec_skips(self, tmp_path: Path) -> None:
        """draft command skips if spec already exists."""
        (tmp_path / "src").mkdir(parents=True)
        (tmp_path / "src" / "validate.spec.md").write_text("existing", encoding="utf-8")
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["draft", "A validator", "src/validate", "--root", str(tmp_path)],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert "already exists" in result.output
        # File should not have been overwritten
        assert (tmp_path / "src" / "validate.spec.md").read_text(encoding="utf-8") == "existing"

    def test_draft_creates_parent_dirs(self, tmp_path: Path) -> None:
        """draft command creates parent directories if needed."""
        runner = CliRunner()
        with patch("speclord.ai.adapter.ClaudeCodeAdapter"), \
             patch("speclord.ai.draft.draft_spec", return_value="spec"):
            result = runner.invoke(
                main,
                ["draft", "Deep module", "src/deep/nested/mod", "--root", str(tmp_path)],
                catch_exceptions=False,
            )
        assert result.exit_code == 0
        assert (tmp_path / "src" / "deep" / "nested" / "mod.spec.md").exists()

    def test_draft_help(self) -> None:
        """draft --help works."""
        runner = CliRunner()
        result = runner.invoke(main, ["draft", "--help"])
        assert result.exit_code == 0
        assert "draft" in result.output.lower()
        assert "--from-code" in result.output
        assert "--type" in result.output

    def test_draft_command_registered(self) -> None:
        """draft command is registered in the CLI group."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert "draft" in result.output

    def test_draft_from_code_flag(self, tmp_path: Path) -> None:
        """--from-code flag is passed through to draft_spec."""
        runner = CliRunner()
        with patch("speclord.ai.adapter.ClaudeCodeAdapter"), \
             patch("speclord.ai.draft.draft_spec", return_value="spec") as mock_draft:
            runner.invoke(
                main,
                ["draft", "Auth module", "src/auth", "--root", str(tmp_path), "--from-code"],
                catch_exceptions=False,
            )
        mock_draft.assert_called_once()
        _, kwargs = mock_draft.call_args
        assert kwargs.get("from_code") is True or mock_draft.call_args[1].get("from_code") is True

    def test_draft_type_flag(self, tmp_path: Path) -> None:
        """--type flag is passed through to draft_spec."""
        runner = CliRunner()
        with patch("speclord.ai.adapter.ClaudeCodeAdapter"), \
             patch("speclord.ai.draft.draft_spec", return_value="spec") as mock_draft:
            runner.invoke(
                main,
                [
                    "draft", "An endpoint", "src/api",
                    "--root", str(tmp_path),
                    "--type", "api-endpoint",
                ],
                catch_exceptions=False,
            )
        mock_draft.assert_called_once()
        _, kwargs = mock_draft.call_args
        assert kwargs.get("spec_type") == "api-endpoint" or \
            mock_draft.call_args[1].get("spec_type") == "api-endpoint"
