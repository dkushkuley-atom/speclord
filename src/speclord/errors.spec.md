---
specVersion: "0.1.0"
inherits: ".spec.yaml"
type: "utility"
status: "active"
owner: "@speclord-team"
generates: "src/speclord/errors.py"
---

## Purpose

Typed error hierarchy for speclord. All errors carry optional filepath and suggestion.

## Exported Interface

- `SpeclordError` — base exception
- `ParseError` — spec file parsing failures
- `ValidationError` — schema validation failures
- `ResolutionError` — chain resolution failures
- `ConfigError` — config loading failures

## Behavior

- All inherit from `SpeclordError`
- `filepath` and `suggestion` are optional keyword-only attributes
