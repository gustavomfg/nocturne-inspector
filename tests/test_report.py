from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from nocturne_inspector.models import InspectionReport, ProjectMetadata
from nocturne_inspector.report import (
    report_to_dict,
    report_to_json,
    save_json_report,
)


def make_report(*, run_id: str = "run-fixed") -> InspectionReport:
    """Create a report with controlled operational metadata."""
    return InspectionReport(
        project=ProjectMetadata(name="demo", root="/demo"),
        inspector_results=(),
        run_id=run_id,
        generated_at="2026-07-18T12:00:00+00:00",
    )


class ReportSerializationTests(unittest.TestCase):
    def test_serializes_report_as_json_compatible_values(self) -> None:
        report = make_report()

        data = report_to_dict(report)
        serialized = report_to_json(report)

        self.assertEqual(json.loads(serialized), data)
        self.assertEqual(data["run_id"], "run-fixed")
        self.assertIn("summary", data)
        self.assertIn("metrics", data)

    def test_serialization_is_stable_when_metadata_is_controlled(self) -> None:
        self.assertEqual(report_to_json(make_report()), report_to_json(make_report()))

    def test_rejects_negative_indentation(self) -> None:
        with self.assertRaises(ValueError):
            report_to_json(make_report(), indent=-1)

    def test_rejects_non_finite_values_as_a_serialization_defense(self) -> None:
        for value in (float("nan"), float("inf"), float("-inf")):
            with (
                self.subTest(value=value),
                patch(
                    "nocturne_inspector.report.report_to_dict",
                    return_value={"metric": value},
                ),
                self.assertRaises(ValueError),
            ):
                report_to_json(make_report())


class ReportWritingTests(unittest.TestCase):
    def test_writes_complete_report_without_leaving_temporary_files(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / "inspection.json"

            result = save_json_report(make_report(), destination)

            self.assertEqual(result, destination.resolve())
            self.assertEqual(
                json.loads(destination.read_text(encoding="utf-8")),
                report_to_dict(make_report()),
            )
            self.assertEqual(tuple(root.glob(".inspection.json.*.tmp")), ())

    def test_does_not_overwrite_an_existing_file_by_default(self) -> None:
        with TemporaryDirectory() as directory:
            destination = Path(directory) / "inspection.json"
            destination.write_text("preserve me", encoding="utf-8")

            with self.assertRaises(FileExistsError):
                save_json_report(make_report(), destination)

            self.assertEqual(
                destination.read_text(encoding="utf-8"),
                "preserve me",
            )

    def test_overwrites_only_when_explicitly_requested(self) -> None:
        with TemporaryDirectory() as directory:
            destination = Path(directory) / "inspection.json"
            destination.write_text("old content", encoding="utf-8")

            save_json_report(make_report(), destination, overwrite=True)

            self.assertEqual(
                json.loads(destination.read_text(encoding="utf-8")),
                report_to_dict(make_report()),
            )

    def test_does_not_create_missing_parent_directories(self) -> None:
        with TemporaryDirectory() as directory:
            destination = Path(directory) / "missing" / "inspection.json"

            with self.assertRaises(FileNotFoundError):
                save_json_report(make_report(), destination)

            self.assertFalse(destination.parent.exists())

    def test_rejects_directory_and_non_directory_parent_destinations(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)

            with self.assertRaises(IsADirectoryError):
                save_json_report(make_report(), root)

            parent_file = root / "not-a-directory"
            parent_file.write_text("content", encoding="utf-8")

            with self.assertRaises(NotADirectoryError):
                save_json_report(make_report(), parent_file / "inspection.json")

    def test_rejects_symbolic_link_destinations(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target.json"
            target.write_text("preserve me", encoding="utf-8")
            destination = root / "inspection.json"
            destination.symlink_to(target)

            with self.assertRaises(ValueError):
                save_json_report(
                    make_report(),
                    destination,
                    overwrite=True,
                )

            self.assertEqual(target.read_text(encoding="utf-8"), "preserve me")

    def test_preserves_existing_file_when_atomic_replacement_fails(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / "inspection.json"
            destination.write_text("preserve me", encoding="utf-8")

            with patch.object(Path, "replace", side_effect=OSError("failure")):
                with self.assertRaises(OSError):
                    save_json_report(
                        make_report(),
                        destination,
                        overwrite=True,
                    )

            self.assertEqual(
                destination.read_text(encoding="utf-8"),
                "preserve me",
            )
            self.assertEqual(tuple(root.glob(".inspection.json.*.tmp")), ())


if __name__ == "__main__":
    unittest.main()
