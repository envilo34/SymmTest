from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional
import heapq
import math
import random

from config import EmiliaTunnelConfig, DEFAULT_CONFIG
from .tunnel import TunnelGeometry, Obstacle
from .agents import Person, PersonState
from .smoke import SmokeField, FireSource, VentilationFan
from .events import SimEvent


@dataclass
class Simulation:
    cfg: EmiliaTunnelConfig = field(default_factory=lambda: DEFAULT_CONFIG)
    geometry: TunnelGeometry = field(init=False)
    smoke: SmokeField = field(init=False)
    persons: List[Person] = field(default_factory=list)

    current_time_s: float = 0.0
    _event_queue: List[SimEvent] = field(default_factory=list, init=False)
    _next_event_priority: int = 0
    _next_person_id: int = 1

    voice_alarm_active: bool = False
    running: bool = False
    fire_position: Optional[tuple[float, float]] = None

    def __post_init__(self):
        self.geometry = TunnelGeometry.from_emilia(self.cfg)
        self.smoke = SmokeField.from_emilia(self.cfg)

    # --- events management  -----------------------------------------

    def schedule_event(self, time_s: float, kind: str, **params) -> None:
        self._next_event_priority += 1
        ev = SimEvent(
            time_s=time_s,
            priority=self._next_event_priority,
            kind=kind,
            params=params,
        )
        heapq.heappush(self._event_queue, ev)

    def _process_due_events(self) -> None:
        while self._event_queue and self._event_queue[0].time_s <= self.current_time_s:
            ev = heapq.heappop(self._event_queue)
            self._handle_event(ev)

    def _handle_event(self, ev: SimEvent) -> None:
        kind = ev.kind
        p = ev.params
        if kind == "start_fire":
            x = float(p.get("position_m", self.cfg.length_m / 2.0))
            y = float(p.get("y_m", self.cfg.width_m / 2.0))
            growth = float(p.get("growth_rate", 0.02))
            max_rate = float(p.get("max_emission_rate", 0.5))
            fire = FireSource(
                x_m=x,
                y_m=y,
                start_time_s=ev.time_s,
                growth_rate=growth,
                max_emission_rate=max_rate,
            )
            self.smoke.add_fire(fire)
            self.fire_position = (x, y)
        elif kind == "spawn_group":
            x = float(p.get("position_m", self.cfg.length_m / 2.0))
            count = int(p.get("count", 10))
            spread_x = float(p.get("spread_m", 10.0))
            self._spawn_group(x, count, spread_x)
        elif kind == "start_voice_alarm":
            self.voice_alarm_active = True
            for person in self.persons:
                person.notify_of_hazard(self.current_time_s)
        elif kind == "set_air_velocity":
            vx = float(p.get("vx_mps", self.cfg.default_air_velocity_x_mps))
            vy = float(p.get("vy_mps", self.cfg.default_air_velocity_y_mps))
            self.smoke.set_air_velocity(vx, vy, self.cfg)
        elif kind == "add_obstacle":
            x = float(p.get("x_m", self.cfg.length_m / 2.0))
            length = float(p.get("length_m", 10.0))
            width = float(p.get("width_m", 3.0))
            y_center = float(p.get("y_center_m", self.cfg.width_m / 2.0))
            obs = Obstacle(
                x_min=max(0.0, x - length / 2.0),
                x_max=min(self.cfg.length_m, x + length / 2.0),
                y_min=max(0.0, y_center - width / 2.0),
                y_max=min(self.cfg.width_m, y_center + width / 2.0),
            )
            self.geometry.obstacles.append(obs)
            self.geometry._build_wall_segments()
        elif kind == "set_air_velocity":
            vx = float(p.get("vx_mps", self.cfg.default_air_velocity_x_mps))
            vy = float(p.get("vy_mps", self.cfg.default_air_velocity_y_mps))
            self.smoke.set_air_velocity(vx, vy, self.cfg)
        elif kind == "add_fan":
            x = float(p.get("x_m", self.cfg.length_m / 2.0))
            y = float(p.get("y_m", self.cfg.width_m - 0.5))  # eg. „ceil”
            radius = float(p.get("radius_m", self.cfg.fan_default_radius_m))
            coeff = float(
                p.get("removal_coeff_per_s", self.cfg.fan_default_removal_coeff_per_s)
            )
            coeff = max(0.0, min(coeff, self.cfg.fan_max_removal_coeff_per_s))

            fan = VentilationFan(
                x_m=x,
                y_m=y,
                radius_m=radius,
                removal_coeff_per_s=coeff,
                flow_strength_mps=self.cfg.fan_default_flow_mps,
                start_time_s=ev.time_s,
            )
            self.smoke.add_fan(fan)

    def clear_events(self) -> None:
        self._event_queue.clear()

    # --- creating pedestrians ----------------------------------------------

    def _spawn_group(self, x_m: float, count: int, spread_x_m: float) -> None:
        for _ in range(count):
            x = x_m + random.uniform(-spread_x_m / 2.0, spread_x_m / 2.0)
            x = max(0.0, min(self.cfg.length_m, x))

            # we draw y in the corredor, but not right next to the wall
            y = random.uniform(0.5, self.cfg.width_m - 0.5)

            rt = random.uniform(self.cfg.reaction_time_min, self.cfg.reaction_time_max)

            target_x, target_y = self.geometry.nearest_exit_point(
                (x, y), fire_pos=self.fire_position
            )

            person = Person(
                id=self._next_person_id,
                x=x,
                y=y,
                radius_m=self.cfg.pedestrian_radius_m,
                mass_kg=self.cfg.pedestrian_mass_kg,
                desired_speed_clear=self.cfg.pedestrian_desired_speed_clear,
                reaction_time_s=rt,
                target_x=target_x,
                target_y=target_y,
                incapacitated_threshold=self.cfg.fed_incapacitated_threshold,
            )
            self._next_person_id += 1
            self.persons.append(person)

    # --- reset / sim step ------------------------------------------

    def reset(self) -> None:
        self.current_time_s = 0.0
        self.persons.clear()
        self.smoke = SmokeField.from_emilia(self.cfg)
        self._event_queue.clear()
        self._next_event_priority = 0
        self._next_person_id = 1
        self.voice_alarm_active = False
        self.fire_position = None
        self.geometry = TunnelGeometry.from_emilia(self.cfg)

    def step(self) -> None:
        dt = self.cfg.dt_s
        self.current_time_s += dt

        # 1) smoke
        self.smoke.step(dt, self.current_time_s)

        # 2) events in queue
        self._process_due_events()

        # 3) pedestrians
        self._update_persons(dt)

    # --- move model details / behavior -----------------------------

    def _update_persons(self, dt: float) -> None:
        cfg = self.cfg
        n = len(self.persons)
        if n == 0:
            return

        # first the "local state": smoke, visibility, FED, start of traffic
        positions = []
        velocities = []
        visibilities = []
        active_indices = []  # people who actually move

        for idx, p in enumerate(self.persons):
            if p.state in (PersonState.SAFE, PersonState.INCAPACITATED):
                positions.append((p.x, p.y))
                velocities.append((p.vx, p.vy))
                visibilities.append(999.0)
                continue

            # threat information – either a global alert or local smoke
            if self.voice_alarm_active:
                p.notify_of_hazard(self.current_time_s)
            else:
                local_smoke = self.smoke.smoke_at(p.x, p.y)
                if local_smoke > 0.05:
                    p.notify_of_hazard(self.current_time_s)

            # time to escape?
            if p.should_start_walking(self.current_time_s):
                p.state = PersonState.WALKING

            # physiology: FED ~ smoke density * coefficient
            local_smoke = self.smoke.smoke_at(p.x, p.y)
            p.fed += cfg.fed_smoke_coeff_per_s * local_smoke * dt
            if p.fed >= p.incapacitated_threshold:
                p.mark_incapacitated()

            positions.append((p.x, p.y))
            velocities.append((p.vx, p.vy))

            vis = self.smoke.visibility_at(p.x, p.y)
            visibilities.append(vis)

            if p.state == PersonState.WALKING:
                active_indices.append(idx)

        if not active_indices:
            return

        # prepare structures for social forces
        forces_x = [0.0] * n
        forces_y = [0.0] * n

        # destination vectors (to exit)
        desired_dirs = []
        for idx, p in enumerate(self.persons):
            tx, ty = p.target_x, p.target_y
            dx = tx - p.x
            dy = ty - p.y
            l = math.hypot(dx, dy)
            if l > 1e-6:
                desired_dirs.append((dx / l, dy / l))
            else:
                desired_dirs.append((0.0, 0.0))

        # --- ped-ped interactions (social force) ----------------------
        A = cfg.sf_A_social
        B = cfg.sf_B_social
        neighbor_R = cfg.neighbor_radius_m

        # vector to herding – average direction of neighbors
        herd_sum = [(0.0, 0.0) for _ in range(n)]
        herd_count = [0 for _ in range(n)]

        for i in range(n):
            pi_x, pi_y = positions[i]
            for j in range(i + 1, n):
                pj_x, pj_y = positions[j]

                dx = pi_x - pj_x
                dy = pi_y - pj_y
                dist = math.hypot(dx, dy)
                if dist < 1e-6:
                    continue

                # repulsion
                n_ij_x = dx / dist
                n_ij_y = dy / dist
                # body radius
                ri = self.persons[i].radius_m
                rj = self.persons[j].radius_m
                r_ij = ri + rj

                force_mag = A * math.exp((r_ij - dist) / B)
                fx = force_mag * n_ij_x
                fy = force_mag * n_ij_y

                forces_x[i] += fx
                forces_y[i] += fy
                forces_x[j] -= fx
                forces_y[j] -= fy

                # neighbors for herding
                if dist <= neighbor_R:
                    vj = self.persons[j].vel_tuple()
                    herd_sum[i] = (herd_sum[i][0] + vj[0], herd_sum[i][1] + vj[1])
                    herd_count[i] += 1

                    vi = self.persons[i].vel_tuple()
                    herd_sum[j] = (herd_sum[j][0] + vi[0], herd_sum[j][1] + vi[1])
                    herd_count[j] += 1

        # --- ped-wall interaction / obstacle -----------------------

        Aw = cfg.sf_A_wall
        Bw = cfg.sf_B_wall

        for idx, p in enumerate(self.persons):
            if p.state != PersonState.WALKING:
                continue
            seg, dist, n_vec, _t_vec = self.geometry.nearest_wall((p.x, p.y))
            if seg is None:
                continue

            # ped radius
            ri = p.radius_m
            force_mag = Aw * math.exp((ri - dist) / Bw)
            fx = force_mag * n_vec[0]
            fy = force_mag * n_vec[1]
            forces_x[idx] += fx
            forces_y[idx] += fy

        # --- „social behavior”: herding + walking near wall ----

        for idx in active_indices:
            p = self.persons[idx]
            vis = visibilities[idx]

            # base dir to exit
            e_tx, e_ty = desired_dirs[idx]

            # herding
            if herd_count[idx] > 0:
                hx, hy = herd_sum[idx]
                l = math.hypot(hx, hy)
                if l > 1e-6:
                    hx /= l
                    hy /= l
                else:
                    hx, hy = 0.0, 0.0
            else:
                hx, hy = 0.0, 0.0

            if vis >= cfg.herding_visibility_threshold_m:
                w_herd = 0.0
            else:
                # the lower the visibility, the stronger the herding
                ratio = max(0.0, min(1.0, (cfg.herding_visibility_threshold_m - vis) /
                                   cfg.herding_visibility_threshold_m))
                w_herd = cfg.herding_max_weight * ratio

            # wall-follow – in low visibility people stick to the walls
            _, _dist, _n, t_vec = self.geometry.nearest_wall((p.x, p.y))
            tx, ty = t_vec
            if vis >= cfg.wall_follow_visibility_threshold_m:
                w_wall = 0.0
            else:
                ratio = max(0.0, min(1.0, (cfg.wall_follow_visibility_threshold_m - vis) /
                                   cfg.wall_follow_visibility_threshold_m))
                w_wall = cfg.wall_follow_max_weight * ratio

            # combination: target + crowd + wall
            ex = (1.0 - w_herd - w_wall) * e_tx + w_herd * hx + w_wall * tx
            ey = (1.0 - w_herd - w_wall) * e_ty + w_herd * hy + w_wall * ty
            l = math.hypot(ex, ey)
            if l > 1e-6:
                ex /= l
                ey /= l
            else:
                ex, ey = e_tx, e_ty

            # --- speed as a function of visibility (Fridolf / Jin) ----------
            v_free = p.desired_speed_clear
            V = visibilities[idx]
            v_target = self._speed_from_visibility(V, v_free)

            # driving force – Helbing & Molnár
            dvx = v_target * ex - p.vx
            dvy = v_target * ey - p.vy
            F_drive_x = p.mass_kg * dvx / cfg.relaxation_time_s
            F_drive_y = p.mass_kg * dvy / cfg.relaxation_time_s

            forces_x[idx] += F_drive_x
            forces_y[idx] += F_drive_y

        # --- traffic integration --------------------------------------------

        for idx in active_indices:
            p = self.persons[idx]
            Fx = forces_x[idx]
            Fy = forces_y[idx]

            ax = Fx / p.mass_kg
            ay = Fy / p.mass_kg

            p.vx += ax * dt
            p.vy += ay * dt

            # maximum speed limit (e.g. 2x target speed)
            v = math.hypot(p.vx, p.vy)
            vmax = 2.0 * p.desired_speed_clear
            if v > vmax and v > 1e-6:
                p.vx = p.vx * vmax / v
                p.vy = p.vy * vmax / v

            p.x += p.vx * dt
            p.y += p.vy * dt

            # restricted to tunnel
            p.x = max(0.0, min(self.cfg.length_m, p.x))
            p.y = max(0.0, min(self.cfg.width_m, p.y))

            # checking if he reached the exit
            if self.geometry.is_at_exit((p.x, p.y), tol_m=1.0):
                p.mark_safe()

    def _speed_from_visibility(self, V: float, v_free: float) -> float:
        """
        Speed dependence on visibility – based on recommendations
        Fridolf/Ronchi (przegląd prac Jin, Frantzich, Nilsson itd.).
        """
        cfg = self.cfg
        if V >= cfg.vis_full_speed_threshold_m:
            return v_free

        # scaling to base 1 m/s
        base_v = 1.0
        base_min_v = cfg.vis_min_speed_mps

        # reduction: 0.34 m/s per metre of fall below 3 m, with a lower limit of 0.2 m/s
        dv = cfg.vis_slowing_slope * (cfg.vis_full_speed_threshold_m - V)
        v = max(base_min_v, base_v - dv)

        # rescale to v_free
        scale = v_free / base_v
        return max(base_min_v * scale, v * scale)

    # --- stats ------------------------------------------------------

    def statistics(self) -> dict:
        total = len(self.persons)
        safe = sum(1 for p in self.persons if p.state == PersonState.SAFE)
        inc = sum(1 for p in self.persons if p.state == PersonState.INCAPACITATED)
        walking = sum(1 for p in self.persons if p.state == PersonState.WALKING)
        waiting = sum(1 for p in self.persons if p.state == PersonState.WAITING)
        return {
            "time_s": self.current_time_s,
            "total": total,
            "safe": safe,
            "incapacitated": inc,
            "walking": walking,
            "waiting": waiting,
        }

    # --- example scenario for Emilia ------------------------------

    def load_emilia_student_experiment(self) -> None:
        """
        A simplified scenario inspired by the tunnel experiments
        (approx. 60 people + vehicle fire). Details can be adjusted.
        """
        self.reset()
        bus_x = self.cfg.length_m / 2.0
        bus_y = self.cfg.width_m / 2.0

        self.schedule_event(
            time_s=0.0,
            kind="spawn_group",
            position_m=bus_x,
            count=60,
            spread_m=8.0,
        )
        self.schedule_event(
            time_s=60.0,
            kind="start_fire",
            position_m=bus_x,
            y_m=bus_y,
            growth_rate=0.03,
            max_emission_rate=0.8,
        )
        self.schedule_event(
            time_s=90.0,
            kind="start_voice_alarm",
        )
        self.schedule_event(
            time_s=20.0,
            kind="add_obstacle",
            x_m=bus_x,
            length_m=12.0,
            width_m=3.0,
            y_center_m=bus_y,
        )
        self.schedule_event(
            time_s=120.0,
            kind="set_air_velocity",
            vx_mps=3.0,
            vy_mps=0.0,
        )

    def apply_tunnel_params(
        self,
        length_m: float,
        width_m: float,
        spacing_m: float,
        num_passages: int,
    ) -> None:
        """
        Updates tunnel parameters (custom model) and resets the simulation
        """
        self.cfg.length_m = float(length_m)
        self.cfg.width_m = float(width_m)
        self.cfg.cross_passage_spacing_m = float(spacing_m)
        self.cfg.num_cross_passages = int(num_passages)

        # reset() will build new geometry + smoke based on the updated cfg
        self.reset()

