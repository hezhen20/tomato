"""核心功能测试 - 保护计时逻辑、累积逻辑、跨天切割"""
import unittest
import os
import sqlite3
import tempfile
from datetime import date, datetime, timedelta
from unittest.mock import patch, MagicMock
from pathlib import Path

# 使用临时数据库，不影响正式数据
import tempfile
_test_db = tempfile.mktemp(suffix=".db")
os.environ["TOMATO_TEST_DB"] = _test_db
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# patch 数据库路径后再导入
import app.database as db
db.DB_PATH = Path(_test_db)

from app.database import (
    init_db, create_user, verify_user, user_exists,
    get_modes, add_mode, delete_mode,
    start_record, stop_record,
    get_daily_summary, get_records_for_date, get_range_summary, get_range_period_summary,
    get_setting, set_setting,
)
from PySide6.QtWidgets import QApplication
from app.ui.history_page import HistoryPage, format_period_detail
from app.hotkeys import HotkeyManager, mode_action_name


def setUpModule():
    init_db()
    create_user("test", "test123")


def tearDownModule():
    try:
        os.unlink(_test_db)
    except OSError:
        pass


class TestUserAuth(unittest.TestCase):
    """用户认证测试"""

    def test_user_exists(self):
        self.assertTrue(user_exists())

    def test_verify_correct_password(self):
        self.assertTrue(verify_user("test", "test123"))

    def test_verify_wrong_password(self):
        self.assertFalse(verify_user("test", "wrong"))

    def test_verify_wrong_username(self):
        self.assertFalse(verify_user("nobody", "test123"))


class TestModeManagement(unittest.TestCase):
    """模式管理测试"""

    def test_default_mode_exists(self):
        modes = get_modes()
        names = [m["name"] for m in modes]
        self.assertIn("工作", names)

    def test_add_and_delete_mode(self):
        mode_id = add_mode("测试模式", "#FF0000")
        modes = get_modes()
        names = [m["name"] for m in modes]
        self.assertIn("测试模式", names)

        delete_mode(mode_id)
        modes = get_modes()
        names = [m["name"] for m in modes]
        self.assertNotIn("测试模式", names)

    def test_add_duplicate_mode_fails(self):
        add_mode("唯一模式", "#000000")
        with self.assertRaises(Exception):
            add_mode("唯一模式", "#111111")
        # cleanup
        modes = get_modes()
        for m in modes:
            if m["name"] == "唯一模式":
                delete_mode(m["id"])


class TestTimeRecording(unittest.TestCase):
    """计时记录测试 - 核心中的核心"""

    def setUp(self):
        self.mode_id = get_modes()[0]["id"]

    def test_start_and_stop_record(self):
        """基本计时：开始 -> 停止，记录应正确保存"""
        record_id = start_record(self.mode_id)
        self.assertIsNotNone(record_id)

        stop_record(record_id, 120)  # 2分钟

        records = get_records_for_date(date.today())
        found = [r for r in records if r["id"] == record_id]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["duration_seconds"], 120)
        self.assertIsNotNone(found[0]["end_time"])

    def test_multiple_sessions_accumulate(self):
        """多次计时应累积：工作30s + 工作60s = 总计90s"""
        r1 = start_record(self.mode_id)
        stop_record(r1, 30)

        r2 = start_record(self.mode_id)
        stop_record(r2, 60)

        summary = get_daily_summary(date.today())
        mode_name = get_modes()[0]["name"]
        self.assertIn(mode_name, summary)
        # 至少包含这两段的时间（可能还有其他测试的记录）
        self.assertGreaterEqual(summary[mode_name]["seconds"], 90)

    def test_zero_duration_not_lost(self):
        """0秒记录也应该被保存"""
        record_id = start_record(self.mode_id)
        stop_record(record_id, 0)

        records = get_records_for_date(date.today())
        found = [r for r in records if r["id"] == record_id]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["duration_seconds"], 0)


class TestDailySummary(unittest.TestCase):
    """每日统计测试"""

    def test_summary_groups_by_mode(self):
        """不同模式的时间应分开统计"""
        mode_id_1 = get_modes()[0]["id"]
        mode_id_2 = add_mode("统计测试模式", "#00FF00")

        r1 = start_record(mode_id_1)
        stop_record(r1, 100)

        r2 = start_record(mode_id_2)
        stop_record(r2, 200)

        summary = get_daily_summary(date.today())
        self.assertIn("统计测试模式", summary)
        self.assertEqual(summary["统计测试模式"]["seconds"], 200)

        # cleanup
        delete_mode(mode_id_2)

    def test_empty_day_returns_empty(self):
        """没有记录的日期应返回空字典"""
        far_date = date(2020, 1, 1)
        summary = get_daily_summary(far_date)
        self.assertEqual(summary, {})


class TestCrossDayLogic(unittest.TestCase):
    """跨天切割逻辑测试 - 关键保护"""

    def test_records_belong_to_correct_date(self):
        """记录应归属到正确的日期"""
        mode_id = get_modes()[0]["id"]

        # 模拟昨天的记录
        yesterday = date.today() - timedelta(days=1)
        with db._conn() as conn:
            yesterday_start = datetime(yesterday.year, yesterday.month, yesterday.day, 23, 0, 0)
            yesterday_end = datetime(yesterday.year, yesterday.month, yesterday.day, 23, 30, 0)
            conn.execute(
                "INSERT INTO time_record (mode_id, start_time, end_time, duration_seconds) VALUES (?, ?, ?, ?)",
                (mode_id, yesterday_start.isoformat(), yesterday_end.isoformat(), 1800),
            )

        # 昨天的记录不应出现在今天
        today_records = get_records_for_date(date.today())
        yesterday_records = get_records_for_date(yesterday)

        today_starts = [r["start_time"] for r in today_records]
        self.assertTrue(
            all(not s.startswith(yesterday.isoformat()) for s in today_starts),
            "Today should not contain yesterday's records"
        )
        self.assertTrue(
            any(r["duration_seconds"] == 1800 for r in yesterday_records),
            "Yesterday should contain the 1800s record"
        )

    def test_range_summary_spans_multiple_days(self):
        """范围统计应覆盖多天"""
        mode_id = get_modes()[0]["id"]
        today = date.today()
        start = today - timedelta(days=6)

        result = get_range_summary(start, today)
        # 应该是一个字典，key 是日期字符串
        self.assertIsInstance(result, dict)


class TestRangePeriodSummary(unittest.TestCase):
    """周/月分时段统计口径测试"""

    def setUp(self):
        self.mode = get_modes()[0]

    def _insert_record(self, start: datetime, duration_seconds: int):
        with db._conn() as conn:
            conn.execute(
                "INSERT INTO time_record (mode_id, start_time, end_time, duration_seconds) VALUES (?, ?, ?, ?)",
                (
                    self.mode["id"],
                    start.isoformat(),
                    (start + timedelta(seconds=duration_seconds)).isoformat(),
                    duration_seconds,
                ),
            )

    def _mode_info(self, result: dict, d: date):
        return result[d.isoformat()][self.mode["name"]]

    def test_midday_record_splits_between_morning_and_afternoon(self):
        d = date(2030, 1, 1)
        self._insert_record(datetime(2030, 1, 1, 11, 30), 3600)

        result = get_range_period_summary(d, d)
        info = self._mode_info(result, d)

        self.assertEqual(info["periods"]["morning"], 1800)
        self.assertEqual(info["periods"]["afternoon"], 1800)
        self.assertEqual(info["periods"]["evening"], 0)
        self.assertEqual(info["seconds"], 3600)

    def test_after_midnight_before_four_belongs_to_previous_evening(self):
        d = date(2030, 1, 2)
        next_day = d + timedelta(days=1)
        self._insert_record(datetime(2030, 1, 2, 23, 0), 3 * 3600)

        result = get_range_period_summary(d, d)
        info = self._mode_info(result, d)
        next_result = get_range_period_summary(next_day, next_day)

        self.assertEqual(info["periods"]["morning"], 0)
        self.assertEqual(info["periods"]["afternoon"], 0)
        self.assertEqual(info["periods"]["evening"], 3 * 3600)
        self.assertEqual(info["seconds"], 3 * 3600)
        self.assertNotIn(next_day.isoformat(), next_result)

    def test_autosaved_midnight_records_still_belong_to_previous_evening(self):
        d = date(2030, 1, 4)
        next_day = d + timedelta(days=1)
        self._insert_record(datetime(2030, 1, 4, 23, 0), 3600)
        self._insert_record(datetime(2030, 1, 5, 0, 0), 2 * 3600)

        result = get_range_period_summary(d, d)
        info = self._mode_info(result, d)
        next_result = get_range_period_summary(next_day, next_day)

        self.assertEqual(info["periods"]["evening"], 3 * 3600)
        self.assertEqual(info["seconds"], 3 * 3600)
        self.assertNotIn(next_day.isoformat(), next_result)

    def test_week_boundary_night_is_not_counted_twice(self):
        first_day = date(2030, 2, 1)
        sunday = first_day + timedelta(days=(6 - first_day.weekday()) % 7)
        monday = sunday - timedelta(days=6)
        next_monday = sunday + timedelta(days=1)
        next_sunday = next_monday + timedelta(days=6)
        self._insert_record(datetime(sunday.year, sunday.month, sunday.day, 23, 0), 3 * 3600)

        this_week = get_range_period_summary(monday, sunday)
        next_week = get_range_period_summary(next_monday, next_sunday)
        info = self._mode_info(this_week, sunday)

        self.assertEqual(info["periods"]["evening"], 3 * 3600)
        self.assertNotIn(sunday.isoformat(), next_week)
        self.assertNotIn(next_monday.isoformat(), next_week)

    def test_month_boundary_night_is_not_counted_twice(self):
        month_end = date(2030, 3, 31)
        next_month_start = date(2030, 4, 1)
        next_month_end = date(2030, 4, 30)
        self._insert_record(datetime(2030, 3, 31, 23, 0), 3 * 3600)

        this_month = get_range_period_summary(date(2030, 3, 1), month_end)
        next_month = get_range_period_summary(next_month_start, next_month_end)
        info = self._mode_info(this_month, month_end)

        self.assertEqual(info["periods"]["evening"], 3 * 3600)
        self.assertNotIn(month_end.isoformat(), next_month)
        self.assertNotIn(next_month_start.isoformat(), next_month)


class TestHistoryPeriodDetailFormatting(unittest.TestCase):
    """历史页时段明细展示格式测试"""

    def test_period_detail_uses_line_breaks(self):
        text = format_period_detail({
            "morning": 1800,
            "afternoon": 0,
            "evening": 7200,
        })

        self.assertEqual(text, "上午 30m\n下午 0m\n晚上 2h 0m")


class TestHistoryPageUi(unittest.TestCase):
    """历史页 UI 结构烟测"""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _insert_record(self, start: datetime, duration_seconds: int):
        mode = get_modes()[0]
        with db._conn() as conn:
            conn.execute(
                "INSERT INTO time_record (mode_id, start_time, end_time, duration_seconds) VALUES (?, ?, ?, ?)",
                (
                    mode["id"],
                    start.isoformat(),
                    (start + timedelta(seconds=duration_seconds)).isoformat(),
                    duration_seconds,
                ),
            )

    def test_day_tab_uses_cards_instead_of_detail_table(self):
        page = HistoryPage()
        try:
            self.assertFalse(hasattr(page, "day_table"))
            page._current_date = date(2031, 1, 1)
            page._refresh_day()
            self.assertEqual(page.day_period_layout.count(), 3)
        finally:
            page.deleteLater()

    def test_week_detail_cell_is_compact_with_tooltip(self):
        self._insert_record(datetime(2031, 1, 2, 11, 30), 3600)
        page = HistoryPage()
        try:
            page._current_date = date(2031, 1, 2)
            page._refresh_week()
            self.assertEqual(page.week_table.columnCount(), 4)
            self.assertFalse(page.week_table.wordWrap())
            self.assertGreaterEqual(page.week_table.rowCount(), 1)
            item = page.week_table.item(0, 2)
            self.assertEqual(item.text(), "查看")
            self.assertIn("上午", item.toolTip())
            self.assertIn("\n", item.toolTip())
        finally:
            page.deleteLater()


class TestAccumulationLogic(unittest.TestCase):
    """累积逻辑测试 - 确保切换模式后时间不丢失"""

    def test_switch_mode_preserves_previous(self):
        """切换模式后，前一个模式的记录应完整保存"""
        modes = get_modes()
        if len(modes) < 2:
            mode_id_2 = add_mode("累积测试", "#0000FF")
        else:
            mode_id_2 = modes[1]["id"]

        mode_id_1 = modes[0]["id"]

        # 模式1计时45秒
        r1 = start_record(mode_id_1)
        stop_record(r1, 45)

        # 切到模式2计时30秒
        r2 = start_record(mode_id_2)
        stop_record(r2, 30)

        # 切回模式1计时15秒
        r3 = start_record(mode_id_1)
        stop_record(r3, 15)

        # 模式1总计应 >= 60秒 (45+15)
        summary = get_daily_summary(date.today())
        mode_name = modes[0]["name"]
        self.assertGreaterEqual(summary[mode_name]["seconds"], 60)

    def test_session_elapsed_vs_total_elapsed(self):
        """session_elapsed 只记录本段，不是累积总时长"""
        mode_id = get_modes()[0]["id"]

        r1 = start_record(mode_id)
        stop_record(r1, 100)  # 第一段100秒

        r2 = start_record(mode_id)
        stop_record(r2, 50)   # 第二段50秒，不是150秒

        # 查第二条记录
        records = get_records_for_date(date.today())
        found = [r for r in records if r["id"] == r2]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["duration_seconds"], 50)


class TestHotkeyManagement(unittest.TestCase):
    """模式快捷键同步测试"""

    def setUp(self):
        self.manager = HotkeyManager()

    def test_sync_adds_hotkey_slot_for_new_mode(self):
        mode_name = "快捷键新增模式"
        mode_id = add_mode(mode_name, "#123456")
        try:
            changed = self.manager.sync_mode_hotkeys()
            self.assertTrue(changed)
            self.assertIn(mode_action_name(mode_name), self.manager.get_all_hotkeys())
            self.assertEqual(self.manager.get_hotkey(mode_action_name(mode_name)), "")
        finally:
            delete_mode(mode_id)
            self.manager.sync_mode_hotkeys()

    def test_sync_removes_hotkey_for_deleted_mode(self):
        mode_name = "快捷键删除模式"
        mode_id = add_mode(mode_name, "#654321")
        action = mode_action_name(mode_name)
        try:
            self.manager.sync_mode_hotkeys()
            self.manager.set_hotkey(action, "<ctrl>+<alt>+1")

            delete_mode(mode_id)

            changed = self.manager.sync_mode_hotkeys()
            self.assertTrue(changed)
            self.assertNotIn(action, self.manager.get_all_hotkeys())
            self.assertEqual(self.manager.get_hotkey(action), "")
        finally:
            if any(mode["id"] == mode_id for mode in get_modes()):
                delete_mode(mode_id)
            self.manager.sync_mode_hotkeys()


class TestSettingsStorage(unittest.TestCase):
    """设置项持久化测试"""

    def test_setting_default_and_replace(self):
        key = "test_setting_storage"
        self.assertEqual(get_setting(key, "fallback"), "fallback")

        set_setting(key, "1")
        self.assertEqual(get_setting(key, "0"), "1")

        set_setting(key, "0")
        self.assertEqual(get_setting(key, "1"), "0")


if __name__ == "__main__":
    unittest.main()
