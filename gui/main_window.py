from __future__ import annotations
from typing import Optional

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QComboBox,
    QDoubleSpinBox,
    QSpinBox,
    QApplication,
)
from PySide6.QtCore import QTimer, Qt

from models.simulation import Simulation
from gui.tunnel_view import TunnelView


class MainWindow(QMainWindow):
    def __init__(self, sim: Optional[Simulation] = None):
        super().__init__()
        self.setWindowTitle("Tunnel evacuation simulation")
        self.sim = sim or Simulation()

        self.timer = QTimer(self)
        self.timer.setInterval(50)  # 50 ms ~ 20 steps per second
        self.timer.timeout.connect(self._on_timer)

        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)

        # tunnel view
        self.tunnel_view = TunnelView(self.sim)
        root_layout.addWidget(self.tunnel_view, stretch=3)

        # control panel
        controls = QWidget()
        controls_layout = QVBoxLayout(controls)
        root_layout.addWidget(controls, stretch=2)

        # buttons
        btn_row = QHBoxLayout()
        self.btn_start = QPushButton("Start")
        self.btn_pause = QPushButton("Pause")
        self.btn_step = QPushButton("Step")
        self.btn_reset = QPushButton("Reset")

        self.btn_start.clicked.connect(self.start_sim)
        self.btn_pause.clicked.connect(self.pause_sim)
        self.btn_step.clicked.connect(self.step_once)
        self.btn_reset.clicked.connect(self.reset_sim)

        for b in (self.btn_start, self.btn_pause, self.btn_step, self.btn_reset):
            btn_row.addWidget(b)
        controls_layout.addLayout(btn_row)

        # status
        self.lbl_status = QLabel("t = 0.0 s")
        self.lbl_stats = QLabel("")
        controls_layout.addWidget(self.lbl_status)
        controls_layout.addWidget(self.lbl_stats)

        tunnel_row = QHBoxLayout()
        controls_layout.addLayout(tunnel_row)

        self.sb_tunnel_length = QDoubleSpinBox()
        self.sb_tunnel_length.setPrefix("L=")
        self.sb_tunnel_length.setSuffix(" m")
        self.sb_tunnel_length.setDecimals(1)
        self.sb_tunnel_length.setRange(50.0, 5000.0)
        self.sb_tunnel_length.setValue(self.sim.cfg.length_m)

        self.sb_tunnel_width = QDoubleSpinBox()
        self.sb_tunnel_width.setPrefix("W=")
        self.sb_tunnel_width.setSuffix(" m")
        self.sb_tunnel_width.setDecimals(1)
        self.sb_tunnel_width.setRange(3.0, 50.0)
        self.sb_tunnel_width.setValue(self.sim.cfg.width_m)

        self.sb_cross_spacing = QDoubleSpinBox()
        self.sb_cross_spacing.setPrefix("Δx=")
        self.sb_cross_spacing.setSuffix(" m")
        self.sb_cross_spacing.setDecimals(1)
        self.sb_cross_spacing.setRange(10.0, 500.0)
        self.sb_cross_spacing.setValue(self.sim.cfg.cross_passage_spacing_m)

        self.sb_cross_num = QSpinBox()
        self.sb_cross_num.setPrefix("Ntransitions=")
        self.sb_cross_num.setRange(0, 20)
        self.sb_cross_num.setValue(self.sim.cfg.num_cross_passages)

        self.btn_apply_tunnel = QPushButton("Use tunnel")
        self.btn_apply_tunnel.clicked.connect(self.apply_tunnel_from_controls)

        for w in (
                self.sb_tunnel_length,
                self.sb_tunnel_width,
                self.sb_cross_spacing,
                self.sb_cross_num,
                self.btn_apply_tunnel,
        ):
            tunnel_row.addWidget(w)

        # events table (time line)
        self.events_table = QTableWidget(0, 3)
        self.events_table.setHorizontalHeaderLabels(["Time [s]", "Type", "Parameters"])
        self.events_table.horizontalHeader().setStretchLastSection(True)
        controls_layout.addWidget(self.events_table, stretch=1)

        # events adding
        add_row = QHBoxLayout()
        controls_layout.addLayout(add_row)

        self.cb_event_type = QComboBox()
        self.cb_event_type.addItems([
            "start_fire",
            "spawn_group",
            "start_voice_alarm",
            "set_air_velocity",
            "add_fan",
        ])

        self.sb_time = QDoubleSpinBox()
        self.sb_time.setPrefix("t=")
        self.sb_time.setSuffix(" s")
        self.sb_time.setDecimals(1)
        self.sb_time.setRange(0.0, 3600.0)

        self.sb_position = QDoubleSpinBox()
        self.sb_position.setPrefix("x=")
        self.sb_position.setSuffix(" m")
        self.sb_position.setDecimals(1)
        self.sb_position.setRange(0.0, self.sim.cfg.length_m)
        self.sb_position.setValue(self.sim.cfg.length_m / 2.0)

        self.sb_y = QDoubleSpinBox()
        self.sb_y.setPrefix("y=")
        self.sb_y.setSuffix(" m")
        self.sb_y.setDecimals(1)
        self.sb_y.setRange(0.0, self.sim.cfg.width_m)
        self.sb_y.setValue(self.sim.cfg.width_m / 2.0)

        self.sb_count = QSpinBox()
        self.sb_count.setPrefix("N=")
        self.sb_count.setRange(1, 500)
        self.sb_count.setValue(50)

        # radius of action (eg. fan)
        self.sb_radius = QDoubleSpinBox()
        self.sb_radius.setPrefix("R=")
        self.sb_radius.setSuffix(" m")
        self.sb_radius.setDecimals(1)
        self.sb_radius.setRange(1.0, 50.0)
        self.sb_radius.setValue(self.sim.cfg.fan_default_radius_m)

        # „p” – universal parameter:
        # - for the start_fire: max_emission_rate
        # - for the set_air_velocity: vx
        # - for the add_fan: removal_coeff_per_s
        self.sb_param = QDoubleSpinBox()
        self.sb_param.setDecimals(2)
        self.sb_param.setRange(0.0, 10.0)
        self.sb_param.setSingleStep(0.1)
        self.sb_param.setPrefix("p=")

        self.btn_add_event = QPushButton("Add event")
        self.btn_add_event.clicked.connect(self.add_event_from_controls)

        for w in (
                self.cb_event_type,
                self.sb_time,
                self.sb_position,
                self.sb_y,
                self.sb_count,
                self.sb_radius,
                self.sb_param,
                self.btn_add_event,
        ):
            add_row.addWidget(w)

        # default scenario – Laliki-inspired bus evacuation
        if not self.sim.persons:
            self.sim.load_laliki_bus_experiment()
        self.refresh_events_table()
        self.update_status_labels()

    # --- simulation management ----------------------------------------------

    def start_sim(self):
        self.sim.running = True
        if not self.timer.isActive():
            self.timer.start()

    def pause_sim(self):
        self.sim.running = False

    def step_once(self):
        self.sim.step()
        self.tunnel_view.update()
        self.update_status_labels()

    def reset_sim(self):
        self.sim.reset()
        self.sim.load_emilia_student_experiment()
        self.refresh_events_table()
        self.update_status_labels()
        self.tunnel_view.update()

    def _on_timer(self):
        if not self.sim.running:
            return
        self.sim.step()
        self.tunnel_view.update()
        self.update_status_labels()

    def update_status_labels(self):
        stats = self.sim.statistics()
        self.lbl_status.setText(f"t = {stats['time_s']:.1f} s")
        self.lbl_stats.setText(
            f"number of people: {stats['total']} | in safe zone: {stats['safe']} | "
            f"incapable: {stats['incapacitated']} | walking: {stats['walking']} | "
            f"waiting: {stats['waiting']}"
        )

    def apply_tunnel_from_controls(self):
        """
        Update tunnel parameters from GUI
        and reset the simulation to an empty scenario
        """
        self.sim.running = False

        length = self.sb_tunnel_length.value()
        width = self.sb_tunnel_width.value()
        spacing = self.sb_cross_spacing.value()
        num_passages = self.sb_cross_num.value()

        self.sim.apply_tunnel_params(
            length_m=length,
            width_m=width,
            spacing_m=spacing,
            num_passages=num_passages,
        )

        # range of event positions adjusted to the new tunnel length
        self.sb_position.setMaximum(self.sim.cfg.length_m)
        self.sb_position.setValue(self.sim.cfg.length_m / 2.0)

        self.refresh_events_table()
        self.update_status_labels()
        self.tunnel_view.update()

        self.sb_y.setMaximum(self.sim.cfg.width_m)
        self.sb_y.setValue(self.sim.cfg.width_m / 2.0)



    # --- events / time line --------------------------------------

    def refresh_events_table(self):
        self.events_table.setRowCount(0)
        events = list(self.sim._event_queue)
        events.sort(key=lambda e: e.time_s)
        for ev in events:
            row = self.events_table.rowCount()
            self.events_table.insertRow(row)
            self.events_table.setItem(row, 0, QTableWidgetItem(f"{ev.time_s:.1f}"))
            self.events_table.setItem(row, 1, QTableWidgetItem(ev.kind))
            self.events_table.setItem(row, 2, QTableWidgetItem(str(ev.params)))

    def add_event_from_controls(self):
        kind = self.cb_event_type.currentText()
        t = self.sb_time.value()
        x = self.sb_position.value()
        y = self.sb_y.value()
        n = self.sb_count.value()
        r = self.sb_radius.value()
        p = self.sb_param.value()

        if kind == "start_fire":
            self.sim.schedule_event(
                time_s=t,
                kind=kind,
                position_m=x,
                max_emission_rate=max(0.1, min(1.0, p if p > 0 else 0.5)),
            )
        elif kind == "spawn_group":
            self.sim.schedule_event(
                time_s=t,
                kind=kind,
                position_m=x,
                count=n,
            )
        elif kind == "start_voice_alarm":
            self.sim.schedule_event(time_s=t, kind=kind)
        elif kind == "set_air_velocity":
            self.sim.schedule_event(
                time_s=t,
                kind=kind,
                vx_mps=p if p != 0 else self.sim.cfg.default_air_velocity_x_mps,
                vy_mps=0.0,
            )

        elif kind == "add_fan":
            self.sim.schedule_event(
                time_s=t,
                kind=kind,
                x_m=x,
                y_m=y,
                radius_m=r,
                removal_coeff_per_s=(
                    p if p > 0 else self.sim.cfg.fan_default_removal_coeff_per_s
                ),
            )

        self.refresh_events_table()
