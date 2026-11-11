"""Persistent accent themes on a paper-and-ink surface system.

The redesign treats the workspace as a sheet of paper: warm stock, ink text,
hairline rules and a single vermilion accent. Light mode is daylight paper,
dark mode is the same sheet at night.
"""
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
DEFAULT_THEME_ID = "vermilion"
APPEARANCE_SETTING_KEY = "appearance_mode"
DEFAULT_APPEARANCE_MODE = "light"
_current_mode = DEFAULT_APPEARANCE_MODE

# Paper stock, ink and rules. Both modes share the same roles so every widget,
# popup and painter can ask for one vocabulary.
_SURFACES = {
    "light": {
        "window": "#F3ECDE", "sidebar": "#EDE4D3", "surface": "#FAF5EA",
        "surface_alt": "#EEE6D6", "input": "#FBF7EE", "button": "#EDE4D3",
        "hover": "#E7DCC7", "pressed": "#DED2BA", "border": "#241B1A16",
        "border_strong": "#381B1A16", "text": "#1B1A16", "title": "#121110",
        "muted": "#5B5649", "placeholder": "#655F50", "disabled": "#A49C8B",
        "track": "#DFD3BC", "danger": "#B4352A", "danger_bg": "#F3DAD3",
        "danger_hover": "#EDCCC3", "danger_border": "#D9A79B", "success": "#4C7A45",
        "glass_tint": "#CCFBF7EE", "glass_edge": "#59FFFFFF",
        "material_highlight": "#FFFFFF",
        # paper-specific roles
        "paper": "#F3ECDE", "paper_hi": "#FAF5EA", "ink": "#1B1A16",
        "on_ink": "#F6F0E3", "ink_fill": "#1B1A16",
        "rule": "#331B1A16", "rule_soft": "#1F1B1A16",
        "amber": "#EFCB78", "amber_soft": "#F4DCA6",
        "blue": "#3F6BA8", "olive": "#5B7F4A",
        "glow": "#EFCB78", "glow_alpha": "150",
    },
    # Night is the same sheet with the lamp off: a neutral near-black stock with
    # a faint green cast, cool white ink, and a single accent halo (方向 B · 柔光).
    "dark": {
        "window": "#0A0E0D", "sidebar": "#0C110F", "surface": "#111715",
        "surface_alt": "#17201D", "input": "#0E1413", "button": "#17201D",
        "hover": "#1B2523", "pressed": "#0C1211", "border": "#22E8F1EC",
        "border_strong": "#3AE8F1EC", "text": "#E7F0EA", "title": "#F7FCF9",
        "muted": "#93A29B", "placeholder": "#84948D", "disabled": "#566157",
        "track": "#1F2A27", "danger": "#E9907E", "danger_bg": "#2A1917",
        "danger_hover": "#35201D", "danger_border": "#6C3B31", "success": "#7FD8AB",
        "glass_tint": "#B3111715", "glass_edge": "#1CFFFFFF",
        "material_highlight": "#E7F0EA",
        "paper": "#0A0E0D", "paper_hi": "#111715", "ink": "#E7F0EA",
        "on_ink": "#0A0E0D", "ink_fill": "#E7F0EA",
        "rule": "#2AE8F1EC", "rule_soft": "#14E8F1EC",
        "amber": "#8FE9C0", "amber_soft": "#17302A",
        "blue": "#7FA8DE", "olive": "#8FC7A6",
        # A cool, nearly colourless lamp: a tinted page wash is what made the old
        # night mode read as brown. The accent halo lives on the dial instead.
        "glow": "#7FC9AE", "glow_alpha": "20",
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

    @lru_cache(maxsize=16)
    def colors_for(self, mode: str) -> dict[str, str]:
        mode = mode if mode in _SURFACES else DEFAULT_APPEARANCE_MODE
        roles = _SURFACES[mode]
        accent = self.light_accent if mode == "light" else self.accent
        accent = accent or readable_color(self.accent, roles["surface"])
        soft = mix_color(accent, roles["surface"], 0.88 if mode == "light" else 0.84)
        hero = mix_color(accent, roles["window"], 0.90)
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
            "selection": mix_color(accent, "#1B1A16", 0.72),
            "selection_text": "#F6F2E7",
            "hero_background": hero,
            "hero_text": roles["title"],
            "hero_muted": readable_color(roles["muted"], hero),
            # Dock pill: daylight keeps the highlighter band, night collapses the
            # gradient into one soft accent wash (方向 B · 柔光聚焦).
            "pill_from": "rgba(239, 203, 120, 0)" if mode == "light" else soft,
            "pill_to": roles["amber"] if mode == "light" else soft,
            "pill_text": roles["text"] if mode == "light" else readable_color(accent, soft),
            # Night keeps the sheet neutral and lets only the dial carry the
            # accent lamp, so the dark surface never drifts toward brown.
            "dial_glow": roles["glow"] if mode == "light" else accent,
            "dial_glow_alpha": "58" if mode == "light" else "30",
        }


# Accent swatches. Vermilion is the house colour of the paper redesign; the
# upstream palettes stay available for people who prefer another ink.
THEME_PRESETS = (
    ThemePreset("vermilion", "朱砂", "#E2674C", "Tomato 纸感配色", "", "#C1462F"),
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
        QPalette.HighlightedText: colors["selection_text"], QPalette.ToolTipBase: colors["surface"],
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
