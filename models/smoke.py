from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Tuple, Protocol, Optional
import numpy as np

from config import EmiliaTunnelConfig, DEFAULT_CONFIG


class FlowProvider(Protocol):
    """Generic velocity provider (e.g. CFD / LBM / PySPH adapters)."""

    def velocity_field(
        self, field: "SmokeField", time_s: float
    ) -> tuple[np.ndarray, np.ndarray]:
        ...


@dataclass
class FireSource:
    """
    Fire – a source of smoke in 2D.
    Emission increases linearly up to max_emission_rate.
    """
    x_m: float
    y_m: float
    start_time_s: float
    growth_rate: float = 0.02
    max_emission_rate: float = 0.5
    active: bool = True

    def emission_rate(self, time_s: float) -> float:
        if not self.active or time_s < self.start_time_s:
            return 0.0
        dt = time_s - self.start_time_s
        return min(self.max_emission_rate, self.growth_rate * dt)


@dataclass
class VentilationFan:
    """
    Point smoke extraction fan (extractor).

    Two effects:
    - local smoke removal (sink) ~ removal_coeff_per_s,
    - local velocity field drawing smoke in (flow_strength_mps).
    """
    x_m: float
    y_m: float
    radius_m: float
    removal_coeff_per_s: float
    flow_strength_mps: float
    start_time_s: float = 0.0
    active: bool = True

    def is_active(self, time_s: float) -> bool:
        return self.active and (time_s >= self.start_time_s)

    def apply_sink(
        self,
        sink: np.ndarray,
        s: np.ndarray,
        field: "SmokeField",
        time_s: float,
    ) -> None:
        """Local "negative" term in the smoke equation."""
        if not self.is_active(time_s):
            return

        nx, ny = field.nx, field.ny
        dx, dy = field.dx_m, field.dy_m
        r = self.radius_m
        if r <= 0.0:
            return

        ix_min = max(0, int((self.x_m - r) / dx))
        ix_max = min(nx - 1, int((self.x_m + r) / dx))
        iy_min = max(0, int((self.y_m - r) / dy))
        iy_max = min(ny - 1, int((self.y_m + r) / dy))

        r2 = r * r

        for ix in range(ix_min, ix_max + 1):
            x = ix * dx
            for iy in range(iy_min, iy_max + 1):
                y = iy * dy
                dxr = x - self.x_m
                dyr = y - self.y_m
                d2 = dxr * dxr + dyr * dyr
                if d2 > r2:
                    continue
                # Gauss – 1 in mid, decreases to ~0 on border
                w = np.exp(-0.5 * d2 / r2)
                sink[ix, iy] += -self.removal_coeff_per_s * w * s[ix, iy]

    def apply_velocity(
        self,
        u: np.ndarray,
        v: np.ndarray,
        field: "SmokeField",
        time_s: float,
    ) -> None:
        """
        It adds a radial velocity field that draws air into the center of the fan.

        This creates a visible "stream" of smoke flowing toward the fan.
        """
        if not self.is_active(time_s):
            return

        nx, ny = field.nx, field.ny
        dx, dy = field.dx_m, field.dy_m
        r = self.radius_m
        if r <= 0.0:
            return

        ix_min = max(0, int((self.x_m - r) / dx))
        ix_max = min(nx - 1, int((self.x_m + r) / dx))
        iy_min = max(0, int((self.y_m - r) / dy))
        iy_max = min(ny - 1, int((self.y_m + r) / dy))

        r2 = r * r
        strength = self.flow_strength_mps

        for ix in range(ix_min, ix_max + 1):
            x = ix * dx
            for iy in range(iy_min, iy_max + 1):
                y = iy * dy
                dxr = self.x_m - x
                dyr = self.y_m - y
                d2 = dxr * dxr + dyr * dyr
                if d2 > r2 or d2 < 1e-6:
                    continue

                d = np.sqrt(d2)
                # dir to center
                ex = dxr / d
                ey = dyr / d

                # force decreases with distance (Gauss)
                w = np.exp(-0.5 * d2 / r2)
                u[ix, iy] += strength * w * ex
                v[ix, iy] += strength * w * ey


@dataclass
class SmokeField:
    """
    2D pole dymu w tunelu:

    - gęstość dymu: density[x, y],
    - 2D pole prędkości: u[x, y], v[x, y],
    - adwekcja density przez (u, v) metodą semi-Lagrangian,
    - dyfuzja + rozpad + źródła (pożary) + sink (wentylatory).
    """
    length_m: float
    width_m: float
    dx_m: float
    dy_m: float
    air_velocity_x_mps: float
    air_velocity_y_mps: float
    diffusivity: float
    decay: float
    extinction_per_density: float
    visibility_coefficient_m: float

    density: np.ndarray = field(init=False)
    u: np.ndarray = field(init=False)
    v: np.ndarray = field(init=False)

    fires: List[FireSource] = field(default_factory=list)
    fans: List[VentilationFan] = field(default_factory=list)

    use_high_order: bool = False
    external_flow_provider: Optional[FlowProvider] = field(default=None, repr=False)

    # „bazowy” przepływ (np. wymuszony podłużny)
    _base_vx: float = field(init=False)
    _base_vy: float = field(init=False)

    def __post_init__(self):
        self.nx = int(self.length_m / self.dx_m) + 1
        self.ny = int(self.width_m / self.dy_m) + 1
        self.density = np.zeros((self.nx, self.ny), dtype=np.float32)
        self.u = np.zeros((self.nx, self.ny), dtype=np.float32)
        self.v = np.zeros((self.nx, self.ny), dtype=np.float32)
        self._base_vx = self.air_velocity_x_mps
        self._base_vy = self.air_velocity_y_mps

    @classmethod
    def from_emilia(cls, cfg: EmiliaTunnelConfig = DEFAULT_CONFIG) -> "SmokeField":
        return cls(
            length_m=cfg.length_m,
            width_m=cfg.width_m,
            dx_m=cfg.dx_m,
            dy_m=cfg.dy_m,
            air_velocity_x_mps=cfg.default_air_velocity_x_mps,
            air_velocity_y_mps=cfg.default_air_velocity_y_mps,
            diffusivity=cfg.smoke_diffusivity,
            decay=cfg.smoke_decay,
            extinction_per_density=cfg.extinction_per_density,
            visibility_coefficient_m=cfg.visibility_coefficient_m,
            use_high_order=cfg.use_high_order_advection,
        )

    # --- zarządzanie źródłami / wentylatorami ----------------------------

    def add_fire(self, fire: FireSource) -> None:
        self.fires.append(fire)

    def add_fan(self, fan: VentilationFan) -> None:
        self.fans.append(fan)

    def clear_fans(self) -> None:
        self.fans.clear()

    def attach_external_flow_provider(self, provider: Optional[FlowProvider]) -> None:
        """Attach/detach CFD/LBM/PySPH provider for velocity fields."""
        self.external_flow_provider = provider

    def set_air_velocity(self, vx: float, vy: float, cfg: EmiliaTunnelConfig = DEFAULT_CONFIG):
        vmax = cfg.max_air_velocity_mps
        vx_clamped = max(-vmax, min(vmax, vx))
        vy_clamped = max(-vmax, min(vmax, vy))
        self._base_vx = vx_clamped
        self._base_vy = vy_clamped

    # --- budowa pola prędkości -------------------------------------------

    def _build_velocity_field(self, time_s: float) -> None:
        """
        Budujemy (u, v) z:
        - bazowego przepływu tunelowego,
        - wkładu wentylatorów (zasysanie).
        """
        self.u.fill(self._base_vx)
        self.v.fill(self._base_vy)

        for fan in self.fans:
            fan.apply_velocity(self.u, self.v, self, time_s)

        if self.external_flow_provider is not None:
            try:
                ext_u, ext_v = self.external_flow_provider.velocity_field(self, time_s)
                if ext_u.shape == self.u.shape and ext_v.shape == self.v.shape:
                    # blend external solver with base field
                    self.u = 0.5 * (self.u + ext_u)
                    self.v = 0.5 * (self.v + ext_v)
            except Exception:
                # Do not crash GUI if optional solver fails
                pass

    # --- źródła dymu -----------------------------------------------------

    def _build_source_term(self, time_s: float) -> np.ndarray:
        src = np.zeros_like(self.density)
        for fire in self.fires:
            rate = fire.emission_rate(time_s)
            if rate <= 0.0:
                continue
            ix = int(min(max(fire.x_m / self.dx_m, 0), self.nx - 1))
            iy = int(min(max(fire.y_m / self.dy_m, 0), self.ny - 1))
            src[ix, iy] += rate
        return src

    # --- semi-Lagrangian adwekcja ----------------------------------------

    def _sample_density(self, s_prev: np.ndarray, x_m: float, y_m: float) -> float:
        """
        Bilinearna interpolacja gęstości w punkcie (x_m, y_m).
        """
        x_m = max(0.0, min(self.length_m, x_m))
        y_m = max(0.0, min(self.width_m, y_m))

        fx = x_m / self.dx_m
        fy = y_m / self.dy_m
        ix0 = int(np.floor(fx))
        iy0 = int(np.floor(fy))

        ix1 = min(ix0 + 1, self.nx - 1)
        iy1 = min(iy0 + 1, self.ny - 1)

        sx = fx - ix0
        sy = fy - iy0

        ix0 = max(0, min(self.nx - 1, ix0))
        iy0 = max(0, min(self.ny - 1, iy0))

        v00 = s_prev[ix0, iy0]
        v10 = s_prev[ix1, iy0]
        v01 = s_prev[ix0, iy1]
        v11 = s_prev[ix1, iy1]

        v0 = (1 - sx) * v00 + sx * v10
        v1 = (1 - sx) * v01 + sx * v11
        return (1 - sy) * v0 + sy * v1

    def _advect_density(self, dt_s: float) -> np.ndarray:
        """
        Semi-Lagrangian: dla każdej komórki patrzymy „wstecz” wzdłuż prędkości,
        skąd powietrze przyszło, i próbkujemy tam starą gęstość.
        """
        s_prev = self.density
        s_new = np.zeros_like(s_prev)

        for ix in range(self.nx):
            x = ix * self.dx_m
            for iy in range(self.ny):
                y = iy * self.dy_m
                vx = self.u[ix, iy]
                vy = self.v[ix, iy]

                x_prev = x - vx * dt_s
                y_prev = y - vy * dt_s

                s_new[ix, iy] = self._sample_density(s_prev, x_prev, y_prev)

        return s_new

    def _advect_density_high_order(self, dt_s: float) -> np.ndarray:
        """
        BFECC (MacCormack-like) advection – reduced numerical diffusion.
        It is still stable for interactive use but preserves gradients better
        for dense plumes near the bus.
        """
        s_prev = self.density

        # forward step
        forward = self._advect_density(dt_s)

        # backward step (reverse velocity)
        u_back = -self.u
        v_back = -self.v

        s_back = np.zeros_like(s_prev)
        for ix in range(self.nx):
            x = ix * self.dx_m
            for iy in range(self.ny):
                y = iy * self.dy_m
                vx = u_back[ix, iy]
                vy = v_back[ix, iy]
                x_prev = x - vx * dt_s
                y_prev = y - vy * dt_s
                s_back[ix, iy] = self._sample_density(forward, x_prev, y_prev)

        corrected = s_prev + 0.5 * (s_prev - s_back)

        # final advection using corrected field
        s_final = np.zeros_like(s_prev)
        for ix in range(self.nx):
            x = ix * self.dx_m
            for iy in range(self.ny):
                y = iy * self.dy_m
                vx = self.u[ix, iy]
                vy = self.v[ix, iy]
                x_prev = x - vx * dt_s
                y_prev = y - vy * dt_s
                s_final[ix, iy] = self._sample_density(corrected, x_prev, y_prev)

        return s_final

    # --- główny krok dymu -----------------------------------------------

    def step(self, dt_s: float, time_s: float) -> None:
        """
        1) Zbuduj pole prędkości (bazowy + wentylatory).
        2) Advectuj density (semi-Lagrangian).
        3) Dyfuzja + rozpad + źródła + sink (wentylatory).
        """
        # 1) prędkości
        self._build_velocity_field(time_s)

        # 2) adwekcja
        if getattr(self, "use_high_order", False):
            self.density = self._advect_density_high_order(dt_s)
        else:
            self.density = self._advect_density(dt_s)

        # 3) dyfuzja + reszta
        s = self.density
        D = self.diffusivity
        dx = self.dx_m
        dy = self.dy_m

        # dyfuzja (Laplasjan)
        lap = np.zeros_like(s)
        lap[1:-1, 1:-1] = (
            (s[2:, 1:-1] - 2 * s[1:-1, 1:-1] + s[:-2, 1:-1]) / (dx * dx)
            + (s[1:-1, 2:] - 2 * s[1:-1, 1:-1] + s[1:-1, :-2]) / (dy * dy)
        )
        lap[0, :] = lap[1, :]
        lap[-1, :] = lap[-2, :]
        lap[:, 0] = lap[:, 1]
        lap[:, -1] = lap[:, -2]

        src = self._build_source_term(time_s)

        sink = np.zeros_like(s)
        for fan in self.fans:
            fan.apply_sink(sink, s, self, time_s)

        dsdt = D * lap - self.decay * s + src + sink
        self.density = np.clip(s + dt_s * dsdt, 0.0, 1.0)

    # --- pomiary ---------------------------------------------------------

    def index_from_world(self, x_m: float, y_m: float) -> Tuple[int, int]:
        ix = int(min(max(x_m / self.dx_m, 0), self.nx - 1))
        iy = int(min(max(y_m / self.dy_m, 0), self.ny - 1))
        return ix, iy

    def smoke_at(self, x_m: float, y_m: float) -> float:
        ix, iy = self.index_from_world(x_m, y_m)
        return float(self.density[ix, iy])

    def extinction_at(self, x_m: float, y_m: float) -> float:
        dens = self.smoke_at(x_m, y_m)
        return self.extinction_per_density * dens

    def visibility_at(self, x_m: float, y_m: float) -> float:
        K = self.extinction_at(x_m, y_m)
        if K <= 1e-6:
            return 999.0
        return self.visibility_coefficient_m / K
