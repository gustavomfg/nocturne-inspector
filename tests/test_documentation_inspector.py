from __future__ import annotations

import unittest
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory

from nocturne_inspector.inspectors.documentation import DocumentationInspector


class ControlledClock:
    """Return a finite sequence of monotonic values for tests."""

    def __init__(self, *values: float) -> None:
        self._values: Iterator[float] = iter(values)

    def __call__(self) -> float:
        return next(self._values)


def workspace_snapshot(root: Path) -> tuple[tuple[str, bytes], ...]:
    """Capture file contents beneath a test workspace."""
    return tuple(
        (path.relative_to(root).as_posix(), path.read_bytes())
        for path in sorted(root.rglob("*"))
        if not path.is_symlink() and path.is_file()
    )


class DocumentationInspectorTests(unittest.TestCase):
    def test_reports_no_findings_for_non_empty_documentation(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            (root / "docs").mkdir()
            (root / "docs" / "guide.md").write_text("Guide\n", encoding="utf-8")
            inspector = DocumentationInspector(clock=ControlledClock(1.0, 1.25))

            result = inspector.inspect(root)

            self.assertEqual(result.findings, ())
            self.assertEqual(result.files_examined, 2)
            self.assertEqual(result.duration_ms, 250.0)

    def test_reports_missing_root_readme_with_search_evidence(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            inspector = DocumentationInspector(clock=ControlledClock(1.0, 1.0))

            result = inspector.inspect(root)

            self.assertEqual(len(result.findings), 1)
            finding = result.findings[0]
            self.assertEqual(
                finding.rule_id,
                "documentation.missing-root-readme",
            )
            self.assertEqual(finding.evidence[0].source.path, ".")
            self.assertIn("readme.md", finding.evidence[0].description)

    def test_reports_zero_byte_documentation_in_stable_order(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").touch()
            (root / "docs").mkdir()
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
            (root / "README.md").write_text(" \n", encoding="utf-8")
            inspector = DocumentationInspector(clock=ControlledClock(1.0, 1.0))

            result = inspector.inspect(root)

            self.assertEqual(result.findings, ())

    def test_does_not_follow_documentation_symlinks(self) -> None:
        with TemporaryDirectory() as directory, TemporaryDirectory() as external:
            root = Path(directory)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            external_file = Path(external) / "outside.md"
            external_file.touch()
            (root / "docs").mkdir()
            (root / "docs" / "outside.md").symlink_to(external_file)
            inspector = DocumentationInspector(clock=ControlledClock(1.0, 1.0))

            result = inspector.inspect(root)

            self.assertEqual(result.findings, ())
            self.assertEqual(result.files_examined, 1)

    def test_inspection_does_not_modify_workspace(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").touch()
            (root / "docs").mkdir()
            (root / "docs" / "guide.md").write_text("Guide\n", encoding="utf-8")
            before = workspace_snapshot(root)
            inspector = DocumentationInspector(clock=ControlledClock(1.0, 1.0))

            inspector.inspect(root)

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
