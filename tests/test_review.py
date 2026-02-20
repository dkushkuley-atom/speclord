"""Tests for the spec reviewer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from speclord.ai.adapter import MockAdapter
from speclord.ai.review import review_spec
from speclord.cli import main
from speclord.types import SpecReview


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


def _mock_review_response(
    score: int = 85,
    summary: str = "Well-structured spec.",
    suggestions: list[dict[str, str]] | None = None,
) -> MockAdapter:
    """Create a MockAdapter that returns a review response."""
    response: dict[str, Any] = {
        "score": score,
        "summary": summary,
        "suggestions": suggestions or [],
    }
    return MockAdapter(analyze_response=response)


# ── review_spec ──────────────────────────────────────────────────────


class TestReviewSpec:
    def test_returns_spec_review(self, tmp_path: Path) -> None:
        """review_spec returns a SpecReview."""
        _write_spec(tmp_path / "hello.spec.md")
        adapter = _mock_review_response()
        result = review_spec(tmp_path / "hello.spec.md", tmp_path, adapter)
        assert isinstance(result, SpecReview)

    def test_review_has_spec_path(self, tmp_path: Path) -> None:
        """SpecReview carries the relative spec path."""
        _write_spec(tmp_path / "hello.spec.md")
        adapter = _mock_review_response()
        result = review_spec(tmp_path / "hello.spec.md", tmp_path, adapter)
        assert result.spec_path == "hello.spec.md"

    def test_review_has_score(self, tmp_path: Path) -> None:
        """SpecReview carries the AI score."""
        _write_spec(tmp_path / "hello.spec.md")
        adapter = _mock_review_response(score=92)
        result = review_spec(tmp_path / "hello.spec.md", tmp_path, adapter)
        assert result.score == 92

    def test_review_has_summary(self, tmp_path: Path) -> None:
        """SpecReview carries the AI summary."""
        _write_spec(tmp_path / "hello.spec.md")
        adapter = _mock_review_response(summary="Good coverage.")
        result = review_spec(tmp_path / "hello.spec.md", tmp_path, adapter)
        assert result.summary == "Good coverage."

    def test_review_with_suggestions(self, tmp_path: Path) -> None:
        """Suggestions from the AI are parsed into ReviewSuggestion objects."""
        _write_spec(tmp_path / "hello.spec.md")
        adapter = _mock_review_response(suggestions=[
            {
                "category": "Completeness",
                "suggestion": "Add error handling section",
                "priority": "high",
            },
            {
                "category": "Clarity",
                "suggestion": "Define return types",
                "priority": "medium",
            },
        ])
        result = review_spec(tmp_path / "hello.spec.md", tmp_path, adapter)
        assert len(result.suggestions) == 2
        assert result.suggestions[0].category == "Completeness"
        assert result.suggestions[0].priority == "high"
        assert result.suggestions[1].category == "Clarity"

    def test_score_clamped_high(self, tmp_path: Path) -> None:
        """Score above 100 is clamped to 100."""
        _write_spec(tmp_path / "hello.spec.md")
        adapter = MockAdapter(analyze_response={"score": 150, "summary": "", "suggestions": []})
        result = review_spec(tmp_path / "hello.spec.md", tmp_path, adapter)
        assert result.score == 100

    def test_score_clamped_low(self, tmp_path: Path) -> None:
        """Score below 0 is clamped to 0."""
        _write_spec(tmp_path / "hello.spec.md")
        adapter = MockAdapter(analyze_response={"score": -10, "summary": "", "suggestions": []})
        result = review_spec(tmp_path / "hello.spec.md", tmp_path, adapter)
        assert result.score == 0

    def test_score_defaults_to_zero(self, tmp_path: Path) -> None:
        """Missing score defaults to 0."""
        _write_spec(tmp_path / "hello.spec.md")
        adapter = MockAdapter(analyze_response={"summary": "no score"})
        result = review_spec(tmp_path / "hello.spec.md", tmp_path, adapter)
        assert result.score == 0

    def test_malformed_suggestion_skipped(self, tmp_path: Path) -> None:
        """Non-dict entries in suggestions are skipped."""
        _write_spec(tmp_path / "hello.spec.md")
        adapter = MockAdapter(analyze_response={
            "score": 80,
            "summary": "",
            "suggestions": [
                "not a dict",
                {"category": "x", "suggestion": "ok", "priority": "low"},
            ],
        })
        result = review_spec(tmp_path / "hello.spec.md", tmp_path, adapter)
        assert len(result.suggestions) == 1

    def test_suggestion_default_priority(self, tmp_path: Path) -> None:
        """Suggestions without priority default to medium."""
        _write_spec(tmp_path / "hello.spec.md")
        adapter = MockAdapter(analyze_response={
            "score": 70,
            "summary": "",
            "suggestions": [{"category": "x", "suggestion": "y"}],
        })
        result = review_spec(tmp_path / "hello.spec.md", tmp_path, adapter)
        assert result.suggestions[0].priority == "medium"

    def test_adapter_receives_schema(self, tmp_path: Path) -> None:
        """The adapter is called with the review JSON schema."""
        _write_spec(tmp_path / "hello.spec.md")
        adapter = _mock_review_response()
        review_spec(tmp_path / "hello.spec.md", tmp_path, adapter)
        schema = adapter.analyze_calls[0]["schema"]
        assert schema["type"] == "object"
        assert "score" in schema["properties"]
        assert "suggestions" in schema["properties"]

    def test_prompt_contains_spec_body(self, tmp_path: Path) -> None:
        """The prompt sent to the adapter includes the spec body."""
        _write_spec(tmp_path / "hello.spec.md", body="Must validate input.")
        adapter = _mock_review_response()
        review_spec(tmp_path / "hello.spec.md", tmp_path, adapter)
        call = adapter.analyze_calls[0]
        assert "Must validate input." in call["prompt"]

    def test_prompt_contains_spec_type(self, tmp_path: Path) -> None:
        """The prompt includes the spec type."""
        _write_spec(tmp_path / "hello.spec.md", type="api-endpoint")
        adapter = _mock_review_response()
        review_spec(tmp_path / "hello.spec.md", tmp_path, adapter)
        call = adapter.analyze_calls[0]
        assert "api-endpoint" in call["prompt"]

    def test_parse_error_propagates(self, tmp_path: Path) -> None:
        """ParseError from a malformed spec propagates."""
        from speclord.errors import ParseError

        (tmp_path / "bad.spec.md").write_text("not valid frontmatter", encoding="utf-8")
        adapter = _mock_review_response()
        with pytest.raises(ParseError):
            review_spec(tmp_path / "bad.spec.md", tmp_path, adapter)


# ── CLI review command ───────────────────────────────────────────────


class TestReviewCLI:
    def _setup_project(self, tmp_path: Path) -> Path:
        """Set up a minimal project with a spec file."""
        _write_spec(tmp_path / "hello.spec.md", body="Says hello.")
        return tmp_path

    def test_review_json_output(self, tmp_path: Path) -> None:
        """--format json produces valid JSON with expected structure."""
        self._setup_project(tmp_path)
        mock_review = SpecReview(
            spec_path="hello.spec.md",
            score=85,
            summary="Good spec.",
            suggestions=[],
        )
        runner = CliRunner()
        with patch("speclord.ai.adapter.ClaudeCodeAdapter"), \
             patch("speclord.ai.review.review_spec", return_value=mock_review):
            result = runner.invoke(
                main,
                [
                    "review", str(tmp_path / "hello.spec.md"),
                    "--root", str(tmp_path), "--format", "json",
                ],
                catch_exceptions=False,
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["spec"] == "hello.spec.md"
        assert data["score"] == 85

    def test_review_text_output(self, tmp_path: Path) -> None:
        """Text mode shows score and summary."""
        self._setup_project(tmp_path)
        mock_review = SpecReview(
            spec_path="hello.spec.md",
            score=72,
            summary="Needs more detail.",
            suggestions=[],
        )
        runner = CliRunner()
        with patch("speclord.ai.adapter.ClaudeCodeAdapter"), \
             patch("speclord.ai.review.review_spec", return_value=mock_review):
            result = runner.invoke(
                main,
                ["review", str(tmp_path / "hello.spec.md"), "--root", str(tmp_path)],
                catch_exceptions=False,
            )
        assert result.exit_code == 0
        assert "72" in result.output
        assert "Needs more detail" in result.output

    def test_review_text_with_suggestions(self, tmp_path: Path) -> None:
        """Text mode shows suggestions."""
        from speclord.types import ReviewSuggestion

        self._setup_project(tmp_path)
        mock_review = SpecReview(
            spec_path="hello.spec.md",
            score=60,
            summary="Incomplete.",
            suggestions=[
                ReviewSuggestion(
                    category="Completeness",
                    suggestion="Add error handling",
                    priority="high",
                ),
            ],
        )
        runner = CliRunner()
        with patch("speclord.ai.adapter.ClaudeCodeAdapter"), \
             patch("speclord.ai.review.review_spec", return_value=mock_review):
            result = runner.invoke(
                main,
                ["review", str(tmp_path / "hello.spec.md"), "--root", str(tmp_path)],
                catch_exceptions=False,
            )
        assert result.exit_code == 0
        assert "Add error handling" in result.output

    def test_review_help(self) -> None:
        """review --help works."""
        runner = CliRunner()
        result = runner.invoke(main, ["review", "--help"])
        assert result.exit_code == 0
        assert "review" in result.output.lower()
        assert "--format" in result.output

    def test_review_command_registered(self) -> None:
        """review command is registered in the CLI group."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert "review" in result.output

    def test_review_file_not_found(self) -> None:
        """review on a nonexistent file exits 1."""
        runner = CliRunner()
        result = runner.invoke(main, ["review", "/nonexistent/file.spec.md", "--root", "."])
        assert result.exit_code != 0

    def test_review_json_with_suggestions(self, tmp_path: Path) -> None:
        """JSON output includes suggestions array."""
        from speclord.types import ReviewSuggestion

        self._setup_project(tmp_path)
        mock_review = SpecReview(
            spec_path="hello.spec.md",
            score=55,
            summary="Needs work.",
            suggestions=[
                ReviewSuggestion(category="Clarity", suggestion="Be specific", priority="medium"),
            ],
        )
        runner = CliRunner()
        with patch("speclord.ai.adapter.ClaudeCodeAdapter"), \
             patch("speclord.ai.review.review_spec", return_value=mock_review):
            result = runner.invoke(
                main,
                [
                    "review", str(tmp_path / "hello.spec.md"),
                    "--root", str(tmp_path), "--format", "json",
                ],
                catch_exceptions=False,
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data["suggestions"]) == 1
        assert data["suggestions"][0]["category"] == "Clarity"
