---
specVersion: "0.1.0"
inherits: ".spec.yaml"
type: "utility"
status: "active"
owner: "@speclord-team"
generates: "src/speclord/parser.py"
dependencies:
  - "src/speclord/types.spec.md"
  - "src/speclord/errors.spec.md"
---

## Purpose

Parse spec files from disk into typed dataclasses. Discover all spec files in a project tree.

## Exported Interface

- `parse_file_spec(path) -> FileSpec`
- `parse_service_spec(path) -> ServiceSpec`
- `parse_org_spec(path) -> OrgSpec`
- `discover_specs(root) -> list[Path]`

## Behavior

- Uses python-frontmatter for .spec.md, PyYAML for .spec.yaml
- Raises `ParseError` with filepath and suggestion on failure
- `discover_specs` skips IGNORE_DIRS (node_modules, .git, __pycache__, etc.)
