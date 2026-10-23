"""Accent selection, live application, contrast, persistence and timer isolation."""
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QScrollArea

import app.database as db
from app.hotkeys import HotkeyManager
from app.ui.colors import contrast_ratio
from app.ui.components import ActivityChart
from app.ui.main_window import MainWindow
from app.ui.settings_page import SettingsPage
from app.ui.theme import (
    DEFAULT_THEME_ID, THEME_PRESETS, THEME_SETTING_KEY, ThemeManager,
    current_theme, current_mode, APPEARANCE_SETTING_KEY, mode_display_color,
    render_stylesheet, stylesheet_template, theme_manager,
)


class ThemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.db_path = Path(self.directory.name) / "themes.db"
        self.db_patch = patch.object(db, "DB_PATH", self.db_path)
        self.db_patch.start()
        db.init_db()
        self.previous_theme = current_theme().id
        self.previous_mode = current_mode()
        self.manager = theme_manager(self.app)
        self.manager.apply(DEFAULT_THEME_ID, mode="dark", persist=False)
        self.widgets = []

    def tearDown(self):
        for widget in self.widgets:
            if isinstance(widget, MainWindow):
                widget._main_page.stop_timer()
                widget._tray.hide()
                widget._floating_ball.close()
                widget._break_reminder_toast.close()
            widget.hide()
            widget.deleteLater()
        self.app.processEvents()
        self.manager.apply(self.previous_theme, mode=self.previous_mode, persist=False)
        self.db_patch.stop()
        self.directory.cleanup()

    def test_all_preset_text_and_interaction_states_have_readable_contrast(self):
        for preset in THEME_PRESETS:
            for mode in ("light", "dark"):
                with self.subTest(theme=preset.id, mode=mode):
                    colors = preset.colors_for(mode)
                    for background in ("accent", "accent_hover", "accent_pressed"):
                        self.assertGreaterEqual(contrast_ratio(colors["on_accent"], colors[background]), 4.5)
                    self.assertGreaterEqual(contrast_ratio(colors["accent_text"], colors["accent_soft"]), 4.5)
                    self.assertGreaterEqual(contrast_ratio(colors["hero_muted"], colors["hero_background"]), 4.5)
                    self.assertGreaterEqual(contrast_ratio(colors["selection_text"], colors["selection"]), 4.5)
                    for role in ("text", "muted", "placeholder"):
                        for background in ("surface", "window", "surface_alt"):
                            self.assertGreaterEqual(contrast_ratio(colors[role], colors[background]), 4.5)
                    self.assertGreaterEqual(contrast_ratio(colors["chart"], colors["window"]), 3)
                    self.assertGreaterEqual(contrast_ratio(colors["focus"], colors["surface"]), 3)
                    self.assertNotRegex(render_stylesheet(stylesheet_template(), preset, mode), r"@[a-z_]+")

    def test_real_theme_buttons_apply_all_presets_without_resetting_active_timer(self):
        window = MainWindow()
        self.widgets.append(window)
        window._hotkey_manager.start = lambda: None
        window._on_login("theme-tester")
        window.show()
        page = window._main_page
        page._start_default_mode()
        for _ in range(5):
            page._tick()
        page.toggle_pause()
        snapshot = (page._elapsed, page._session_elapsed, page._current_record_id)
        modes_before = db.get_modes()
        history_date = date.today() - timedelta(days=10)
        window._history_page._current_date = history_date
        settings = window._settings_page
        settings._tabs.setCurrentIndex(settings._tabs.count() - 1)
        window._switch_page(3)
        self.app.processEvents()
        for preset in THEME_PRESETS:
            with self.subTest(theme=preset.id):
                QTest.mouseClick(settings.theme_buttons[preset.id], Qt.LeftButton)
                self.app.processEvents()
                self.assertEqual(current_theme().id, preset.id)
                self.assertEqual(db.get_setting(THEME_SETTING_KEY), preset.id)
                self.assertEqual(sum(button.isChecked() for button in settings.theme_buttons.values()), 1)
                self.assertIn(preset.name, settings.theme_save_status.text())
                self.assertEqual((page._elapsed, page._session_elapsed, page._current_record_id), snapshot)
                self.assertTrue(page._running and page._paused)
                self.assertEqual(db.get_modes(), modes_before)
                self.assertEqual(window._history_page._current_date, history_date)
                self.assertEqual(page.pause_btn.palette().button().color().name().upper(), preset.accent)

    def test_saved_choice_loads_in_fresh_process_before_login(self):
        self.manager.apply("purple", mode="light")
        script = '''
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
import app.database as db
from app.ui.main_window import MainWindow
from app.ui.theme import current_theme, current_mode, theme_manager
db.DB_PATH = Path(sys.argv[1])
app = QApplication([])
theme_manager(app)
window = MainWindow()
assert current_theme().id == 'purple'
assert current_mode() == 'light'
assert '#644AC9' in app.styleSheet()
assert window._stack.currentIndex() == 0
window._tray.hide()
window._floating_ball.close()
window._break_reminder_toast.close()
print('RESTORED_PURPLE_BEFORE_LOGIN')
'''
        result = subprocess.run([sys.executable, "-c", script, str(self.db_path)],
                                cwd=Path(__file__).resolve().parents[1],
                                env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("RESTORED_PURPLE_BEFORE_LOGIN", result.stdout)
        self.assertNotRegex(result.stderr, r"Unknown color|Could not parse|QPainter")

    def test_unknown_saved_choice_safely_uses_original_theme(self):
        db.set_setting(THEME_SETTING_KEY, "obsolete-or-invalid-theme")
        manager = ThemeManager(self.app)
        try:
            self.assertEqual(current_theme().id, DEFAULT_THEME_ID)
            self.assertNotRegex(self.app.styleSheet(), r"@[a-z_]+")
        finally:
            manager.deleteLater()

    def test_failed_save_keeps_the_previous_theme_and_setting(self):
        self.manager.apply("blue")
        stylesheet_before = self.app.styleSheet()
        with patch("app.ui.theme.set_settings", side_effect=sqlite3.OperationalError("database is locked")):
            with self.assertRaises(sqlite3.OperationalError):
                self.manager.apply("pink", mode="light")
        self.assertEqual(current_theme().id, "blue")
        self.assertEqual(db.get_setting(THEME_SETTING_KEY), "blue")
        self.assertEqual(self.app.styleSheet(), stylesheet_before)
        self.assertEqual(current_mode(), "dark")
        self.assertEqual(db.get_setting(APPEARANCE_SETTING_KEY), "dark")

    def test_light_and_dark_controls_keep_the_live_timer_and_mode_colors(self):
        window = MainWindow()
        self.widgets.append(window)
        window._hotkey_manager.start = lambda: None
        window._on_login("theme-tester")
        window.show()
        page = window._main_page
        page._start_default_mode()
        for _ in range(7):
            page._tick()
        snapshot = (page._elapsed, page._session_elapsed, page._current_record_id)
        modes_before = db.get_modes()
        settings = window._settings_page
        settings._tabs.setCurrentIndex(settings._tabs.count() - 1)
        window._switch_page(3)
        for mode in ("light", "dark"):
            QTest.mouseClick(settings.appearance_mode_buttons[mode], Qt.LeftButton)
            self.assertEqual(current_mode(), mode)
            self.assertEqual(db.get_setting(APPEARANCE_SETTING_KEY), mode)
            self.assertEqual(sum(button.isChecked() for button in settings.appearance_mode_buttons.values()), 1)
            self.assertEqual((page._elapsed, page._session_elapsed, page._current_record_id), snapshot)
            self.assertTrue(page._running and page._timer.isActive())
            self.assertEqual(db.get_modes(), modes_before)

    def test_partial_preference_write_rolls_back_both_values(self):
        self.manager.apply("blue", mode="dark")
        with self.assertRaises(sqlite3.ProgrammingError):
            db.set_settings({THEME_SETTING_KEY: "purple", APPEARANCE_SETTING_KEY: object()})
        self.assertEqual(db.get_setting(THEME_SETTING_KEY), "blue")
        self.assertEqual(db.get_setting(APPEARANCE_SETTING_KEY), "dark")

    def test_sidebar_toggle_updates_the_mode_selector_and_saved_preference(self):
        window = MainWindow()
        self.widgets.append(window)
        window._hotkey_manager.start = lambda: None
        window._on_login("theme-tester")
        window.show()
        for expected in ("light", "dark"):
            QTest.mouseClick(window._theme_toggle, Qt.LeftButton)
            self.assertEqual(current_mode(), expected)
            self.assertEqual(db.get_setting(APPEARANCE_SETTING_KEY), expected)
            self.assertTrue(window._settings_page.appearance_mode_buttons[expected].isChecked())
            self.assertIn("深色" if expected == "light" else "浅色", window._theme_toggle.toolTip())

    def test_light_mode_settings_remain_usable_in_compact_window(self):
        window = MainWindow()
        self.widgets.append(window)
        window._hotkey_manager.start = lambda: None
        window._on_login("theme-tester")
        self.manager.set_mode("light")
        window.resize(760, 620)
        window.show()
        window._switch_page(3)
        tabs = window._settings_page._tabs
        for index in range(tabs.count()):
            tabs.setCurrentIndex(index)
            self.app.processEvents()
            page = tabs.currentWidget()
            self.assertIsInstance(page, QScrollArea)
            self.assertEqual(page.horizontalScrollBar().maximum(), 0)
            self.assertLessEqual(page.widget().minimumSizeHint().width(), page.viewport().width())
        self.assertEqual(window.width(), 760)
        self.assertEqual(window._settings_page.new_mode_input.palette().base().color().name().upper(), "#FFFFFF")

    def test_saved_feedback_updates_its_color_with_appearance_mode(self):
        from app.ui.theme import theme_colors
        settings = SettingsPage(HotkeyManager(), "theme-tester")
        self.widgets.append(settings)
        settings._save_reminder_settings()
        for mode in ("light", "dark"):
            self.manager.set_mode(mode)
            self.assertEqual(settings.reminder_save_status.palette().windowText().color().name().upper(), theme_colors()["success"])

    def test_bright_and_dark_mode_colors_remain_readable_on_both_surfaces(self):
        from app.ui.theme import theme_colors
        for mode in ("light", "dark"):
            self.manager.set_mode(mode, persist=False)
            for value in ("#FFFFFF", "#000000", "#00F5A0", "#111122", "#FF9800"):
                self.assertGreaterEqual(contrast_ratio(mode_display_color(value), theme_colors()["surface"]), 4.5)

    def test_native_keyboard_activation_selects_theme(self):
        settings = SettingsPage(HotkeyManager(), "theme-tester")
        self.widgets.append(settings)
        settings.resize(760, 620)
        settings._tabs.setCurrentIndex(settings._tabs.count() - 1)
        settings.show()
        button = settings.theme_buttons["peach"]
        button.setFocus()
        QTest.keyClick(button, Qt.Key_Space)
        self.assertTrue(button.isChecked())
        self.assertEqual(db.get_setting(THEME_SETTING_KEY), "peach")

    def test_painted_chart_uses_current_accent_after_each_switch(self):
        chart = ActivityChart()
        self.widgets.append(chart)
        chart.resize(420, 140)
        chart.set_days([("周一", 3600)])
        for preset in THEME_PRESETS:
            self.manager.apply(preset.id, persist=False)
            image = chart.grab().toImage()
            self.assertEqual(image.pixelColor(chart.width() // 2, chart.height() // 2).name().upper(), preset.accent)


if __name__ == "__main__":
    unittest.main()
