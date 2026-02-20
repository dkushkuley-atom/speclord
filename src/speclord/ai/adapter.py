"""LLM adapter — protocol and implementations for AI calls."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from speclord.errors import AIError


@runtime_checkable
class LLMAdapter(Protocol):
    """Protocol for AI backends used by analysis and generation commands."""

    def analyze(
        self,
        prompt: str,
        system: str,
        cwd: Path,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        """Send a prompt and get structured JSON back.

        The adapter should instruct the model to return JSON matching
        the provided schema. Used for drift analysis, spec review, etc.
        """
        ...

    def generate(
        self,
        prompt: str,
        system: str,
        cwd: Path,
    ) -> str:
        """Send a prompt and get free-form text back.

        Used for spec drafting and other generative tasks.
        """
        ...


class MockAdapter:
    """Test adapter that returns canned responses.

    Records all calls for assertion in tests.
    """

    def __init__(
        self,
        analyze_response: dict[str, Any] | None = None,
        generate_response: str | None = None,
    ) -> None:
        self.analyze_response = analyze_response or {}
        self.generate_response = generate_response or ""
        self.analyze_calls: list[dict[str, Any]] = []
        self.generate_calls: list[dict[str, Any]] = []

    def analyze(
        self,
        prompt: str,
        system: str,
        cwd: Path,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        self.analyze_calls.append({
            "prompt": prompt,
            "system": system,
            "cwd": cwd,
            "schema": schema,
        })
        return dict(self.analyze_response)

    def generate(
        self,
        prompt: str,
        system: str,
        cwd: Path,
    ) -> str:
        self.generate_calls.append({
            "prompt": prompt,
            "system": system,
            "cwd": cwd,
        })
        return self.generate_response


class ClaudeCodeAdapter:
    """Real adapter that calls the Claude Code CLI.

    Requires ``claude`` to be installed and available on PATH.
    Uses ``--print`` mode for non-interactive single-turn output.
    """

    def __init__(
        self,
        model: str = "sonnet",
        max_turns: int = 10,
    ) -> None:
        self.model = model
        self.max_turns = max_turns

    def analyze(
        self,
        prompt: str,
        system: str,
        cwd: Path,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        schema_text = json.dumps(schema, indent=2)
        full_prompt = (
            f"{prompt}\n\n"
            f"Return ONLY valid JSON matching this schema:\n"
            f"{schema_text}"
        )
        raw = self._call(full_prompt, system, cwd)
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise AIError(
                f"Model returned invalid JSON: {e}",
                suggestion="Try again or use a different model.",
            ) from e

    def generate(
        self,
        prompt: str,
        system: str,
        cwd: Path,
    ) -> str:
        return self._call(prompt, system, cwd)

    def _call(self, prompt: str, system: str, cwd: Path) -> str:
        """Run the claude CLI and return stdout."""
        cmd = [
            "claude",
            "--print",
            "--model", self.model,
            "--max-turns", str(self.max_turns),
        ]
        if system:
            cmd.extend(["--system-prompt", system])

        try:
            result = subprocess.run(
                cmd,
                input=prompt,
                capture_output=True,
                text=True,
                cwd=str(cwd),
                check=True,
            )
        except FileNotFoundError:
            raise AIError(
                "Claude CLI not found. Install it with: npm i -g @anthropic-ai/claude-code",
                suggestion="Ensure 'claude' is on your PATH.",
            )
        except subprocess.CalledProcessError as e:
            raise AIError(
                f"Claude CLI failed (exit {e.returncode}): {e.stderr.strip()}",
            ) from e

        return result.stdout.strip()
