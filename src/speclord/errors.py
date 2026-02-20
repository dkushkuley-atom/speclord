"""Custom error types for speclord."""

from __future__ import annotations


class SpeclordError(Exception):
    """Base error for all speclord operations.

    Attributes:
        filepath: Path to the file that caused the error (if applicable).
        suggestion: Actionable fix recommendation.
    """

    def __init__(
        self,
        message: str,
        *,
        filepath: str | None = None,
        suggestion: str | None = None,
    ) -> None:
        super().__init__(message)
        self.filepath = filepath
        self.suggestion = suggestion


class ParseError(SpeclordError):
    """Raised when a spec file cannot be parsed."""


class ValidationError(SpeclordError):
    """Raised when a spec fails validation."""


class ResolutionError(SpeclordError):
    """Raised when the inherits chain cannot be resolved."""


class ConfigError(SpeclordError):
    """Raised when a config file is malformed or contains invalid values."""


class CycleError(SpeclordError):
    """Raised when a dependency cycle is detected in the spec graph."""

    def __init__(self, cycle: list[str]) -> None:
        self.cycle = cycle
        path = " → ".join(cycle)
        super().__init__(f"Dependency cycle detected: {path}")


class AIError(SpeclordError):
    """Raised when an AI adapter call fails."""
