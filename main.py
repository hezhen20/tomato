"""Tomato Timer - 时间追踪应用"""
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.database import init_db
from app.single_instance import SingleInstance
from app.ui.main_window import MainWindow


def load_stylesheet() -> str:
    # 支持 PyInstaller 打包后的路径
    if getattr(sys, 'frozen', False):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).parent
    qss_path = base / "app" / "ui" / "style.qss"
    if qss_path.exists():
        return qss_path.read_text(encoding="utf-8")
    return ""


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Tomato Timer")
    app.setQuitOnLastWindowClosed(False)

    single_instance = SingleInstance(parent=app)
    if not single_instance.acquire_or_notify():
        return 0

    init_db()
    app.setStyleSheet(load_stylesheet())

    window = MainWindow()
    single_instance.activation_requested.connect(window.show_and_activate)
    app.aboutToQuit.connect(single_instance.close)
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
