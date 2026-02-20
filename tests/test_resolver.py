"""Tests for spec chain resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from speclord.errors import ResolutionError
from speclord.resolver import resolve_chain


class TestResolveChain:
    def test_full_chain(self, valid_repo: Path) -> None:
        spec = valid_repo / "packages/auth/src/handler.spec.md"
        chain = resolve_chain(spec, valid_repo)

        assert chain.file_spec.type == "api-endpoint"
        assert chain.service_spec is not None
        assert chain.service_spec.service == "auth"
        assert chain.org_spec is not None
        assert chain.org_spec.organization == "test-org"

    def test_file_only_no_parent(self, tmp_path: Path) -> None:
        """File spec with inherits pointing to nonexistent parent."""
        spec = tmp_path / "test.spec.md"
        spec.write_text(
            '---\nspecVersion: "0.1.0"\ninherits: ".spec.yaml"\n'
            'type: "utility"\nowner: "@team"\nstatus: "draft"\n---\nBody.\n'
        )
        chain = resolve_chain(spec, tmp_path)
        assert chain.file_spec.type == "utility"
        assert chain.service_spec is None
        assert chain.org_spec is None

    def test_file_with_org_only(self, tmp_path: Path) -> None:
        """File spec inheriting directly from org spec (no service)."""
        org = tmp_path / "org.spec.yaml"
        org.write_text('specVersion: "0.1.0"\norganization: "acme"\n')

        spec = tmp_path / "test.spec.md"
        spec.write_text(
            '---\nspecVersion: "0.1.0"\ninherits: "org.spec.yaml"\n'
            'type: "utility"\nowner: "@team"\nstatus: "draft"\n---\nBody.\n'
        )
        chain = resolve_chain(spec, tmp_path)
        assert chain.service_spec is None
        assert chain.org_spec is not None
        assert chain.org_spec.organization == "acme"

    def test_file_with_service_and_org(self, tmp_path: Path) -> None:
        """Full three-level chain."""
        org = tmp_path / "org.spec.yaml"
        org.write_text('specVersion: "0.1.0"\norganization: "acme"\n')

        pkg = tmp_path / "pkg"
        pkg.mkdir()
        svc = pkg / ".spec.yaml"
        svc.write_text(
            'specVersion: "0.1.0"\ninherits: "../org.spec.yaml"\n'
            'service: "pkg"\nowner: "@team"\n'
        )

        src = pkg / "src"
        src.mkdir()
        spec = src / "module.spec.md"
        spec.write_text(
            '---\nspecVersion: "0.1.0"\ninherits: "../.spec.yaml"\n'
            'type: "utility"\nowner: "@team"\nstatus: "draft"\n---\nBody.\n'
        )

        chain = resolve_chain(spec, tmp_path)
        assert chain.file_spec.type == "utility"
        assert chain.service_spec is not None
        assert chain.service_spec.service == "pkg"
        assert chain.org_spec is not None
        assert chain.org_spec.organization == "acme"

    def test_nonexistent_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ResolutionError):
            resolve_chain(tmp_path / "nonexistent.spec.md", tmp_path)

    def test_malformed_spec_raises(self, tmp_path: Path) -> None:
        spec = tmp_path / "bad.spec.md"
        spec.write_text("not a spec\n")
        with pytest.raises(ResolutionError, match="Cannot parse"):
            resolve_chain(spec, tmp_path)
