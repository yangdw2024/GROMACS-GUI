# -*- coding: utf-8 -*-
"""
GROMACS-GUI 现代化视觉规范与双主题系统 (Design Tokens & QSS Engine)
集中管理深色/浅色主题颜色、字体、间距、圆角与控件状态，
采用 ID 与语义属性选择器 (setProperty("role", ...))，避免意外覆盖已有业务控件的独立样式。
"""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPalette

DARK_TOKENS = {
    "name": "dark",
    "bg_app": "#0F172A",          # Slate 900 主背景
    "bg_surface": "#1E293B",      # Slate 800 面板/导航栏/顶栏背景
    "bg_elevated": "#263349",     # 悬浮/输入框/次级容器背景
    "bg_console": "#090D16",      # 底部终端背景
    "bg_hover": "#334155",        # 悬停态背景
    "bg_active_nav": "#1D4ED8",   # 导航选中高亮底色
    "border": "#334155",          # 常规分隔边框
    "border_subtle": "#1E293B",   # 弱边框
    "border_focus": "#3B82F6",    # 焦点高亮边框
    "text_primary": "#F8FAFC",    # 主文字
    "text_secondary": "#94A3B8",  # 次级说明文字
    "text_muted": "#64748B",      # 占位/禁用文字
    "group_title": "#93C5FD",     # GroupBox 标题色
    "primary": "#2563EB",         # 主品牌蓝
    "primary_hover": "#3B82F6",
    "primary_pressed": "#1D4ED8",
    "success": "#10B981",         # 运行/成功绿
    "success_hover": "#059669",
    "danger": "#EF4444",          # 停止/错误红
    "danger_hover": "#DC2626",
    "warning": "#F59E0B",         # 警告琥珀色
    "badge_bg": "#1E3A8A",
    "badge_text": "#93C5FD",
    "badge_gpu_bg": "#064E3B",
    "badge_gpu_text": "#6EE7B7",
}

LIGHT_TOKENS = {
    "name": "light",
    "bg_app": "#F1F5F9",          # Slate 100 主背景
    "bg_surface": "#FFFFFF",      # 纯白面板/导航栏/顶栏背景
    "bg_elevated": "#F8FAFC",     # 表单输入框/次级容器背景
    "bg_console": "#0F172A",      # 终端保持深色高对比度护眼风格
    "bg_hover": "#E2E8F0",        # 悬停态背景
    "bg_active_nav": "#EFF6FF",   # 导航选中浅蓝底
    "border": "#CBD5E1",          # 常规分隔边框
    "border_subtle": "#E2E8F0",   # 弱边框
    "border_focus": "#2563EB",    # 焦点高亮边框
    "text_primary": "#0F172A",    # 主文字
    "text_secondary": "#475569",  # 次级说明文字
    "text_muted": "#94A3B8",      # 占位/禁用文字
    "group_title": "#0D47A1",     # GroupBox 标题色
    "primary": "#2563EB",         # 主品牌蓝
    "primary_hover": "#1D4ED8",
    "primary_pressed": "#1E40AF",
    "success": "#059669",         # 运行/成功绿
    "success_hover": "#047857",
    "danger": "#DC2626",          # 停止/错误红
    "danger_hover": "#B91C1C",
    "warning": "#D97706",         # 警告橙
    "badge_bg": "#DBEAFE",
    "badge_text": "#1E40AF",
    "badge_gpu_bg": "#D1FAE5",
    "badge_gpu_text": "#065F46",
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
    """构建现代化主窗口外壳与基础控件样式表"""
    def px(val: int) -> str:
        return f"{max(1, int(round(val * scale)))}px"

    def pt(val: float) -> str:
        return f"{max(7, int(round(val * scale)))}pt"

    t = tokens
    nav_active_fg = "#FFFFFF" if t["name"] == "dark" else "#1D4ED8"
    nav_active_border = "#60A5FA" if t["name"] == "dark" else "#2563EB"

    return f"""
    QMainWindow {{
        background-color: {t["bg_app"]};
        color: {t["text_primary"]};
    }}
    QWidget {{
        color: {t["text_primary"]};
        font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", sans-serif;
    }}

    /* ==================== 顶部简洁状态栏与可展开硬件抽屉 ==================== */
    QFrame#topHeaderBar {{
        background-color: {t["bg_surface"]};
        border-bottom: {px(1)} solid {t["border"]};
    }}
    QFrame#sysConfigDrawer {{
        background-color: {t["bg_elevated"]};
        border-bottom: {px(1)} solid {t["border"]};
    }}
    QLabel#brandTitle {{
        color: {t["text_primary"]};
        font-size: {pt(11.5)};
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
        padding: {px(7)} {px(10)};
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

    /* ==================== 语义化主控按钮 ==================== */
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
    QPushButton[role="secondaryTool"] {{
        background-color: {t["bg_elevated"]};
        color: {t["text_primary"]};
        border: {px(1)} solid {t["border"]};
        border-radius: {px(6)};
        padding: {px(4)} {px(10)};
        min-height: {px(24)};
        font-weight: 600;
    }}
    QPushButton[role="secondaryTool"]:hover {{
        background-color: {t["bg_hover"]};
        border-color: {t["border_focus"]};
    }}

    /* ==================== 基础表单与分组框样式 ==================== */
    QGroupBox {{
        font-weight: bold;
        color: {t["group_title"]};
        background-color: {t["bg_surface"]};
        border: {px(1)} solid {t["border"]};
        border-radius: {px(6)};
        margin-top: {px(10)};
        padding-top: {px(8)};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: {px(10)};
        padding: 0 {px(6)};
        color: {t["group_title"]};
    }}
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
        background-color: {t["bg_elevated"]};
        color: {t["text_primary"]};
        border: {px(1)} solid {t["border"]};
        border-radius: {px(4)};
        padding: {px(3)} {px(6)};
        min-height: {px(20)};
    }}
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
        border: {px(1)} solid {t["border_focus"]};
    }}
    QComboBox QAbstractItemView {{
        background-color: {t["bg_surface"]};
        color: {t["text_primary"]};
        selection-background-color: {t["primary"]};
        selection-color: #FFFFFF;
    }}
    QTabWidget::pane {{
        border: {px(1)} solid {t["border"]};
        border-radius: {px(6)};
        background-color: {t["bg_surface"]};
    }}
    QTabBar::tab {{
        background-color: {t["bg_elevated"]};
        color: {t["text_secondary"]};
        padding: {px(6)} {px(14)};
        margin-right: {px(2)};
        border-top-left-radius: {px(5)};
        border-top-right-radius: {px(5)};
        font-weight: bold;
    }}
    QTabBar::tab:selected {{
        background-color: {t["primary"]};
        color: #FFFFFF;
    }}
    QScrollArea {{
        border: none;
        background-color: transparent;
    }}
    QTextEdit, QPlainTextEdit, QListWidget, QTableWidget {{
        background-color: {t["bg_elevated"]};
        color: {t["text_primary"]};
        border: {px(1)} solid {t["border"]};
        border-radius: {px(4)};
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
    QTextEdit#consoleLogView {{
        background-color: {t["bg_console"]};
        color: #E2E8F0;
        border: none;
        font-family: "Consolas", "Cascadia Mono", monospace;
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
    QToolTip {{
        background-color: {t["bg_surface"]};
        color: {t["text_primary"]};
        border: {px(1)} solid {t["border_focus"]};
        padding: {px(4)};
        border-radius: {px(4)};
    }}
    """
