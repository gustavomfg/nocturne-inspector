from __future__ import annotations

import unittest
from pathlib import Path
from typing import cast

from nocturne_inspector.inspectors.base import Inspector
from nocturne_inspector.models import FindingCategory, InspectorResult


class IncompleteInspector(Inspector):
    """Inspector intentionally missing the required interface method."""

    name = "incomplete"
    category = FindingCategory.TESTING


class RecordingInspector(Inspector):
    """Minimal concrete inspector used to verify the base contract."""

    name = "recording"
    category = FindingCategory.TESTING

    def __init__(self) -> None:
        self.inspected_root: Path | None = None

    def inspect(self, project_root: Path) -> InspectorResult:
        self.inspected_root = project_root
        return InspectorResult(
            inspector=self.name,
            category=self.category,
            findings=(),
            duration_ms=0.0,
            files_examined=0,
        )


class InspectorContractTests(unittest.TestCase):
    def test_contract_cannot_be_instantiated_directly(self) -> None:
        with self.assertRaises(TypeError):
            cast(type[RecordingInspector], Inspector)()

    def test_subclass_must_implement_inspect(self) -> None:
        with self.assertRaises(TypeError):
            cast(type[RecordingInspector], IncompleteInspector)()

    def test_concrete_inspector_receives_path_and_returns_result(self) -> None:
        root = Path("/deterministic/project")
        inspector = RecordingInspector()

        result = inspector.inspect(root)

        self.assertEqual(inspector.inspected_root, root)
        self.assertEqual(result.inspector, inspector.name)
        self.assertIs(result.category, inspector.category)


if __name__ == "__main__":
    unittest.main()
