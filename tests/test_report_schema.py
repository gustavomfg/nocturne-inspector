from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError

from nocturne_inspector.models import (
    INSPECTOR_VERSION,
    REPORT_SCHEMA_VERSION,
    Confidence,
    Evidence,
    Finding,
    FindingCategory,
    FindingKind,
    InspectionReport,
    InspectorResult,
    InspectorStatus,
    ProjectMetadata,
    Recommendation,
    Severity,
    SourceLocation,
)

SCHEMA_PATH = Path("docs/inspection-report.schema.json")
FIXED_TIMESTAMP = "2026-07-18T12:00:00+00:00"


def make_finding(
    *,
    path: str,
    recommendation: Recommendation | None,
) -> Finding:
    """Create a finding that exercises the complete nested report contract."""
    return Finding(
        rule_id="documentation.empty-file",
        title="Empty documentation file",
        description="A documentation file contains zero bytes.",
        category=FindingCategory.DOCUMENTATION,
        kind=FindingKind.CONFIRMED_ISSUE,
        severity=Severity.LOW,
        confidence=Confidence.from_score(
            1.0,
            "The file size was read directly from the filesystem.",
        ),
        evidence=(
            Evidence(
                description="The file contains zero bytes.",
                source=SourceLocation(
                    path=path,
                    line_start=1,
                    line_end=1,
                    symbol="document",
                ),
                excerpt="",
            ),
        ),
        impact="The file provides no documentation content.",
        recommendation=recommendation,
    )


def make_complete_report() -> InspectionReport:
    """Create a report covering findings, failures, warnings, and metrics."""
    filled_recommendation = Recommendation(
        summary="Document the intended topic.",
        rationale="Non-empty documentation communicates project context.",
        effort="small",
        breaking_change_risk=False,
    )
    successful = InspectorResult(
        inspector="documentation",
        category=FindingCategory.DOCUMENTATION,
        findings=(
            make_finding(
                path="CHANGELOG.md",
                recommendation=filled_recommendation,
            ),
            make_finding(path="LICENSE", recommendation=None),
        ),
        duration_ms=2.5,
        files_examined=2,
        warnings=("One optional document could not be examined.",),
    )
    failed = InspectorResult(
        inspector="testing",
        category=FindingCategory.TESTING,
        findings=(),
        duration_ms=0.0,
        files_examined=0,
        status=InspectorStatus.FAILED,
        error="PermissionError while executing inspector.",
    )
    return InspectionReport(
        project=ProjectMetadata(
            name="demo",
            root="/demo",
            languages=("Python",),
            files_scanned=3,
        ),
        inspector_results=(failed, successful),
        run_id="run-fixed",
        generated_at=FIXED_TIMESTAMP,
    )


def load_schema() -> object:
    """Load the canonical report schema as JSON data."""
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def create_validator() -> Draft202012Validator:
    """Create the validator used by contract tests, including format checks."""
    schema = load_schema()
    if not isinstance(schema, dict):
        raise TypeError("Report schema must be a JSON object.")

    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


class ReportSchemaTests(unittest.TestCase):
    def test_schema_is_valid_json_and_matches_runtime_version(self) -> None:
        schema = load_schema()
        self.assertIsInstance(schema, dict)
        assert isinstance(schema, dict)

        Draft202012Validator.check_schema(schema)

        self.assertEqual(
            schema["$schema"], "https://json-schema.org/draft/2020-12/schema"
        )
        self.assertEqual(
            schema["properties"]["schema_version"]["const"],
            REPORT_SCHEMA_VERSION,
        )

    def test_runtime_report_contains_every_required_top_level_field(self) -> None:
        schema = load_schema()
        self.assertIsInstance(schema, dict)
        assert isinstance(schema, dict)
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
        schema = load_schema()
        self.assertIsInstance(schema, dict)
        assert isinstance(schema, dict)
        finding_contract = schema["$defs"]["finding"]

        self.assertEqual(
            set(finding_contract["required"]),
            set(finding_contract["properties"]),
        )

    def test_schema_documents_inspector_execution_status(self) -> None:
        schema = load_schema()
        self.assertIsInstance(schema, dict)
        assert isinstance(schema, dict)
        result_contract = schema["$defs"]["inspectorResult"]

        self.assertEqual(
            set(result_contract["required"]),
            set(result_contract["properties"]),
        )
        self.assertEqual(
            result_contract["properties"]["status"]["enum"],
            ["success", "failed"],
        )

    def test_complete_runtime_report_satisfies_schema(self) -> None:
        validator = create_validator()

        validator.validate(make_complete_report().to_dict())

    def test_rejects_incompatible_nested_report_changes(self) -> None:
        validator = create_validator()

        missing_project_name = make_complete_report().to_dict()
        project = missing_project_name["project"]
        assert isinstance(project, dict)
        del project["name"]

        invalid_severity = make_complete_report().to_dict()
        inspector_results = invalid_severity["inspector_results"]
        assert isinstance(inspector_results, list)
        first_result = inspector_results[0]
        assert isinstance(first_result, dict)
        findings = first_result["findings"]
        assert isinstance(findings, list)
        first_finding = findings[0]
        assert isinstance(first_finding, dict)
        first_finding["severity"] = "urgent"

        invalid_timestamp = make_complete_report().to_dict()
        invalid_timestamp["generated_at"] = "not-a-date-time"

        unexpected_field = make_complete_report().to_dict()
        unexpected_field["unsupported"] = True

        incompatible_reports = (
            missing_project_name,
            invalid_severity,
            invalid_timestamp,
            unexpected_field,
        )

        for report in incompatible_reports:
            with self.subTest(report=report), self.assertRaises(ValidationError):
                validator.validate(report)


if __name__ == "__main__":
    unittest.main()
