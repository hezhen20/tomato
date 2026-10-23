"""数据库管理模块"""
import sqlite3
import hashlib
import os
import sys
from contextlib import contextmanager
from datetime import datetime, date, timedelta, time
from pathlib import Path


def _get_data_dir() -> Path:
    """获取跨平台的数据存储目录"""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "TomatoTimer"
    elif sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "TomatoTimer"
    else:
        # Linux / other
        return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "TomatoTimer"


DB_PATH = _get_data_dir() / "tomato.db"

DEFAULT_MODES = [
    ("工作", "#00F5A0"),
]

PERIOD_KEYS = ("morning", "afternoon", "evening")
PERIOD_LABELS = {
    "morning": "上午",
    "afternoon": "下午",
    "evening": "晚上",
}

MORNING_START = time(4, 0)
AFTERNOON_START = time(12, 0)
EVENING_START = time(18, 0)

# ---- 休息提醒设置 ----
BREAK_REMINDER_ENABLED_KEY = "break_reminder_enabled"
BREAK_REMINDER_INTERVAL_KEY = "break_reminder_interval_minutes"
BREAK_REMINDER_GRACE_KEY = "break_reminder_pause_grace_minutes"
BREAK_REMINDER_MESSAGE_KEY = "break_reminder_message"
BREAK_REMINDER_ENABLED_DEFAULT = "1"
BREAK_REMINDER_INTERVAL_DEFAULT = 45
BREAK_REMINDER_GRACE_DEFAULT = 5
BREAK_REMINDER_MESSAGE_DEFAULT = "45分钟到了，该休息了，喝点水活动一下吧，身体第一哦！"


@contextmanager
def _conn():
    """安全的数据库连接管理，确保连接始终关闭"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_connection():
    """保留供外部直接使用（如测试），但推荐用 _conn()"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    with _conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS user (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS mode (
                id INTEGER PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                color TEXT NOT NULL DEFAULT '#00F5A0',
                sort_order INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS time_record (
                id INTEGER PRIMARY KEY,
                mode_id INTEGER NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT,
                duration_seconds INTEGER DEFAULT 0,
                FOREIGN KEY (mode_id) REFERENCES mode(id)
            );
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)
        for i, (name, color) in enumerate(DEFAULT_MODES):
            conn.execute(
                "INSERT OR IGNORE INTO mode (name, color, sort_order) VALUES (?, ?, ?)",
                (name, color, i),
            )


def hash_password(password: str) -> str:
    salt = "tomato_fixed_salt"
    return hashlib.sha256((password + salt).encode()).hexdigest()


# ---- 用户 ----
def create_user(username: str, password: str):
    with _conn() as conn:
        conn.execute(
            "INSERT INTO user (username, password_hash) VALUES (?, ?)",
            (username, hash_password(password)),
        )


def verify_user(username: str, password: str) -> bool:
    with _conn() as conn:
        row = conn.execute(
            "SELECT password_hash FROM user WHERE username = ?", (username,)
        ).fetchone()
    if row is None:
        return False
    return row["password_hash"] == hash_password(password)


def user_exists(username: str = None) -> bool:
    with _conn() as conn:
        if username:
            row = conn.execute("SELECT COUNT(*) as cnt FROM user WHERE username=?", (username,)).fetchone()
        else:
            row = conn.execute("SELECT COUNT(*) as cnt FROM user").fetchone()
    return row["cnt"] > 0


def change_password(username: str, new_password: str):
    with _conn() as conn:
        conn.execute(
            "UPDATE user SET password_hash = ? WHERE username = ?",
            (hash_password(new_password), username),
        )


# ---- 模式 ----
def get_modes() -> list:
    with _conn() as conn:
        rows = conn.execute("SELECT * FROM mode ORDER BY sort_order").fetchall()
    return [dict(r) for r in rows]


def add_mode(name: str, color: str) -> int:
    with _conn() as conn:
        c = conn.execute(
            "INSERT INTO mode (name, color, sort_order) VALUES (?, ?, (SELECT COALESCE(MAX(sort_order),0)+1 FROM mode))",
            (name, color),
        )
        return c.lastrowid


def update_mode(mode_id: int, name: str, color: str):
    with _conn() as conn:
        conn.execute("UPDATE mode SET name=?, color=? WHERE id=?", (name, color, mode_id))


def delete_mode(mode_id: int):
    with _conn() as conn:
        conn.execute("DELETE FROM mode WHERE id=?", (mode_id,))


# ---- 计时记录 ----
def start_record(mode_id: int) -> int:
    with _conn() as conn:
        c = conn.execute(
            "INSERT INTO time_record (mode_id, start_time) VALUES (?, ?)",
            (mode_id, datetime.now().isoformat()),
        )
        return c.lastrowid


def stop_record(record_id: int, elapsed_seconds: int):
    with _conn() as conn:
        conn.execute(
            "UPDATE time_record SET end_time=?, duration_seconds=? WHERE id=?",
            (datetime.now().isoformat(), elapsed_seconds, record_id),
        )


def get_records_for_date(d: date) -> list:
    with _conn() as conn:
        start = datetime(d.year, d.month, d.day).isoformat()
        end = datetime(d.year, d.month, d.day, 23, 59, 59).isoformat()
        rows = conn.execute(
            """SELECT tr.*, m.name as mode_name, m.color as mode_color
               FROM time_record tr JOIN mode m ON tr.mode_id = m.id
               WHERE tr.start_time BETWEEN ? AND ?
               ORDER BY tr.start_time""",
            (start, end),
        ).fetchall()
    return [dict(r) for r in rows]


def get_records_in_date_range(start_date: date, end_date: date) -> list:
    """返回日期范围内可清理的已完成记录，按最新开始时间倒序。"""
    if end_date < start_date:
        return []
    return get_records_in_datetime_range(
        datetime.combine(start_date, time.min),
        datetime.combine(end_date + timedelta(days=1), time.min),
    )


def delete_records_in_date_range(start_date: date, end_date: date) -> int:
    """删除日期范围内已完成的记录，返回实际删除条数。"""
    if end_date < start_date:
        return 0
    return delete_records_in_datetime_range(
        datetime.combine(start_date, time.min),
        datetime.combine(end_date + timedelta(days=1), time.min),
    )


def get_records_in_datetime_range(start_at: datetime, end_at: datetime) -> list:
    """返回 [start_at, end_at) 内可清理的已完成记录，按最新开始时间倒序。"""
    if end_at <= start_at:
        return []

    with _conn() as conn:
        rows = conn.execute(
            """SELECT tr.id, tr.start_time, tr.end_time, tr.duration_seconds,
                      COALESCE(m.name, '已删除模式') as mode_name,
                      COALESCE(m.color, '#A8B3C7') as mode_color
               FROM time_record tr
               LEFT JOIN mode m ON tr.mode_id = m.id
               WHERE tr.start_time >= ?
                 AND tr.start_time < ?
                 AND tr.end_time IS NOT NULL
                 AND COALESCE(tr.duration_seconds, 0) > 0
               ORDER BY tr.start_time DESC""",
            (start_at.isoformat(), end_at.isoformat()),
        ).fetchall()
    return [dict(r) for r in rows]


def delete_records_in_datetime_range(start_at: datetime, end_at: datetime) -> int:
    """删除 [start_at, end_at) 内已完成的记录，返回实际删除条数。"""
    if end_at <= start_at:
        return 0

    with _conn() as conn:
        cursor = conn.execute(
            """DELETE FROM time_record
               WHERE start_time >= ?
                 AND start_time < ?
                 AND end_time IS NOT NULL
                 AND COALESCE(duration_seconds, 0) > 0""",
            (start_at.isoformat(), end_at.isoformat()),
        )
        return cursor.rowcount


def get_daily_summary(d: date) -> dict:
    """返回某天各模式的总时长 {mode_name: {seconds, color}}"""
    records = get_records_for_date(d)
    summary = {}
    for r in records:
        name = r["mode_name"]
        if name not in summary:
            summary[name] = {"seconds": 0, "color": r["mode_color"]}
        summary[name]["seconds"] += r["duration_seconds"]
    return summary


def get_range_summary(start_date: date, end_date: date) -> dict:
    """返回日期范围内每天各模式的总时长"""
    result = {}
    with _conn() as conn:
        start = datetime(start_date.year, start_date.month, start_date.day).isoformat()
        end = datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59).isoformat()
        rows = conn.execute(
            """SELECT date(tr.start_time) as day, m.name as mode_name, m.color as mode_color,
                      SUM(tr.duration_seconds) as total_seconds
               FROM time_record tr JOIN mode m ON tr.mode_id = m.id
               WHERE tr.start_time BETWEEN ? AND ?
               GROUP BY day, m.name
               ORDER BY day""",
            (start, end),
        ).fetchall()
    for r in rows:
        day = r["day"]
        if day not in result:
            result[day] = {}
        result[day][r["mode_name"]] = {
            "seconds": r["total_seconds"],
            "color": r["mode_color"],
        }
    return result


def _period_for_datetime(dt: datetime):
    """返回时间点所属的统计日、时段 key、当前时段结束时间。"""
    current_day = dt.date()
    current_time = dt.time()

    if MORNING_START <= current_time < AFTERNOON_START:
        return current_day, "morning", datetime.combine(current_day, AFTERNOON_START)
    if AFTERNOON_START <= current_time < EVENING_START:
        return current_day, "afternoon", datetime.combine(current_day, EVENING_START)
    if current_time >= EVENING_START:
        return current_day, "evening", datetime.combine(current_day + timedelta(days=1), MORNING_START)
    return current_day - timedelta(days=1), "evening", datetime.combine(current_day, MORNING_START)


def _split_record_periods(start_dt: datetime, duration_seconds: int) -> list:
    """把单条计时记录按上午/下午/晚上切分。"""
    if not duration_seconds or duration_seconds <= 0:
        return []

    end_dt = start_dt + timedelta(seconds=duration_seconds)
    cursor = start_dt
    pieces = []

    while cursor < end_dt:
        stat_day, period_key, period_end = _period_for_datetime(cursor)
        next_cursor = min(period_end, end_dt)
        seconds = (next_cursor - cursor).total_seconds()
        if seconds > 0:
            pieces.append((stat_day.isoformat(), period_key, seconds))
        if next_cursor <= cursor:
            break
        cursor = next_cursor

    return pieces


def _normalize_period_seconds(periods: dict) -> dict:
    """转成整数秒，并保证三个时段之和等于原始总秒数。"""
    exact = {key: float(periods.get(key, 0) or 0) for key in PERIOD_KEYS}
    normalized = {key: int(exact[key]) for key in PERIOD_KEYS}
    target_total = int(round(sum(exact.values())))
    remainder = target_total - sum(normalized.values())

    if remainder > 0:
        order = sorted(
            PERIOD_KEYS,
            key=lambda key: exact[key] - normalized[key],
            reverse=True,
        )
        for i in range(remainder):
            normalized[order[i % len(order)]] += 1

    return normalized


def get_range_period_summary(start_date: date, end_date: date) -> dict:
    """返回日期范围内每天各模式的上午/下午/晚上时长。"""
    if end_date < start_date:
        return {}

    window_start = datetime.combine(start_date, MORNING_START)
    window_end = datetime.combine(end_date + timedelta(days=1), MORNING_START)
    result = {}

    with _conn() as conn:
        rows = conn.execute(
            """SELECT tr.*, m.name as mode_name, m.color as mode_color
               FROM time_record tr JOIN mode m ON tr.mode_id = m.id
               WHERE COALESCE(tr.duration_seconds, 0) > 0
                 AND julianday(tr.start_time) < julianday(?)
                 AND julianday(tr.start_time) + (COALESCE(tr.duration_seconds, 0) / 86400.0) > julianday(?)
               ORDER BY tr.start_time""",
            (window_end.isoformat(), window_start.isoformat()),
        ).fetchall()

    for r in rows:
        start_dt = datetime.fromisoformat(r["start_time"])
        duration_seconds = int(r["duration_seconds"] or 0)
        for day, period_key, seconds in _split_record_periods(start_dt, duration_seconds):
            if day < start_date.isoformat() or day > end_date.isoformat():
                continue
            if day not in result:
                result[day] = {}
            name = r["mode_name"]
            if name not in result[day]:
                result[day][name] = {
                    "seconds": 0.0,
                    "color": r["mode_color"],
                    "periods": {key: 0.0 for key in PERIOD_KEYS},
                }
            result[day][name]["periods"][period_key] += seconds
            result[day][name]["seconds"] += seconds

    normalized_result = {}
    for day, modes in result.items():
        normalized_result[day] = {}
        for name, info in modes.items():
            periods = _normalize_period_seconds(info["periods"])
            normalized_result[day][name] = {
                "seconds": sum(periods.values()),
                "color": info["color"],
                "periods": periods,
            }

    return normalized_result


# ---- 设置 ----
def get_setting(key: str, default: str = "") -> str:
    with _conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str):
    with _conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value)
        )


def set_settings(values: dict[str, str]):
    """Save related preferences atomically, including appearance mode and accent."""
    with _conn() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            values.items(),
        )


def _setting_int(key: str, default: int, minimum: int, maximum: int) -> int:
    """读取并约束整数设置，避免旧配置或手工修改导致异常。"""
    try:
        value = int(get_setting(key, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def break_reminder_enabled() -> bool:
    return get_setting(
        BREAK_REMINDER_ENABLED_KEY,
        BREAK_REMINDER_ENABLED_DEFAULT,
    ).strip() != "0"


def break_reminder_interval_minutes() -> int:
    return _setting_int(BREAK_REMINDER_INTERVAL_KEY, BREAK_REMINDER_INTERVAL_DEFAULT, 5, 240)


def break_reminder_grace_minutes() -> int:
    return _setting_int(BREAK_REMINDER_GRACE_KEY, BREAK_REMINDER_GRACE_DEFAULT, 0, 60)


def break_reminder_message() -> str:
    value = get_setting(BREAK_REMINDER_MESSAGE_KEY, BREAK_REMINDER_MESSAGE_DEFAULT).strip()
    return value or BREAK_REMINDER_MESSAGE_DEFAULT
