from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True)
class AlignedUnit:
    start: float
    end: float
    label: str
    tier: str = "phones"

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


@dataclass(frozen=True)
class VisemeFrame:
    time: float
    end: float
    unit: str
    viseme: str
    spriteIndex: int
    jawOpen: float
    mouthScaleX: float = 1.0
    mouthScaleY: float = 1.0
    confidence: float = 1.0

    def to_json(self) -> dict[str, Any]:
        return asdict(self)
