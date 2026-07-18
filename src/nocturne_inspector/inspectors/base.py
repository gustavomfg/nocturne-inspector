from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from nocturne_inspector.models import (
    FindingCategory,
    InspectorResult,
)


class Inspector(ABC):
    """Base contract implemented by every specialist inspector."""

    name: str
    category: FindingCategory

    @abstractmethod
    def inspect(self, project_root: Path) -> InspectorResult:
        """
        Inspect a project without modifying it.

        Args:
            project_root:
                Root directory of the project being inspected.

        Returns:
            Structured inspection result containing findings and metadata.
        """
        raise NotImplementedError