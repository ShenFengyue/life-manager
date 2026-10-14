"""视觉主题：极简、克制的中性色 + GitHub 风格绿色热力图。

参考 GitHub 的贡献热力图与 Linear 的信息层级。
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QPalette

# ------------------------------------------------------------------ 配色
BG = "#ffffff"
SURFACE = "#f6f8fa"
SURFACE_ALT = "#eef1f4"
BORDER = "#d0d7de"
BORDER_MUTED = "#e4e8ec"
TEXT = "#1f2328"
TEXT_MUTED = "#656d76"
TEXT_SUBTLE = "#8b949e"
ACCENT = "#0969da"
ACCENT_SOFT = "#ddf4ff"
ACCENT_HOVER = "#0860ca"
DANGER = "#cf222e"
PAGE_BG = "#ffffff"

# 热力图配色（与 app.heatmap.LEVEL_COLORS 保持一致）
LEVEL_COLORS: tuple[str, ...] = ("#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39")

# 思维导图里区分领域的强调色（低饱和，按领域顺序循环使用）
MAP_PALETTE: tuple[str, ...] = (
    "#0969da",
    "#8250df",
    "#bf8700",
    "#1a7f37",
    "#0e7490",
    "#cf222e",
)


def map_color(index: int) -> str:
    return MAP_PALETTE[index % len(MAP_PALETTE)]

STATUS_STYLE: dict[str, tuple[str, str]] = {
    "待开始": (TEXT_MUTED, "#f6f8fa"),
    "进行中": (ACCENT, ACCENT_SOFT),
    "已暂停": ("#9a6700", "#fff8c5"),
    "已完成": ("#1a7f37", "#dafbe1"),
    "已归档": (TEXT_MUTED, "#eaeef2"),
}

FONT_FAMILIES = "Microsoft YaHei UI, Microsoft YaHei, Segoe UI, PingFang SC, sans-serif"


def app_font() -> QFont:
    font = QFont("Microsoft YaHei UI")
    font.setPointSize(10)
    font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    return font


def light_palette() -> QPalette:
    """固定使用浅色调色板。

    桌面 UI 采用克制的中性色，因此不跟随 Windows 深色模式，
    否则未被样式表覆盖的容器会被系统调色板渲染成深色块。
    """
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(BG))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Base, QColor(BG))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(SURFACE))
    palette.setColor(QPalette.ColorRole.Text, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Button, QColor(SURFACE))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#24292f"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(TEXT_SUBTLE))
    palette.setColor(QPalette.ColorRole.Link, QColor(ACCENT))
    palette.setColor(QPalette.ColorRole.Light, QColor(BORDER_MUTED))
    palette.setColor(QPalette.ColorRole.Midlight, QColor(BORDER_MUTED))
    palette.setColor(QPalette.ColorRole.Mid, QColor(BORDER))
    palette.setColor(QPalette.ColorRole.Dark, QColor("#afb8c1"))
    palette.setColor(QPalette.ColorRole.Shadow, QColor("#d0d7de"))
    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(TEXT_SUBTLE))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Base, QColor(SURFACE))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Button, QColor(SURFACE))
    return palette


def stylesheet() -> str:
    return f"""
    QWidget {{
        font-family: {FONT_FAMILIES};
        font-size: 13px;
        color: {TEXT};
    }}
    QMainWindow, QDialog {{ background: {PAGE_BG}; }}
    QToolTip {{
        background: #24292f;
        color: #ffffff;
        border: none;
        padding: 4px 6px;
    }}

    /* ---------------------------------------------------- 侧边导航 */
    #Sidebar {{ background: {SURFACE}; border-right: 1px solid {BORDER_MUTED}; }}
    #SidebarTitle {{ color: {TEXT}; font-size: 16px; font-weight: 600; }}
    #SidebarSubtitle {{ color: {TEXT_SUBTLE}; font-size: 11px; }}
    #NavGroup {{
        background: {BG};
        border: 1px solid {BORDER};
        border-radius: 10px;
    }}
    #NavButton {{
        text-align: left;
        border: none;
        border-left: 3px solid transparent;
        border-radius: 0;
        background: transparent;
        padding: 0;
    }}
    #NavButton:hover {{ background: {SURFACE}; }}
    #NavButton:checked {{ background: {ACCENT_SOFT}; border-left: 3px solid {ACCENT}; }}
    #NavSeparator {{ background: {BORDER_MUTED}; border: none; }}

    /* -------------------------------------------------------- 顶栏 */
    #TopBar {{ background: {PAGE_BG}; border-bottom: 1px solid {BORDER_MUTED}; }}
    #PageTitle {{ font-size: 15px; font-weight: 600; }}

    /* -------------------------------------------------------- 卡片 */
    #Card {{
        background: {BG};
        border: 1px solid {BORDER};
        border-radius: 8px;
    }}
    #FocusCard {{
        background: {BG};
        border: 1px solid {BORDER};
        border-radius: 8px;
    }}
    #SectionHeader {{ color: {TEXT}; font-size: 13px; font-weight: 600; }}
    #Muted {{ color: {TEXT_MUTED}; font-size: 12px; }}
    #Subtle {{ color: {TEXT_SUBTLE}; font-size: 11px; }}
    #Mono {{ font-family: Consolas, "Cascadia Mono", monospace; font-size: 12px; color: {TEXT_MUTED}; }}

    /* -------------------------------------------------------- 按钮 */
    QPushButton {{
        background: {SURFACE};
        border: 1px solid {BORDER};
        border-radius: 6px;
        padding: 5px 12px;
        color: {TEXT};
    }}
    QPushButton:hover {{ background: {SURFACE_ALT}; }}
    QPushButton:pressed {{ background: #e6eaee; }}
    QPushButton:disabled {{ color: {TEXT_SUBTLE}; background: {SURFACE}; border-color: {BORDER_MUTED}; }}
    QPushButton#Primary {{ background: {ACCENT}; border-color: {ACCENT}; color: #ffffff; font-weight: 600; }}
    QPushButton#Primary:hover {{ background: {ACCENT_HOVER}; border-color: {ACCENT_HOVER}; }}
    QPushButton#Ghost {{ background: transparent; border: none; color: {ACCENT}; padding: 3px 6px; }}
    QPushButton#Ghost:hover {{ background: {ACCENT_SOFT}; border-radius: 6px; }}
    QPushButton#Collapse {{
        background: transparent; border: 1px solid transparent; color: {TEXT_MUTED};
        font-size: 15px; padding: 2px 8px;
    }}
    QPushButton#Collapse:hover {{ background: {SURFACE_ALT}; border-radius: 6px; color: {TEXT}; }}
    QPushButton#SectionToggle {{
        text-align: left; background: transparent; border: none;
        color: {TEXT}; font-weight: 600; padding: 4px 2px;
    }}
    QPushButton#SectionToggle:hover {{ color: {ACCENT}; }}

    /* --------------------------------------------------- 输入控件 */
    QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QDateEdit, QSpinBox {{
        background: {BG};
        border: 1px solid {BORDER};
        border-radius: 6px;
        padding: 4px 8px;
        selection-background-color: {ACCENT_SOFT};
        selection-color: {TEXT};
    }}
    QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QDateEdit:focus {{
        border-color: {ACCENT};
    }}
    QComboBox::drop-down {{ border: none; width: 18px; }}
    QComboBox QAbstractItemView {{
        background: {BG}; border: 1px solid {BORDER}; selection-background-color: {ACCENT_SOFT};
        selection-color: {TEXT}; outline: none;
    }}
    QCheckBox {{ color: {TEXT_MUTED}; spacing: 6px; }}

    /* ----------------------------------------------------- 树与表 */
    QTreeWidget, QTableWidget, QListWidget {{
        background: {BG};
        border: 1px solid {BORDER};
        border-radius: 8px;
        outline: none;
        gridline-color: {BORDER_MUTED};
    }}
    QTreeWidget::item, QListWidget::item {{ padding: 4px 2px; }}
    QTreeWidget::item:selected, QTableWidget::item:selected, QListWidget::item:selected {{
        background: {ACCENT_SOFT}; color: {TEXT};
    }}
    QHeaderView::section {{
        background: {SURFACE};
        color: {TEXT_MUTED};
        border: none;
        border-bottom: 1px solid {BORDER_MUTED};
        border-right: 1px solid {BORDER_MUTED};
        padding: 6px 8px;
        font-weight: 600;
    }}
    QTableWidget {{ gridline-color: {BORDER_MUTED}; }}

    /* ----------------------------------------------------- 滚动条 */
    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
    QScrollBar::handle:vertical {{ background: #d0d7de; border-radius: 5px; min-height: 30px; }}
    QScrollBar::handle:vertical:hover {{ background: #afb8c1; }}
    QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 0; }}
    QScrollBar::handle:horizontal {{ background: #d0d7de; border-radius: 5px; min-width: 30px; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

    QSplitter::handle {{ background: {BORDER_MUTED}; }}
    QSplitter::handle:hover {{ background: {BORDER}; }}
    QScrollArea {{ border: none; background: {PAGE_BG}; }}
    QStatusBar {{ background: {SURFACE}; color: {TEXT_MUTED}; border-top: 1px solid {BORDER_MUTED}; }}
    QTabWidget::pane {{ border: 1px solid {BORDER}; border-radius: 8px; }}
    QTabBar::tab {{ padding: 6px 12px; color: {TEXT_MUTED}; }}
    QTabBar::tab:selected {{ color: {TEXT}; font-weight: 600; }}
    QMenu {{ background: {BG}; border: 1px solid {BORDER}; padding: 4px; }}
    QMenu::item {{ padding: 5px 20px 5px 12px; border-radius: 4px; }}
    QMenu::item:selected {{ background: {ACCENT_SOFT}; }}
    QGroupBox {{ border: 1px solid {BORDER}; border-radius: 8px; margin-top: 12px; padding-top: 10px; }}
    QGroupBox::title {{ subcontrol-origin: margin; left: 10px; color: {TEXT_MUTED}; }}
    """
