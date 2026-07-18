from __future__ import annotations

import unittest
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory

from nocturne_inspector.inspectors.documentation import DocumentationInspector

ESSENTIAL_FILES = (
    "AGENTS.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "README.md",
    "SECURITY.md",
)


class ControlledClock:
    """Return a finite sequence of monotonic values for tests."""

    def __init__(self, *values: float) -> None:
        self._values: Iterator[float] = iter(values)

    def __call__(self) -> float:
        return next(self._values)


def create_documented_project(root: Path) -> None:
    """Create every essential documentation path with deterministic content."""
    for name in ESSENTIAL_FILES:
        (root / name).write_text(f"{name}\n", encoding="utf-8")

    (root / "docs").mkdir()
    (root / "docs" / "guide.md").write_text("Guide\n", encoding="utf-8")


def workspace_snapshot(root: Path) -> tuple[tuple[str, bytes], ...]:
    """Capture file contents beneath a test workspace."""
    return tuple(
        (path.relative_to(root).as_posix(), path.read_bytes())
        for path in sorted(root.rglob("*"))
        if not path.is_symlink() and path.is_file()
    )


class DocumentationInspectorTests(unittest.TestCase):
    def test_reports_no_findings_when_essential_documentation_exists(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            create_documented_project(root)
            inspector = DocumentationInspector(clock=ControlledClock(1.0, 1.25))

            result = inspector.inspect(root)

            self.assertEqual(result.findings, ())
            self.assertEqual(result.files_examined, 7)
            self.assertEqual(result.duration_ms, 250.0)

    def test_reports_each_missing_essential_path_with_direct_evidence(self) -> None:
        expected_paths = (*ESSENTIAL_FILES, "docs")

        for missing_path in expected_paths:
            with self.subTest(path=missing_path), TemporaryDirectory() as directory:
                root = Path(directory)
                create_documented_project(root)
                candidate = root / missing_path

                if candidate.is_dir():
                    for child in candidate.iterdir():
                        child.unlink()
                    candidate.rmdir()
                else:
                    candidate.unlink()

                result = DocumentationInspector(
                    clock=ControlledClock(1.0, 1.0)
                ).inspect(root)
                missing = tuple(
                    finding
                    for finding in result.findings
                    if finding.rule_id == "documentation.missing-essential-path"
                )

                self.assertEqual(len(missing), 1)
                self.assertEqual(missing[0].evidence[0].source.path, missing_path)

    def test_reports_invalid_essential_path_types(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            create_documented_project(root)
            (root / "README.md").unlink()
            (root / "README.md").mkdir()
            (root / "docs" / "guide.md").unlink()
            (root / "docs").rmdir()
            (root / "docs").write_text("not a directory\n", encoding="utf-8")

            result = DocumentationInspector(clock=ControlledClock(1.0, 1.0)).inspect(
                root
            )
            invalid_paths = {
                finding.evidence[0].source.path
                for finding in result.findings
                if finding.rule_id == "documentation.invalid-essential-path"
            }

            self.assertEqual(invalid_paths, {"README.md", "docs"})

    def test_reports_zero_byte_documentation_with_stable_semantics(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            create_documented_project(root)
            (root / "README.md").write_bytes(b"")
            (root / "docs" / "z.md").touch()
            (root / "docs" / "a.rst").touch()

            first = DocumentationInspector(clock=ControlledClock(1.0, 1.0)).inspect(
                root
            )
            second = DocumentationInspector(clock=ControlledClock(2.0, 2.0)).inspect(
                root
            )

            first_semantics = tuple(
                (finding.identifier, finding.rule_id, finding.evidence[0].source.path)
                for finding in first.findings
            )
            second_semantics = tuple(
                (finding.identifier, finding.rule_id, finding.evidence[0].source.path)
                for finding in second.findings
            )
            self.assertEqual(first_semantics, second_semantics)
            self.assertEqual(
                tuple(finding.identifier for finding in first.findings),
                tuple(sorted(finding.identifier for finding in first.findings)),
            )

    def test_does_not_treat_whitespace_only_file_as_zero_byte(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            create_documented_project(root)
            (root / "README.md").write_text(" \n", encoding="utf-8")

            result = DocumentationInspector(clock=ControlledClock(1.0, 1.0)).inspect(
                root
            )

            self.assertEqual(result.findings, ())

    def test_does_not_follow_documentation_symlinks(self) -> None:
        with TemporaryDirectory() as directory, TemporaryDirectory() as external:
            root = Path(directory)
            create_documented_project(root)
            (root / "docs" / "guide.md").unlink()
            (root / "docs").rmdir()
            external_docs = Path(external) / "docs"
            external_docs.mkdir()
            (external_docs / "outside.md").touch()
            (root / "docs").symlink_to(external_docs, target_is_directory=True)

            result = DocumentationInspector(clock=ControlledClock(1.0, 1.0)).inspect(
                root
            )

            invalid = tuple(
                finding
                for finding in result.findings
                if finding.rule_id == "documentation.invalid-essential-path"
            )
            self.assertEqual(len(invalid), 1)
            self.assertEqual(invalid[0].evidence[0].source.path, "docs")
            self.assertEqual(result.files_examined, len(ESSENTIAL_FILES))

    def test_inspection_does_not_modify_workspace(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            create_documented_project(root)
            before = workspace_snapshot(root)

            DocumentationInspector(clock=ControlledClock(1.0, 1.0)).inspect(root)

            self.assertEqual(workspace_snapshot(root), before)

    def test_rejects_missing_or_non_directory_project_roots(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            project_file = root / "project.txt"
            project_file.touch()
            inspector = DocumentationInspector(clock=ControlledClock(1.0, 1.0))

            with self.assertRaises(FileNotFoundError):
                inspector.inspect(root / "missing")

            with self.assertRaises(NotADirectoryError):
                inspector.inspect(project_file)


if __name__ == "__main__":
    unittest.main()
