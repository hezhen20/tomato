"""Shared paper-and-ink UI primitives, drawn with QPainter.

Everything here is painted locally: no external assets, no network access, and
no dependency on a widget style for the parts that carry the design.
"""
from __future__ import annotations

from PySide6.QtCore import (
    QByteArray, QEvent, QEasingCurve, QPointF, QRectF, QSize, Qt,
    QVariantAnimation,
)
from PySide6.QtGui import (
    QColor, QFont, QFontMetrics, QIcon, QPainter, QPainterPath, QPen, QPixmap,
    QRadialGradient,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSizePolicy,
    QToolTip, QVBoxLayout, QWidget,
)
from app.ui.colors import mix_color, readable_color
from app.ui.theme import application_palette, current_mode, current_theme, theme_colors

# Lucide icons, MIT license: https://github.com/lucide-icons/lucide
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
    "chevron-down": '<path d="m6 9 6 6 6-6"/>',
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

UI_FONTS = ["Segoe UI", "Microsoft YaHei UI", "PingFang SC"]
SERIF_FONTS = ["Songti SC", "SimSun", "STSong", "Georgia", "serif"]
MONO_FONTS = ["Consolas", "Cascadia Mono", "Courier New", "monospace"]


def ui_font(size: int, weight: int = QFont.Normal) -> QFont:
    font = QFont()
    font.setFamilies(UI_FONTS)
    font.setPixelSize(size)
    font.setWeight(weight)
    return font


def serif_font(size: int, weight: int = QFont.Bold) -> QFont:
    font = QFont()
    font.setFamilies(SERIF_FONTS)
    font.setPixelSize(size)
    font.setWeight(weight)
    return font


def mono_font(size: int, weight: int = QFont.Normal) -> QFont:
    font = QFont()
    font.setFamilies(MONO_FONTS)
    font.setPixelSize(size)
    font.setWeight(weight)
    font.setStyleHint(QFont.Monospace)
    return font


def configure_application(app):
    """Give native popups and spin controls the same paper palette as QSS."""
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


def _paint_mark(painter: QPainter, ink: QColor, size: int):
    """Draw the seal-plus-hourglass mark on a 24x24 grid.

    Two optical sizes: below 22px the seal rule is dropped and the glass grows
    to fill the frame, which is the only way a 16px tray icon keeps its shape.
    """
    framed = size >= 22
    if framed:
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(ink, 1.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawRoundedRect(QRectF(1.4, 1.4, 21.2, 21.2), 5.2, 5.2)
        top, bottom, half, waist, bow, stroke = 4.6, 19.4, 5.5, 0.8, 0.8, 1.75
    else:
        top, bottom, half, waist, bow, stroke = 2.6, 21.4, 7.2, 1.0, 1.0, 2.2

    # Glass: two bowed triangles meeting at a narrow waist.
    upper_mid = (top + 12 - waist) / 2
    lower_mid = (bottom + 12 + waist) / 2
    glass = QPainterPath()
    glass.moveTo(12 - half, top)
    glass.lineTo(12 + half, top)
    glass.quadTo(12 + bow, upper_mid, 12, 12 - waist)
    glass.quadTo(12 - bow, upper_mid, 12 - half, top)
    glass.closeSubpath()
    glass.moveTo(12 - half, bottom)
    glass.lineTo(12 + half, bottom)
    glass.quadTo(12 + bow, lower_mid, 12, 12 + waist)
    glass.quadTo(12 - bow, lower_mid, 12 - half, bottom)
    glass.closeSubpath()
    painter.setBrush(Qt.NoBrush)
    painter.setPen(QPen(ink, stroke, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.drawPath(glass)

    # The sand state is the whole story: lower bulb filled, upper bulb empty.
    # Filling it also gives the mark a solid mass that survives 16px.
    sand = QPainterPath()
    sand.moveTo(12 - (half - 1.1), bottom - 0.85)
    sand.lineTo(12 + (half - 1.1), bottom - 0.85)
    sand.lineTo(12, 12 + waist + 0.95)
    sand.closeSubpath()
    painter.setPen(Qt.NoPen)
    painter.setBrush(ink)
    painter.drawPath(sand)


def _render_mark(size: int, ratio: int = 2) -> QPixmap:
    """Paint the mark at `ratio` times the requested size for clean edges."""
    pix = QPixmap(size * ratio, size * ratio)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.scale(size * ratio / 24, size * ratio / 24)
    _paint_mark(painter, QColor(theme_colors()["accent"]), size)
    painter.end()
    return pix


def logo(size: int = 36) -> QPixmap:
    """A vermilion seal holding a sand glass — the app mark.

    The seal keeps the paper-and-ink identity; the hourglass carries the time
    meaning without borrowing a glyph. A filled lower bulb under an empty one
    says "counting down" before any word does.
    """
    pix = _render_mark(size)
    pix.setDevicePixelRatio(2)
    return pix


def app_icon() -> QIcon:
    """Every size Windows asks for, each drawn at its own weight.

    A single bitmap downscaled by the shell loses the glass outline at 16px;
    drawing each size keeps the mark readable in the title bar, the taskbar
    and the Alt-Tab switcher alike.
    """
    mark = QIcon()
    for size in (16, 20, 24, 32, 40, 48, 64, 128, 256):
        entry = _render_mark(size).scaled(
            size, size, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        mark.addPixmap(entry)
    return mark


def swatch_icon(color: str, size: int = 28) -> QIcon:
    pix = QPixmap(size * 2, size * 2)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QPen(QColor(theme_colors()["border_strong"]), 1))
    painter.setBrush(QColor(color))
    painter.drawEllipse(QRectF(3, 3, size * 2 - 6, size * 2 - 6))
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
    copy.setSpacing(7)
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


class Rule(QFrame):
    """A hairline printed rule."""

    def __init__(self, strong: bool = False, parent=None):
        super().__init__(parent)
        self._strong = strong
        self.setFixedHeight(1)

    def paintEvent(self, event):
        painter = QPainter(self)
        color = QColor(theme_colors()["rule"] if self._strong else theme_colors()["rule_soft"])
        painter.fillRect(self.rect(), color)


class RingDial(QWidget):
    """A printed dial: sixty ticks, one progress arc, a soft lamp behind it."""

    def __init__(self, diameter: int = 496, parent=None):
        super().__init__(parent)
        self._progress = 0.0
        self._diameter = diameter
        self.setFixedSize(diameter, diameter)
        self.setAccessibleName("当前专注进度")

    def set_progress(self, value: float):
        value = max(0.0, min(1.0, float(value)))
        if abs(value - self._progress) < 0.004:
            return
        self._progress = value
        self.update()

    def set_diameter(self, diameter: int):
        if diameter == self._diameter:
            return
        self._diameter = diameter
        self.setFixedSize(diameter, diameter)
        self.update()

    def paintEvent(self, event):
        colors = theme_colors()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        size = min(self.width(), self.height())
        center = QRectF(0, 0, size, size).center()
        radius = size * 0.379
        tick_inner = radius + size * 0.022
        tick_outer = radius + size * 0.040

        # the lamp behind the dial: a warm disc on paper, a halo hugging the ring at night
        glow = QColor(colors["dial_glow"])
        glow.setAlpha(int(colors["dial_glow_alpha"]))
        if current_mode() == "dark":
            spread = radius * 1.18
            lamp = QRadialGradient(center, spread)
            clear = QColor(glow)
            clear.setAlpha(0)
            lamp.setColorAt(0.0, clear)
            lamp.setColorAt(0.60, clear)
            lamp.setColorAt(0.88, glow)
            lamp.setColorAt(1.0, clear)
        else:
            spread = radius * 1.5
            lamp = QRadialGradient(center, spread)
            lamp.setColorAt(0.0, glow)
            clear = QColor(glow)
            clear.setAlpha(0)
            lamp.setColorAt(0.78, clear)
        painter.setPen(Qt.NoPen)
        painter.setBrush(lamp)
        painter.drawEllipse(center, spread, spread)

        tick_pen_soft = QPen(QColor(colors["ink"]))
        tick_pen_soft.setColor(QColor(colors["ink"]))
        c_soft = tick_pen_soft.color()
        c_soft.setAlpha(38 if current_mode() == "light" else 46)
        tick_pen_soft.setColor(c_soft)
        tick_pen_soft.setWidthF(1.0)
        tick_pen_soft.setCapStyle(Qt.RoundCap)

        tick_pen_strong = QPen(c_soft)
        tick_pen_strong.setColor(QColor(c_soft.red(), c_soft.green(), c_soft.blue(), 96 if current_mode() == "light" else 104))
        tick_pen_strong.setWidthF(1.3)
        tick_pen_strong.setCapStyle(Qt.RoundCap)

        import math
        for index in range(60):
            angle = index / 60 * math.tau - math.pi / 2
            major = index % 5 == 0
            start_r = tick_inner if major else tick_inner + size * 0.008
            painter.setPen(tick_pen_strong if major else tick_pen_soft)
            painter.drawLine(
                int(center.x() + math.cos(angle) * start_r), int(center.y() + math.sin(angle) * start_r),
                int(center.x() + math.cos(angle) * tick_outer), int(center.y() + math.sin(angle) * tick_outer),
            )

        face = QColor(colors["surface"])
        face.setAlpha(24 if current_mode() == "light" else 20)
        painter.setBrush(face)
        painter.setPen(QPen(QColor(colors["border"]), 1))
        painter.drawEllipse(center, radius, radius)

        if self._progress > 0.002:
            accent = QColor(colors["accent"])
            glow_pen = QPen(QColor(accent.red(), accent.green(), accent.blue(), 46), 9)
            glow_pen.setCapStyle(Qt.RoundCap)
            painter.setPen(glow_pen)
            painter.drawArc(
                QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2),
                int(90 * 16), int(-self._progress * 360 * 16),
            )
            arc_pen = QPen(accent, 2.4)
            arc_pen.setCapStyle(Qt.RoundCap)
            painter.setPen(arc_pen)
            painter.drawArc(
                QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2),
                int(90 * 16), int(-self._progress * 360 * 16),
            )
            # the head of the arc
            angle = -math.pi / 2 + self._progress * math.tau
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(accent.red(), accent.green(), accent.blue(), 235))
            painter.drawEllipse(
                QRectF(center.x() + math.cos(angle) * radius - 3.2,
                       center.y() + math.sin(angle) * radius - 3.2, 6.4, 6.4)
            )


class LedgerRow(QWidget):
    """A ruled row: dot, name, dotted leader, value. Painted, not boxed."""

    def __init__(self, name: str = "", color: str = "", value: str = "",
                 *, prefix: str = "", font_size: int = 14, parent=None):
        super().__init__(parent)
        self._name = name
        self._color = color
        self._value = value
        self._prefix = prefix
        self._font_size = font_size
        self._zero = False
        self.setFixedHeight(42 if not prefix else 40)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_data(self, name: str, color: str, value: str, *, prefix: str | None = None, zero: bool = False):
        self._name = name
        self._color = color
        self._value = value
        if prefix is not None:
            self._prefix = prefix
        self._zero = zero
        self.setToolTip(name)
        self.update()

    def paintEvent(self, event):
        colors = theme_colors()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0, 0, 0, 0)

        rule = QColor(colors["rule_soft"])
        painter.fillRect(QRectF(0, rect.height() - 1, rect.width(), 1), rule)

        x = 0.0
        if self._prefix:
            painter.setFont(mono_font(11))
            painter.setPen(QColor(colors["muted"]))
            prefix_width = 118 if len(self._prefix) > 6 else 82
            painter.drawText(QRectF(0, 0, prefix_width, rect.height()),
                             Qt.AlignVCenter | Qt.AlignLeft, self._prefix)
            x = prefix_width

        dot_color = QColor(self._color) if self._color else QColor(colors["muted"])
        if self._zero:
            dot_color.setAlpha(120)
        painter.setPen(Qt.NoPen)
        painter.setBrush(dot_color)
        painter.drawEllipse(QRectF(x + 4, rect.height() / 2 - 2.6, 5.2, 5.2))
        x += 20

        painter.setFont(ui_font(self._font_size))
        painter.setPen(QColor(colors["muted"] if self._zero else colors["text"]))
        metrics = QFontMetrics(painter.font())
        value_width = max(52.0, metrics.horizontalAdvance(self._value) + 8)
        name_rect = QRectF(x, 0, max(40.0, rect.width() - x - value_width - 26), rect.height())
        name = metrics.elidedText(self._name, Qt.ElideRight, int(name_rect.width()))
        painter.drawText(name_rect, Qt.AlignVCenter | Qt.AlignLeft, name)

        # dotted leader
        lead_start = x + metrics.horizontalAdvance(name) + 8
        lead_end = rect.width() - value_width - 10
        if lead_end > lead_start + 12:
            pen = QPen(QColor(colors["muted"]))
            pen.setColor(QColor(colors["muted"]))
            dot = pen.color()
            dot.setAlpha(110)
            pen.setColor(dot)
            pen.setWidthF(1)
            pen.setStyle(Qt.DotLine)
            painter.setPen(pen)
            painter.drawLine(int(lead_start), int(rect.height() / 2), int(lead_end), int(rect.height() / 2))

        painter.setFont(mono_font(12))
        painter.setPen(QColor(colors["muted"] if self._zero else colors["text"]))
        painter.drawText(QRectF(rect.width() - value_width, 0, value_width, rect.height()),
                         Qt.AlignVCenter | Qt.AlignRight, self._value)


class HatchChart(QWidget):
    """Hand-ledger bar chart: hatched columns, dashed guides, one accent bar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._columns = []          # [(label, seconds, is_accent)]
        self._caption = ""
        self._unit = 3600
        self._hover = -1
        self.setMinimumHeight(150)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setMouseTracking(True)
        self.setAccessibleName("每周投入柱状图")

    def set_columns(self, columns, *, caption: str = "", unit: int | None = None):
        self._columns = list(columns)
        self._caption = caption
        if unit is not None:
            self._unit = unit
        self.setAccessibleDescription("；".join(f"{label} {seconds} 秒" for label, seconds, _ in self._columns))
        self.update()

    def _bars_area(self) -> QRectF:
        return QRectF(self.rect()).adjusted(0, 26, 0, -26)

    def paintEvent(self, event):
        colors = theme_colors()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        area = self._bars_area()
        if not self._columns or area.width() <= 0:
            return

        peak = max((seconds for _, seconds, _ in self._columns), default=0)
        tallest = max(1, peak)

        # dashed guides
        for fraction in (0.25, 0.5, 0.75):
            y = area.bottom() - area.height() * fraction
            pen = QPen(QColor(colors["rule_soft"]))
            pen.setStyle(Qt.DashLine)
            pen.setWidthF(1)
            painter.setPen(pen)
            painter.drawLine(int(area.left()), int(y), int(area.right()), int(y))

        count = len(self._columns)
        step = area.width() / count
        bar_width = min(30.0, step * 0.55)
        painter.setFont(mono_font(10))
        for index, (label, seconds, is_accent) in enumerate(self._columns):
            height = 0.0 if not seconds else max(3.0, area.height() * seconds / tallest)
            x = area.left() + step * (index + 0.5) - bar_width / 2
            bar = QRectF(x, area.bottom() - height, bar_width, height)
            base = QColor(colors["accent"] if is_accent else colors["blue"])
            fill = QColor(base)
            fill.setAlpha(150 if is_accent else 108)
            painter.setPen(QPen(base, 1))
            painter.setBrush(fill)
            painter.drawRect(bar)

            # hatching
            painter.save()
            clip = QPainterPath()
            clip.addRect(bar)
            painter.setClipPath(clip)
            hatch = QPen(QColor(base.red(), base.green(), base.blue(), 190))
            hatch.setWidthF(1.0)
            painter.setPen(hatch)
            offset = -bar.height()
            while offset < bar.width() + bar.height():
                painter.drawLine(
                    int(bar.left() + offset), int(bar.bottom()),
                    int(bar.left() + offset + bar.height()), int(bar.top()),
                )
                offset += 5
            painter.restore()

            painter.setPen(QColor(colors["accent"] if is_accent else colors["muted"]))
            painter.setFont(mono_font(11))
            if seconds:
                painter.drawText(QRectF(x - 16, bar.top() - 19, bar_width + 32, 15),
                                 Qt.AlignCenter, self._short_duration(seconds))
            painter.setPen(QColor(colors["accent"] if is_accent else colors["muted"]))
            painter.setFont(ui_font(11))
            painter.drawText(QRectF(area.left() + step * index, area.bottom() + 7, step, 16),
                             Qt.AlignCenter, label)

        painter.setPen(QPen(QColor(colors["rule"]), 1))
        painter.drawLine(int(area.left()), int(area.bottom()), int(area.right()), int(area.bottom()))

    @staticmethod
    def _short_duration(seconds: int) -> str:
        hours, rest = divmod(int(seconds), 3600)
        minutes = rest // 60
        if hours:
            return f"{hours}h{minutes:02d}"
        return f"{minutes}m" if minutes else f"{seconds}s"

    def mouseMoveEvent(self, event):
        area = self._bars_area()
        if not self._columns or area.width() <= 0:
            return
        index = int((event.position().x() - area.left()) / (area.width() / len(self._columns)))
        index = max(0, min(len(self._columns) - 1, index))
        if index != self._hover:
            self._hover = index
            label, seconds, _ = self._columns[index]
            hours, rest = divmod(int(seconds), 3600)
            minutes = rest // 60
            text = f"{label} · {hours}小时 {minutes}分钟" if hours else f"{label} · {minutes}分钟"
            QToolTip.showText(event.globalPosition().toPoint(), text, self)
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._hover = -1
        QToolTip.hideText()
        super().leaveEvent(event)


class Seal(QWidget):
    """A rubber stamp: date and weekday inside a rotated double rule."""

    def __init__(self, top: str = "", bottom: str = "WED", size: int = 64, parent=None):
        super().__init__(parent)
        self._top = top
        self._bottom = bottom
        self.setFixedSize(size, size)
        self.setAccessibleName(f"日期 {top}")

    def set_text(self, top: str, bottom: str = ""):
        self._top = top
        if bottom:
            self._bottom = bottom
        self.update()

    def paintEvent(self, event):
        colors = theme_colors()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        painter.translate(self.width() / 2, self.height() / 2)
        painter.rotate(-7)
        side = min(self.width(), self.height()) - 4
        rect = QRectF(-side / 2, -side / 2, side, side)
        ink = QColor(colors["accent"])
        ink.setAlpha(165)
        painter.setPen(QPen(ink, 1.6))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect, 4, 4)
        faint = QColor(ink)
        faint.setAlpha(80)
        painter.setPen(QPen(faint, 0.9))
        painter.drawRoundedRect(rect.adjusted(4, 4, -4, -4), 2, 2)
        painter.setFont(serif_font(int(side * 0.26)))
        painter.setPen(ink)
        painter.drawText(QRectF(rect.left(), rect.top() + side * 0.16, side, side * 0.34),
                         Qt.AlignCenter, self._top)
        painter.setFont(mono_font(max(9, int(side * 0.15))))
        painter.drawText(QRectF(rect.left(), rect.top() + side * 0.56, side, side * 0.2),
                         Qt.AlignCenter, self._bottom)


class IndexButton(QPushButton):
    """Left-hand numbered index used by settings."""

    def __init__(self, number: str, title: str, parent=None):
        super().__init__(title, parent)
        self._number = number
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(40)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setAccessibleName(f"{number} {title}")
        self.setFlat(True)

    def paintEvent(self, event):
        colors = theme_colors()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect())
        active = self.isChecked()
        if active:
            painter.fillRect(QRectF(0, 8, 2, rect.height() - 16), QColor(colors["accent"]))
        elif self.underMouse():
            painter.fillRect(rect.adjusted(6, 2, -2, -2), QColor(colors["hover"]))

        painter.setFont(mono_font(10))
        painter.setPen(QColor(colors["accent"] if active else colors["muted"]))
        painter.drawText(QRectF(14, 0, 24, rect.height()), Qt.AlignVCenter | Qt.AlignLeft, self._number)

        painter.setFont(ui_font(13, QFont.DemiBold if active else QFont.Normal))
        painter.setPen(QColor(colors["text"] if active else colors["muted"]))
        painter.drawText(QRectF(40, 0, rect.width() - 46, rect.height()),
                         Qt.AlignVCenter | Qt.AlignLeft, self.text())

    def enterEvent(self, event):
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.update()
        super().leaveEvent(event)


class ActivityChart(QWidget):
    """Exact recorded durations, with zero-value days kept in the time axis."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._days = []
        self._dates = []
        self._detail_labels = []
        self._value_label = "每日投入"
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

    def set_days(self, days, *, dates=None, detail_labels=None, value_label="每日投入"):
        days = list(days)
        dates = list(dates) if dates is not None else [None] * len(days)
        if len(dates) != len(days):
            raise ValueError("Each chart day must have a matching date")
        detail_labels = list(detail_labels) if detail_labels is not None else [None] * len(days)
        if len(detail_labels) != len(days):
            raise ValueError("Each chart column must have a matching detail label")
        if (days == self._days and dates == self._dates
                and detail_labels == self._detail_labels and value_label == self._value_label):
            return
        self._reset_hover()
        self._days, self._dates = days, dates
        self._detail_labels, self._value_label = detail_labels, value_label
        self._hover_levels = [0.0] * len(days)
        self.setAccessibleDescription("；".join(
            self._detail_text(i).replace("\n", "，") for i in range(len(days))
        ))
        if self.isVisible():
            self._start_reveal()
        self.update()

    def _plot_area(self):
        bottom_margin = max(28, self.fontMetrics().height() + 12)
        return QRectF(self.rect().adjusted(8, 22, -8, -bottom_margin))

    def _axis_labels(self, area):
        """Let text span adjacent columns, reserving space for both endpoints."""
        metrics = self.fontMetrics()
        count = len(self._days)
        step = area.width() / count

        def label_at(index):
            text = self._days[index][0]
            width = max(metrics.horizontalAdvance(text), metrics.boundingRect(text).width()) + 8
            center = area.left() + step * (index + .5)
            left = max(2, min(center - width / 2, self.width() - width - 2))
            return QRectF(left, area.bottom() + 6, width, metrics.height() + 2), text

        labels = [label_at(0)]
        last_rect, last_text = label_at(count - 1)
        gap = 8
        for index in range(1, count - 1):
            if count > 7 and index % 5:
                continue
            rect, text = label_at(index)
            if rect.left() >= labels[-1][0].right() + gap and rect.right() + gap <= last_rect.left():
                labels.append((rect, text))
        if count > 1 and last_rect.left() >= labels[-1][0].right() + gap:
            labels.append((last_rect, last_text))
        return labels

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
        if self._detail_labels[index] is not None:
            label = self._detail_labels[index]
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
        accent = QColor(colors["chart"])
        for i, (_, seconds) in enumerate(self._days):
            hover = self._hover_levels[i]
            width = max(3, step * (.54 + .08 * hover))
            x = area.left() + step * (i + .5) - width / 2
            height = max(3, area.height() * seconds / maximum * self._reveal)
            painter.setPen(Qt.NoPen)
            if hover > 0:
                highlight = QColor(accent)
                highlight.setAlphaF(.07 * hover)
                painter.setBrush(highlight)
                painter.drawRect(QRectF(area.left() + step * i, area.top(), step, area.height()))
            base = accent if seconds else QColor(colors["track"])
            fill = QColor(base)
            fill.setAlpha(60 if not seconds else 44 + int(40 * hover))
            painter.setPen(QPen(base, 1))
            painter.setBrush(fill)
            bar = QRectF(x, area.bottom() - height, width, height)
            painter.drawRect(bar)
            if seconds:
                painter.save()
                clip = QPainterPath()
                clip.addRect(bar)
                painter.setClipPath(clip)
                hatch = QPen(QColor(base.red(), base.green(), base.blue(), 165))
                hatch.setWidthF(1.0)
                painter.setPen(hatch)
                offset = -bar.height()
                while offset < bar.width() + bar.height():
                    painter.drawLine(int(bar.left() + offset), int(bar.bottom()),
                                     int(bar.left() + offset + bar.height()), int(bar.top()))
                    offset += 5
                painter.restore()

        painter.setPen(QPen(QColor(colors["rule"]), 1))
        painter.drawLine(int(area.left()), int(area.bottom()), int(area.right()), int(area.bottom()))

        painter.setFont(mono_font(10))
        painter.setPen(QColor(colors["muted"]))
        for rect, label in self._axis_labels(area):
            painter.drawText(rect, Qt.AlignCenter, label)
        hours, minutes = divmod(peak // 60, 60)
        painter.setPen(QColor(colors["muted"]))
        painter.drawText(8, 14, f"{self._value_label} · 最高 {hours}h {minutes:02d}m")

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
