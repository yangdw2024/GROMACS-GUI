# -*- coding: utf-8 -*-
"""
Part 2 结构处理独立组件 (StructureTab) 专项单元测试与回归测试
覆盖：
1. 默认输入文件配置与 7 个结构工具在 struc_widgets 中的映射；
2. build_structure_tool_command() 命令生成等价性（含力场注入 md_ff 与 ndx_struc 选项）；
3. 结构工具 run_structure_tool() 信号分发与空工作目录拦截；
4. get_config / set_config 配置序列化往返一致性；
5. set_running_state 运行状态锁对全部工具按钮的锁定与恢复；
6. 主窗口 GromacsGUI 挂载 StructureTab 后的全量别名兼容、运行状态锁定 (_set_running_state)、
   按钮点击以及旧接口 win.run_structure_tool() 单次派发防重发（全面 Mock 隔离真实命令与弹窗）。
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
def struc_tab(qapp, tmp_path):
    from gui.tabs.structure_tab import StructureTab
    tab = StructureTab(
        get_work_dir=lambda: str(tmp_path),
        get_gmx_path=lambda: "gmx",
        get_md_ff=lambda: "amber99sb-ildn"
    )
    return tab


def test_structure_tab_defaults(struc_tab):
    """测试 1: 验证结构输入文件与 7 种工具的默认值与部件存在性"""
    assert struc_tab.struc_input.text() == "protein.pdb"
    assert struc_tab.struc_index.text() == ""

    expected_tools = [
        "gmx make_ndx", "editconf", "pdb2gmx",
        "gmx genrestr", "genconf", "gmx check", "gmx dump"
    ]
    for k in expected_tools:
        assert k in struc_tab.struc_widgets, f"Missing tool in struc_widgets: {k}"
        w = struc_tab.struc_widgets[k]
        assert "out" in w and "opt" in w and "run_btn" in w
        assert w["run_btn"].isEnabled()

    assert "ndx_struc" in struc_tab.struc_widgets["gmx make_ndx"]
    assert "custom" in struc_tab.struc_widgets["gmx make_ndx"]


def test_structure_tools_command_dispatch(struc_tab, tmp_path):
    """测试 2: 验证各种结构工具命令生成与信号派发（含力场注入）"""
    cmds = []
    logs = []
    struc_tab.run_requested.connect(lambda c, w, s: cmds.append((c, w, s)))
    struc_tab.log_requested.connect(lambda m, l: logs.append((m, l)))

    # 2.1 测试 pdb2gmx 工具（注入力场参数）
    struc_tab.struc_widgets["pdb2gmx"]["out"].setText("my_prot.gro")
    struc_tab.struc_widgets["pdb2gmx"]["opt"].setText("-ignh")
    struc_tab.run_structure_tool("pdb2gmx")

    assert len(cmds) == 1
    cmd = cmds[0][0][0]
    assert cmd[0:2] == ["gmx", "pdb2gmx"]
    assert "-ff" in cmd and "amber99sb-ildn" in cmd
    assert "-o" in cmd and "my_prot.gro" in cmd
    assert "-ignh" in cmd
    assert cmds[0][1] == str(tmp_path)
    assert cmds[0][2] == "生成拓扑"

    # 2.2 测试 make_ndx 工具
    cmds.clear()
    struc_tab.struc_widgets["gmx make_ndx"]["opt"].setText("-select 'resname ALA'")
    struc_tab.run_structure_tool("gmx make_ndx")
    assert len(cmds) == 1
    assert "make_ndx" in cmds[0][0][0] or "select" in " ".join(cmds[0][0][0])


def test_structure_empty_work_dir_aborts(qapp):
    """测试 3: 验证空工作目录时不派发任务"""
    from gui.tabs.structure_tab import StructureTab
    tab = StructureTab(get_work_dir=lambda: "")
    cmds = []
    tab.run_requested.connect(lambda c, w, s: cmds.append((c, w, s)))
    tab.run_structure_tool("pdb2gmx")
    assert len(cmds) == 0


def test_structure_config_roundtrip_and_running_state(struc_tab):
    """测试 4: 验证配置持久化与运行状态锁定"""
    struc_tab.struc_input.setText("ligand.pdb")
    struc_tab.struc_index.setText("system.ndx")
    struc_tab.struc_widgets["editconf"]["out"].setText("box.gro")
    struc_tab.struc_widgets["editconf"]["opt"].setText("-bt cubic -d 1.2")

    cfg = struc_tab.get_config()
    assert cfg["struc_input"] == "ligand.pdb"
    assert cfg["struc_index"] == "system.ndx"
    assert cfg["tools"]["editconf"]["out"] == "box.gro"
    assert cfg["tools"]["editconf"]["opt"] == "-bt cubic -d 1.2"

    struc_tab.struc_input.setText("reset.pdb")
    struc_tab.set_config(cfg)
    assert struc_tab.struc_input.text() == "ligand.pdb"
    assert struc_tab.struc_widgets["editconf"]["out"].text() == "box.gro"

    # 测试运行状态锁定
    struc_tab.set_running_state(True)
    assert not struc_tab.struc_widgets["pdb2gmx"]["run_btn"].isEnabled()
    assert not struc_tab.struc_widgets["editconf"]["run_btn"].isEnabled()

    struc_tab.set_running_state(False)
    assert struc_tab.struc_widgets["pdb2gmx"]["run_btn"].isEnabled()
    assert struc_tab.struc_widgets["editconf"]["run_btn"].isEnabled()


def test_main_window_structure_integration(qapp, tmp_path):
    """测试 5: 验证主窗口 GromacsGUI 挂载 StructureTab 后的属性兼容与旧方法派发无重发"""
    from gui.main_window import GromacsGUI

    with mock.patch("PyQt5.QtWidgets.QMessageBox.warning") as mock_warn, \
         mock.patch("PyQt5.QtWidgets.QMessageBox.information"), \
         mock.patch("PyQt5.QtWidgets.QMessageBox.critical") as mock_crit:

        win = GromacsGUI()
        win.setAttribute(Qt.WA_DontShowOnScreen, True)
        try:
            assert hasattr(win, "struc_tab")
            assert win.struc_input is win.struc_tab.struc_input
            assert win.struc_index is win.struc_tab.struc_index
            assert win.struc_widgets is win.struc_tab.struc_widgets

            # 运行状态切换联动
            assert win.struc_widgets["pdb2gmx"]["run_btn"].isEnabled()
            win._set_running_state(True)
            qapp.processEvents()
            assert not win.struc_widgets["pdb2gmx"]["run_btn"].isEnabled()

            win._set_running_state(False)
            qapp.processEvents()
            assert win.struc_widgets["pdb2gmx"]["run_btn"].isEnabled()

            # Mock 调度器以隔离外部任务启动
            run_cmd_mock = mock.MagicMock()
            win.run_command = run_cmd_mock
            win.struc_tab.run_requested.disconnect()
            win.struc_tab.run_requested.connect(run_cmd_mock)

            win.path_edit.setText(str(tmp_path))
            win.struc_input.setText("test.pdb")

            # 模拟点击工具运行按钮
            win.struc_widgets["pdb2gmx"]["run_btn"].click()
            qapp.processEvents()
            assert run_cmd_mock.call_count == 1

            # 直接调用旧公共方法 win.run_structure_tool("pdb2gmx")
            run_cmd_mock.reset_mock()
            win.run_structure_tool("pdb2gmx")
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
