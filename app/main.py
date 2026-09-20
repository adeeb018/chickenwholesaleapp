import sys
from PySide6.QtWidgets import QApplication
from app.database.connection import init_db
from app.ui.main_window import MainWindow

def main():
    # 1. Initialize SQLite Database & seed defaults
    init_db()

    # 2. Launch Qt Application
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("ChickenWholesale")
    app.setOrganizationName("ChickenWholesaleShop")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
