---
specVersion: "0.1.0"
inherits: ".spec.yaml"
type: "utility"
status: "active"
owner: "@speclord-team"
generates: "src/speclord/context.py"
dependencies:
  - "src/speclord/resolver.spec.md"
  - "src/speclord/types.spec.md"
---

## Purpose

Build AI-ready context text from a spec's resolved inheritance chain.

## Exported Interface

- `build_context(spec_path, root) -> str`

## Behavior

- Resolves the full chain (org → service → file) and formats as structured markdown
- Includes org constraints, service conventions, file metadata, and markdown body
- Omits absent layers (no org section if no org spec found)
