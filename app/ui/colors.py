"""UI 颜色工具：在深色主题中保证自定义模式颜色可读。"""

from PySide6.QtGui import QColor


INK = "#061017"
WHITE = "#F8FAFC"
SURFACE = "#0D1220"
BRAND_GREEN = "#00F5A0"


def _color(value: str, fallback: str = BRAND_GREEN) -> QColor:
    qcolor = QColor(value)
    if qcolor.isValid():
        return qcolor
    return QColor(fallback)


def _linear_channel(value: int) -> float:
    channel = value / 255
    if channel <= 0.03928:
        return channel / 12.92
    return ((channel + 0.055) / 1.055) ** 2.4


def relative_luminance(value: str) -> float:
    qcolor = _color(value)
    return (
        0.2126 * _linear_channel(qcolor.red())
        + 0.7152 * _linear_channel(qcolor.green())
        + 0.0722 * _linear_channel(qcolor.blue())
    )


def contrast_ratio(foreground: str, background: str = SURFACE) -> float:
    fg = relative_luminance(foreground)
    bg = relative_luminance(background)
    lighter = max(fg, bg)
    darker = min(fg, bg)
    return (lighter + 0.05) / (darker + 0.05)


def mix_color(source: str, target: str = SURFACE, target_ratio: float = 0.9) -> str:
    """把 source 向 target 混合，常用于深色主题下的模式胶囊背景。"""
    source_color = _color(source)
    target_color = _color(target, WHITE)
    ratio = max(0.0, min(1.0, target_ratio))
    red = int(source_color.red() * (1 - ratio) + target_color.red() * ratio)
    green = int(source_color.green() * (1 - ratio) + target_color.green() * ratio)
    blue = int(source_color.blue() * (1 - ratio) + target_color.blue() * ratio)
    return QColor(red, green, blue).name().upper()


def readable_color(color: str, background: str = SURFACE, min_ratio: float = 4.5) -> str:
    """返回同一模式色的可读版本，避免暗色在深底上看不清。"""
    base = _color(color)
    original = base.name().upper()
    if contrast_ratio(original, background) >= min_ratio:
        return original

    # 浅底上向正文色收敛；深底上向白色收敛，保留部分原始色相。
    target = INK if relative_luminance(background) > 0.5 else WHITE
    best = original
    best_ratio = contrast_ratio(original, background)
    for step in range(1, 21):
        candidate = mix_color(original, target, step / 20)
        ratio = contrast_ratio(candidate, background)
        if ratio > best_ratio:
            best = candidate
            best_ratio = ratio
        if ratio >= min_ratio:
            return candidate
    return best


def foreground_for(background: str) -> str:
    """为模式色填充背景挑选白字或深色字。"""
    bg = _color(background).name().upper()
    white_ratio = contrast_ratio(WHITE, bg)
    ink_ratio = contrast_ratio(INK, bg)
    return WHITE if white_ratio >= ink_ratio else INK


def color_swatch_style(color: str, radius: int = 16) -> str:
    border = mix_color(readable_color(color), WHITE, 0.25)
    return f"background-color: {_color(color).name().upper()}; border-radius: {radius}px; border: 2px solid {border};"
