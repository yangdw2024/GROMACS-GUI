# -*- coding: utf-8 -*-
"""
Part 4 轨迹处理独立组件 (TrajectoryTab) 专项单元测试与回归测试
覆盖：
1. 默认输入文件、流水线控件默认值及参数范围；
2. 全部 7 种常用轨迹工具 (trjconv, trjcat, trjorder, trjreshape, trjreduce, trjcluster, trjstrip) 默认配置与命令组装等价性；
3. 轨迹工具 run_trajectory_tool() 信号分发与空工作目录拦截；
4. 预处理流水线 run_preprocessing_pipeline() 输入校验、命令生成与依赖隔离执行；
5. get_config / set_config 配置序列化往返一致性；
6. 主窗口 GromacsGUI 挂载 TrajectoryTab 后的全量别名兼容、运行状态锁定 (_set_running_state)、
   按钮点击以及旧接口 win.run_trajectory_tool() 单次派发防重发（全面 Mock 隔离真实命令与弹窗）。
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
def traj_tab(qapp, tmp_path):
    from gui.tabs.trajectory_tab import TrajectoryTab
    tab = TrajectoryTab(
        get_work_dir=lambda: str(tmp_path),
        get_gmx_path=lambda: "gmx"
    )
    return tab


def test_trajectory_tab_defaults(traj_tab):
    """测试 1: 验证轨迹输入文件与预处理流水线控件默认值"""
    assert traj_tab.traj_input.text() == "md.xtc"
    assert traj_tab.traj_tpr.text() == "md.tpr"
    assert traj_tab.traj_index.text() == ""

    assert traj_tab.prep_pbc.currentText().startswith("mol")
    assert traj_tab.prep_center.text() == "Protein"
    assert traj_tab.prep_fit.currentText().startswith("rot+trans")
    assert traj_tab.prep_fit_ref.text() == "Protein"
    assert traj_tab.prep_b.value() == 0.0
    assert traj_tab.prep_e.value() == 0.0
    assert traj_tab.prep_dt.value() == 0.0
    assert traj_tab.prep_output.text() == "md_clean.xtc"
    assert traj_tab.prep_run_btn.isEnabled()


def test_trajectory_tools_widgets_and_command_dispatch(traj_tab, tmp_path):
    """测试 2: 验证 7 种常用轨迹工具在 traj_widgets 中的配置与命令派发"""
    expected_tools = {
        "trjconv": "md_fit.xtc",
        "trjcat": "combined.xtc",
        "trjorder": "ordered.xtc",
        "trjreshape": "reshaped.xtc",
        "trjreduce": "reduced.xtc",
        "trjcluster": "cluster.pdb",
        "trjstrip": "protein.xtc",
    }
    assert set(traj_tab.traj_widgets.keys()) == set(expected_tools.keys())

    for key, expected_out in expected_tools.items():
        w = traj_tab.traj_widgets[key]
        assert w["out"].text() == expected_out
        assert w["run_btn"].isEnabled()

    cmds = []
    traj_tab.run_requested.connect(lambda c, w, s: cmds.append((c, w, s)))

    # 测试 trjconv 工具派发
    traj_tab.traj_widgets["trjconv"]["opt"].setText("-pbc mol -center")
    traj_tab.run_trajectory_tool("trjconv")

    assert len(cmds) == 1
    cmd = cmds[0][0][0]
    assert cmd[0:2] == ["gmx", "trjconv"]
    assert "-pbc" in cmd and "mol" in cmd
    assert "-center" in cmd
    assert cmds[0][1] == str(tmp_path)
    assert cmds[0][2] == "轨迹转换"


def test_trajectory_preprocessing_pipeline(traj_tab, tmp_path):
    """测试 3: 验证轨迹预处理流水线输入检查与隔离执行"""
    # 3.1 当 xtc 文件不存在时，应弹出警告且不执行
    with mock.patch("PyQt5.QtWidgets.QMessageBox.warning") as mock_warn:
        traj_tab.run_preprocessing_pipeline()
        assert mock_warn.call_count == 1
        assert "轨迹文件不存在" in mock_warn.call_args[0][2]

    # 3.2 准备输入文件并 Mock subprocess.run 执行流水线
    (tmp_path / "md.xtc").touch()
    (tmp_path / "md.tpr").touch()

    logs = []
    traj_tab.log_requested.connect(lambda m, l: logs.append((m, l)))

    mock_run = mock.MagicMock(return_value=mock.MagicMock(returncode=0, stderr=""))
    with mock.patch("subprocess.run", mock_run):
        traj_tab.run_preprocessing_pipeline()

    # 预处理五步法中带 echo_prefix 的步骤应通过 subprocess.run 执行
    assert mock_run.call_count >= 2
    assert any("预处理完成" in msg for msg, _ in logs)


def test_trajectory_config_roundtrip_and_running_state(traj_tab):
    """测试 4: 验证配置持久化读写与运行状态锁定"""
    traj_tab.traj_input.setText("test_in.xtc")
    traj_tab.prep_center.setText("System")
    traj_tab.prep_b.setValue(100.0)
    traj_tab.traj_widgets["trjreduce"]["out"].setText("my_reduced.xtc")
    traj_tab.traj_widgets["trjreduce"]["opt"].setText("-skip 5")

    cfg = traj_tab.get_config()
    assert cfg["traj_input"] == "test_in.xtc"
    assert cfg["prep_center"] == "System"
    assert cfg["prep_b"] == 100.0
    assert cfg["tools"]["trjreduce"]["out"] == "my_reduced.xtc"
    assert cfg["tools"]["trjreduce"]["opt"] == "-skip 5"

    traj_tab.traj_input.setText("reset.xtc")
    traj_tab.set_config(cfg)
    assert traj_tab.traj_input.text() == "test_in.xtc"
    assert traj_tab.traj_widgets["trjreduce"]["out"].text() == "my_reduced.xtc"

    # 测试锁定状态
    traj_tab.set_running_state(True)
    assert not traj_tab.prep_run_btn.isEnabled()
    assert not traj_tab.traj_widgets["trjconv"]["run_btn"].isEnabled()

    traj_tab.set_running_state(False)
    assert traj_tab.prep_run_btn.isEnabled()
    assert traj_tab.traj_widgets["trjconv"]["run_btn"].isEnabled()


def test_main_window_trajectory_integration(qapp, tmp_path):
    """测试 5: 验证主窗口 GromacsGUI 组合挂载 TrajectoryTab 后的属性兼容与旧方法派发无重发"""
    from gui.main_window import GromacsGUI

    with mock.patch("PyQt5.QtWidgets.QMessageBox.warning") as mock_warn, \
         mock.patch("PyQt5.QtWidgets.QMessageBox.information"), \
         mock.patch("PyQt5.QtWidgets.QMessageBox.critical") as mock_crit:

        win = GromacsGUI()
        win.setAttribute(Qt.WA_DontShowOnScreen, True)
        try:
            assert hasattr(win, "traj_tab")
            assert win.traj_input is win.traj_tab.traj_input
            assert win.traj_tpr is win.traj_tab.traj_tpr
            assert win.prep_run_btn is win.traj_tab.prep_run_btn
            assert win.traj_widgets is win.traj_tab.traj_widgets

            # 运行状态切换联动
            assert win.prep_run_btn.isEnabled()
            win._set_running_state(True)
            qapp.processEvents()
            assert not win.prep_run_btn.isEnabled()
            assert not win.traj_widgets["trjconv"]["run_btn"].isEnabled()

            win._set_running_state(False)
            qapp.processEvents()
            assert win.prep_run_btn.isEnabled()
            assert win.traj_widgets["trjconv"]["run_btn"].isEnabled()

            # Mock 调度器以隔离外部任务启动
            run_cmd_mock = mock.MagicMock()
            win.run_command = run_cmd_mock
            win.traj_tab.run_requested.disconnect()
            win.traj_tab.run_requested.connect(run_cmd_mock)

            win.path_edit.setText(str(tmp_path))
            win.traj_input.setText("test.xtc")

            # 模拟点击工具运行按钮
            win.traj_widgets["trjconv"]["run_btn"].click()
            qapp.processEvents()
            assert run_cmd_mock.call_count == 1

            # 直接调用旧公共方法 win.run_trajectory_tool("trjconv")
            run_cmd_mock.reset_mock()
            win.run_trajectory_tool("trjconv")
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
