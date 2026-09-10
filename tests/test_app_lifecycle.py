"""开发热重载与单实例启动测试。"""
import os
import uuid
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

import dev
import main as app_main
from app.single_instance import SingleInstance, default_instance_key
from app.ui.main_window import MainWindow


_qt_app = QApplication.instance() or QApplication([])


class TestDevReload(unittest.TestCase):
    def test_source_and_stylesheet_files_are_watched(self):
        for path in ("main.py", "main.pyw", "app/ui/history_page.py", "app/ui/style.qss"):
            with self.subTest(path=path):
                self.assertTrue(dev.should_watch_file(path))

    def test_unrelated_files_are_not_watched(self):
        for path in ("README.md", "tomato.db", "app/__pycache__/main.pyc", "build/app.exe"):
            with self.subTest(path=path):
                self.assertFalse(dev.should_watch_file(path))

    @patch("watchfiles.run_process")
    def test_dev_entry_starts_python_function_target(self, run_process):
        self.assertEqual(dev.main(), 0)

        _, kwargs = run_process.call_args
        self.assertEqual(kwargs["target"], "main.main")
        self.assertEqual(kwargs["target_type"], "function")


class TestSingleInstance(unittest.TestCase):
    def setUp(self):
        self.instance_key = f"TomatoTimerTest-{uuid.uuid4().hex}"
        self.instances = []

    def tearDown(self):
        for instance in reversed(self.instances):
            instance.close()
        QApplication.processEvents()

    def _instance(self):
        instance = SingleInstance(self.instance_key)
        self.instances.append(instance)
        return instance

    def test_default_key_is_stable_and_does_not_expose_home_path(self):
        key = default_instance_key()
        self.assertEqual(key, default_instance_key())
        self.assertTrue(key.startswith("TomatoTimer-"))
        self.assertNotIn(os.path.expanduser("~"), key)

    def test_second_instance_notifies_primary(self):
        primary = self._instance()
        activated = []
        primary.activation_requested.connect(lambda: activated.append(True))
        self.assertTrue(primary.acquire_or_notify())

        secondary = self._instance()
        self.assertFalse(secondary.acquire_or_notify())
        QApplication.processEvents()

        self.assertEqual(activated, [True])

    def test_lock_can_be_acquired_after_primary_closes(self):
        primary = self._instance()
        self.assertTrue(primary.acquire_or_notify())
        primary.close()

        replacement = self._instance()
        self.assertTrue(replacement.acquire_or_notify())


class TestAppStartup(unittest.TestCase):
    @patch.object(app_main, "MainWindow")
    @patch.object(app_main, "init_db")
    @patch.object(app_main, "SingleInstance")
    @patch.object(app_main, "QApplication")
    def test_secondary_instance_exits_before_business_initialization(
        self,
        application_cls,
        single_instance_cls,
        init_db,
        main_window_cls,
    ):
        application = MagicMock()
        application_cls.return_value = application
        single_instance_cls.return_value.acquire_or_notify.return_value = False

        self.assertEqual(app_main.main(), 0)

        init_db.assert_not_called()
        main_window_cls.assert_not_called()

    def test_window_activation_restores_all_window_surfaces(self):
        window = MagicMock()
        window._floating_ball = MagicMock()
        window._float_sync_timer = MagicMock()

        MainWindow.show_and_activate(window)

        window.showNormal.assert_called_once_with()
        window.raise_.assert_called_once_with()
        window.activateWindow.assert_called_once_with()
        window._floating_ball.hide.assert_called_once_with()
        window._float_sync_timer.stop.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
