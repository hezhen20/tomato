"""全局快捷键管理模块"""

import json

from pynput import keyboard
from PySide6.QtCore import QObject, Signal

from app.database import get_modes, get_setting, set_setting

DEFAULT_HOTKEYS = {
    "pause_resume": "<ctrl>+<alt>+p",
    "stop": "<ctrl>+<alt>+q",
}

MODE_ACTION_PREFIX = "mode_"


def mode_action_name(mode_name: str) -> str:
    return f"{MODE_ACTION_PREFIX}{mode_name}"


class HotkeyManager(QObject):
    hotkey_triggered = Signal(str)

    def __init__(self):
        super().__init__()
        self._listener = None
        self._hotkeys = {}
        self.load_hotkeys()
        self.sync_mode_hotkeys()

    def load_hotkeys(self):
        raw = get_setting("hotkeys", "")
        if raw:
            try:
                self._hotkeys = json.loads(raw)
            except json.JSONDecodeError:
                self._hotkeys = dict(DEFAULT_HOTKEYS)
        else:
            self._hotkeys = dict(DEFAULT_HOTKEYS)

    def save_hotkeys(self):
        set_setting("hotkeys", json.dumps(self._hotkeys, ensure_ascii=False))

    def get_hotkey(self, action: str) -> str:
        return self._hotkeys.get(action, "")

    def set_hotkey(self, action: str, hotkey_str: str):
        self._hotkeys[action] = hotkey_str
        self.save_hotkeys()

    def get_all_hotkeys(self) -> dict:
        return dict(self._hotkeys)

    def set_mode_hotkey(self, mode_name: str, hotkey_str: str):
        self.set_hotkey(mode_action_name(mode_name), hotkey_str)

    def remove_mode_hotkey(self, mode_name: str):
        key = mode_action_name(mode_name)
        if key in self._hotkeys:
            del self._hotkeys[key]
            self.save_hotkeys()

    def sync_mode_hotkeys(self, save: bool = True) -> bool:
        current_mode_actions = {mode_action_name(mode["name"]) for mode in get_modes()}
        existing_mode_actions = {
            action for action in self._hotkeys if action.startswith(MODE_ACTION_PREFIX)
        }

        changed = False

        for action in current_mode_actions - existing_mode_actions:
            self._hotkeys[action] = ""
            changed = True

        for action in existing_mode_actions - current_mode_actions:
            del self._hotkeys[action]
            changed = True

        if changed and save:
            self.save_hotkeys()

        return changed

    def start(self):
        self.stop()
        self.load_hotkeys()
        self.sync_mode_hotkeys()

        hotkey_map = {}
        for action, combo in self._hotkeys.items():
            if combo:
                hotkey_map[combo] = self._make_callback(action)

        if not hotkey_map:
            return

        try:
            self._listener = keyboard.GlobalHotKeys(hotkey_map)
            self._listener.start()
        except Exception as exc:
            print(f"快捷键注册失败: {exc}")

    def stop(self):
        if self._listener:
            self._listener.stop()
            self._listener = None

    def restart(self):
        self.start()

    def _make_callback(self, action: str):
        def callback():
            self.hotkey_triggered.emit(action)

        return callback
