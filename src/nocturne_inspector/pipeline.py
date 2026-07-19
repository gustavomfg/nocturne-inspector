from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from nocturne_inspector.inspectors.registry import InspectorRegistry
from nocturne_inspector.models import InspectionReport, ProjectContext, ProjectMetadata
from nocturne_inspector.scanner import scan_project


def _new_run_id() -> str:
    """Create an operational identifier for one inspection execution."""
    return str(uuid4())


def _current_utc_timestamp() -> str:
    """Create an ISO 8601 timestamp for one inspection execution."""
    return datetime.now(UTC).isoformat()


class InspectionPipeline:
    """Execute registered inspectors sequentially and assemble their report."""

    def __init__(
        self,
        registry: InspectorRegistry,
        *,
        context_factory: Callable[[Path], ProjectContext] = scan_project,
        run_id_factory: Callable[[], str] = _new_run_id,
        generated_at_factory: Callable[[], str] = _current_utc_timestamp,
    ) -> None:
        """Create a pipeline with controllable operational metadata factories."""
        self._registry = registry
        self._context_factory = context_factory
        self._run_id_factory = run_id_factory
        self._generated_at_factory = generated_at_factory

    def run(self, project_root: Path) -> InspectionReport:
        """Inspect one workspace and return a complete in-memory report."""
        context = self._context_factory(project_root)
        root = context.root

        inspectors = self._registry.inspectors()
        results = []

        for inspector in inspectors:
            result = inspector.inspect(context)

            if result.inspector != inspector.name:
                raise ValueError(
                    f"Inspector {inspector.name!r} returned result name "
                    f"{result.inspector!r}."
                )

            if result.category is not inspector.category:
                raise ValueError(
                    f"Inspector {inspector.name!r} returned category "
                    f"{result.category.value!r}; expected "
                    f"{inspector.category.value!r}."
                )

            results.append(result)

        project_name = root.name or root.anchor

        return InspectionReport(
            project=ProjectMetadata(
                name=project_name,
                root=root.as_posix(),
                languages=context.languages,
                files_scanned=context.files_scanned,
            ),
            inspector_results=tuple(results),
            run_id=self._run_id_factory(),
            generated_at=self._generated_at_factory(),
        )
