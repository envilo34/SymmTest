from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass(order=True)
class SimEvent:
    """Event in queue (discrete system)."""
    time_s: float
    priority: int
    kind: str = field(compare=False)
    params: Dict[str, Any] = field(default_factory=dict, compare=False)
