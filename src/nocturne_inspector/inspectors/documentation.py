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
    ProjectContext,
    Recommendation,
    Severity,
    SourceLocation,
)


class DocumentationInspector(Inspector):
    """Inspect deterministic, filesystem-backed documentation conditions."""

    name = "documentation"
    category = FindingCategory.DOCUMENTATION

    _essential_files = (
        "AGENTS.md",
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "LICENSE",
        "README.md",
        "SECURITY.md",
    )
    _docs_directory = "docs"
    _documentation_suffixes = frozenset({".md", ".mdx", ".rst", ".txt"})

    def __init__(self, *, clock: Callable[[], float] = perf_counter) -> None:
        """Create an inspector with an optionally controlled monotonic clock."""
        self._clock = clock

    def inspect(self, context: ProjectContext) -> InspectorResult:
        """Inspect essential paths and zero-byte documentation files."""
        root = context.root

        started_at = self._clock()
        findings, essential_files, docs_root = self._inspect_essential_paths(root)
        documentation_files = self._documentation_files(
            context,
            essential_files=essential_files,
            docs_root=docs_root,
        )
        warnings: list[str] = []

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

    def _inspect_essential_paths(
        self,
        root: Path,
    ) -> tuple[list[Finding], tuple[Path, ...], Path | None]:
        findings: list[Finding] = []
        files: list[Path] = []

        for name in self._essential_files:
            candidate = root / name

            if candidate.is_symlink():
                findings.append(
                    self._invalid_essential_path_finding(
                        name,
                        expected="regular file",
                        observed="symbolic link",
                    )
                )
            elif not candidate.exists():
                findings.append(self._missing_essential_path_finding(name))
            elif not candidate.is_file():
                findings.append(
                    self._invalid_essential_path_finding(
                        name,
                        expected="regular file",
                        observed=self._path_kind(candidate),
                    )
                )
            else:
                files.append(candidate)

        docs_root = root / self._docs_directory

        if docs_root.is_symlink():
            findings.append(
                self._invalid_essential_path_finding(
                    self._docs_directory,
                    expected="directory",
                    observed="symbolic link",
                )
            )
            valid_docs_root: Path | None = None
        elif not docs_root.exists():
            findings.append(self._missing_essential_path_finding(self._docs_directory))
            valid_docs_root = None
        elif not docs_root.is_dir():
            findings.append(
                self._invalid_essential_path_finding(
                    self._docs_directory,
                    expected="directory",
                    observed=self._path_kind(docs_root),
                )
            )
            valid_docs_root = None
        else:
            valid_docs_root = docs_root

        return findings, tuple(files), valid_docs_root

    def _documentation_files(
        self,
        context: ProjectContext,
        *,
        essential_files: tuple[Path, ...],
        docs_root: Path | None,
    ) -> tuple[Path, ...]:
        files = set(essential_files)

        if docs_root is not None:
            files.update(
                context.root / relative_path
                for relative_path in context.files
                if relative_path.parts[0] == self._docs_directory
                and relative_path.suffix.casefold() in self._documentation_suffixes
            )

        return tuple(
            sorted(
                files,
                key=lambda path: path.relative_to(context.root).as_posix(),
            )
        )

    @staticmethod
    def _path_kind(path: Path) -> str:
        if path.is_dir():
            return "directory"

        if path.is_file():
            return "regular file"

        return "unsupported filesystem entry"

    def _missing_essential_path_finding(self, relative_path: str) -> Finding:
        return Finding(
            rule_id="documentation.missing-essential-path",
            title="Essential documentation path not found",
            description=(
                f"The expected documentation path {relative_path!r} is absent."
            ),
            category=self.category,
            kind=FindingKind.CONFIRMED_ISSUE,
            severity=Severity.LOW,
            confidence=Confidence.from_score(
                1.0,
                "The expected root path was checked directly without heuristics.",
            ),
            evidence=(
                Evidence(
                    description="The expected path does not exist at the project root.",
                    source=SourceLocation(path=relative_path),
                ),
            ),
            impact="An expected project documentation entry is unavailable.",
            recommendation=Recommendation(
                summary=f"Add the expected documentation path {relative_path!r}.",
                rationale=(
                    "The project documentation contract lists this path as an "
                    "essential entry."
                ),
            ),
        )

    def _invalid_essential_path_finding(
        self,
        relative_path: str,
        *,
        expected: str,
        observed: str,
    ) -> Finding:
        return Finding(
            rule_id="documentation.invalid-essential-path",
            title="Essential documentation path has an invalid type",
            description=(
                f"The path {relative_path!r} is a {observed}; expected {expected}."
            ),
            category=self.category,
            kind=FindingKind.CONFIRMED_ISSUE,
            severity=Severity.LOW,
            confidence=Confidence.from_score(
                1.0,
                "The path type was read directly from the filesystem.",
            ),
            evidence=(
                Evidence(
                    description=f"Observed {observed}; expected {expected}.",
                    source=SourceLocation(path=relative_path),
                ),
            ),
            impact="The expected documentation entry cannot be inspected as required.",
            recommendation=Recommendation(
                summary=f"Provide {relative_path!r} as a {expected}.",
                rationale=(
                    "The documented project contract requires the expected path type."
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
