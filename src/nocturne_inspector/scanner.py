from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from nocturne_inspector.models import ProjectContext

DEFAULT_EXCLUDED_DIRECTORIES = (
    ".git",
    ".idea",
    ".mypy_cache",
    ".nocturne",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    ".vscode",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "logs",
    "node_modules",
    "out",
    "release",
)

_LANGUAGE_BY_SUFFIX = {
    ".c": "C",
    ".cc": "C++",
    ".cpp": "C++",
    ".cs": "C#",
    ".cxx": "C++",
    ".go": "Go",
    ".java": "Java",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".php": "PHP",
    ".py": "Python",
    ".pyi": "Python",
    ".rb": "Ruby",
    ".rs": "Rust",
    ".scala": "Scala",
    ".sh": "Shell",
    ".swift": "Swift",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
}


class ProjectScanner:
    """Build one deterministic, read-only inventory for a project workspace."""

    def __init__(
        self,
        *,
        excluded_directories: Iterable[str] = DEFAULT_EXCLUDED_DIRECTORIES,
    ) -> None:
        exclusions = tuple(sorted(set(excluded_directories)))

        if any(not name.strip() or Path(name).name != name for name in exclusions):
            raise ValueError("Exclusions must be non-empty directory names.")

        self._excluded_directories = exclusions

    def scan(self, project_root: Path) -> ProjectContext:
        """Scan regular files without following symbolic links."""
        root = project_root.expanduser().resolve(strict=True)

        if not root.is_dir():
            raise NotADirectoryError(f"Project root is not a directory: {root}")

        excluded = frozenset(self._excluded_directories)
        files: list[Path] = []

        for directory, directory_names, file_names in root.walk(
            on_error=self._raise_walk_error
        ):
            directory_names[:] = sorted(
                name
                for name in directory_names
                if name not in excluded and not (directory / name).is_symlink()
            )

            for file_name in sorted(file_names):
                candidate = directory / file_name

                if candidate.is_symlink() or not candidate.is_file():
                    continue

                files.append(candidate.relative_to(root))

        languages = {
            language
            for path in files
            if (language := _LANGUAGE_BY_SUFFIX.get(path.suffix.casefold())) is not None
        }
        return ProjectContext(
            root=root,
            files=tuple(files),
            languages=tuple(languages),
            excluded_directories=self._excluded_directories,
        )

    @staticmethod
    def _raise_walk_error(error: OSError) -> None:
        """Reject incomplete inventories instead of silently hiding scan errors."""
        raise error


def scan_project(project_root: Path) -> ProjectContext:
    """Build a project context with the default deterministic scan policy."""
    return ProjectScanner().scan(project_root)
