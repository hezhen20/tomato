"""Paper workspace: warm stock, one soft lamp, static grain.

The redesign replaces the acrylic stack with a printed sheet: a single base
colour, a diffuse glow sampled from the accent, and a fixed grain texture.
Everything is cached per theme so the background costs one blit per repaint.
"""
from functools import lru_cache
import random
import sys

from PySide6.QtCore import QPoint, QRectF, Qt
from PySide6.QtGui import (
    QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient,
)
from PySide6.QtWidgets import QApplication, QFrame, QWidget

from app.ui.theme import current_mode, current_theme, resolve_theme, theme_colors


@lru_cache(maxsize=16)
def _paper(theme_id: str, mode: str, width: int = 960, height: int = 720) -> QPixmap:
    """Pre-render the sheet: stock colour, one lamp, and a faint vignette."""
    colors = resolve_theme(theme_id).colors_for(mode)
    image = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
    image.fill(QColor(colors["window"]))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)

    lamp = QRadialGradient(width * 0.5, height * 0.42, width * 0.62)
    glow = QColor(colors["glow"])
    glow.setAlpha(int(colors["glow_alpha"]))
    lamp.setColorAt(0.0, glow)
    glow.setAlpha(0)
    lamp.setColorAt(0.72, glow)
    painter.fillRect(image.rect(), lamp)

    if mode == "dark":
        # Night keeps a lamp-lit centre and lets the corners fall away.
        falloff = QRadialGradient(width * 0.5, height * 0.44, max(width, height) * 0.74)
        clear = QColor("#000000")
        clear.setAlpha(0)
        deep = QColor("#000000")
        deep.setAlpha(112)
        falloff.setColorAt(0.0, clear)
        falloff.setColorAt(0.58, clear)
        falloff.setColorAt(1.0, deep)
        painter.fillRect(image.rect(), falloff)
    else:
        edge = QLinearGradient(0, 0, 0, height)
        shade = QColor("#000000")
        shade.setAlpha(14)
        clear = QColor(shade)
        clear.setAlpha(0)
        edge.setColorAt(0.0, clear)
        edge.setColorAt(1.0, shade)
        painter.fillRect(image.rect(), edge)
    painter.end()
    return QPixmap.fromImage(image)


@lru_cache(maxsize=2)
def _grain(mode: str) -> QPixmap:
    size = 128
    image = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    rng = random.Random(728)
    alpha = 8 if mode == "dark" else 7
    tone = 255 if mode == "dark" else 40
    for y in range(size):
        for x in range(size):
            if rng.randrange(100) >= 58:
                continue
            value = 255 - abs(rng.randrange(90))
            color = QColor(tone, tone, tone, alpha)
            if mode == "light":
                color = QColor(90, 80, 60, alpha + rng.randrange(4))
            else:
                color = QColor(value, value, value, alpha + rng.randrange(3))
            image.setPixelColor(x, y, color)
    return QPixmap.fromImage(image)


class PaperWorkspace(QWidget):
    """The sheet everything is printed on."""

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.drawPixmap(
            self.rect(), _paper(current_theme().id, current_mode()),
        )
        painter.setOpacity(0.55 if current_mode() == "dark" else 0.75)
        painter.drawTiledPixmap(self.rect(), _grain(current_mode()))


# Kept for compatibility with older imports.
MaterialWorkspace = PaperWorkspace


def paint_surface(painter: QPainter, widget: QWidget, radius: int = 14,
                  variant: str = "panel", opacity: int = 216):
    """A sheet panel: translucent stock, hairline rule, no blur."""
    colors = theme_colors()
    rect = QRectF(widget.rect()).adjusted(.5, .5, -.5, -.5)
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing)

    tint = QColor(colors["surface"])
    tint.setAlpha(242 if variant == "solid" else opacity)
    painter.fillPath(path, tint)

    wash = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    sheen = QColor("#FFFFFF")
    sheen.setAlpha(28 if current_mode() == "light" else 16)
    clear = QColor(sheen)
    clear.setAlpha(0)
    wash.setColorAt(0.0, sheen)
    wash.setColorAt(1.0, clear)
    painter.fillPath(path, wash)

    painter.setPen(QPen(QColor(colors["border"]), 1))
    painter.setBrush(Qt.NoBrush)
    painter.drawPath(path)
    painter.restore()


def paint_frosted(painter: QPainter, widget: QWidget, radius: int = 14, variant: str = "panel"):
    """Compatibility shim for the floating chip and reminder toast."""
    paint_surface(painter, widget, radius, variant, opacity=236)


class FrostedSurface(QFrame):
    def __init__(self, parent=None, *, radius=14, variant="panel"):
        super().__init__(parent)
        self._radius = radius
        self._variant = variant

    def paintEvent(self, event):
        painter = QPainter(self)
        paint_surface(painter, self, self._radius, self._variant)


class PaperSurface(FrostedSurface):
    """Named alias for the redesign's opaque panels."""


def update_native_chrome(window: QWidget) -> bool:
    """Keep the native Windows title bar and corners consistent with the theme."""
    if sys.platform != "win32" or QApplication.platformName() != "windows":
        return False
    try:
        import ctypes
        from ctypes import wintypes
        dwm = ctypes.WinDLL("dwmapi")
        function = dwm.DwmSetWindowAttribute
        function.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
        function.restype = wintypes.LONG
        dark = ctypes.c_int(current_mode() == "dark")
        result = function(int(window.winId()), 20, ctypes.byref(dark), ctypes.sizeof(dark))
        return result >= 0
    except (OSError, AttributeError):
        return False
