# -*- coding: utf-8 -*-
"""
Part 6 MMPBSA 自由能计算独立组件 (MmpbsaTab) 专项单元测试与回归测试
覆盖：
1. 全部输入控件默认值、数值范围与单位后缀；
2. build_mmpbsa_command() 命令生成等价性（含默认回退与自定义输入）；
3. 空工作目录安全拦截；
4. Qt 信号 run_requested 与 log_requested 分发；
5. get_config / set_config 配置读写往返一致性；
6. 主窗口 GromacsGUI 组合挂载后的全量属性别名兼容、_set_running_state 锁定、
   按钮点击以及旧公共接口 win.run_mmpbsa() 单次派发防重发（Mock 隔离真实计算）。
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
def mmpbsa_tab(qapp, tmp_path):
    from gui.tabs.mmpbsa_tab import MmpbsaTab
    tab = MmpbsaTab(get_work_dir=lambda: str(tmp_path))
    return tab


def test_mmpbsa_tab_defaults_and_ranges(mmpbsa_tab):
    """测试 1: 验证所有输入控件的默认值、范围与后缀与旧版严格一致"""
    assert mmpbsa_tab.mmpbsa_tpr.text() == "md.tpr"
    assert mmpbsa_tab.mmpbsa_xtc.text() == "md.xtc"
    assert mmpbsa_tab.mmpbsa_index.text() == "index.ndx"
    assert mmpbsa_tab.mmpbsa_top.text() == "topol.top"

    assert mmpbsa_tab.mmpbsa_start.minimum() == 0
    assert mmpbsa_tab.mmpbsa_start.maximum() == 1000000
    assert mmpbsa_tab.mmpbsa_start.value() == 0.0
    assert mmpbsa_tab.mmpbsa_start.decimals() == 1
    assert mmpbsa_tab.mmpbsa_start.suffix() == " ps"

    assert mmpbsa_tab.mmpbsa_end.minimum() == 0
    assert mmpbsa_tab.mmpbsa_end.maximum() == 1000000
    assert mmpbsa_tab.mmpbsa_end.value() == 0.0
    assert mmpbsa_tab.mmpbsa_end.suffix() == " ps (0=到结尾)"

    assert mmpbsa_tab.mmpbsa_interval.minimum() == 1
    assert mmpbsa_tab.mmpbsa_interval.maximum() == 100000
    assert mmpbsa_tab.mmpbsa_interval.value() == 1000.0
    assert mmpbsa_tab.mmpbsa_interval.decimals() == 0

    assert mmpbsa_tab.mmpbsa_nt.minimum() == 1
    assert mmpbsa_tab.mmpbsa_nt.maximum() == 64
    assert mmpbsa_tab.mmpbsa_nt.value() == 4

    formats = [mmpbsa_tab.mmpbsa_fmt.itemText(i) for i in range(mmpbsa_tab.mmpbsa_fmt.count())]
    assert formats == ["png", "pdf", "svg", "jpg", "tiff"]

    assert mmpbsa_tab.mmpbsa_width.minimum() == 1
    assert mmpbsa_tab.mmpbsa_width.maximum() == 50
    assert mmpbsa_tab.mmpbsa_width.value() == 8.0
    assert mmpbsa_tab.mmpbsa_width.suffix() == " inch"

    assert mmpbsa_tab.mmpbsa_height.minimum() == 1
    assert mmpbsa_tab.mmpbsa_height.maximum() == 50
    assert mmpbsa_tab.mmpbsa_height.value() == 6.0

    assert mmpbsa_tab.mmpbsa_run_btn.isEnabled()


def test_mmpbsa_command_equivalence_and_signal_dispatch(mmpbsa_tab, tmp_path):
    """测试 2: 验证命令组装与 build_mmpbsa_command 完全等价，并正确发出 Qt 信号"""
    from simulation.analysis import build_mmpbsa_command

    cmds = []
    logs = []
    mmpbsa_tab.run_requested.connect(lambda c, w, s: cmds.append((c, w, s)))
    mmpbsa_tab.log_requested.connect(lambda m, l: logs.append((m, l)))

    # 2.1 自定义输入文件
    mmpbsa_tab.mmpbsa_tpr.setText("prod.tpr")
    mmpbsa_tab.mmpbsa_xtc.setText("prod_fit.xtc")
    mmpbsa_tab.mmpbsa_index.setText("groups.ndx")
    mmpbsa_tab.mmpbsa_top.setText("complex.top")

    mmpbsa_tab.run_mmpbsa()

    expected_cmd, expected_step = build_mmpbsa_command({
        "tpr": "prod.tpr",
        "xtc": "prod_fit.xtc",
        "ndx": "groups.ndx",
        "top": "complex.top",
    })
    assert len(cmds) == 1
    assert cmds[0][0] == [expected_cmd]
    assert cmds[0][1] == str(tmp_path)
    assert cmds[0][2] == expected_step
    assert any("gmx_MMPBSA" in msg for msg, _ in logs)

    # 2.2 空白输入回退默认值
    cmds.clear()
    mmpbsa_tab.mmpbsa_tpr.setText("   ")
    mmpbsa_tab.mmpbsa_xtc.setText("")
    mmpbsa_tab.mmpbsa_index.setText("")
    mmpbsa_tab.mmpbsa_top.setText("")
    mmpbsa_tab.run_mmpbsa()

    default_cmd, _ = build_mmpbsa_command({
        "tpr": "md.tpr",
        "xtc": "md.xtc",
        "ndx": "index.ndx",
        "top": "topol.top",
    })
    assert len(cmds) == 1
    assert cmds[0][0] == [default_cmd]


def test_mmpbsa_empty_work_dir_aborts(qapp):
    """测试 3: 验证空工作目录时不派发任何任务或日志"""
    from gui.tabs.mmpbsa_tab import MmpbsaTab
    tab = MmpbsaTab(get_work_dir=lambda: "")
    cmds = []
    tab.run_requested.connect(lambda c, w, s: cmds.append((c, w, s)))
    tab.run_mmpbsa()
    assert len(cmds) == 0


def test_mmpbsa_config_roundtrip_and_running_state(mmpbsa_tab):
    """测试 4: 验证配置序列化接口及运行状态锁定开关"""
    mmpbsa_tab.mmpbsa_tpr.setText("custom.tpr")
    mmpbsa_tab.mmpbsa_start.setValue(100.5)
    mmpbsa_tab.mmpbsa_end.setValue(5000.0)
    mmpbsa_tab.mmpbsa_interval.setValue(250.0)
    mmpbsa_tab.mmpbsa_nt.setValue(16)
    mmpbsa_tab.mmpbsa_fmt.setCurrentText("svg")
    mmpbsa_tab.mmpbsa_width.setValue(10.5)
    mmpbsa_tab.mmpbsa_height.setValue(7.5)

    cfg = mmpbsa_tab.get_config()
    assert cfg["tpr"] == "custom.tpr"
    assert cfg["start"] == 100.5
    assert cfg["end"] == 5000.0
    assert cfg["interval"] == 250.0
    assert cfg["nt"] == 16
    assert cfg["fmt"] == "svg"
    assert cfg["width"] == 10.5
    assert cfg["height"] == 7.5

    mmpbsa_tab.mmpbsa_tpr.setText("reset.tpr")
    mmpbsa_tab.mmpbsa_nt.setValue(1)
    mmpbsa_tab.set_config(cfg)
    assert mmpbsa_tab.mmpbsa_tpr.text() == "custom.tpr"
    assert mmpbsa_tab.mmpbsa_nt.value() == 16
    assert mmpbsa_tab.mmpbsa_fmt.currentText() == "svg"

    mmpbsa_tab.set_running_state(True)
    assert not mmpbsa_tab.mmpbsa_run_btn.isEnabled()
    mmpbsa_tab.set_running_state(False)
    assert mmpbsa_tab.mmpbsa_run_btn.isEnabled()


def test_main_window_mmpbsa_integration_aliases_and_no_double_dispatch(qapp, tmp_path):
    """测试 5: 验证主窗口组合挂载 MmpbsaTab 后的别名、运行锁、旧接口 run_mmpbsa 单次派发及依赖隔离"""
    from gui.main_window import GromacsGUI
    from simulation.analysis import build_mmpbsa_command

    with mock.patch("PyQt5.QtWidgets.QMessageBox.warning") as mock_warn, \
         mock.patch("PyQt5.QtWidgets.QMessageBox.information"), \
         mock.patch("PyQt5.QtWidgets.QMessageBox.critical") as mock_crit:

        win = GromacsGUI()
        win.setAttribute(Qt.WA_DontShowOnScreen, True)
        try:
            # 1. 验证属性别名完整映射至 mmpbsa_tab 实例
            assert hasattr(win, "mmpbsa_tab")
            for attr in [
                "mmpbsa_tpr", "mmpbsa_xtc", "mmpbsa_index", "mmpbsa_top",
                "mmpbsa_start", "mmpbsa_end", "mmpbsa_interval", "mmpbsa_nt",
                "mmpbsa_fmt", "mmpbsa_width", "mmpbsa_height", "mmpbsa_run_btn"
            ]:
                assert hasattr(win, attr), f"Missing alias attribute on GromacsGUI: {attr}"
                assert getattr(win, attr) is getattr(win.mmpbsa_tab, attr)

            # 2. 验证 _set_running_state() 锁定与解锁运行按钮
            assert win.mmpbsa_run_btn.isEnabled()
            win._set_running_state(True)
            qapp.processEvents()
            assert not win.mmpbsa_run_btn.isEnabled()
            win._set_running_state(False)
            qapp.processEvents()
            assert win.mmpbsa_run_btn.isEnabled()

            # 3. Mock 统一任务派发器（不启动真实 GROMACS / GMXMMPBSA / QThread）
            run_cmd_mock = mock.MagicMock()
            win.run_command = run_cmd_mock
            win.mmpbsa_tab.run_requested.disconnect()
            win.mmpbsa_tab.run_requested.connect(run_cmd_mock)

            win.path_edit.setText(str(tmp_path))
            win.mmpbsa_tpr.setText("fclfcl.tpr")
            win.mmpbsa_xtc.setText("fclfcl.xtc")

            expected_cmd, expected_step = build_mmpbsa_command({
                "tpr": "fclfcl.tpr",
                "xtc": "fclfcl.xtc",
                "ndx": "index.ndx",
                "top": "topol.top",
            })

            # 4. 模拟点击按钮派发一次
            win.mmpbsa_run_btn.click()
            qapp.processEvents()
            assert run_cmd_mock.call_count == 1
            args1, _ = run_cmd_mock.call_args
            assert args1[0] == [expected_cmd]
            assert args1[1] == str(tmp_path)
            assert args1[2] == expected_step

            # 5. 直接调用旧公共方法 win.run_mmpbsa()，验证单次派发、无异常、无重复派发
            run_cmd_mock.reset_mock()
            win.run_mmpbsa()
            qapp.processEvents()
            assert run_cmd_mock.call_count == 1
            args2, _ = run_cmd_mock.call_args
            assert args2[0] == [expected_cmd]
            assert args2[1] == str(tmp_path)
            assert args2[2] == expected_step

            assert mock_warn.call_count == 0
            assert mock_crit.call_count == 0
        finally:
            if getattr(win, "worker", None) is not None and win.worker.isRunning():
                win.worker.stop()
                win.worker.wait(1000)
            win.close()
            qapp.processEvents()
