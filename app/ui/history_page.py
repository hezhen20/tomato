"""历史统计页面"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QTabWidget, QHeaderView, QFrame,
    QToolTip, QSizePolicy, QDateTimeEdit, QCalendarWidget, QMessageBox, QScrollArea, QLayout,
    QStackedWidget, QButtonGroup,
)
from PySide6.QtCore import Qt, QDateTime, QTime, Signal
from PySide6.QtGui import QColor, QCursor, QFont
from datetime import date, datetime, timedelta

from app.database import (
    PERIOD_KEYS,
    PERIOD_LABELS,
    delete_records_in_datetime_range,
    get_records_for_date,
    get_records_in_datetime_range,
    get_range_period_summary,
    stat_day,
)
from app.ui.colors import readable_color
from app.ui.components import ActivityChart, ElidedLabel, LedgerRow, icon, page_header, scroll_page
from app.ui.theme import current_theme, theme_colors, mode_display_color
from app.ui.task_stats_page import TaskStatsPage


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

DETAIL_COLUMN_INDEX = 2

WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


class HistoryPage(QWidget):
    records_changed = Signal()

    def __init__(self):
        super().__init__()
        self._current_date = stat_day()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(44, 22, 44, 22)
        layout.addWidget(page_header("时间统计", "回看每一段投入，看见自己的节奏。"))

        views = QHBoxLayout()
        views.setSpacing(6)
        self._view_group = QButtonGroup(self)
        self.date_view_button = QPushButton("按日期")
        self.task_view_button = QPushButton("按任务")
        for index, button in enumerate((self.date_view_button, self.task_view_button)):
            button.setObjectName("viewSwitch")
            button.setCheckable(True)
            self._view_group.addButton(button, index)
            views.addWidget(button)
        self.date_view_button.setChecked(True)
        views.addStretch()
        layout.addLayout(views)
        self._views = QStackedWidget()
        layout.addWidget(self._views, 1)

        tabs = QTabWidget()
        self._tabs = tabs
        tabs.addTab(scroll_page(self._build_day_tab()), "日")
        tabs.tabBar().setUsesScrollButtons(True)
        tabs.addTab(self._build_week_tab(), "周")
        tabs.addTab(self._build_month_tab(), "月")
        tabs.addTab(scroll_page(self._build_manage_tab()), "管理")
        tabs.tabBar().setExpanding(False)
        tabs.tabBar().setDrawBase(False)
        tabs.currentChanged.connect(self._on_tab_changed)
        self._views.addWidget(tabs)
        self.task_page = TaskStatsPage()
        self.task_page.day_requested.connect(self._open_task_day)
        self._views.addWidget(scroll_page(self.task_page))
        self._view_group.idClicked.connect(self._switch_view)
        for button in (self.day_prev, self.week_prev, self.month_prev):
            button.setText("")
            button.setIcon(icon("chevron-left"))
            button.setToolTip("上一时段")
            button.setAccessibleName("上一时段")
        for button in (self.day_next, self.week_next, self.month_next):
            button.setText("")
            button.setIcon(icon("chevron-right"))
            button.setToolTip("下一时段")
            button.setAccessibleName("下一时段")
        for button in self.findChildren(QPushButton):
            button.setCursor(Qt.PointingHandCursor)

    def _build_day_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)
        layout.setContentsMargins(0, 24, 4, 0)

        # 日期导航
        nav = QHBoxLayout()
        nav.addStretch(1)
        self.day_prev = QPushButton("◀")
        self.day_prev.setObjectName("navArrowButton")
        self.day_prev.setFixedSize(36, 36)
        self.day_prev.clicked.connect(lambda: self._nav_day(-1))
        nav.addWidget(self.day_prev)

        self.day_label = QLabel()
        self.day_label.setObjectName("dateLabel")
        self.day_label.setAlignment(Qt.AlignCenter)
        self.day_label.setMinimumWidth(220)
        nav.addWidget(self.day_label)

        self.day_next = QPushButton("▶")
        self.day_next.setObjectName("navArrowButton")
        self.day_next.setFixedSize(36, 36)
        self.day_next.clicked.connect(lambda: self._nav_day(1))
        nav.addWidget(self.day_next)
        nav.addStretch(1)
        layout.addLayout(nav)

        # 汇总
        self.day_summary_layout = QVBoxLayout()
        layout.addLayout(self.day_summary_layout)

        # 分时段卡片
        self.day_period_layout = QHBoxLayout()
        self.day_period_layout.setSpacing(12)
        layout.addLayout(self.day_period_layout)

        records_caption = QLabel("今日记录 · RECORDS")
        records_caption.setProperty("class", "monoCaption")
        layout.addSpacing(18)
        layout.addWidget(records_caption)
        self.day_records_layout = QVBoxLayout()
        self.day_records_layout.setSpacing(0)
        layout.addLayout(self.day_records_layout)
        layout.addStretch()

        return w

    def _build_week_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)
        layout.setContentsMargins(0, 24, 0, 0)

        nav = QHBoxLayout()
        nav.addStretch(1)
        self.week_prev = QPushButton("◀")
        self.week_prev.setObjectName("navArrowButton")
        self.week_prev.setFixedSize(36, 36)
        self.week_prev.clicked.connect(lambda: self._nav_week(-1))
        nav.addWidget(self.week_prev)

        self.week_label = QLabel()
        self.week_label.setObjectName("dateLabel")
        self.week_label.setAlignment(Qt.AlignCenter)
        self.week_label.setMinimumWidth(220)
        nav.addWidget(self.week_label)

        self.week_next = QPushButton("▶")
        self.week_next.setObjectName("navArrowButton")
        self.week_next.setFixedSize(36, 36)
        self.week_next.clicked.connect(lambda: self._nav_week(1))
        nav.addWidget(self.week_next)
        nav.addStretch(1)
        layout.addLayout(nav)

        # 周汇总
        self.week_summary_layout = QVBoxLayout()
        layout.addLayout(self.week_summary_layout)

        self.week_chart = ActivityChart()
        layout.addWidget(self.week_chart)

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
        self.week_table.verticalHeader().setDefaultSectionSize(44)
        self.week_table.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.week_table.itemClicked.connect(
            lambda item: self._show_period_detail_tooltip(self.week_table, item)
        )
        layout.addWidget(self.week_table, 1)

        return w

    def _build_month_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)
        layout.setContentsMargins(0, 24, 0, 0)

        nav = QHBoxLayout()
        nav.addStretch(1)
        self.month_prev = QPushButton("◀")
        self.month_prev.setObjectName("navArrowButton")
        self.month_prev.setFixedSize(36, 36)
        self.month_prev.clicked.connect(lambda: self._nav_month(-1))
        nav.addWidget(self.month_prev)

        self.month_label = QLabel()
        self.month_label.setObjectName("dateLabel")
        self.month_label.setAlignment(Qt.AlignCenter)
        self.month_label.setMinimumWidth(220)
        nav.addWidget(self.month_label)

        self.month_next = QPushButton("▶")
        self.month_next.setObjectName("navArrowButton")
        self.month_next.setFixedSize(36, 36)
        self.month_next.clicked.connect(lambda: self._nav_month(1))
        nav.addWidget(self.month_next)
        nav.addStretch(1)
        layout.addLayout(nav)

        self.month_summary_layout = QVBoxLayout()
        layout.addLayout(self.month_summary_layout)

        self.month_chart = ActivityChart()
        layout.addWidget(self.month_chart)

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
        self.month_table.verticalHeader().setDefaultSectionSize(44)
        self.month_table.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.month_table.itemClicked.connect(
            lambda item: self._show_period_detail_tooltip(self.month_table, item)
        )
        layout.addWidget(self.month_table, 1)

        return w

    def _build_manage_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)
        layout.setContentsMargins(0, 24, 4, 0)

        header = QFrame()
        header.setObjectName("historyManageHeader")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 10)
        header_layout.setSpacing(5)

        title = QLabel("清理计时记录")
        title.setObjectName("historyManageTitle")
        header_layout.addWidget(title)

        hint = QLabel("选择精确到分钟的时间范围，先预览再删除。结束分钟包含在范围内；删除后无法恢复。")
        hint.setObjectName("historyManageHint")
        hint.setWordWrap(True)
        header_layout.addWidget(hint)
        layout.addWidget(header)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)

        from_label = QLabel("从")
        from_label.setProperty("class", "mutedLabel")
        filter_row.addWidget(from_label)
        self.manage_start_edit = self._build_datetime_edit()
        self.manage_start_edit.dateTimeChanged.connect(self._refresh_manage_records)
        filter_row.addWidget(self.manage_start_edit)

        to_label = QLabel("到")
        to_label.setProperty("class", "mutedLabel")
        filter_row.addWidget(to_label)
        self.manage_end_edit = self._build_datetime_edit()
        self.manage_end_edit.dateTimeChanged.connect(self._refresh_manage_records)
        filter_row.addWidget(self.manage_end_edit)

        filter_row.addStretch()
        layout.addLayout(filter_row)

        summary_card = QFrame()
        summary_card.setObjectName("historyManageSummaryCard")
        summary_layout = QVBoxLayout(summary_card)
        summary_layout.setContentsMargins(16, 16, 16, 16)
        summary_layout.setSpacing(10)

        summary_title = QLabel("范围内汇总")
        summary_title.setObjectName("historyManageSummaryTitle")
        summary_layout.addWidget(summary_title)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(28)

        total_column = QVBoxLayout()
        total_caption = QLabel("累计专注")
        total_caption.setProperty("class", "mutedLabel")
        total_column.addWidget(total_caption)
        self.manage_total_label = QLabel("0m")
        self.manage_total_label.setObjectName("historyManageTotalLabel")
        total_column.addWidget(self.manage_total_label)
        stats_row.addLayout(total_column)

        stats_row.addStretch()
        summary_layout.addLayout(stats_row)

        modes_title = QLabel("按模式")
        modes_title.setObjectName("historyManageModesTitle")
        summary_layout.addWidget(modes_title)

        self.manage_mode_layout = QVBoxLayout()
        self.manage_mode_layout.setSpacing(6)
        summary_layout.addLayout(self.manage_mode_layout)
        summary_layout.addStretch()

        self.manage_empty_label = QLabel()
        self.manage_empty_label.setObjectName("historyManageEmpty")
        self.manage_empty_label.setAlignment(Qt.AlignCenter)
        self.manage_empty_label.setWordWrap(True)
        summary_layout.addWidget(self.manage_empty_label)
        layout.addWidget(summary_card)
        layout.addStretch()

        action_row = QHBoxLayout()
        action_row.addStretch()
        self.manage_delete_btn = QPushButton("删除记录")
        self.manage_delete_btn.setObjectName("deleteRecordsButton")
        self.manage_delete_btn.setMinimumWidth(148)
        self.manage_delete_btn.clicked.connect(self._confirm_delete_records)
        action_row.addWidget(self.manage_delete_btn)
        layout.addLayout(action_row)

        now = QDateTime.currentDateTime()
        self.manage_start_edit.setDateTime(QDateTime(now.date(), QTime(0, 0)))
        self.manage_end_edit.setDateTime(now.addSecs(-now.time().second()))
        return w

    def _build_datetime_edit(self):
        edit = QDateTimeEdit()
        edit.setCalendarPopup(True)
        edit.setDisplayFormat("yyyy/MM/dd HH:mm")
        # Future timestamps are safe for filtering and keep two-digit hour entry usable.
        edit.setMinimumWidth(184)
        edit.setFixedHeight(38)
        edit.setFont(QFont("Microsoft YaHei UI", 10))

        calendar = edit.calendarWidget()
        calendar.setFont(QFont("Microsoft YaHei UI", 10))
        calendar.setHorizontalHeaderFormat(QCalendarWidget.HorizontalHeaderFormat.ShortDayNames)
        return edit

    def refresh(self):
        self._current_date = stat_day()
        self._refresh_day()
        self._refresh_week()
        self._refresh_month()
        self._refresh_manage_records()
        if self._views.currentIndex() == 1:
            self.task_page.refresh()

    def refresh_theme(self):
        self._refresh_day()
        self._refresh_week()
        self._refresh_month()
        self._refresh_manage_records()
        self.task_page.refresh_theme()

    def _switch_view(self, index):
        self._views.setCurrentIndex(index)
        self._view_group.button(index).setChecked(True)
        if index == 1:
            self.task_page.refresh()

    def open_task_statistics(self, mode_id=None):
        self._switch_view(1)
        self.task_page.select_task(mode_id)

    def _open_task_day(self, day):
        self._current_date = day
        self._switch_view(0)
        self._tabs.setCurrentIndex(0)
        self._refresh_day()

    def _on_tab_changed(self, index):
        if index == 0:
            self._refresh_day()
        elif index == 1:
            self._refresh_week()
        elif index == 2:
            self._refresh_month()
        elif index == 3:
            self._refresh_manage_records()

    # ---- 日视图 ----
    def _nav_day(self, delta):
        self._current_date += timedelta(days=delta)
        self._refresh_day()

    def _refresh_day(self):
        d = self._current_date
        today = stat_day()
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
        self._refresh_day_records(d)

    def _refresh_day_records(self, day: date):
        layout = getattr(self, "day_records_layout", None)
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        records = [r for r in get_records_for_date(day) if r.get("end_time")]
        if not records:
            empty = QLabel("这一天还没有完成的记录。")
            empty.setProperty("class", "emptyState")
            layout.addWidget(empty)
            return
        for record in records[-6:][::-1]:
            ended = datetime.fromisoformat(record["end_time"])
            started = datetime.fromisoformat(record["start_time"])
            prefix = f"{started.strftime('%H:%M')}—{ended.strftime('%H:%M')}"
            row = LedgerRow(prefix=prefix)
            seconds = int(record.get("duration_seconds") or 0)
            row.set_data(
                record.get("mode_name") or "已删除模式",
                mode_display_color(record.get("mode_color") or "#999999"),
                format_duration(seconds),
            )
            layout.addWidget(row)

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

        self._populate_period_table(self.week_table, data)
        self.week_chart.set_days([
            (WEEKDAYS[i], sum(info["seconds"] for info in data.get((monday + timedelta(days=i)).isoformat(), {}).values()))
            for i in range(7)
        ], dates=[monday + timedelta(days=i) for i in range(7)])

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

        self._populate_period_table(self.month_table, data)
        self.month_chart.set_days([
            (str(day), sum(info["seconds"] for info in data.get(date(y, m, day).isoformat(), {}).values()))
            for day in range(1, last_day.day + 1)
        ], dates=[date(y, m, day) for day in range(1, last_day.day + 1)])

    # ---- 工具方法 ----
    def _populate_period_table(self, table: QTableWidget, data: dict):
        """填充周/月明细表，并按日期合并重复日期、显示当天总时长。"""
        grouped_rows = []
        for day_str in sorted(data.keys()):
            mode_rows = [
                (name, info["periods"], int(info["seconds"] or 0))
                for name, info in data[day_str].items()
            ]
            if len(mode_rows) > 1:
                day_total = sum(seconds for _, _, seconds in mode_rows)
                total_periods = {key: 0 for key in PERIOD_KEYS}
                for _, periods, _ in mode_rows:
                    for key in PERIOD_KEYS:
                        total_periods[key] += int(periods.get(key, 0) or 0)
                grouped_rows.append({
                    "day": day_str,
                    "name": "总计",
                    "periods": total_periods,
                    "seconds": day_total,
                    "is_total": True,
                    "row_span": len(mode_rows) + 1,
                })
                grouped_rows.extend(
                    {
                        "day": None,
                        "name": name,
                        "periods": periods,
                        "seconds": seconds,
                        "is_total": False,
                        "row_span": 1,
                    }
                    for name, periods, seconds in mode_rows
                )
            else:
                name, periods, seconds = mode_rows[0]
                grouped_rows.append({
                    "day": day_str,
                    "name": name,
                    "periods": periods,
                    "seconds": seconds,
                    "is_total": False,
                    "row_span": 1,
                })

        table.clearSpans()
        table.clearContents()
        table.setRowCount(len(grouped_rows))
        row_index = 0
        for row in grouped_rows:
            if row["day"]:
                day_item = QTableWidgetItem(row["day"])
                day_item.setTextAlignment(Qt.AlignCenter)
                table.setItem(row_index, 0, day_item)

            name_item = QTableWidgetItem(row["name"])
            if row["is_total"]:
                name_item.setFont(QFont(name_item.font().family(), name_item.font().pointSize(), QFont.Bold))
            table.setItem(row_index, 1, name_item)

            detail = self._format_period_detail(row["periods"])
            detail_item = QTableWidgetItem("查看")
            detail_item.setToolTip(detail)
            detail_item.setData(Qt.UserRole, detail)
            detail_item.setForeground(QColor(current_theme().colors["accent_text"]))
            detail_item.setTextAlignment(Qt.AlignCenter)
            if row["is_total"]:
                detail_font = detail_item.font()
                detail_font.setBold(True)
                detail_item.setFont(detail_font)
            table.setItem(row_index, 2, detail_item)

            duration_item = QTableWidgetItem(format_duration(row["seconds"]))
            if row["is_total"]:
                duration_item.setFont(QFont(duration_item.font().family(), duration_item.font().pointSize(), QFont.Bold))
            table.setItem(row_index, 3, duration_item)

            if row["row_span"] > 1:
                table.setSpan(row_index, 0, row["row_span"], 1)
            row_index += 1

    def _clear_layout(self, layout):
        """Detach before deleting, or the old cards keep painting until the
        event loop gets round to them and the rebuilt rows overlap."""
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
            elif item.layout() is not None:
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

        title_row = QHBoxLayout()
        mark = QLabel()
        mark.setPixmap(icon({"morning": "sun", "afternoon": "sunset", "evening": "moon"}[period_key]).pixmap(18, 18))
        title_row.addWidget(mark)
        title = QLabel(PERIOD_LABELS[period_key])
        title.setProperty("class", "periodTitle")
        title_row.addWidget(title)
        title_row.addStretch()
        layout.addLayout(title_row)

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
        row.setContentsMargins(0, 6, 0, 6)
        row.setSpacing(6)

        display_color = mode_display_color(info["color"])
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {display_color}; font-size: 14px;")
        row.addWidget(dot)

        name_lbl = ElidedLabel(name)
        name_lbl.setProperty("class", "periodModeName")
        row.addWidget(name_lbl, 1)

        seconds = int(info["periods"].get(period_key, 0) or 0)
        duration_lbl = QLabel(format_duration(seconds))
        duration_lbl.setStyleSheet(f"color: {display_color}; font-size: 13px; font-weight: 700;")
        row.addWidget(duration_lbl)

        return row_widget

    # ---- 记录管理 ----
    def _manage_dates(self):
        start_at = self.manage_start_edit.dateTime().toPython().replace(second=0, microsecond=0)
        end_minute = self.manage_end_edit.dateTime().toPython().replace(second=0, microsecond=0)
        return start_at, end_minute, end_minute + timedelta(minutes=1)

    def _refresh_manage_records(self, *_):
        start_at, end_minute, end_exclusive = self._manage_dates()
        self._clear_layout(self.manage_mode_layout)

        if start_at >= end_exclusive:
            self.manage_total_label.setText("—")
            self.manage_empty_label.setText("起始时间不能晚于结束时间，请调整后再试。")
            self.manage_empty_label.setVisible(True)
            self.manage_delete_btn.setText("删除此范围记录")
            self.manage_delete_btn.setEnabled(False)
            self._manage_records = []
            return

        records = get_records_in_datetime_range(start_at, end_exclusive)
        total_seconds = sum(int(record.get("duration_seconds") or 0) for record in records)
        self._manage_records = records
        self.manage_total_label.setText(format_duration(total_seconds))
        self.manage_delete_btn.setText("删除此范围记录")
        self.manage_delete_btn.setEnabled(bool(records))
        self.manage_empty_label.setVisible(not records)
        self.manage_empty_label.setText(
            "这个范围内没有可删除的已完成记录。\n当前进行中的计时会保留。"
        )

        mode_totals = {}
        for record in records:
            name = record.get("mode_name") or "已删除模式"
            info = mode_totals.setdefault(
                name,
                {"seconds": 0, "color": record.get("mode_color") or "#A8B3C7"},
            )
            info["seconds"] += int(record.get("duration_seconds") or 0)

        for name, info in sorted(
            mode_totals.items(), key=lambda item: item[1]["seconds"], reverse=True
        ):
            self.manage_mode_layout.addWidget(
                self._build_manage_mode_row(name, info["seconds"], info["color"])
            )

    def _build_manage_mode_row(self, name: str, seconds: int, color: str) -> QWidget:
        row_widget = QWidget()
        row_widget.setProperty("class", "historyManageModeRow")
        row = QHBoxLayout(row_widget)
        row.setContentsMargins(10, 7, 10, 7)
        row.setSpacing(7)

        display_color = mode_display_color(color, theme_colors()["surface_alt"])
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {display_color}; font-size: 13px;")
        row.addWidget(dot)

        name_label = ElidedLabel(name)
        name_label.setProperty("class", "historyManageModeName")
        row.addWidget(name_label, 1)

        duration_label = QLabel(format_duration(seconds))
        duration_label.setProperty("class", "historyManageModeDuration")
        duration_label.setStyleSheet(f"color: {display_color};")
        row.addWidget(duration_label)
        return row_widget

    def _confirm_delete_records(self):
        start_at, end_minute, end_exclusive = self._manage_dates()
        records = getattr(self, "_manage_records", [])
        if start_at >= end_exclusive or not records:
            return

        total_seconds = sum(int(record.get("duration_seconds") or 0) for record in records)
        date_text = self._format_manage_range(start_at, end_minute)
        message_box = QMessageBox(self)
        message_box.setIcon(QMessageBox.Warning)
        message_box.setWindowTitle("确认删除记录")
        message_box.setText(f"确定删除 {date_text} 内的专注记录吗？")
        message_box.setInformativeText(
            f"将移除合计 {format_duration(total_seconds)}。此操作无法撤销，正在进行中的计时不会被删除。"
        )
        message_box.setStandardButtons(QMessageBox.Cancel | QMessageBox.Yes)
        message_box.setDefaultButton(QMessageBox.Cancel)
        if message_box.exec() != QMessageBox.Yes:
            return

        if delete_records_in_datetime_range(start_at, end_exclusive):
            self.records_changed.emit()
        self._refresh_manage_records()
        self._refresh_day()
        self._refresh_week()
        self._refresh_month()

        notice = QMessageBox(self)
        notice.setIcon(QMessageBox.Information)
        notice.setWindowTitle("已删除")
        notice.setText("已删除所选时间范围内的专注记录。")
        notice.setStandardButtons(QMessageBox.Ok)
        notice.exec()

    @staticmethod
    def _format_manage_range(start_at: datetime, end_minute: datetime) -> str:
        return f"{start_at.strftime('%Y/%m/%d %H:%M')} — {end_minute.strftime('%Y/%m/%d %H:%M')}"

    def _add_summary_row(self, parent_layout, summary: dict, total: int):
        caption = QLabel("累计投入 · TOTAL")
        caption.setProperty("class", "monoCaption")
        parent_layout.addWidget(caption)
        total_lbl = QLabel(format_duration(total))
        total_lbl.setObjectName("summaryTotalLabel")
        parent_layout.addWidget(total_lbl)
        if not summary:
            lbl = QLabel("这段时间还没有记录。回到专注页，开始积累你的时间。")
            lbl.setProperty("class", "emptyState")
            lbl.setWordWrap(True)
            parent_layout.addWidget(lbl)
            return

        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setAlignment(Qt.AlignLeft)
        row.setSizeConstraint(QLayout.SetMinimumSize)
        row.setSpacing(18)
        for name, data in summary.items():
            chip = QWidget()
            chip_row = QHBoxLayout(chip)
            chip_row.setContentsMargins(0, 0, 0, 0)
            chip_row.setSpacing(6)
            dot = QLabel("●")
            dot.setStyleSheet(
                f"color: {mode_display_color(data['color'], theme_colors()['window'])}; font-size: 9px;"
            )
            chip_row.addWidget(dot)
            label = QLabel(f"{name}  {format_duration(data['seconds'])}")
            label.setStyleSheet(f"color: {theme_colors()['text']}; font-size: 11px; letter-spacing: .5px;")
            chip_row.addWidget(label)
            row.addWidget(chip)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(44)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(container)
        parent_layout.addWidget(scroll)
