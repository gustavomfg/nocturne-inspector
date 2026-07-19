from __future__ import annotations

import json
import unittest
from pathlib import Path

from nocturne_inspector.models import (
    INSPECTOR_VERSION,
    REPORT_SCHEMA_VERSION,
    InspectionReport,
    ProjectMetadata,
)

SCHEMA_PATH = Path("docs/inspection-report.schema.json")
FIXED_TIMESTAMP = "2026-07-18T12:00:00+00:00"


class ReportSchemaTests(unittest.TestCase):
    def test_schema_is_valid_json_and_matches_runtime_version(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

        self.assertEqual(
            schema["$schema"], "https://json-schema.org/draft/2020-12/schema"
        )
        self.assertEqual(
            schema["properties"]["schema_version"]["const"],
            REPORT_SCHEMA_VERSION,
        )

    def test_runtime_report_contains_every_required_top_level_field(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        report = InspectionReport(
            project=ProjectMetadata(name="demo", root="/demo"),
            inspector_results=(),
            run_id="run-fixed",
            generated_at=FIXED_TIMESTAMP,
        ).to_dict()

        self.assertEqual(set(report), set(schema["required"]))
        self.assertEqual(report["schema_version"], REPORT_SCHEMA_VERSION)
        self.assertEqual(report["inspector_version"], INSPECTOR_VERSION)

    def test_schema_documents_every_serialized_finding_field(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        finding_contract = schema["$defs"]["finding"]

        self.assertEqual(
            set(finding_contract["required"]),
            set(finding_contract["properties"]),
        )

    def test_schema_documents_inspector_execution_status(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        result_contract = schema["$defs"]["inspectorResult"]

        self.assertEqual(
            set(result_contract["required"]),
            set(result_contract["properties"]),
        )
        self.assertEqual(
            result_contract["properties"]["status"]["enum"],
            ["success", "failed"],
        )


if __name__ == "__main__":
    unittest.main()
