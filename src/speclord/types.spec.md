---
specVersion: "0.1.0"
inherits: ".spec.yaml"
type: "data-model"
status: "active"
owner: "@speclord-team"
generates: "src/speclord/types.py"
---

## Purpose

Core data types for the speclord system. All spec representations are frozen dataclasses.

## Exported Interface

- `FileSpec` — parsed .spec.md (frontmatter + body)
- `ServiceSpec` — parsed .spec.yaml service config
- `OrgSpec` — parsed org.spec.yaml
- `LintFinding` — single validation result
- `RegistryEntry` — compiled spec entry
- `ResolvedChain` — file → service → org resolution
- `CoverageReport` — spec coverage metrics
- `VALID_SPEC_TYPES`, `VALID_STATUSES` — allowed values

## Behavior

- Dataclasses with sensible defaults (priority="normal", empty lists/dicts)
- No business logic — pure data containers
