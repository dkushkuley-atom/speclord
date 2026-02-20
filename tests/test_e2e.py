"""End-to-end tests — full non-AI workflow in a temp directory.

Exercises the entire pipeline: init → new → lint → compile → coverage →
context → resolve → emit → check → deps → search → status →
migrate scan/plan/progress.
"""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from speclord.cli import main


def _invoke(runner: CliRunner, args: list[str]) -> str:
    """Invoke a CLI command and assert it exits cleanly."""
    result = runner.invoke(main, args, catch_exceptions=False)
    assert result.exit_code == 0, (
        f"Command {args} failed (exit {result.exit_code}):\n{result.output}"
    )
    return result.output


class TestEndToEnd:
    """Full workflow exercising every non-AI CLI command."""

    def test_full_workflow(self, tmp_path: Path) -> None:
        """Walk through the entire speclord pipeline in a fresh project."""
        runner = CliRunner()
        root = str(tmp_path)

        # ── 1. init ──────────────────────────────────────────────
        output = _invoke(runner, ["init", "--root", root, "--org", "acme"])
        assert "Initialized" in output
        assert (tmp_path / ".spec" / "templates").is_dir()
        assert (tmp_path / "org.spec.yaml").exists()

        # Verify org spec content
        org_content = (tmp_path / "org.spec.yaml").read_text(encoding="utf-8")
        assert "acme" in org_content
        assert "specVersion" in org_content

        # ── 2. new (scaffold specs) ─────────────────────────────
        # Create some code files first
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "__init__.py").write_text("", encoding="utf-8")
        (tmp_path / "src" / "auth.py").write_text(
            "def login(user, pw): pass\n", encoding="utf-8"
        )
        (tmp_path / "src" / "utils.py").write_text(
            "def helper(): return 42\n", encoding="utf-8"
        )

        # Create a service spec for src/
        output = _invoke(runner, ["new", "service", "src", "--root", root])
        assert "Created" in output
        assert (tmp_path / "src" / ".spec.yaml").exists()

        # Create file specs
        output = _invoke(runner, ["new", "utility", "src/auth", "--root", root])
        assert "Created" in output
        assert (tmp_path / "src" / "auth.spec.md").exists()

        output = _invoke(runner, ["new", "utility", "src/utils", "--root", root])
        assert "Created" in output
        assert (tmp_path / "src" / "utils.spec.md").exists()

        # ── 3. lint ──────────────────────────────────────────────
        output = _invoke(runner, ["lint", "--root", root])
        # Scaffolded specs should be valid
        assert "valid" in output.lower() or "error" not in output.lower()

        # JSON mode
        output = _invoke(runner, ["lint", "--root", root, "--format", "json"])
        data = json.loads(output)
        assert isinstance(data, list)

        # ── 4. compile ───────────────────────────────────────────
        output = _invoke(runner, ["compile", "--root", root])
        assert "Compiled" in output
        assert (tmp_path / "registry.lock.json").exists()

        # Verify registry content
        registry = json.loads(
            (tmp_path / "registry.lock.json").read_text(encoding="utf-8")
        )
        assert "specs" in registry
        assert len(registry["specs"]) == 2  # auth.spec.md + utils.spec.md

        # ── 5. coverage ─────────────────────────────────────────
        output = _invoke(runner, ["coverage", "--root", root])
        assert "100" in output or "coverage" in output.lower()

        # JSON mode
        output = _invoke(runner, ["coverage", "--root", root, "--format", "json"])
        data = json.loads(output)
        assert data["total_files"] == 2
        assert data["specced_files"] == 2
        assert data["coverage_pct"] == 100.0

        # ── 6. context ───────────────────────────────────────────
        spec_file = str(tmp_path / "src" / "auth.spec.md")
        output = _invoke(runner, ["context", spec_file, "--root", root])
        assert "auth" in output.lower()
        # Context should include chain info
        assert "spec" in output.lower()

        # Batch mode
        output = _invoke(
            runner, ["context", "--batch", "src/*.spec.md", "--root", root]
        )
        assert len(output) > 0

        # ── 7. resolve ───────────────────────────────────────────
        output = _invoke(runner, ["resolve", spec_file, "--root", root])
        assert "auth" in output.lower()

        # JSON mode
        output = _invoke(
            runner, ["resolve", spec_file, "--root", root, "--format", "json"]
        )
        data = json.loads(output)
        assert "file" in data
        assert data["file"]["type"] == "utility"

        # ── 8. emit ──────────────────────────────────────────────
        output = _invoke(runner, ["emit", "claude", "--root", root])
        assert "Wrote" in output
        assert (tmp_path / "CLAUDE.md").exists()

        claude_content = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
        assert len(claude_content) > 0

        # Dry run
        output = _invoke(runner, ["emit", "claude", "--root", root, "--dry-run"])
        assert len(output) > 0

        # ── 9. check ─────────────────────────────────────────────
        # Scaffolded specs have generates: "src/auth" but actual file is
        # src/auth.py, so check correctly flags missing-generates-target.
        # We verify check runs and produces structured output.
        result = runner.invoke(
            main, ["check", "--root", root, "--format", "json"],
            catch_exceptions=False,
        )
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert any(f["rule"] == "missing-generates-target" for f in data)

        # ── 10. deps ─────────────────────────────────────────────
        output = _invoke(runner, ["deps", "--root", root])
        assert len(output) > 0

        # JSON mode
        output = _invoke(runner, ["deps", "--root", root, "--format", "json"])
        data = json.loads(output)
        assert "nodes" in data

        # Single file deps
        output = _invoke(runner, ["deps", spec_file, "--root", root])
        assert "auth" in output.lower()

        # ── 11. search ───────────────────────────────────────────
        # Use JSON mode — Rich tables truncate long tmpdir paths
        output = _invoke(
            runner, ["search", "auth", "--root", root, "--format", "json"]
        )
        data = json.loads(output)
        assert isinstance(data, list)
        assert len(data) >= 1
        assert any("auth" in entry["file"] for entry in data)

        # Search by type
        output = _invoke(
            runner,
            ["search", "--type", "utility", "--root", root, "--format", "json"],
        )
        data = json.loads(output)
        assert len(data) == 2  # auth + utils

        # ── 12. status ───────────────────────────────────────────
        output = _invoke(runner, ["status", "--root", root])
        assert "Speclord Status" in output
        assert "Coverage" in output
        assert "Lint" in output
        assert "Check" in output

        # ── 13. migrate scan ─────────────────────────────────────
        output = _invoke(runner, ["migrate", "scan", "--root", root])
        assert "100" in output or "specced" in output.lower()

        # JSON mode
        output = _invoke(
            runner, ["migrate", "scan", "--root", root, "--format", "json"]
        )
        data = json.loads(output)
        assert "total_files" in data

        # ── 14. migrate plan ─────────────────────────────────────
        output = _invoke(runner, ["migrate", "plan", "--root", root])
        # All files specced, so nothing to migrate
        assert "nothing to migrate" in output.lower() or "phase" in output.lower()

        # ── 15. migrate progress ─────────────────────────────────
        output = _invoke(runner, ["migrate", "progress", "--root", root])
        assert "Progress" in output or "progress" in output.lower()

    def test_workflow_with_unspecced_files(self, tmp_path: Path) -> None:
        """Test the pipeline when some files lack specs."""
        runner = CliRunner()
        root = str(tmp_path)

        # Set up project
        _invoke(runner, ["init", "--root", root])
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "__init__.py").write_text("", encoding="utf-8")
        (tmp_path / "src" / "covered.py").write_text("x = 1", encoding="utf-8")
        (tmp_path / "src" / "uncovered.py").write_text("y = 2", encoding="utf-8")

        # Only spec one file
        _invoke(runner, ["new", "utility", "src/covered", "--root", root])

        # Coverage should be 50%
        output = _invoke(runner, ["coverage", "--root", root, "--format", "json"])
        data = json.loads(output)
        assert data["total_files"] == 2
        assert data["specced_files"] == 1
        assert data["coverage_pct"] == 50.0
        assert "src/uncovered.py" in data["unspecced"]

        # Coverage --min should fail at 80%
        result = runner.invoke(
            main, ["coverage", "--root", root, "--min", "80"],
            catch_exceptions=False,
        )
        assert result.exit_code == 1

        # Migrate scan shows the gap
        output = _invoke(
            runner, ["migrate", "scan", "--root", root, "--format", "json"]
        )
        data = json.loads(output)
        assert data["unspecced_files"] == 1

        # Migrate plan suggests a phase
        output = _invoke(
            runner, ["migrate", "plan", "--root", root, "--format", "json"]
        )
        data = json.loads(output)
        assert len(data) >= 1  # At least one phase

    def test_init_idempotent(self, tmp_path: Path) -> None:
        """Running init twice doesn't break anything."""
        runner = CliRunner()
        root = str(tmp_path)

        _invoke(runner, ["init", "--root", root])
        output = _invoke(runner, ["init", "--root", root])
        assert "already exists" in output

    def test_new_idempotent(self, tmp_path: Path) -> None:
        """Scaffolding a spec that already exists warns instead of overwriting."""
        runner = CliRunner()
        root = str(tmp_path)

        _invoke(runner, ["init", "--root", root])
        _invoke(runner, ["new", "utility", "src/foo", "--root", root])

        output = _invoke(runner, ["new", "utility", "src/foo", "--root", root])
        assert "already exists" in output

    def test_version(self) -> None:
        """--version prints version info."""
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "speclord" in result.output.lower()

    def test_help(self) -> None:
        """--help shows all commands."""
        runner = CliRunner()
        output = _invoke(runner, ["--help"])
        for cmd in [
            "lint", "compile", "init", "new", "context", "resolve",
            "emit", "coverage", "check", "drift", "review", "draft",
            "deps", "search", "status", "migrate",
        ]:
            assert cmd in output, f"Missing command: {cmd}"
