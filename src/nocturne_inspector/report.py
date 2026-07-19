from __future__ import annotations

import json
from pathlib import Path
from tempfile import NamedTemporaryFile

from nocturne_inspector.models import InspectionReport, JsonValue


def report_to_dict(report: InspectionReport) -> dict[str, JsonValue]:
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
        allow_nan=False,
        ensure_ascii=False,
        indent=indent,
        sort_keys=False,
    )


def save_json_report(
    report: InspectionReport,
    destination: Path,
    *,
    indent: int = 2,
    overwrite: bool = False,
) -> Path:
    """
    Save an inspection report to an explicit destination atomically.

    The destination parent must already exist. Existing files are preserved
    unless overwrite is explicitly enabled, and symbolic-link destinations
    are always rejected. Saving is independent from project inspection; this
    function must only be called in response to an explicit output request.
    """
    expanded_destination = destination.expanduser()
    resolved_destination = expanded_destination.resolve()
    parent = resolved_destination.parent

    if not parent.exists():
        raise FileNotFoundError(
            f"Report destination directory does not exist: {parent}"
        )

    if not parent.is_dir():
        raise NotADirectoryError(
            f"Report destination parent is not a directory: {parent}"
        )

    if expanded_destination.is_symlink():
        raise ValueError("Report destination cannot be a symbolic link.")

    if resolved_destination.exists():
        if resolved_destination.is_dir():
            raise IsADirectoryError(
                f"Report destination is a directory: {resolved_destination}"
            )

        if not overwrite:
            raise FileExistsError(
                f"Report destination already exists: {resolved_destination}"
            )

    content = report_to_json(report, indent=indent)
    temporary_destination: Path | None = None

    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=parent,
            prefix=f".{resolved_destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_file.write(content)
            temporary_file.flush()
            temporary_destination = Path(temporary_file.name)

        if overwrite:
            temporary_destination.replace(resolved_destination)
        else:
            resolved_destination.hardlink_to(temporary_destination)
            temporary_destination.unlink()
            temporary_destination = None
    finally:
        if temporary_destination is not None:
            temporary_destination.unlink(missing_ok=True)

    return resolved_destination
