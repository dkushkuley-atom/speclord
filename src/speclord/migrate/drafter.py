"""Batch spec drafter — AI-powered drafting for unspecced files."""

from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path

from speclord.ai.adapter import LLMAdapter
from speclord.ai.draft import draft_spec
from speclord.config import SpeclordConfig, load_config
from speclord.migrate.scanner import scan_codebase


@dataclass
class DraftResult:
    """Result of drafting a single spec."""

    source_path: str
    spec_path: str
    success: bool
    error: str | None = None


def batch_draft(
    root: Path,
    adapter: LLMAdapter,
    config: SpeclordConfig | None = None,
    *,
    directory: str | None = None,
) -> Generator[DraftResult, None, None]:
    """Draft specs for all unspecced files, yielding results as they complete.

    Args:
        root: Project root directory.
        adapter: The LLM adapter to use for generation.
        config: Optional config (loaded from root if not provided).
        directory: Optional directory filter (relative to root).

    Yields:
        DraftResult for each file processed.
    """
    root = root.resolve()
    if config is None:
        config = load_config(root)

    scan = scan_codebase(root, config)

    for entry in scan.by_directory:
        # Apply directory filter if specified
        if directory is not None:
            if not entry.directory.startswith(directory) and entry.directory != directory:
                continue

        for unspecced_path in entry.unspecced:
            source = Path(unspecced_path)
            # Strip extension to get the spec target path
            spec_target = source.with_suffix("")
            spec_output = root / f"{spec_target.as_posix()}.spec.md"

            if spec_output.exists():
                continue

            description = f"Source file: {source.name}"

            try:
                content = draft_spec(
                    description,
                    spec_target,
                    root,
                    adapter,
                    from_code=True,
                )
                spec_output.parent.mkdir(parents=True, exist_ok=True)
                spec_output.write_text(content, encoding="utf-8")

                try:
                    rel_spec = spec_output.relative_to(root).as_posix()
                except ValueError:
                    rel_spec = str(spec_output)

                yield DraftResult(
                    source_path=unspecced_path,
                    spec_path=rel_spec,
                    success=True,
                )
            except Exception as e:
                yield DraftResult(
                    source_path=unspecced_path,
                    spec_path=f"{spec_target.as_posix()}.spec.md",
                    success=False,
                    error=str(e),
                )
