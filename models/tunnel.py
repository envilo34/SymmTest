from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
import math

from config import EmiliaTunnelConfig, DEFAULT_CONFIG


@dataclass
class Obstacle:
    """A rectangular obstacle (e.g. a vehicle) in a tunnel."""
    x_min: float
    y_min: float
    x_max: float
    y_max: float


@dataclass
class WallSegment:
    """A section of wall/obstacle used in social force."""
    x1: float
    y1: float
    x2: float
    y2: float


@dataclass
class TunnelGeometry:
    length_m: float
    width_m: float
    cross_passage_positions_m: List[float] = field(default_factory=list)
    obstacles: List[Obstacle] = field(default_factory=list)

    wall_segments: List[WallSegment] = field(default_factory=list, init=False)

    @classmethod
    def from_emilia(cls, cfg: EmiliaTunnelConfig = DEFAULT_CONFIG) -> "TunnelGeometry":
        positions: List[float] = []
        spacing = cfg.cross_passage_spacing_m
        pos = spacing
        while pos < cfg.length_m and len(positions) < cfg.num_cross_passages:
            positions.append(pos)
            pos += spacing
        geom = cls(
            length_m=cfg.length_m,
            width_m=cfg.width_m,
            cross_passage_positions_m=positions,
        )
        geom._build_wall_segments()
        return geom

    # --- walls and exits -------------------------------------------------

    def _build_wall_segments(self) -> None:
        """External walls + obstacle edges."""
        segs: List[WallSegment] = []

        L = self.length_m
        W = self.width_m

        # tunnel envelope
        segs.append(WallSegment(0.0, 0.0, L, 0.0))   # dół
        segs.append(WallSegment(0.0, W, L, W))       # góra
        segs.append(WallSegment(0.0, 0.0, 0.0, W))   # portal 0
        segs.append(WallSegment(L, 0.0, L, W))       # portal L

        # obstacles as rects
        for obs in self.obstacles:
            segs.append(WallSegment(obs.x_min, obs.y_min, obs.x_max, obs.y_min))
            segs.append(WallSegment(obs.x_max, obs.y_min, obs.x_max, obs.y_max))
            segs.append(WallSegment(obs.x_max, obs.y_max, obs.x_min, obs.y_max))
            segs.append(WallSegment(obs.x_min, obs.y_max, obs.x_min, obs.y_min))

        self.wall_segments = segs

    def exit_points(self) -> List[Tuple[float, float]]:
        """
        “Exit” points – tunnel portals + emergency passages on the walls.
        In 2D we use these points as targets for agents.
        """
        exits: List[Tuple[float, float]] = []
        mid_y = self.width_m / 2.0

        # portals
        exits.append((0.0, mid_y))
        exits.append((self.length_m, mid_y))

        # emergency exits – doors in the lower and upper walls
        for x in self.cross_passage_positions_m:
            exits.append((x, 0.3))                # dół
            exits.append((x, self.width_m - 0.3)) # góra

        return exits

    def nearest_exit_point(
        self,
        pos: Tuple[float, float],
        fire_pos: Optional[Tuple[float, float]] = None,
    ) -> Tuple[float, float]:
        """
        The nearest exit, but if we know the location of the fire,
        we prefer exits "on the side opposite the fire".
        """
        px, py = pos
        exits = self.exit_points()

        if fire_pos is not None:
            fx, _ = fire_pos
            direction_from_fire = 1.0 if px >= fx else -1.0
            filtered = []
            for ex_x, ex_y in exits:
                dir_exit = 1.0 if ex_x >= fx else -1.0
                if dir_exit == direction_from_fire:
                    filtered.append((ex_x, ex_y))
            if filtered:
                exits = filtered

        return min(exits, key=lambda e: math.hypot(e[0] - px, e[1] - py))

    def is_at_exit(self, pos: Tuple[float, float], tol_m: float = 1.0) -> bool:
        px, py = pos
        for ex_x, ex_y in self.exit_points():
            if math.hypot(px - ex_x, py - ex_y) <= tol_m:
                return True
        return False

    # --- auxiliary to social force --------------------------------------

    def nearest_wall(
        self, pos: Tuple[float, float]
    ) -> Tuple[Optional[WallSegment], float, Tuple[float, float], Tuple[float, float]]:
        """
        Returns: (segment, distance, normal vector n, tangent vector t)
        """
        px, py = pos
        best_seg: Optional[WallSegment] = None
        best_dist = float("inf")
        best_n = (0.0, 0.0)
        best_t = (0.0, 0.0)

        for seg in self.wall_segments:
            d, n, t = self._point_segment_distance(px, py, seg)
            if d < best_dist:
                best_dist = d
                best_seg = seg
                best_n = n
                best_t = t
        return best_seg, best_dist, best_n, best_t

    @staticmethod
    def _point_segment_distance(
        px: float, py: float, seg: WallSegment
    ) -> Tuple[float, Tuple[float, float], Tuple[float, float]]:
        """Distance of a point from a segment + normal + tangent direction."""
        x1, y1, x2, y2 = seg.x1, seg.y1, seg.x2, seg.y2
        vx, vy = x2 - x1, y2 - y1
        wx, wy = px - x1, py - y1

        seg_len2 = vx * vx + vy * vy
        if seg_len2 <= 1e-9:
            t = 0.0
        else:
            t = (wx * vx + wy * vy) / seg_len2
            t = max(0.0, min(1.0, t))

        proj_x = x1 + t * vx
        proj_y = y1 + t * vy

        dx = px - proj_x
        dy = py - proj_y
        dist = math.hypot(dx, dy)

        if dist > 1e-9:
            nx, ny = dx / dist, dy / dist
        else:
            l = math.hypot(vx, vy)
            if l > 1e-9:
                nx, ny = -vy / l, vx / l
            else:
                nx, ny = 0.0, 0.0

        tl = math.hypot(vx, vy)
        if tl > 1e-9:
            tx, ty = vx / tl, vy / tl
        else:
            tx, ty = 0.0, 0.0

        return dist, (nx, ny), (tx, ty)
