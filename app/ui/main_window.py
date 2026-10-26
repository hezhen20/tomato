"""主窗口"""
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QStackedWidget, QSystemTrayIcon, QMenu, QLabel, QFrame,
)
from PySide6.QtCore import Qt, Slot, QTimer
from PySide6.QtGui import QIcon, QAction, QShortcut, QKeySequence

from app.ui.login_page import LoginPage
from app.ui.main_page import MainPage
from app.ui.history_page import HistoryPage
from app.ui.settings_page import SettingsPage, floating_time_mask_enabled
from app.ui.floating_ball import FloatingBall
from app.ui.break_reminder import BreakReminderToast
from app.hotkeys import HotkeyManager
from app.ui.components import icon, logo, ElidedLabel
from app.ui.theme import current_theme, current_mode, theme_manager, theme_colors
from app.ui.materials import FrostedSurface, MaterialWorkspace, update_native_chrome


def _make_icon():
    return QIcon(logo(64))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tomato Timer")
        self.setMinimumSize(760, 620)
        self.resize(1080, 780)
        self._theme_manager = theme_manager()

        self._icon = _make_icon()
        self.setWindowIcon(self._icon)

        self._hotkey_manager = HotkeyManager()
        self._username = ""
        self._quitting = False
        self._break_reminder_toast = BreakReminderToast()
        self._break_reminder_toast.closed.connect(self._on_break_reminder_closed)

        self._setup_ui()
        self._setup_tray()
        self._setup_floating_ball()
        self._theme_manager.theme_changed.connect(self._on_theme_changed)

    def _setup_ui(self):
        central = MaterialWorkspace()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)

        self._root_layout = QHBoxLayout(central)
        self._root_layout.setContentsMargins(0, 0, 0, 0)
        self._root_layout.setSpacing(0)

        # Persistent desktop sidebar. The login page uses the full window.
        self._nav_bar = FrostedSurface(radius=0, variant="sidebar")
        self._nav_bar.setObjectName("navBar")
        self._nav_bar.setFixedWidth(192)
        self._nav_bar.hide()
        nav_layout = QVBoxLayout(self._nav_bar)
        nav_layout.setContentsMargins(16, 28, 16, 18)
        nav_layout.setSpacing(6)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(10)
        brand_icon = QLabel()
        brand_icon.setPixmap(logo(34))
        brand_icon.setFixedSize(34, 34)
        self._brand_icon = brand_icon
        brand_row.addWidget(brand_icon)
        self._brand_text = QLabel()
        self._update_brand_text()
        self._brand_text.setTextFormat(Qt.RichText)
        self._brand_text.setObjectName("sidebarBrand")
        brand_row.addWidget(self._brand_text, 1)
        nav_layout.addLayout(brand_row)
        nav_layout.addSpacing(38)

        self._nav_buttons = []
        self._nav_labels = ["专注计时", "时间统计", "偏好设置"]
        self._nav_icons = ["timer", "chart", "settings"]
        for offset, (text, name) in enumerate(zip(self._nav_labels, self._nav_icons), 1):
            btn = QPushButton(text)
            btn.setIcon(icon(name))
            btn.setProperty("class", "navBtn")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setToolTip(f"{text} · Alt+{offset}")
            btn.setAccessibleName(text)
            btn.clicked.connect(lambda _, i=offset: self._switch_page(i))
            nav_layout.addWidget(btn)
            self._nav_buttons.append(btn)
            shortcut = QShortcut(QKeySequence(f"Alt+{offset}"), self)
            shortcut.activated.connect(lambda i=offset: self._switch_page(i) if self._username else None)

        nav_layout.addStretch()
        self._theme_toggle = QPushButton()
        self._theme_toggle.setProperty("class", "navBtn")
        self._theme_toggle.setCursor(Qt.PointingHandCursor)
        self._theme_toggle.clicked.connect(self._toggle_appearance)
        self._update_theme_toggle()
        nav_layout.addWidget(self._theme_toggle)
        nav_layout.addSpacing(16)
        self._sidebar_hint = QLabel("把时间留给\n真正重要的事。")
        self._sidebar_hint.setObjectName("sidebarHint")
        nav_layout.addWidget(self._sidebar_hint)
        nav_layout.addSpacing(22)
        self._local_status = QLabel("●  数据保存在本机")
        self._local_status.setObjectName("localStatus")
        nav_layout.addWidget(self._local_status)
        nav_layout.addSpacing(16)
        rule = QFrame()
        rule.setObjectName("sidebarRule")
        rule.setFixedHeight(1)
        nav_layout.addWidget(rule)
        nav_layout.addSpacing(10)
        account = QHBoxLayout()
        self._avatar = QLabel("T")
        self._avatar.setObjectName("avatar")
        self._avatar.setFixedSize(32, 32)
        self._avatar.setAlignment(Qt.AlignCenter)
        account.addWidget(self._avatar)
        self._account_label = ElidedLabel("本地账户")
        self._account_label.setObjectName("accountLabel")
        account.addWidget(self._account_label, 1)
        nav_layout.addLayout(account)
        self._root_layout.addWidget(self._nav_bar)

        self._stack = QStackedWidget()
        self._root_layout.addWidget(self._stack, 1)

        # 登录页
        self._login_page = LoginPage()
        self._login_page.login_success.connect(self._on_login)
        self._stack.addWidget(self._login_page)

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
        self._account_label.setText(username)
        self._account_label.setToolTip(username)
        self._avatar.setText(username[:1].upper())

        # 创建主要页面
        self._main_page = MainPage()
        self._main_page.history_requested.connect(lambda: self._switch_page(2))
        self._main_page.task_statistics_requested.connect(self._open_task_statistics)
        self._main_page.settings_requested.connect(self._open_mode_settings)
        self._main_page.break_reminder_requested.connect(self._on_break_reminder_requested)
        self._stack.addWidget(self._main_page)

        self._history_page = HistoryPage()
        self._history_page.records_changed.connect(self._main_page.refresh_today_summary)
        self._history_page.records_changed.connect(self._sync_floating_ball)
        self._history_page.records_changed.connect(self._history_page.task_page.refresh)
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
        self._update_sidebar()
        self._switch_page(1)

    def _switch_page(self, index: int):
        self._stack.setCurrentIndex(index)
        for i, btn in enumerate(self._nav_buttons):
            btn.setChecked(i == index - 1)
            btn.setIcon(icon(self._nav_icons[i], theme_colors()["accent_text"] if i == index - 1 else theme_colors()["muted"]))
        if index == 1 and hasattr(self, "_main_page"):
            self._main_page.refresh_today_summary()
        if index == 2:
            self._history_page.refresh()

    def _open_mode_settings(self):
        self._settings_page._tabs.setCurrentIndex(0)
        self._switch_page(3)

    def _open_task_statistics(self, mode_id):
        self._switch_page(2)
        self._history_page.open_task_statistics(mode_id)

    @Slot(str)
    def _on_theme_changed(self, _theme_id):
        self._icon = _make_icon()
        self.setWindowIcon(self._icon)
        self._tray.setIcon(self._icon)
        self._brand_icon.setPixmap(logo(34))
        self._update_brand_text()
        self._update_theme_toggle()
        self._login_page.refresh_theme()
        for name, button in zip(self._nav_icons, self._nav_buttons):
            button.setIcon(icon(name, theme_colors()["accent_text"] if button.isChecked() else theme_colors()["muted"]))
        if hasattr(self, "_main_page"):
            self._main_page.refresh_theme()
        if hasattr(self, "_history_page"):
            self._history_page.refresh_theme()
        self._floating_ball.update()
        self.centralWidget().update()
        self._nav_bar.update()
        self._break_reminder_toast.update()
        update_native_chrome(self)

    def _update_brand_text(self):
        self._brand_text.setText(f"<b>Tomato</b><br/><span style='font-size:10px; color:{theme_colors()['muted']}'>专注每一刻</span>")

    def _update_theme_toggle(self):
        label = "切换到浅色" if current_mode() == "dark" else "切换到深色"
        self._theme_toggle.setIcon(icon("sun" if current_mode() == "dark" else "moon"))
        self._theme_toggle.setText(label if self.width() >= 960 else "")
        self._theme_toggle.setToolTip(label)
        self._theme_toggle.setAccessibleName(label)

    def _toggle_appearance(self):
        try:
            self._theme_manager.set_mode("light" if current_mode() == "dark" else "dark")
        except Exception as exc:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "外观未保存", f"保存失败，请重试：{exc}")

    def showEvent(self, event):
        super().showEvent(event)
        update_native_chrome(self)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_nav_bar"):
            self._update_sidebar()

    def _update_sidebar(self):
        compact = self.width() < 960
        self._nav_bar.setFixedWidth(68 if compact else 192)
        self._brand_text.setVisible(not compact)
        self._sidebar_hint.setVisible(not compact)
        self._local_status.setVisible(not compact)
        self._account_label.setVisible(not compact)
        for btn, text in zip(self._nav_buttons, self._nav_labels):
            btn.setText("" if compact else text)
        self._update_theme_toggle()

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
        self._history_page.task_page.refresh()
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
        self._quitting = True
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
        # Qt sends close events when QApplication.quit() is requested as well.
        # Only a normal window close should be redirected to the tray.
        if self._quitting:
            event.accept()
            return
        event.ignore()
        self.hide()
        self._floating_ball.set_time_mask_enabled(floating_time_mask_enabled())
        self._sync_floating_ball()
        self._floating_ball.show()
        self._float_sync_timer.start()
        self._tray.showMessage("Tomato Timer", "已最小化到系统托盘，悬浮球显示中", QSystemTrayIcon.Information, 2000)
