"""Compact desktop timer; drag to move, double-click to restore the app."""
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import Qt, QRectF, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QFont, QMouseEvent

from app.ui.colors import readable_color
from app.ui.theme import current_theme, theme_colors, mode_display_color
from app.ui.materials import paint_frosted


class FloatingBall(QWidget):
    double_clicked = Signal()

    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(184, 76)
        self.setCursor(Qt.OpenHandCursor)
        self.setToolTip("拖动调整位置 · 双击返回 Tomato")
        self.setAccessibleName("悬浮计时器，双击返回主窗口")
        self._drag_pos = None
        self._mode_name = ""
        self._mode_color = theme_colors()["accent"]
        self._time_text = "00:00:00"
        self._status = ""
        self._time_mask_enabled = True
        screen = QApplication.primaryScreen()
        if screen:
            area = screen.availableGeometry()
            self.move(area.right() - self.width() - 20, area.bottom() - self.height() - 20)

    def update_display(self, mode_name: str, mode_color: str, time_text: str, status: str):
        self._mode_name = mode_name
        self._mode_color = mode_color
        self._time_text = time_text
        self._status = status
        self.update()

    def clear_display(self):
        self._mode_name = ""
        self._mode_color = theme_colors()["accent"]
        self._time_text = "00:00:00"
        self._status = ""
        self.update()

    def set_time_mask_enabled(self, enabled: bool):
        self._time_mask_enabled = enabled
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        paint_frosted(painter, self, 11)
        font = QFont()
        font.setFamilies(["Segoe UI", "Microsoft YaHei UI", "PingFang SC"])
        font.setPointSize(9)
        painter.setFont(font)
        color = mode_display_color(self._mode_color if self._mode_name else theme_colors()["accent"])
        painter.setPen(QColor(color))
        name = painter.fontMetrics().elidedText(self._mode_name or "Tomato Timer", Qt.ElideRight, 110)
        painter.drawText(QRectF(14, 10, 125, 20), Qt.AlignVCenter, name)
        painter.setPen(QColor(theme_colors()["muted"]))
        state = {"running": "计时中", "paused": "暂停", "stopped": "结束"}.get(self._status, "就绪")
        font.setPointSize(8)
        painter.setFont(font)
        painter.drawText(QRectF(132, 10, 40, 20), Qt.AlignRight | Qt.AlignVCenter, state)
        if self._mode_name and self._time_mask_enabled:
            self._draw_time_glass_mask(painter)
        else:
            font.setFamilies(["Cascadia Mono", "Consolas", "Courier New"])
            font.setPointSize(17)
            painter.setFont(font)
            painter.setPen(QColor(theme_colors()["text"]))
            painter.drawText(QRectF(14, 35, 156, 28), Qt.AlignVCenter, self._time_text)
        painter.end()

    def _draw_time_glass_mask(self, painter):
        # A static opaque veil protects the timer reading without visual distraction.
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(current_theme().colors["accent_soft"]))
        painter.drawRoundedRect(QRectF(14, 37, 156, 24), 6, 6)
        painter.setPen(QColor(current_theme().colors["accent_text"]))
        font = QFont()
        font.setFamilies(["Segoe UI", "Microsoft YaHei UI", "PingFang SC"])
        font.setPointSize(9)
        painter.setFont(font)
        text = {"running": "安心专注，时间在走", "paused": "暂停片刻", "stopped": "本段已结束"}.get(self._status, "准备就绪")
        painter.drawText(QRectF(14, 37, 156, 24), Qt.AlignCenter, text)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._drag_pos = None
        self.setCursor(Qt.OpenHandCursor)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        self.double_clicked.emit()
