# -*- coding: utf-8 -*-
"""
Part 3 高级模拟独立组件 (AdvancedTab) 专项单元测试与回归测试
覆盖：
1. 伞形采样、WHAM、元动力学及 ABF 各部件默认值与范围；
2. 伞形采样 MDP 批次生成 (generate_umbrella_mdp) 文件内容与条数校验；
3. WHAM 自由能计算与元动力学 (PLUMED) 命令构建及 Qt 信号派发 (run_requested)；
4. PLUMED metad 与 ABF 配置文件生成 (generate_plumed_meta, generate_plumed_abf)；
5. get_config / set_config 配置序列化往返一致性；
6. set_running_state 运行状态锁对全部高级模拟按钮的锁定与恢复；
7. 主窗口 GromacsGUI 挂载 AdvancedTab 后的全量别名兼容、运行状态锁定 (_set_running_state)、
   按钮点击以及旧接口 win.run_wham(), win.run_metadynamics() 单次派发防重发（全面 Mock 隔离真实命令与弹窗）。
"""

import os
import sys
import unittest.mock as mock
import pytest
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture
def adv_tab(qapp, tmp_path):
    from gui.tabs.advanced_tab import AdvancedTab
    tab = AdvancedTab(
        get_work_dir=lambda: str(tmp_path),
        get_gmx_path=lambda: "gmx",
        get_mdrun_extra=lambda: ["-nt", "4", "-nb", "gpu"]
    )
    return tab


def test_advanced_tab_defaults(adv_tab):
    """测试 1: 验证控件初始状态、范围与默认值"""
    # 伞形采样
    assert adv_tab.umb_tpr.text() == "md.tpr"
    assert adv_tab.umb_xtc.text() == "md.xtc"
    assert adv_tab.umb_pull_coord.currentText() == "distance"
    assert adv_tab.umb_pull_force.value() == 1000.0
    assert adv_tab.umb_pull_start.value() == 0.0
    assert adv_tab.umb_pull_end.value() == 5.0
    assert adv_tab.umb_pull_nwindows.value() == 10
    assert adv_tab.umb_run_btn.isEnabled()

    # WHAM
    assert adv_tab.wham_files.text() == "pull*.xvg"
    assert adv_tab.wham_temp.value() == 300.0
    assert adv_tab.wham_out.text() == "profile.xvg"
    assert adv_tab.wham_run_btn.isEnabled()

    # 元动力学
    assert adv_tab.meta_tpr.text() == "md.tpr"
    assert adv_tab.meta_plumed.text() == "plumed.dat"
    assert adv_tab.meta_biasfactor.value() == 10.0
    assert adv_tab.meta_height.value() == 0.3
    assert adv_tab.meta_sigma.value() == 0.1
    assert adv_tab.meta_gen_btn.isEnabled()
    assert adv_tab.meta_run_btn.isEnabled()

    # ABF
    assert adv_tab.abf_tpr.text() == "md.tpr"
    assert adv_tab.abf_plumed.text() == "plumed_abf.dat"
    assert adv_tab.abf_min.value() == 0.0
    assert adv_tab.abf_max.value() == 5.0
    assert adv_tab.abf_nbins.value() == 100
    assert adv_tab.abf_gen_btn.isEnabled()


def test_umbrella_mdp_generation(adv_tab, tmp_path):
    """测试 2: 验证伞形采样 MDP 批量生成"""
    logs = []
    adv_tab.log_requested.connect(lambda m, l: logs.append((m, l)))

    adv_tab.umb_pull_nwindows.setValue(5)
    adv_tab.generate_umbrella_mdp()

    # 检查生成的文件
    for i in range(5):
        f = tmp_path / f"umbrella_{i}.mdp"
        assert f.is_file(), f"Missing MDP file: {f}"
        content = f.read_text(encoding="utf-8")
        assert "pull = yes" in content
        assert "pull_coord1_init" in content

    assert any("已生成 5 个伞形采样 MDP 文件" in m for m, _ in logs)


def test_wham_and_metadynamics_dispatch(adv_tab, tmp_path):
    """测试 3: 验证 WHAM 与元动力学命令生成与信号上抛"""
    cmds = []
    adv_tab.run_requested.connect(lambda c, w, s: cmds.append((c, w, s)))

    # 3.1 测试 WHAM
    adv_tab.wham_files.setText("sim_pull*.xvg")
    adv_tab.wham_temp.setValue(310.0)
    adv_tab.wham_out.setText("pmf.xvg")
    adv_tab.run_wham()

    assert len(cmds) == 1
    wham_cmd = cmds[0][0][0]
    assert wham_cmd[0:2] == ["gmx", "wham"]
    assert "-it" in wham_cmd and "sim_pull*.xvg" in wham_cmd
    assert "-temp" in wham_cmd and "310.0" in wham_cmd
    assert "-o" in wham_cmd and "pmf.xvg" in wham_cmd
    assert cmds[0][1] == str(tmp_path)
    assert cmds[0][2] == "WHAM 自由能计算"

    # 3.2 测试元动力学
    cmds.clear()
    adv_tab.run_metadynamics()
    assert len(cmds) == 1
    meta_cmd = cmds[0][0][0]
    assert meta_cmd[0:2] == ["gmx", "mdrun"]
    assert "-plumed" in meta_cmd and "plumed.dat" in meta_cmd
    assert "-nt" in meta_cmd and "4" in meta_cmd
    assert cmds[0][2] == "元动力学模拟"


def test_plumed_meta_and_abf_generation(adv_tab, tmp_path):
    """测试 4: 验证 PLUMED 输入文件生成"""
    logs = []
    adv_tab.log_requested.connect(lambda m, l: logs.append((m, l)))

    adv_tab.meta_biasfactor.setValue(15.0)
    adv_tab.generate_plumed_meta()
    meta_file = tmp_path / "plumed.dat"
    assert meta_file.is_file()
    assert "METAD" in meta_file.read_text(encoding="utf-8")

    adv_tab.generate_plumed_abf()
    abf_file = tmp_path / "plumed_abf.dat"
    assert abf_file.is_file()
    assert "ABF" in abf_file.read_text(encoding="utf-8")


def test_advanced_config_roundtrip_and_running_state(adv_tab):
    """测试 5: 验证配置持久化与运行状态锁"""
    adv_tab.umb_pull_force.setValue(2500.0)
    adv_tab.wham_temp.setValue(325.0)
    adv_tab.meta_biasfactor.setValue(20.0)
    adv_tab.abf_nbins.setValue(200)

    cfg = adv_tab.get_config()
    assert cfg["umb_pull_force"] == 2500.0
    assert cfg["wham_temp"] == 325.0
    assert cfg["meta_biasfactor"] == 20.0
    assert cfg["abf_nbins"] == 200

    adv_tab.umb_pull_force.setValue(100.0)
    adv_tab.set_config(cfg)
    assert adv_tab.umb_pull_force.value() == 2500.0
    assert adv_tab.wham_temp.value() == 325.0
    assert adv_tab.meta_biasfactor.value() == 20.0
    assert adv_tab.abf_nbins.value() == 200

    # 运行状态切换
    adv_tab.set_running_state(True)
    assert not adv_tab.umb_run_btn.isEnabled()
    assert not adv_tab.wham_run_btn.isEnabled()
    assert not adv_tab.meta_run_btn.isEnabled()
    assert not adv_tab.meta_gen_btn.isEnabled()
    assert not adv_tab.abf_gen_btn.isEnabled()

    adv_tab.set_running_state(False)
    assert adv_tab.umb_run_btn.isEnabled()
    assert adv_tab.wham_run_btn.isEnabled()
    assert adv_tab.meta_run_btn.isEnabled()
    assert adv_tab.meta_gen_btn.isEnabled()
    assert adv_tab.abf_gen_btn.isEnabled()


def test_main_window_advanced_integration(qapp, tmp_path):
    """测试 6: 验证主窗口 GromacsGUI 挂载 AdvancedTab 后的属性兼容与旧方法派发无重发"""
    from gui.main_window import GromacsGUI

    with mock.patch("PyQt5.QtWidgets.QMessageBox.warning") as mock_warn, \
         mock.patch("PyQt5.QtWidgets.QMessageBox.information"), \
         mock.patch("PyQt5.QtWidgets.QMessageBox.critical") as mock_crit:

        win = GromacsGUI()
        win.setAttribute(Qt.WA_DontShowOnScreen, True)
        try:
            assert hasattr(win, "advanced_tab")
            assert win.umb_run_btn is win.advanced_tab.umb_run_btn
            assert win.wham_run_btn is win.advanced_tab.wham_run_btn
            assert win.meta_run_btn is win.advanced_tab.meta_run_btn
            assert win.meta_gen_btn is win.advanced_tab.meta_gen_btn
            assert win.abf_gen_btn is win.advanced_tab.abf_gen_btn

            # 运行状态切换联动
            assert win.wham_run_btn.isEnabled()
            win._set_running_state(True)
            qapp.processEvents()
            assert not win.wham_run_btn.isEnabled()

            win._set_running_state(False)
            qapp.processEvents()
            assert win.wham_run_btn.isEnabled()

            # Mock 调度器以隔离外部任务启动
            run_cmd_mock = mock.MagicMock()
            win.run_command = run_cmd_mock
            win.advanced_tab.run_requested.disconnect()
            win.advanced_tab.run_requested.connect(run_cmd_mock)

            win.path_edit.setText(str(tmp_path))

            # 模拟点击工具运行按钮
            win.wham_run_btn.click()
            qapp.processEvents()
            assert run_cmd_mock.call_count == 1

            # 直接调用旧公共方法 win.run_wham()
            run_cmd_mock.reset_mock()
            win.run_wham()
            qapp.processEvents()
            assert run_cmd_mock.call_count == 1

            # 直接调用旧公共方法 win.run_metadynamics()
            run_cmd_mock.reset_mock()
            win.run_metadynamics()
            qapp.processEvents()
            assert run_cmd_mock.call_count == 1

            assert mock_warn.call_count == 0
            assert mock_crit.call_count == 0

        finally:
            if getattr(win, "worker", None) is not None and win.worker.isRunning():
                win.worker.stop()
                win.worker.wait(1000)
            win.close()
            qapp.processEvents()
