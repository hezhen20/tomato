"""以已有计时模式为任务标签的独立统计视图。"""
from calendar import monthrange
from datetime import date, timedelta

from PySide6.QtCore import QDate, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QFrame, QGridLayout, QHBoxLayout, QHeaderView,
    QLabel, QProgressBar, QPushButton, QSizePolicy, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from app.database import (
    PERIOD_KEYS, PERIOD_LABELS, get_mode_date_bounds, get_modes,
    get_range_period_summary, stat_day,
)
from app.ui.components import ActivityChart, ElidedLabel, icon
from app.ui.theme import mode_display_color


def duration_text(seconds: int) -> str:
    """短时专注也显示秒数，完整精度另在工具提示中保留。"""
    hours, rest = divmod(int(seconds), 3600)
    minutes, seconds = divmod(rest, 60)
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m" if minutes else f"{seconds}s"


def exact_duration(seconds: int) -> str:
    hours, rest = divmod(int(seconds), 3600)
    minutes, seconds = divmod(rest, 60)
    return f"{hours}小时 {minutes}分钟 {seconds}秒"


def trend_columns(start: date, end: date, daily: dict):
    """长范围按周、月或年汇总；保留空档和每根柱子的精确日期范围。"""
    days = (end - start).days + 1
    months = (end.year - start.year) * 12 + end.month - start.month + 1
    unit = "日" if days <= 31 else "周" if days <= 210 else "月" if months <= 31 else "年"
    columns, details = [], []
    cursor = start
    while cursor <= end:
        if unit == "日":
            stop = cursor
            label = cursor.strftime("%m/%d")
        elif unit == "周":
            stop = min(end, cursor + timedelta(days=6 - cursor.weekday()))
            label = cursor.strftime("%m/%d")
        elif unit == "月":
            stop = min(end, cursor.replace(day=monthrange(cursor.year, cursor.month)[1]))
            label = cursor.strftime("%y/%m")
        else:
            stop = min(end, date(cursor.year, 12, 31))
            label = str(cursor.year)
        total = sum(info["seconds"] for day, info in daily.items() if cursor.isoformat() <= day <= stop.isoformat())
        columns.append((label, total))
        details.append(cursor.isoformat() if cursor == stop else f"{cursor.isoformat()} 至 {stop.isoformat()}")
        cursor = stop + timedelta(days=1)
    return columns, details, f"每{unit}投入"


class StatsComboBox(QComboBox):
    """在明暗主题中保留清晰的下拉指示。"""
    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        icon("chevron-down").paint(painter, self.width() - 24, (self.height() - 16) // 2, 16, 16)


class TaskStatsPage(QWidget):
    day_requested = Signal(object)

    def __init__(self):
        super().__init__()
        self._anchor = self._today()
        self._follow_today = True
        self._daily = {}
        self._setup_ui()
        self._timer = QTimer(self)
        self._timer.setInterval(30_000)
        self._timer.timeout.connect(self.refresh)

    @staticmethod
    def _today():
        return stat_day()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 18, 4, 8)
        layout.setSpacing(16)

        selector = QHBoxLayout()
        caption = QLabel("任务标签")
        selector.addWidget(caption)
        self.task_combo = StatsComboBox()
        self.task_combo.setAccessibleName("选择要统计的任务标签")
        self.task_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.task_combo.setMinimumContentsLength(8)
        self.task_combo.setMinimumWidth(0)
        self.task_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        caption.setBuddy(self.task_combo)
        self.task_combo.currentIndexChanged.connect(self._refresh_data)
        selector.addWidget(self.task_combo, 1)
        self.refresh_button = QPushButton("刷新")
        self.refresh_button.clicked.connect(self.refresh)
        selector.addWidget(self.refresh_button)
        layout.addLayout(selector)

        title_row = QHBoxLayout()
        self.task_title = ElidedLabel("选择一个任务，回看专注轨迹")
        self.task_title.setProperty("class", "settingsTitle")
        title_row.addWidget(self.task_title, 1)
        self.range_combo = StatsComboBox()
        self.range_combo.setAccessibleName("任务统计时间范围")
        for label, key in (("今日", "day"), ("本周", "week"), ("本月", "month"), ("全部记录", "all"), ("自定义", "custom")):
            self.range_combo.addItem(label, key)
        self.range_combo.setCurrentIndex(2)
        self.range_combo.currentIndexChanged.connect(self._refresh_data)
        title_row.addWidget(self.range_combo)
        layout.addLayout(title_row)

        dates = QHBoxLayout()
        dates.setSpacing(6)
        self.prev_button = QPushButton()
        self.prev_button.setObjectName("navArrowButton")
        self.prev_button.setToolTip("上一时段")
        self.prev_button.setAccessibleName("上一时段")
        self.prev_button.clicked.connect(lambda: self._navigate(-1))
        dates.addWidget(self.prev_button)
        self.start_edit = self._date_edit("统计开始日期")
        dates.addWidget(self.start_edit, 1)
        dates.addWidget(QLabel("至"))
        self.end_edit = self._date_edit("统计结束日期")
        dates.addWidget(self.end_edit, 1)
        self.next_button = QPushButton()
        self.next_button.setObjectName("navArrowButton")
        self.next_button.setToolTip("下一时段")
        self.next_button.setAccessibleName("下一时段")
        self.next_button.clicked.connect(lambda: self._navigate(1))
        dates.addWidget(self.next_button)
        self.current_button = QPushButton("回到本期")
        self.current_button.clicked.connect(self._return_to_current)
        dates.addWidget(self.current_button)
        layout.addLayout(dates)

        self.status_label = QLabel()
        self.status_label.setObjectName("taskStatsStatus")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        summary = QFrame()
        summary.setObjectName("taskStatsSummary")
        metrics = QGridLayout(summary)
        metrics.setContentsMargins(16, 14, 16, 14)
        metrics.setHorizontalSpacing(12)
        self.metric_values = {}
        for col, (key, text) in enumerate((("total", "累计专注"), ("days", "专注天数"), ("average", "专注日均"), ("peak", "单日最高"))):
            label = QLabel(text)
            label.setProperty("class", "mutedLabel")
            metrics.addWidget(label, 0, col)
            value = QLabel("—")
            value.setObjectName("taskMetricValue")
            metrics.addWidget(value, 1, col)
            metrics.setColumnStretch(col, 1)
            self.metric_values[key] = value
        self.metric_values["average"].setToolTip("累计时长 ÷ 有专注记录的天数")
        layout.addWidget(summary)

        periods_heading = QLabel("时段分布")
        periods_heading.setProperty("class", "sectionTitle")
        layout.addWidget(periods_heading)
        periods_row = QHBoxLayout()
        periods_row.setSpacing(10)
        self.period_values, self.period_bars, self.period_shares = {}, {}, {}
        for key, time_range in zip(PERIOD_KEYS, ("04:00–12:00", "12:00–18:00", "18:00–次日04:00")):
            card = QFrame()
            card.setObjectName("periodCard")
            body = QVBoxLayout(card)
            body.setContentsMargins(12, 12, 12, 12)
            body.setSpacing(7)
            name = QLabel(PERIOD_LABELS[key])
            name.setProperty("class", "periodTitle")
            body.addWidget(name)
            span = QLabel(time_range)
            span.setProperty("class", "periodRange")
            body.addWidget(span)
            value = QLabel("0s")
            value.setObjectName("taskMetricValue")
            body.addWidget(value)
            bar = QProgressBar()
            bar.setObjectName("taskPeriodBar")
            bar.setRange(0, 1000)
            bar.setTextVisible(False)
            bar.setFixedHeight(5)
            body.addWidget(bar)
            share = QLabel("占比 0%")
            share.setProperty("class", "mutedLabel")
            body.addWidget(share)
            self.period_values[key], self.period_bars[key], self.period_shares[key] = value, bar, share
            periods_row.addWidget(card, 1)
        layout.addLayout(periods_row)

        self.insight_label = QLabel()
        self.insight_label.setProperty("class", "mutedLabel")
        self.insight_label.setWordWrap(True)
        layout.addWidget(self.insight_label)

        self.chart = ActivityChart()
        self.chart.setAccessibleName("当前任务专注时长趋势")
        layout.addWidget(self.chart)

        detail_label = QLabel("每日明细 · 仅列有专注的日期，最新在前；双击回看当日全部任务。")
        detail_label.setProperty("class", "mutedLabel")
        detail_label.setWordWrap(True)
        layout.addWidget(detail_label)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["统计日期", "上午", "下午", "晚上", "合计"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.setMinimumHeight(220)
        self.table.cellDoubleClicked.connect(self._open_day)
        layout.addWidget(self.table)

        note = QLabel("统计日从 04:00 开始；凌晨 00:00–04:00 归入前一天晚上。跨时段自动拆分，暂停不计入时长。\n统计使用已保存记录，计时中约每 30 秒更新。专注日均只计算有记录的日期。")
        note.setProperty("class", "mutedLabel")
        note.setWordWrap(True)
        layout.addWidget(note)
        for button in self.findChildren(QPushButton):
            button.setCursor(Qt.PointingHandCursor)
        self.refresh_theme()

    def _date_edit(self, name):
        edit = QDateEdit(QDate.currentDate())
        edit.setCalendarPopup(True)
        edit.setDisplayFormat("yyyy/MM/dd")
        edit.setMinimumDate(QDate(1900, 1, 1))
        edit.setMaximumDate(QDate(9998, 12, 31))
        edit.setMinimumWidth(120)
        edit.setAccessibleName(name)
        edit.dateChanged.connect(self._refresh_data)
        return edit

    def refresh_theme(self):
        self.prev_button.setIcon(icon("chevron-left"))
        self.next_button.setIcon(icon("chevron-right"))
        self._refresh_data()

    def refresh(self):
        selected = self.task_combo.currentData()
        modes = get_modes()
        self.task_combo.blockSignals(True)
        self.task_combo.clear()
        for mode in modes:
            self.task_combo.addItem(mode["name"], mode["id"])
            self.task_combo.setItemData(self.task_combo.count() - 1, mode["name"], Qt.ToolTipRole)
        index = self.task_combo.findData(selected)
        self.task_combo.setCurrentIndex(index if index >= 0 else (0 if modes else -1))
        self.task_combo.blockSignals(False)
        self.task_combo.setEnabled(bool(modes))
        if self._follow_today:
            self._anchor = self._today()
        self._refresh_data()

    def select_task(self, mode_id=None):
        self.refresh()
        if mode_id is not None:
            self.task_combo.setCurrentIndex(self.task_combo.findData(mode_id))

    def _set_dates(self, start, end):
        for edit, day in ((self.start_edit, start), (self.end_edit, end)):
            edit.blockSignals(True)
            edit.setDate(QDate(day.year, day.month, day.day))
            edit.blockSignals(False)

    def _date_range(self):
        key = self.range_combo.currentData()
        anchor = self._anchor
        if key == "day":
            return anchor, anchor
        if key == "week":
            start = anchor - timedelta(days=anchor.weekday())
            return start, start + timedelta(days=6)
        if key == "month":
            return anchor.replace(day=1), anchor.replace(day=monthrange(anchor.year, anchor.month)[1])
        if key == "all":
            return get_mode_date_bounds(self.task_combo.currentData()) or (self._today(), self._today())
        return self.start_edit.date().toPython(), self.end_edit.date().toPython()

    def _navigate(self, direction):
        key = self.range_combo.currentData()
        if key == "all":
            return
        start, end = self._date_range()
        if key == "month":
            month_index = start.year * 12 + start.month - 1 + direction
            year, month = divmod(month_index, 12)
            if not 1900 <= year <= 9998:
                return
            self._anchor = date(year, month + 1, 1)
        else:
            shift = timedelta(days=((end - start).days + 1) * direction)
            if start + shift < date(1900, 1, 1) or end + shift > date(9998, 12, 31):
                return
            self._anchor = start + shift
            if key == "custom":
                self._set_dates(start + shift, end + shift)
        self._follow_today = False
        self._refresh_data()

    def _return_to_current(self):
        self._anchor, self._follow_today = self._today(), True
        if self.range_combo.currentData() == "custom":
            self.range_combo.setCurrentIndex(2)
        self._refresh_data()

    def _refresh_data(self, *_):
        if not hasattr(self, "table"):
            return
        mode_id = self.task_combo.currentData()
        key = self.range_combo.currentData()
        start, end = self._date_range()
        self.start_edit.setEnabled(key == "custom")
        self.end_edit.setEnabled(key == "custom")
        if key != "custom":
            self._set_dates(start, end)
        valid = start <= end
        for button in (self.prev_button, self.next_button):
            button.setEnabled(mode_id is not None and key != "all" and valid)
        self.current_button.setEnabled(mode_id is not None and key != "all")
        self._daily = {}
        if mode_id is not None and valid:
            data = get_range_period_summary(start, end, mode_id=mode_id)
            self._daily = {day: info for day, modes in data.items() for info in modes.values() if info["seconds"] > 0}
        total = sum(info["seconds"] for info in self._daily.values())
        count = len(self._daily)
        peak_day = max(self._daily, key=lambda day: self._daily[day]["seconds"], default=None)
        peak = self._daily[peak_day]["seconds"] if peak_day else 0
        title = self.task_combo.currentText() if mode_id is not None else "还没有任务标签"
        self.task_title.setText(title)
        self.task_title.setToolTip(title)
        self.task_combo.setToolTip(title)
        self.metric_values["total"].setText(duration_text(total))
        self.metric_values["total"].setToolTip(exact_duration(total))
        self.metric_values["days"].setText(f"{count} 天")
        average = total // count if count else 0
        self.metric_values["average"].setText(duration_text(average))
        self.metric_values["average"].setToolTip(f"累计时长 ÷ 有专注记录的天数\n{exact_duration(average)}")
        self.metric_values["peak"].setText(duration_text(peak))
        self.metric_values["peak"].setToolTip(f"{peak_day or '暂无记录'}\n{exact_duration(peak)}")
        period_totals = {key: sum(info["periods"][key] for info in self._daily.values()) for key in PERIOD_KEYS}
        for period, seconds in period_totals.items():
            self.period_values[period].setText(duration_text(seconds))
            self.period_values[period].setToolTip(exact_duration(seconds))
            share = seconds / total if total else 0
            self.period_bars[period].setValue(round(share * 1000))
            self.period_shares[period].setText(f"占比 {share:.1%}")
        if mode_id is None:
            message = "还没有任务标签，请先到偏好设置添加专注模式。"
        elif not valid:
            message = "开始日期不能晚于结束日期，请调整日期范围。"
        elif not total:
            message = "这个任务在所选范围内还没有专注记录。试试其他日期或「全部记录」。"
        else:
            message = f"{start:%Y/%m/%d} — {end:%Y/%m/%d} · {count} 个有专注的统计日"
        self.status_label.setText(message)
        if total:
            best_periods = "、".join(PERIOD_LABELS[p] for p in PERIOD_KEYS if period_totals[p] == max(period_totals.values()))
            self.insight_label.setText(f"投入最多的时段：{best_periods} · 单日最高：{peak_day}，{duration_text(peak)}")
        else:
            self.insight_label.setText("有记录后，这里会显示投入最多的时段与专注最高的一天。")
        columns, details, caption = trend_columns(start, end, self._daily) if valid and mode_id is not None else ([], [], "每日投入")
        self.chart.set_days(columns, detail_labels=details, value_label=caption)
        self._populate_table()

    def _populate_table(self):
        self.table.setRowCount(len(self._daily))
        for row, day in enumerate(sorted(self._daily, reverse=True)):
            info = self._daily[day]
            date_item = QTableWidgetItem(day.replace("-", "/"))
            date_item.setData(Qt.UserRole, day)
            date_item.setToolTip("双击回看当日全部任务")
            self.table.setItem(row, 0, date_item)
            for col, seconds in enumerate([info["periods"][p] for p in PERIOD_KEYS] + [info["seconds"]], 1):
                item = QTableWidgetItem(duration_text(seconds))
                item.setTextAlignment(Qt.AlignCenter)
                item.setToolTip(exact_duration(seconds))
                if col == 4:
                    item.setForeground(QColor(mode_display_color(info["color"])))
                self.table.setItem(row, col, item)

    def _open_day(self, row, _column):
        item = self.table.item(row, 0)
        if item:
            self.day_requested.emit(date.fromisoformat(item.data(Qt.UserRole)))

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()
        self._timer.start()

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)
