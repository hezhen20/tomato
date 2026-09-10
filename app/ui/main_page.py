"""主页面 - 计时器"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QSizePolicy,
)
from PySide6.QtCore import Signal, Qt, QTimer, Slot
from datetime import date

from app.database import get_modes, start_record, stop_record, get_daily_summary
from app.ui.colors import foreground_for, mix_color, readable_color

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

        self._setup_ui()
        self.refresh_modes()
        self.refresh_today_summary()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        timer_card = QFrame()
        timer_card.setObjectName("timerCard")
        timer_layout = QVBoxLayout(timer_card)
        timer_layout.setSpacing(14)
        timer_layout.setContentsMargins(22, 22, 22, 22)

        title = QLabel("当前计时")
        title.setProperty("class", "sectionTitle")
        title.setAlignment(Qt.AlignCenter)
        timer_layout.addWidget(title)

        # 当前模式标签
        self.mode_label = QLabel("选择模式开始计时")
        self.mode_label.setObjectName("modeLabel")
        self.mode_label.setAlignment(Qt.AlignCenter)
        timer_layout.addWidget(self.mode_label)

        # 计时器显示
        self.timer_label = QLabel("00:00:00")
        self.timer_label.setObjectName("timerLabel")
        self.timer_label.setAlignment(Qt.AlignCenter)
        timer_layout.addWidget(self.timer_label)

        # 状态标签
        self.status_label = QLabel("就绪")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setAlignment(Qt.AlignCenter)
        timer_layout.addWidget(self.status_label)

        # 模式按钮区域
        self.modes_layout = QHBoxLayout()
        self.modes_layout.setSpacing(10)
        self.modes_layout.setAlignment(Qt.AlignCenter)
        timer_layout.addLayout(self.modes_layout)

        # 控制按钮
        ctrl_layout = QHBoxLayout()
        ctrl_layout.setSpacing(10)
        ctrl_layout.setAlignment(Qt.AlignCenter)

        self.pause_btn = QPushButton("暂停")
        self.pause_btn.setObjectName("btnPause")
        self.pause_btn.setFixedWidth(110)
        self.pause_btn.clicked.connect(self.toggle_pause)
        self.pause_btn.setEnabled(False)
        ctrl_layout.addWidget(self.pause_btn)

        self.stop_btn = QPushButton("结束")
        self.stop_btn.setObjectName("btnStop")
        self.stop_btn.setFixedWidth(110)
        self.stop_btn.clicked.connect(self.stop_timer)
        self.stop_btn.setEnabled(False)
        ctrl_layout.addWidget(self.stop_btn)

        timer_layout.addLayout(ctrl_layout)
        layout.addWidget(timer_card)

        summary_card = QFrame()
        summary_card.setObjectName("summaryCard")
        summary_card_layout = QVBoxLayout(summary_card)
        summary_card_layout.setSpacing(10)
        summary_card_layout.setContentsMargins(18, 18, 18, 18)

        # 今日统计
        sep = QLabel("今日统计")
        sep.setProperty("class", "sectionTitle")
        summary_card_layout.addWidget(sep)

        self.summary_layout = QVBoxLayout()
        self.summary_layout.setSpacing(8)
        summary_card_layout.addLayout(self.summary_layout)
        layout.addWidget(summary_card)

        layout.addStretch()

    def refresh_modes(self):
        # 清除旧按钮
        for btn in self._mode_buttons:
            btn.deleteLater()
        self._mode_buttons.clear()

        modes = get_modes()
        for mode in modes:
            btn = QPushButton(mode["name"])
            btn.setProperty("class", "modeBtn")
            btn.setCheckable(True)
            color = mode["color"]
            display_color = readable_color(color)
            bg_color = mix_color(color, "#0D1220", 0.74)
            hover_color = mix_color(color, "#102636", 0.66)
            border_color = mix_color(display_color, "#0D1220", 0.45)
            checked_text_color = foreground_for(color)
            btn.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: {bg_color};
                    color: {display_color};
                    border: 1px solid {border_color};
                    border-radius: 17px;
                    padding: 6px 18px;
                    font-size: 13px;
                    font-weight: 700;
                    min-height: 32px;
                }}
                QPushButton:hover {{
                    background-color: {hover_color};
                }}
                QPushButton:checked {{
                    background-color: {color};
                    color: {checked_text_color};
                    border-color: {color};
                }}
                """
            )
            btn.clicked.connect(lambda checked, m=mode: self._on_mode_click(m))
            self.modes_layout.addWidget(btn)
            self._mode_buttons.append(btn)

    def _on_mode_click(self, mode: dict):
        if self._running and self._current_mode and self._current_mode["id"] == mode["id"]:
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

        self.mode_label.setText(f"● {mode['name']}")
        self.mode_label.setStyleSheet(f"color: {readable_color(mode['color'])};")
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

            self._paused = False
            self._timer.start()
            self.pause_btn.setText("暂停")
            self.status_label.setText("计时中...")
        else:
            self._paused = True
            self._timer.stop()
            self.pause_btn.setText("继续")
            self.status_label.setText("已暂停")

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
        self.refresh_today_summary()

    def _save_current(self):
        if self._current_record_id and self._session_elapsed > 0:
            stop_record(self._current_record_id, self._session_elapsed)
        self._timer.stop()
        self._running = False
        self._paused = False
        self._current_record_id = None

    def _reset_ui(self):
        self.mode_label.setText("选择模式开始计时")
        self.mode_label.setStyleSheet("")
        self.timer_label.setText("00:00:00")
        self.status_label.setText("就绪")
        self.pause_btn.setText("暂停")
        self.pause_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        for btn in self._mode_buttons:
            btn.setChecked(False)

    def _tick(self):
        today = date.today()
        if today != self._current_date:
            self._handle_day_change(today)
            return
        self._elapsed += 1
        self._session_elapsed += 1
        self._autosave_counter += 1
        self.timer_label.setText(format_time(self._elapsed))

        # 每30秒自动保存一次当前进度
        if self._autosave_counter >= 30 and self._current_record_id and self._session_elapsed > 0:
            stop_record(self._current_record_id, self._session_elapsed)
            # 开一条新记录接着计
            self._current_record_id = start_record(self._current_mode["id"])
            self._session_elapsed = 0
            self._autosave_counter = 0

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
        self.timer_label.setText(format_time(self._elapsed))
        self.refresh_today_summary()

    def refresh_today_summary(self):
        # 清除旧内容
        while self.summary_layout.count():
            item = self.summary_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        summary = get_daily_summary(date.today())
        if not summary:
            lbl = QLabel("今天还没有记录，选择一个模式开始计时")
            lbl.setProperty("class", "emptyState")
            lbl.setAlignment(Qt.AlignCenter)
            self.summary_layout.addWidget(lbl)
            return

        for name, data in summary.items():
            display_color = readable_color(data["color"])
            row = QHBoxLayout()
            row.setContentsMargins(12, 8, 12, 8)
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {display_color}; font-size: 16px;")
            dot.setFixedWidth(20)
            row.addWidget(dot)

            name_lbl = QLabel(name)
            name_lbl.setStyleSheet("color: #F8FAFC; font-size: 14px;")
            row.addWidget(name_lbl)

            row.addStretch()

            time_lbl = QLabel(format_duration(data["seconds"]))
            time_lbl.setStyleSheet(f"color: {display_color}; font-size: 14px; font-weight: bold;")
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
