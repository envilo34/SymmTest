from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class PersonState(str, Enum):
    WAITING = "waiting"
    WALKING = "walking"
    SAFE = "safe"
    INCAPACITATED = "incapacitated"


@dataclass
class Person:
    """
    Agent w 2D – position (x,y), velocity (vx,vy), physiological condition.
    """
    id: int
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0

    radius_m: float = 0.25
    mass_kg: float = 80.0

    desired_speed_clear: float = 1.3  # m/s without smoke
    state: PersonState = PersonState.WAITING

    # reaction time / info about danger
    reaction_time_s: float = 0.0
    hazard_known_time_s: Optional[float] = None

    # evacuation target (exit)
    target_x: float = 0.0
    target_y: float = 0.0

    # physiology – integrated FED
    fed: float = 0.0
    incapacitated_threshold: float = 1.0

    def pos_tuple(self) -> tuple[float, float]:
        return (self.x, self.y)

    def vel_tuple(self) -> tuple[float, float]:
        return (self.vx, self.vy)

    def notify_of_hazard(self, current_time_s: float) -> None:
        if self.hazard_known_time_s is None:
            self.hazard_known_time_s = current_time_s

    def should_start_walking(self, current_time_s: float) -> bool:
        if self.state != PersonState.WAITING:
            return False
        if self.hazard_known_time_s is None:
            return False
        return (current_time_s - self.hazard_known_time_s) >= self.reaction_time_s

    def mark_safe(self) -> None:
        self.state = PersonState.SAFE

    def mark_incapacitated(self) -> None:
        self.state = PersonState.INCAPACITATED
        self.vx = 0.0
        self.vy = 0.0
