"""数据库管理模块"""
import sqlite3
import hashlib
import os
import sys
from contextlib import contextmanager
from datetime import datetime, date, timedelta
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
