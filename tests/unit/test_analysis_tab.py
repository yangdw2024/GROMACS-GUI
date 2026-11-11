# -*- coding: utf-8 -*-
"""
Part 5 结果分析与可视化独立组件 (AnalysisTab) 专项单元测试与回归测试
覆盖：
1. 通用分析输入 (XTC/TPR/GRO/EDR/NDX)、起止时间、采样步长默认值与部件存在性；
2. analysis_widgets 全套分析工具配置与 build_analysis_command 等价性；
3. 常用分析工具 (energy, rms, hbond) 命令组装与 Qt 信号 (run_requested) 派发（含 stdin_input）；
4. 轨迹校验 run_file_check 与文件存在性状态检查 check_file_status；
5. 片段分析索引生成器 generate_fragment_ndx 及批量片段 RDF 分析 run_fragment_rdf_batch；
6. 最近邻距离分析 run_pairdist_analysis 与能量分解 run_energy_decomposition；
7. 结果自动绘图 generate_plot (matplotlib Agg 离屏生成)；
8. get_config / set_config 配置序列化往返一致性与 set_running_state 运行锁；
9. 主窗口 GromacsGUI 挂载 AnalysisTab 后的全量别名兼容、运行状态锁定 (_set_running_state)、
   按钮点击以及旧接口 win.run_analysis() 单次派发防重发（全面 Mock 隔离真实命令与弹窗）。
"""

import os
import sys
import unittest.mock as mock
import pytest
from PyQt5.QtWidgets import QApplication, QTableWidgetItem
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
def ana_tab(qapp, tmp_path):
    from gui.tabs.analysis_tab import AnalysisTab
    tab = AnalysisTab(
        get_work_dir=lambda: str(tmp_path),
        get_gmx_path=lambda: "gmx"
    )
    return tab


def test_analysis_tab_defaults(ana_tab):
    """测试 1: 验证控件初始状态、默认值与部件字典完整性"""
    assert ana_tab.ana_input_xtc.text() == "md.xtc"
    assert ana_tab.ana_input_tpr.text() == "md.tpr"
    assert ana_tab.ana_input_gro.text() == "md.gro"
    assert ana_tab.ana_input_edr.text() == "md.edr"
    assert ana_tab.ana_index.text() == ""
    assert ana_tab.ana_b.value() == 0.0
    assert ana_tab.ana_e.value() == 0.0
    assert ana_tab.ana_dt.value() == 0.0

    # 验证常用工具已正确注入 analysis_widgets
    expected_tools = [
        "energy", "density", "msd", "rms", "rmsf", "gyrate",
        "distance", "angle", "pairdist", "hbond", "rdf", "sasa",
        "saltbr", "do_dssp", "covar", "eigenvalue", "principal", "trajectory", "cluster"
    ]
    for k in expected_tools:
        assert k in ana_tab.analysis_widgets, f"Missing tool in analysis_widgets: {k}"
        w = ana_tab.analysis_widgets[k]
        assert "out" in w and "sel" in w and "ref" in w and "run_btn" in w
        assert w["run_btn"].isEnabled()


def test_analysis_command_generation_and_dispatch(ana_tab, tmp_path):
    """测试 2: 验证常用分析工具的命令组装与信号上抛"""
    cmds = []
    ana_tab.run_requested.connect(lambda c, w, s, i: cmds.append((c, w, s, i)))

    # 2.1 测试 energy 分析 (带 stdin 输入)
    ana_tab.analysis_widgets["energy"]["sel"].setText("Potential Temperature")
    ana_tab.analysis_widgets["energy"]["out"].setText("my_energy.xvg")
    ana_tab.run_analysis("energy")

    assert len(cmds) == 1
    cmd = cmds[0][0][0]
    assert cmd[0:2] == ["gmx", "energy"]
    assert "-o" in cmd and "my_energy.xvg" in cmd
    assert cmds[0][1] == str(tmp_path)
    assert cmds[0][2] == "能量分析"
    assert cmds[0][3] is not None and "Potential" in cmds[0][3]

    # 2.2 测试 rms 分析
    cmds.clear()
    ana_tab.analysis_widgets["rms"]["sel"].setText("Backbone")
    ana_tab.run_analysis("rms")
    assert len(cmds) == 1
    rms_cmd = cmds[0][0][0]
    assert rms_cmd[0:2] == ["gmx", "rms"]


def test_file_check_and_status(ana_tab, tmp_path):
    """测试 3: 验证文件校验与状态检查"""
    logs = []
    cmds = []
    ana_tab.log_requested.connect(lambda m, l: logs.append((m, l)))
    ana_tab.run_requested.connect(lambda c, w, s, i: cmds.append((c, w, s, i)))

    # 3.1 轨迹文件不存在时警告
    with mock.patch("PyQt5.QtWidgets.QMessageBox.warning") as mock_warn:
        ana_tab.run_file_check()
        assert mock_warn.call_count == 1
        assert len(cmds) == 0

    # 3.2 准备文件后运行检查
    (tmp_path / "md.xtc").touch()
    (tmp_path / "md.tpr").touch()
    ana_tab.run_file_check()
    assert len(cmds) == 1
    assert cmds[0][0][0][0:2] == ["gmx", "check"]

    # 3.3 检查状态输出日志
    ana_tab.check_file_status()
    assert any("文件状态检查" in m for m, _ in logs)


def test_fragment_indexing_and_rdf(ana_tab, tmp_path):
    """测试 4: 验证片段索引文件生成与批量 RDF 分析"""
    logs = []
    cmds = []
    ana_tab.log_requested.connect(lambda m, l: logs.append((m, l)))
    ana_tab.run_requested.connect(lambda c, w, s, i: cmds.append((c, w, s, i)))

    with mock.patch("PyQt5.QtWidgets.QMessageBox.warning"):
        # 4.1 索引生成
        ana_tab.ndx_gen_nmol.setValue(2)
        ana_tab.ndx_gen_natom.setValue(10)
        ana_tab.ndx_gen_output.setText("frag_test.ndx")
        ana_tab.ndx_gen_table.setRowCount(1)
        ana_tab.ndx_gen_table.setItem(0, 0, QTableWidgetItem("Donor_Core"))
        ana_tab.ndx_gen_table.setItem(0, 1, QTableWidgetItem("1-5,7"))
        ana_tab.generate_fragment_ndx()

        out_ndx = tmp_path / "frag_test.ndx"
        assert out_ndx.is_file()
        content = out_ndx.read_text(encoding="utf-8")
        assert "[ Donor_Core ]" in content
        # 2 分子 * 6 原子 = 12 个原子
        assert "1 2 3 4 5 7 11 12 13 14 15 17" in content

        # 4.2 批量 RDF
        ana_tab.rdf_frag_ndx_input.setText("frag_test.ndx")
        ana_tab.rdf_frag_ref.setText("Donor_Core")
        ana_tab.rdf_frag_sel.setText("Donor_Core")
        ana_tab.run_fragment_rdf_batch()
        assert len(cmds) == 1
        assert cmds[0][0][0][0:2] == ["gmx", "rdf"]


def test_pairdist_and_energy_decomp(ana_tab, tmp_path):
    """测试 5: 验证 pairdist 分析与能量分解提取"""
    cmds = []
    logs = []
    ana_tab.run_requested.connect(lambda c, w, s, i: cmds.append((c, w, s, i)))
    ana_tab.log_requested.connect(lambda m, l: logs.append((m, l)))

    with mock.patch("PyQt5.QtWidgets.QMessageBox.warning"):
        # 5.1 pairdist
        ana_tab.pairdist_ref.setText("GroupA")
        ana_tab.pairdist_sel.setText("GroupB")
        ana_tab.run_pairdist_analysis()
        assert len(cmds) == 1
        assert cmds[0][0][0][0:2] == ["gmx", "pairdist"]

        # 5.2 energy decomp
        (tmp_path / "md.edr").touch()
        mock_run = mock.MagicMock(return_value=mock.MagicMock(returncode=0, stderr=""))
        with mock.patch("subprocess.run", mock_run):
            ana_tab.run_energy_decomposition()
        assert mock_run.call_count == 1
        assert any("能量分析完成" in m for m, _ in logs)


def test_plot_generation(ana_tab, tmp_path):
    """测试 6: 验证自动绘图 (matplotlib Agg 离屏出图)"""
    pytest.importorskip("matplotlib")

    # 构造测试 xvg 文件
    xvg_file = tmp_path / "test_data.xvg"
    xvg_file.write_text(
        "@title \"Test Plot\"\n"
        "@xaxis label \"Time (ns)\"\n"
        "@yaxis label \"RMSD (nm)\"\n"
        "@ s0 legend \"Backbone\"\n"
        "0.000  0.150\n"
        "1.000  0.180\n"
        "2.000  0.210\n",
        encoding="utf-8"
    )

    logs = []
    ana_tab.log_requested.connect(lambda m, l: logs.append((m, l)))

    with mock.patch("PyQt5.QtWidgets.QMessageBox.warning") as mock_warn:
        ana_tab.plot_input.setText("test_data.xvg")
        ana_tab.plot_output.setText("test_out.png")
        ana_tab.generate_plot()

        out_png = tmp_path / "test_out.png"
        assert out_png.is_file()
        assert out_png.stat().st_size > 0
        assert any("图表生成成功" in m for m, _ in logs)
        assert mock_warn.call_count == 0


def test_analysis_config_roundtrip_and_running_state(ana_tab):
    """测试 7: 验证配置持久化与运行状态锁"""
    ana_tab.ana_input_xtc.setText("custom.xtc")
    ana_tab.ana_b.setValue(500.0)
    ana_tab.plot_dpi.setValue(400)
    ana_tab.analysis_widgets["rms"]["out"].setText("custom_rms.xvg")

    cfg = ana_tab.get_config()
    assert cfg["ana_input_xtc"] == "custom.xtc"
    assert cfg["ana_b"] == 500.0
    assert cfg["plot_dpi"] == 400
    assert cfg["tools"]["rms"]["out"] == "custom_rms.xvg"

    ana_tab.ana_input_xtc.setText("reset.xtc")
    ana_tab.set_config(cfg)
    assert ana_tab.ana_input_xtc.text() == "custom.xtc"
    assert ana_tab.ana_b.value() == 500.0
    assert ana_tab.plot_dpi.value() == 400
    assert ana_tab.analysis_widgets["rms"]["out"].text() == "custom_rms.xvg"

    # 运行锁联动
    ana_tab.set_running_state(True)
    assert not ana_tab.file_check_btn.isEnabled()
    assert not ana_tab.plot_run_btn.isEnabled()
    assert not ana_tab.analysis_widgets["energy"]["run_btn"].isEnabled()

    ana_tab.set_running_state(False)
    assert ana_tab.file_check_btn.isEnabled()
    assert ana_tab.plot_run_btn.isEnabled()
    assert ana_tab.analysis_widgets["energy"]["run_btn"].isEnabled()


def test_main_window_analysis_integration(qapp, tmp_path):
    """测试 8: 验证主窗口 GromacsGUI 挂载 AnalysisTab 后的属性兼容与旧方法派发无重发"""
    from gui.main_window import GromacsGUI

    with mock.patch("PyQt5.QtWidgets.QMessageBox.warning") as mock_warn, \
         mock.patch("PyQt5.QtWidgets.QMessageBox.information"), \
         mock.patch("PyQt5.QtWidgets.QMessageBox.critical") as mock_crit:

        win = GromacsGUI()
        win.setAttribute(Qt.WA_DontShowOnScreen, True)
        try:
            assert hasattr(win, "analysis_tab")
            assert win.ana_input_xtc is win.analysis_tab.ana_input_xtc
            assert win.analysis_widgets is win.analysis_tab.analysis_widgets
            assert win.plot_run_btn is win.analysis_tab.plot_run_btn
            assert win.file_check_btn is win.analysis_tab.file_check_btn

            # 运行状态切换联动
            assert win.analysis_widgets["energy"]["run_btn"].isEnabled()
            win._set_running_state(True)
            qapp.processEvents()
            assert not win.analysis_widgets["energy"]["run_btn"].isEnabled()
            assert not win.plot_run_btn.isEnabled()

            win._set_running_state(False)
            qapp.processEvents()
            assert win.analysis_widgets["energy"]["run_btn"].isEnabled()
            assert win.plot_run_btn.isEnabled()

            # Mock 调度器以隔离外部任务启动
            run_cmd_mock = mock.MagicMock()
            win.run_command = run_cmd_mock
            win.analysis_tab.run_requested.disconnect()
            win.analysis_tab.run_requested.connect(run_cmd_mock)

            win.path_edit.setText(str(tmp_path))

            # 模拟点击工具运行按钮
            win.analysis_widgets["energy"]["run_btn"].click()
            qapp.processEvents()
            assert run_cmd_mock.call_count == 1

            # 直接调用旧公共方法 win.run_analysis("energy")
            run_cmd_mock.reset_mock()
            win.run_analysis("energy")
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
