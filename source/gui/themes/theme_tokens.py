# -*- coding: utf-8 -*-
"""
GROMACS-GUI 现代化视觉设计系统 (Design System & QSS Engine)
集中管理深色/浅色主题的颜色、排版、圆角、间距及语义化组件样式，
遵循克制、专业、高对比度科研桌面软件规范，彻底取代页面内硬编码的彩虹色与低对比度内联样式。
"""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPalette

DESIGN_SYSTEM_META = {
    "font_ui": '"Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", sans-serif',
    "font_mono": '"Consolas", "Cascadia Mono", "Courier New", monospace',
    "radius_sm": 4,
    "radius_md": 6,
    "radius_lg": 8,
    "space_xs": 4,
    "space_sm": 8,
    "space_md": 12,
    "space_lg": 16,
}

DARK_TOKENS = {
    "name": "dark",
    "bg_app": "#0F172A",          # Slate 900 主背景
    "bg_surface": "#1E293B",      # Slate 800 面板/导航栏/顶栏背景
    "bg_elevated": "#263349",     # 悬浮/输入框/次级容器背景
    "bg_card": "#192335",         # 子工具卡片底色
    "bg_console": "#090D16",      # 底部终端背景
    "bg_hover": "#334155",        # 悬停态背景
    "bg_active_nav": "#1D4ED8",   # 导航选中高亮底色
    "border": "#334155",          # 常规分隔边框
    "border_subtle": "#243044",   # 弱边框
    "border_focus": "#3B82F6",    # 焦点高亮边框
    "border_phase": "#3B82F6",    # 阶段性主卡片点缀边框
    "text_primary": "#F8FAFC",    # 主文字 (高对比度)
    "text_secondary": "#CBD5E1",  # 次级说明文字 (Slate 300, 在深色底上清晰可读)
    "text_muted": "#94A3B8",      # 占位/分组小标题
    "group_title": "#93C5FD",     # GroupBox 标题色
    "primary": "#2563EB",         # 主品牌蓝 (Cobalt Blue)
    "primary_hover": "#3B82F6",
    "primary_pressed": "#1D4ED8",
    "success": "#10B981",         # 运行/成功绿 (Emerald)
    "success_hover": "#059669",
    "danger": "#EF4444",          # 停止/错误红 (Rose)
    "danger_hover": "#DC2626",
    "warning": "#F59E0B",         # 警告琥珀色
    "warning_bg": "rgba(245, 158, 11, 0.14)",
    "warning_text": "#FCD34D",
    "accent": "#0284C7",          # 辅助科研操作色 (Sky 600)
    "accent_hover": "#0369A1",
    "browse_bg": "#334155",
    "browse_hover": "#475569",
    "badge_bg": "#1E3A8A",
    "badge_text": "#93C5FD",
    "badge_gpu_bg": "#064E3B",
    "badge_gpu_text": "#6EE7B7",
    "table_header_bg": "#1E293B",
    "scrollbar_bg": "#0F172A",
    "scrollbar_handle": "#475569",
}

LIGHT_TOKENS = {
    "name": "light",
    "bg_app": "#F1F5F9",          # Slate 100 主背景
    "bg_surface": "#FFFFFF",      # 纯白面板/导航栏/顶栏背景
    "bg_elevated": "#F8FAFC",     # 表单输入框/次级容器背景
    "bg_card": "#F8FAFC",         # 子工具卡片底色
    "bg_console": "#0F172A",      # 终端保持深色高对比度护眼风格
    "bg_hover": "#E2E8F0",        # 悬停态背景
    "bg_active_nav": "#EFF6FF",   # 导航选中浅蓝底
    "border": "#CBD5E1",          # 常规分隔边框
    "border_subtle": "#E2E8F0",   # 弱边框
    "border_focus": "#2563EB",    # 焦点高亮边框
    "border_phase": "#2563EB",    # 阶段性主卡片点缀边框
    "text_primary": "#0F172A",    # 主文字 (Slate 900)
    "text_secondary": "#475569",  # 次级说明文字 (Slate 600)
    "text_muted": "#64748B",      # 占位/分组小标题
    "group_title": "#1E40AF",     # GroupBox 标题色 (Blue 800)
    "primary": "#2563EB",         # 主品牌蓝
    "primary_hover": "#1D4ED8",
    "primary_pressed": "#1E40AF",
    "success": "#059669",         # 运行/成功绿
    "success_hover": "#047857",
    "danger": "#DC2626",          # 停止/错误红
    "danger_hover": "#B91C1C",
    "warning": "#D97706",         # 警告橙
    "warning_bg": "rgba(245, 158, 11, 0.12)",
    "warning_text": "#92400E",
    "accent": "#0284C7",          # 辅助科研操作色
    "accent_hover": "#0369A1",
    "browse_bg": "#475569",
    "browse_hover": "#334155",
    "badge_bg": "#DBEAFE",
    "badge_text": "#1E40AF",
    "badge_gpu_bg": "#D1FAE5",
    "badge_gpu_text": "#065F46",
    "table_header_bg": "#F1F5F9",
    "scrollbar_bg": "#F1F5F9",
    "scrollbar_handle": "#94A3B8",
}


def get_theme_tokens(theme_name: str) -> dict:
    return DARK_TOKENS if str(theme_name).lower() == "dark" else LIGHT_TOKENS


def build_palette(tokens: dict) -> QPalette:
    """构建与当前主题对应的 QPalette"""
    palette = QPalette()
    if tokens["name"] == "dark":
        palette.setColor(QPalette.Window, QColor(15, 23, 42))
        palette.setColor(QPalette.WindowText, QColor(248, 250, 252))
        palette.setColor(QPalette.Base, QColor(30, 41, 59))
        palette.setColor(QPalette.AlternateBase, QColor(38, 51, 73))
        palette.setColor(QPalette.ToolTipBase, QColor(30, 41, 59))
        palette.setColor(QPalette.ToolTipText, QColor(248, 250, 252))
        palette.setColor(QPalette.Text, QColor(248, 250, 252))
        palette.setColor(QPalette.Button, QColor(30, 41, 59))
        palette.setColor(QPalette.ButtonText, QColor(248, 250, 252))
        palette.setColor(QPalette.BrightText, Qt.red)
        palette.setColor(QPalette.Highlight, QColor(37, 99, 235))
        palette.setColor(QPalette.HighlightedText, Qt.white)
    else:
        palette.setColor(QPalette.Window, QColor(241, 245, 249))
        palette.setColor(QPalette.WindowText, QColor(15, 23, 42))
        palette.setColor(QPalette.Base, QColor(255, 255, 255))
        palette.setColor(QPalette.AlternateBase, QColor(248, 250, 252))
        palette.setColor(QPalette.ToolTipBase, QColor(255, 255, 255))
        palette.setColor(QPalette.ToolTipText, QColor(15, 23, 42))
        palette.setColor(QPalette.Text, QColor(15, 23, 42))
        palette.setColor(QPalette.Button, QColor(248, 250, 252))
        palette.setColor(QPalette.ButtonText, QColor(15, 23, 42))
        palette.setColor(QPalette.BrightText, Qt.red)
        palette.setColor(QPalette.Highlight, QColor(37, 99, 235))
        palette.setColor(QPalette.HighlightedText, Qt.white)
    return palette


def build_shell_stylesheet(tokens: dict, scale: float = 1.0) -> str:
    """构建现代化主窗口外壳与全套语义化组件样式表"""
    def px(val: int) -> str:
        return f"{max(1, int(round(val * scale)))}px"

    def pt(val: float) -> str:
        return f"{max(7, int(round(val * scale)))}pt"

    t = tokens
    nav_active_fg = "#FFFFFF" if t["name"] == "dark" else "#1D4ED8"
    nav_active_border = "#60A5FA" if t["name"] == "dark" else "#2563EB"
    font_ui = DESIGN_SYSTEM_META["font_ui"]
    font_mono = DESIGN_SYSTEM_META["font_mono"]

    return f"""
    QMainWindow {{
        background-color: {t["bg_app"]};
        color: {t["text_primary"]};
    }}
    QWidget {{
        color: {t["text_primary"]};
        font-family: {font_ui};
    }}

    /* ==================== 顶部双层工作台状态与操作栏 ==================== */
    QFrame#topHeaderBar {{
        background-color: {t["bg_surface"]};
        border-bottom: {px(1)} solid {t["border_subtle"]};
    }}
    QFrame#workdirBar {{
        background-color: {t["bg_elevated"]};
        border-bottom: {px(1)} solid {t["border"]};
    }}
    QFrame#sysConfigDrawer {{
        background-color: {t["bg_elevated"]};
        border-bottom: {px(1)} solid {t["border"]};
    }}
    QLabel#brandTitle {{
        color: {t["text_primary"]};
        font-size: {pt(11)};
        font-weight: bold;
    }}
    QLabel#brandSubtitle {{
        color: {t["text_secondary"]};
        font-size: {pt(8)};
    }}
    QPushButton[role="envBadge"] {{
        background-color: {t["badge_bg"]};
        color: {t["badge_text"]};
        border: {px(1)} solid {t["border_focus"]};
        border-radius: {px(6)};
        padding: {px(4)} {px(10)};
        font-size: {pt(8.5)};
        font-weight: bold;
    }}
    QPushButton[role="envBadge"]:hover {{
        background-color: {t["bg_hover"]};
    }}
    QPushButton[role="gpuBadge"] {{
        background-color: {t["badge_gpu_bg"]};
        color: {t["badge_gpu_text"]};
        border: {px(1)} solid {t["success"]};
        border-radius: {px(6)};
        padding: {px(4)} {px(10)};
        font-size: {pt(8.5)};
        font-weight: bold;
    }}
    QPushButton[role="gpuBadge"]:hover {{
        background-color: {t["bg_hover"]};
    }}

    /* ==================== 左侧垂直导航工作台 ==================== */
    QFrame#leftNavRail {{
        background-color: {t["bg_surface"]};
        border-right: {px(1)} solid {t["border"]};
    }}
    QLabel[role="navSectionHeader"] {{
        color: {t["text_muted"]};
        font-size: {pt(8)};
        font-weight: bold;
        padding: {px(6)} {px(10)} {px(2)} {px(10)};
    }}
    QPushButton[role="navItem"] {{
        background-color: transparent;
        color: {t["text_secondary"]};
        border: none;
        border-left: {px(3)} solid transparent;
        border-radius: {px(5)};
        text-align: left;
        padding: {px(5)} {px(10)};
        font-size: {pt(9)};
        font-weight: 600;
    }}
    QPushButton[role="navItem"]:hover {{
        background-color: {t["bg_hover"]};
        color: {t["text_primary"]};
    }}
    QPushButton[role="navItem"][active="true"] {{
        background-color: {t["bg_active_nav"]};
        color: {nav_active_fg};
        border-left: {px(3)} solid {nav_active_border};
        font-weight: bold;
    }}

    /* ==================== 语义化主控与操作按钮 ==================== */
    QPushButton[role="primaryRun"] {{
        background-color: {t["success"]};
        color: #FFFFFF;
        border: none;
        border-radius: {px(6)};
        padding: {px(5)} {px(14)};
        min-height: {px(26)};
        font-weight: bold;
    }}
    QPushButton[role="primaryRun"]:hover {{
        background-color: {t["success_hover"]};
    }}
    QPushButton[role="primaryRun"]:disabled {{
        background-color: {t["bg_elevated"]};
        color: {t["text_muted"]};
    }}
    QPushButton[role="dangerStop"] {{
        background-color: {t["danger"]};
        color: #FFFFFF;
        border: none;
        border-radius: {px(6)};
        padding: {px(5)} {px(12)};
        min-height: {px(26)};
        font-weight: bold;
    }}
    QPushButton[role="dangerStop"]:hover {{
        background-color: {t["danger_hover"]};
    }}
    QPushButton[role="dangerStop"]:disabled {{
        background-color: {t["bg_elevated"]};
        color: {t["text_muted"]};
        border: {px(1)} solid {t["border"]};
    }}
    QPushButton[role="secondaryTool"], QToolButton[role="secondaryTool"] {{
        background-color: {t["bg_elevated"]};
        color: {t["text_primary"]};
        border: {px(1)} solid {t["border"]};
        border-radius: {px(6)};
        padding: {px(4)} {px(10)};
        min-height: {px(24)};
        font-weight: 600;
    }}
    QPushButton[role="secondaryTool"]:hover, QToolButton[role="secondaryTool"]:hover {{
        background-color: {t["bg_hover"]};
        border-color: {t["border_focus"]};
    }}
    QPushButton[role="actionBtn"] {{
        background-color: {t["primary"]};
        color: #FFFFFF;
        border: none;
        border-radius: {px(5)};
        padding: {px(5)} {px(14)};
        min-height: {px(24)};
        font-weight: bold;
    }}
    QPushButton[role="actionBtn"]:hover {{
        background-color: {t["primary_hover"]};
    }}
    QPushButton[role="actionBtn"]:disabled {{
        background-color: {t["bg_elevated"]};
        color: {t["text_muted"]};
    }}
    QPushButton[role="accentBtn"] {{
        background-color: {t["accent"]};
        color: #FFFFFF;
        border: none;
        border-radius: {px(5)};
        padding: {px(5)} {px(14)};
        min-height: {px(24)};
        font-weight: bold;
    }}
    QPushButton[role="accentBtn"]:hover {{
        background-color: {t["accent_hover"]};
    }}
    QPushButton[role="browseBtn"] {{
        background-color: {t["browse_bg"]};
        color: #FFFFFF;
        border: none;
        border-radius: {px(4)};
        padding: {px(3)} {px(8)};
        font-size: {pt(8.5)};
    }}
    QPushButton[role="browseBtn"]:hover {{
        background-color: {t["browse_hover"]};
    }}

    /* ==================== 语义化提示标签与文本 ==================== */
    QLabel[role="hint"], QLabel[role="desc"] {{
        color: {t["text_secondary"]};
        font-size: {pt(8.5)};
    }}
    QLabel[role="warningBanner"] {{
        background-color: {t["warning_bg"]};
        color: {t["warning_text"]};
        padding: {px(8)} {px(12)};
        border-radius: {px(6)};
        border: {px(1)} solid {t["warning"]};
        font-weight: bold;
    }}

    /* ==================== 基础表单与容器样式（限定在主窗口与其容器内部） ==================== */
    QMainWindow QGroupBox, QWidget#rootWidget QGroupBox {{
        font-weight: bold;
        color: {t["group_title"]};
        background-color: {t["bg_surface"]};
        border: {px(1)} solid {t["border"]};
        border-radius: {px(6)};
        margin-top: {px(10)};
        padding-top: {px(10)};
    }}
    QMainWindow QGroupBox[role="phaseGroup"], QWidget#rootWidget QGroupBox[role="phaseGroup"] {{
        background-color: {t["bg_surface"]};
        border: {px(1)} solid {t["border_phase"]};
        border-radius: {px(8)};
        margin-top: {px(12)};
        padding-top: {px(12)};
    }}
    QMainWindow QGroupBox[role="toolCard"], QWidget#rootWidget QGroupBox[role="toolCard"] {{
        background-color: {t["bg_card"]};
        border: {px(1)} solid {t["border_subtle"]};
        border-radius: {px(6)};
        margin-top: {px(8)};
        padding-top: {px(8)};
    }}
    QMainWindow QGroupBox::title, QWidget#rootWidget QGroupBox::title {{
        subcontrol-origin: margin;
        left: {px(10)};
        padding: 0 {px(6)};
        color: {t["group_title"]};
    }}
    QMainWindow QLineEdit, QWidget#rootWidget QLineEdit,
    QMainWindow QComboBox, QWidget#rootWidget QComboBox,
    QMainWindow QSpinBox, QWidget#rootWidget QSpinBox,
    QMainWindow QDoubleSpinBox, QWidget#rootWidget QDoubleSpinBox {{
        background-color: {t["bg_elevated"]};
        color: {t["text_primary"]};
        border: {px(1)} solid {t["border"]};
        border-radius: {px(4)};
        padding: {px(3)} {px(6)};
        min-height: {px(20)};
    }}
    QMainWindow QLineEdit:focus, QWidget#rootWidget QLineEdit:focus,
    QMainWindow QComboBox:focus, QWidget#rootWidget QComboBox:focus,
    QMainWindow QSpinBox:focus, QWidget#rootWidget QSpinBox:focus,
    QMainWindow QDoubleSpinBox:focus, QWidget#rootWidget QDoubleSpinBox:focus {{
        border: {px(1)} solid {t["border_focus"]};
    }}
    QComboBox QAbstractItemView {{
        background-color: {t["bg_surface"]};
        color: {t["text_primary"]};
        selection-background-color: {t["primary"]};
        selection-color: #FFFFFF;
    }}
    QTabWidget#mainTabWidget::pane {{
        border: {px(1)} solid {t["border"]};
        border-radius: {px(6)};
        background-color: {t["bg_surface"]};
    }}
    QTabWidget#mainTabWidget > QTabBar::tab {{
        background-color: {t["bg_elevated"]};
        color: {t["text_secondary"]};
        padding: {px(6)} {px(14)};
        margin-right: {px(2)};
        border-top-left-radius: {px(5)};
        border-top-right-radius: {px(5)};
        font-weight: bold;
    }}
    QTabWidget#mainTabWidget > QTabBar::tab:selected {{
        background-color: {t["primary"]};
        color: #FFFFFF;
    }}
    QMainWindow QScrollArea, QWidget#rootWidget QScrollArea {{
        border: none;
        background-color: transparent;
    }}
    QMainWindow QTextEdit, QWidget#rootWidget QTextEdit,
    QMainWindow QPlainTextEdit, QWidget#rootWidget QPlainTextEdit,
    QMainWindow QListWidget, QWidget#rootWidget QListWidget,
    QMainWindow QTableWidget, QWidget#rootWidget QTableWidget {{
        background-color: {t["bg_elevated"]};
        color: {t["text_primary"]};
        border: {px(1)} solid {t["border"]};
        border-radius: {px(4)};
        gridline-color: {t["border_subtle"]};
    }}
    QHeaderView::section {{
        background-color: {t["table_header_bg"]};
        color: {t["text_primary"]};
        padding: {px(4)} {px(6)};
        border: none;
        border-bottom: {px(1)} solid {t["border"]};
        font-weight: bold;
    }}
    QScrollBar:vertical {{
        background: {t["scrollbar_bg"]};
        width: {px(8)};
        margin: 0px;
    }}
    QScrollBar::handle:vertical {{
        background: {t["scrollbar_handle"]};
        min-height: {px(24)};
        border-radius: {px(4)};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}

    /* ==================== 底部可折叠日志与监控抽屉 ==================== */
    QFrame#bottomConsoleDrawer {{
        background-color: {t["bg_surface"]};
        border-top: {px(1)} solid {t["border"]};
    }}
    QFrame#consoleHeaderBar {{
        background-color: {t["bg_elevated"]};
        border-bottom: {px(1)} solid {t["border"]};
    }}
    QMainWindow QTextEdit#consoleLogView, QWidget#rootWidget QTextEdit#consoleLogView, QTextEdit#consoleLogView {{
        background-color: {t["bg_console"]};
        color: #E2E8F0;
        border: none;
        font-family: {font_mono};
    }}
    QProgressBar {{
        background-color: {t["bg_elevated"]};
        color: {t["text_primary"]};
        border: {px(1)} solid {t["border"]};
        border-radius: {px(4)};
        text-align: center;
    }}
    QProgressBar::chunk {{
        background-color: {t["primary"]};
        border-radius: {px(3)};
    }}
    QMenu {{
        background-color: {t["bg_surface"]};
        color: {t["text_primary"]};
        border: {px(1)} solid {t["border"]};
    }}
    QMenu::item:selected {{
        background-color: {t["primary"]};
        color: #FFFFFF;
    }}
    QToolTip {{
        background-color: {t["bg_surface"]};
        color: {t["text_primary"]};
        border: {px(1)} solid {t["border_focus"]};
        padding: {px(4)};
        border-radius: {px(4)};
    }}
    """
