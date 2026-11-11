# -*- coding: utf-8 -*-
"""
Part 1 MD模拟全流程独立组件 (MdTab) 专项单元测试与回归测试
覆盖：
1. 全局参数、盒子设置、已有拓扑开关、蒸发配置、退火表格及 Step 1~12 卡片默认值；
2. 盒子类型与尺寸设置联动 (_on_box_type_changed, _get_box_params)；
3. 跳过步骤与已有拓扑切换状态机 (_on_use_existing_toggled, _update_skip_steps_visibility)；
4. 单步命令与一键完整MD流派发 (run_md_step, run_all_md) 信号等价性；
5. 第五阶段 SA 溶剂蒸发 (run_evap_step) 隔离文件构建、脚本写入与多轮循环命令上抛；
6. 第六阶段退火模拟 (run_anneal_step) MDP生成与 grompp/mdrun 命令派发；
7. generate_mdp_template MDP 模板生成；
8. 主窗口 GromacsGUI 挂载 MdTab 后的全量别名兼容、运行状态锁定 (_set_running_state)、
   以及旧接口单次派发防重发（全面 Mock 隔离真实外部 GROMACS 进程与弹窗）。
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
def md_tab(qapp, tmp_path):
    from gui.tabs.md_tab import MdTab
    fake_gmx = tmp_path / "gmx.exe"
    fake_gmx.write_text("dummy", encoding="utf-8")
    tab = MdTab(
        get_work_dir=lambda: str(tmp_path),
        get_gmx_path=lambda: str(fake_gmx),
        get_mdrun_extra=lambda is_em=False: ["-nt", "4", "-nb", "cpu"],
        get_sys_cpu_cores=lambda: 8,
        get_sys_gpu_info=lambda: {"available": False}
    )
    return tab


def test_md_tab_defaults_and_steps(md_tab):
    """测试 1: 验证全局参数、蒸发/退火控件默认值以及所有 12 个步骤卡片"""
    assert md_tab.md_ff.currentText() == "amber03"
    assert md_tab.md_water.currentText() == "spc"
    assert md_tab.md_temp.value() == 300.0
    assert md_tab.md_pressure.value() == 1.0
    assert md_tab.md_dt.value() == 0.002
    assert md_tab.md_nsteps.value() == 50000000
    assert md_tab.md_nt.value() == 6

    assert md_tab.evap_resname.text() == "CF"
    assert md_tab.evap_atoms_per_mol.value() == 5
    assert md_tab.evap_delete_num.value() == 100
    assert md_tab.evap_loops.value() == 500
    assert md_tab.evap_prefix.text() == "evap"

    assert md_tab.anneal_table.rowCount() == 7
    assert md_tab.anneal_prefix.text() == "anneal"

    expected_steps = [
        "Step 1", "Step 2", "Step 3", "Step 4",
        "Step 5", "Step 6", "Step 7", "Step 8",
        "Step 9", "Step 10", "Step 11", "Step 12"
    ]
    for k in expected_steps:
        assert k in md_tab.md_step_btns, f"Missing MD step card: {k}"
        assert md_tab.md_step_btns[k]["run_btn"].isEnabled()


def test_box_type_visibility_and_params(md_tab):
    """测试 2: 验证模拟盒子类型与尺寸切换逻辑及命令行参数组装"""
    # 默认 cubic + 按边距 (-d)
    params = md_tab._get_box_params()
    assert "-c" in params and "-d" in params and "cubic" in params

    # 切换至 rectangular + 按盒子边长 (-box)
    md_tab.md_box_type.setCurrentText("rectangular (长方体)")
    md_tab.md_box_size_mode.setCurrentText("按盒子边长 (-box)")
    md_tab.md_box_x.setValue(4.0)
    md_tab.md_box_y.setValue(5.0)
    md_tab.md_box_z.setValue(6.0)
    md_tab.md_princ.setChecked(True)

    params2 = md_tab._get_box_params()
    assert "-princ" in params2
    assert ["-box", "4.0", "5.0", "6.0"] == params2[1:5]


def test_use_existing_top_and_skip_steps(md_tab):
    """测试 3: 验证复用已有拓扑与跳过步骤的控件显隐状态机"""
    assert not md_tab.use_existing_top.isChecked()
    assert md_tab.step1_widget.isVisibleTo(md_tab)
    assert not md_tab.step1_existing.isVisibleTo(md_tab)

    md_tab.use_existing_top.setChecked(True)
    assert not md_tab.step1_widget.isVisibleTo(md_tab)
    assert md_tab.step1_existing.isVisibleTo(md_tab)
    assert md_tab.skip_editconf.isChecked()
    assert md_tab.skip_solvate.isChecked()
    assert md_tab.skip_genion.isChecked()
    assert not md_tab.md_step_btns["Step 2"]["group"].isVisibleTo(md_tab)


def test_run_md_step_and_run_all_md_dispatch(md_tab, tmp_path):
    """测试 4: 验证单步执行与完整 MD 流水线命令生成和 Qt 信号上抛"""
    cmds = []
    md_tab.run_requested.connect(lambda c, w, s: cmds.append((c, w, s)))

    # 4.1 Step 1 (pdb2gmx)
    md_tab.run_md_step("Step 1")
    assert len(cmds) == 1
    assert "pdb2gmx" in cmds[0][0][0]
    assert cmds[0][1] == str(tmp_path)

    # 4.2 run_all_md
    cmds.clear()
    md_tab.run_all_md()
    assert len(cmds) == 1
    assert cmds[0][2] == "完整MD流程"
    assert len(cmds[0][0]) > 3


def test_run_evap_step_command_building(md_tab, tmp_path):
    """测试 5: 验证 SA 溶剂蒸发步骤文件校验、删除脚本生成与循环命令构建"""
    # 构建隔离微型输入文件
    (tmp_path / "npt2.gro").write_text("Test\n1\n    1CF      C1    1   0.000   0.000   0.000\n1.0 1.0 1.0\n", encoding="utf-8")
    (tmp_path / "topol.top").write_text("[ system ]\nTest\n[ molecules ]\nCF 10\n", encoding="utf-8")
    (tmp_path / "npt-sa.mdp").write_text("integrator = md\n", encoding="utf-8")

    md_tab.evap_loops.setValue(2)
    md_tab.evap_delete_num.setValue(5)

    cmds = []
    md_tab.run_requested.connect(lambda c, w, s: cmds.append((c, w, s)))

    md_tab.run_evap_step()

    assert len(cmds) == 1
    assert cmds[0][2] == "溶剂/添加剂蒸发"
    # 2轮蒸发命令链，确认 delete_solvent.py 与逐轮继承命令生成正确
    assert len(cmds[0][0]) == 18
    assert (tmp_path / "delete_solvent.py").is_file()


def test_run_anneal_step_and_mdp_generation(md_tab, tmp_path):
    """测试 6: 验证退火模拟步骤生成退火 MDP 并派发 grompp + mdrun"""
    (tmp_path / "npt.gro").write_text("Test\n0\n1.0 1.0 1.0\n", encoding="utf-8")
    (tmp_path / "topol.top").write_text("[ system ]\nTest\n", encoding="utf-8")

    cmds = []
    md_tab.run_requested.connect(lambda c, w, s: cmds.append((c, w, s)))

    md_tab.run_anneal_step()
    assert len(cmds) == 1
    assert cmds[0][2] == "退火模拟"
    assert len(cmds[0][0]) == 2
    assert (tmp_path / "anneal.mdp").is_file()

    # 测试生成默认 MDP 模板
    md_tab.generate_mdp_template("em")
    assert (tmp_path / "em.mdp").is_file()


def test_main_window_md_tab_integration(qapp, tmp_path):
    """测试 7: 验证主窗口挂载 MdTab 后的全量别名兼容、运行锁与旧接口无重发"""
    from gui.main_window import GromacsGUI

    fake_gmx = tmp_path / "gmx.exe"
    fake_gmx.write_text("dummy", encoding="utf-8")

    with mock.patch("PyQt5.QtWidgets.QMessageBox.warning") as mock_warn, \
         mock.patch("PyQt5.QtWidgets.QMessageBox.information"), \
         mock.patch("PyQt5.QtWidgets.QMessageBox.critical") as mock_crit:

        win = GromacsGUI()
        win.setAttribute(Qt.WA_DontShowOnScreen, True)
        try:
            assert hasattr(win, "md_tab")
            for attr in [
                "md_ff", "md_water", "md_box_type", "md_step_btns",
                "evap_mode", "evap_resname", "anneal_table",
                "evap_run_btn", "anneal_run_btn", "se_run_btn"
            ]:
                assert hasattr(win, attr), f"Missing alias on GromacsGUI: {attr}"
                assert getattr(win, attr) is getattr(win.md_tab, attr)

            # 验证 _set_running_state 锁联动
            assert win.evap_run_btn.isEnabled()
            assert win.md_step_btns["Step 1"]["run_btn"].isEnabled()
            win._set_running_state(True)
            qapp.processEvents()
            assert not win.evap_run_btn.isEnabled()
            assert not win.anneal_run_btn.isEnabled()
            assert not win.md_step_btns["Step 1"]["run_btn"].isEnabled()

            win._set_running_state(False)
            qapp.processEvents()
            assert win.evap_run_btn.isEnabled()
            assert win.md_step_btns["Step 1"]["run_btn"].isEnabled()

            # Mock 任务调度器与 gmx_path
            run_cmd_mock = mock.MagicMock()
            win.run_command = run_cmd_mock
            win.md_tab.run_requested.disconnect()
            win.md_tab.run_requested.connect(run_cmd_mock)

            win.gmx_path = str(fake_gmx)
            win.path_edit.setText(str(tmp_path))

            # 直接调用旧接口 win.run_md_step("Step 1")
            win.run_md_step("Step 1")
            qapp.processEvents()
            assert run_cmd_mock.call_count == 1

            # 直接调用旧接口 win.run_all_md()
            run_cmd_mock.reset_mock()
            win.run_all_md()
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
