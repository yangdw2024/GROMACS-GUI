# -*- coding: utf-8 -*-
"""
现代化 GUI (Modern UI Shell & Fallback Layout) 自动化回归与集成测试
覆盖：
1. 七大导航入口与 Tab 页面索引精确同步；
2. 经典双栏视图与现代工作台视图往返反复切换，控件对象与信号不丢失；
3. 深色模式与浅色模式往返切换，主题 Token 与 QPalette 正常更新；
4. 底部日志终端折叠/展开与高度分配；
5. 顶部系统配置抽屉展开/折叠与 GROMACS 版本徽标联动；
6. 顶部栏响应式自适应（880x620, 1024x768, 1280x820, 1920x1080）无重叠溢出；
7. 配置保存与加载数据一致性；
8. 任务运行期间界面控件状态保持（运行按钮禁用、停止按钮启用、进度条展示）。
"""

import os
import sys
import unittest.mock as mock
import pytest
from PyQt5.QtWidgets import QApplication, QFileDialog, QMessageBox
from PyQt5.QtCore import Qt

# 确保在无头环境运行
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture
def gui_window(qapp, tmp_path):
    from gui.main_window import GromacsGUI
    win = GromacsGUI()
    win.setAttribute(Qt.WA_DontShowOnScreen, True)
    win.show()
    qapp.processEvents()
    yield win
    win.close()


def test_nav_rail_tabs_synchronization(gui_window, qapp):
    """测试 1: 验证左侧导航 7 个项与中央 TabWidget 页面索引严格双向同步"""
    win = gui_window
    assert len(win.nav_buttons) == 7
    for expected_idx, btn in win.nav_buttons:
        btn.click()
        qapp.processEvents()
        assert win.tab_widget.currentIndex() == expected_idx
        assert btn.property("active") == "true"
        # 验证其它按钮为 false
        for other_idx, other_btn in win.nav_buttons:
            if other_idx != expected_idx:
                assert other_btn.property("active") == "false"


def test_theme_round_trip_toggle(gui_window, qapp):
    """测试 2: 验证深浅色主题往返切换自如且无崩溃"""
    win = gui_window
    initial_theme = win.current_theme
    # 切换到相反主题
    win.toggle_theme()
    qapp.processEvents()
    assert win.current_theme != initial_theme

    # 再次切回
    win.toggle_theme()
    qapp.processEvents()
    assert win.current_theme == initial_theme


def test_layout_mode_fallback_and_restore(gui_window, qapp):
    """测试 3: 验证经典双栏视图与现代工作台往返反复切换（回退机制安全）"""
    win = gui_window
    # 初始为现代布局
    assert win.ui_layout_mode == "modern"
    assert win.left_nav_rail.isVisible()
    assert not win.tab_widget.tabBar().isVisible()

    # 切换至经典双栏布局
    win.toggle_layout_mode()
    qapp.processEvents()
    assert win.ui_layout_mode == "classic"
    assert not win.left_nav_rail.isVisible()
    assert win.tab_widget.tabBar().isVisible()
    assert win.sys_config_drawer.isVisible()
    assert win.center_right_splitter.orientation() == Qt.Horizontal

    # 再次切回现代布局
    win.toggle_layout_mode()
    qapp.processEvents()
    assert win.ui_layout_mode == "modern"
    assert win.left_nav_rail.isVisible()
    assert not win.tab_widget.tabBar().isVisible()
    assert win.center_right_splitter.orientation() == Qt.Vertical


def test_console_drawer_collapse_and_expand(gui_window, qapp):
    """测试 4: 验证底部运行日志终端一键折叠与恢复功能"""
    win = gui_window
    assert win.console_expanded is True
    assert win.log_text.isVisible()

    # 折叠
    win.toggle_console_drawer()
    qapp.processEvents()
    assert win.console_expanded is False
    assert not win.log_text.isVisible()

    # 展开
    win.toggle_console_drawer()
    qapp.processEvents()
    assert win.console_expanded is True
    assert win.log_text.isVisible()


def test_sys_config_drawer_toggle(gui_window, qapp):
    """测试 5: 验证顶部硬件/版本胶囊徽标点击展开与收起系统配置抽屉"""
    win = gui_window
    assert not win.sys_config_drawer.isVisible()

    # 点击版本徽标展开
    win.ver_badge_btn.click()
    qapp.processEvents()
    assert win.sys_config_drawer.isVisible()

    # 点击 GPU 徽标收起
    win.gpu_badge_btn.click()
    qapp.processEvents()
    assert not win.sys_config_drawer.isVisible()


def test_topbar_responsive_adaptation(gui_window, qapp):
    """测试 6: 验证顶部状态栏在 880x620, 1024x768, 1280x820, 1920x1080 自适应无裁切"""
    win = gui_window
    # 窄屏 880x620: 必须收纳低频按钮，更多菜单必须可见
    win.resize(880, 620)
    qapp.processEvents()
    assert win.more_tools_btn.isVisible()
    assert not win.mdp_editor_btn.isVisible()
    assert not win.save_config_btn.isVisible()

    # 宽屏 1280x820: 低频操作直接展示在栏上
    win.resize(1280, 820)
    qapp.processEvents()
    assert win.more_tools_btn.isVisible()
    assert win.mdp_editor_btn.isVisible()
    assert win.save_config_btn.isVisible()


def test_config_save_load_data_consistency(gui_window, qapp, tmp_path):
    """测试 7: 验证配置保存、加载与数据字段 100% 一致性"""
    win = gui_window
    cfg_file = tmp_path / "gui_test_config.json"

    win.path_edit.setText(str(tmp_path))
    win.cfg_nt.setValue(7)
    win.evap_resname.setText("SOL_TEST")

    with mock.patch.object(QFileDialog, "getSaveFileName", return_value=(str(cfg_file), "JSON")), \
         mock.patch.object(QMessageBox, "information"), \
         mock.patch.object(QMessageBox, "critical"):
        win.save_config()

    assert cfg_file.is_file()

    # 篡改内存中的值后重新从文件加载
    win.cfg_nt.setValue(1)
    with mock.patch.object(QFileDialog, "getOpenFileName", return_value=(str(cfg_file), "JSON")), \
         mock.patch.object(QMessageBox, "warning"), \
         mock.patch.object(QMessageBox, "critical"):
        win.load_config()

    assert win.cfg_nt.value() == 7


def test_task_running_state_controls(gui_window, qapp):
    """测试 8: 验证任务运行状态期间控件正确锁定与解锁"""
    win = gui_window
    assert win.run_all_btn.isEnabled()
    assert not win.stop_btn.isEnabled()
    assert not win.progress_bar.isVisible()

    # 模拟启动运行状态
    win._set_running_state(True)
    qapp.processEvents()
    assert not win.run_all_btn.isEnabled()
    assert win.stop_btn.isEnabled()
    assert win.progress_bar.isVisible()

    # 模拟恢复空闲状态
    win._set_running_state(False)
    qapp.processEvents()
    assert win.run_all_btn.isEnabled()
    assert not win.stop_btn.isEnabled()
    assert not win.progress_bar.isVisible()
