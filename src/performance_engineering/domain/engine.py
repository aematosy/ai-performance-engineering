from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class PerformanceEngine(ABC):
    """Engine-independent contract for load generators."""

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def generate(
        self,
        model: dict[str, Any],
        profile: dict[str, Any],
        output: Path,
    ) -> Path:
        raise NotImplementedError

    @abstractmethod
    def validate(
        self,
        artifact: Path,
        context: dict[str, Any],
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def execute(
        self,
        artifact: Path,
        context: dict[str, Any],
    ) -> Path:
        raise NotImplementedError
