---
specVersion: "0.1.0"
inherits: ".spec.yaml"
type: "utility"
status: "active"
owner: "@speclord-team"
generates: "src/speclord/registry.py"
dependencies:
  - "src/speclord/parser.spec.md"
  - "src/speclord/hasher.spec.md"
---

## Purpose

Compile all file specs into a registry.lock.json snapshot for fast lookups.

## Exported Interface

- `compile_registry(root) -> dict`

## Behavior

- Discovers all file specs, parses them, computes content hashes
- Writes registry.lock.json to root with specs dict + errors list
- Gracefully handles parse errors (records in errors list)
