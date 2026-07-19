# Inspection report contract

Nocturne Inspector exports one versioned JSON document. The canonical machine
contract is [`inspection-report.schema.json`](inspection-report.schema.json).
Schema version `0.3.0` belongs to the v0.1 foundation and may evolve only
through an explicit documented version change.

## Top-level fields

| Field | Meaning | Stability |
| --- | --- | --- |
| `schema_version` | Version of the JSON contract. | Stable for a schema release. |
| `inspector_version` | Version of the producing Inspector. | Changes with releases. |
| `run_id` | Identifier of one execution. | Operational and variable. |
| `generated_at` | Time at which the report was assembled. | Operational and variable. |
| `project` | Name, normalized root, detected languages, and scanner count. | Evidence metadata. |
| `inspector_results` | Result emitted by each registered specialist. | Deterministically ordered. |
| `summary` | Counts derived from all findings. | Deterministic. |
| `metrics` | Duration and file-examination totals. | Duration may vary. |

`project.files_scanned` is the number of regular, non-symbolic-link files in the
shared scanner inventory after documented directory exclusions are applied.
`project.languages` contains the sorted languages identified by the scanner's
explicit extension map. Specialist examinations are reported separately in
`metrics.total_files_examined` and each result's `files_examined` field; the
same inventory file may be examined by more than one specialist.

## Assessment coverage

The summary distinguishes a zero finding count from an assessment that did not
run. `assessed_categories` contains categories with at least one successful
inspector result. `unassessed_categories` contains every other report category,
including a category whose registered inspectors all failed. The two sorted
collections are disjoint and together contain every category in the contract.

`by_category` remains an exhaustive finding counter. A zero is evidence that no
finding was emitted only when the same category appears in
`assessed_categories`; otherwise the category was not successfully assessed.

## Inspector execution status

Every `inspector_results` entry contains a `status` and nullable `error`.
Successful results use `status: "success"` and `error: null`. When a specialist
encounters an expected operational filesystem error, the pipeline preserves
other results, records `status: "failed"`, emits no findings for that
specialist, and stores a sanitized error classification without paths or the
original exception message.

Context creation errors, unexpected inspector exceptions, and result identity
or category mismatches remain fatal because they indicate that a complete scan
cannot start or that an architectural contract was violated. Failed result
durations and file counts are `0` because an interrupted inspector does not
return trustworthy metrics.

## Findings and evidence

Findings live only in `inspector_results[].findings`; the report does not copy
them to a second top-level collection. Each finding contains a stable
`identifier`, its producing `rule_id`, category, kind, severity, confidence,
impact, evidence, and optional recommendation.

Every finding has at least one evidence item. A source location uses a
project-relative POSIX path whenever the inspector has project context. Line
and symbol fields are nullable when evidence applies to a file or expected path
as a whole.

Finding identifiers are SHA-256 values derived from the rule, category, and
ordered evidence locations. Wording changes do not change identity; a rule,
category, or location change does.

## Deterministic ordering

- inspector results are ordered by category and inspector name;
- findings are ordered by stable identifier;
- evidence is ordered by source location and description;
- warnings and detected languages are sorted;
- summary keys and coverage categories follow the enums declared by the schema;
- assessed and unassessed category lists are sorted.

Operational metadata (`run_id`, `generated_at`, and durations) is intentionally
excluded from semantic determinism.

## Compatibility

Consumers must read `schema_version` before interpreting a report. Additive or
breaking field changes require a schema version change and an update to both
the JSON Schema and this document. The Inspector version does not replace the
schema version: different Inspector releases may emit the same contract.

Schema `0.2.0` added the required `status` and `error` fields to every inspector
result. Schema `0.3.0` adds required `assessed_categories` and
`unassessed_categories` fields to the summary. Consumers of earlier schemas
must negotiate version `0.3.0` before interpreting assessment coverage.

Report serialization is independent from persistence. Analysis remains
read-only; a file is written only when the user explicitly supplies an output
destination.
