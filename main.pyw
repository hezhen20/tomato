"""Tomato Timer - 时间追踪应用"""
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from app.database import init_db
from app.ui.main_window import MainWindow


def load_stylesheet() -> str:
    qss_path = Path(__file__).parent / "app" / "ui" / "style.qss"
    if qss_path.exists():
        return qss_path.read_text(encoding="utf-8")
    return ""


def main():
    init_db()

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(load_stylesheet())

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
