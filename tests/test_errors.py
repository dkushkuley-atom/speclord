"""Tests for custom error types."""

from __future__ import annotations

from speclord.errors import ParseError, ResolutionError, SpeclordError, ValidationError


def test_speclord_error_basic() -> None:
    err = SpeclordError("something broke")
    assert str(err) == "something broke"
    assert err.filepath is None
    assert err.suggestion is None


def test_speclord_error_with_fields() -> None:
    err = SpeclordError(
        "bad spec",
        filepath="src/auth/login.spec.md",
        suggestion="Add a specVersion field",
    )
    assert str(err) == "bad spec"
    assert err.filepath == "src/auth/login.spec.md"
    assert err.suggestion == "Add a specVersion field"


def test_parse_error_inherits() -> None:
    err = ParseError("invalid YAML", filepath="broken.spec.md")
    assert isinstance(err, SpeclordError)
    assert err.filepath == "broken.spec.md"


def test_validation_error_inherits() -> None:
    err = ValidationError("missing required field")
    assert isinstance(err, SpeclordError)


def test_resolution_error_inherits() -> None:
    err = ResolutionError(
        "circular dependency",
        filepath="a.spec.md",
        suggestion="Check the inherits chain",
    )
    assert isinstance(err, SpeclordError)
    assert err.suggestion == "Check the inherits chain"
