"""设置页面 - 快捷键配置 + 模式管理 + 修改密码"""

from PySide6.QtCore import Qt, Signal, QEvent, QSize
from PySide6.QtGui import QColor, QKeyEvent
from PySide6.QtWidgets import (
    QColorDialog,
    QButtonGroup,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.database import (
    BREAK_REMINDER_ENABLED_KEY,
    BREAK_REMINDER_GRACE_KEY,
    BREAK_REMINDER_INTERVAL_KEY,
    BREAK_REMINDER_MESSAGE_DEFAULT,
    BREAK_REMINDER_MESSAGE_KEY,
    add_mode,
    break_reminder_enabled,
    break_reminder_grace_minutes,
    break_reminder_interval_minutes,
    break_reminder_message,
    change_password,
    delete_mode,
    get_modes,
    get_setting,
    set_setting,
    update_mode,
    verify_user,
)
from app.hotkeys import MODE_ACTION_PREFIX, mode_action_name
from app.ui.colors import color_swatch_style
from app.ui.mode_table import ModeTableView
from app.ui.components import icon, page_header, scroll_page, ElidedLabel, swatch_icon, set_feedback, IndexButton
from app.ui.theme import THEME_PRESETS, current_theme, current_mode, theme_manager, theme_colors

_KEY_NAMES = {
    Qt.Key_Control: "Ctrl",
    Qt.Key_Alt: "Alt",
    Qt.Key_Shift: "Shift",
    Qt.Key_Meta: "Win",
}
_MOD_KEYS = {Qt.Key_Control, Qt.Key_Alt, Qt.Key_Shift, Qt.Key_Meta}
FLOATING_TIME_MASK_KEY = "floating_time_glass_mask"
FLOATING_TIME_MASK_DEFAULT = "1"


def floating_time_mask_enabled() -> bool:
    return get_setting(FLOATING_TIME_MASK_KEY, FLOATING_TIME_MASK_DEFAULT).strip() != "0"


class HotkeyRecorder(QPushButton):
    """点击后进入录入状态，按下组合键自动记录。"""

    hotkey_changed = Signal(str)

    def __init__(self, initial_text: str = ""):
        super().__init__(initial_text or "点击设置快捷键")
        self._recording = False
        self._hotkey_display = initial_text
        self._held_modifiers = set()
        self.setMinimumWidth(160)
        self.setObjectName("hotkeyRecorder")
        self.setCursor(Qt.PointingHandCursor)
        self.clicked.connect(self._start_recording)

    def get_hotkey_display(self) -> str:
        return self._hotkey_display

    def set_hotkey_display(self, text: str):
        self._hotkey_display = text
        if not self._recording:
            self.setText(text or "点击设置快捷键")

    def _refresh_recording_style(self):
        self.setProperty("recording", self._recording)
        self.style().unpolish(self)
        self.style().polish(self)

    def _start_recording(self):
        self._recording = True
        self._held_modifiers.clear()
        self.setText("请按下快捷键...")
        self._refresh_recording_style()
        self.grabKeyboard()

    def _stop_recording(self):
        self._recording = False
        self._refresh_recording_style()
        self.releaseKeyboard()

    def event(self, event):
        # Recording takes precedence over the window's Alt+1/2/3 navigation.
        if event.type() == QEvent.ShortcutOverride and self._recording:
            event.accept()
            return True
        return super().event(event)

    def keyPressEvent(self, event: QKeyEvent):
        if not self._recording:
            super().keyPressEvent(event)
            return

        key = event.key()

        if key == Qt.Key_Escape:
            self.setText(self._hotkey_display or "点击设置快捷键")
            self._stop_recording()
            return

        if key in _MOD_KEYS:
            self._held_modifiers.add(key)
            parts = [_KEY_NAMES[k] for k in sorted(self._held_modifiers)]
            self.setText("+".join(parts) + "+...")
            return

        if not self._held_modifiers:
            self.setText("需要 Ctrl/Alt/Shift 组合")
            return

        parts = []
        for mod in [Qt.Key_Control, Qt.Key_Alt, Qt.Key_Shift, Qt.Key_Meta]:
            if mod in self._held_modifiers:
                parts.append(_KEY_NAMES[mod])

        key_text = event.text().upper()
        if not key_text.strip():
            key_text = _special_key_name(key)
        if not key_text:
            return

        parts.append(key_text)
        combo = "+".join(parts)

        self._hotkey_display = combo
        self.setText(combo)
        self._stop_recording()
        self.hotkey_changed.emit(combo)

    def keyReleaseEvent(self, event: QKeyEvent):
        if self._recording and event.key() in _MOD_KEYS:
            self._held_modifiers.discard(event.key())
        super().keyReleaseEvent(event)

    def focusOutEvent(self, event):
        if self._recording:
            self.setText(self._hotkey_display or "点击设置快捷键")
            self._stop_recording()
        super().focusOutEvent(event)


def _special_key_name(key: int) -> str:
    names = {
        Qt.Key_F1: "F1",
        Qt.Key_F2: "F2",
        Qt.Key_F3: "F3",
        Qt.Key_F4: "F4",
        Qt.Key_F5: "F5",
        Qt.Key_F6: "F6",
        Qt.Key_F7: "F7",
        Qt.Key_F8: "F8",
        Qt.Key_F9: "F9",
        Qt.Key_F10: "F10",
        Qt.Key_F11: "F11",
        Qt.Key_F12: "F12",
        Qt.Key_Space: "Space",
        Qt.Key_Return: "Enter",
        Qt.Key_Tab: "Tab",
        Qt.Key_Backspace: "Backspace",
        Qt.Key_Delete: "Delete",
        Qt.Key_Home: "Home",
        Qt.Key_End: "End",
        Qt.Key_PageUp: "PageUp",
        Qt.Key_PageDown: "PageDown",
        Qt.Key_Up: "Up",
        Qt.Key_Down: "Down",
        Qt.Key_Left: "Left",
        Qt.Key_Right: "Right",
        Qt.Key_Insert: "Insert",
    }
    return names.get(key, "")


class SettingsPage(QWidget):
    modes_changed = Signal()
    hotkeys_changed = Signal()
    floating_settings_changed = Signal(bool)
    reminder_settings_changed = Signal()

    def __init__(self, hotkey_manager, username: str):
        super().__init__()
        self._hotkey_manager = hotkey_manager
        self._username = username
        self.hotkey_recorders = {}
        self._mode_hotkey_row_widgets = []
        self._editing_mode_id = None
        self._editing_mode_name = ""
        self._editing_color = "#FF9800"
        self._theme_manager = theme_manager()
        self._setup_ui()
        self._theme_manager.theme_changed.connect(self._sync_theme_selection)

    def _setup_ui(self):
        self._hotkey_manager.sync_mode_hotkeys()

        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(44, 22, 44, 22)
        layout.addWidget(page_header("偏好设置", "让工具适应你，而不是反过来。"))

        body = QHBoxLayout()
        body.setSpacing(44)
        body.setContentsMargins(0, 16, 0, 0)

        index = QWidget()
        index.setFixedWidth(176)
        index_layout = QVBoxLayout(index)
        index_layout.setContentsMargins(0, 4, 0, 0)
        index_layout.setSpacing(2)
        self._index_buttons = []
        for offset, title in enumerate(
            ["模式管理", "全局快捷键", "休息提醒", "悬浮窗", "账户安全", "外观"], 1
        ):
            button = IndexButton(f"{offset:02d}", title)
            button.clicked.connect(lambda _, i=offset - 1: self._tabs.setCurrentIndex(i))
            index_layout.addWidget(button)
            self._index_buttons.append(button)
        index_layout.addStretch()
        foot = QLabel("数据保存在本机\nSQLite · 无云端同步")
        foot.setProperty("class", "mutedLabel")
        foot.setStyleSheet("font-size:10px; letter-spacing:1px; line-height:1.7;")
        index_layout.addWidget(foot)
        body.addWidget(index)

        tabs = QTabWidget()
        self._tabs = tabs
        tabs.setDocumentMode(True)
        for page, title in [
            (self._build_modes_tab(), "模式管理"),
            (self._build_hotkeys_tab(), "快捷键"),
            (self._build_reminder_tab(), "休息提醒"),
            (self._build_floating_tab(), "悬浮窗"),
            (self._build_password_tab(), "账户安全"),
            (self._build_appearance_tab(), "外观"),
        ]:
            page.layout().setContentsMargins(0, 4, 4, 0)
            tabs.addTab(scroll_page(page), title)
        tabs.tabBar().hide()
        tabs.currentChanged.connect(self.sync_index)
        body.addWidget(tabs, 1)
        layout.addLayout(body, 1)
        self.sync_index(0)
        for btn in self.findChildren(QPushButton):
            btn.setCursor(Qt.PointingHandCursor)

    def sync_index(self, index: int):
        for offset, button in enumerate(getattr(self, "_index_buttons", [])):
            button.setChecked(offset == index)

    def refresh_theme(self):
        if hasattr(self, "theme_buttons"):
            self._sync_theme_selection(current_theme().id)
        for button in getattr(self, "_index_buttons", []):
            button.update()
        if hasattr(self, "modes_table"):
            self._refresh_modes_table()
        self.update()

    @staticmethod
    def _section_intro(layout, title, description):
        heading = QLabel(title)
        heading.setProperty("class", "settingsTitle")
        layout.addWidget(heading)
        hint = QLabel(description)
        hint.setProperty("class", "mutedLabel")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addSpacing(12)

    def _build_appearance_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(14)
        self._section_intro(layout, "换一种颜色，找到喜欢的感觉", "选择后立即应用并自动保存，下次打开时依然是你的配色。")

        mode_title = QLabel("界面明暗")
        mode_title.setObjectName("appearanceSectionTitle")
        layout.addWidget(mode_title)
        modes = QHBoxLayout()
        modes.setSpacing(12)
        self.appearance_mode_buttons = {}
        self._appearance_mode_group = QButtonGroup(self)
        for mode, label, symbol in [("light", "浅色 · 清透", "sun"), ("dark", "深色 · 静谧", "moon")]:
            button = QPushButton(label)
            button.setProperty("class", "appearanceMode")
            button.setCheckable(True)
            button.setIcon(icon(symbol))
            button.setAccessibleName(label)
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda checked, value=mode: self._choose_appearance_mode(value))
            self._appearance_mode_group.addButton(button)
            self.appearance_mode_buttons[mode] = button
            modes.addWidget(button, 1)
        layout.addLayout(modes)
        layout.addSpacing(8)

        color_title = QLabel("强调色")
        color_title.setObjectName("appearanceSectionTitle")
        layout.addWidget(color_title)

        hint = QLabel("强调色用于圆环、印章、导航下划线与图表。你创建的模式颜色会继续保留。")
        hint.setProperty("class", "mutedLabel")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addSpacing(4)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        self.theme_buttons = {}
        self._theme_button_group = QButtonGroup(self)
        self._theme_button_group.setExclusive(True)
        for index, preset in enumerate(THEME_PRESETS):
            button = QPushButton(preset.name)
            button.setProperty("class", "themeChoice")
            button.setCheckable(True)
            button.setIcon(swatch_icon(preset.accent))
            button.setIconSize(QSize(28, 28))
            button.setCursor(Qt.PointingHandCursor)
            button.setAccessibleName(f"主题色：{preset.name}")
            button.setToolTip(f"{preset.source_name}\n{preset.accent}")
            button.clicked.connect(lambda checked, theme_id=preset.id: self._choose_theme(theme_id))
            self._theme_button_group.addButton(button)
            self.theme_buttons[preset.id] = button
            grid.addWidget(button, index // 2, index % 2)
        layout.addLayout(grid)

        self.theme_save_status = QLabel()
        self.theme_save_status.setObjectName("themeSaveStatus")
        self.theme_save_status.setWordWrap(True)
        layout.addWidget(self.theme_save_status)
        self.theme_source = QLabel()
        self.theme_source.setObjectName("themeSource")
        self.theme_source.setWordWrap(True)
        self.theme_source.setOpenExternalLinks(True)
        layout.addWidget(self.theme_source)

        note = QLabel("配色参考 Catppuccin、Dracula 和 Nord。界面为纸感底色、发丝线与印章式标记。")
        note.setProperty("class", "mutedLabel")
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch()
        self._sync_theme_selection(current_theme().id)
        return widget

    def _choose_theme(self, theme_id):
        try:
            self._theme_manager.apply(theme_id)
        except Exception as exc:
            self._sync_theme_selection(current_theme().id)
            QMessageBox.warning(self, "主题色未保存", f"保存失败，请重试：{exc}")

    def _choose_appearance_mode(self, mode):
        try:
            self._theme_manager.set_mode(mode)
        except Exception as exc:
            self._sync_theme_selection(current_theme().id)
            QMessageBox.warning(self, "外观未保存", f"保存失败，请重试：{exc}")

    def _sync_theme_selection(self, theme_id):
        if not hasattr(self, "theme_buttons"):
            return
        self.theme_buttons[theme_id].setChecked(True)
        self.appearance_mode_buttons[current_mode()].setChecked(True)
        preset = current_theme()
        mode_name = "浅色" if current_mode() == "light" else "深色"
        self.theme_save_status.setText(f"当前外观：{mode_name} · {preset.name} · 自动保存")
        for value, button in self.appearance_mode_buttons.items():
            button.setIcon(icon("sun" if value == "light" else "moon", theme_colors()["accent_text"] if value == current_mode() else theme_colors()["muted"]))
        for choice in THEME_PRESETS:
            self.theme_buttons[choice.id].setIcon(swatch_icon(choice.colors["accent"]))
        if preset.source_url:
            link_color = preset.colors["accent_text"]
            self.theme_source.setText(f'配色来源：<a style="color:{link_color}" href="{preset.source_url}">{preset.source_name}</a>')
        else:
            self.theme_source.setText("配色来源：Tomato 原有配色")
        if hasattr(self, "_add_mode_button"):
            self._add_mode_button.setIcon(icon("plus", preset.colors["on_accent"]))

    def _build_modes_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)
        self._section_intro(layout, "为不同的事情，留出专属时间", "自定义工作、学习或生活模式。颜色将用于计时和统计中的模式识别。")

        add_layout = QHBoxLayout()
        self.new_mode_input = QLineEdit()
        self.new_mode_input.setPlaceholderText("新模式名称")
        add_layout.addWidget(self.new_mode_input)

        self._new_color = "#FF9800"
        self.color_btn = QPushButton()
        self.color_btn.setProperty("class", "colorBtn")
        self.color_btn.setFixedSize(32, 32)
        self.color_btn.setAccessibleName("新模式颜色")
        self.color_btn.setToolTip("选择新模式颜色")
        self.color_btn.setStyleSheet(color_swatch_style(self._new_color))
        self.color_btn.clicked.connect(self._pick_color)
        add_layout.addWidget(self.color_btn)

        add_btn = QPushButton("添加")
        add_btn.setObjectName("primaryButton")
        add_btn.setIcon(icon("plus", current_theme().colors["on_accent"]))
        self._add_mode_button = add_btn
        add_btn.clicked.connect(self._add_mode)
        add_layout.addWidget(add_btn)
        layout.addLayout(add_layout)

        edit_panel = QFrame()
        edit_panel.setObjectName("settingsCard")
        edit_layout = QHBoxLayout(edit_panel)
        edit_layout.setContentsMargins(10, 8, 10, 8)
        edit_layout.setSpacing(8)

        self.edit_mode_input = QLineEdit()
        self.edit_mode_input.setPlaceholderText("编辑模式名称")
        edit_layout.addWidget(self.edit_mode_input, 1)

        self.edit_color_btn = QPushButton()
        self.edit_color_btn.setProperty("class", "colorBtn")
        self.edit_color_btn.setFixedSize(32, 32)
        self.edit_color_btn.setAccessibleName("编辑模式颜色")
        self.edit_color_btn.setStyleSheet(color_swatch_style(self._editing_color))
        self.edit_color_btn.clicked.connect(self._pick_edit_color)
        edit_layout.addWidget(self.edit_color_btn)

        save_edit_btn = QPushButton("保存")
        save_edit_btn.setObjectName("primaryButton")
        save_edit_btn.setMinimumWidth(54)
        save_edit_btn.clicked.connect(self._save_mode_edit)
        edit_layout.addWidget(save_edit_btn)

        cancel_edit_btn = QPushButton("取消")
        cancel_edit_btn.setObjectName("ghostButton")
        cancel_edit_btn.setMinimumWidth(54)
        cancel_edit_btn.clicked.connect(self._cancel_mode_edit)
        edit_layout.addWidget(cancel_edit_btn)

        self._edit_mode_panel = edit_panel
        self._edit_mode_panel.setVisible(False)
        layout.addWidget(self._edit_mode_panel)

        hint = QLabel("点击“编辑”修改模式名称或颜色，历史记录会继续保留。")
        hint.setProperty("class", "mutedLabel")
        layout.addWidget(hint)

        self.modes_table = ModeTableView()
        self.modes_table.setMinimumHeight(240)
        self.modes_table.mode_delegate.editRequested.connect(self._edit_mode_row)
        self.modes_table.mode_delegate.deleteRequested.connect(self._delete_mode_row)
        self.modes_table.mode_delegate.colorRequested.connect(self._edit_mode_row)
        layout.addWidget(self.modes_table)
        layout.addStretch()

        self._refresh_modes_table()
        return widget

    def _pick_color(self):
        color = QColorDialog.getColor(QColor(self._new_color), self, "选择颜色")
        if color.isValid():
            self._new_color = color.name()
            self.color_btn.setStyleSheet(color_swatch_style(self._new_color))

    def _pick_edit_color(self):
        color = QColorDialog.getColor(QColor(self._editing_color), self, "选择颜色")
        if color.isValid():
            self._editing_color = color.name()
            self.edit_color_btn.setStyleSheet(color_swatch_style(self._editing_color))

    def _add_mode(self):
        name = self.new_mode_input.text().strip()
        if not name:
            return

        try:
            add_mode(name, self._new_color)
            self.new_mode_input.clear()
            self._refresh_modes_table()
            self.modes_changed.emit()
        except Exception as exc:
            QMessageBox.warning(self, "错误", f"添加失败: {exc}")

    def _delete_mode(self, mode_id: int):
        reply = QMessageBox.question(self, "确认", "确定删除该模式？相关记录不会被删除。")
        if reply != QMessageBox.Yes:
            return

        delete_mode(mode_id)
        if self._editing_mode_id == mode_id:
            self._cancel_mode_edit()
        self._refresh_modes_table()
        self.modes_changed.emit()

    def _edit_mode_row(self, row: int):
        mode = self.modes_table.mode_model.mode_at(row)
        if mode is not None:
            self._start_mode_edit(mode["id"])

    def _delete_mode_row(self, row: int):
        mode = self.modes_table.mode_model.mode_at(row)
        if mode is not None:
            self._delete_mode(mode["id"])

    def _start_mode_edit(self, mode_id: int):
        mode = next((item for item in get_modes() if item["id"] == mode_id), None)
        if mode is None:
            return

        self._editing_mode_id = mode_id
        self._editing_mode_name = mode["name"]
        self._editing_color = mode["color"]
        self.edit_mode_input.setText(mode["name"])
        self.edit_color_btn.setStyleSheet(color_swatch_style(mode["color"]))
        self._edit_mode_panel.setVisible(True)
        self.edit_mode_input.setFocus()
        self.edit_mode_input.selectAll()

    def _cancel_mode_edit(self):
        self._editing_mode_id = None
        self._editing_mode_name = ""
        self._edit_mode_panel.setVisible(False)
        self.edit_mode_input.clear()

    def _save_mode_edit(self):
        if self._editing_mode_id is None:
            return

        name = self.edit_mode_input.text().strip()
        color = self._editing_color
        if not name:
            QMessageBox.warning(self, "提示", "模式名称不能为空。")
            self.edit_mode_input.setFocus()
            return

        for other in get_modes():
            if other["id"] != self._editing_mode_id and other["name"].strip().casefold() == name.casefold():
                QMessageBox.warning(self, "提示", "模式名称不能重复。")
                self.edit_mode_input.setFocus()
                return

        try:
            update_mode(self._editing_mode_id, name, color)
            if name != self._editing_mode_name:
                self._hotkey_manager.rename_mode_hotkey(self._editing_mode_name, name)
            self._cancel_mode_edit()
            self._refresh_modes_table()
            self.modes_changed.emit()
        except Exception as exc:
            QMessageBox.warning(self, "错误", f"保存失败: {exc}")

    def _refresh_modes_table(self):
        self.modes_table.mode_model.set_modes(get_modes())

    def _build_hotkeys_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        self._section_intro(layout, "不用切回窗口，也能掌控时间", "全局快捷键在其他应用中同样有效。点击按键区域，直接录入新的组合键。")

        hint = QLabel("点击按钮后直接按下快捷键组合即可录入。\n按 Esc 取消录入。")
        hint.setProperty("class", "mutedLabel")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        fixed_actions = [
            ("pause_resume", "暂停/继续"),
            ("stop", "结束计时"),
        ]
        for action, label in fixed_actions:
            current = self._hotkey_manager.get_hotkey(action)
            layout.addWidget(
                self._build_hotkey_row(
                    action,
                    label,
                    self._pynput_to_display(current),
                )
            )

        layout.addSpacing(8)
        layout.addWidget(QLabel("模式快捷键:"))

        self._mode_hotkeys_container = QWidget()
        self._mode_hotkeys_layout = QVBoxLayout(self._mode_hotkeys_container)
        self._mode_hotkeys_layout.setContentsMargins(0, 0, 0, 0)
        self._mode_hotkeys_layout.setSpacing(8)
        layout.addWidget(self._mode_hotkeys_container)

        save_btn = QPushButton("保存快捷键")
        save_btn.setObjectName("primaryButton")
        save_btn.clicked.connect(self._save_hotkeys)
        layout.addWidget(save_btn, alignment=Qt.AlignLeft)

        layout.addStretch()
        self.refresh_mode_hotkeys()
        return widget

    def _build_hotkey_row(self, action: str, label_text: str, current_text: str) -> QWidget:
        row_widget = QWidget()
        row = QHBoxLayout(row_widget)
        row.setContentsMargins(0, 0, 0, 0)

        label = ElidedLabel(label_text)
        row.addWidget(label, 1)

        recorder = HotkeyRecorder(current_text)
        self.hotkey_recorders[action] = recorder
        row.addWidget(recorder)

        clear_btn = QPushButton("清除")
        clear_btn.setObjectName("ghostButton")
        clear_btn.setMinimumWidth(50)
        clear_btn.clicked.connect(lambda _, a=action: self._clear_hotkey(a))
        row.addWidget(clear_btn)

        return row_widget

    def refresh_mode_hotkeys(self):
        self._hotkey_manager.sync_mode_hotkeys()

        if not hasattr(self, "_mode_hotkeys_layout"):
            return

        for widget in self._mode_hotkey_row_widgets:
            widget.deleteLater()
        self._mode_hotkey_row_widgets.clear()

        for action in list(self.hotkey_recorders):
            if action.startswith(MODE_ACTION_PREFIX):
                del self.hotkey_recorders[action]

        for mode in get_modes():
            action = mode_action_name(mode["name"])
            current = self._hotkey_manager.get_hotkey(action)
            row_widget = self._build_hotkey_row(
                action,
                f"切换到「{mode['name']}」",
                self._pynput_to_display(current),
            )
            self._mode_hotkeys_layout.addWidget(row_widget)
            self._mode_hotkey_row_widgets.append(row_widget)

    def _clear_hotkey(self, action: str):
        if action in self.hotkey_recorders:
            self.hotkey_recorders[action].set_hotkey_display("")

    def _save_hotkeys(self):
        combo_map = {}
        conflicts = []

        for action, recorder in self.hotkey_recorders.items():
            combo = recorder.get_hotkey_display().strip()
            if not combo:
                continue

            combo_lower = combo.lower()
            if combo_lower in combo_map:
                other = combo_map[combo_lower]
                conflicts.append((combo, self._action_label(other), self._action_label(action)))
            else:
                combo_map[combo_lower] = action

        if conflicts:
            msg = "检测到快捷键冲突:\n\n"
            for combo, action_1, action_2 in conflicts:
                msg += f"  {combo}  同时绑定了「{action_1}」和「{action_2}」\n"
            msg += "\n请修改后再保存。"
            QMessageBox.warning(self, "快捷键冲突", msg)
            return

        self._hotkey_manager.sync_mode_hotkeys()
        for action, recorder in self.hotkey_recorders.items():
            text = recorder.get_hotkey_display().strip()
            self._hotkey_manager.set_hotkey(action, self._display_to_pynput(text))

        self.hotkeys_changed.emit()
        QMessageBox.information(self, "成功", "快捷键已保存")

    def _action_label(self, action: str) -> str:
        labels = {
            "pause_resume": "暂停/继续",
            "stop": "结束计时",
        }
        if action in labels:
            return labels[action]
        if action.startswith(MODE_ACTION_PREFIX):
            return f"切换到「{action[len(MODE_ACTION_PREFIX):]}」"
        return action

    def _pynput_to_display(self, value: str) -> str:
        if not value:
            return ""

        return (
            value.replace("<ctrl>", "Ctrl")
            .replace("<alt>", "Alt")
            .replace("<shift>", "Shift")
            .replace("<meta>", "Win")
            .replace("<", "")
            .replace(">", "")
        )

    def _display_to_pynput(self, value: str) -> str:
        if not value:
            return ""

        result = []
        for part in [piece.strip().lower() for piece in value.split("+")]:
            if part in ("ctrl", "control"):
                result.append("<ctrl>")
            elif part == "alt":
                result.append("<alt>")
            elif part == "shift":
                result.append("<shift>")
            elif part in ("win", "meta"):
                result.append("<meta>")
            else:
                result.append(part)
        return "+".join(result)

    def _build_floating_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(14)
        self._section_intro(layout, "保持专注，减少读秒", "关闭主窗口后，悬浮组件会继续呈现当前模式和计时状态。双击即可回到主窗口。")

        hint = QLabel("关闭主窗口后会进入悬浮小组件。这里的设置会立即应用，无需重启。")
        hint.setProperty("class", "mutedLabel")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        mask_card = QFrame()
        mask_card.setObjectName("settingsCard")
        card_layout = QHBoxLayout(mask_card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(16)

        copy_layout = QVBoxLayout()
        copy_layout.setContentsMargins(0, 0, 0, 0)
        copy_layout.setSpacing(6)

        title = QLabel("时间玻璃遮罩")
        title.setProperty("class", "sectionTitle")
        copy_layout.addWidget(title)

        description = QLabel("开启后，悬浮窗会用高不透明磨砂层遮住时间数字，降低读数冲动，同时保留模式和运行状态。")
        description.setProperty("class", "mutedLabel")
        description.setWordWrap(True)
        copy_layout.addWidget(description)

        card_layout.addLayout(copy_layout, stretch=1)

        enabled = floating_time_mask_enabled()
        self.floating_time_mask_toggle = QPushButton()
        self.floating_time_mask_toggle.setObjectName("toggleButton")
        self.floating_time_mask_toggle.setCheckable(True)
        self.floating_time_mask_toggle.setFixedWidth(92)
        self.floating_time_mask_toggle.setChecked(enabled)
        self._set_floating_time_mask_toggle_text(enabled)
        self.floating_time_mask_toggle.toggled.connect(self._on_floating_time_mask_toggled)
        card_layout.addWidget(self.floating_time_mask_toggle, alignment=Qt.AlignTop)

        layout.addWidget(mask_card)
        layout.addStretch()
        return widget

    def _build_reminder_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(14)
        self._section_intro(layout, "认真投入，也记得休息", "按你的节奏设置提醒。提醒出现时，计时会继续，直到你主动暂停或结束。")

        intro = QLabel(
            "把提醒当作轻轻敲肩，而不是强制中断。计时只计算有效工作时间，"
            "暂停本身不会把提醒倒计时往前推进。"
        )
        intro.setProperty("class", "mutedLabel")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        card = QFrame()
        card.setObjectName("settingsCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(14)

        header = QHBoxLayout()
        title = QLabel("工作节奏提醒")
        title.setProperty("class", "sectionTitle")
        header.addWidget(title)
        header.addStretch()

        self.reminder_enabled_toggle = QPushButton()
        self.reminder_enabled_toggle.setObjectName("toggleButton")
        self.reminder_enabled_toggle.setCheckable(True)
        self.reminder_enabled_toggle.setFixedWidth(92)
        self.reminder_enabled_toggle.setChecked(break_reminder_enabled())
        self._set_reminder_toggle_text(self.reminder_enabled_toggle.isChecked())
        self.reminder_enabled_toggle.toggled.connect(self._set_reminder_toggle_text)
        header.addWidget(self.reminder_enabled_toggle)
        card_layout.addLayout(header)

        desc = QLabel("到达设定时长后，在屏幕正中央弹出一张提醒卡。")
        desc.setProperty("class", "mutedLabel")
        desc.setWordWrap(True)
        card_layout.addWidget(desc)

        interval_row = QHBoxLayout()
        interval_label = QLabel("提醒间隔")
        interval_label.setMinimumWidth(130)
        interval_row.addWidget(interval_label)
        self.reminder_interval_spin = QSpinBox()
        self.reminder_interval_spin.setRange(5, 240)
        self.reminder_interval_spin.setSuffix(" 分钟")
        self.reminder_interval_spin.setValue(break_reminder_interval_minutes())
        self.reminder_interval_spin.setFixedWidth(150)
        interval_row.addWidget(self.reminder_interval_spin)
        interval_row.addStretch()
        card_layout.addLayout(interval_row)

        grace_row = QHBoxLayout()
        grace_label = QLabel("暂停宽限期")
        grace_label.setMinimumWidth(130)
        grace_row.addWidget(grace_label)
        self.reminder_grace_spin = QSpinBox()
        self.reminder_grace_spin.setRange(0, 60)
        self.reminder_grace_spin.setSuffix(" 分钟")
        self.reminder_grace_spin.setValue(break_reminder_grace_minutes())
        self.reminder_grace_spin.setFixedWidth(150)
        grace_row.addWidget(self.reminder_grace_spin)
        grace_row.addStretch()
        card_layout.addLayout(grace_row)

        grace_hint = QLabel("暂停不超过这个时长，继续后仍算同一轮工作；超过则下一次提醒从头计算。")
        grace_hint.setProperty("class", "mutedLabel")
        grace_hint.setWordWrap(True)
        card_layout.addWidget(grace_hint)

        message_label = QLabel("休息文案")
        message_label.setProperty("class", "sectionTitle")
        card_layout.addWidget(message_label)

        self.reminder_message_edit = QTextEdit()
        self.reminder_message_edit.setPlainText(break_reminder_message())
        self.reminder_message_edit.setPlaceholderText(BREAK_REMINDER_MESSAGE_DEFAULT)
        self.reminder_message_edit.setFixedHeight(76)
        card_layout.addWidget(self.reminder_message_edit)

        message_hint = QLabel("支持自定义文字，提醒关闭前会一直保留在屏幕中央。")
        message_hint.setProperty("class", "mutedLabel")
        message_hint.setWordWrap(True)
        card_layout.addWidget(message_hint)

        self.reminder_save_status = QLabel("")
        self.reminder_save_status.setObjectName("settingsSaveStatus")
        self.reminder_save_status.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self.reminder_save_status)

        save_btn = QPushButton("保存提醒设置")
        save_btn.setObjectName("primaryButton")
        save_btn.clicked.connect(self._save_reminder_settings)
        card_layout.addWidget(save_btn, alignment=Qt.AlignRight)

        layout.addWidget(card)
        layout.addStretch()
        return widget

    def _set_reminder_toggle_text(self, enabled: bool):
        self.reminder_enabled_toggle.setText("已开启" if enabled else "已关闭")

    def _save_reminder_settings(self):
        enabled = self.reminder_enabled_toggle.isChecked()
        message = self.reminder_message_edit.toPlainText().strip()
        if not message:
            set_feedback(self.reminder_save_status, "休息文案不能为空")
            return
        if len(message) > 200:
            set_feedback(self.reminder_save_status, "休息文案不能超过 200 个字符")
            return
        set_setting(BREAK_REMINDER_ENABLED_KEY, "1" if enabled else "0")
        set_setting(BREAK_REMINDER_INTERVAL_KEY, str(self.reminder_interval_spin.value()))
        set_setting(BREAK_REMINDER_GRACE_KEY, str(self.reminder_grace_spin.value()))
        set_setting(BREAK_REMINDER_MESSAGE_KEY, message)
        set_feedback(self.reminder_save_status, "已保存，下一轮计时立即生效", success=True)
        self.reminder_settings_changed.emit()

    def _set_floating_time_mask_toggle_text(self, enabled: bool):
        self.floating_time_mask_toggle.setText("已开启" if enabled else "已关闭")

    def _on_floating_time_mask_toggled(self, enabled: bool):
        set_setting(FLOATING_TIME_MASK_KEY, "1" if enabled else "0")
        self._set_floating_time_mask_toggle_text(enabled)
        self.floating_settings_changed.emit(enabled)

    def _build_password_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)
        self._section_intro(layout, "账户安全", "修改当前本地账户的密码。已有计时记录和偏好设置会继续保留。")
        panel = QFrame()
        panel.setObjectName("passwordPanel")
        panel.setMaximumWidth(400)
        form = QVBoxLayout(panel)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(10)

        def add_field(label, field):
            caption = QLabel(label)
            caption.setProperty("class", "fieldLabel")
            caption.setBuddy(field)
            field.setAccessibleName(label)
            form.addWidget(caption)
            form.addWidget(field)
            form.addSpacing(6)

        self.old_pw = QLineEdit()
        self.old_pw.setPlaceholderText("当前密码")
        self.old_pw.setEchoMode(QLineEdit.Password)
        add_field("当前密码", self.old_pw)

        self.new_pw = QLineEdit()
        self.new_pw.setPlaceholderText("新密码")
        self.new_pw.setEchoMode(QLineEdit.Password)
        add_field("新密码", self.new_pw)

        self.new_pw2 = QLineEdit()
        self.new_pw2.setPlaceholderText("确认新密码")
        self.new_pw2.setEchoMode(QLineEdit.Password)
        add_field("确认新密码", self.new_pw2)
        self.new_pw2.returnPressed.connect(self._change_password)

        self.pw_msg = QLabel("")
        self.pw_msg.setObjectName("msgLabel")
        self.pw_msg.setAlignment(Qt.AlignCenter)
        form.addWidget(self.pw_msg)

        btn = QPushButton("修改密码")
        btn.setObjectName("primaryButton")
        btn.clicked.connect(self._change_password)
        form.addWidget(btn, alignment=Qt.AlignLeft)
        layout.addWidget(panel)

        layout.addStretch()
        return widget

    def _change_password(self):
        set_feedback(self.pw_msg, "")
        old = self.old_pw.text().strip()
        new = self.new_pw.text().strip()
        new2 = self.new_pw2.text().strip()

        if not old or not new:
            self.pw_msg.setText("请填写所有字段")
            return
        if new != new2:
            self.pw_msg.setText("两次密码不一致")
            return
        if not verify_user(self._username, old):
            self.pw_msg.setText("当前密码错误")
            return

        change_password(self._username, new)
        set_feedback(self.pw_msg, "密码修改成功", success=True)
        self.old_pw.clear()
        self.new_pw.clear()
        self.new_pw2.clear()
