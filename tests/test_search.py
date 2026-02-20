"""Tests for the spec search module."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from speclord.cli import main
from speclord.search import search_specs


def _write_spec(
    path: Path,
    *,
    spec_type: str = "utility",
    status: str = "active",
    owner: str = "@dev",
    generates: str | None = None,
    dependencies: list[str] | None = None,
    body: str = "Body text.",
) -> None:
    extra = ""
    if generates is not None:
        extra += f"generates: '{generates}'\n"
    if dependencies:
        extra += "dependencies:\n"
        for dep in dependencies:
            extra += f"  - '{dep}'\n"
    content = (
        f"---\nspecVersion: '0.1.0'\ninherits: '.spec.yaml'\n"
        f"type: {spec_type}\nstatus: {status}\nowner: '{owner}'\n"
        f"{extra}---\n{body}\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _setup_repo(tmp_path: Path) -> None:
    (tmp_path / ".spec.yaml").write_text(
        "specVersion: '0.1.0'\ninherits: 'org.spec.yaml'\n"
        "service: test\nowner: '@dev'\n"
    )
    _write_spec(
        tmp_path / "auth.spec.md",
        spec_type="api-endpoint",
        status="active",
        owner="@auth-team",
        body="Handles user authentication and JWT tokens.",
    )
    _write_spec(
        tmp_path / "models.spec.md",
        spec_type="data-model",
        status="draft",
        owner="@data-team",
        body="User and account data models.",
    )
    _write_spec(
        tmp_path / "utils.spec.md",
        spec_type="utility",
        status="active",
        owner="@dev",
        body="Shared helper functions.",
    )


class TestSearchSpecs:
    def test_keyword_match_body(self, tmp_path: Path) -> None:
        """Query matches body text."""
        _setup_repo(tmp_path)
        results = search_specs(tmp_path, "JWT")
        assert len(results) == 1
        assert "auth" in results[0].file_path

    def test_keyword_case_insensitive(self, tmp_path: Path) -> None:
        """Search is case-insensitive."""
        _setup_repo(tmp_path)
        results = search_specs(tmp_path, "jwt")
        assert len(results) == 1

    def test_keyword_match_type(self, tmp_path: Path) -> None:
        """Query matches type field."""
        _setup_repo(tmp_path)
        results = search_specs(tmp_path, "data-model")
        assert len(results) == 1
        assert "models" in results[0].file_path

    def test_keyword_match_owner(self, tmp_path: Path) -> None:
        """Query matches owner field."""
        _setup_repo(tmp_path)
        results = search_specs(tmp_path, "auth-team")
        assert len(results) == 1

    def test_keyword_match_file_path(self, tmp_path: Path) -> None:
        """Query matches file path."""
        _setup_repo(tmp_path)
        results = search_specs(tmp_path, "utils")
        assert len(results) == 1

    def test_no_results(self, tmp_path: Path) -> None:
        """Query with no matches → empty list."""
        _setup_repo(tmp_path)
        results = search_specs(tmp_path, "nonexistent-query-xyz")
        assert results == []

    def test_empty_query_returns_all(self, tmp_path: Path) -> None:
        """Empty query with no filters → returns all specs."""
        _setup_repo(tmp_path)
        results = search_specs(tmp_path, "")
        assert len(results) == 3

    def test_filter_by_type(self, tmp_path: Path) -> None:
        """--type filter narrows results."""
        _setup_repo(tmp_path)
        results = search_specs(tmp_path, "", type_filter="utility")
        assert len(results) == 1
        assert results[0].type == "utility"

    def test_filter_by_owner(self, tmp_path: Path) -> None:
        """--owner filter narrows results."""
        _setup_repo(tmp_path)
        results = search_specs(tmp_path, "", owner_filter="@data-team")
        assert len(results) == 1
        assert results[0].owner == "@data-team"

    def test_filter_by_status(self, tmp_path: Path) -> None:
        """--status filter narrows results."""
        _setup_repo(tmp_path)
        results = search_specs(tmp_path, "", status_filter="draft")
        assert len(results) == 1
        assert results[0].status == "draft"

    def test_combined_query_and_filter(self, tmp_path: Path) -> None:
        """Query + filter both apply."""
        _setup_repo(tmp_path)
        results = search_specs(tmp_path, "helper", type_filter="utility")
        assert len(results) == 1
        results = search_specs(tmp_path, "helper", type_filter="api-endpoint")
        assert len(results) == 0

    def test_multiple_filters(self, tmp_path: Path) -> None:
        """Multiple filters all apply (AND logic)."""
        _setup_repo(tmp_path)
        results = search_specs(
            tmp_path, "", type_filter="api-endpoint", status_filter="active"
        )
        assert len(results) == 1
        assert "auth" in results[0].file_path

    def test_empty_repo(self, tmp_path: Path) -> None:
        """No specs → empty list."""
        results = search_specs(tmp_path, "anything")
        assert results == []

    def test_parse_error_skipped(self, tmp_path: Path) -> None:
        """Malformed specs are skipped, not crashed."""
        (tmp_path / "bad.spec.md").write_text("not valid")
        _setup_repo(tmp_path)
        results = search_specs(tmp_path, "helper")
        assert len(results) == 1


class TestSearchCLI:
    def test_text_output(self, tmp_path: Path) -> None:
        """Text mode shows matching specs in a table."""
        _setup_repo(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            main, ["search", "JWT", "--root", str(tmp_path)]
        )
        assert result.exit_code == 0
        assert "auth" in result.output
        assert "1" in result.output  # result count

    def test_json_output(self, tmp_path: Path) -> None:
        """JSON mode returns valid JSON."""
        _setup_repo(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            main, ["search", "JWT", "--root", str(tmp_path), "--format", "json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["type"] == "api-endpoint"

    def test_filter_flags(self, tmp_path: Path) -> None:
        """CLI filter flags work."""
        _setup_repo(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            main, ["search", "--type", "utility", "--root", str(tmp_path)]
        )
        assert result.exit_code == 0
        assert "utility" in result.output
        assert "Search Results (1)" in result.output

    def test_no_results_message(self, tmp_path: Path) -> None:
        """No matches → dim message."""
        _setup_repo(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            main, ["search", "zzzznotfound", "--root", str(tmp_path)]
        )
        assert result.exit_code == 0
        assert "No matching" in result.output

    def test_no_query_no_filter_error(self, tmp_path: Path) -> None:
        """No query and no filters → error."""
        runner = CliRunner()
        result = runner.invoke(main, ["search", "--root", str(tmp_path)])
        assert result.exit_code != 0

    def test_filter_only_no_query(self, tmp_path: Path) -> None:
        """Filter without query → lists all matching that filter."""
        _setup_repo(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["search", "--status", "active", "--root", str(tmp_path), "--format", "json"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 2  # auth and utils are active
