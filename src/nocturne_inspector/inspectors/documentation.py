from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path
from time import perf_counter
from typing import ClassVar

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

    _root_documentation_files = (
        "AGENTS.md",
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "LICENSE",
        "README.md",
        "SECURITY.md",
    )
    _docs_directory = "docs"
    _documentation_suffixes = frozenset({".md", ".mdx", ".rst", ".txt"})
    _default_required_paths = ("README.md",)
    _path_rule_names: ClassVar[dict[str, str]] = {
        "AGENTS.md": "agents",
        "CHANGELOG.md": "changelog",
        "CONTRIBUTING.md": "contributing",
        "LICENSE": "license",
        "README.md": "readme",
        "SECURITY.md": "security",
        "docs": "docs-directory",
    }

    def __init__(
        self,
        *,
        additional_required_paths: Iterable[str] = (),
        clock: Callable[[], float] = perf_counter,
    ) -> None:
        """Create an inspector with an explicit documentation requirement policy."""
        if isinstance(additional_required_paths, str):
            raise TypeError("additional_required_paths must contain path names.")

        configured_paths = set(additional_required_paths)
        normalized_required_paths = tuple(
            sorted(configured_paths | set(self._default_required_paths))
        )
        unsupported_paths = tuple(
            sorted(
                path for path in configured_paths if path not in self._path_rule_names
            )
        )

        if unsupported_paths:
            unsupported = ", ".join(repr(path) for path in unsupported_paths)
            raise ValueError(f"Unsupported required documentation path: {unsupported}")

        self._required_paths = frozenset(normalized_required_paths)
        self._clock = clock

    def inspect(self, context: ProjectContext) -> InspectorResult:
        """Inspect essential paths and zero-byte documentation files."""
        root = context.root

        started_at = self._clock()
        findings, root_files, docs_root = self._inspect_documentation_paths(root)
        documentation_files = self._documentation_files(
            context,
            root_files=root_files,
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

    def _inspect_documentation_paths(
        self,
        root: Path,
    ) -> tuple[list[Finding], tuple[Path, ...], Path | None]:
        findings: list[Finding] = []
        files: list[Path] = []

        for name in self._root_documentation_files:
            candidate = root / name
            required = name in self._required_paths

            if candidate.is_symlink():
                if required:
                    findings.append(
                        self._invalid_required_path_finding(
                            name,
                            expected="regular file",
                            observed="symbolic link",
                        )
                    )
            elif not candidate.exists():
                if required:
                    findings.append(self._missing_required_path_finding(name))
            elif not candidate.is_file():
                if required:
                    findings.append(
                        self._invalid_required_path_finding(
                            name,
                            expected="regular file",
                            observed=self._path_kind(candidate),
                        )
                    )
            else:
                files.append(candidate)

        docs_root = root / self._docs_directory
        docs_required = self._docs_directory in self._required_paths

        if docs_root.is_symlink():
            if docs_required:
                findings.append(
                    self._invalid_required_path_finding(
                        self._docs_directory,
                        expected="directory",
                        observed="symbolic link",
                    )
                )
            valid_docs_root: Path | None = None
        elif not docs_root.exists():
            if docs_required:
                findings.append(
                    self._missing_required_path_finding(self._docs_directory)
                )
            valid_docs_root = None
        elif not docs_root.is_dir():
            if docs_required:
                findings.append(
                    self._invalid_required_path_finding(
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
        root_files: tuple[Path, ...],
        docs_root: Path | None,
    ) -> tuple[Path, ...]:
        files = set(root_files)

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

    def _missing_required_path_finding(self, relative_path: str) -> Finding:
        return Finding(
            rule_id=self._rule_id("missing", relative_path),
            title="Required documentation path not found",
            description=(
                f"The required documentation path {relative_path!r} is absent."
            ),
            category=self.category,
            kind=FindingKind.CONFIRMED_ISSUE,
            severity=Severity.LOW,
            confidence=Confidence.from_score(
                1.0,
                "The configured path requirement was checked directly.",
            ),
            evidence=(
                Evidence(
                    description="The expected path does not exist at the project root.",
                    source=SourceLocation(path=relative_path),
                ),
            ),
            impact=(
                "A documentation entry required by the active policy is unavailable."
            ),
            recommendation=Recommendation(
                summary=f"Add the expected documentation path {relative_path!r}.",
                rationale=(
                    "The active documentation policy explicitly requires this path."
                ),
            ),
        )

    def _invalid_required_path_finding(
        self,
        relative_path: str,
        *,
        expected: str,
        observed: str,
    ) -> Finding:
        return Finding(
            rule_id=self._rule_id("invalid", relative_path),
            title="Required documentation path has an invalid type",
            description=(
                f"The path {relative_path!r} is a {observed}; expected {expected}."
            ),
            category=self.category,
            kind=FindingKind.CONFIRMED_ISSUE,
            severity=Severity.LOW,
            confidence=Confidence.from_score(
                1.0,
                "The configured path requirement and filesystem type were checked "
                "directly.",
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
                    "The active documentation policy explicitly requires the expected "
                    "path type."
                ),
            ),
        )

    def _rule_id(self, condition: str, relative_path: str) -> str:
        rule_name = self._path_rule_names[relative_path]
        return f"documentation.{condition}-{rule_name}"

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
