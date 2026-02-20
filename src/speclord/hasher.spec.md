---
specVersion: "0.1.0"
inherits: ".spec.yaml"
type: "utility"
status: "active"
owner: "@speclord-team"
generates: "src/speclord/hasher.py"
---

## Purpose

Content hashing for spec change detection.

## Exported Interface

- `hash_content(text) -> str`

## Behavior

- Returns a hex-encoded SHA-256 digest of the input string
- Deterministic — same input always produces same hash
