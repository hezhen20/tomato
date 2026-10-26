"""主页面 - 计时器"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QSizePolicy,
    QScrollArea, QProgressBar, QLayout,
)
from PySide6.QtCore import Signal, Qt, QTimer, Slot
from datetime import date
import time

from app.database import (
    break_reminder_enabled,
    break_reminder_grace_minutes,
    break_reminder_interval_minutes,
    break_reminder_message,
    get_daily_summary,
    get_modes,
    start_record,
    stop_record,
)
from app.ui.colors import mix_color, readable_color
from app.ui.components import ElidedLabel, icon, page_header, scroll_page
from app.ui.theme import current_theme, theme_colors, mode_display_color
from app.ui.materials import FrostedSurface

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
    return f"{m}m"


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
        self._current_date = date.today()  # 当前计时所属日期
        self._mode_buttons = []
        self._continuous_active_seconds = 0
        self._pause_started_at = None
        self._reminder_pending = False
        self._reminder_enabled = True
        self._reminder_interval_minutes = 45
        self._reminder_grace_minutes = 5
        self._reminder_message = ""

        self._setup_ui()
        self._load_reminder_settings()
        self.refresh_modes()
        self.refresh_today_summary()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(24)
        layout.setContentsMargins(32, 28, 32, 20)
        self.date_label = QLabel()
        self.date_label.setObjectName("dateBadge")
        layout.addWidget(page_header("专注计时", "一次只做一件事，让每一份投入都有迹可循。", self.date_label))

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(24)
        layout.addWidget(scroll_page(body), 1)

        timer_card = FrostedSurface()
        self._timer_card = timer_card
        timer_card.setObjectName("timerCard")
        timer_layout = QVBoxLayout(timer_card)
        timer_layout.setSpacing(0)
        timer_layout.setContentsMargins(28, 22, 28, 24)
        top = QHBoxLayout()
        self.state_chip = QLabel("●  准备就绪")
        self.state_chip.setObjectName("stateChip")
        top.addWidget(self.state_chip, alignment=Qt.AlignLeft)
        top.addStretch()
        caption = QLabel("今日模式累计")
        caption.setProperty("class", "mutedLabel")
        top.addWidget(caption)
        timer_layout.addLayout(top)
        timer_layout.addSpacing(24)

        self.mode_label = ElidedLabel("准备好，进入心流")
        self.mode_label.setObjectName("modeLabel")
        self.mode_label.setAlignment(Qt.AlignCenter)
        timer_layout.addWidget(self.mode_label)
        timer_layout.addSpacing(8)

        self.timer_label = QLabel("00:00:00")
        self.timer_label.setObjectName("timerLabel")
        self.timer_label.setAlignment(Qt.AlignCenter)
        self.timer_label.setAccessibleName("当前模式今日累计时间")
        timer_layout.addWidget(self.timer_label)
        timer_layout.addSpacing(5)

        self.status_label = QLabel("选择一个模式，开启这一段专注")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setAlignment(Qt.AlignCenter)
        timer_layout.addWidget(self.status_label)
        timer_layout.addSpacing(28)

        mode_header = QHBoxLayout()
        mode_caption = QLabel("专注模式")
        mode_caption.setProperty("class", "mutedLabel")
        mode_header.addWidget(mode_caption)
        mode_header.addStretch()
        manage = QPushButton("管理模式")
        manage.setObjectName("textButton")
        manage.setCursor(Qt.PointingHandCursor)
        manage.clicked.connect(self.settings_requested.emit)
        mode_header.addWidget(manage)
        timer_layout.addLayout(mode_header)
        timer_layout.addSpacing(8)

        mode_container = QWidget()
        self.modes_layout = QHBoxLayout(mode_container)
        self.modes_layout.setContentsMargins(0, 0, 0, 0)
        self.modes_layout.setSpacing(8)
        self.modes_layout.setAlignment(Qt.AlignLeft)
        self.modes_layout.setSizeConstraint(QLayout.SetMinimumSize)
        mode_scroll = QScrollArea()
        mode_scroll.setObjectName("modeScroll")
        mode_scroll.setWidgetResizable(True)
        mode_scroll.setFrameShape(QFrame.NoFrame)
        mode_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        mode_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        mode_scroll.setFixedHeight(58)
        mode_scroll.setWidget(mode_container)
        timer_layout.addWidget(mode_scroll)
        timer_layout.addSpacing(14)

        ctrl_layout = QHBoxLayout()
        ctrl_layout.setSpacing(10)
        self.start_btn = QPushButton("开始专注")
        self.start_btn.setObjectName("primaryButton")
        self.start_btn.setIcon(icon("play", current_theme().colors["on_accent"]))
        self.start_btn.setMinimumHeight(44)
        self.start_btn.clicked.connect(self._start_default_mode)
        ctrl_layout.addWidget(self.start_btn, 1)

        self.pause_btn = QPushButton("暂停")
        self.pause_btn.setObjectName("btnPause")
        self.pause_btn.setIcon(icon("pause", current_theme().colors["on_accent"]))
        self.pause_btn.setMinimumHeight(44)
        self.pause_btn.clicked.connect(self.toggle_pause)
        self.pause_btn.setEnabled(False)
        self.pause_btn.hide()
        ctrl_layout.addWidget(self.pause_btn, 1)

        self.stop_btn = QPushButton("结束计时")
        self.stop_btn.setObjectName("btnStop")
        self.stop_btn.setIcon(icon("stop"))
        self.stop_btn.setMinimumHeight(44)
        self.stop_btn.clicked.connect(self.stop_timer)
        self.stop_btn.setEnabled(False)
        ctrl_layout.addWidget(self.stop_btn)

        timer_layout.addLayout(ctrl_layout)
        body_layout.addWidget(timer_card)

        reminder_row = QHBoxLayout()
        reminder_icon = QLabel()
        reminder_icon.setPixmap(icon("coffee").pixmap(16, 16))
        reminder_row.addWidget(reminder_icon)
        self.reminder_hint_label = QLabel("")
        self.reminder_hint_label.setObjectName("reminderHintLabel")
        self.reminder_hint_label.setWordWrap(True)
        reminder_row.addWidget(self.reminder_hint_label, 1)
        body_layout.addLayout(reminder_row)

        summary_card = QFrame()
        summary_card.setObjectName("summaryCard")
        summary_card_layout = QVBoxLayout(summary_card)
        summary_card_layout.setSpacing(16)
        summary_card_layout.setContentsMargins(0, 0, 0, 0)
        summary_top = QHBoxLayout()
        heading = QLabel("今日概览")
        heading.setProperty("class", "sectionTitle")
        summary_top.addWidget(heading)
        self.summary_total = QLabel("0m")
        self.summary_total.setObjectName("todayTotal")
        summary_top.addWidget(self.summary_total)
        summary_top.addStretch()
        self.task_stats_btn = QPushButton("任务统计")
        self.task_stats_btn.setObjectName("textButton")
        self.task_stats_btn.setCursor(Qt.PointingHandCursor)
        self.task_stats_btn.setToolTip("查看当前任务的专注时长与时段分布")
        self.task_stats_btn.clicked.connect(lambda: self.task_statistics_requested.emit(
            self._current_mode["id"] if self._current_mode else None
        ))
        summary_top.addWidget(self.task_stats_btn)
        history_btn = QPushButton("查看统计  →")
        history_btn.setObjectName("textButton")
        history_btn.setCursor(Qt.PointingHandCursor)
        history_btn.clicked.connect(self.history_requested.emit)
        summary_top.addWidget(history_btn)
        summary_card_layout.addLayout(summary_top)

        self.summary_layout = QVBoxLayout()
        self.summary_layout.setSpacing(12)
        summary_card_layout.addLayout(self.summary_layout)
        body_layout.addWidget(summary_card)
        body_layout.addStretch()
        for btn in (self.start_btn, self.pause_btn, self.stop_btn):
            btn.setCursor(Qt.PointingHandCursor)

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
        self.pause_btn.setIcon(icon("play" if self._paused else "pause", current_theme().colors["on_accent"]))
        self.state_chip.setText("●  已暂停" if self._paused else "●  专注进行中" if self._running else "●  准备就绪")
        self.state_chip.setProperty("active", self._running and not self._paused)
        self.state_chip.style().unpolish(self.state_chip)
        self.state_chip.style().polish(self.state_chip)

    def refresh_theme(self):
        self.start_btn.setIcon(icon("play", current_theme().colors["on_accent"]))
        self._update_controls()
        self.refresh_modes()
        self.refresh_today_summary()
        self.stop_btn.setIcon(icon("stop"))
        self._timer_card.update()

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

    def _update_reminder_hint(self):
        if self._reminder_enabled:
            self.reminder_hint_label.setText(
                f"每 {self._reminder_interval_minutes} 分钟提醒休息 · "
                f"暂停超过 {self._reminder_grace_minutes} 分钟后重新计算提醒"
            )
        else:
            self.reminder_hint_label.setText("休息提醒已关闭，可在设置中重新开启")

    def refresh_modes(self):
        # 清除旧按钮
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
            color = mode["color"]
            roles = theme_colors()
            checked_background = mix_color(color, roles["surface"], 0.88)
            display_color = readable_color(color, checked_background)
            bg_color = roles["surface_alt"]
            hover_color = roles["hover"]
            border_color = roles["border"]
            btn.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: {bg_color};
                    color: {roles['text']};
                    border: 1px solid {border_color};
                    border-radius: 7px;
                    padding: 4px 16px;
                    font-size: 13px;
                    font-weight: 500;
                    min-height: 28px;
                }}
                QPushButton:hover {{
                    background-color: {hover_color};
                }}
                QPushButton:checked {{
                    background-color: {checked_background};
                    color: {display_color};
                    border-color: {mix_color(display_color, roles['surface'], 0.6)};
                }}
                QPushButton:focus {{ border-color: {roles['accent']}; }}
                """
            )
            btn.clicked.connect(lambda checked, m=mode: self._on_mode_click(m))
            self.modes_layout.addWidget(btn)
            self._mode_buttons.append(btn)
            btn.setChecked(mode["id"] == current_mode_id)

        self.start_btn.setText("开始专注" if modes else "添加第一个模式")

        # 设置页修改模式名称/颜色后，正在计时的页面也立即使用最新数据。
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
        # 如果正在计时，先停止当前的
        if self._running:
            self._save_current()
        self._start_mode(mode)

    def _get_today_accumulated(self, mode_id: int) -> int:
        """获取今天该模式已累积的秒数"""
        summary = get_daily_summary(date.today())
        modes = get_modes()
        for m in modes:
            if m["id"] == mode_id:
                data = summary.get(m["name"])
                return data["seconds"] if data else 0
        return 0

    def _start_mode(self, mode: dict):
        self._current_mode = mode
        self._current_date = date.today()
        # 从今天已有记录累积，而不是从零开始
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
        self.pause_btn.setText("暂停")
        self.pause_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)

        # 更新按钮选中状态
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
            # 恢复前检测跨天
            today = date.today()
            if today != self._current_date:
                # 保存旧记录到昨天
                if self._current_record_id and self._session_elapsed > 0:
                    stop_record(self._current_record_id, self._session_elapsed)
                # 新一天重新开始
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
            self.pause_btn.setText("暂停")
            self.status_label.setText("计时中...")
        else:
            self._paused = True
            self._timer.stop()
            self._pause_started_at = time.monotonic()
            self.pause_btn.setText("继续")
            self.status_label.setText("已暂停")
        self._update_controls()

    @Slot()
    def stop_timer(self):
        if not self._running:
            return
        self._save_current()
        # 停止后保留当前累积时间显示，不清零
        self.status_label.setText("已停止")
        self.pause_btn.setText("暂停")
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
        self.pause_btn.setText("暂停")
        self.pause_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        for btn in self._mode_buttons:
            btn.setChecked(False)
        self._update_controls()

    def _tick(self):
        today = date.today()
        if today != self._current_date:
            self._handle_day_change(today)
            return
        self._elapsed += 1
        self._session_elapsed += 1
        self._continuous_active_seconds += 1
        self._autosave_counter += 1
        self.timer_label.setText(format_time(self._elapsed))

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

        # 每30秒自动保存一次当前进度
        if self._autosave_counter >= 30 and self._current_record_id and self._session_elapsed > 0:
            stop_record(self._current_record_id, self._session_elapsed)
            # 开一条新记录接着计
            self._current_record_id = start_record(self._current_mode["id"])
            self._session_elapsed = 0
            self._autosave_counter = 0
            self.refresh_today_summary()

    def _handle_day_change(self, new_date: date):
        """跨天自动切割：保存昨天的记录，开始新一天的记录"""
        # 保存到昨天
        if self._current_record_id and self._session_elapsed > 0:
            stop_record(self._current_record_id, self._session_elapsed)

        # 新的一天，重新开始
        self._current_date = new_date
        self._session_elapsed = 0
        self._elapsed = 0  # 新一天从0开始
        self._current_record_id = start_record(self._current_mode["id"])
        self._continuous_active_seconds = 0
        self._reminder_pending = False
        self.timer_label.setText(format_time(self._elapsed))
        self.refresh_today_summary()

    def dismiss_break_reminder(self):
        """关闭提醒浮层，仅重置下一次提醒的计数，不改变计时状态。"""
        self._reminder_pending = False
        self._continuous_active_seconds = 0

    def refresh_today_summary(self):
        # 清除旧内容
        while self.summary_layout.count():
            item = self.summary_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        today = date.today()
        summary = get_daily_summary(today)
        if self._running and self._current_mode and self._session_elapsed and self._current_date == today:
            name = self._current_mode["name"]
            entry = summary.setdefault(name, {"seconds": 0, "color": self._current_mode["color"]})
            entry["seconds"] += self._session_elapsed

        # 累计显示与概览共用同一份数据，删除已保存记录后不再沿用旧累计值。
        # 尚未保存的当前段仅在计时（含暂停）时计入，停止后已落库，不重复累加。
        if self._current_mode:
            self._elapsed = summary.get(self._current_mode["name"], {}).get("seconds", 0)
            self.timer_label.setText(format_time(self._elapsed))

        total = sum(item["seconds"] for item in summary.values())
        self.summary_total.setText(format_duration(total))
        self.date_label.setText(f"{today.month}月{today.day}日 · " + ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][today.weekday()])
        if not summary:
            lbl = QLabel("今天的故事，从第一次专注开始。\n开始计时后，你的投入会在这里慢慢积累。")
            lbl.setProperty("class", "emptyState")
            lbl.setAlignment(Qt.AlignCenter)
            self.summary_layout.addWidget(lbl)
            return

        for name, data in summary.items():
            display_color = mode_display_color(data["color"], theme_colors()["window"])
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {display_color}; font-size: 16px;")
            dot.setFixedWidth(20)
            row.addWidget(dot)

            name_lbl = ElidedLabel(name)
            row.addWidget(name_lbl, 1)

            bar = QProgressBar()
            bar.setRange(0, max(1, total))
            bar.setValue(data["seconds"])
            bar.setTextVisible(False)
            bar.setFixedHeight(5)
            bar.setStyleSheet(f"QProgressBar {{ background: {theme_colors()['track']}; border: none; border-radius: 2px; }} QProgressBar::chunk {{ background: {display_color}; border-radius: 2px; }}")
            row.addWidget(bar, 2)
            row.addSpacing(20)

            time_lbl = QLabel(format_duration(data["seconds"]))
            time_lbl.setStyleSheet(f"color: {theme_colors()['text']}; font-size: 13px;")
            time_lbl.setMinimumWidth(70)
            time_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            row.addWidget(time_lbl)

            container = QWidget()
            container.setProperty("class", "summaryRow")
            container.setLayout(row)
            self.summary_layout.addWidget(container)

    def switch_to_mode(self, mode_name: str):
        """通过模式名称切换（供快捷键调用）
        - 当前没在计时 → 启动该模式
        - 当前正在计时且是同一模式 → 暂停/恢复
        - 当前正在计时但是不同模式 → 切换到新模式
        """
        modes = get_modes()
        for mode in modes:
            if mode["name"] == mode_name:
                if self._running and self._current_mode and self._current_mode["id"] == mode["id"]:
                    self.toggle_pause()
                else:
                    self._on_mode_click(mode)
                return
