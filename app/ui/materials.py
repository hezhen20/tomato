"""In-app frosted materials using Qt's cached blur, tint, texture and highlights.

Material layering references Microsoft's open-source WinUI Gallery / Acrylic:
https://github.com/microsoft/WinUI-Gallery
https://learn.microsoft.com/windows/apps/design/style/acrylic
Only the painted background is blurred; text and controls stay native and sharp.
"""
from functools import lru_cache
import random
import sys

from PySide6.QtCore import QPoint, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient
from PySide6.QtWidgets import QApplication, QFrame, QGraphicsBlurEffect, QGraphicsScene, QWidget

from app.ui.theme import current_mode, current_theme, resolve_theme, theme_colors


@lru_cache(maxsize=14)
def _backdrop(theme_id: str, mode: str) -> QImage:
    colors = resolve_theme(theme_id).colors_for(mode)
    image = QImage(384, 288, QImage.Format_ARGB32_Premultiplied)
    image.fill(QColor(colors["window"]))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    # Diffuse accent illumination gives translucent panels a visible substrate.
    for x, y, radius, opacity in [(330, 34, 180, 62), (48, 240, 158, 34)]:
        glow = QRadialGradient(x, y, radius)
        color = QColor(colors["accent"])
        color.setAlpha(opacity if mode == "dark" else int(opacity * .72))
        glow.setColorAt(0, color)
        color.setAlpha(0)
        glow.setColorAt(1, color)
        painter.fillRect(image.rect(), glow)
    painter.end()
    scene = QGraphicsScene()
    scene.setSceneRect(QRectF(image.rect()))
    item = scene.addPixmap(QPixmap.fromImage(image))
    blur = QGraphicsBlurEffect()
    blur.setBlurRadius(18)
    blur.setBlurHints(QGraphicsBlurEffect.QualityHint)
    item.setGraphicsEffect(blur)
    output = QImage(image.size(), image.format())
    output.fill(QColor(colors["window"]))
    painter = QPainter(output)
    scene.render(painter, QRectF(output.rect()), QRectF(image.rect()))
    painter.end()
    return output


@lru_cache(maxsize=2)
def _grain(mode: str) -> QPixmap:
    image = QImage(96, 96, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    rng = random.Random(728)
    for y in range(96):
        for x in range(96):
            value = rng.randrange(256)
            image.setPixelColor(x, y, QColor(value, value, value, 9 if mode == "dark" else 11))
    return QPixmap.fromImage(image)


class MaterialWorkspace(QWidget):
    """Stable background sampling coordinates for all in-app acrylic panes."""
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.drawImage(QRectF(self.rect()), _backdrop(current_theme().id, current_mode()))
        painter.setOpacity(.35)
        painter.drawTiledPixmap(self.rect(), _grain(current_mode()))


def paint_frosted(painter: QPainter, widget: QWidget, radius: int = 14, variant: str = "panel"):
    """Draw a blurred substrate, a high-opacity tint, grain, and a lit rim."""
    colors = theme_colors()
    rect = QRectF(widget.rect()).adjusted(.5, .5, -.5, -.5)
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.SmoothPixmapTransform)
    painter.setClipPath(path)
    workspace = widget.parentWidget()
    while workspace is not None and not isinstance(workspace, MaterialWorkspace):
        workspace = workspace.parentWidget()
    if workspace is None:
        painter.drawImage(rect, _backdrop(current_theme().id, current_mode()))
    else:
        position = widget.mapTo(workspace, QPoint(0, 0))
        painter.drawImage(QRectF(-position.x(), -position.y(), workspace.width(), workspace.height()),
                          _backdrop(current_theme().id, current_mode()))
    tint = QColor(colors["sidebar"] if variant == "sidebar" else colors["surface"])
    tint.setAlpha(170 if variant == "hero" else 188 if variant == "sidebar" else 176)
    painter.fillPath(path, tint)
    light = QLinearGradient(rect.topLeft(), rect.bottomRight())
    top = QColor("#FFFFFF")
    top.setAlpha(13 if current_mode() == "dark" else 110)
    clear = QColor(top)
    clear.setAlpha(0)
    light.setColorAt(0, top)
    light.setColorAt(.65, clear)
    painter.fillPath(path, light)
    painter.setOpacity(.65)
    painter.drawTiledPixmap(widget.rect(), _grain(current_mode()))
    painter.setOpacity(1)
    painter.setClipping(False)
    edge = QLinearGradient(rect.topLeft(), rect.bottomRight())
    edge.setColorAt(0, QColor(colors["glass_edge"]))
    edge.setColorAt(1, QColor(colors["border"]))
    painter.setPen(QPen(edge, 1))
    painter.setBrush(Qt.NoBrush)
    painter.drawPath(path)
    painter.restore()


class FrostedSurface(QFrame):
    def __init__(self, parent=None, *, radius=14, variant="panel"):
        super().__init__(parent)
        self._radius = radius
        self._variant = variant

    def paintEvent(self, event):
        painter = QPainter(self)
        paint_frosted(painter, self, self._radius, self._variant)


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
