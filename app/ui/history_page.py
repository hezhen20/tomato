"""历史统计页面"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QTabWidget, QHeaderView, QFrame,
    QToolTip, QSizePolicy,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QCursor
from datetime import date, timedelta

from app.database import (
    PERIOD_KEYS,
    PERIOD_LABELS,
    get_range_period_summary,
)
from app.ui.colors import readable_color


def format_duration(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    if h > 0:
        return f"{h}h {m}m"
    return f"{m}m"


def format_period_detail(periods: dict) -> str:
    return "\n".join(
        f"{PERIOD_LABELS[key]} {format_duration(int(periods.get(key, 0) or 0))}"
        for key in PERIOD_KEYS
    )


PERIOD_TIME_RANGES = {
    "morning": "04:00-12:00",
    "afternoon": "12:00-18:00",
    "evening": "18:00-04:00",
}

PERIOD_ICONS = {
    "morning": "☀",
    "afternoon": "◐",
    "evening": "☾",
}

DETAIL_COLUMN_INDEX = 2

WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


class HistoryPage(QWidget):
    def __init__(self):
        super().__init__()
        self._current_date = date.today()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        tabs = QTabWidget()
        tabs.addTab(self._build_day_tab(), "日")
        tabs.addTab(self._build_week_tab(), "周")
        tabs.addTab(self._build_month_tab(), "月")
        tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(tabs)

    def _build_day_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)

        # 日期导航
        nav = QHBoxLayout()
        self.day_prev = QPushButton("◀")
        self.day_prev.setObjectName("navArrowButton")
        self.day_prev.setFixedSize(36, 36)
        self.day_prev.clicked.connect(lambda: self._nav_day(-1))
        nav.addWidget(self.day_prev)

        self.day_label = QLabel()
        self.day_label.setObjectName("dateLabel")
        self.day_label.setAlignment(Qt.AlignCenter)
        nav.addWidget(self.day_label)

        self.day_next = QPushButton("▶")
        self.day_next.setObjectName("navArrowButton")
        self.day_next.setFixedSize(36, 36)
        self.day_next.clicked.connect(lambda: self._nav_day(1))
        nav.addWidget(self.day_next)
        layout.addLayout(nav)

        # 汇总
        self.day_summary_layout = QVBoxLayout()
        layout.addLayout(self.day_summary_layout)

        # 分时段卡片
        self.day_period_layout = QHBoxLayout()
        self.day_period_layout.setSpacing(12)
        layout.addLayout(self.day_period_layout)
        layout.addStretch()

        return w

    def _build_week_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)

        nav = QHBoxLayout()
        self.week_prev = QPushButton("◀")
        self.week_prev.setObjectName("navArrowButton")
        self.week_prev.setFixedSize(36, 36)
        self.week_prev.clicked.connect(lambda: self._nav_week(-1))
        nav.addWidget(self.week_prev)

        self.week_label = QLabel()
        self.week_label.setObjectName("dateLabel")
        self.week_label.setAlignment(Qt.AlignCenter)
        nav.addWidget(self.week_label)

        self.week_next = QPushButton("▶")
        self.week_next.setObjectName("navArrowButton")
        self.week_next.setFixedSize(36, 36)
        self.week_next.clicked.connect(lambda: self._nav_week(1))
        nav.addWidget(self.week_next)
        layout.addLayout(nav)

        # 周汇总
        self.week_summary_layout = QVBoxLayout()
        layout.addLayout(self.week_summary_layout)

        # 每日柱状图（用文本模拟）
        self.week_table = QTableWidget()
        self.week_table.setColumnCount(4)
        self.week_table.setHorizontalHeaderLabels(["日期", "模式", "明细", "时长"])
        self.week_table.setWordWrap(False)
        self.week_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.week_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.week_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.week_table.setAlternatingRowColors(True)
        self.week_table.setShowGrid(False)
        self.week_table.verticalHeader().setVisible(False)
        self.week_table.verticalHeader().setDefaultSectionSize(36)
        self.week_table.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.week_table.itemClicked.connect(
            lambda item: self._show_period_detail_tooltip(self.week_table, item)
        )
        layout.addWidget(self.week_table)

        return w

    def _build_month_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)

        nav = QHBoxLayout()
        self.month_prev = QPushButton("◀")
        self.month_prev.setObjectName("navArrowButton")
        self.month_prev.setFixedSize(36, 36)
        self.month_prev.clicked.connect(lambda: self._nav_month(-1))
        nav.addWidget(self.month_prev)

        self.month_label = QLabel()
        self.month_label.setObjectName("dateLabel")
        self.month_label.setAlignment(Qt.AlignCenter)
        nav.addWidget(self.month_label)

        self.month_next = QPushButton("▶")
        self.month_next.setObjectName("navArrowButton")
        self.month_next.setFixedSize(36, 36)
        self.month_next.clicked.connect(lambda: self._nav_month(1))
        nav.addWidget(self.month_next)
        layout.addLayout(nav)

        self.month_summary_layout = QVBoxLayout()
        layout.addLayout(self.month_summary_layout)

        self.month_table = QTableWidget()
        self.month_table.setColumnCount(4)
        self.month_table.setHorizontalHeaderLabels(["日期", "模式", "明细", "时长"])
        self.month_table.setWordWrap(False)
        self.month_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.month_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.month_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.month_table.setAlternatingRowColors(True)
        self.month_table.setShowGrid(False)
        self.month_table.verticalHeader().setVisible(False)
        self.month_table.verticalHeader().setDefaultSectionSize(36)
        self.month_table.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.month_table.itemClicked.connect(
            lambda item: self._show_period_detail_tooltip(self.month_table, item)
        )
        layout.addWidget(self.month_table)

        return w

    def refresh(self):
        self._current_date = date.today()
        self._refresh_day()

    def _on_tab_changed(self, index):
        if index == 0:
            self._refresh_day()
        elif index == 1:
            self._refresh_week()
        elif index == 2:
            self._refresh_month()

    # ---- 日视图 ----
    def _nav_day(self, delta):
        self._current_date += timedelta(days=delta)
        self._refresh_day()

    def _refresh_day(self):
        d = self._current_date
        today = date.today()
        if d == today:
            self.day_label.setText(f"今天 ({d.strftime('%m/%d')})")
        else:
            wd = WEEKDAYS[d.weekday()]
            self.day_label.setText(f"{d.strftime('%Y/%m/%d')} {wd}")

        data = get_range_period_summary(d, d)
        day_data = data.get(d.isoformat(), {})

        # 汇总
        self._clear_layout(self.day_summary_layout)
        total = sum(v["seconds"] for v in day_data.values())
        self._add_summary_row(self.day_summary_layout, day_data, total)

        # 分时段卡片
        self._clear_layout(self.day_period_layout)
        self._add_period_cards(day_data)

    # ---- 周视图 ----
    def _nav_week(self, delta):
        self._current_date += timedelta(weeks=delta)
        self._refresh_week()

    def _refresh_week(self):
        d = self._current_date
        monday = d - timedelta(days=d.weekday())
        sunday = monday + timedelta(days=6)
        self.week_label.setText(f"{monday.strftime('%m/%d')} - {sunday.strftime('%m/%d')}")

        data = get_range_period_summary(monday, sunday)

        # 汇总
        self._clear_layout(self.week_summary_layout)
        merged = {}
        for day_data in data.values():
            for name, info in day_data.items():
                if name not in merged:
                    merged[name] = {"seconds": 0, "color": info["color"]}
                merged[name]["seconds"] += info["seconds"]
        total = sum(v["seconds"] for v in merged.values())
        self._add_summary_row(self.week_summary_layout, merged, total)

        # 表格
        rows = []
        for day_str in sorted(data.keys()):
            for name, info in data[day_str].items():
                rows.append((day_str, name, info["periods"], info["seconds"]))
        self.week_table.setRowCount(len(rows))
        for i, (day_str, name, periods, secs) in enumerate(rows):
            self.week_table.setItem(i, 0, QTableWidgetItem(day_str))
            self.week_table.setItem(i, 1, QTableWidgetItem(name))
            detail = self._format_period_detail(periods)
            detail_item = QTableWidgetItem("查看")
            detail_item.setToolTip(detail)
            detail_item.setData(Qt.UserRole, detail)
            detail_item.setForeground(QColor("#7DF9FF"))
            detail_item.setTextAlignment(Qt.AlignCenter)
            self.week_table.setItem(i, 2, detail_item)
            self.week_table.setItem(i, 3, QTableWidgetItem(format_duration(secs)))

    # ---- 月视图 ----
    def _nav_month(self, delta):
        y = self._current_date.year
        m = self._current_date.month + delta
        if m > 12:
            y += 1; m = 1
        elif m < 1:
            y -= 1; m = 12
        self._current_date = self._current_date.replace(year=y, month=m, day=1)
        self._refresh_month()

    def _refresh_month(self):
        d = self._current_date
        self.month_label.setText(f"{d.strftime('%Y年%m月')}")

        y, m = d.year, d.month
        if m == 12:
            last_day = date(y + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = date(y, m + 1, 1) - timedelta(days=1)
        first_day = date(y, m, 1)

        data = get_range_period_summary(first_day, last_day)

        self._clear_layout(self.month_summary_layout)
        merged = {}
        for day_data in data.values():
            for name, info in day_data.items():
                if name not in merged:
                    merged[name] = {"seconds": 0, "color": info["color"]}
                merged[name]["seconds"] += info["seconds"]
        total = sum(v["seconds"] for v in merged.values())
        self._add_summary_row(self.month_summary_layout, merged, total)

        rows = []
        for day_str in sorted(data.keys()):
            for name, info in data[day_str].items():
                rows.append((day_str, name, info["periods"], info["seconds"]))
        self.month_table.setRowCount(len(rows))
        for i, (day_str, name, periods, secs) in enumerate(rows):
            self.month_table.setItem(i, 0, QTableWidgetItem(day_str))
            self.month_table.setItem(i, 1, QTableWidgetItem(name))
            detail = self._format_period_detail(periods)
            detail_item = QTableWidgetItem("查看")
            detail_item.setToolTip(detail)
            detail_item.setData(Qt.UserRole, detail)
            detail_item.setForeground(QColor("#7DF9FF"))
            detail_item.setTextAlignment(Qt.AlignCenter)
            self.month_table.setItem(i, 2, detail_item)
            self.month_table.setItem(i, 3, QTableWidgetItem(format_duration(secs)))

    # ---- 工具方法 ----
    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _format_period_detail(self, periods: dict) -> str:
        return format_period_detail(periods)

    def _show_period_detail_tooltip(self, table: QTableWidget, item: QTableWidgetItem):
        if not item or item.column() != DETAIL_COLUMN_INDEX:
            return
        detail = item.data(Qt.UserRole) or item.toolTip()
        if detail:
            QToolTip.showText(QCursor.pos(), detail, table)

    def _add_period_cards(self, day_data: dict):
        for period_key in PERIOD_KEYS:
            self.day_period_layout.addWidget(self._build_period_card(period_key, day_data))

    def _build_period_card(self, period_key: str, day_data: dict) -> QFrame:
        card = QFrame()
        card.setObjectName("periodCard")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        layout = QVBoxLayout(card)
        layout.setSpacing(8)
        layout.setContentsMargins(16, 14, 16, 14)

        title = QLabel(f"{PERIOD_ICONS[period_key]} {PERIOD_LABELS[period_key]}")
        title.setProperty("class", "periodTitle")
        layout.addWidget(title)

        time_range = QLabel(PERIOD_TIME_RANGES[period_key])
        time_range.setProperty("class", "periodRange")
        layout.addWidget(time_range)

        total_seconds = sum(
            int(info["periods"].get(period_key, 0) or 0)
            for info in day_data.values()
        )
        total = QLabel(format_duration(total_seconds))
        total.setObjectName("periodTotalLabel")
        layout.addWidget(total)

        active_modes = [
            (name, info)
            for name, info in day_data.items()
            if int(info["periods"].get(period_key, 0) or 0) > 0
        ]

        if not active_modes:
            empty = QLabel("暂无记录")
            empty.setProperty("class", "emptyState")
            layout.addWidget(empty)
        else:
            for name, info in active_modes:
                layout.addWidget(self._build_period_mode_row(name, info, period_key))
        layout.addStretch()

        return card

    def _build_period_mode_row(self, name: str, info: dict, period_key: str) -> QWidget:
        row_widget = QWidget()
        row_widget.setProperty("class", "periodModeRow")
        row = QHBoxLayout(row_widget)
        row.setContentsMargins(10, 6, 10, 6)
        row.setSpacing(6)

        display_color = readable_color(info["color"])
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {display_color}; font-size: 14px;")
        row.addWidget(dot)

        name_lbl = QLabel(name)
        name_lbl.setProperty("class", "periodModeName")
        row.addWidget(name_lbl)
        row.addStretch()

        seconds = int(info["periods"].get(period_key, 0) or 0)
        duration_lbl = QLabel(format_duration(seconds))
        duration_lbl.setStyleSheet(f"color: {display_color}; font-size: 13px; font-weight: 700;")
        row.addWidget(duration_lbl)

        return row_widget

    def _add_summary_row(self, parent_layout, summary: dict, total: int):
        if not summary:
            lbl = QLabel("暂无记录")
            lbl.setProperty("class", "emptyState")
            lbl.setAlignment(Qt.AlignCenter)
            parent_layout.addWidget(lbl)
            return

        total_lbl = QLabel(f"总计: {format_duration(total)}")
        total_lbl.setObjectName("summaryTotalLabel")
        total_lbl.setAlignment(Qt.AlignCenter)
        parent_layout.addWidget(total_lbl)

        row = QHBoxLayout()
        row.setAlignment(Qt.AlignCenter)
        row.setSpacing(20)
        for name, data in summary.items():
            item_lbl = QLabel(f"● {name}: {format_duration(data['seconds'])}")
            item_lbl.setStyleSheet(f"color: {readable_color(data['color'])}; font-size: 13px; font-weight: 700; padding: 4px 2px;")
            row.addWidget(item_lbl)
        container = QWidget()
        container.setLayout(row)
        parent_layout.addWidget(container)
