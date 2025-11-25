import argparse
import sys
from PySide6.QtWidgets import QApplication

from config import DEFAULT_CONFIG
from models.simulation import Simulation
from gui.main_window import MainWindow


def parse_args():
    parser = argparse.ArgumentParser(description="Tunnel / bus evacuation GUI")
    parser.add_argument(
        "--scenario",
        choices=["bus", "tunnel"],
        default="bus",
        help="Initial scenario (bus=Laliki inspired, tunnel=student demo)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    app = QApplication(sys.argv)

    sim = Simulation(cfg=DEFAULT_CONFIG)
    if args.scenario == "tunnel":
        sim.load_emilia_student_experiment()
    else:
        sim.load_laliki_bus_experiment()

    window = MainWindow(sim=sim)
    window.resize(1100, 700)
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()