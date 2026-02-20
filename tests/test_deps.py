"""Tests for the dependency graph module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from speclord.cli import main
from speclord.deps import build_dep_graph, get_dep_tree, topological_sort
from speclord.errors import CycleError


def _write_spec(
    path: Path,
    *,
    inherits: str = ".spec.yaml",
    dependencies: list[str] | None = None,
    body: str = "Body.",
) -> None:
    deps_yaml = ""
    if dependencies:
        deps_yaml = "dependencies:\n"
        for dep in dependencies:
            deps_yaml += f"  - '{dep}'\n"
    content = (
        f"---\nspecVersion: '0.1.0'\ninherits: '{inherits}'\n"
        f"type: utility\nstatus: active\nowner: '@dev'\n"
        f"{deps_yaml}---\n{body}\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _write_inherits(tmp_path: Path) -> None:
    (tmp_path / ".spec.yaml").write_text(
        "specVersion: '0.1.0'\ninherits: 'org.spec.yaml'\n"
        "service: test\nowner: '@dev'\n"
    )


class TestBuildDepGraph:
    def test_no_deps(self, tmp_path: Path) -> None:
        """Specs without dependencies → all nodes, no edges."""
        _write_inherits(tmp_path)
        _write_spec(tmp_path / "a.spec.md")
        _write_spec(tmp_path / "b.spec.md")
        graph = build_dep_graph(tmp_path)
        assert "a.spec.md" in graph.adjacency
        assert "b.spec.md" in graph.adjacency
        assert graph.adjacency["a.spec.md"] == []
        assert graph.adjacency["b.spec.md"] == []

    def test_simple_deps(self, tmp_path: Path) -> None:
        """A depends on B → edge from A to B."""
        _write_inherits(tmp_path)
        _write_spec(tmp_path / "a.spec.md", dependencies=["b"])
        _write_spec(tmp_path / "b.spec.md")
        graph = build_dep_graph(tmp_path)
        assert graph.adjacency["a.spec.md"] == ["b.spec.md"]
        assert graph.adjacency["b.spec.md"] == []

    def test_diamond_deps(self, tmp_path: Path) -> None:
        """Diamond: A→B, A→C, B→D, C→D."""
        _write_inherits(tmp_path)
        _write_spec(tmp_path / "a.spec.md", dependencies=["b", "c"])
        _write_spec(tmp_path / "b.spec.md", dependencies=["d"])
        _write_spec(tmp_path / "c.spec.md", dependencies=["d"])
        _write_spec(tmp_path / "d.spec.md")
        graph = build_dep_graph(tmp_path)
        assert sorted(graph.adjacency["a.spec.md"]) == ["b.spec.md", "c.spec.md"]
        assert graph.adjacency["b.spec.md"] == ["d.spec.md"]
        assert graph.adjacency["c.spec.md"] == ["d.spec.md"]
        assert graph.adjacency["d.spec.md"] == []

    def test_broken_dep_excluded(self, tmp_path: Path) -> None:
        """Dependency pointing to nonexistent spec → not in adjacency list."""
        _write_inherits(tmp_path)
        _write_spec(tmp_path / "a.spec.md", dependencies=["missing"])
        graph = build_dep_graph(tmp_path)
        assert graph.adjacency["a.spec.md"] == []

    def test_empty_repo(self, tmp_path: Path) -> None:
        """No specs → empty graph."""
        graph = build_dep_graph(tmp_path)
        assert graph.adjacency == {}

    def test_subdirectory_specs(self, tmp_path: Path) -> None:
        """Specs in subdirs are included with relative paths."""
        _write_inherits(tmp_path)
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / ".spec.yaml").write_text(
            "specVersion: '0.1.0'\ninherits: '../.spec.yaml'\n"
            "service: sub\nowner: '@dev'\n"
        )
        _write_spec(sub / "x.spec.md", inherits=".spec.yaml")
        graph = build_dep_graph(tmp_path)
        assert "sub/x.spec.md" in graph.adjacency

    def test_parse_error_skipped(self, tmp_path: Path) -> None:
        """Malformed spec → skipped (not in graph or crash)."""
        _write_inherits(tmp_path)
        bad = tmp_path / "bad.spec.md"
        bad.write_text("not valid frontmatter")
        _write_spec(tmp_path / "good.spec.md")
        graph = build_dep_graph(tmp_path)
        # bad.spec.md has no adjacency entry (parse failed before adding deps)
        # good.spec.md should still be present
        assert "good.spec.md" in graph.adjacency


class TestTopologicalSort:
    def test_no_deps(self, tmp_path: Path) -> None:
        """All independent → returns all nodes (sorted by name)."""
        _write_inherits(tmp_path)
        _write_spec(tmp_path / "a.spec.md")
        _write_spec(tmp_path / "b.spec.md")
        graph = build_dep_graph(tmp_path)
        order = topological_sort(graph)
        assert set(order) == {"a.spec.md", "b.spec.md"}

    def test_linear_chain(self, tmp_path: Path) -> None:
        """A → B → C → topo order is [C, B, A]."""
        _write_inherits(tmp_path)
        _write_spec(tmp_path / "a.spec.md", dependencies=["b"])
        _write_spec(tmp_path / "b.spec.md", dependencies=["c"])
        _write_spec(tmp_path / "c.spec.md")
        graph = build_dep_graph(tmp_path)
        order = topological_sort(graph)
        assert order.index("c.spec.md") < order.index("b.spec.md")
        assert order.index("b.spec.md") < order.index("a.spec.md")

    def test_diamond(self, tmp_path: Path) -> None:
        """Diamond: D appears before B and C, which appear before A."""
        _write_inherits(tmp_path)
        _write_spec(tmp_path / "a.spec.md", dependencies=["b", "c"])
        _write_spec(tmp_path / "b.spec.md", dependencies=["d"])
        _write_spec(tmp_path / "c.spec.md", dependencies=["d"])
        _write_spec(tmp_path / "d.spec.md")
        graph = build_dep_graph(tmp_path)
        order = topological_sort(graph)
        assert order.index("d.spec.md") < order.index("b.spec.md")
        assert order.index("d.spec.md") < order.index("c.spec.md")
        assert order.index("b.spec.md") < order.index("a.spec.md")
        assert order.index("c.spec.md") < order.index("a.spec.md")

    def test_cycle_raises(self, tmp_path: Path) -> None:
        """A → B → A → CycleError."""
        _write_inherits(tmp_path)
        _write_spec(tmp_path / "a.spec.md", dependencies=["b"])
        _write_spec(tmp_path / "b.spec.md", dependencies=["a"])
        graph = build_dep_graph(tmp_path)
        with pytest.raises(CycleError) as exc_info:
            topological_sort(graph)
        assert len(exc_info.value.cycle) >= 2

    def test_self_cycle(self, tmp_path: Path) -> None:
        """A → A → CycleError."""
        _write_inherits(tmp_path)
        _write_spec(tmp_path / "a.spec.md", dependencies=["a"])
        graph = build_dep_graph(tmp_path)
        with pytest.raises(CycleError):
            topological_sort(graph)

    def test_empty_graph(self) -> None:
        """Empty graph → empty list."""
        from speclord.types import DepGraph

        graph = DepGraph(adjacency={})
        assert topological_sort(graph) == []


class TestGetDepTree:
    def test_no_deps(self, tmp_path: Path) -> None:
        """Node with no deps → empty tree."""
        _write_inherits(tmp_path)
        _write_spec(tmp_path / "a.spec.md")
        graph = build_dep_graph(tmp_path)
        tree = get_dep_tree(graph, "a.spec.md")
        assert tree == {"a.spec.md": {}}

    def test_linear_tree(self, tmp_path: Path) -> None:
        """A → B → C → nested tree."""
        _write_inherits(tmp_path)
        _write_spec(tmp_path / "a.spec.md", dependencies=["b"])
        _write_spec(tmp_path / "b.spec.md", dependencies=["c"])
        _write_spec(tmp_path / "c.spec.md")
        graph = build_dep_graph(tmp_path)
        tree = get_dep_tree(graph, "a.spec.md")
        assert tree == {
            "a.spec.md": {
                "b.spec.md": {
                    "c.spec.md": {},
                },
            },
        }

    def test_circular_marked(self, tmp_path: Path) -> None:
        """Circular dep → marked with (circular)."""
        _write_inherits(tmp_path)
        _write_spec(tmp_path / "a.spec.md", dependencies=["b"])
        _write_spec(tmp_path / "b.spec.md", dependencies=["a"])
        graph = build_dep_graph(tmp_path)
        tree = get_dep_tree(graph, "a.spec.md")
        # a → b → a(circular)
        b_subtree = tree["a.spec.md"]["b.spec.md"]
        assert "(circular)" in b_subtree["a.spec.md"]


class TestDepsCLI:
    def test_full_graph_text(self, tmp_path: Path) -> None:
        """Full graph shows table and topological order."""
        _write_inherits(tmp_path)
        _write_spec(tmp_path / "a.spec.md", dependencies=["b"])
        _write_spec(tmp_path / "b.spec.md")
        runner = CliRunner()
        result = runner.invoke(main, ["deps", "--root", str(tmp_path)])
        assert result.exit_code == 0
        assert "a.spec.md" in result.output
        assert "b.spec.md" in result.output
        assert "Topological order" in result.output

    def test_full_graph_json(self, tmp_path: Path) -> None:
        """JSON mode returns valid JSON with nodes, edges, order."""
        _write_inherits(tmp_path)
        _write_spec(tmp_path / "a.spec.md", dependencies=["b"])
        _write_spec(tmp_path / "b.spec.md")
        runner = CliRunner()
        result = runner.invoke(
            main, ["deps", "--root", str(tmp_path), "--format", "json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "nodes" in data
        assert "edges" in data
        assert "order" in data
        assert "a.spec.md" in data["nodes"]

    def test_single_file_text(self, tmp_path: Path) -> None:
        """Single file shows dependency tree."""
        _write_inherits(tmp_path)
        _write_spec(tmp_path / "a.spec.md", dependencies=["b"])
        _write_spec(tmp_path / "b.spec.md")
        spec = tmp_path / "a.spec.md"
        runner = CliRunner()
        result = runner.invoke(
            main, ["deps", str(spec), "--root", str(tmp_path)]
        )
        assert result.exit_code == 0
        assert "a.spec.md" in result.output
        assert "b.spec.md" in result.output

    def test_single_file_json(self, tmp_path: Path) -> None:
        """Single file JSON returns dependency tree."""
        _write_inherits(tmp_path)
        _write_spec(tmp_path / "a.spec.md", dependencies=["b"])
        _write_spec(tmp_path / "b.spec.md")
        spec = tmp_path / "a.spec.md"
        runner = CliRunner()
        result = runner.invoke(
            main, ["deps", str(spec), "--root", str(tmp_path), "--format", "json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "a.spec.md" in data

    def test_empty_repo(self, tmp_path: Path) -> None:
        """Empty repo → no specs message."""
        runner = CliRunner()
        result = runner.invoke(main, ["deps", "--root", str(tmp_path)])
        assert result.exit_code == 0
        assert "No file specs" in result.output

    def test_cycle_text(self, tmp_path: Path) -> None:
        """Cycle in full graph → error message and exit 1."""
        _write_inherits(tmp_path)
        _write_spec(tmp_path / "a.spec.md", dependencies=["b"])
        _write_spec(tmp_path / "b.spec.md", dependencies=["a"])
        runner = CliRunner()
        result = runner.invoke(main, ["deps", "--root", str(tmp_path)])
        assert result.exit_code != 0
        assert "Cycle" in result.output or "cycle" in result.output

    def test_cycle_json(self, tmp_path: Path) -> None:
        """Cycle in JSON mode → cycle field in output, exit 1."""
        _write_inherits(tmp_path)
        _write_spec(tmp_path / "a.spec.md", dependencies=["b"])
        _write_spec(tmp_path / "b.spec.md", dependencies=["a"])
        runner = CliRunner()
        result = runner.invoke(
            main, ["deps", "--root", str(tmp_path), "--format", "json"]
        )
        assert result.exit_code != 0
        data = json.loads(result.output)
        assert data["order"] is None
        assert "cycle" in data

    def test_file_not_found(self, tmp_path: Path) -> None:
        """Nonexistent file → error."""
        runner = CliRunner()
        result = runner.invoke(
            main, ["deps", str(tmp_path / "nope.spec.md"), "--root", str(tmp_path)]
        )
        assert result.exit_code != 0
