# -*- coding: utf-8 -*-
"""
M3 中英文国际化与语言系统 (i18n) 专项测试与回归测试
覆盖：
1. 翻译词典完整性校验（所有 key 均同时存在 zh 和 en，无空串）；
2. GromacsGUI 全量切换语言 ("zh" <-> "en") 时主窗口外壳与七大功能组件级联更新；
3. 语言切换过程中不丢失任何现有表单状态与参数数值；
4. 科学命令与计算参数语言不变性：中英文模式下构建的 GROMACS / 绘图 / 脚本命令完全一致；
5. 旧版中文配置 JSON 向后加载兼容性；
6. 英文界面下 880x620 与 1280x820 多分辨率几何防重叠与防截断检查。
"""

import os
import sys
import json
import unittest.mock as mock
import pytest
from PyQt5.QtWidgets import QApplication, QFileDialog, QMessageBox
from PyQt5.QtCore import Qt

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_translations_dictionary_completeness():
    """测试 1: 验证所有 i18n 字典键值同时包含非空 zh 与 en 文本"""
    from gui.i18n import TRANSLATIONS, tr, set_language, get_language

    assert len(TRANSLATIONS) >= 50
    for key, pair in TRANSLATIONS.items():
        assert "zh" in pair and pair["zh"].strip(), f"Missing zh for key: {key}"
        assert "en" in pair and pair["en"].strip(), f"Missing en for key: {key}"

    prev = get_language()
    try:
        set_language("en")
        assert get_language() == "en"
        assert tr("run_all") == "▶ Run All"
        set_language("zh")
        assert get_language() == "zh"
        assert tr("run_all") == "▶ 一键运行"
    finally:
        set_language(prev)


def test_full_gui_language_switch_and_state_preservation(qapp, tmp_path):
    """测试 2: 验证切换语言后主窗口与七大 Tab 同步翻译且不丢失用户表单输入"""
    from gui.main_window import GromacsGUI

    win = GromacsGUI()
    win.setAttribute(Qt.WA_DontShowOnScreen, True)
    try:
        # 设置用户表单输入状态
        win.md_temp.setValue(350.5)
        win.md_box_size_mode.setCurrentIndex(1)  # box mode
        win.evap_resname.setText("SOL_KEEP")
        win.script_edit.setPlainText("gmx check -f md.xtc")

        # 切换至英文
        win.set_language("en")
        qapp.processEvents()

        assert win.run_all_btn.text() == "▶ Run All"
        assert win.lang_btn.text() == "中文"
        assert win.nav_buttons[0][1].text() == "Part 1 · MD Simulation"
        assert win.nav_buttons[6][1].text() == "Part 7 · Custom Scripts"
        assert win.mmpbsa_run_btn.text() == "▶ Run MMPBSA Calculation"
        assert win.script_run_btn.text() == "▶ Run Script"
        assert win.md_box_size_mode.currentText() == "By Box Size (-box)"

        # 验证表单状态 100% 保留
        assert win.md_temp.value() == 350.5
        assert win.md_box_size_mode.currentIndex() == 1
        assert win.evap_resname.text() == "SOL_KEEP"
        assert win.script_edit.toPlainText() == "gmx check -f md.xtc"

        # 切换回中文
        win.set_language("zh")
        qapp.processEvents()
        assert win.run_all_btn.text() == "▶ 一键运行"
        assert win.lang_btn.text() == "EN"
        assert win.nav_buttons[0][1].text() == "Part 1 · MD 模拟"
        assert win.md_temp.value() == 350.5
    finally:
        win.close()


def test_command_invariance_across_languages(qapp, tmp_path):
    """测试 3: 验证切换中英文后生成的 GROMACS 命令、盒子参数与脚本模板 100% 等价"""
    from gui.main_window import GromacsGUI
    from simulation.md_runner import build_md_step_command

    fake_gmx = tmp_path / "gmx.exe"
    fake_gmx.write_text("dummy", encoding="utf-8")

    win = GromacsGUI()
    win.setAttribute(Qt.WA_DontShowOnScreen, True)
    try:
        win.gmx_path = str(fake_gmx)
        win.path_edit.setText(str(tmp_path))

        # 1. 中文状态下设置 Box 为按盒子边长 (-box) 并记录命令与参数
        win.set_language("zh")
        win.md_box_size_mode.setCurrentIndex(1)  # -box
        win.md_box_type.setCurrentText("rectangular (长方体)")
        win.md_box_x.setValue(4.5)
        win.md_box_y.setValue(5.5)
        win.md_box_z.setValue(6.5)

        zh_box_params = win.md_tab._get_box_params()

        # 同步模拟 Step 2 editconf 构建命令
        s2_info = win.md_step_btns["Step 2"]
        s2_info["size_mode_combo"].setCurrentIndex(1)
        s2_info["box_type_combo"].setCurrentText("rectangular (长方体)")
        s2_info["box_x_spin"].setValue(4.5)
        s2_info["box_y_spin"].setValue(5.5)
        s2_info["box_z_spin"].setValue(6.5)

        zh_cmds = []
        win.md_tab.run_requested.disconnect()
        win.md_tab.run_requested.connect(lambda c, w, s: zh_cmds.append(c))
        win.run_md_step("Step 2")

        # 2. 切换为英文后再次获取盒子参数并生成命令
        win.set_language("en")
        s2_info["size_mode_combo"].setItemText(1, "By Box Size (-box)")
        en_box_params = win.md_tab._get_box_params()

        en_cmds = []
        win.md_tab.run_requested.disconnect()
        win.md_tab.run_requested.connect(lambda c, w, s: en_cmds.append(c))
        win.run_md_step("Step 2")

        assert zh_box_params == en_box_params
        assert zh_cmds == en_cmds, f"Command drifted in English mode! zh={zh_cmds} vs en={en_cmds}"

        # 3. ScriptTab 模板生成一致性
        win.set_language("zh")
        win.script_tab.load_script_template("em")
        zh_script = win.script_edit.toPlainText()

        win.set_language("en")
        win.script_tab.load_script_template("em")
        en_script = win.script_edit.toPlainText()
        assert zh_script == en_script
    finally:
        win.set_language("zh")
        win.close()


def test_legacy_chinese_config_loads_in_english_mode(qapp, tmp_path):
    """测试 4: 验证英文模式下仍可正常加载旧版未含 language 字段的中文配置 JSON"""
    from gui.main_window import GromacsGUI

    legacy_cfg = {
        "version": "1.0",
        "global": {
            "work_dir": str(tmp_path),
            "temp": 315.0,
            "box_type": "cubic (立方体)",
            "size_mode": "按边距 (-d)",
            "ff": "amber99sb-ildn",
        },
        "part1_steps": {},
        "script_type": "Shell 命令"
    }
    cfg_path = tmp_path / "legacy_zh.json"
    cfg_path.write_text(json.dumps(legacy_cfg, ensure_ascii=False), encoding="utf-8")

    win = GromacsGUI()
    win.setAttribute(Qt.WA_DontShowOnScreen, True)
    try:
        win.set_language("en")
        with mock.patch.object(QFileDialog, "getOpenFileName", return_value=(str(cfg_path), "JSON")), \
             mock.patch.object(QMessageBox, "warning"), \
             mock.patch.object(QMessageBox, "critical"):
            win.load_config()

        assert win.md_temp.value() == 315.0
        assert win.md_ff.currentText() == "amber99sb-ildn"
        assert (win.script_type.currentData() or win.script_type.currentText()) == "Shell 命令"
    finally:
        win.set_language("zh")
        win.close()


def test_english_ui_geometry_no_overlap(qapp):
    """测试 5: 验证英文模式下 880x620 与 1280x820 顶栏按钮及导航无重叠越界"""
    from gui.main_window import GromacsGUI

    win = GromacsGUI()
    win.setAttribute(Qt.WA_DontShowOnScreen, True)
    try:
        win.set_language("en")
        win.show()
        for w, h in [(880, 620), (1280, 820)]:
            win.resize(w, h)
            qapp.processEvents()
            qapp.processEvents()

            row1 = [
                win.run_all_btn, win.stop_btn, win.mdp_editor_btn, win.monitor_btn,
                win.save_config_btn, win.load_config_btn, win.more_tools_btn,
                win.theme_btn, win.layout_mode_btn, win.lang_btn
            ]
            vis = [b for b in row1 if b.isVisible()]
            for i in range(len(vis)):
                g1 = vis[i].geometry()
                assert g1.left() >= 0 and g1.right() <= w, f"EN [{w}x{h}] out of bounds: {vis[i].text()} {g1}"
                for j in range(i + 1, len(vis)):
                    assert not g1.intersects(vis[j].geometry()), (
                        f"EN [{w}x{h}] overlap: {vis[i].text()} vs {vis[j].text()}"
                    )
    finally:
        win.set_language("zh")
        win.close()
