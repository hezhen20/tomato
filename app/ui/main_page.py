"""主页面 — 一枚圆环，左右两列安静的数字。"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QScrollArea, QLayout,
)
from PySide6.QtCore import Signal, Qt, QTimer, Slot
from PySide6.QtGui import QPainter
from datetime import date, timedelta
import time

from app.database import (
    break_reminder_enabled,
    break_reminder_grace_minutes,
    break_reminder_interval_minutes,
    break_reminder_message,
    get_modes,
    get_range_summary,
    get_stat_day_summary,
    start_record,
    stat_day,
    stop_record,
)
from app.ui.components import (
    ElidedLabel, HatchChart, LedgerRow, RingDial, Seal, icon,
)
from app.ui.theme import current_theme, theme_colors, mode_display_color
from app.ui.materials import paint_surface

WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
STAT_DAY_HINT = "统计日从 04:00 开始：凌晨 00:00–04:00 仍计入前一天。"


def format_time(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def format_duration(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    if h > 0:
        return f"{h}h {m}m"
    if m > 0:
        return f"{m}m"
    return f"{seconds}s"


class Dock(QFrame):
    """Bottom capsule holding the mode list."""

    def paintEvent(self, event):
        painter = QPainter(self)
        paint_surface(painter, self, radius=self.height() // 2, variant="panel", opacity=236)


class MainPage(QWidget):
    break_reminder_requested = Signal(str, int, str)
    history_requested = Signal()
    task_statistics_requested = Signal(object)
    settings_requested = Signal()

    def __init__(self):
        super().__init__()
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)

        self._elapsed = 0
        self._session_elapsed = 0  # 本次计时段的秒数
        self._autosave_counter = 0  # 自动保存计数器
        self._running = False
        self._paused = False
        self._current_mode = None
        self._current_record_id = None
        self._current_date = stat_day()  # 当前计时所属的统计日（04:00 起算）
        self._mode_buttons = []
        self._continuous_active_seconds = 0
        self._pause_started_at = None
        self._reminder_pending = False
        self._reminder_enabled = True
        self._reminder_interval_minutes = 45
        self._reminder_grace_minutes = 5
        self._reminder_message = ""
        self._ledger_rows = []

        self._setup_ui()
        self._load_reminder_settings()
        self.refresh_modes()
        self.refresh_today_summary()

    # ---------------- layout ----------------
    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(44, 22, 44, 24)

        body = QHBoxLayout()
        body.setSpacing(36)
        root.addLayout(body, 1)

        # left — today's ledger
        self._left = QWidget()
        self._left.setFixedWidth(206)
        left = QVBoxLayout(self._left)
        left.setContentsMargins(0, 6, 0, 0)
        left.setSpacing(0)

        self._today_caption = QLabel("TODAY · 今日")
        self._today_caption.setProperty("class", "monoCaption")
        left.addWidget(self._today_caption)

        total_row = QHBoxLayout()
        total_row.setContentsMargins(0, 6, 0, 0)
        total_row.setSpacing(8)
        self.summary_total = QLabel("0m")
        self.summary_total.setObjectName("todayTotal")
        total_row.addWidget(self.summary_total)
        unit = QLabel("累计")
        unit.setObjectName("todayUnit")
        unit.setAlignment(Qt.AlignBottom)
        total_row.addWidget(unit)
        total_row.addStretch()
        left.addLayout(total_row)

        self._today_sub = QLabel("")
        self._today_sub.setProperty("class", "mutedLabel")
        left.addWidget(self._today_sub)
        left.addSpacing(20)

        self._summary_layout = QVBoxLayout()
        self._summary_layout.setSpacing(0)
        left.addLayout(self._summary_layout)
        left.addStretch()

        seal_row = QHBoxLayout()
        seal_row.setSpacing(12)
        self._seal = Seal("", "周三", 64)
        seal_row.addWidget(self._seal, alignment=Qt.AlignTop)
        self.date_label = QLabel("")
        self.date_label.setProperty("class", "monoCaption")
        self.date_label.setWordWrap(True)
        seal_row.addWidget(self.date_label, alignment=Qt.AlignBottom)
        left.addLayout(seal_row)
        left.addSpacing(8)
        body.addWidget(self._left)

        # center — the dial
        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)
        center_layout.addStretch(1)

        self.state_chip = QLabel("●  准备就绪")
        self.state_chip.setObjectName("stateChip")
        self.state_chip.setAlignment(Qt.AlignCenter)
        center_layout.addWidget(self.state_chip, alignment=Qt.AlignHCenter)
        center_layout.addSpacing(4)

        self._dial = RingDial(496)
        dial_layout = QVBoxLayout(self._dial)
        dial_layout.setContentsMargins(0, 0, 0, 0)
        dial_layout.setSpacing(0)
        dial_layout.addStretch(1)

        self.mode_label = ElidedLabel("准备好，进入心流")
        self.mode_label.setObjectName("modeLabel")
        self.mode_label.setAlignment(Qt.AlignCenter)
        dial_layout.addWidget(self.mode_label)
        dial_layout.addSpacing(14)

        self.timer_label = QLabel("00:00:00")
        self.timer_label.setObjectName("timerLabel")
        self.timer_label.setAlignment(Qt.AlignCenter)
        self.timer_label.setAccessibleName("当前模式今日累计时间")
        dial_layout.addWidget(self.timer_label)
        dial_layout.addSpacing(16)

        self.status_label = QLabel("选择一个模式，开启这一段专注")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setAlignment(Qt.AlignCenter)
        dial_layout.addWidget(self.status_label)
        dial_layout.addStretch(1)
        center_layout.addWidget(self._dial, alignment=Qt.AlignHCenter)

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 26, 0, 0)
        controls.setSpacing(18)
        controls.addStretch(1)
        spacer_left = QWidget()
        spacer_left.setFixedWidth(52)
        controls.addWidget(spacer_left)

        self.start_btn = QPushButton()
        self.start_btn.setObjectName("dialPrimary")
        self.start_btn.setIcon(icon("play", current_theme().colors["on_ink"], 26))
        self.start_btn.setFixedSize(72, 72)
        self.start_btn.setToolTip("开始专注")
        self.start_btn.setAccessibleName("开始专注")
        self.start_btn.clicked.connect(self._start_default_mode)
        controls.addWidget(self.start_btn)

        self.pause_btn = QPushButton()
        self.pause_btn.setObjectName("dialPrimary")
        self.pause_btn.setIcon(icon("pause", current_theme().colors["on_ink"], 26))
        self.pause_btn.setFixedSize(72, 72)
        self.pause_btn.setToolTip("暂停")
        self.pause_btn.setAccessibleName("暂停或继续")
        self.pause_btn.clicked.connect(self.toggle_pause)
        self.pause_btn.setEnabled(False)
        self.pause_btn.hide()
        controls.addWidget(self.pause_btn)

        self.stop_btn = QPushButton()
        self.stop_btn.setObjectName("dialGhost")
        self.stop_btn.setIcon(icon("stop", current_theme().colors["muted"], 20))
        self.stop_btn.setFixedSize(52, 52)
        self.stop_btn.setToolTip("结束计时")
        self.stop_btn.setAccessibleName("结束计时")
        self.stop_btn.clicked.connect(self.stop_timer)
        self.stop_btn.setEnabled(False)
        controls.addWidget(self.stop_btn)

        controls.addStretch(1)
        center_layout.addLayout(controls)

        self._hint = QLabel("数据保存在本机 · 每 30 秒自动保存")
        self._hint.setProperty("class", "monoCaption")
        self._hint.setAlignment(Qt.AlignCenter)
        center_layout.addSpacing(14)
        center_layout.addWidget(self._hint)
        center_layout.addStretch(1)
        body.addWidget(center, 1)

        # right — the week, one quiet chart
        self._right = QWidget()
        self._right.setFixedWidth(250)
        right = QVBoxLayout(self._right)
        right.setContentsMargins(0, 6, 0, 0)
        right.setSpacing(0)

        week_head = QHBoxLayout()
        week_caption = QLabel("本周 · WEEK")
        week_caption.setProperty("class", "monoCaption")
        week_head.addWidget(week_caption)
        week_head.addStretch()
        self._week_total = QLabel("")
        self._week_total.setProperty("class", "weekValue")
        week_head.addWidget(self._week_total)
        right.addLayout(week_head)
        right.addSpacing(10)

        self.week_chart = HatchChart()
        self.week_chart.setFixedHeight(214)
        right.addWidget(self.week_chart)

        self._week_note = QLabel("")
        self._week_note.setProperty("class", "monoCaption")
        self._week_note.setWordWrap(True)
        right.addSpacing(16)
        right.addWidget(self._week_note)
        right.addSpacing(26)

        footer = QHBoxLayout()
        footer.setSpacing(14)
        self.task_stats_btn = QPushButton("任务统计")
        self.task_stats_btn.setObjectName("textButton")
        self.task_stats_btn.setCursor(Qt.PointingHandCursor)
        self.task_stats_btn.setToolTip("查看当前任务的专注时长与时段分布")
        self.task_stats_btn.clicked.connect(lambda: self.task_statistics_requested.emit(
            self._current_mode["id"] if self._current_mode else None
        ))
        footer.addWidget(self.task_stats_btn)
        footer.addStretch()

        history_btn = QPushButton("查看统计  →")
        history_btn.setObjectName("textButton")
        history_btn.setCursor(Qt.PointingHandCursor)
        history_btn.clicked.connect(self.history_requested.emit)
        footer.addWidget(history_btn)
        right.addLayout(footer)
        right.addStretch()
        body.addWidget(self._right)

        # dock
        self._dock = Dock()
        self._dock.setFixedHeight(54)
        dock_layout = QHBoxLayout(self._dock)
        dock_layout.setContentsMargins(10, 6, 8, 6)
        dock_layout.setSpacing(6)

        self._mode_container = QWidget()
        self.modes_layout = QHBoxLayout(self._mode_container)
        self.modes_layout.setContentsMargins(0, 0, 0, 0)
        self.modes_layout.setSpacing(2)
        self.modes_layout.setAlignment(Qt.AlignLeft)
        self.modes_layout.setSizeConstraint(QLayout.SetMinimumSize)
        mode_scroll = QScrollArea()
        mode_scroll.setObjectName("modeScroll")
        mode_scroll.setWidgetResizable(True)
        mode_scroll.setFrameShape(QFrame.NoFrame)
        mode_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        mode_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        mode_scroll.setStyleSheet("QScrollBar:horizontal { height:3px; background:transparent; }")
        mode_scroll.setWidget(self._mode_container)
        dock_layout.addWidget(mode_scroll, 1)

        divider = QFrame()
        divider.setObjectName("sidebarRule")
        divider.setFixedSize(1, 16)
        dock_layout.addWidget(divider)

        self._add_mode_btn = QPushButton("＋")
        self._add_mode_btn.setObjectName("dockAdd")
        self._add_mode_btn.setToolTip("管理模式")
        self._add_mode_btn.setCursor(Qt.PointingHandCursor)
        self._add_mode_btn.clicked.connect(self.settings_requested.emit)
        dock_layout.addWidget(self._add_mode_btn)

        self._dock.setMaximumWidth(760)
        root.addSpacing(18)
        root.addWidget(self._dock, alignment=Qt.AlignHCenter)

        for btn in (self.start_btn, self.pause_btn, self.stop_btn, self._add_mode_btn, self.task_stats_btn):
            btn.setCursor(Qt.PointingHandCursor)

        self._reminder_hint_label = QLabel("")
        self._reminder_hint_label.setProperty("class", "mutedLabel")
        self._reminder_hint_label.hide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_layout()

    def _apply_layout(self):
        compact = self.width() < 1040
        self._left.setVisible(not compact)
        self._right.setVisible(not compact)
        if compact:
            available = min(self.width() - 120, self.height() - 240)
            diameter = max(300, min(400, available))
        else:
            available = min(self.width() - 640, self.height() - 268)
            diameter = max(330, min(496, available))
        if diameter != self._dial.width():
            self._dial.set_diameter(diameter)
            size = int(diameter * 0.173)
            self.timer_label.setStyleSheet(f"font-size:{size}px;")

    # ---------------- data ----------------
    def _start_default_mode(self):
        modes = get_modes()
        mode = next((m for m in modes if self._current_mode and m["id"] == self._current_mode["id"]), None)
        if mode or modes:
            self._on_mode_click(mode or modes[0])
        else:
            self.settings_requested.emit()

    def _update_controls(self):
        self.start_btn.setVisible(not self._running)
        self.pause_btn.setVisible(self._running)
        running_icon = "play" if self._paused else "pause"
        self.pause_btn.setIcon(icon(running_icon, current_theme().colors["on_ink"], 26))
        self.state_chip.setText("●  已暂停" if self._paused else "●  专注进行中" if self._running else "●  准备就绪")
        self.state_chip.setProperty("active", self._running and not self._paused)
        self.state_chip.style().unpolish(self.state_chip)
        self.state_chip.style().polish(self.state_chip)
        self._update_dial()

    def _update_dial(self):
        target_minutes = self._reminder_interval_minutes if self._reminder_enabled else 60
        target = max(60, target_minutes * 60)
        if self._running:
            progress = (self._continuous_active_seconds % target) / target
        else:
            progress = 0.0
        self._dial.set_progress(progress)

    def refresh_theme(self):
        self.start_btn.setIcon(icon("play", current_theme().colors["on_ink"], 26))
        self._update_controls()
        self.stop_btn.setIcon(icon("stop", theme_colors()["muted"], 20))
        self.refresh_modes()
        self.refresh_today_summary()
        self._dial.set_diameter(self._dial.width() - 1)
        self._dial.set_diameter(self._dial.width() + 1)
        self._apply_layout()

    def _load_reminder_settings(self):
        self._reminder_enabled = break_reminder_enabled()
        self._reminder_interval_minutes = break_reminder_interval_minutes()
        self._reminder_grace_minutes = break_reminder_grace_minutes()
        self._reminder_message = break_reminder_message()
        self._update_reminder_hint()

    def reload_reminder_settings(self):
        """设置页保存后刷新本页配置，正在计时也会立即使用新值。"""
        self._load_reminder_settings()
        if not self._reminder_enabled:
            self._reminder_pending = False
        self._update_dial()

    def _update_reminder_hint(self):
        if self._reminder_enabled:
            self._reminder_hint_label.setText(
                f"每 {self._reminder_interval_minutes} 分钟提醒休息 · "
                f"暂停超过 {self._reminder_grace_minutes} 分钟后重新计算提醒"
            )
        else:
            self._reminder_hint_label.setText("休息提醒已关闭，可在设置中重新开启")

    def refresh_modes(self):
        for btn in self._mode_buttons:
            self.modes_layout.removeWidget(btn)
            btn.hide()
            btn.deleteLater()
        self._mode_buttons.clear()

        modes = get_modes()
        current_mode_id = self._current_mode["id"] if self._current_mode else None
        for mode in modes:
            btn = QPushButton(mode["name"])
            btn.setProperty("class", "modeBtn")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setToolTip(mode["name"] + " · 点击开始此模式")
            btn.setMaximumWidth(200)
            btn.setText(btn.fontMetrics().elidedText(mode["name"], Qt.ElideRight, 160))
            btn.clicked.connect(lambda checked, m=mode: self._on_mode_click(m))
            self.modes_layout.addWidget(btn)
            self._mode_buttons.append(btn)
            btn.setChecked(mode["id"] == current_mode_id)

        # Settings may have renamed or recoloured the running mode.
        if current_mode_id is not None:
            latest_mode = next((mode for mode in modes if mode["id"] == current_mode_id), None)
            if latest_mode is not None:
                self._current_mode = latest_mode
                self.mode_label.setText(f"● {latest_mode['name']}")
                self.mode_label.setToolTip(latest_mode["name"])
                self.mode_label.setStyleSheet(f"color: {mode_display_color(latest_mode['color'])};")

    def _on_mode_click(self, mode: dict):
        if self._running and self._current_mode and self._current_mode["id"] == mode["id"]:
            for index, candidate in enumerate(get_modes()):
                if index < len(self._mode_buttons):
                    self._mode_buttons[index].setChecked(candidate["id"] == mode["id"])
            return
        if self._running:
            self._save_current()
        self._start_mode(mode)

    def _get_today_accumulated(self, mode_id: int) -> int:
        """获取当前统计日（04:00–次日 04:00）该模式已累积的秒数"""
        summary = get_stat_day_summary(stat_day())
        modes = get_modes()
        for m in modes:
            if m["id"] == mode_id:
                data = summary.get(m["name"])
                return data["seconds"] if data else 0
        return 0

    def _start_mode(self, mode: dict):
        self._current_mode = mode
        self._current_date = stat_day()
        self._elapsed = self._get_today_accumulated(mode["id"])
        self._session_elapsed = 0
        self._paused = False
        self._running = True
        self._current_record_id = start_record(mode["id"])
        self._continuous_active_seconds = 0
        self._pause_started_at = None
        self._reminder_pending = False

        self.mode_label.setText(f"● {mode['name']}")
        self.mode_label.setToolTip(mode["name"])
        self.mode_label.setStyleSheet(f"color: {mode_display_color(mode['color'])};")
        self.timer_label.setText(format_time(self._elapsed))
        self.status_label.setText("计时中...")
        self.pause_btn.setToolTip("暂停")
        self.pause_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)

        modes = get_modes()
        for i, btn in enumerate(self._mode_buttons):
            if i < len(modes):
                btn.setChecked(modes[i]["id"] == mode["id"])

        self._timer.start()
        self._update_controls()
        self.refresh_today_summary()

    @Slot()
    def toggle_pause(self):
        if not self._running:
            return
        if self._paused:
            today = stat_day()
            if today != self._current_date:
                if self._current_record_id and self._session_elapsed > 0:
                    stop_record(self._current_record_id, self._session_elapsed)
                self._current_date = today
                self._session_elapsed = 0
                self._elapsed = self._get_today_accumulated(self._current_mode["id"])
                self._current_record_id = start_record(self._current_mode["id"])
                self.timer_label.setText(format_time(self._elapsed))
                self.refresh_today_summary()
                self._continuous_active_seconds = 0

            pause_duration = 0
            if self._pause_started_at is not None:
                pause_duration = max(0, time.monotonic() - self._pause_started_at)
            if pause_duration >= self._reminder_grace_minutes * 60:
                self._continuous_active_seconds = 0
            self._pause_started_at = None

            self._paused = False
            self._timer.start()
            self.pause_btn.setToolTip("暂停")
            self.status_label.setText("计时中...")
        else:
            self._paused = True
            self._timer.stop()
            self._pause_started_at = time.monotonic()
            self.pause_btn.setToolTip("继续")
            self.status_label.setText("已暂停")
        self._update_controls()

    @Slot()
    def stop_timer(self):
        if not self._running:
            return
        self._save_current()
        self.status_label.setText("已停止")
        self.pause_btn.setToolTip("暂停")
        self.pause_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self._update_controls()
        self.refresh_today_summary()

    def _save_current(self):
        if self._current_record_id and self._session_elapsed > 0:
            stop_record(self._current_record_id, self._session_elapsed)
        self._timer.stop()
        self._running = False
        self._paused = False
        self._current_record_id = None
        self._pause_started_at = None
        self._reminder_pending = False

    def _reset_ui(self):
        self.mode_label.setText("选择模式开始计时")
        self.mode_label.setStyleSheet("")
        self.timer_label.setText("00:00:00")
        self.status_label.setText("就绪")
        self._update_reminder_hint()
        self.pause_btn.setToolTip("暂停")
        self.pause_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        for btn in self._mode_buttons:
            btn.setChecked(False)
        self._update_controls()

    def _tick(self):
        today = stat_day()
        if today != self._current_date:
            self._handle_day_change(today)
            return
        self._elapsed += 1
        self._session_elapsed += 1
        self._continuous_active_seconds += 1
        self._autosave_counter += 1
        self.timer_label.setText(format_time(self._elapsed))
        self._update_dial()

        if (
            self._reminder_enabled
            and not self._reminder_pending
            and self._continuous_active_seconds >= self._reminder_interval_minutes * 60
        ):
            self._reminder_pending = True
            self.break_reminder_requested.emit(
                self._current_mode["name"],
                self._reminder_interval_minutes,
                self._reminder_message,
            )

        if self._autosave_counter >= 30 and self._current_record_id and self._session_elapsed > 0:
            stop_record(self._current_record_id, self._session_elapsed)
            self._current_record_id = start_record(self._current_mode["id"])
            self._session_elapsed = 0
            self._autosave_counter = 0
            self.refresh_today_summary()

    def _handle_day_change(self, new_date: date):
        """统计日切换（04:00）：保存前一天的记录，开始新一天的记录"""
        if self._current_record_id and self._session_elapsed > 0:
            stop_record(self._current_record_id, self._session_elapsed)

        self._current_date = new_date
        self._session_elapsed = 0
        self._elapsed = self._get_today_accumulated(self._current_mode["id"])
        self._current_record_id = start_record(self._current_mode["id"])
        self._continuous_active_seconds = 0
        self._reminder_pending = False
        self.timer_label.setText(format_time(self._elapsed))
        self.refresh_today_summary()

    def dismiss_break_reminder(self):
        """关闭提醒浮层，仅重置下一次提醒的计数，不改变计时状态。"""
        self._reminder_pending = False
        self._continuous_active_seconds = 0
        self._update_dial()

    # ---------------- today ----------------
    def refresh_today_summary(self):
        for row in self._ledger_rows:
            self._summary_layout.removeWidget(row)
            row.hide()
            row.setParent(None)
            row.deleteLater()
        self._ledger_rows.clear()
        while self._summary_layout.count():
            item = self._summary_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()

        today = stat_day()
        summary = get_stat_day_summary(today)
        if self._running and self._current_mode and self._session_elapsed and self._current_date == today:
            name = self._current_mode["name"]
            entry = summary.setdefault(name, {"seconds": 0, "color": self._current_mode["color"]})
            entry["seconds"] += self._session_elapsed

        if self._current_mode:
            self._elapsed = summary.get(self._current_mode["name"], {}).get("seconds", 0)
            self.timer_label.setText(format_time(self._elapsed))

        total = sum(item["seconds"] for item in summary.values())
        self.summary_total.setText(format_duration(total))
        self._today_sub.setText(
            f"{len(summary)} 个模式 · 最长 {format_duration(max((s['seconds'] for s in summary.values()), default=0))}"
        )
        self._seal.set_text(f"{today.month}.{today.day}", WEEKDAYS[today.weekday()])
        self.date_label.setText(
            f"{today.month}月{today.day}日 · {WEEKDAYS[today.weekday()]}"
            + ("" if today == date.today() else " · 统计日至 04:00")
        )
        self.date_label.setToolTip(STAT_DAY_HINT)
        self._seal.setToolTip(
            f"{today.month}月{today.day}日 · {WEEKDAYS[today.weekday()]}" + ("" if today == date.today() else " · 统计日至 04:00")
        )

        if not summary:
            empty = QLabel("今天还没有记录。\n从第一次专注开始。")
            empty.setProperty("class", "emptyState")
            empty.setWordWrap(True)
            self._summary_layout.addWidget(empty)
        else:
            ordered = sorted(summary.items(), key=lambda item: item[1]["seconds"], reverse=True)
            for name, data in ordered[:5]:
                row = LedgerRow()
                row.set_data(name, mode_display_color(data["color"]), format_duration(data["seconds"]),
                             zero=data["seconds"] == 0)
                self._summary_layout.addWidget(row)
                self._ledger_rows.append(row)
            if len(ordered) > 5:
                more = QLabel(f"另有 {len(ordered) - 5} 个模式")
                more.setProperty("class", "mutedLabel")
                more.setStyleSheet("font-size:10px; padding-top:8px;")
                self._summary_layout.addWidget(more)

        self._refresh_week(today)

    def _refresh_week(self, today: date):
        monday = today - timedelta(days=today.weekday())
        try:
            data = get_range_summary(monday, today)
        except Exception:
            data = {}
        columns = []
        for index in range(7):
            day = monday + timedelta(days=index)
            total = sum(info["seconds"] for info in data.get(day.isoformat(), {}).values())
            columns.append((WEEKDAYS[index][1:], total, day == today))
        self.week_chart.set_columns(columns, caption="本周投入")
        week_total = sum(value for _, value, _ in columns)
        self._week_total.setText(format_duration(week_total))
        best_index = max(range(len(columns)), key=lambda index: columns[index][1])
        if columns[best_index][1]:
            self._week_note.setText(
                f"本周最长的一天是{WEEKDAYS[best_index]}，{format_duration(columns[best_index][1])}。"
            )
        else:
            self._week_note.setText("这一周还没有记录。")

    def switch_to_mode(self, mode_name: str):
        """通过模式名称切换（供快捷键调用）"""
        modes = get_modes()
        for mode in modes:
            if mode["name"] == mode_name:
                if self._running and self._current_mode and self._current_mode["id"] == mode["id"]:
                    self.toggle_pause()
                else:
                    self._on_mode_click(mode)
                return
