"""Persistent accent themes. Product surfaces and user-defined mode colors stay separate."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import re
import sys

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from app.database import get_setting, set_settings
from app.ui.colors import contrast_ratio, foreground_for, mix_color, readable_color, relative_luminance


THEME_SETTING_KEY = "appearance_accent_theme"
DEFAULT_THEME_ID = "mint"
APPEARANCE_SETTING_KEY = "appearance_mode"
DEFAULT_APPEARANCE_MODE = "dark"
_current_mode = DEFAULT_APPEARANCE_MODE

# Catppuccin Latte-inspired light surfaces, paired with the established graphite
# dark surfaces. All content, controls, popups and painter-based UI share roles.
_SURFACES = {
    "dark": {
        "window": "#181B23", "sidebar": "#141820", "surface": "#222630",
        "surface_alt": "#272C37", "input": "#1C2029", "button": "#2B303B",
        "hover": "#343B48", "pressed": "#202630", "border": "#3E4655",
        "border_strong": "#626D7F", "text": "#E8EBF2", "title": "#F4F6FB",
        "muted": "#A8B1C2", "placeholder": "#A0ABBD", "disabled": "#778397",
        "track": "#3A4352", "danger": "#ECA5AD", "danger_bg": "#412B34",
        "danger_hover": "#543440", "danger_border": "#82515F", "success": "#A6DDAF",
        "glass_tint": "#B6222630", "glass_edge": "#24E6EFFF",
        "material_highlight": "#8293B0",
    },
    "light": {
        "window": "#EFF1F5", "sidebar": "#E6E9EF", "surface": "#FFFFFF",
        "surface_alt": "#F1F3F8", "input": "#FFFFFF", "button": "#E8ECF3",
        "hover": "#DCE3EE", "pressed": "#D2DBE8", "border": "#C8CFDD",
        "border_strong": "#7E8CA4", "text": "#34394C", "title": "#202638",
        "muted": "#566178", "placeholder": "#606B80", "disabled": "#929BAE",
        "track": "#D4DBE7", "danger": "#A12F46", "danger_bg": "#FCE9EE",
        "danger_hover": "#F8D9E2", "danger_border": "#D192A1", "success": "#266A3D",
        "glass_tint": "#AEFFFFFF", "glass_edge": "#E1FFFFFF",
        "material_highlight": "#FFFFFF",
    },
}


@dataclass(frozen=True)
class ThemePreset:
    id: str
    name: str
    accent: str
    source_name: str
    source_url: str
    light_accent: str = ""

    @property
    def colors(self) -> dict[str, str]:
        return self.colors_for(current_mode())

    @lru_cache(maxsize=14)
    def colors_for(self, mode: str) -> dict[str, str]:
        mode = mode if mode in _SURFACES else DEFAULT_APPEARANCE_MODE
        roles = _SURFACES[mode]
        accent = self.light_accent if mode == "light" else self.accent
        accent = accent or readable_color(self.accent, roles["surface"])
        soft = mix_color(accent, roles["surface"], 0.89 if mode == "light" else 0.84)
        hero = mix_color(accent, roles["window"], 0.89)
        on_accent = foreground_for(accent)
        def variant(target, ratio):
            value = mix_color(accent, target, ratio)
            return value if contrast_ratio(on_accent, value) >= 4.5 else accent
        return {
            **roles,
            "accent": accent,
            "on_accent": on_accent,
            "accent_hover": variant("#000000" if relative_luminance(on_accent) > .5 else "#FFFFFF", 0.12),
            "accent_pressed": variant("#000000", 0.12),
            "accent_soft": soft,
            "accent_soft_hover": mix_color(accent, roles["surface"], 0.78),
            "accent_text": readable_color(accent, soft),
            "accent_border": mix_color(accent, roles["surface"], 0.35),
            "focus": readable_color(accent, roles["surface"], 3.3),
            "chart": readable_color(accent, roles["window"], 3.3),
            "selection": mix_color(accent, "#202227", 0.69),
            "selection_text": "#F4F5F7",
            "hero_background": hero,
            "hero_text": roles["title"],
            "hero_muted": readable_color(roles["muted"], hero),
        }


# Exact accent swatches from upstream palettes. Surface/hover roles are adapted
# for Tomato's graphite workspace, rather than claiming to port the full themes.
THEME_PRESETS = (
    ThemePreset("blue", "明亮蓝", "#89B4FA", "Catppuccin Mocha · Blue",
                "https://github.com/catppuccin/palette/blob/main/palette.json", "#1E66F5"),
    ThemePreset("purple", "Dracula 紫", "#BD93F9", "Dracula · Purple",
                "https://github.com/dracula/dracula-theme#color-palette-oss", "#644AC9"),
    ThemePreset("cyan", "Nord 冰青", "#88C0D0", "Nord · Frost / nord8",
                "https://github.com/nordtheme/nord/blob/develop/src/nord.styl", "#2E6F80"),
    ThemePreset("peach", "蜜桃橙", "#FAB387", "Catppuccin Mocha · Peach",
                "https://github.com/catppuccin/palette/blob/main/palette.json", "#FE640B"),
    ThemePreset("pink", "玫瑰粉", "#F5C2E7", "Catppuccin Mocha · Pink",
                "https://github.com/catppuccin/palette/blob/main/palette.json", "#EA76CB"),
    ThemePreset("green", "清新绿", "#A6E3A1", "Catppuccin Mocha · Green",
                "https://github.com/catppuccin/palette/blob/main/palette.json", "#40A02B"),
    ThemePreset("mint", "原版薄荷绿", "#A8D5BA", "Tomato 原有配色", "", "#24734B"),
)
_PRESETS_BY_ID = {preset.id: preset for preset in THEME_PRESETS}
_current_preset = _PRESETS_BY_ID[DEFAULT_THEME_ID]


def current_theme() -> ThemePreset:
    return _current_preset


def current_mode() -> str:
    return _current_mode


def theme_colors() -> dict[str, str]:
    return current_theme().colors


def mode_display_color(color: str, background: str | None = None) -> str:
    """Adapt user mode colors for reading without modifying their stored values."""
    return readable_color(color, background or theme_colors()["surface"])


def resolve_theme(theme_id: str) -> ThemePreset:
    """Unknown or obsolete saved values safely fall back to the existing theme."""
    return _PRESETS_BY_ID.get(theme_id, _PRESETS_BY_ID[DEFAULT_THEME_ID])


def stylesheet_template() -> str:
    if getattr(sys, "frozen", False):
        path = Path(sys._MEIPASS) / "app" / "ui" / "style.qss"
    else:
        path = Path(__file__).with_name("style.qss")
    return path.read_text(encoding="utf-8") if path.exists() else ""


def render_stylesheet(template: str, preset: ThemePreset | None = None, mode: str | None = None) -> str:
    colors = (preset or current_theme()).colors_for(mode or current_mode())
    return re.sub(r"@([a-z_]+)", lambda match: colors[match.group(1)], template)


def application_palette(preset: ThemePreset | None = None) -> QPalette:
    colors = (preset or current_theme()).colors
    palette = QPalette()
    for role, value in {
        QPalette.Window: colors["window"], QPalette.WindowText: colors["text"],
        QPalette.Base: colors["input"], QPalette.AlternateBase: colors["surface_alt"],
        QPalette.Text: colors["text"], QPalette.Button: colors["button"],
        QPalette.ButtonText: colors["text"], QPalette.Highlight: colors["selection"],
        QPalette.HighlightedText: "#F4F5F7", QPalette.ToolTipBase: colors["surface"],
        QPalette.ToolTipText: colors["text"], QPalette.PlaceholderText: colors["placeholder"],
        QPalette.Light: colors["border_strong"], QPalette.Midlight: colors["border"],
        QPalette.Mid: colors["border"], QPalette.Dark: colors["pressed"],
        QPalette.Shadow: colors["window"], QPalette.Link: colors["accent_text"],
    }.items():
        palette.setColor(role, QColor(value))
    for role in (QPalette.Text, QPalette.WindowText, QPalette.ButtonText):
        palette.setColor(QPalette.Disabled, role, QColor(colors["disabled"]))
    return palette


class ThemeManager(QObject):
    theme_changed = Signal(str)

    def __init__(self, app: QApplication):
        super().__init__(app)
        self._app = app
        self._template = stylesheet_template()
        self.apply(get_setting(THEME_SETTING_KEY, DEFAULT_THEME_ID),
                   mode=get_setting(APPEARANCE_SETTING_KEY, DEFAULT_APPEARANCE_MODE), persist=False)

    def apply(self, theme_id: str, *, mode: str | None = None, persist: bool = True):
        global _current_preset, _current_mode
        preset = resolve_theme(theme_id)
        appearance = current_mode() if mode is None else mode
        appearance = appearance if appearance in _SURFACES else DEFAULT_APPEARANCE_MODE
        stylesheet = render_stylesheet(self._template, preset, appearance)
        # Save before changing the UI, so a failed write cannot claim success.
        if persist:
            set_settings({THEME_SETTING_KEY: preset.id, APPEARANCE_SETTING_KEY: appearance})
        _current_preset = preset
        _current_mode = appearance
        self._app.setPalette(application_palette(preset))
        self._app.setStyleSheet(stylesheet)
        self.theme_changed.emit(preset.id)

    def set_mode(self, mode: str, *, persist: bool = True):
        self.apply(current_theme().id, mode=mode, persist=persist)


def theme_manager(app: QApplication | None = None) -> ThemeManager:
    app = app or QApplication.instance()
    if app is None:
        raise RuntimeError("Create QApplication before applying a theme")
    manager = getattr(app, "_tomato_theme_manager", None)
    if manager is None:
        manager = ThemeManager(app)
        app._tomato_theme_manager = manager
    return manager
