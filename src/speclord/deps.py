"""Dependency graph — build, sort, and cycle-detect for spec dependencies."""

from __future__ import annotations

from pathlib import Path

from speclord.errors import CycleError, ParseError
from speclord.parser import discover_specs, parse_file_spec
from speclord.types import DepGraph


def build_dep_graph(root: Path) -> DepGraph:
    """Build a directed dependency graph from all file specs under root.

    Nodes are spec paths relative to root (posix format).
    Edges go from a spec to the specs it depends on.
    Only dependencies that resolve to existing specs are included.
    """
    root = root.resolve()
    adjacency: dict[str, list[str]] = {}

    # Discover all file specs and map absolute path → relative key
    abs_to_rel: dict[Path, str] = {}
    for path in discover_specs(root):
        if not path.name.endswith(".spec.md"):
            continue
        try:
            rel = path.relative_to(root).as_posix()
        except ValueError:
            continue
        abs_to_rel[path.resolve()] = rel
        adjacency[rel] = []

    # Resolve dependencies for each spec
    for abs_path, rel_key in abs_to_rel.items():
        try:
            spec = parse_file_spec(abs_path)
        except ParseError:
            continue

        for dep in spec.dependencies:
            dep_p = Path(dep)
            if not dep_p.suffix:
                resolved = abs_path.parent / f"{dep_p}.spec.md"
            elif dep_p.suffix == ".md":
                resolved = abs_path.parent / dep_p
            else:
                resolved = abs_path.parent / f"{dep_p}.spec.md"

            resolved = resolved.resolve()
            if resolved in abs_to_rel:
                adjacency[rel_key].append(abs_to_rel[resolved])

    return DepGraph(adjacency=adjacency)


def topological_sort(graph: DepGraph) -> list[str]:
    """Return nodes in dependency-first topological order.

    If A depends on B, B appears before A in the result.
    Raises CycleError if the graph contains a cycle.
    """
    # DFS coloring: 0=unvisited, 1=in-progress, 2=done
    color: dict[str, int] = {node: 0 for node in graph.adjacency}
    order: list[str] = []
    path: list[str] = []

    def visit(node: str) -> None:
        if color[node] == 2:
            return
        if color[node] == 1:
            cycle_start = path.index(node)
            raise CycleError(path[cycle_start:] + [node])

        color[node] = 1
        path.append(node)

        for dep in graph.adjacency.get(node, []):
            visit(dep)

        path.pop()
        color[node] = 2
        order.append(node)

    for node in sorted(graph.adjacency):
        visit(node)

    return order


def get_dep_tree(graph: DepGraph, node: str) -> dict[str, object]:
    """Get the recursive dependency tree for a single node.

    Returns a nested dict where keys are spec names and values
    are their own dependency trees. Circular refs are marked.
    """
    visited: set[str] = set()

    def _build(n: str) -> dict[str, object]:
        if n in visited:
            return {"(circular)": {}}
        visited.add(n)
        deps = graph.adjacency.get(n, [])
        result = {dep: _build(dep) for dep in deps}
        visited.discard(n)
        return result

    return {node: _build(node)}
