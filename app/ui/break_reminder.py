"""居中的休息提醒：静态、半透明、需要用户手动确认。"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
)

from app.database import BREAK_REMINDER_MESSAGE_DEFAULT
from app.ui.components import ElidedLabel
from app.ui.materials import FrostedSurface


class BreakReminderToast(QWidget):
    """一个稳定的中心提醒，不自动关闭，也不改变计时状态。"""

    closed = Signal()

    def __init__(self):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setObjectName("breakReminderWindow")
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowTitle("Tomato Timer — 休息提醒")
        self.setFixedWidth(480)
        self.setMinimumHeight(250)
        self.resize(480, 250)

        self._closing = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        card = FrostedSurface()
        card.setObjectName("breakReminderCard")
        outer.addWidget(card)

        root = QVBoxLayout(card)
        root.setContentsMargins(22, 20, 22, 18)
        root.setSpacing(14)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(7)

        status_dot = QLabel("●")
        status_dot.setObjectName("reminderStatusDot")
        header.addWidget(status_dot)

        eyebrow = QLabel("休息提醒")
        eyebrow.setObjectName("reminderEyebrow")
        header.addWidget(eyebrow)

        header.addStretch(1)

        self._mode_chip = ElidedLabel("")
        self._mode_chip.setObjectName("reminderModeChip")
        self._mode_chip.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self._mode_chip.setMinimumWidth(60)
        self._mode_chip.setMaximumWidth(180)
        self._mode_chip.setAlignment(Qt.AlignCenter)
        header.addWidget(self._mode_chip)
        root.addLayout(header)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(16)

        time_block = QFrame()
        time_block.setObjectName("reminderTimeBlock")
        time_block.setFixedSize(88, 88)
        time_layout = QVBoxLayout(time_block)
        time_layout.setContentsMargins(7, 10, 7, 8)
        time_layout.setSpacing(0)

        self._minutes = QLabel("45")
        self._minutes.setObjectName("reminderMinutes")
        self._minutes.setAlignment(Qt.AlignCenter)
        time_layout.addWidget(self._minutes)

        unit = QLabel("分钟")
        unit.setObjectName("reminderUnit")
        unit.setAlignment(Qt.AlignCenter)
        time_layout.addWidget(unit)
        body.addWidget(time_block, alignment=Qt.AlignTop)

        content = QVBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(6)

        self._title = QLabel("该休息一下了")
        self._title.setObjectName("reminderTitle")
        content.addWidget(self._title)

        self._message = QLabel(BREAK_REMINDER_MESSAGE_DEFAULT)
        self._message.setObjectName("reminderMessage")
        self._message.setWordWrap(True)
        content.addWidget(self._message)
        content.addStretch(1)
        body.addLayout(content, stretch=1)
        root.addLayout(body)

        rule = QFrame()
        rule.setObjectName("reminderRule")
        rule.setFixedHeight(1)
        root.addWidget(rule)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(12)
        self._meta = QLabel("")
        self._meta.setObjectName("reminderMeta")
        self._meta.setWordWrap(True)
        footer.addWidget(self._meta, stretch=1)

        acknowledge_btn = QPushButton("知道了")
        acknowledge_btn.setObjectName("reminderAcknowledgeButton")
        acknowledge_btn.setFixedSize(92, 34)
        acknowledge_btn.setCursor(QCursor(Qt.PointingHandCursor))
        acknowledge_btn.clicked.connect(self._request_close)
        footer.addWidget(acknowledge_btn)
        root.addLayout(footer)

    def show_reminder(self, mode_name: str, interval_minutes: int, message: str = ""):
        """更新提醒内容并立即显示在当前屏幕中央。"""
        self._closing = False
        self._title.setText("该休息一下了")
        self._minutes.setText(str(interval_minutes))
        self._mode_chip.setText(mode_name.strip() or "工作")
        self._mode_chip.setToolTip(mode_name.strip() or "工作")
        self._message.setText(message.strip() or BREAK_REMINDER_MESSAGE_DEFAULT)
        self._meta.setText(f"连续投入 {interval_minutes} 分钟 · 现在起来活动一下")

        self.adjustSize()

        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            geometry = self.geometry()
            geometry.moveCenter(area.center())
            self.setGeometry(geometry)

        self.show()
        self.raise_()

    def _request_close(self):
        """只关闭提醒本身，不暂停、继续或结束计时。"""
        if self._closing:
            return
        self._closing = True
        self.closed.emit()
        self.hide()

    def closeEvent(self, event):
        if not self._closing:
            self.closed.emit()
            self._closing = True
        event.accept()
