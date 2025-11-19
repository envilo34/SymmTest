from __future__ import annotations
from typing import Optional

from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtCore import Qt, QRectF, QPointF

from models.simulation import Simulation
from models.agents import PersonState


class TunnelView(QWidget):
    """
    2D tunnel view:
    - smoke as 2D field in tunnel rectangle,
    - obstacles, people, fire
    - scroll zoom,
    - panning right mouse button.
    """

    def __init__(self, simulation: Simulation, parent: Optional[Widget] = None):
        super().__init__(parent)
        self.sim = simulation

        # pview params
        self._zoom = 1.0
        self._min_zoom = 0.3
        self._max_zoom = 5.0
        self._pan_x = 0.0    # in piexls
        self._pan_y = 0.0

        self._panning = False
        self._last_mouse_pos: Optional[QPointF] = None

        self.setMinimumHeight(250)
        self.setMinimumWidth(800)
        self.setMouseTracking(True)

    # ------------------------------------------------------------------ #
    # DRAWING
    # ------------------------------------------------------------------ #

    def paintEvent(self, event):
        painter = QPainter(self)
        rect = self.rect()

        # background
        painter.fillRect(rect, QColor(15, 15, 20))

        if not self.sim:
            return

        margin = 40
        base_rect = QRectF(
            margin,
            margin,
            rect.width() - 2 * margin,
            rect.height() - 2 * margin,
        )

        # we scale and move tunnel_rect relative to base_rect
        center = base_rect.center()
        scaled_w = base_rect.width() * self._zoom
        scaled_h = base_rect.height() * self._zoom

        tunnel_rect = QRectF(
            center.x() - scaled_w / 2 + self._pan_x,
            center.y() - scaled_h / 2 + self._pan_y,
            scaled_w,
            scaled_h,
        )

        geom = self.sim.geometry
        L = geom.length_m
        W = geom.width_m

        # tunnel – background for smoke
        painter.setPen(QPen(QColor(90, 90, 90)))
        painter.setBrush(QColor(40, 40, 40))
        painter.drawRect(tunnel_rect)

        # --- SMOKE 2D -------------------------------------------------------
        if self.sim.smoke is not None:
            sf = self.sim.smoke
            nx = sf.nx
            ny = sf.ny

            for ix in range(nx - 1):
                for iy in range(ny - 1):
                    dens = float(sf.density[ix, iy])
                    if dens <= 0.0:
                        continue

                    alpha = int(max(20, min(255, dens * 255)))

                    # cell boundaries in world (m)
                    x0_world = ix * sf.dx_m
                    x1_world = (ix + 1) * sf.dx_m
                    y0_world = iy * sf.dy_m
                    y1_world = (iy + 1) * sf.dy_m

                    x0_view = self._world_to_view_x(x0_world, tunnel_rect, L)
                    x1_view = self._world_to_view_x(x1_world, tunnel_rect, L)
                    y0_view = self._world_to_view_y(y0_world, tunnel_rect, W)
                    y1_view = self._world_to_view_y(y1_world, tunnel_rect, W)

                    left = min(x0_view, x1_view)
                    right = max(x0_view, x1_view)
                    top = min(y0_view, y1_view)
                    bottom = max(y0_view, y1_view)

                    cell_rect = QRectF(left, top, right - left, bottom - top)

                    painter.setBrush(QColor(160, 160, 160, alpha))
                    painter.setPen(Qt.NoPen)
                    painter.drawRect(cell_rect)

        # tunnel outline
        painter.setPen(QPen(QColor(180, 180, 180)))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(tunnel_rect)

        # evacuation passages
        painter.setBrush(QColor(0, 200, 0))
        painter.setPen(Qt.NoPen)
        for x in geom.cross_passage_positions_m:
            vx = self._world_to_view_x(x, tunnel_rect, L)
            painter.drawRect(QRectF(vx - 4, tunnel_rect.bottom(), 8, 10))
            painter.drawRect(QRectF(vx - 4, tunnel_rect.top() - 10, 8, 10))

        # obstacles
        painter.setBrush(QColor(120, 80, 40))
        painter.setPen(Qt.NoPen)
        for obs in geom.obstacles:
            x1 = self._world_to_view_x(obs.x_min, tunnel_rect, L)
            x2 = self._world_to_view_x(obs.x_max, tunnel_rect, L)
            y1 = self._world_to_view_y(obs.y_min, tunnel_rect, W)
            y2 = self._world_to_view_y(obs.y_max, tunnel_rect, W)

            left = min(x1, x2)
            right = max(x1, x2)
            top = min(y1, y2)
            bottom = max(y1, y2)

            painter.drawRect(QRectF(left, top, right - left, bottom - top))

        # fire
        if self.sim.fire_position is not None:
            fx, fy = self.sim.fire_position
            vx = self._world_to_view_x(fx, tunnel_rect, L)
            vy = self._world_to_view_y(fy, tunnel_rect, W)
            painter.setBrush(QColor(255, 80, 0))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QRectF(vx - 8, vy - 8, 16, 16))

        # people
        for p in self.sim.persons:
            vx = self._world_to_view_x(p.x, tunnel_rect, L)
            vy = self._world_to_view_y(p.y, tunnel_rect, W)

            if p.state == PersonState.SAFE:
                color = QColor(0, 200, 0)
            elif p.state == PersonState.INCAPACITATED:
                color = QColor(200, 0, 0)
            elif p.state == PersonState.WALKING:
                color = QColor(255, 255, 0)
            else:
                color = QColor(0, 150, 255)

            painter.setBrush(color)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QRectF(vx - 4, vy - 4, 8, 8))

        # fans
        if hasattr(self.sim.smoke, "fans"):
            painter.setBrush(QColor(0, 150, 255))
            painter.setPen(Qt.NoPen)
            for fan in self.sim.smoke.fans:
                fx = self._world_to_view_x(fan.x_m, tunnel_rect, L)
                fy = self._world_to_view_y(fan.y_m, tunnel_rect, W)
                painter.drawRect(QRectF(fx - 5, fy - 5, 10, 10))


        painter.end()

    # ------------------------------------------------------------------ #
    # ZOOM / PAN
    # ------------------------------------------------------------------ #

    def wheelEvent(self, event):
        # scroll – zoom
        delta = event.angleDelta().y()
        if delta == 0:
            return

        # simple zoom: +10% / -10%
        factor = 1.1 if delta > 0 else 0.9
        new_zoom = self._zoom * factor
        new_zoom = max(self._min_zoom, min(self._max_zoom, new_zoom))

        self._zoom = new_zoom
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            self._panning = True
            self._last_mouse_pos = event.position()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._panning and self._last_mouse_pos is not None:
            pos = event.position()
            dx = pos.x() - self._last_mouse_pos.x()
            dy = pos.y() - self._last_mouse_pos.y()
            self._pan_x += dx
            self._pan_y += dy
            self._last_mouse_pos = pos
            self.update()
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.RightButton:
            self._panning = False
            self._last_mouse_pos = None
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        # double mid click / right – view reset
        if event.button() in (Qt.MiddleButton, Qt.RightButton):
            self._zoom = 1.0
            self._pan_x = 0.0
            self._pan_y = 0.0
            self.update()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    # ------------------------------------------------------------------ #
    # MAPPING WORLD <-> SCREEN
    # ------------------------------------------------------------------ #

    @staticmethod
    def _world_to_view_x(x_m: float, tunnel_rect: QRectF, L: float) -> float:
        return tunnel_rect.left() + (x_m / L) * tunnel_rect.width()

    @staticmethod
    def _world_to_view_y(y_m: float, tunnel_rect: QRectF, W: float) -> float:
        # y=0 przy dolnej ścianie, y=W przy górnej – odwrotne niż na ekranie
        return tunnel_rect.bottom() - (y_m / W) * tunnel_rect.height()
