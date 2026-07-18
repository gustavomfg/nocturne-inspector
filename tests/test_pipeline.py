from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from nocturne_inspector.inspectors.base import Inspector
from nocturne_inspector.inspectors.registry import InspectorRegistry
from nocturne_inspector.models import FindingCategory, InspectorResult
from nocturne_inspector.pipeline import InspectionPipeline

FIXED_TIMESTAMP = "2026-07-18T12:00:00+00:00"


class RecordingInspector(Inspector):
    """Record sequential pipeline execution for tests."""

    category = FindingCategory.TESTING

    def __init__(self, name: str, events: list[str], *, files_examined: int) -> None:
        self.name = name
        self._events = events
        self._files_examined = files_examined
        self.received_root: Path | None = None

    def inspect(self, project_root: Path) -> InspectorResult:
        self.received_root = project_root
        self._events.append(self.name)
        return InspectorResult(
            inspector=self.name,
            category=self.category,
            findings=(),
            duration_ms=0.0,
            files_examined=self._files_examined,
        )


class FailingInspector(Inspector):
    """Fail deterministically to verify pipeline error propagation."""

    name = "failure"
    category = FindingCategory.TESTING

    def inspect(self, project_root: Path) -> InspectorResult:
        raise RuntimeError("deterministic inspector failure")


def create_pipeline(registry: InspectorRegistry) -> InspectionPipeline:
    """Create a pipeline with controlled operational metadata."""
    return InspectionPipeline(
        registry,
        run_id_factory=lambda: "run-fixed",
        generated_at_factory=lambda: FIXED_TIMESTAMP,
    )


class InspectionPipelineTests(unittest.TestCase):
    def test_executes_registry_snapshot_sequentially(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            events: list[str] = []
            registry = InspectorRegistry()
            second = RecordingInspector("second", events, files_examined=2)
            first = RecordingInspector("first", events, files_examined=1)
            registry.register(second)
            registry.register(first)

            report = create_pipeline(registry).run(root)

            self.assertEqual(events, ["first", "second"])
            self.assertEqual(first.received_root, root.resolve())
            self.assertEqual(second.received_root, root.resolve())
            self.assertEqual(report.total_files_examined, 3)

    def test_builds_project_and_run_metadata(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            report = create_pipeline(InspectorRegistry()).run(root)

            self.assertEqual(report.project.name, root.name)
            self.assertEqual(report.project.root, root.as_posix())
            self.assertEqual(report.project.files_scanned, 0)
            self.assertEqual(report.run_id, "run-fixed")
            self.assertEqual(report.generated_at, FIXED_TIMESTAMP)
            self.assertEqual(report.inspector_results, ())

    def test_propagates_failure_and_stops_later_inspectors(self) -> None:
        with TemporaryDirectory() as directory:
            events: list[str] = []
            registry = InspectorRegistry()
            registry.register(FailingInspector())
            registry.register(RecordingInspector("later", events, files_examined=0))

            with self.assertRaisesRegex(RuntimeError, "deterministic"):
                create_pipeline(registry).run(Path(directory))

            self.assertEqual(events, [])

    def test_rejects_missing_and_non_directory_workspaces(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            project_file = root / "project.txt"
            project_file.touch()
            pipeline = create_pipeline(InspectorRegistry())

            with self.assertRaises(FileNotFoundError):
                pipeline.run(root / "missing")

            with self.assertRaises(NotADirectoryError):
                pipeline.run(project_file)


if __name__ == "__main__":
    unittest.main()
