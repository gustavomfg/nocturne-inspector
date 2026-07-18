from __future__ import annotations

import unittest
from dataclasses import replace

from nocturne_inspector.models import (
    Confidence,
    ConfidenceLevel,
    Evidence,
    Finding,
    FindingCategory,
    FindingKind,
    InspectionReport,
    InspectorResult,
    ProjectMetadata,
    Recommendation,
    Severity,
    SourceLocation,
)

FIXED_TIMESTAMP = "2026-07-18T12:00:00+00:00"


def make_finding(
    *,
    rule_id: str = "documentation.empty-file",
    path: str = "README.md",
    category: FindingCategory = FindingCategory.DOCUMENTATION,
    description: str = "The documentation file is empty.",
) -> Finding:
    """Create a valid finding for domain tests."""
    return Finding(
        rule_id=rule_id,
        title="Empty documentation file",
        description=description,
        category=category,
        kind=FindingKind.CONFIRMED_ISSUE,
        severity=Severity.LOW,
        confidence=Confidence.from_score(
            1.0,
            "The file size is deterministically zero bytes.",
        ),
        evidence=(
            Evidence(
                description="The file contains zero bytes.",
                source=SourceLocation(path=path),
            ),
        ),
        impact="The file provides no documentation.",
        recommendation=Recommendation(
            summary="Document the relevant project information.",
            rationale="Non-empty documentation communicates project context.",
        ),
    )


def make_result(
    *findings: Finding,
    inspector: str = "documentation",
    category: FindingCategory = FindingCategory.DOCUMENTATION,
) -> InspectorResult:
    """Create a valid inspector result for domain tests."""
    return InspectorResult(
        inspector=inspector,
        category=category,
        findings=findings,
        duration_ms=2.5,
        files_examined=1,
    )


class SourceLocationTests(unittest.TestCase):
    def test_rejects_invalid_line_ranges(self) -> None:
        with self.assertRaises(ValueError):
            SourceLocation(path="README.md", line_start=0)

        with self.assertRaises(ValueError):
            SourceLocation(path="README.md", line_start=3, line_end=2)

    def test_rejects_empty_paths(self) -> None:
        with self.assertRaises(ValueError):
            SourceLocation(path=" ")


class ConfidenceTests(unittest.TestCase):
    def test_maps_boundary_scores_to_documented_levels(self) -> None:
        cases = (
            (0.0, ConfidenceLevel.LOW),
            (0.49, ConfidenceLevel.LOW),
            (0.5, ConfidenceLevel.MEDIUM),
            (0.79, ConfidenceLevel.MEDIUM),
            (0.8, ConfidenceLevel.HIGH),
            (1.0, ConfidenceLevel.HIGH),
        )

        for score, expected in cases:
            with self.subTest(score=score):
                confidence = Confidence.from_score(score, "Measured evidence.")
                self.assertIs(confidence.level, expected)

    def test_rejects_out_of_range_scores(self) -> None:
        for score in (-0.01, 1.01):
            with self.subTest(score=score), self.assertRaises(ValueError):
                Confidence.from_score(score, "Measured evidence.")

    def test_rejects_level_that_does_not_match_score(self) -> None:
        with self.assertRaises(ValueError):
            Confidence(
                score=0.9,
                level=ConfidenceLevel.LOW,
                rationale="Measured evidence.",
            )


class FindingTests(unittest.TestCase):
    def test_requires_rule_and_evidence(self) -> None:
        finding = make_finding()

        with self.assertRaises(ValueError):
            Finding(
                rule_id=" ",
                title=finding.title,
                description=finding.description,
                category=finding.category,
                kind=finding.kind,
                severity=finding.severity,
                confidence=finding.confidence,
                evidence=finding.evidence,
                impact=finding.impact,
            )

        with self.assertRaises(ValueError):
            Finding(
                rule_id=finding.rule_id,
                title=finding.title,
                description=finding.description,
                category=finding.category,
                kind=finding.kind,
                severity=finding.severity,
                confidence=finding.confidence,
                evidence=(),
                impact=finding.impact,
            )

    def test_identifier_is_stable_for_same_rule_category_and_location(self) -> None:
        first = make_finding(description="First wording.")
        second = make_finding(description="Updated wording.")

        self.assertEqual(first.identifier, second.identifier)

    def test_identifier_changes_with_rule_category_or_location(self) -> None:
        baseline = make_finding()
        variants = (
            make_finding(rule_id="documentation.missing-readme"),
            make_finding(path="docs/README.md"),
            make_finding(category=FindingCategory.ARCHITECTURE),
        )

        for variant in variants:
            with self.subTest(identifier=variant.identifier):
                self.assertNotEqual(baseline.identifier, variant.identifier)

    def test_evidence_order_does_not_change_identifier(self) -> None:
        first_evidence = Evidence(
            description="First evidence.",
            source=SourceLocation(path="docs/a.md"),
        )
        second_evidence = Evidence(
            description="Second evidence.",
            source=SourceLocation(path="docs/b.md"),
        )
        baseline = make_finding()
        first = replace(
            baseline,
            evidence=(second_evidence, first_evidence),
        )
        second = replace(
            baseline,
            evidence=(first_evidence, second_evidence),
        )

        self.assertEqual(first.evidence, second.evidence)
        self.assertEqual(first.identifier, second.identifier)


class InspectorResultTests(unittest.TestCase):
    def test_rejects_findings_from_another_category(self) -> None:
        with self.assertRaises(ValueError):
            make_result(
                make_finding(category=FindingCategory.ARCHITECTURE),
            )

    def test_orders_findings_and_warnings_deterministically(self) -> None:
        first = make_finding(path="docs/a.md")
        second = make_finding(path="docs/b.md")
        result = InspectorResult(
            inspector="documentation",
            category=FindingCategory.DOCUMENTATION,
            findings=(second, first),
            duration_ms=0.0,
            files_examined=2,
            warnings=("z warning", "a warning"),
        )

        self.assertEqual(
            tuple(finding.identifier for finding in result.findings),
            tuple(sorted((first.identifier, second.identifier))),
        )
        self.assertEqual(result.warnings, ("a warning", "z warning"))


class InspectionReportTests(unittest.TestCase):
    def test_aggregates_findings_and_metrics(self) -> None:
        first = make_finding(path="README.md")
        second = make_finding(path="docs/empty.md")
        report = InspectionReport(
            project=ProjectMetadata(
                name="demo",
                root="/demo",
                languages=("Python", "Markdown", "Python"),
                files_scanned=2,
            ),
            inspector_results=(make_result(second, first),),
            run_id="run-fixed",
            generated_at=FIXED_TIMESTAMP,
        )

        self.assertEqual(report.project.languages, ("Markdown", "Python"))
        self.assertEqual(report.summary.total_findings, 2)
        self.assertEqual(report.summary.by_severity[Severity.LOW.value], 2)
        self.assertEqual(
            report.summary.by_category[FindingCategory.DOCUMENTATION.value],
            2,
        )
        self.assertEqual(report.total_duration_ms, 2.5)
        self.assertEqual(report.total_files_examined, 1)

    def test_orders_inspector_results_deterministically(self) -> None:
        documentation = make_result(inspector="z-documentation")
        architecture = make_result(
            inspector="architecture",
            category=FindingCategory.ARCHITECTURE,
        )
        report = InspectionReport(
            project=ProjectMetadata(name="demo", root="/demo"),
            inspector_results=(documentation, architecture),
            run_id="run-fixed",
            generated_at=FIXED_TIMESTAMP,
        )

        self.assertEqual(
            tuple(result.inspector for result in report.inspector_results),
            ("architecture", "z-documentation"),
        )

    def test_accepts_controlled_run_metadata(self) -> None:
        report = InspectionReport(
            project=ProjectMetadata(name="demo", root="/demo"),
            inspector_results=(),
            run_id="test-run-id",
            generated_at=FIXED_TIMESTAMP,
        )

        self.assertEqual(report.run_id, "test-run-id")
        self.assertEqual(report.generated_at, FIXED_TIMESTAMP)

    def test_rejects_invalid_run_metadata(self) -> None:
        project = ProjectMetadata(name="demo", root="/demo")

        with self.assertRaises(ValueError):
            InspectionReport(
                project=project,
                inspector_results=(),
                run_id=" ",
                generated_at=FIXED_TIMESTAMP,
            )

        for generated_at in ("not-a-timestamp", "2026-07-18T12:00:00"):
            with self.subTest(generated_at=generated_at):
                with self.assertRaises(ValueError):
                    InspectionReport(
                        project=project,
                        inspector_results=(),
                        run_id="run-fixed",
                        generated_at=generated_at,
                    )


if __name__ == "__main__":
    unittest.main()
