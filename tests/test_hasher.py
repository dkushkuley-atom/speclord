"""Tests for content hashing."""

from __future__ import annotations

from speclord.hasher import hash_content


def test_consistent_hash() -> None:
    h1 = hash_content("hello world")
    h2 = hash_content("hello world")
    assert h1 == h2


def test_different_content_different_hash() -> None:
    h1 = hash_content("hello")
    h2 = hash_content("world")
    assert h1 != h2


def test_returns_hex_string() -> None:
    h = hash_content("test")
    assert len(h) == 64  # sha256 hex is 64 chars
    assert all(c in "0123456789abcdef" for c in h)


def test_empty_string() -> None:
    h = hash_content("")
    assert len(h) == 64
