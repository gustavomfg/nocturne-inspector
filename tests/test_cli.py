from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

from nocturne_inspector import __version__
from nocturne_inspector.cli import main
from nocturne_inspector.inspectors.registry import InspectorRegistry
from nocturne_inspector.models import InspectionReport
from nocturne_inspector.pipeline import InspectionPipeline

FIXED_TIMESTAMP = "2026-07-18T12:00:00+00:00"


def create_pipeline() -> InspectionPipeline:
    """Create an empty pipeline with controlled operational metadata."""
    return InspectionPipeline(
        InspectorRegistry(),
        run_id_factory=lambda: "run-fixed",
        generated_at_factory=lambda: FIXED_TIMESTAMP,
    )


class FailingPipeline(InspectionPipeline):
    """Pipeline that raises a deterministic user-facing error."""

    def __init__(self) -> None:
        super().__init__(InspectorRegistry())

    def run(self, project_root: Path) -> InspectionReport:
        raise ValueError("controlled failure")


class CliTests(unittest.TestCase):
    def test_help_describes_inspection_command(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output), self.assertRaises(SystemExit) as raised:
            main(["--help"])

        self.assertEqual(raised.exception.code, 0)
        self.assertIn("inspect", output.getvalue())
        self.assertIn("Engineering Intelligence Engine", output.getvalue())

    def test_version_reports_package_version(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output), self.assertRaises(SystemExit) as raised:
            main(["--version"])

        self.assertEqual(raised.exception.code, 0)
        self.assertEqual(
            output.getvalue().strip(),
            f"nocturne-inspector {__version__}",
        )

    def test_inspect_prints_json_to_standard_output(self) -> None:
        with TemporaryDirectory() as directory:
            output = io.StringIO()

            status = main(
                ["inspect", directory, "--format", "json"],
                pipeline=create_pipeline(),
                stdout=output,
            )

            report = json.loads(output.getvalue())
            self.assertEqual(status, 0)
            self.assertEqual(report["run_id"], "run-fixed")
            self.assertEqual(report["generated_at"], FIXED_TIMESTAMP)
            self.assertEqual(report["project"]["root"], Path(directory).as_posix())

    def test_inspect_writes_only_to_explicit_output(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / "inspection.json"
            output = io.StringIO()

            status = main(
                ["inspect", str(root), "--output", str(destination)],
                pipeline=create_pipeline(),
                stdout=output,
            )

            self.assertEqual(status, 0)
            self.assertEqual(output.getvalue(), "")
            self.assertEqual(
                json.loads(destination.read_text(encoding="utf-8"))["run_id"],
                "run-fixed",
            )

    def test_inspect_does_not_overwrite_existing_output(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / "inspection.json"
            destination.write_text("preserve me", encoding="utf-8")
            errors = io.StringIO()

            status = main(
                ["inspect", str(root), "--output", str(destination)],
                pipeline=create_pipeline(),
                stderr=errors,
            )

            self.assertEqual(status, 1)
            self.assertIn("already exists", errors.getvalue())
            self.assertEqual(
                destination.read_text(encoding="utf-8"),
                "preserve me",
            )

    def test_inspect_reports_pipeline_errors_without_traceback(self) -> None:
        errors = io.StringIO()

        status = main(
            ["inspect", "."],
            pipeline=FailingPipeline(),
            stderr=errors,
        )

        self.assertEqual(status, 1)
        self.assertEqual(errors.getvalue().strip(), "error: controlled failure")


if __name__ == "__main__":
    unittest.main()
