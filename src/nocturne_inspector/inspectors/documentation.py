from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from time import perf_counter

from nocturne_inspector.inspectors.base import Inspector
from nocturne_inspector.models import (
    Confidence,
    Evidence,
    Finding,
    FindingCategory,
    FindingKind,
    InspectorResult,
    Recommendation,
    Severity,
    SourceLocation,
)


class DocumentationInspector(Inspector):
    """Inspect deterministic, filesystem-backed documentation conditions."""

    name = "documentation"
    category = FindingCategory.DOCUMENTATION

    _readme_names = frozenset({"readme", "readme.md", "readme.rst", "readme.txt"})
    _documentation_suffixes = frozenset({".md", ".mdx", ".rst", ".txt"})

    def __init__(self, *, clock: Callable[[], float] = perf_counter) -> None:
        """Create an inspector with an optionally controlled monotonic clock."""
        self._clock = clock

    def inspect(self, project_root: Path) -> InspectorResult:
        """Inspect root README presence and zero-byte documentation files."""
        root = project_root.expanduser().resolve(strict=True)

        if not root.is_dir():
            raise NotADirectoryError(f"Project root is not a directory: {root}")

        started_at = self._clock()
        documentation_files = self._documentation_files(root)
        findings: list[Finding] = []
        warnings: list[str] = []

        if not self._has_root_readme(root):
            findings.append(self._missing_readme_finding())

        for documentation_file in documentation_files:
            relative_path = documentation_file.relative_to(root).as_posix()

            try:
                size = documentation_file.stat().st_size
            except OSError:
                warnings.append(
                    f"Could not examine documentation file: {relative_path}"
                )
                continue

            if size == 0:
                findings.append(self._empty_documentation_finding(relative_path))

        duration_ms = (self._clock() - started_at) * 1_000
        return InspectorResult(
            inspector=self.name,
            category=self.category,
            findings=tuple(findings),
            duration_ms=duration_ms,
            files_examined=len(documentation_files),
            warnings=tuple(warnings),
        )

    def _has_root_readme(self, root: Path) -> bool:
        for entry in sorted(
            root.iterdir(),
            key=lambda path: (path.name.casefold(), path.name),
        ):
            if entry.name.casefold() not in self._readme_names:
                continue

            if not entry.is_symlink() and entry.is_file():
                return True

        return False

    def _documentation_files(self, root: Path) -> tuple[Path, ...]:
        files: set[Path] = set()

        for entry in root.iterdir():
            if entry.name.casefold() not in self._readme_names:
                continue

            if not entry.is_symlink() and entry.is_file():
                files.add(entry)

        docs_root = root / "docs"

        if not docs_root.is_symlink() and docs_root.is_dir():
            for directory, directory_names, file_names in docs_root.walk():
                directory_names[:] = sorted(
                    name
                    for name in directory_names
                    if not (directory / name).is_symlink()
                )

                for file_name in sorted(file_names):
                    candidate = directory / file_name

                    if candidate.is_symlink() or not candidate.is_file():
                        continue

                    if candidate.suffix.casefold() in self._documentation_suffixes:
                        files.add(candidate)

        return tuple(sorted(files, key=lambda path: path.relative_to(root).as_posix()))

    def _missing_readme_finding(self) -> Finding:
        checked_names = ", ".join(sorted(self._readme_names))
        return Finding(
            rule_id="documentation.missing-root-readme",
            title="Root README not found",
            description="No recognized README file exists at the project root.",
            category=self.category,
            kind=FindingKind.IMPROVEMENT_OPPORTUNITY,
            severity=Severity.LOW,
            confidence=Confidence.from_score(
                1.0,
                "The project root was checked against a fixed README name set.",
            ),
            evidence=(
                Evidence(
                    description=f"No root file matched: {checked_names}.",
                    source=SourceLocation(path="."),
                ),
            ),
            impact="The project has no conventional root documentation entry point.",
            recommendation=Recommendation(
                summary="Add a root README with essential project information.",
                rationale=(
                    "A conventional entry point makes project documentation "
                    "directly discoverable."
                ),
            ),
        )

    def _empty_documentation_finding(self, relative_path: str) -> Finding:
        return Finding(
            rule_id="documentation.empty-file",
            title="Empty documentation file",
            description="A documentation file contains zero bytes.",
            category=self.category,
            kind=FindingKind.CONFIRMED_ISSUE,
            severity=Severity.LOW,
            confidence=Confidence.from_score(
                1.0,
                "The finding is based on the file size reported by the filesystem.",
            ),
            evidence=(
                Evidence(
                    description="The file size is exactly zero bytes.",
                    source=SourceLocation(path=relative_path),
                ),
            ),
            impact="The file does not currently provide documentation content.",
            recommendation=Recommendation(
                summary="Document the intended topic or remove the empty placeholder.",
                rationale=(
                    "Every tracked documentation file should communicate useful "
                    "information or have an explicit lifecycle outside the report."
                ),
            ),
        )
