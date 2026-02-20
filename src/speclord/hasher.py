"""Content hashing for spec change detection."""

from __future__ import annotations

import hashlib


def hash_content(content: str) -> str:
    """Return a sha256 hex digest of the given content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
