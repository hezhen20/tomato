"""模式列表的 Qt Model/View 实现。

模式设置页不应该把大量 QWidget 嵌入 QTableWidget 单元格：当窗口变窄或样式
包含 padding/min-height 时，cell widget 的 sizeHint 很容易超过单元格几何范围，
最终出现输入框、颜色块和操作按钮被裁剪的问题。

这里使用 Qt 原生的 Model/View 方案：数据由 ``ModeTableModel`` 管理，颜色和操作
按钮由 ``ModeTableDelegate`` 绘制并处理点击。这样表格只管理几何和滚动，行内
不会再有失控的子控件布局。
"""

from __future__ import annotations

from typing import Iterable

from PySide6.QtCore import QAbstractTableModel, QEvent, QModelIndex, Qt, Signal, QRect, QSize
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QStyledItemDelegate,
    QTableView,
)
from app.ui.theme import current_theme, theme_colors


class ModeTableModel(QAbstractTableModel):
    """只读模式展示模型。

    编辑由页面上的独立编辑面板完成，模型只暴露当前模式的稳定 id、名称和颜色。
    ``id`` 不参与显示，但保留在每一行，避免重命名时误把历史记录当成新模式。
    """

    HEADERS = ("名称", "颜色", "操作")

    def __init__(self, modes: Iterable[dict] | None = None, parent=None):
        super().__init__(parent)
        self._modes = list(modes or [])

    @property
    def modes(self) -> list[dict]:
        return list(self._modes)

    def set_modes(self, modes: Iterable[dict]) -> None:
        self.beginResetModel()
        self._modes = list(modes)
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._modes)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):
        if role == Qt.TextAlignmentRole and orientation == Qt.Horizontal:
            return int(Qt.AlignLeft | Qt.AlignVCenter)
        if role != Qt.DisplayRole or orientation != Qt.Horizontal:
            return None
        if 0 <= section < len(self.HEADERS):
            return self.HEADERS[section]
        return None

    def headerAlignment(self, section: int):
        return Qt.AlignLeft | Qt.AlignVCenter

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._modes)):
            return None

        mode = self._modes[index.row()]
        column = index.column()
        if role in (Qt.DisplayRole, Qt.EditRole):
            if column == 0:
                return str(mode.get("name", ""))
            if column == 1:
                return str(mode.get("color", "#A8B3C7"))
            return ""
        if role == Qt.ToolTipRole and column == 1:
            return str(mode.get("color", "#A8B3C7"))
        if role == Qt.UserRole:
            return mode.get("id")
        return None

    def flags(self, index: QModelIndex):
        if not index.isValid():
            return Qt.NoItemFlags
        # 名称由独立编辑面板处理，避免直接在表格内创建 QLineEdit。
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def mode_at(self, row: int) -> dict | None:
        if 0 <= row < len(self._modes):
            return dict(self._modes[row])
        return None


class ModeTableDelegate(QStyledItemDelegate):
    """绘制颜色 swatch 和编辑/删除动作，不创建嵌入式按钮。"""

    editRequested = Signal(int)
    deleteRequested = Signal(int)
    colorRequested = Signal(int)

    ACTION_EDIT = "编辑"
    ACTION_DELETE = "删除"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._action_rects: dict[tuple[int, int], tuple[QRect, QRect]] = {}

    def sizeHint(self, option, index) -> QSize:
        base = super().sizeHint(option, index)
        return QSize(base.width(), max(38, base.height(), 38))

    def paint(self, painter: QPainter, option, index):
        if index.column() == 1:
            self._paint_color(painter, option, index)
            return
        if index.column() == 2:
            self._paint_actions(painter, option, index)
            return
        super().paint(painter, option, index)

    def _paint_color(self, painter: QPainter, option, index):
        color = QColor(index.data(Qt.DisplayRole) or "#A8B3C7")
        if not color.isValid():
            color = QColor("#A8B3C7")
        diameter = 13
        center_y = option.rect.center().y()
        rect = QRect(option.rect.left() + 12, center_y - diameter // 2, diameter, diameter)
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(theme_colors()["border_strong"]), 1))
        painter.setBrush(color)
        painter.drawEllipse(rect)
        painter.restore()

    def _paint_actions(self, painter, option, index):
        rect = option.rect.adjusted(6, 6, -6, -6)
        # Reserve fixed, non-overlapping hit boxes. The delegate paints the text
        # directly, so QSS padding/min-height cannot enlarge a child widget.
        gap = 6
        button_width = max(42, (rect.width() - gap) // 2)
        edit_rect = QRect(rect.left(), rect.top(), button_width, rect.height())
        delete_rect = QRect(edit_rect.right() + gap, rect.top(), button_width, rect.height())
        self._action_rects[(index.row(), index.column())] = (edit_rect, delete_rect)

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        colors = current_theme().colors
        self._draw_button(painter, edit_rect, self.ACTION_EDIT, colors["accent_text"])
        self._draw_button(painter, delete_rect, self.ACTION_DELETE, colors["danger"])
        painter.restore()

    @staticmethod
    def _draw_button(painter, rect, text, foreground):
        font = painter.font()
        font.setPixelSize(11)
        painter.setFont(font)
        painter.setPen(QColor(foreground))
        painter.drawText(rect, Qt.AlignCenter, text)

    def editorEvent(self, event, model, option, index):
        if index.column() == 1 and event.type() == QEvent.MouseButtonRelease:
            self.colorRequested.emit(index.row())
            return True

        if index.column() != 2:
            return super().editorEvent(event, model, option, index)

        if event.type() not in (QEvent.MouseButtonRelease, QEvent.MouseButtonPress):
            return False
        rect = option.rect.adjusted(6, 6, -6, -6)
        gap = 6
        button_width = max(42, (rect.width() - gap) // 2)
        edit_rect = QRect(rect.left(), rect.top(), button_width, rect.height())
        delete_rect = QRect(edit_rect.right() + gap, rect.top(), button_width, rect.height())
        pos = event.position().toPoint()
        if event.type() == QEvent.MouseButtonRelease:
            if edit_rect.contains(pos):
                self.editRequested.emit(index.row())
                return True
            if delete_rect.contains(pos):
                self.deleteRequested.emit(index.row())
                return True
        return True


class ModeTableView(QTableView):
    """为模式管理页提供稳定默认尺寸和滚动策略的表格视图。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setModel(ModeTableModel(parent=self))
        self.setItemDelegate(ModeTableDelegate(self))
        self.setSelectionMode(QAbstractItemView.NoSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setShowGrid(False)
        self.setWordWrap(False)
        self.setAlternatingRowColors(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(38)
        self.horizontalHeader().setStretchLastSection(False)
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.setColumnWidth(1, 60)
        self.setColumnWidth(2, 116)
        self.setMinimumHeight(80)

    @property
    def mode_model(self) -> ModeTableModel:
        return self.model()

    @property
    def mode_delegate(self) -> ModeTableDelegate:
        return self.itemDelegate()
