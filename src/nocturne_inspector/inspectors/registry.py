from __future__ import annotations

from nocturne_inspector.inspectors.base import Inspector
from nocturne_inspector.inspectors.documentation import DocumentationInspector


class InspectorRegistry:
    """Register and discover independent inspectors deterministically."""

    def __init__(self) -> None:
        self._inspectors_by_name: dict[str, Inspector] = {}

    def register(self, inspector: Inspector) -> None:
        """Register one inspector, rejecting empty or duplicate names."""
        name = inspector.name.strip()

        if not name:
            raise ValueError("Inspector name cannot be empty.")

        if name in self._inspectors_by_name:
            raise ValueError(f"Inspector already registered: {name}")

        self._inspectors_by_name[name] = inspector

    def inspectors(self) -> tuple[Inspector, ...]:
        """Return a stable snapshot ordered by category and inspector name."""
        return tuple(
            sorted(
                self._inspectors_by_name.values(),
                key=lambda inspector: (inspector.category.value, inspector.name),
            )
        )


def create_default_registry() -> InspectorRegistry:
    """Create the registry used by the standalone Inspector application."""
    registry = InspectorRegistry()
    registry.register(DocumentationInspector())
    return registry
