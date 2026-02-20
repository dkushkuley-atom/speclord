"""Tests for registry compilation."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from speclord.cli import main
from speclord.registry import compile_registry


class TestCompileRegistry:
    def test_compiles_valid_repo(self, valid_repo: Path) -> None:
        registry = compile_registry(valid_repo)
        assert "version" in registry
        assert "specs" in registry
        assert len(registry["specs"]) >= 1
        assert registry["errors"] == []

    def test_spec_entry_has_required_fields(self, valid_repo: Path) -> None:
        registry = compile_registry(valid_repo)
        for path, entry in registry["specs"].items():
            assert "hash" in entry
            assert "type" in entry
            assert "status" in entry
            assert "dependencies" in entry
            assert len(entry["hash"]) == 64  # sha256

    def test_writes_lock_file(self, valid_repo: Path) -> None:
        compile_registry(valid_repo)
        lock = valid_repo / "registry.lock.json"
        assert lock.exists()
        data = json.loads(lock.read_text())
        assert "version" in data
        assert "specs" in data

    def test_empty_dir(self, tmp_path: Path) -> None:
        registry = compile_registry(tmp_path)
        assert registry["specs"] == {}
        assert registry["errors"] == []

    def test_handles_parse_errors(self, tmp_path: Path) -> None:
        bad = tmp_path / "broken.spec.md"
        bad.write_text("---\n---\nno fields\n")
        registry = compile_registry(tmp_path)
        assert len(registry["errors"]) == 1
        assert registry["specs"] == {}

    def test_hash_changes_on_content_change(self, tmp_path: Path) -> None:
        spec = tmp_path / "test.spec.md"
        spec.write_text(
            '---\nspecVersion: "0.1.0"\ninherits: ".spec.yaml"\n'
            'type: "utility"\nowner: "@team"\nstatus: "draft"\n---\nVersion 1.\n'
        )
        reg1 = compile_registry(tmp_path)
        hash1 = list(reg1["specs"].values())[0]["hash"]

        spec.write_text(
            '---\nspecVersion: "0.1.0"\ninherits: ".spec.yaml"\n'
            'type: "utility"\nowner: "@team"\nstatus: "draft"\n---\nVersion 2.\n'
        )
        reg2 = compile_registry(tmp_path)
        hash2 = list(reg2["specs"].values())[0]["hash"]

        assert hash1 != hash2

    def test_generates_field_included(self, valid_repo: Path) -> None:
        registry = compile_registry(valid_repo)
        handler = registry["specs"].get("packages/auth/src/handler.spec.md")
        assert handler is not None
        assert handler["generates"] == "packages/auth/src/handler.py"

    def test_only_indexes_file_specs(self, valid_repo: Path) -> None:
        """Service specs and org specs are not in the registry entries."""
        registry = compile_registry(valid_repo)
        for path in registry["specs"]:
            assert path.endswith(".spec.md")


class TestCompileCLI:
    def test_compile_command(self, valid_repo: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["compile", "--root", str(valid_repo)])
        assert result.exit_code == 0
        assert "compiled" in result.output.lower()
        assert (valid_repo / "registry.lock.json").exists()

    def test_compile_empty_dir(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["compile", "--root", str(tmp_path)])
        assert result.exit_code == 0
        assert "0 spec" in result.output
