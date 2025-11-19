import sys
from PySide6.QtWidgets import QApplication

from config import DEFAULT_CONFIG
from models.simulation import Simulation
from gui.main_window import MainWindow

def main():
    app = QApplication(sys.argv)

    sim = Simulation(cfg=DEFAULT_CONFIG)
    window = MainWindow(sim=sim)
    window.resize(1100, 700)
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()