from __future__ import annotations

import unittest
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory

from nocturne_inspector.inspectors.documentation import DocumentationInspector
from nocturne_inspector.models import FindingKind
from nocturne_inspector.scanner import scan_project

ROOT_DOCUMENTATION_FILES = (
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
    """Create every known documentation path with deterministic content."""
    for name in ROOT_DOCUMENTATION_FILES:
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
    def test_reports_no_findings_when_known_documentation_exists(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            create_documented_project(root)
            inspector = DocumentationInspector(clock=ControlledClock(1.0, 1.25))

            result = inspector.inspect(scan_project(root))

            self.assertEqual(result.findings, ())
            self.assertEqual(result.files_examined, 7)
            self.assertEqual(result.duration_ms, 250.0)

    def test_default_policy_requires_only_readme(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)

            result = DocumentationInspector(clock=ControlledClock(1.0, 1.0)).inspect(
                scan_project(root)
            )

            self.assertEqual(len(result.findings), 1)
            finding = result.findings[0]
            self.assertEqual(finding.rule_id, "documentation.missing-readme")
            self.assertIs(finding.kind, FindingKind.CONFIRMED_ISSUE)
            self.assertEqual(finding.evidence[0].source.path, "README.md")

    def test_absent_optional_paths_do_not_produce_findings(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("Project\n", encoding="utf-8")

            result = DocumentationInspector(clock=ControlledClock(1.0, 1.0)).inspect(
                scan_project(root)
            )

            self.assertEqual(result.findings, ())
            self.assertEqual(result.files_examined, 1)

    def test_explicit_policy_uses_distinct_rule_ids_for_each_path(self) -> None:
        expected_rule_ids = {
            "documentation.missing-agents",
            "documentation.missing-changelog",
            "documentation.missing-contributing",
            "documentation.missing-docs-directory",
            "documentation.missing-license",
            "documentation.missing-readme",
            "documentation.missing-security",
        }

        with TemporaryDirectory() as directory:
            root = Path(directory)
            inspector = DocumentationInspector(
                additional_required_paths=(*ROOT_DOCUMENTATION_FILES, "docs"),
                clock=ControlledClock(1.0, 1.0),
            )

            result = inspector.inspect(scan_project(root))

            self.assertEqual(
                {finding.rule_id for finding in result.findings},
                expected_rule_ids,
            )
            self.assertTrue(
                all(
                    finding.kind is FindingKind.CONFIRMED_ISSUE
                    for finding in result.findings
                )
            )

    def test_reports_invalid_types_only_for_explicit_requirements(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            create_documented_project(root)
            (root / "README.md").unlink()
            (root / "README.md").mkdir()
            (root / "docs" / "guide.md").unlink()
            (root / "docs").rmdir()
            (root / "docs").write_text("not a directory\n", encoding="utf-8")

            result = DocumentationInspector(
                additional_required_paths=("docs",),
                clock=ControlledClock(1.0, 1.0),
            ).inspect(scan_project(root))

            self.assertEqual(
                {finding.rule_id for finding in result.findings},
                {
                    "documentation.invalid-docs-directory",
                    "documentation.invalid-readme",
                },
            )

    def test_rejects_unknown_required_path(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported.md"):
            DocumentationInspector(additional_required_paths=("unsupported.md",))

        with self.assertRaises(TypeError):
            DocumentationInspector(additional_required_paths="SECURITY.md")

    def test_reports_zero_byte_documentation_with_stable_semantics(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            create_documented_project(root)
            (root / "README.md").write_bytes(b"")
            (root / "docs" / "z.md").touch()
            (root / "docs" / "a.rst").touch()

            first = DocumentationInspector(clock=ControlledClock(1.0, 1.0)).inspect(
                scan_project(root)
            )
            second = DocumentationInspector(clock=ControlledClock(2.0, 2.0)).inspect(
                scan_project(root)
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
                scan_project(root)
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

            result = DocumentationInspector(
                additional_required_paths=("docs",),
                clock=ControlledClock(1.0, 1.0),
            ).inspect(scan_project(root))

            invalid = tuple(
                finding
                for finding in result.findings
                if finding.rule_id == "documentation.invalid-docs-directory"
            )
            self.assertEqual(len(invalid), 1)
            self.assertEqual(invalid[0].evidence[0].source.path, "docs")
            self.assertEqual(result.files_examined, len(ROOT_DOCUMENTATION_FILES))

    def test_inspection_does_not_modify_workspace(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            create_documented_project(root)
            before = workspace_snapshot(root)

            DocumentationInspector(clock=ControlledClock(1.0, 1.0)).inspect(
                scan_project(root)
            )

            self.assertEqual(workspace_snapshot(root), before)


if __name__ == "__main__":
    unittest.main()
