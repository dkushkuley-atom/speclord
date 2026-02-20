---
specVersion: "0.1.0"
inherits: ".spec.yaml"
type: "utility"
status: "active"
owner: "@speclord-team"
generates: "src/speclord/resolver.py"
dependencies:
  - "src/speclord/parser.spec.md"
  - "src/speclord/types.spec.md"
  - "src/speclord/errors.spec.md"
---

## Purpose

Resolve the inheritance chain for a file spec: file → service → org.

## Exported Interface

- `resolve_chain(spec_path, root) -> ResolvedChain`

## Behavior

- Follows `inherits` field to walk up the chain
- Returns `ResolvedChain` with optional service_spec and org_spec
- Raises `ResolutionError` if inherits path doesn't resolve
