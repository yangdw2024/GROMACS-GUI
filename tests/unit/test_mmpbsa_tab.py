# -*- coding: utf-8 -*-
"""
Part 6 MMPBSA 自由能计算独立组件 (MmpbsaTab) 与 Issue #5 科学增强专项测试
覆盖：
1. 全部输入控件默认值、数值范围与单位后缀；
2. 真实 NDX 索引组解析 (parse_ndx_groups) 与不存在组拦截；
3. 采样时间 (ps) 到 1-based 帧索引严格换算 (convert_ps_to_mmpbsa_frames) 与异常边界拦截；
4. mmpbsa.in 输入文件生成、-cg 动态组别绑定与 MPI 并行命令构建 (build_mmpbsa_command)；
5. 外部 gmx_MMPBSA 环境检测缺失安全阻断；
6. 空工作目录安全拦截、get_config / set_config 配置读写往返一致性 (含新字段)；
7. 主窗口 GromacsGUI 组合挂载后的全量别名兼容、_set_running_state 锁定、
   按钮点击以及旧接口 win.run_mmpbsa() 单次派发防重发（全面 Mock 隔离真实计算）。
"""

import json
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
    tab = MmpbsaTab(
        get_work_dir=lambda: str(tmp_path),
        detect_runner=lambda: (["gmx_MMPBSA"], "mocked gmx_MMPBSA")
    )
    return tab


def test_mmpbsa_tab_defaults_and_ranges(mmpbsa_tab):
    """测试 1: 验证所有输入控件的默认值、范围与后缀"""
    assert mmpbsa_tab.mmpbsa_tpr.text() == "md.tpr"
    assert mmpbsa_tab.mmpbsa_xtc.text() == "md.xtc"
    assert mmpbsa_tab.mmpbsa_index.text() == "index.ndx"
    assert mmpbsa_tab.mmpbsa_top.text() == "topol.top"
    assert mmpbsa_tab.mmpbsa_rec_group.text() == "1"
    assert mmpbsa_tab.mmpbsa_lig_group.text() == "13"
    assert mmpbsa_tab.mmpbsa_traj_dt.value() == 10.0

    assert mmpbsa_tab.mmpbsa_start.minimum() == 0
    assert mmpbsa_tab.mmpbsa_start.maximum() == 1000000
    assert mmpbsa_tab.mmpbsa_start.value() == 0.0
    assert mmpbsa_tab.mmpbsa_start.decimals() == 1
    assert mmpbsa_tab.mmpbsa_start.suffix() == " ps"

    assert mmpbsa_tab.mmpbsa_end.value() == 0.0
    assert mmpbsa_tab.mmpbsa_interval.value() == 1000.0
    assert mmpbsa_tab.mmpbsa_nt.minimum() == 1
    assert mmpbsa_tab.mmpbsa_nt.maximum() == 64
    assert mmpbsa_tab.mmpbsa_nt.value() == 4

    formats = [mmpbsa_tab.mmpbsa_fmt.itemText(i) for i in range(mmpbsa_tab.mmpbsa_fmt.count())]
    assert formats == ["png", "pdf", "svg", "jpg", "tiff"]
    assert mmpbsa_tab.mmpbsa_width.value() == 8.0
    assert mmpbsa_tab.mmpbsa_height.value() == 6.0
    assert mmpbsa_tab.mmpbsa_run_btn.isEnabled()


def test_mmpbsa_time_to_frame_and_ndx_parsing(tmp_path):
    """测试 2: 验证 ps -> 帧号换算公式及真实 NDX 索引组解析"""
    from simulation.analysis import convert_ps_to_mmpbsa_frames, parse_ndx_groups, build_mmpbsa_input_file

    # 2.1 ps 时间不能直接等同于帧索引
    sf, ef, iv = convert_ps_to_mmpbsa_frames(1000.0, 5000.0, 100.0, traj_dt_ps=10.0)
    assert sf == 101
    assert ef == 501
    assert iv == 10

    # end=0 表示到末尾 (None)
    sf2, ef2, iv2 = convert_ps_to_mmpbsa_frames(0.0, 0.0, 200.0, traj_dt_ps=20.0)
    assert sf2 == 1
    assert ef2 is None
    assert iv2 == 10

    with pytest.raises(ValueError):
        convert_ps_to_mmpbsa_frames(500.0, 100.0, 10.0, traj_dt_ps=10.0)

    # 2.2 解析真实 NDX 索引组
    ndx = tmp_path / "opv.ndx"
    ndx.write_text("[ System ]\n1 2\n[ DON ]\n1\n[ ACC ]\n2\n", encoding="utf-8")
    groups = parse_ndx_groups(str(ndx))
    assert groups == [(0, "System"), (1, "DON"), (2, "ACC")]

    # 2.3 mmpbsa.in 生成
    inp = build_mmpbsa_input_file({"startframe": 101, "endframe": 501, "interval": 10})
    assert "startframe=101" in inp
    assert "endframe=501" in inp
    assert "interval=10" in inp


def test_mmpbsa_full_parameter_command_and_signal_dispatch(mmpbsa_tab, tmp_path):
    """测试 3: 验证全参数生效 (mmpbsa.in, 动态组别, MPI, 绘图规格文件) 与信号派发"""
    # 构造有机光伏体系 NDX（只有 0, 1, 2 组，不存在组 13！）
    ndx_file = tmp_path / "groups.ndx"
    ndx_file.write_text("[ System ]\n1 2 3\n[ DON ]\n1 2\n[ ACC ]\n3\n", encoding="utf-8")

    cmds = []
    logs = []
    mmpbsa_tab.run_requested.connect(lambda c, w, s: cmds.append((c, w, s)))
    mmpbsa_tab.log_requested.connect(lambda m, l: logs.append((m, l)))

    mmpbsa_tab.mmpbsa_tpr.setText("prod.tpr")
    mmpbsa_tab.mmpbsa_xtc.setText("prod_fit.xtc")
    mmpbsa_tab.mmpbsa_index.setText("groups.ndx")
    mmpbsa_tab.mmpbsa_top.setText("complex.top")
    mmpbsa_tab.mmpbsa_rec_group.setText("1")
    mmpbsa_tab.mmpbsa_lig_group.setText("2")
    mmpbsa_tab.mmpbsa_start.setValue(1000.0)
    mmpbsa_tab.mmpbsa_end.setValue(5000.0)
    mmpbsa_tab.mmpbsa_interval.setValue(100.0)
    mmpbsa_tab.mmpbsa_traj_dt.setValue(10.0)
    mmpbsa_tab.mmpbsa_nt.setValue(8)
    mmpbsa_tab.mmpbsa_fmt.setCurrentText("svg")
    mmpbsa_tab.mmpbsa_width.setValue(10.0)

    with mock.patch("shutil.which", side_effect=lambda name: "/usr/bin/mpirun" if name == "mpirun" else None):
        mmpbsa_tab.run_mmpbsa()

    assert len(cmds) == 1
    cmd = cmds[0][0][0]
    # 校验 MPI 并行参数与自定义组别 -cg 1 2 生效
    assert cmd[0:3] == ["/usr/bin/mpirun", "-np", "8"]
    assert "-i" in cmd and "mmpbsa.in" in cmd
    cg_idx = cmd.index("-cg")
    assert cmd[cg_idx + 1:cg_idx + 3] == ["1", "2"]

    # 校验 mmpbsa.in 与 plot spec 已写入磁盘
    in_text = (tmp_path / "mmpbsa.in").read_text(encoding="utf-8")
    assert "startframe=101" in in_text and "endframe=501" in in_text and "interval=10" in in_text

    plot_spec = json.loads((tmp_path / "mmpbsa_plot_spec.json").read_text(encoding="utf-8"))
    assert plot_spec["format"] == "svg" and plot_spec["width_inch"] == 10.0


def test_mmpbsa_blocks_invalid_ndx_group_and_missing_env(qapp, tmp_path):
    """测试 4: 验证不存在的 NDX 组别与缺失 gmx_MMPBSA 环境安全拦截"""
    from gui.tabs.mmpbsa_tab import MmpbsaTab

    # 4.1 缺失环境拦截
    tab_no_env = MmpbsaTab(
        get_work_dir=lambda: str(tmp_path),
        detect_runner=lambda: (None, "未检测到 gmx_MMPBSA")
    )
    cmds, logs = [], []
    tab_no_env.run_requested.connect(lambda c, w, s: cmds.append(c))
    tab_no_env.log_requested.connect(lambda m, l: logs.append((m, l)))
    tab_no_env.run_mmpbsa()
    assert len(cmds) == 0
    assert any(lvl == "error" and "gmx_MMPBSA" in msg for msg, lvl in logs)

    # 4.2 NDX 中无组 13 时阻断硬编码错误
    (tmp_path / "index.ndx").write_text("[ System ]\n1\n[ DON ]\n1\n", encoding="utf-8")
    tab_bad_grp = MmpbsaTab(
        get_work_dir=lambda: str(tmp_path),
        detect_runner=lambda: (["gmx_MMPBSA"], "ok")
    )
    cmds2, logs2 = [], []
    tab_bad_grp.run_requested.connect(lambda c, w, s: cmds2.append(c))
    tab_bad_grp.log_requested.connect(lambda m, l: logs2.append((m, l)))
    tab_bad_grp.run_mmpbsa()  # 默认 lig=13，不存在于仅有 0,1 的 index.ndx 中
    assert len(cmds2) == 0
    assert any(lvl == "error" and "13" in msg for msg, lvl in logs2)


def test_mmpbsa_empty_work_dir_aborts(qapp):
    """测试 5: 验证空工作目录时不派发任何任务或日志"""
    from gui.tabs.mmpbsa_tab import MmpbsaTab
    tab = MmpbsaTab(get_work_dir=lambda: "")
    cmds = []
    tab.run_requested.connect(lambda c, w, s: cmds.append((c, w, s)))
    tab.run_mmpbsa()
    assert len(cmds) == 0


def test_mmpbsa_config_roundtrip_and_running_state(mmpbsa_tab):
    """测试 6: 验证配置序列化接口（含新字段）及运行状态锁定开关"""
    mmpbsa_tab.mmpbsa_tpr.setText("custom.tpr")
    mmpbsa_tab.mmpbsa_rec_group.setText("2")
    mmpbsa_tab.mmpbsa_lig_group.setText("4")
    mmpbsa_tab.mmpbsa_traj_dt.setValue(25.0)
    mmpbsa_tab.mmpbsa_start.setValue(100.5)
    mmpbsa_tab.mmpbsa_end.setValue(5000.0)
    mmpbsa_tab.mmpbsa_interval.setValue(250.0)
    mmpbsa_tab.mmpbsa_nt.setValue(16)
    mmpbsa_tab.mmpbsa_fmt.setCurrentText("svg")
    mmpbsa_tab.mmpbsa_width.setValue(10.5)
    mmpbsa_tab.mmpbsa_height.setValue(7.5)

    cfg = mmpbsa_tab.get_config()
    assert cfg["rec_group"] == "2"
    assert cfg["lig_group"] == "4"
    assert cfg["traj_dt"] == 25.0

    mmpbsa_tab.mmpbsa_rec_group.setText("0")
    mmpbsa_tab.set_config(cfg)
    assert mmpbsa_tab.mmpbsa_rec_group.text() == "2"
    assert mmpbsa_tab.mmpbsa_lig_group.text() == "4"
    assert mmpbsa_tab.mmpbsa_traj_dt.value() == 25.0

    mmpbsa_tab.set_running_state(True)
    assert not mmpbsa_tab.mmpbsa_run_btn.isEnabled()
    mmpbsa_tab.set_running_state(False)
    assert mmpbsa_tab.mmpbsa_run_btn.isEnabled()


def test_main_window_mmpbsa_integration_aliases_and_no_double_dispatch(qapp, tmp_path):
    """测试 7: 验证主窗口挂载 MmpbsaTab 后的别名、运行锁、旧接口单次派发及依赖隔离"""
    from gui.main_window import GromacsGUI

    with mock.patch("PyQt5.QtWidgets.QMessageBox.warning") as mock_warn, \
         mock.patch("PyQt5.QtWidgets.QMessageBox.information"), \
         mock.patch("PyQt5.QtWidgets.QMessageBox.critical") as mock_crit:

        win = GromacsGUI()
        win.setAttribute(Qt.WA_DontShowOnScreen, True)
        try:
            assert hasattr(win, "mmpbsa_tab")
            for attr in [
                "mmpbsa_tpr", "mmpbsa_xtc", "mmpbsa_index", "mmpbsa_top",
                "mmpbsa_rec_group", "mmpbsa_lig_group", "mmpbsa_traj_dt",
                "mmpbsa_start", "mmpbsa_end", "mmpbsa_interval", "mmpbsa_nt",
                "mmpbsa_fmt", "mmpbsa_width", "mmpbsa_height", "mmpbsa_run_btn"
            ]:
                assert hasattr(win, attr), f"Missing alias attribute on GromacsGUI: {attr}"
                assert getattr(win, attr) is getattr(win.mmpbsa_tab, attr)

            assert win.mmpbsa_run_btn.isEnabled()
            win._set_running_state(True)
            qapp.processEvents()
            assert not win.mmpbsa_run_btn.isEnabled()
            win._set_running_state(False)
            qapp.processEvents()
            assert win.mmpbsa_run_btn.isEnabled()

            run_cmd_mock = mock.MagicMock()
            win.run_command = run_cmd_mock
            win.mmpbsa_tab.run_requested.disconnect()
            win.mmpbsa_tab.run_requested.connect(run_cmd_mock)
            win.mmpbsa_tab._detect_runner = lambda: (["gmx_MMPBSA"], "mocked")

            win.path_edit.setText(str(tmp_path))
            win.mmpbsa_tpr.setText("fclfcl.tpr")

            win.mmpbsa_run_btn.click()
            qapp.processEvents()
            assert run_cmd_mock.call_count == 1

            run_cmd_mock.reset_mock()
            win.run_mmpbsa()
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
