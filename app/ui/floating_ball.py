"""悬浮球 - 最小化后显示当前计时状态"""
import math

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QRectF, Signal, QTimer
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QBrush, QPen, QFont, QMouseEvent

from app.ui.colors import readable_color


class FloatingBall(QWidget):
    double_clicked = Signal()

    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool  # 不在任务栏显示
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(132, 60)

        self._drag_pos = None
        self._mode_name = ""
        self._mode_color = "#00F5A0"
        self._time_text = "00:00:00"
        self._status = ""  # "running", "paused", ""
        self._time_mask_enabled = True
        self._mask_phase = 0.0
        self._mask_animation_timer = QTimer(self)
        self._mask_animation_timer.setInterval(120)
        self._mask_animation_timer.timeout.connect(self._advance_mask_animation)

        # 默认位置：屏幕右下角
        from PySide6.QtWidgets import QApplication
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() - 140, screen.height() - 120)

    def update_display(self, mode_name: str, mode_color: str, time_text: str, status: str):
        self._mode_name = mode_name
        self._mode_color = mode_color
        self._time_text = time_text
        self._status = status
        self._refresh_mask_animation_state()
        self.update()

    def clear_display(self):
        self._mode_name = ""
        self._mode_color = "#00F5A0"
        self._time_text = "00:00:00"
        self._status = ""
        self._refresh_mask_animation_state()
        self.update()

    def set_time_mask_enabled(self, enabled: bool):
        if self._time_mask_enabled == enabled:
            return
        self._time_mask_enabled = enabled
        self._refresh_mask_animation_state()
        self.update()

    def _advance_mask_animation(self):
        if not self._should_animate_mask():
            self._mask_animation_timer.stop()
            return
        self._mask_phase = (self._mask_phase + 0.012) % 1.0
        self.update()

    def _should_animate_mask(self) -> bool:
        return self._time_mask_enabled and self._status == "running" and bool(self._mode_name) and self.isVisible()

    def _refresh_mask_animation_state(self):
        if self._should_animate_mask():
            if not self._mask_animation_timer.isActive():
                self._mask_animation_timer.start()
        else:
            if self._mask_animation_timer.isActive():
                self._mask_animation_timer.stop()
            if self._status != "running":
                self._mask_phase = 0.0

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 轻量深色浮层，和主窗口的赛博朋克深色主题一致
        shadow = QColor("#000000")
        shadow.setAlpha(80)
        painter.setBrush(QBrush(shadow))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(5, 7, self.width() - 10, self.height() - 10, 14, 14)

        bg_color = QColor("#0D1220")
        bg_color.setAlpha(246)
        painter.setBrush(QBrush(bg_color))
        border_color = QColor(self._mode_color)
        display_color = QColor(readable_color(self._mode_color))
        if self._status == "paused":
            border_color = QColor("#2A3650")
        elif display_color.isValid():
            border_color = display_color
        container_rect = QRectF(3, 3, self.width() - 8, self.height() - 10)
        painter.setPen(QPen(border_color, 1))
        painter.drawRoundedRect(container_rect, 14, 14)

        if self._mode_name:
            # 模式名
            painter.setPen(display_color)
            font = QFont()
            font.setFamilies(["Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", "PingFang SC"])
            font.setPointSize(9)
            font.setBold(True)
            painter.setFont(font)
            prefix = "⏸ " if self._status == "paused" else "● "
            painter.drawText(13, 7, 106, 20, Qt.AlignLeft | Qt.AlignVCenter, prefix + self._mode_name)

            # 时间。开启遮罩时先把数字压低，再用高不透明玻璃层覆盖，避免用户下意识读秒。
            time_color = QColor("#F8FAFC")
            if self._time_mask_enabled:
                time_color.setAlpha(42)
            painter.setPen(time_color)
            font = QFont()
            font.setFamilies(["Cascadia Mono", "Consolas", "Courier New"])
            font.setPointSize(14)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(10, 28, 110, 24, Qt.AlignCenter, self._time_text)

            if self._time_mask_enabled:
                self._draw_time_glass_mask(painter)
        else:
            painter.setPen(QColor("#A8B3C7"))
            font = QFont()
            font.setFamilies(["Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", "PingFang SC"])
            font.setPointSize(9)
            painter.setFont(font)
            painter.drawText(0, 0, self.width(), self.height(), Qt.AlignCenter, "Tomato")

        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(border_color, 1))
        painter.drawRoundedRect(container_rect, 14, 14)

        painter.end()

    def _draw_time_glass_mask(self, painter: QPainter):
        """在时间数字上覆盖磨砂玻璃层，弱化读数但保留运行状态感。"""
        mask_rect = QRectF(11, 28, self.width() - 24, 22)

        painter.setPen(Qt.NoPen)

        base = QColor("#07101D")
        base.setAlpha(248)
        painter.setBrush(QBrush(base))
        painter.drawRoundedRect(mask_rect, 11, 11)

        gradient = QLinearGradient(mask_rect.topLeft(), mask_rect.bottomRight())
        top = QColor("#EAF8FF")
        top.setAlpha(72)
        middle = QColor("#101B2D")
        middle.setAlpha(242)
        bottom = QColor("#02060D")
        bottom.setAlpha(252)
        gradient.setColorAt(0.0, top)
        gradient.setColorAt(0.42, middle)
        gradient.setColorAt(1.0, bottom)

        painter.setBrush(QBrush(gradient))
        painter.drawRoundedRect(mask_rect, 10, 10)

        shine = QColor("#FFFFFF")
        shine.setAlpha(74)
        painter.setPen(QPen(shine, 1))
        painter.drawLine(
            int(mask_rect.left() + 10),
            int(mask_rect.top() + 3),
            int(mask_rect.right() - 10),
            int(mask_rect.top() + 3),
        )

        veil = QLinearGradient(mask_rect.left(), mask_rect.top(), mask_rect.right(), mask_rect.top())
        clear = QColor("#FFFFFF")
        clear.setAlpha(0)
        soft = QColor("#F8FAFC")
        soft.setAlpha(32)
        veil.setColorAt(0.0, clear)
        veil.setColorAt(0.24, soft)
        veil.setColorAt(0.48, clear)
        veil.setColorAt(0.68, soft)
        veil.setColorAt(1.0, clear)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(veil))
        painter.drawRoundedRect(mask_rect.adjusted(4, 5, -4, -4), 8, 8)

        if self._status == "running":
            self._draw_mask_shimmer(painter, mask_rect)

        grain = QColor("#F8FAFC")
        grain.setAlpha(36)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(grain))
        for x, y, size in (
            (19, 33, 1.4), (30, 47, 1.1), (43, 38, 1.6), (57, 50, 1.2),
            (72, 33, 1.2), (86, 46, 1.5), (99, 36, 1.1), (111, 49, 1.3),
        ):
            painter.drawEllipse(QRectF(x, y, size, size))

    def _draw_mask_shimmer(self, painter: QPainter, mask_rect: QRectF):
        """运行时的克制扫光：像细小星尘从左向右掠过。"""
        phase = self._mask_phase
        sweep_center = mask_rect.left() - 24 + (mask_rect.width() + 48) * phase

        sweep = QLinearGradient(sweep_center - 20, mask_rect.top(), sweep_center + 20, mask_rect.top())
        clear = QColor("#FFFFFF")
        clear.setAlpha(0)
        glow = QColor("#FFFFFF")
        glow.setAlpha(34)
        sweep.setColorAt(0.0, clear)
        sweep.setColorAt(0.48, glow)
        sweep.setColorAt(1.0, clear)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(sweep))
        painter.drawRoundedRect(mask_rect.adjusted(5, 4, -5, -4), 8, 8)

        painter.setBrush(Qt.NoBrush)
        for offset, y_ratio, size, strength in (
            (0.00, 0.32, 1.3, 1.0),
            (0.18, 0.68, 1.0, 0.72),
            (0.37, 0.45, 1.6, 0.9),
            (0.61, 0.72, 1.1, 0.68),
            (0.78, 0.36, 1.4, 0.86),
        ):
            local_phase = (phase + offset) % 1.0
            x = mask_rect.left() + 8 + (mask_rect.width() - 16) * local_phase
            y = mask_rect.top() + 6 + (mask_rect.height() - 12) * y_ratio
            twinkle = 0.5 + 0.5 * math.sin((local_phase * 2 * math.pi) + offset * 11)
            alpha = int((20 + 64 * twinkle) * strength)
            if alpha <= 30:
                continue

            star = QColor("#F8FAFC")
            star.setAlpha(alpha)
            painter.setPen(QPen(star, 1))
            painter.drawLine(int(x - size), int(y), int(x + size), int(y))
            painter.drawLine(int(x), int(y - size), int(x), int(y + size))

            core = QColor("#FFFFFF")
            core.setAlpha(min(132, alpha + 26))
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(core))
            painter.drawEllipse(QRectF(x - size / 2, y - size / 2, size, size))

    def showEvent(self, event):
        super().showEvent(event)
        self._refresh_mask_animation_state()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._refresh_mask_animation_state()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._drag_pos and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._drag_pos = None

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        self.double_clicked.emit()
