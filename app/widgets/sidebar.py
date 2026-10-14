"""左侧导航（可收起）。

按钮做得更大、之间有明确分界线，点击更省事：
每个条目是一整行（高约 46px），行间有 1px 分隔线，选中行左侧有一条强调色竖条，
右侧显示对应的快捷键。
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from .. import theme

NAV_ITEMS: tuple[tuple[str, str, str], ...] = (
    ("overview", "总览", "Ctrl+1"),
    ("heatmaps", "热力图", "Ctrl+2"),
    ("mindmap", "记录地图", "Ctrl+3"),
    ("activity", "活动记录", "Ctrl+4"),
    ("processes", "进程树", "Ctrl+5"),
    ("diary", "日记", "Ctrl+6"),
)

# 固定在左栏最下方的条目
BOTTOM_ITEMS: tuple[tuple[str, str, str], ...] = (("data", "数据", "Ctrl+7"),)

ALL_NAV_ITEMS: tuple[tuple[str, str, str], ...] = NAV_ITEMS + BOTTOM_ITEMS


def _separator() -> QFrame:
    line = QFrame()
    line.setObjectName("NavSeparator")
    line.setFixedHeight(1)
    return line


class NavButton(QPushButton):
    """一行导航：左边名称，右边快捷键。"""

    def __init__(self, label: str, shortcut: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("NavButton")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(46)

        row = QHBoxLayout(self)
        row.setContentsMargins(16, 10, 14, 10)
        row.setSpacing(8)
        self.label = QLabel(label)
        self.label.setObjectName("NavLabel")
        row.addStretch(1)
        row.addWidget(self.label)
        row.addStretch(1)
        # 快捷键不再显示在界面上（功能保留，注册在 main_window 里）
        self.shortcut_text = shortcut
        # 选中状态的文字颜色在代码里切换：
        # Qt 的样式表对「后代选择器 + 伪状态」（如 #NavButton:checked #NavLabel）支持不可靠，
        # 写成那样会让所有条目都套用选中样式。
        self.toggled.connect(self._sync_label_style)
        self._sync_label_style(False)

    def _sync_label_style(self, checked: bool) -> None:
        color = theme.ACCENT if checked else theme.TEXT
        weight = 600 if checked else 500
        self.label.setStyleSheet(
            f"color: {color}; font-size: 14px; font-weight: {weight}; background: transparent;"
        )


class Sidebar(QWidget):
    """极简导航：支持整体收起，收起后由顶栏的切换按钮重新展开。"""

    pageSelected = Signal(str)

    WIDTH = 248

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(self.WIDTH)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 18, 16, 16)
        layout.setSpacing(6)

        title = QLabel("Life Manager")
        title.setObjectName("SidebarTitle")
        subtitle = QLabel(f"v{__version__} · 本地单机")
        subtitle.setObjectName("SidebarSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(16)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self.buttons: dict[str, QPushButton] = {}
        layout.addWidget(self._build_group(NAV_ITEMS))

        layout.addStretch(1)
        # 「数据」固定在左栏最下面
        layout.addWidget(self._build_group(BOTTOM_ITEMS))

        self.set_current("overview")

    def _build_group(self, items: tuple[tuple[str, str, str], ...]) -> QFrame:
        group = QFrame()
        group.setObjectName("NavGroup")
        group_layout = QVBoxLayout(group)
        group_layout.setContentsMargins(0, 0, 0, 0)
        group_layout.setSpacing(0)
        for index, (key, label, shortcut) in enumerate(items):
            if index:
                group_layout.addWidget(_separator())
            button = NavButton(label, shortcut)
            button.clicked.connect(
                lambda _checked=False, page_key=key: self.pageSelected.emit(page_key)
            )
            group_layout.addWidget(button)
            self._group.addButton(button)
            self.buttons[key] = button
        return group

    def set_current(self, key: str) -> None:
        button = self.buttons.get(key)
        if button is not None and not button.isChecked():
            button.setChecked(True)
