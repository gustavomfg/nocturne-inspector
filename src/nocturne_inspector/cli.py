from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO, cast

from nocturne_inspector import __version__
from nocturne_inspector.inspectors.registry import create_default_registry
from nocturne_inspector.pipeline import InspectionPipeline
from nocturne_inspector.report import report_to_json, save_json_report


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for the standalone Inspector."""
    parser = argparse.ArgumentParser(
        prog="nocturne-inspector",
        description="Nocturne Inspector — Engineering Intelligence Engine",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser(
        "inspect",
        help="inspect a project without modifying it",
    )
    inspect_parser.add_argument("path", type=Path, metavar="PATH")
    inspect_parser.add_argument(
        "--output",
        type=Path,
        help="write the report to an explicit destination",
    )
    inspect_parser.add_argument(
        "--format",
        choices=("json",),
        default="json",
        help="report format (default: json)",
    )
    return parser


def create_pipeline() -> InspectionPipeline:
    """Create the default execution pipeline without exposing specialists."""
    return InspectionPipeline(create_default_registry())


def main(
    argv: Sequence[str] | None = None,
    *,
    pipeline: InspectionPipeline | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Execute the CLI and return a process-compatible exit status."""
    parser = build_parser()
    arguments = parser.parse_args(argv)
    output_stream = stdout or sys.stdout
    error_stream = stderr or sys.stderr

    if arguments.command != "inspect":
        parser.error(f"unsupported command: {arguments.command}")

    project_path = cast(Path, arguments.path)
    output_path = cast(Path | None, arguments.output)
    active_pipeline = pipeline or create_pipeline()

    try:
        report = active_pipeline.run(project_path)

        if output_path is None:
            print(report_to_json(report), file=output_stream)
        else:
            save_json_report(report, output_path)
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=error_stream)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
