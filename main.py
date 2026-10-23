"""Tomato Timer - 时间追踪应用"""
import sys

from PySide6.QtWidgets import QApplication

from app.database import init_db
from app.single_instance import SingleInstance
from app.ui.main_window import MainWindow
from app.ui.components import configure_application
from app.ui.theme import render_stylesheet, stylesheet_template, theme_manager


def load_stylesheet() -> str:
    return render_stylesheet(stylesheet_template())


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Tomato Timer")
    app.setQuitOnLastWindowClosed(False)

    single_instance = SingleInstance(parent=app)
    if not single_instance.acquire_or_notify():
        return 0

    init_db()
    configure_application(app)
    theme_manager(app)

    window = MainWindow()
    single_instance.activation_requested.connect(window.show_and_activate)
    app.aboutToQuit.connect(single_instance.close)
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
