"""UI regression coverage using native Qt input and isolated SQLite data."""
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt, QDateTime
from PySide6.QtGui import QFontDatabase
from PySide6.QtTest import QTest, QSignalSpy
from PySide6.QtWidgets import QApplication, QScrollArea

import app.database as db
from app.hotkeys import HotkeyManager
from app.ui.components import configure_application
from app.ui.login_page import LoginPage
from app.ui.main_page import MainPage
from app.ui.main_window import MainWindow
from app.ui.history_page import HistoryPage
from app.ui.break_reminder import BreakReminderToast
from app.ui.settings_page import SettingsPage
from main import load_stylesheet


class UiWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        # Windows offscreen Qt does not discover system fonts automatically.
        for filename in ("segoeui.ttf", "seguisb.ttf", "msyh.ttc", "msyhbd.ttc", "consola.ttf"):
            font_path = Path("C:/Windows/Fonts") / filename
            if font_path.exists():
                QFontDatabase.addApplicationFont(str(font_path))
        cls._previous_style = cls.app.styleSheet()
        configure_application(cls.app)
        cls.app.setStyleSheet(load_stylesheet())

    @classmethod
    def tearDownClass(cls):
        cls.app.setStyleSheet(cls._previous_style)

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(db, "DB_PATH", Path(self.directory.name) / "ui.db")
        self.db_patch.start()
        db.init_db()
        db.create_user("tester", "secret")
        self.widgets = []

    def tearDown(self):
        for widget in reversed(self.widgets):
            if isinstance(widget, MainWindow):
                if hasattr(widget, "_main_page"):
                    widget._main_page.stop_timer()
                widget._float_sync_timer.stop()
                widget._floating_ball.close()
                widget._break_reminder_toast.close()
                widget._tray.hide()
            elif isinstance(widget, MainPage):
                widget.stop_timer()
            widget.hide()
            widget.deleteLater()
        self.app.processEvents()
        self.db_patch.stop()
        self.directory.cleanup()

    def show_widget(self, widget, size=(840, 730)):
        self.widgets.append(widget)
        widget.resize(*size)
        widget.show()
        self.app.processEvents()
        return widget

    def make_window(self):
        window = self.show_widget(MainWindow(), (1080, 780))
        # Do not register real global shortcuts while running UI tests.
        window._hotkey_manager.start = lambda: None
        window._on_login("tester")
        self.app.processEvents()
        return window

    def insert_record(self, mode_id, seconds, start=None):
        start = start or datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
        with db._conn() as conn:
            cursor = conn.execute(
                "INSERT INTO time_record(mode_id,start_time,end_time,duration_seconds) VALUES(?,?,?,?)",
                (mode_id, start.isoformat(), (start + timedelta(seconds=seconds)).isoformat(), seconds),
            )
            return cursor.lastrowid

    def test_login_validation_and_enter_submit_existing_user(self):
        page = self.show_widget(LoginPage())
        spy = QSignalSpy(page.login_success)
        QTest.mouseClick(page.submit_btn, Qt.LeftButton)
        self.assertIn("用户名", page.msg_label.text())
        page.username_input.setText("tester")
        page.password_input.setText("wrong")
        QTest.keyClick(page.password_input, Qt.Key_Return)
        self.assertEqual(spy.count(), 0)
        page.password_input.setText("secret")
        QTest.keyClick(page.password_input, Qt.Key_Return)
        self.assertEqual(spy.count(), 1)
        self.assertEqual(spy.at(0), ["tester"])

    def test_login_still_registers_new_local_user(self):
        page = self.show_widget(LoginPage())
        page.username_input.setText("new-user")
        page.password_input.setText("new-secret")
        QTest.mouseClick(page.submit_btn, Qt.LeftButton)
        self.assertTrue(db.verify_user("new-user", "new-secret"))

    def test_start_pause_resume_stop_preserves_accumulated_seconds(self):
        mode = db.get_modes()[0]
        self.insert_record(mode["id"], 120)
        page = self.show_widget(MainPage())
        QTest.mouseClick(page.start_btn, Qt.LeftButton)
        self.assertTrue(page._running)
        self.assertFalse(page.pause_btn.isHidden())
        for _ in range(7):
            page._tick()
        QTest.mouseClick(page.pause_btn, Qt.LeftButton)
        self.assertTrue(page._paused)
        self.assertFalse(page._timer.isActive())
        QTest.mouseClick(page.pause_btn, Qt.LeftButton)
        self.assertFalse(page._paused)
        QTest.mouseClick(page.stop_btn, Qt.LeftButton)
        self.assertEqual(db.get_daily_summary(date.today())[mode["name"]]["seconds"], 127)
        self.assertEqual(page.timer_label.text(), "00:02:07")
        self.assertFalse(page.start_btn.isHidden())

    def test_mode_button_switch_saves_previous_session(self):
        first = db.get_modes()[0]
        db.add_mode("阅读", "#99AAEE")
        page = self.show_widget(MainPage())
        QTest.mouseClick(page._mode_buttons[0], Qt.LeftButton)
        for _ in range(5):
            page._tick()
        QTest.mouseClick(page._mode_buttons[1], Qt.LeftButton)
        for _ in range(3):
            page._tick()
        QTest.mouseClick(page.stop_btn, Qt.LeftButton)
        summary = db.get_daily_summary(date.today())
        self.assertEqual(summary[first["name"]]["seconds"], 5)
        self.assertEqual(summary["阅读"]["seconds"], 3)

    def test_autosave_then_stop_does_not_double_count(self):
        page = self.show_widget(MainPage())
        QTest.mouseClick(page.start_btn, Qt.LeftButton)
        for _ in range(35):
            page._tick()
        QTest.mouseClick(page.stop_btn, Qt.LeftButton)
        self.assertEqual(db.get_daily_summary(date.today())[page._current_mode["name"]]["seconds"], 35)
        self.assertEqual(page.timer_label.text(), "00:00:35")

    def test_hotkey_recorder_takes_precedence_over_navigation(self):
        window = self.make_window()
        window._switch_page(3)
        settings = window._settings_page
        settings._tabs.setCurrentIndex(1)
        self.app.processEvents()
        recorder = settings.hotkey_recorders["pause_resume"]
        QTest.mouseClick(recorder, Qt.LeftButton)
        QTest.keyPress(recorder, Qt.Key_Alt)
        QTest.keyClick(recorder, Qt.Key_1, Qt.AltModifier)
        QTest.keyRelease(recorder, Qt.Key_Alt)
        self.assertEqual(recorder.get_hotkey_display(), "Alt+1")
        self.assertEqual(window._stack.currentIndex(), 3)

    def test_mode_rename_preserves_record_and_refreshes_current_mode(self):
        window = self.make_window()
        page, settings = window._main_page, window._settings_page
        page._start_default_mode()
        page._tick()
        mode_id = page._current_mode["id"]
        settings._start_mode_edit(mode_id)
        settings.edit_mode_input.setText("新的工作模式")
        # Mode edits restart shortcut listeners in production; avoid OS hooks here.
        with patch.object(window._hotkey_manager, "restart", lambda: None):
            settings._save_mode_edit()
        self.app.processEvents()
        self.assertEqual(page._current_mode["id"], mode_id)
        self.assertEqual(page._current_mode["name"], "新的工作模式")
        page.stop_timer()
        self.assertEqual(db.get_daily_summary(date.today())["新的工作模式"]["seconds"], 1)

    def test_navigation_actions_open_history_and_mode_settings(self):
        window = self.make_window()
        window._main_page.history_requested.emit()
        self.assertEqual(window._stack.currentIndex(), 2)
        window._settings_page._tabs.setCurrentIndex(4)
        window._main_page.settings_requested.emit()
        self.assertEqual(window._stack.currentIndex(), 3)
        self.assertEqual(window._settings_page._tabs.currentIndex(), 0)
        QTest.keyClick(window, Qt.Key_1, Qt.AltModifier)
        self.assertEqual(window._stack.currentIndex(), 1)

    def test_compact_layout_keeps_all_settings_tabs_reachable(self):
        window = self.make_window()
        window.resize(760, 620)
        window._switch_page(3)
        self.app.processEvents()
        self.assertEqual(window.width(), 760)
        self.assertEqual(window._nav_bar.width(), 68)
        tabs = window._settings_page._tabs
        for index in range(tabs.count()):
            tabs.setCurrentIndex(index)
            self.app.processEvents()
            page = tabs.currentWidget()
            self.assertIsInstance(page, QScrollArea)
            self.assertEqual(page.horizontalScrollBar().maximum(), 0)
            self.assertLessEqual(page.widget().minimumSizeHint().width(), page.viewport().width())

    def test_many_long_mode_names_scroll_without_expanding_window(self):
        for i in range(12):
            db.add_mode(f"很长的自定义模式名称-{i}-" + "学习" * 20, "#111122")
        window = self.make_window()
        window.resize(760, 620)
        window._main_page.refresh_modes()
        self.app.processEvents()
        mode_scroll = window._main_page.findChild(QScrollArea, "modeScroll")
        self.assertEqual(window.width(), 760)
        self.assertGreater(mode_scroll.horizontalScrollBar().maximum(), 0)
        self.assertEqual(len(window._main_page._mode_buttons), 13)
        for button in window._main_page._mode_buttons:
            self.assertLessEqual(button.width(), 200)

    def test_history_retains_date_merging_and_daily_totals(self):
        page = self.show_widget(HistoryPage())
        data = {"2030-01-01": {
            "工作": {"seconds": 3600, "periods": {"morning": 3600}},
            "学习": {"seconds": 1800, "periods": {"afternoon": 1800}},
        }}
        page._populate_period_table(page.week_table, data)
        self.assertEqual(page.week_table.rowCount(), 3)
        self.assertEqual(page.week_table.rowSpan(0, 0), 3)
        self.assertEqual(page.week_table.item(0, 1).text(), "总计")
        self.assertEqual(page.week_table.item(0, 3).text(), "1h 30m")
        self.assertIn("上午 1h 0m", page.week_table.item(0, 2).toolTip())

    def test_chart_values_match_recorded_daily_totals(self):
        mode = db.get_modes()[0]
        self.insert_record(mode["id"], 3600)
        page = self.show_widget(HistoryPage())
        page.refresh()
        self.assertEqual(len(page.week_chart._days), 7)
        self.assertEqual(sum(value for _, value in page.week_chart._days), 3600)
        self.assertEqual(sum(value for _, value in page.month_chart._days), 3600)

    def test_record_delete_confirmation_preserves_active_timer(self):
        mode = db.get_modes()[0]
        self.insert_record(mode["id"], 3600)
        active_id = db.start_record(mode["id"])
        page = self.show_widget(HistoryPage())
        page.manage_end_edit.setDateTime(QDateTime.currentDateTime().addDays(1))
        self.assertTrue(page.manage_delete_btn.isEnabled())
        # Confirm both dialogs; this exercises the real delete handler and refreshes.
        from PySide6.QtWidgets import QMessageBox
        with patch.object(QMessageBox, "exec", return_value=QMessageBox.Yes):
            page._confirm_delete_records()
        self.assertEqual(page._manage_records, [])
        with db._conn() as conn:
            row = conn.execute("SELECT end_time FROM time_record WHERE id=?", (active_id,)).fetchone()
        self.assertIsNotNone(row)
        self.assertIsNone(row["end_time"])

    def test_floating_mask_and_restore_signal(self):
        window = self.make_window()
        window._main_page._start_default_mode()
        window._sync_floating_ball()
        floating = window._floating_ball
        self.assertEqual(floating._status, "running")
        floating.set_time_mask_enabled(False)
        self.assertFalse(floating._time_mask_enabled)
        window.hide()
        floating.show()
        floating.double_clicked.emit()
        self.assertTrue(window.isVisible())
        self.assertFalse(floating.isVisible())

    def test_break_reminder_long_mode_stays_inside_window(self):
        toast = self.show_widget(BreakReminderToast(), (480, 250))
        for name in ("工作", "很长的自定义模式" * 20):
            toast.show_reminder(name, 45, "起身活动一下。" * 25)
            self.app.processEvents()
            self.assertEqual(toast.width(), 480)
            self.assertLessEqual(toast._mode_chip.geometry().right(), toast.width() - 20)
            self.assertGreaterEqual(toast._mode_chip.geometry().left(), 20)

    def test_full_application_entry_starts_real_window(self):
        script = '''
import tempfile, uuid
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
import app.database as db
import main
from app.single_instance import SingleInstance
with tempfile.TemporaryDirectory() as directory:
    db.DB_PATH = Path(directory) / 'startup.db'
    original_window = main.MainWindow
    def create_window():
        window = original_window()
        QTimer.singleShot(150, window._quit)
        print('STARTUP_OK', flush=True)
        return window
    main.MainWindow = create_window
    main.SingleInstance = lambda parent: SingleInstance('UiTest-' + uuid.uuid4().hex, parent)
    assert main.main() == 0
'''
        result = subprocess.run([sys.executable, "-X", "faulthandler", "-c", script],
                                cwd=Path(__file__).resolve().parents[1],
                                env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("STARTUP_OK", result.stdout)
        self.assertNotRegex(result.stderr, r"QPainter|Could not parse|Unknown property|access violation")


if __name__ == "__main__":
    unittest.main()
