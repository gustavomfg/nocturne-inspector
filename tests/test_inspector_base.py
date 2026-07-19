from __future__ import annotations

import unittest
from pathlib import Path
from typing import cast

from nocturne_inspector.inspectors.base import Inspector
from nocturne_inspector.models import FindingCategory, InspectorResult, ProjectContext


class IncompleteInspector(Inspector):
    """Inspector intentionally missing the required interface method."""

    name = "incomplete"
    category = FindingCategory.TESTING


class RecordingInspector(Inspector):
    """Minimal concrete inspector used to verify the base contract."""

    name = "recording"
    category = FindingCategory.TESTING

    def __init__(self) -> None:
        self.context: ProjectContext | None = None

    def inspect(self, context: ProjectContext) -> InspectorResult:
        self.context = context
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

    def test_concrete_inspector_receives_context_and_returns_result(self) -> None:
        root = Path("/deterministic/project")
        context = ProjectContext(root=root, files=())
        inspector = RecordingInspector()

        result = inspector.inspect(context)

        self.assertIs(inspector.context, context)
        self.assertEqual(result.inspector, inspector.name)
        self.assertIs(result.category, inspector.category)


if __name__ == "__main__":
    unittest.main()
