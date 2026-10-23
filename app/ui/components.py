"""Shared desktop UI primitives. No external assets or network access required."""
from __future__ import annotations

from PySide6.QtCore import QByteArray, QEvent, QEasingCurve, Qt, QRectF, QSize, QVariantAnimation
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QScrollArea, QSizePolicy, QToolTip, QVBoxLayout, QWidget,
)
from app.ui.colors import mix_color
from app.ui.theme import application_palette, current_theme, theme_colors

# Lucide icons, MIT license: https://github.com/lucide-icons/lucide
# Copyright (c) Lucide Contributors. SVG geometry only; rendered locally by Qt.
_PATHS = {
    "timer": '<circle cx="12" cy="13" r="8"/><path d="M12 9v4l2 2M9 2h6M19 3l2 2"/>',
    "chart": '<path d="M3 3v18h18M7 14v3M12 10v7M17 6v11"/>',
    "settings": '<path d="M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z"/><path d="m9 3 1-1h4l1 3 3 1 3-1 2 4-2 2v3l2 2-2 4-3-1-3 1-1 3h-4l-1-3-3-1-3 1-2-4 2-2v-3L1 9l2-4 3 1 3-1Z" transform="translate(1 0) scale(.92)"/>',
    "play": '<path d="m8 5 11 7-11 7V5Z"/>',
    "pause": '<path d="M8 5v14M16 5v14"/>',
    "stop": '<rect x="6" y="6" width="12" height="12" rx="2"/>',
    "arrow": '<path d="M5 12h14m-5-5 5 5-5 5"/>',
    "chevron-left": '<path d="m15 18-6-6 6-6"/>',
    "chevron-right": '<path d="m9 18 6-6-6-6"/>',
    "check": '<path d="m5 12 4 4L19 6"/>',
    "lock": '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V6a4 4 0 0 1 8 0v4"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5"/>',
    "sunset": '<path d="M3 16h18M5 20h14M7 12a5 5 0 0 1 10 0M12 2v3M3 7l2 2m14 0 2-2"/>',
    "moon": '<path d="M20.9 13a9 9 0 0 1-9.9-9.9A9 9 0 1 0 20.9 13Z"/>',
    "coffee": '<path d="M18 8h1a3 3 0 0 1 0 6h-1M3 8h15v9a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3V8ZM6 2v2m4-2v2m4-2v2"/>',
    "keyboard": '<rect x="2" y="5" width="20" height="14" rx="2"/><path d="M6 9h.01M10 9h.01M14 9h.01M18 9h.01M6 13h.01M10 13h.01M14 13h.01M18 13h.01M8 16h8"/>',
    "window": '<rect x="3" y="3" width="18" height="18" rx="3"/><path d="M3 9h18M7 6h.01m3 0h.01"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "calendar": '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 11h18"/>',
}


def configure_application(app):
    """Give native popups and spin controls the same dark palette as QSS."""
    app.setStyle("Fusion")
    app.setPalette(application_palette())


def icon(name: str, color: str | None = None, size: int = 20) -> QIcon:
    color = color or theme_colors()["muted"]
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" '
           f'viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.7" '
           f'stroke-linecap="round" stroke-linejoin="round">{_PATHS[name]}</svg>')
    pix = QPixmap(size * 2, size * 2)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    QSvgRenderer(QByteArray(svg.encode())).render(painter)
    painter.end()
    pix.setDevicePixelRatio(2)
    return QIcon(pix)


def logo(size: int = 36) -> QPixmap:
    pix = QPixmap(size * 2, size * 2)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.scale(size / 24 * 2, size / 24 * 2)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(theme_colors()["accent"]))
    painter.drawRoundedRect(QRectF(0, 0, 24, 24), 7, 7)
    painter.setBrush(Qt.NoBrush)
    painter.setPen(QPen(QColor(current_theme().colors["on_accent"]), 1.8, Qt.SolidLine, Qt.RoundCap))
    painter.drawEllipse(QRectF(5.5, 6.5, 13, 13))
    painter.drawLine(12, 10, 12, 13)
    painter.drawLine(12, 13, 15, 13)
    painter.drawLine(10, 4, 14, 4)
    painter.end()
    pix.setDevicePixelRatio(2)
    return pix


def swatch_icon(color: str, size: int = 28) -> QIcon:
    pix = QPixmap(size * 2, size * 2)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(color))
    painter.drawRoundedRect(QRectF(1, 1, size * 2 - 2, size * 2 - 2), 9, 9)
    painter.end()
    pix.setDevicePixelRatio(2)
    return QIcon(pix)


def set_feedback(label: QLabel, text: str, *, success: bool = False):
    """Semantic feedback survives a light/dark switch without stale inline colors."""
    label.setStyleSheet("")
    label.setProperty("feedback", "success" if success else "error")
    label.setText(text)
    label.style().unpolish(label)
    label.style().polish(label)


class ElidedLabel(QLabel):
    """Keep full accessible text while long user-entered names fit their row."""
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setTextFormat(Qt.PlainText)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setToolTip(text)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setFont(self.font())
        painter.setPen(self.palette().windowText().color())
        painter.drawText(self.contentsRect(), self.alignment(),
                         self.fontMetrics().elidedText(self.text(), Qt.ElideRight, self.contentsRect().width()))


def page_header(title: str, subtitle: str, trailing: QWidget | None = None) -> QWidget:
    widget = QWidget()
    widget.setObjectName("pageHeader")
    row = QHBoxLayout(widget)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(16)
    copy = QVBoxLayout()
    copy.setSpacing(5)
    heading = QLabel(title)
    heading.setProperty("class", "pageTitle")
    copy.addWidget(heading)
    description = QLabel(subtitle)
    description.setProperty("class", "mutedLabel")
    description.setWordWrap(True)
    copy.addWidget(description)
    row.addLayout(copy, 1)
    if trailing is not None:
        row.addWidget(trailing, alignment=Qt.AlignVCenter)
    return widget


def scroll_page(widget: QWidget) -> QScrollArea:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    scroll.setWidget(widget)
    return scroll


class ActivityChart(QWidget):
    """Exact recorded durations, with zero-value days kept in the time axis."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._days = []
        self._dates = []
        self._hover_index = -1
        self._hover_levels = []
        self._hover_from = []
        self._reveal = 1.0
        self._hover_animation = QVariantAnimation(self)
        self._hover_animation.setDuration(160)
        self._hover_animation.setStartValue(0.0)
        self._hover_animation.setEndValue(1.0)
        self._hover_animation.setEasingCurve(QEasingCurve.OutCubic)
        self._hover_animation.valueChanged.connect(self._animate_hover)
        self._reveal_animation = QVariantAnimation(self)
        self._reveal_animation.setDuration(360)
        self._reveal_animation.setStartValue(0.0)
        self._reveal_animation.setEndValue(1.0)
        self._reveal_animation.setEasingCurve(QEasingCurve.OutCubic)
        self._reveal_animation.valueChanged.connect(self._animate_reveal)
        self.setMinimumHeight(132)
        self.setMaximumHeight(160)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setMouseTracking(True)
        self.setAccessibleName("每日累计时长柱状图")

    def set_days(self, days, *, dates=None):
        days = list(days)
        dates = list(dates) if dates is not None else [None] * len(days)
        if len(dates) != len(days):
            raise ValueError("Each chart day must have a matching date")
        if days == self._days and dates == self._dates:
            return
        self._reset_hover()
        self._days, self._dates = days, dates
        self._hover_levels = [0.0] * len(days)
        self.setAccessibleDescription("；".join(
            self._detail_text(i).replace("\n", "，") for i in range(len(days))
        ))
        if self.isVisible():
            self._start_reveal()
        self.update()

    def _plot_area(self):
        return QRectF(self.rect().adjusted(8, 20, -8, -28))

    def _index_at(self, position):
        area = self._plot_area()
        if not self._days or area.width() <= 0 or not area.contains(position):
            return -1
        return min(len(self._days) - 1, int((position.x() - area.left()) / area.width() * len(self._days)))

    def _detail_text(self, index):
        label, total = self._days[index]
        day = self._dates[index]
        if day is not None:
            weekday = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")[day.weekday()]
            label = f"{day.isoformat()}（{weekday}）"
        hours, remainder = divmod(total, 3600)
        minutes, seconds = divmod(remainder, 60)
        duration = f"{hours}小时 {minutes}分钟" if hours else f"{minutes}分钟"
        if seconds:
            duration += f" {seconds}秒"
        return f"{label}\n累计投入：{duration}"

    def _set_hovered(self, index):
        if index == self._hover_index:
            return
        self._hover_animation.stop()
        self._hover_from = self._hover_levels[:]
        self._hover_index = index
        self._hover_animation.start()

    def _animate_hover(self, progress):
        self._hover_levels = [
            start + (float(i == self._hover_index) - start) * progress
            for i, start in enumerate(self._hover_from)
        ]
        self.update()

    def _reset_hover(self):
        if self._hover_index >= 0:
            QToolTip.hideText()
        self._hover_animation.stop()
        self._hover_index = -1
        self._hover_from = []
        self._hover_levels = [0.0] * len(self._days)

    def _start_reveal(self):
        self._reveal_animation.stop()
        self._reveal = 0.0
        self._reveal_animation.start()

    def _animate_reveal(self, progress):
        self._reveal = progress
        self.update()

    def _show_detail(self, index, global_position):
        area = self._plot_area()
        step = area.width() / len(self._days)
        column = QRectF(area.left() + step * index, area.top(), step, area.height())
        QToolTip.showText(global_position, self._detail_text(index), self, column.toAlignedRect())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if not self._days:
            return
        area = self._plot_area()
        peak = max(value for _, value in self._days)
        maximum = max(3600, peak)
        step = area.width() / len(self._days)
        colors = theme_colors()
        for i, (label, seconds) in enumerate(self._days):
            hover = self._hover_levels[i]
            width = max(3, step * (.56 + .10 * hover))
            x = area.left() + step * (i + .5) - width / 2
            height = max(3, area.height() * seconds / maximum * self._reveal)
            painter.setPen(Qt.NoPen)
            if hover > 0:
                highlight = QColor(colors["chart"])
                highlight.setAlphaF(.08 * hover)
                painter.setBrush(highlight)
                painter.drawRoundedRect(QRectF(area.left() + step * i, area.top(), step, area.height()), 5, 5)
            base = colors["chart"] if seconds else colors["track"]
            painter.setBrush(QColor(mix_color(base, colors["title"], .18 * hover)))
            painter.drawRoundedRect(QRectF(x, area.bottom() - height, width, height), 3, 3)
            if len(self._days) <= 7 or i % 5 == 0 or i == len(self._days) - 1:
                painter.setPen(QColor(colors["muted"]))
                painter.drawText(QRectF(area.left() + step * i, area.bottom() + 10, step, 20), Qt.AlignCenter, label)
        painter.setPen(QColor(colors["muted"]))
        painter.drawText(8, 13, f"每日投入 · 最高 {peak // 3600}h {(peak % 3600) // 60}m")

    def mouseMoveEvent(self, event):
        index = self._index_at(event.position())
        self._set_hovered(index)
        if index >= 0:
            self._show_detail(index, event.globalPosition().toPoint())
        else:
            QToolTip.hideText()
        super().mouseMoveEvent(event)

    def event(self, event):
        if event.type() == QEvent.ToolTip:
            index = self._index_at(event.pos())
            self._set_hovered(index)
            if index >= 0:
                self._show_detail(index, event.globalPos())
                event.accept()
            else:
                QToolTip.hideText()
                event.ignore()
            return True
        return super().event(event)

    def leaveEvent(self, event):
        self._set_hovered(-1)
        QToolTip.hideText()
        super().leaveEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        if self._days:
            self._start_reveal()

    def hideEvent(self, event):
        self._reset_hover()
        self._reveal_animation.stop()
        self._reveal = 1.0
        super().hideEvent(event)
