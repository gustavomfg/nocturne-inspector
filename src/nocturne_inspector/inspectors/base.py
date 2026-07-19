from __future__ import annotations

from abc import ABC, abstractmethod

from nocturne_inspector.models import (
    FindingCategory,
    InspectorResult,
    ProjectContext,
)


class Inspector(ABC):
    """Base contract implemented by every specialist inspector."""

    name: str
    category: FindingCategory

    @abstractmethod
    def inspect(self, context: ProjectContext) -> InspectorResult:
        """
        Inspect a project without modifying it.

        Args:
            context:
                Immutable project inventory shared by every inspector.

        Returns:
            Structured inspection result containing findings and metadata.
        """
        raise NotImplementedError
