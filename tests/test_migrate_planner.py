"""Tests for the migration planner."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from speclord.cli import main
from speclord.config import SpeclordConfig
from speclord.migrate.planner import plan_migration


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


def _setup_layered_repo(tmp_path: Path) -> None:
    """Create a repo with core → dependent → leaf directory structure.

    core/: types.py (specced, depended-on), utils.py (unspecced)
    svc/:  handler.py (specced, depends on core/types), routes.py (unspecced)
    leaf/: helpers.py (unspecced, no specs at all)
    """
    _write_inherits(tmp_path)

    # Core directory — has a spec that others depend on
    core = tmp_path / "core"
    core.mkdir()
    (core / "types.py").write_text("pass")
    _write_spec(core / "types.spec.md")
    (core / "utils.py").write_text("pass")  # unspecced

    # Dependent directory — has a spec that depends on core
    svc = tmp_path / "svc"
    svc.mkdir()
    (svc / "handler.py").write_text("pass")
    _write_spec(svc / "handler.spec.md", dependencies=["../core/types"])
    (svc / "routes.py").write_text("pass")  # unspecced

    # Leaf directory — no specs at all
    leaf = tmp_path / "leaf"
    leaf.mkdir()
    (leaf / "helpers.py").write_text("pass")  # unspecced


class TestPlanMigration:
    def test_three_phases(self, tmp_path: Path) -> None:
        """Layered repo produces 3 phases: Core, Dependent, Leaf."""
        _setup_layered_repo(tmp_path)
        plan = plan_migration(tmp_path, SpeclordConfig())
        phase_names = [p.name for p in plan.phases]
        assert phase_names == ["Core", "Dependent", "Leaf"]

    def test_core_phase_files(self, tmp_path: Path) -> None:
        """Core phase contains unspecced files from core directory."""
        _setup_layered_repo(tmp_path)
        plan = plan_migration(tmp_path, SpeclordConfig())
        core_phase = plan.phases[0]
        assert core_phase.name == "Core"
        assert "core/utils.py" in core_phase.files

    def test_dependent_phase_files(self, tmp_path: Path) -> None:
        """Dependent phase contains unspecced files from svc directory."""
        _setup_layered_repo(tmp_path)
        plan = plan_migration(tmp_path, SpeclordConfig())
        dep_phase = plan.phases[1]
        assert dep_phase.name == "Dependent"
        assert "svc/routes.py" in dep_phase.files

    def test_leaf_phase_files(self, tmp_path: Path) -> None:
        """Leaf phase contains unspecced files from leaf directory."""
        _setup_layered_repo(tmp_path)
        plan = plan_migration(tmp_path, SpeclordConfig())
        leaf_phase = plan.phases[2]
        assert leaf_phase.name == "Leaf"
        assert "leaf/helpers.py" in leaf_phase.files

    def test_ordering_respects_deps(self, tmp_path: Path) -> None:
        """Core comes before Dependent, which comes before Leaf."""
        _setup_layered_repo(tmp_path)
        plan = plan_migration(tmp_path, SpeclordConfig())
        names = [p.name for p in plan.phases]
        assert names.index("Core") < names.index("Dependent")
        assert names.index("Dependent") < names.index("Leaf")

    def test_fully_specced(self, tmp_path: Path) -> None:
        """No unspecced files → empty plan."""
        _write_inherits(tmp_path)
        (tmp_path / "foo.py").write_text("pass")
        _write_spec(tmp_path / "foo.spec.md")
        plan = plan_migration(tmp_path, SpeclordConfig())
        assert plan.phases == []

    def test_empty_repo(self, tmp_path: Path) -> None:
        """No code files → empty plan."""
        plan = plan_migration(tmp_path, SpeclordConfig())
        assert plan.phases == []

    def test_no_deps_all_leaf(self, tmp_path: Path) -> None:
        """Specs without dependencies → unspecced files all go to Leaf."""
        _write_inherits(tmp_path)
        (tmp_path / "a.py").write_text("pass")
        _write_spec(tmp_path / "a.spec.md")
        (tmp_path / "b.py").write_text("pass")  # unspecced
        plan = plan_migration(tmp_path, SpeclordConfig())
        assert len(plan.phases) == 1
        assert plan.phases[0].name == "Leaf"
        assert "b.py" in plan.phases[0].files

    def test_files_sorted_within_phase(self, tmp_path: Path) -> None:
        """Files within each phase are sorted alphabetically."""
        _write_inherits(tmp_path)
        d = tmp_path / "dir"
        d.mkdir()
        (d / "zebra.py").write_text("pass")
        (d / "alpha.py").write_text("pass")
        (d / "middle.py").write_text("pass")
        plan = plan_migration(tmp_path, SpeclordConfig())
        assert len(plan.phases) == 1
        assert plan.phases[0].files == sorted(plan.phases[0].files)


class TestMigratePlanCLI:
    def test_text_output(self, tmp_path: Path) -> None:
        """Text mode shows phased plan."""
        _setup_layered_repo(tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["migrate", "plan", "--root", str(tmp_path)])
        assert result.exit_code == 0
        assert "Migration Plan" in result.output
        assert "Phase 1: Core" in result.output
        assert "Phase 2: Dependent" in result.output
        assert "Phase 3: Leaf" in result.output

    def test_json_output(self, tmp_path: Path) -> None:
        """JSON mode returns valid JSON with phase data."""
        _setup_layered_repo(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            main, ["migrate", "plan", "--root", str(tmp_path), "--format", "json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 3
        assert data[0]["phase"] == "Core"
        assert "files" in data[0]

    def test_fully_specced_message(self, tmp_path: Path) -> None:
        """All files specced → nothing to migrate."""
        _write_inherits(tmp_path)
        (tmp_path / "foo.py").write_text("pass")
        _write_spec(tmp_path / "foo.spec.md")
        runner = CliRunner()
        result = runner.invoke(main, ["migrate", "plan", "--root", str(tmp_path)])
        assert result.exit_code == 0
        assert "nothing to migrate" in result.output

    def test_empty_repo(self, tmp_path: Path) -> None:
        """Empty repo → nothing to migrate."""
        runner = CliRunner()
        result = runner.invoke(main, ["migrate", "plan", "--root", str(tmp_path)])
        assert result.exit_code == 0
        assert "nothing to migrate" in result.output
