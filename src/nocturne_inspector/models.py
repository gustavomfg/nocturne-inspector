from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from uuid import uuid4

from nocturne_inspector import __version__

REPORT_SCHEMA_VERSION = "0.3.0"
INSPECTOR_VERSION = __version__

_SEMANTIC_VERSION_PATTERN = re.compile(
    r"^(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)

type JsonValue = (
    str | int | float | bool | None | list[JsonValue] | dict[str, JsonValue]
)


def _utc_now_isoformat() -> str:
    """Return the current UTC instant in an ISO 8601 representation."""
    return datetime.now(UTC).isoformat()


def _to_json_compatible(value: object) -> JsonValue:
    """Recursively convert domain collections into JSON-compatible values."""
    if isinstance(value, dict):
        converted: dict[str, JsonValue] = {}

        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("JSON object keys must be strings.")

            converted[key] = _to_json_compatible(item)

        return converted

    if isinstance(value, (list, tuple)):
        return [_to_json_compatible(item) for item in value]

    if value is None or isinstance(value, str | int | float | bool):
        return value

    raise TypeError(f"Unsupported JSON value: {type(value).__name__}")


def _validate_semantic_version(value: str, *, field_name: str) -> None:
    """Validate a semantic version used by the exported report contract."""
    if _SEMANTIC_VERSION_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be a valid semantic version.")


class Severity(StrEnum):
    """Impact level assigned to a finding."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ConfidenceLevel(StrEnum):
    """Human-readable representation of evidence confidence."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class FindingCategory(StrEnum):
    """Engineering domain responsible for a finding."""

    ARCHITECTURE = "architecture"
    SECURITY = "security"
    PERFORMANCE = "performance"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    ACCESSIBILITY = "accessibility"
    DEPENDENCIES = "dependencies"
    RELEASE = "release"
    DEVELOPER_EXPERIENCE = "developer_experience"


class FindingKind(StrEnum):
    """Nature of a finding produced by an inspector."""

    CONFIRMED_ISSUE = "confirmed_issue"
    DOCUMENTATION_INCONSISTENCY = "documentation_inconsistency"
    TECHNICAL_DEBT = "technical_debt"
    RISK = "risk"
    IMPROVEMENT_OPPORTUNITY = "improvement_opportunity"
    NEEDS_INVESTIGATION = "needs_investigation"
    POSITIVE_FINDING = "positive_finding"


class InspectorStatus(StrEnum):
    """Execution outcome recorded for one specialist inspector."""

    SUCCESS = "success"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class SourceLocation:
    """Location from which a piece of evidence was collected."""

    path: str
    line_start: int | None = None
    line_end: int | None = None
    symbol: str | None = None

    def __post_init__(self) -> None:
        if not self.path.strip():
            raise ValueError("Source path cannot be empty.")

        if self.line_start is not None and self.line_start < 1:
            raise ValueError("line_start must be greater than zero.")

        if self.line_end is not None and self.line_end < 1:
            raise ValueError("line_end must be greater than zero.")

        if (
            self.line_start is not None
            and self.line_end is not None
            and self.line_end < self.line_start
        ):
            raise ValueError("line_end cannot be lower than line_start.")

    @classmethod
    def from_path(
        cls,
        path: Path,
        *,
        project_root: Path | None = None,
        line_start: int | None = None,
        line_end: int | None = None,
        symbol: str | None = None,
    ) -> SourceLocation:
        """
        Create a source location from a filesystem path.

        When project_root is provided, the stored path is relative to the
        project whenever possible. This avoids leaking unnecessary absolute
        paths into exported reports.
        """
        resolved_path = path.expanduser().resolve()

        if project_root is not None:
            resolved_root = project_root.expanduser().resolve()

            try:
                normalized_path = resolved_path.relative_to(resolved_root)
            except ValueError:
                normalized_path = resolved_path
        else:
            normalized_path = resolved_path

        return cls(
            path=normalized_path.as_posix(),
            line_start=line_start,
            line_end=line_end,
            symbol=symbol,
        )


@dataclass(frozen=True, slots=True)
class Evidence:
    """Concrete information supporting a finding."""

    description: str
    source: SourceLocation
    excerpt: str | None = None

    def __post_init__(self) -> None:
        if not self.description.strip():
            raise ValueError("Evidence description cannot be empty.")


@dataclass(frozen=True, slots=True)
class Recommendation:
    """Suggested response to a finding."""

    summary: str
    rationale: str
    effort: str | None = None
    breaking_change_risk: bool = False

    def __post_init__(self) -> None:
        if not self.summary.strip():
            raise ValueError("Recommendation summary cannot be empty.")

        if not self.rationale.strip():
            raise ValueError("Recommendation rationale cannot be empty.")


@dataclass(frozen=True, slots=True)
class Confidence:
    """Confidence assigned to a finding based on its available evidence."""

    score: float
    level: ConfidenceLevel
    rationale: str

    def __post_init__(self) -> None:
        if not 0.0 <= self.score <= 1.0:
            raise ValueError("Confidence score must be between 0.0 and 1.0.")

        if not self.rationale.strip():
            raise ValueError("Confidence rationale cannot be empty.")

        expected_level = self.level_for_score(self.score)

        if self.level is not expected_level:
            raise ValueError(
                "Confidence level does not match its numeric score. "
                f"Expected {expected_level.value!r} for score {self.score}."
            )

    @staticmethod
    def level_for_score(score: float) -> ConfidenceLevel:
        """Convert a normalized confidence score into a readable level."""
        if not 0.0 <= score <= 1.0:
            raise ValueError("Confidence score must be between 0.0 and 1.0.")

        if score >= 0.8:
            return ConfidenceLevel.HIGH

        if score >= 0.5:
            return ConfidenceLevel.MEDIUM

        return ConfidenceLevel.LOW

    @classmethod
    def from_score(
        cls,
        score: float,
        rationale: str,
    ) -> Confidence:
        """Create a confidence value and infer its level automatically."""
        return cls(
            score=score,
            level=cls.level_for_score(score),
            rationale=rationale,
        )


@dataclass(frozen=True, slots=True)
class Finding:
    """Evidence-based conclusion produced by an inspector."""

    rule_id: str
    title: str
    description: str
    category: FindingCategory
    kind: FindingKind
    severity: Severity
    confidence: Confidence
    evidence: tuple[Evidence, ...]
    impact: str
    recommendation: Recommendation | None = None
    identifier: str = field(init=False)

    def __post_init__(self) -> None:
        if not self.rule_id.strip():
            raise ValueError("Finding rule_id cannot be empty.")

        if not self.title.strip():
            raise ValueError("Finding title cannot be empty.")

        if not self.description.strip():
            raise ValueError("Finding description cannot be empty.")

        if not self.impact.strip():
            raise ValueError("Finding impact cannot be empty.")

        if not self.evidence:
            raise ValueError("A finding must contain at least one piece of evidence.")

        ordered_evidence = tuple(
            sorted(
                self.evidence,
                key=lambda item: (
                    item.source.path,
                    item.source.line_start or 0,
                    item.source.line_end or 0,
                    item.source.symbol or "",
                    item.description,
                    item.excerpt or "",
                ),
            )
        )
        object.__setattr__(self, "evidence", ordered_evidence)
        object.__setattr__(self, "identifier", self._stable_identifier())

    def _stable_identifier(self) -> str:
        """Build an identifier from the rule, category, and evidence locations."""
        identity = {
            "category": self.category.value,
            "locations": [
                {
                    "line_end": item.source.line_end,
                    "line_start": item.source.line_start,
                    "path": item.source.path,
                    "symbol": item.source.symbol,
                }
                for item in self.evidence
            ],
            "rule_id": self.rule_id,
        }
        canonical_identity = json.dumps(
            identity,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        digest = hashlib.sha256(canonical_identity.encode("utf-8")).hexdigest()
        return f"finding:{digest}"


@dataclass(frozen=True, slots=True)
class InspectorResult:
    """Structured output produced by one specialist inspector."""

    inspector: str
    category: FindingCategory
    findings: tuple[Finding, ...]
    duration_ms: float
    files_examined: int
    warnings: tuple[str, ...] = ()
    status: InspectorStatus = InspectorStatus.SUCCESS
    error: str | None = None

    def __post_init__(self) -> None:
        if not self.inspector.strip():
            raise ValueError("Inspector name cannot be empty.")

        if not math.isfinite(self.duration_ms):
            raise ValueError("Inspector duration must be finite.")

        if self.duration_ms < 0:
            raise ValueError("Inspector duration cannot be negative.")

        if self.files_examined < 0:
            raise ValueError("files_examined cannot be negative.")

        if self.status is InspectorStatus.SUCCESS and self.error is not None:
            raise ValueError("Successful inspector results cannot contain an error.")

        if self.status is InspectorStatus.FAILED:
            if self.error is None or not self.error.strip():
                raise ValueError("Failed inspector results must contain an error.")

            if self.findings:
                raise ValueError("Failed inspector results cannot contain findings.")

        invalid_categories = tuple(
            finding.category
            for finding in self.findings
            if finding.category is not self.category
        )

        if invalid_categories:
            raise ValueError(
                "Every finding in an InspectorResult must use the result category."
            )

        object.__setattr__(
            self,
            "findings",
            tuple(sorted(self.findings, key=lambda finding: finding.identifier)),
        )
        object.__setattr__(self, "warnings", tuple(sorted(self.warnings)))


@dataclass(frozen=True, slots=True)
class ProjectContext:
    """Immutable filesystem context shared by every project inspector."""

    root: Path
    files: tuple[Path, ...]
    languages: tuple[str, ...] = ()
    excluded_directories: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.root.is_absolute():
            raise ValueError("Project context root must be an absolute path.")

        for path in self.files:
            if path.is_absolute() or not path.parts or ".." in path.parts:
                raise ValueError(
                    "Project context files must be project-relative paths."
                )

        normalized_files = tuple(
            sorted(set(self.files), key=lambda path: path.as_posix())
        )
        normalized_languages = tuple(sorted(set(self.languages)))
        normalized_exclusions = tuple(sorted(set(self.excluded_directories)))

        if any(
            not name.strip() or Path(name).name != name
            for name in normalized_exclusions
        ):
            raise ValueError("Exclusions must be non-empty directory names.")

        object.__setattr__(self, "files", normalized_files)
        object.__setattr__(self, "languages", normalized_languages)
        object.__setattr__(self, "excluded_directories", normalized_exclusions)

    @property
    def files_scanned(self) -> int:
        """Return the number of regular files in the deterministic inventory."""
        return len(self.files)


@dataclass(frozen=True, slots=True)
class ProjectMetadata:
    """Basic information about the inspected project."""

    name: str
    root: str
    languages: tuple[str, ...] = ()
    files_scanned: int = 0

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Project name cannot be empty.")

        if not self.root.strip():
            raise ValueError("Project root cannot be empty.")

        if self.files_scanned < 0:
            raise ValueError("files_scanned cannot be negative.")

        object.__setattr__(self, "languages", tuple(sorted(set(self.languages))))


@dataclass(frozen=True, slots=True)
class InspectionSummary:
    """Aggregated metrics for an inspection report."""

    total_findings: int
    by_severity: dict[str, int]
    by_category: dict[str, int]
    by_kind: dict[str, int]
    assessed_categories: tuple[str, ...]
    unassessed_categories: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.total_findings < 0:
            raise ValueError("total_findings cannot be negative.")

        for collection_name, collection in (
            ("by_severity", self.by_severity),
            ("by_category", self.by_category),
            ("by_kind", self.by_kind),
        ):
            if any(value < 0 for value in collection.values()):
                raise ValueError(f"{collection_name} cannot contain negative values.")

        known_categories = {category.value for category in FindingCategory}
        assessed = set(self.assessed_categories)
        unassessed = set(self.unassessed_categories)

        if assessed & unassessed:
            raise ValueError("Assessed and unassessed categories cannot overlap.")

        if assessed | unassessed != known_categories:
            raise ValueError(
                "Assessed and unassessed categories must partition all categories."
            )

        object.__setattr__(self, "assessed_categories", tuple(sorted(assessed)))
        object.__setattr__(self, "unassessed_categories", tuple(sorted(unassessed)))


@dataclass(frozen=True, slots=True)
class InspectionReport:
    """Complete, versioned report generated by Nocturne Inspector."""

    project: ProjectMetadata
    inspector_results: tuple[InspectorResult, ...]
    schema_version: str = REPORT_SCHEMA_VERSION
    inspector_version: str = INSPECTOR_VERSION
    run_id: str = field(default_factory=lambda: str(uuid4()))
    generated_at: str = field(default_factory=_utc_now_isoformat)

    def __post_init__(self) -> None:
        if not self.schema_version.strip():
            raise ValueError("schema_version cannot be empty.")

        _validate_semantic_version(
            self.schema_version,
            field_name="schema_version",
        )

        if not self.inspector_version.strip():
            raise ValueError("inspector_version cannot be empty.")

        _validate_semantic_version(
            self.inspector_version,
            field_name="inspector_version",
        )

        if not self.run_id.strip():
            raise ValueError("run_id cannot be empty.")

        if not self.generated_at.strip():
            raise ValueError("generated_at cannot be empty.")

        try:
            generated_at = datetime.fromisoformat(self.generated_at)
        except ValueError as error:
            raise ValueError("generated_at must be a valid ISO 8601 value.") from error

        if generated_at.tzinfo is None:
            raise ValueError("generated_at must include timezone information.")

        object.__setattr__(
            self,
            "inspector_results",
            tuple(
                sorted(
                    self.inspector_results,
                    key=lambda result: (result.category.value, result.inspector),
                )
            ),
        )

    @property
    def findings(self) -> tuple[Finding, ...]:
        """Return all findings produced by every inspector."""
        return tuple(
            finding for result in self.inspector_results for finding in result.findings
        )

    @property
    def total_duration_ms(self) -> float:
        """Return the combined execution time of every inspector."""
        return sum(result.duration_ms for result in self.inspector_results)

    @property
    def total_files_examined(self) -> int:
        """Return the total number of inspector file examinations."""
        return sum(result.files_examined for result in self.inspector_results)

    @property
    def summary(self) -> InspectionSummary:
        """Build aggregated report counts."""
        severity_counts = {severity.value: 0 for severity in Severity}

        category_counts = {category.value: 0 for category in FindingCategory}

        kind_counts = {kind.value: 0 for kind in FindingKind}

        for finding in self.findings:
            severity_counts[finding.severity.value] += 1
            category_counts[finding.category.value] += 1
            kind_counts[finding.kind.value] += 1

        assessed_categories = {
            result.category.value
            for result in self.inspector_results
            if result.status is InspectorStatus.SUCCESS
        }
        all_categories = {category.value for category in FindingCategory}

        return InspectionSummary(
            total_findings=len(self.findings),
            by_severity=severity_counts,
            by_category=category_counts,
            by_kind=kind_counts,
            assessed_categories=tuple(assessed_categories),
            unassessed_categories=tuple(all_categories - assessed_categories),
        )

    def to_dict(self) -> dict[str, JsonValue]:
        """Convert the report to JSON-compatible primitive values."""
        data = _to_json_compatible(asdict(self))

        if not isinstance(data, dict):
            raise TypeError("Serialized inspection report must be a JSON object.")

        data["summary"] = _to_json_compatible(asdict(self.summary))
        data["metrics"] = {
            "total_duration_ms": self.total_duration_ms,
            "total_files_examined": self.total_files_examined,
        }

        return data
