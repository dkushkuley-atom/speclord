"""Tests for the AI adapter layer."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from speclord.ai.adapter import ClaudeCodeAdapter, LLMAdapter, MockAdapter
from speclord.errors import AIError


class TestMockAdapter:
    def test_satisfies_protocol(self) -> None:
        """MockAdapter is recognized as an LLMAdapter."""
        adapter = MockAdapter()
        assert isinstance(adapter, LLMAdapter)

    def test_analyze_returns_configured_response(self, tmp_path: Path) -> None:
        """analyze() returns the response passed to the constructor."""
        response = {"drift": "none", "score": 100}
        adapter = MockAdapter(analyze_response=response)
        result = adapter.analyze("prompt", "system", tmp_path, {"type": "object"})
        assert result == response

    def test_analyze_returns_copy(self, tmp_path: Path) -> None:
        """analyze() returns a copy, not a reference to the original."""
        response = {"key": "value"}
        adapter = MockAdapter(analyze_response=response)
        result = adapter.analyze("p", "s", tmp_path, {})
        result["key"] = "modified"
        assert adapter.analyze_response["key"] == "value"

    def test_analyze_default_empty_dict(self, tmp_path: Path) -> None:
        """Default analyze response is empty dict."""
        adapter = MockAdapter()
        result = adapter.analyze("p", "s", tmp_path, {})
        assert result == {}

    def test_analyze_tracks_calls(self, tmp_path: Path) -> None:
        """analyze() records all calls for assertion."""
        adapter = MockAdapter()
        schema: dict[str, Any] = {"type": "object"}
        adapter.analyze("prompt1", "sys1", tmp_path, schema)
        adapter.analyze("prompt2", "sys2", tmp_path, schema)
        assert len(adapter.analyze_calls) == 2
        assert adapter.analyze_calls[0]["prompt"] == "prompt1"
        assert adapter.analyze_calls[1]["prompt"] == "prompt2"

    def test_analyze_call_captures_all_args(self, tmp_path: Path) -> None:
        """Each recorded call has all four arguments."""
        adapter = MockAdapter()
        schema: dict[str, Any] = {"type": "object"}
        adapter.analyze("p", "s", tmp_path, schema)
        call = adapter.analyze_calls[0]
        assert call["prompt"] == "p"
        assert call["system"] == "s"
        assert call["cwd"] == tmp_path
        assert call["schema"] == schema

    def test_generate_returns_configured_response(self, tmp_path: Path) -> None:
        """generate() returns the text passed to the constructor."""
        adapter = MockAdapter(generate_response="# Generated Spec")
        result = adapter.generate("prompt", "system", tmp_path)
        assert result == "# Generated Spec"

    def test_generate_default_empty_string(self, tmp_path: Path) -> None:
        """Default generate response is empty string."""
        adapter = MockAdapter()
        result = adapter.generate("p", "s", tmp_path)
        assert result == ""

    def test_generate_tracks_calls(self, tmp_path: Path) -> None:
        """generate() records all calls for assertion."""
        adapter = MockAdapter()
        adapter.generate("prompt1", "sys1", tmp_path)
        adapter.generate("prompt2", "sys2", tmp_path)
        assert len(adapter.generate_calls) == 2
        assert adapter.generate_calls[0]["prompt"] == "prompt1"
        assert adapter.generate_calls[1]["system"] == "sys2"

    def test_generate_call_captures_all_args(self, tmp_path: Path) -> None:
        """Each recorded call has all three arguments."""
        adapter = MockAdapter()
        adapter.generate("p", "s", tmp_path)
        call = adapter.generate_calls[0]
        assert call["prompt"] == "p"
        assert call["system"] == "s"
        assert call["cwd"] == tmp_path


class TestClaudeCodeAdapter:
    def test_satisfies_protocol(self) -> None:
        """ClaudeCodeAdapter is recognized as an LLMAdapter."""
        adapter = ClaudeCodeAdapter()
        assert isinstance(adapter, LLMAdapter)

    def test_default_config(self) -> None:
        """Default model is sonnet, max_turns is 10."""
        adapter = ClaudeCodeAdapter()
        assert adapter.model == "sonnet"
        assert adapter.max_turns == 10

    def test_custom_config(self) -> None:
        """Constructor accepts custom model and max_turns."""
        adapter = ClaudeCodeAdapter(model="opus", max_turns=25)
        assert adapter.model == "opus"
        assert adapter.max_turns == 25

    def test_analyze_cli_not_found(self, tmp_path: Path) -> None:
        """analyze() raises AIError when claude CLI is missing."""
        adapter = ClaudeCodeAdapter()
        with patch(
            "speclord.ai.adapter.subprocess.run",
            side_effect=FileNotFoundError,
        ):
            with pytest.raises(AIError, match="Claude CLI not found"):
                adapter.analyze("p", "s", tmp_path, {})

    def test_generate_cli_not_found(self, tmp_path: Path) -> None:
        """generate() raises AIError when claude CLI is missing."""
        adapter = ClaudeCodeAdapter()
        with patch(
            "speclord.ai.adapter.subprocess.run",
            side_effect=FileNotFoundError,
        ):
            with pytest.raises(AIError, match="Claude CLI not found"):
                adapter.generate("p", "s", tmp_path)

    def test_analyze_invalid_json(self, tmp_path: Path) -> None:
        """analyze() raises AIError when model returns non-JSON."""
        adapter = ClaudeCodeAdapter()
        mock_result = type("R", (), {"stdout": "not json", "returncode": 0})()
        with patch(
            "speclord.ai.adapter.subprocess.run",
            return_value=mock_result,
        ):
            with pytest.raises(AIError, match="invalid JSON"):
                adapter.analyze("p", "s", tmp_path, {})

    def test_analyze_valid_json(self, tmp_path: Path) -> None:
        """analyze() parses valid JSON from CLI output."""
        adapter = ClaudeCodeAdapter()
        response = '{"score": 95, "issues": []}'
        mock_result = type("R", (), {"stdout": response, "returncode": 0})()
        with patch(
            "speclord.ai.adapter.subprocess.run",
            return_value=mock_result,
        ):
            result = adapter.analyze("p", "s", tmp_path, {})
        assert result == {"score": 95, "issues": []}

    def test_generate_returns_stdout(self, tmp_path: Path) -> None:
        """generate() returns stripped CLI stdout."""
        adapter = ClaudeCodeAdapter()
        mock_result = type(
            "R", (), {"stdout": "  generated text  \n", "returncode": 0}
        )()
        with patch(
            "speclord.ai.adapter.subprocess.run",
            return_value=mock_result,
        ):
            result = adapter.generate("p", "s", tmp_path)
        assert result == "generated text"


class TestAIError:
    def test_inherits_speclord_error(self) -> None:
        """AIError is a SpeclordError."""
        from speclord.errors import SpeclordError

        err = AIError("test")
        assert isinstance(err, SpeclordError)

    def test_message(self) -> None:
        """AIError carries the message."""
        err = AIError("model failed")
        assert str(err) == "model failed"

    def test_suggestion(self) -> None:
        """AIError supports suggestion kwarg."""
        err = AIError("fail", suggestion="try again")
        assert err.suggestion == "try again"
