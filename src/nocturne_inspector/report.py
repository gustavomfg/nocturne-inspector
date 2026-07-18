from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nocturne_inspector.models import InspectionReport


def report_to_dict(report: InspectionReport) -> dict[str, Any]:
    """Convert an inspection report into primitive values."""
    return report.to_dict()


def report_to_json(
    report: InspectionReport,
    *,
    indent: int = 2,
) -> str:
    """Serialize an inspection report as formatted JSON."""
    if indent < 0:
        raise ValueError("JSON indentation cannot be negative.")

    return json.dumps(
        report_to_dict(report),
        ensure_ascii=False,
        indent=indent,
        sort_keys=False,
    )


def save_json_report(
    report: InspectionReport,
    destination: Path,
    *,
    indent: int = 2,
) -> Path:
    """
    Save an inspection report using an atomic file replacement.

    The report is first written to a temporary sibling file. The destination
    is replaced only after the complete JSON has been written successfully.
    """
    resolved_destination = destination.expanduser().resolve()
    resolved_destination.parent.mkdir(parents=True, exist_ok=True)

    temporary_destination = resolved_destination.with_name(
        f".{resolved_destination.name}.tmp"
    )

    content = report_to_json(report, indent=indent)

    try:
        temporary_destination.write_text(
            content,
            encoding="utf-8",
        )
        temporary_destination.replace(resolved_destination)
    finally:
        temporary_destination.unlink(missing_ok=True)

    return resolved_destination