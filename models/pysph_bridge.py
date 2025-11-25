"""Integration hooks for optional PySPH velocity sampling."""

from __future__ import annotations

from typing import Optional

import numpy as np

try:  # optional
    import pysph  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    pysph = None

from .smoke import FlowProvider, SmokeField


class PySPHAdapter(FlowProvider):
    """
    Uses a user-provided PySPH solver object. The solver must expose a
    ``get_velocity_field(nx, ny, dx, dy)`` method returning (u, v)
    arrays compatible with SmokeField.
    """

    def __init__(self, solver: Optional[object] = None):
        self.solver = solver

    def velocity_field(
        self, field: SmokeField, time_s: float
    ) -> tuple[np.ndarray, np.ndarray]:
        if self.solver is None or pysph is None:
            return field.u, field.v
        try:
            return self.solver.get_velocity_field(field.nx, field.ny, field.dx_m, field.dy_m)
        except Exception:
            return field.u, field.v

