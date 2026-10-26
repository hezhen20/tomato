"""任务统计的数据边界与真实 Qt 交互回归，全部使用临时数据库。"""
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QDate, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

import app.database as db
from app.ui.history_page import HistoryPage
from app.ui.task_stats_page import TaskStatsPage, trend_columns


class TaskStatsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(db, "DB_PATH", Path(self.directory.name) / "tasks.db")
        self.db_patch.start()
        db.init_db()
        self.first = db.get_modes()[0]["id"]
        self.second = db.add_mode("阅读", "#89B4FA")
        self.widgets = []

    def tearDown(self):
        for widget in self.widgets:
            widget.hide()
            widget.deleteLater()
        self.app.processEvents()
        self.db_patch.stop()
        self.directory.cleanup()

    def insert(self, mode_id, start, seconds, end=None):
        with db._conn() as conn:
            return conn.execute(
                "INSERT INTO time_record(mode_id,start_time,end_time,duration_seconds) VALUES(?,?,?,?)",
                (mode_id, start.isoformat(), (end or start + timedelta(seconds=seconds)).isoformat(), seconds),
            ).lastrowid

    def page(self):
        page = TaskStatsPage()
        self.widgets.append(page)
        page._anchor, page._follow_today = date(2030, 3, 15), False
        page.refresh()
        return page

    def test_task_filter_and_rename_keep_identity(self):
        day = date(2030, 3, 15)
        self.insert(self.first, datetime(2030, 3, 15, 9), 1800)
        self.insert(self.second, datetime(2030, 3, 15, 10), 7200)
        result = db.get_range_period_summary(day, day, self.first)
        self.assertEqual(result[day.isoformat()]["工作"]["seconds"], 1800)
        self.assertNotIn("阅读", result[day.isoformat()])
        db.update_mode(self.first, "开发", "#A6E3A1")
        result = db.get_range_period_summary(day, day, self.first)
        self.assertEqual(result[day.isoformat()]["开发"]["seconds"], 1800)
        self.assertEqual(db.get_range_period_summary(day, day, 999999), {})

    def test_periods_split_at_noon_evening_and_four(self):
        self.insert(self.first, datetime(2030, 3, 31, 11, 30), 3600)
        self.insert(self.first, datetime(2030, 3, 31, 17, 30), 3600)
        self.insert(self.first, datetime(2030, 3, 31, 23), 6 * 3600)
        march = db.get_range_period_summary(date(2030, 3, 31), date(2030, 3, 31), self.first)
        info = march["2030-03-31"]["工作"]
        self.assertEqual(info["periods"], {"morning": 1800, "afternoon": 3600, "evening": 19800})
        april = db.get_range_period_summary(date(2030, 4, 1), date(2030, 4, 1), self.first)
        self.assertEqual(april["2030-04-01"]["工作"]["periods"], {"morning": 3600, "afternoon": 0, "evening": 0})
        self.assertEqual(info["seconds"] + april["2030-04-01"]["工作"]["seconds"], 8 * 3600)

    def test_all_bounds_exclude_zero_records_and_exclusive_end(self):
        self.insert(self.first, datetime(2030, 1, 1, 2), 7200)
        self.insert(self.first, datetime(2030, 4, 1, 2), 7200)
        self.insert(self.first, datetime(2040, 1, 1, 9), 0)
        self.insert(self.second, datetime(2000, 1, 1, 9), 3600)
        self.assertEqual(db.get_mode_date_bounds(self.first), (date(2029, 12, 31), date(2030, 3, 31)))
        self.assertIsNone(db.get_mode_date_bounds(999999))

    def test_saved_chunks_count_once_and_pause_gap_is_excluded(self):
        self.insert(self.first, datetime(2030, 3, 15, 11, 59, 30), 30)
        self.insert(self.first, datetime(2030, 3, 15, 12), 30)
        self.insert(self.first, datetime(2030, 3, 15, 13), 30)
        with db._conn() as conn:
            conn.execute("INSERT INTO time_record(mode_id,start_time) VALUES(?,?)", (self.first, "2030-03-15T14:00:00"))
        page = self.page()
        self.assertEqual(page.metric_values["total"].text(), "1m")
        self.assertEqual(page.metric_values["total"].toolTip(), "0小时 1分钟 30秒")
        self.assertEqual(page.period_values["morning"].text(), "30s")
        self.assertEqual(page.period_values["afternoon"].text(), "1m")
        self.assertEqual(sum(value for _, value in page.chart._days), 90)

    def test_picker_switches_task_and_summary_chart_table_agree(self):
        self.insert(self.first, datetime(2030, 3, 15, 9), 3600)
        self.insert(self.second, datetime(2030, 3, 15, 11, 30), 3600)
        self.insert(self.second, datetime(2030, 3, 16, 19), 7200)
        page = self.page()
        page.task_combo.setCurrentIndex(page.task_combo.findData(self.second))
        self.assertEqual(page.task_title.text(), "阅读")
        self.assertEqual(page.metric_values["total"].text(), "3h 0m")
        self.assertEqual(page.metric_values["days"].text(), "2 天")
        self.assertEqual(page.metric_values["average"].text(), "1h 30m")
        self.assertEqual(page.metric_values["peak"].text(), "2h 0m")
        self.assertEqual(sum(value for _, value in page.chart._days), 10800)
        self.assertEqual(page.table.rowCount(), 2)
        self.assertEqual(page.table.item(0, 0).text(), "2030/03/16")
        self.assertAlmostEqual(sum(bar.value() for bar in page.period_bars.values()), 1000, delta=2)

    def test_custom_range_inclusive_end_invalid_range_clears_stale_data(self):
        self.insert(self.first, datetime(2030, 4, 1, 2), 3600)
        self.insert(self.first, datetime(2030, 4, 1, 5), 3600)
        page = self.page()
        page.range_combo.setCurrentIndex(page.range_combo.findData("custom"))
        page.start_edit.setDate(QDate(2030, 3, 31))
        page.end_edit.setDate(QDate(2030, 3, 31))
        self.assertEqual(page.metric_values["total"].text(), "1h 0m")
        self.assertEqual(page.period_values["evening"].text(), "1h 0m")
        page.start_edit.setDate(QDate(2030, 4, 2))
        self.assertIn("开始日期不能晚于结束日期", page.status_label.text())
        self.assertEqual(page.table.rowCount(), 0)
        self.assertEqual(page.chart._days, [])
        self.assertEqual(page.metric_values["total"].text(), "0s")
        self.assertFalse(page.prev_button.isEnabled())

    def test_navigation_keeps_task_and_handles_year_boundary(self):
        page = self.page()
        page.select_task(self.second)
        page._anchor = date(2030, 12, 31)
        page._refresh_data()
        QTest.mouseClick(page.next_button, Qt.LeftButton)
        self.assertEqual(page.start_edit.date().toPython(), date(2031, 1, 1))
        self.assertEqual(page.end_edit.date().toPython(), date(2031, 1, 31))
        self.assertEqual(page.task_combo.currentData(), self.second)
        page.range_combo.setCurrentIndex(page.range_combo.findData("all"))
        self.assertFalse(page.next_button.isEnabled())

    def test_refresh_keeps_selected_id_after_rename_and_handles_deleted_task(self):
        self.insert(self.second, datetime(2030, 3, 15, 9), 3600)
        page = self.page()
        page.select_task(self.second)
        db.update_mode(self.second, "阅读与笔记", "#F5C2E7")
        page.refresh()
        self.assertEqual(page.task_combo.currentData(), self.second)
        self.assertEqual(page.task_title.text(), "阅读与笔记")
        self.assertEqual(page.metric_values["total"].text(), "1h 0m")
        db.delete_records_in_date_range(date(2030, 3, 15), date(2030, 3, 15))
        page.refresh()
        self.assertEqual(page.metric_values["total"].text(), "0s")
        db.delete_mode(self.second)
        db.delete_mode(self.first)
        page.refresh()
        self.assertFalse(page.task_combo.isEnabled())
        self.assertIn("还没有任务标签", page.status_label.text())

    def test_long_trend_buckets_preserve_total_and_empty_gaps(self):
        daily = {"2030-01-01": {"seconds": 1800}, "2030-12-31": {"seconds": 3600}}
        columns, labels, caption = trend_columns(date(2030, 1, 1), date(2030, 12, 31), daily)
        self.assertEqual(caption, "每月投入")
        self.assertEqual(len(columns), 12)
        self.assertEqual(sum(value for _, value in columns), 5400)
        self.assertEqual(columns[1][1], 0)
        self.assertEqual(labels[-1], "2030-12-01 至 2030-12-31")
        columns, _, caption = trend_columns(date(2028, 1, 1), date(2030, 12, 31), daily)
        self.assertEqual(caption, "每年投入")
        self.assertEqual(sum(value for _, value in columns), 5400)

    def test_history_entry_and_day_drilldown_preserve_existing_tabs(self):
        self.insert(self.first, datetime(2030, 3, 15, 9), 3600)
        page = HistoryPage()
        self.widgets.append(page)
        page.resize(760, 620)
        page.show()
        QTest.mouseClick(page.task_view_button, Qt.LeftButton)
        self.assertEqual(page._views.currentIndex(), 1)
        page.task_page._anchor, page.task_page._follow_today = date(2030, 3, 15), False
        page.task_page._refresh_data()
        page.task_page._open_day(0, 0)
        self.assertEqual(page._views.currentIndex(), 0)
        self.assertEqual(page._current_date, date(2030, 3, 15))
        self.assertEqual(page._tabs.count(), 4)
        self.assertEqual(page._tabs.tabText(3), "管理")


if __name__ == "__main__":
    unittest.main()
