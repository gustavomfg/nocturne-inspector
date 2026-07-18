from __future__ import annotations

import unittest
from pathlib import Path

from nocturne_inspector.inspectors.base import Inspector
from nocturne_inspector.inspectors.documentation import DocumentationInspector
from nocturne_inspector.inspectors.registry import (
    InspectorRegistry,
    create_default_registry,
)
from nocturne_inspector.models import FindingCategory, InspectorResult


class StubInspector(Inspector):
    """Minimal inspector with configurable identity for registry tests."""

    def __init__(self, name: str, category: FindingCategory) -> None:
        self.name = name
        self.category = category

    def inspect(self, project_root: Path) -> InspectorResult:
        return InspectorResult(
            inspector=self.name,
            category=self.category,
            findings=(),
            duration_ms=0.0,
            files_examined=0,
        )


class InspectorRegistryTests(unittest.TestCase):
    def test_registers_and_discovers_inspectors_in_stable_order(self) -> None:
        registry = InspectorRegistry()
        second = StubInspector("zeta", FindingCategory.TESTING)
        first = StubInspector("alpha", FindingCategory.DOCUMENTATION)
        registry.register(second)
        registry.register(first)

        self.assertEqual(registry.inspectors(), (first, second))

    def test_rejects_empty_and_duplicate_names(self) -> None:
        registry = InspectorRegistry()
        registry.register(StubInspector("documentation", FindingCategory.DOCUMENTATION))

        with self.assertRaises(ValueError):
            registry.register(
                StubInspector("documentation", FindingCategory.DOCUMENTATION)
            )

        with self.assertRaises(ValueError):
            registry.register(StubInspector(" ", FindingCategory.TESTING))

        with self.assertRaises(ValueError):
            registry.register(StubInspector(" spaced ", FindingCategory.TESTING))

    def test_discovery_returns_an_immutable_snapshot(self) -> None:
        registry = InspectorRegistry()
        first = StubInspector("first", FindingCategory.TESTING)
        second = StubInspector("second", FindingCategory.TESTING)
        registry.register(first)

        snapshot = registry.inspectors()
        registry.register(second)

        self.assertEqual(snapshot, (first,))
        self.assertEqual(registry.inspectors(), (first, second))

    def test_default_registry_contains_documentation_inspector(self) -> None:
        inspectors = create_default_registry().inspectors()

        self.assertEqual(len(inspectors), 1)
        self.assertIsInstance(inspectors[0], DocumentationInspector)


if __name__ == "__main__":
    unittest.main()
