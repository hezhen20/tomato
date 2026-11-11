"""04:00 统计日口径回归：计时页必须与历史/任务统计保持一致。"""
import os
import tempfile
import unittest
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

import app.database as db
from app.ui.main_page import MainPage, WEEKDAYS


@contextmanager
def frozen_clock(*moments: datetime):
    """把数据库层读取的当前时间钉在给定时刻，最后一个时刻之后不再走动。

    记录按 start_time + duration_seconds 归入统计日，所以只伪造 stat_day()
    不够：写库的时间戳还是真实时间，凌晨跑测试时那几秒会被算进「今天」，
    断言就会随运行时刻漂移。这里连同记录时间一起固定。
    """
    queue = list(moments)

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            if len(queue) > 1:
                return queue.pop(0)
            return queue[0]

    with patch.object(db, "datetime", FrozenDatetime):
        yield


class StatDayHelperTests(unittest.TestCase):
    def test_stat_day_starts_at_four_am(self):
        self.assertEqual(db.stat_day(datetime(2026, 11, 4, 0, 0)), date(2026, 11, 3))
        self.assertEqual(db.stat_day(datetime(2026, 11, 4, 2, 30)), date(2026, 11, 3))
        self.assertEqual(db.stat_day(datetime(2026, 11, 4, 3, 59, 59)), date(2026, 11, 3))
        self.assertEqual(db.stat_day(datetime(2026, 11, 4, 4, 0)), date(2026, 11, 4))
        self.assertEqual(db.stat_day(datetime(2026, 11, 4, 23, 59)), date(2026, 11, 4))


class _TempDatabaseCase(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(
            db, "DB_PATH", Path(self.directory.name) / "stat_day.db"
        )
        self.db_patch.start()
        db.init_db()
        self.mode = db.get_modes()[0]

    def tearDown(self):
        self.db_patch.stop()
        self.directory.cleanup()

    def insert(self, start: datetime, seconds: int):
        with db._conn() as conn:
            conn.execute(
                "INSERT INTO time_record(mode_id,start_time,end_time,duration_seconds)"
                " VALUES(?,?,?,?)",
                (
                    self.mode["id"],
                    start.isoformat(),
                    (start + timedelta(seconds=seconds)).isoformat(),
                    seconds,
                ),
            )


class StatDaySummaryTests(_TempDatabaseCase):
    def test_after_midnight_hours_stay_with_previous_stat_day(self):
        self.insert(datetime(2026, 11, 3, 23, 0), 2 * 3600)  # 23:00–01:00

        previous = db.get_stat_day_summary(date(2026, 11, 3))
        current = db.get_stat_day_summary(date(2026, 11, 4))

        self.assertEqual(previous[self.mode["name"]]["seconds"], 2 * 3600)
        self.assertEqual(current, {})

    def test_record_crossing_four_am_is_split(self):
        self.insert(datetime(2026, 11, 4, 3, 59), 120)  # 03:59–04:01

        self.assertEqual(
            db.get_stat_day_summary(date(2026, 11, 3))[self.mode["name"]]["seconds"],
            60,
        )
        self.assertEqual(
            db.get_stat_day_summary(date(2026, 11, 4))[self.mode["name"]]["seconds"],
            60,
        )


class TimerPageStatDayTests(_TempDatabaseCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        super().setUp()
        self.page = MainPage()

    def tearDown(self):
        self.page._save_current()
        self.page.deleteLater()
        self.app.processEvents()
        super().tearDown()

    def test_timer_keeps_accumulating_after_midnight(self):
        """00:16 打开计时页时应延续前一天累计，而不是从 0 重新开始。"""
        stat_day = date.today() - timedelta(days=1)
        self.insert(datetime.combine(stat_day, datetime.min.time()) + timedelta(hours=23), 3600)

        with patch("app.ui.main_page.stat_day", return_value=stat_day):
            self.page._start_mode(self.mode)
            self.assertEqual(self.page._current_date, stat_day)
            self.assertEqual(self.page.timer_label.text(), "01:00:00")
            self.assertEqual(self.page.summary_total.text(), "1h 0m")

            self.page._tick()
            self.assertEqual(self.page.timer_label.text(), "01:00:01")

    def test_timer_rolls_over_at_four_am(self):
        """统计日切换时保存前一段并从新一天的累计值继续。

        时钟钉在 03:59:55：五秒专注恰好收在 04:00:00，那 5 秒整个属于前一天，
        新的一天仍是空的，所以切换后读数必须归零。数据库按写入时间归日，
        不钉住时钟的话这个断言只在凌晨 04:00 前成立。
        """
        first_day = date.today() - timedelta(days=1)
        started = datetime.combine(first_day + timedelta(days=1), time(3, 59, 55))

        with frozen_clock(started, started + timedelta(seconds=5)):
            with patch("app.ui.main_page.stat_day", return_value=first_day):
                self.page._start_mode(self.mode)
                for _ in range(5):
                    self.page._tick()
                first_record_id = self.page._current_record_id

            with patch("app.ui.main_page.stat_day", return_value=date.today()):
                self.page._tick()

        with db._conn() as conn:
            saved = conn.execute(
                "SELECT duration_seconds FROM time_record WHERE id=?",
                (first_record_id,),
            ).fetchone()
            restarted_at = conn.execute(
                "SELECT start_time FROM time_record WHERE id=?",
                (self.page._current_record_id,),
            ).fetchone()["start_time"]
        self.assertEqual(saved["duration_seconds"], 5)
        self.assertEqual(self.page._current_date, date.today())
        self.assertEqual(self.page._session_elapsed, 0)
        self.assertEqual(self.page._elapsed, 0)
        self.assertEqual(self.page.timer_label.text(), "00:00:00")
        self.assertIsNotNone(self.page._current_record_id)
        self.assertNotEqual(self.page._current_record_id, first_record_id)

        # 那 5 秒记在前一天，新记录正好从 04:00 开始，所以新一天是空的。
        self.assertEqual(db.get_stat_day_summary(first_day)[self.mode["name"]]["seconds"], 5)
        self.assertEqual(db.get_stat_day_summary(date.today()), {})
        self.assertEqual(restarted_at, (started + timedelta(seconds=5)).isoformat())

    def test_date_badge_explains_the_four_am_cutoff(self):
        stat_day = date.today() - timedelta(days=1)
        with patch("app.ui.main_page.stat_day", return_value=stat_day):
            self.page.refresh_today_summary()

        self.assertEqual(
            self.page.date_label.text(),
            f"{stat_day.month}月{stat_day.day}日 · "
            f"{WEEKDAYS[stat_day.weekday()]} · 统计日至 04:00",
        )
        self.assertIn("04:00", self.page.date_label.toolTip())


if __name__ == "__main__":
    unittest.main()
