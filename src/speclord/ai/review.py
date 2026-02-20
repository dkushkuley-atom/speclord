"""Spec reviewer — AI-powered quality assessment of spec files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from speclord.ai.adapter import LLMAdapter
from speclord.ai.prompts import build_review_prompt
from speclord.parser import parse_file_spec
from speclord.types import ReviewSuggestion, SpecReview

# JSON schema the adapter sends to the model
_REVIEW_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "score": {"type": "integer", "minimum": 0, "maximum": 100},
        "summary": {"type": "string"},
        "suggestions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "suggestion": {"type": "string"},
                    "priority": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                    },
                },
            },
        },
    },
}


def review_spec(
    spec_path: Path,
    root: Path,
    adapter: LLMAdapter,
) -> SpecReview:
    """Review a file spec for quality using AI.

    Parses the spec, builds a review prompt, and asks the AI to
    evaluate clarity, completeness, and actionability.

    Args:
        spec_path: Path to the .spec.md file.
        root: Project root directory.
        adapter: The LLM adapter to use for review.

    Returns:
        A SpecReview with score and suggestions.
    """
    spec_path = spec_path.resolve()
    root = root.resolve()

    file_spec = parse_file_spec(spec_path)
    prompt, system = build_review_prompt(file_spec)
    raw = adapter.analyze(prompt, system, root, _REVIEW_SCHEMA)

    try:
        rel = spec_path.relative_to(root).as_posix()
    except ValueError:
        rel = str(spec_path)

    return _parse_response(rel, raw)


def _parse_response(spec_path: str, raw: dict[str, Any]) -> SpecReview:
    """Convert the raw AI response dict into a SpecReview."""
    score = raw.get("score", 0)
    if not isinstance(score, int):
        try:
            score = int(score)
        except (TypeError, ValueError):
            score = 0
    score = max(0, min(100, score))

    summary = raw.get("summary", "")
    raw_suggestions = raw.get("suggestions", [])

    suggestions: list[ReviewSuggestion] = []
    for s in raw_suggestions:
        if not isinstance(s, dict):
            continue
        suggestions.append(
            ReviewSuggestion(
                category=s.get("category", ""),
                suggestion=s.get("suggestion", ""),
                priority=s.get("priority", "medium"),
            )
        )

    return SpecReview(
        spec_path=spec_path,
        score=score,
        summary=summary,
        suggestions=suggestions,
    )
