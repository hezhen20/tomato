"""主窗口"""
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QStackedWidget, QSystemTrayIcon, QMenu,
)
from PySide6.QtCore import Qt, Slot, QTimer
from PySide6.QtGui import QIcon, QAction, QPixmap, QPainter, QColor
from pathlib import Path

from app.ui.login_page import LoginPage
from app.ui.main_page import MainPage
from app.ui.history_page import HistoryPage
from app.ui.settings_page import SettingsPage, floating_time_mask_enabled
from app.ui.floating_ball import FloatingBall
from app.ui.break_reminder import BreakReminderToast
from app.hotkeys import HotkeyManager


def _make_icon():
    """生成一个简单的番茄图标"""
    pix = QPixmap(64, 64)
    pix.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor("#00F5A0"))
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(6, 6, 52, 52)

    painter.setBrush(QColor("#061017"))
    painter.drawEllipse(18, 18, 28, 28)
    painter.setBrush(QColor("#00F5A0"))
    painter.drawEllipse(22, 22, 20, 20)

    painter.setBrush(QColor("#7DF9FF"))
    painter.drawEllipse(30, 12, 4, 8)
    painter.end()
    return QIcon(pix)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tomato Timer")
        self.setMinimumSize(500, 620)
        self.resize(500, 620)

        self._icon = _make_icon()
        self.setWindowIcon(self._icon)

        self._hotkey_manager = HotkeyManager()
        self._username = ""
        self._break_reminder_toast = BreakReminderToast()
        self._break_reminder_toast.closed.connect(self._on_break_reminder_closed)

        self._setup_ui()
        self._setup_tray()
        self._setup_floating_ball()

    def _setup_ui(self):
        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)

        self._root_layout = QVBoxLayout(central)
        self._root_layout.setContentsMargins(0, 0, 0, 0)
        self._root_layout.setSpacing(0)

        # 页面栈
        self._stack = QStackedWidget()
        self._root_layout.addWidget(self._stack)

        # 登录页
        self._login_page = LoginPage()
        self._login_page.login_success.connect(self._on_login)
        self._stack.addWidget(self._login_page)

        # 导航栏（登录后显示）
        self._nav_bar = QWidget()
        self._nav_bar.setObjectName("navBar")
        self._nav_bar.setVisible(False)
        nav_layout = QHBoxLayout(self._nav_bar)
        nav_layout.setContentsMargins(14, 8, 14, 8)
        nav_layout.setSpacing(8)

        self._nav_buttons = []
        for text, idx in [("计时", 1), ("历史", 2), ("设置", 3)]:
            btn = QPushButton(text)
            btn.setProperty("class", "navBtn")
            btn.setCheckable(True)
            btn.clicked.connect(lambda _, i=idx: self._switch_page(i))
            nav_layout.addWidget(btn)
            self._nav_buttons.append(btn)

        self._root_layout.insertWidget(0, self._nav_bar)

    def _setup_tray(self):
        self._tray = QSystemTrayIcon(self._icon, self)
        menu = QMenu()
        show_action = QAction("显示", self)
        show_action.triggered.connect(self._show_window)
        menu.addAction(show_action)

        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self._quit)
        menu.addAction(quit_action)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _setup_floating_ball(self):
        self._floating_ball = FloatingBall()
        self._floating_ball.set_time_mask_enabled(floating_time_mask_enabled())
        self._floating_ball.double_clicked.connect(self._show_window)

        # 定时器同步悬浮球显示
        self._float_sync_timer = QTimer(self)
        self._float_sync_timer.setInterval(500)
        self._float_sync_timer.timeout.connect(self._sync_floating_ball)

    def _sync_floating_ball(self):
        if not hasattr(self, "_main_page"):
            return
        mp = self._main_page
        if mp._running and mp._current_mode:
            status = "paused" if mp._paused else "running"
            self._floating_ball.update_display(
                mp._current_mode["name"],
                mp._current_mode["color"],
                mp.timer_label.text(),
                status,
            )
        elif mp._current_mode:
            # 已停止但有模式
            self._floating_ball.update_display(
                mp._current_mode["name"],
                mp._current_mode["color"],
                mp.timer_label.text(),
                "stopped",
            )
        else:
            self._floating_ball.clear_display()

    @Slot(str)
    def _on_login(self, username: str):
        self._username = username

        # 创建主要页面
        self._main_page = MainPage()
        self._main_page.break_reminder_requested.connect(self._on_break_reminder_requested)
        self._stack.addWidget(self._main_page)

        self._history_page = HistoryPage()
        self._stack.addWidget(self._history_page)

        self._settings_page = SettingsPage(self._hotkey_manager, username)
        self._settings_page.modes_changed.connect(self._on_modes_changed)
        self._settings_page.hotkeys_changed.connect(self._on_hotkeys_changed)
        self._settings_page.floating_settings_changed.connect(self._on_floating_settings_changed)
        self._settings_page.reminder_settings_changed.connect(self._on_reminder_settings_changed)
        self._stack.addWidget(self._settings_page)

        # 连接快捷键
        self._hotkey_manager.hotkey_triggered.connect(self._on_hotkey)
        self._hotkey_manager.start()

        # 显示导航和主页
        self._nav_bar.setVisible(True)
        self._switch_page(1)

    def _switch_page(self, index: int):
        self._stack.setCurrentIndex(index)
        for i, btn in enumerate(self._nav_buttons):
            btn.setChecked(i == index - 1)
        if index == 2:
            self._history_page.refresh()

    @Slot(str)
    def _on_hotkey(self, action: str):
        if action == "pause_resume":
            self._main_page.toggle_pause()
        elif action == "stop":
            self._main_page.stop_timer()
            self._main_page.refresh_today_summary()
        elif action.startswith("mode_"):
            mode_name = action[5:]
            self._main_page.switch_to_mode(mode_name)

    def _on_modes_changed(self):
        self._main_page.refresh_modes()
        self._settings_page.refresh_mode_hotkeys()
        self._hotkey_manager.restart()

    def _on_hotkeys_changed(self):
        self._hotkey_manager.restart()

    @Slot(str, int, str)
    def _on_break_reminder_requested(self, mode_name: str, interval_minutes: int, message: str):
        self._break_reminder_toast.show_reminder(mode_name, interval_minutes, message)

    @Slot()
    def _on_break_reminder_closed(self):
        if hasattr(self, "_main_page"):
            self._main_page.dismiss_break_reminder()

    @Slot()
    def _on_reminder_settings_changed(self):
        self._break_reminder_toast.close()
        if hasattr(self, "_main_page"):
            self._main_page.reload_reminder_settings()

    @Slot(bool)
    def _on_floating_settings_changed(self, time_mask_enabled: bool):
        self._floating_ball.set_time_mask_enabled(time_mask_enabled)
        if self._floating_ball.isVisible():
            self._sync_floating_ball()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self._show_window()

    @Slot()
    def show_and_activate(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()
        self._floating_ball.hide()
        self._float_sync_timer.stop()

    def _show_window(self):
        self.show_and_activate()

    def _quit(self):
        if hasattr(self, "_main_page") and self._main_page._running:
            self._main_page.stop_timer()
        self._hotkey_manager.stop()
        self._float_sync_timer.stop()
        self._break_reminder_toast.close()
        self._floating_ball.close()
        self._tray.hide()
        from PySide6.QtWidgets import QApplication
        QApplication.quit()

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self._floating_ball.set_time_mask_enabled(floating_time_mask_enabled())
        self._sync_floating_ball()
        self._floating_ball.show()
        self._float_sync_timer.start()
        self._tray.showMessage("Tomato Timer", "已最小化到系统托盘，悬浮球显示中", QSystemTrayIcon.Information, 2000)
