"""Optional CFD/LBM style flow providers used by SmokeField."""

from __future__ import annotations

import math

import numpy as np

from .smoke import FlowProvider, SmokeField


class SimpleLBMModule(FlowProvider):
    """
    Lightweight placeholder for a lattice-Boltzmann-like solver.

    It does not attempt to be a full CFD model; instead it synthesizes
    a recirculation field that resembles the expected structure around
    a warm vehicle plume. The API matches FlowProvider so it can be
    swapped for a real solver without changes in SmokeField.
    """

    def __init__(self, swirl_strength: float = 0.5, bias: float = 0.2):
        self.swirl_strength = swirl_strength
        self.bias = bias

    def velocity_field(
        self, field: SmokeField, time_s: float
    ) -> tuple[np.ndarray, np.ndarray]:
        u = np.zeros_like(field.u)
        v = np.zeros_like(field.v)

        cx = field.length_m / 2.0
        cy = field.width_m / 2.0
        strength = self.swirl_strength * (1.0 + 0.1 * math.sin(time_s))

        for ix in range(field.nx):
            x = ix * field.dx_m
            for iy in range(field.ny):
                y = iy * field.dy_m
                dx = x - cx
                dy = y - cy
                r2 = dx * dx + dy * dy + 1e-6
                u[ix, iy] = -strength * dy / r2 + self.bias
                v[ix, iy] = strength * dx / r2
        return u, v


class ExternalCFDHook(FlowProvider):
    """
    Adapter around user-provided callbacks – enables plugging a real
    CFD/LBM solver at runtime without modifying the simulation loop.
    """

    def __init__(self, callback):
        self.callback = callback

    def velocity_field(
        self, field: SmokeField, time_s: float
    ) -> tuple[np.ndarray, np.ndarray]:
        return self.callback(field, time_s)

