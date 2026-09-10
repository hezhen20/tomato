"""历史统计页面"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QTabWidget, QHeaderView, QFrame,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from datetime import date, timedelta

from app.database import get_daily_summary, get_range_summary, get_records_for_date
from app.ui.colors import readable_color


def format_duration(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    if h > 0:
        return f"{h}h {m}m"
    return f"{m}m"


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

        # 详细记录表
        self.day_table = QTableWidget()
        self.day_table.setColumnCount(4)
        self.day_table.setHorizontalHeaderLabels(["模式", "开始", "结束", "时长"])
        self.day_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.day_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.day_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.day_table.setAlternatingRowColors(True)
        self.day_table.setShowGrid(False)
        self.day_table.verticalHeader().setVisible(False)
        self.day_table.verticalHeader().setDefaultSectionSize(36)
        layout.addWidget(self.day_table)

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
        self.week_table.setColumnCount(3)
        self.week_table.setHorizontalHeaderLabels(["日期", "模式", "时长"])
        self.week_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.week_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.week_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.week_table.setAlternatingRowColors(True)
        self.week_table.setShowGrid(False)
        self.week_table.verticalHeader().setVisible(False)
        self.week_table.verticalHeader().setDefaultSectionSize(36)
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
        self.month_table.setColumnCount(3)
        self.month_table.setHorizontalHeaderLabels(["日期", "模式", "时长"])
        self.month_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.month_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.month_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.month_table.setAlternatingRowColors(True)
        self.month_table.setShowGrid(False)
        self.month_table.verticalHeader().setVisible(False)
        self.month_table.verticalHeader().setDefaultSectionSize(36)
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

        # 汇总
        self._clear_layout(self.day_summary_layout)
        summary = get_daily_summary(d)
        total = sum(v["seconds"] for v in summary.values())
        self._add_summary_row(self.day_summary_layout, summary, total)

        # 详细记录
        records = get_records_for_date(d)
        self.day_table.setRowCount(len(records))
        for i, r in enumerate(records):
            self.day_table.setItem(i, 0, QTableWidgetItem(r["mode_name"]))
            start = r["start_time"][11:19] if r["start_time"] else ""
            end = r["end_time"][11:19] if r["end_time"] else "进行中"
            self.day_table.setItem(i, 1, QTableWidgetItem(start))
            self.day_table.setItem(i, 2, QTableWidgetItem(end))
            self.day_table.setItem(i, 3, QTableWidgetItem(format_duration(r["duration_seconds"])))

    # ---- 周视图 ----
    def _nav_week(self, delta):
        self._current_date += timedelta(weeks=delta)
        self._refresh_week()

    def _refresh_week(self):
        d = self._current_date
        monday = d - timedelta(days=d.weekday())
        sunday = monday + timedelta(days=6)
        self.week_label.setText(f"{monday.strftime('%m/%d')} - {sunday.strftime('%m/%d')}")

        data = get_range_summary(monday, sunday)

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
                rows.append((day_str, name, info["seconds"]))
        self.week_table.setRowCount(len(rows))
        for i, (day_str, name, secs) in enumerate(rows):
            self.week_table.setItem(i, 0, QTableWidgetItem(day_str))
            self.week_table.setItem(i, 1, QTableWidgetItem(name))
            self.week_table.setItem(i, 2, QTableWidgetItem(format_duration(secs)))

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

        data = get_range_summary(first_day, last_day)

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
                rows.append((day_str, name, info["seconds"]))
        self.month_table.setRowCount(len(rows))
        for i, (day_str, name, secs) in enumerate(rows):
            self.month_table.setItem(i, 0, QTableWidgetItem(day_str))
            self.month_table.setItem(i, 1, QTableWidgetItem(name))
            self.month_table.setItem(i, 2, QTableWidgetItem(format_duration(secs)))

    # ---- 工具方法 ----
    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

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
