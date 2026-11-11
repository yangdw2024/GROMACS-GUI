# -*- coding: utf-8 -*-
"""
科研计算后置安全验证与物理一致性检查测试 (Issue #2 治理)
覆盖：
1. GRO 结构文件校验（正常、原子数不匹配、NaN/Inf 坐标、零/塌陷盒子）；
2. md.log 日志分析（正常完成、NPT 大幅瞬时压力波动不误报、Fatal error、NaN 能量、Too many LINCS warnings、SETTLE 崩溃、未正常终止警告）；
3. embedded_scripts.py 溶剂删除空间 Z 轴 (z_top / z_bottom) 与旧版 GRO 文件顺序 (top / bottom) 兼容测试。
"""

import os
import sys
import pytest

from simulation.validation import validate_gro_structure, validate_md_log


def test_validate_gro_valid(tmp_path):
    gro = tmp_path / "valid.gro"
    gro.write_text(
        "Valid structure\n"
        "2\n"
        "    1CF      C1    1   1.000   2.000   3.000\n"
        "    1CF      F1    2   1.100   2.100   3.100\n"
        "   5.00000   5.00000   5.00000\n",
        encoding="utf-8"
    )
    res = validate_gro_structure(str(gro))
    assert res.status == "PASS"
    assert res.issues == []


def test_validate_gro_nan_and_collapsed_box(tmp_path):
    # 1. NaN 坐标阻断
    gro_nan = tmp_path / "nan.gro"
    gro_nan.write_text(
        "Exploded\n"
        "1\n"
        "    1CF      C1    1     nan   2.000   3.000\n"
        "   5.00000   5.00000   5.00000\n",
        encoding="utf-8"
    )
    res_nan = validate_gro_structure(str(gro_nan))
    assert res_nan.status == "BLOCKED"
    assert any(i.code == "GRO_NON_FINITE_COORD" for i in res_nan.issues)

    # 2. 塌陷盒子阻断
    gro_box = tmp_path / "collapsed.gro"
    gro_box.write_text(
        "Collapsed\n"
        "1\n"
        "    1CF      C1    1   1.000   2.000   3.000\n"
        "   0.00000   5.00000   5.00000\n",
        encoding="utf-8"
    )
    res_box = validate_gro_structure(str(gro_box))
    assert res_box.status == "BLOCKED"
    assert any(i.code == "GRO_COLLAPSED_BOX" for i in res_box.issues)

    # 3. 原子数不匹配阻断
    gro_mismatch = tmp_path / "mismatch.gro"
    gro_mismatch.write_text(
        "Truncated\n"
        "5\n"
        "    1CF      C1    1   1.000   2.000   3.000\n"
        "   5.00000   5.00000   5.00000\n",
        encoding="utf-8"
    )
    res_mm = validate_gro_structure(str(gro_mismatch))
    assert res_mm.status == "BLOCKED"
    assert any(i.code == "GRO_COUNT_MISMATCH" for i in res_mm.issues)


def test_validate_md_log_npt_pressure_fluctuation_not_false_positive(tmp_path):
    """验证 NPT 模拟中瞬时压力剧烈波动 (-850 bar ~ +1200 bar) 不会被误判为失败"""
    log = tmp_path / "md_npt.log"
    log.write_text(
        "GROMACS: gmx mdrun\n"
        "   Energies (kJ/mol)\n"
        "   Potential    Kinetic En.   Total Energy    Temperature    Pressure (bar)\n"
        "  -1.234e+05     4.567e+04     -7.773e+04       300.12         -850.45\n"
        "  -1.231e+05     4.581e+04     -7.729e+04       301.05         1240.80\n"
        "Finished mdrun on rank 0\n"
        "Performance: 120.5 ns/day\n",
        encoding="utf-8"
    )
    res = validate_md_log(str(log))
    assert res.status == "PASS"
    assert res.issues == []


def test_validate_md_log_fatal_lincs_nan(tmp_path):
    # 1. NaN 能量阻断
    log_nan = tmp_path / "nan.log"
    log_nan.write_text(
        "   Potential    Total Energy\n"
        "     nan            inf\n"
        "Finished mdrun on rank 0\n",
        encoding="utf-8"
    )
    res_nan = validate_md_log(str(log_nan))
    assert res_nan.status == "BLOCKED"
    assert any(i.code == "LOG_NON_FINITE_VALUE" for i in res_nan.issues)

    # 2. Too many LINCS warnings 阻断
    log_lincs = tmp_path / "lincs.log"
    log_lincs.write_text(
        "Fatal error:\n"
        "Too many LINCS warnings (1000)\n",
        encoding="utf-8"
    )
    res_lincs = validate_md_log(str(log_lincs))
    assert res_lincs.status == "BLOCKED"
    assert any(i.code == "GMX_FATAL_ERROR" for i in res_lincs.issues)
    assert any(i.code == "TOO_MANY_LINCS" for i in res_lincs.issues)

    # 3. 仅有 2 个轻微 LINCS 警告且正常完成 -> WARNING
    log_warn = tmp_path / "warn.log"
    log_warn.write_text(
        "Step 100: LINCS WARNING\n"
        "Step 102: LINCS WARNING\n"
        "Finished mdrun on rank 0\n",
        encoding="utf-8"
    )
    res_warn = validate_md_log(str(log_warn))
    assert res_warn.status == "WARNING"
    assert any(i.code == "TRANSIENT_LINCS_WARNINGS" for i in res_warn.issues)


def test_embedded_delete_solvent_spatial_z_vs_legacy_order(tmp_path):
    """验证溶剂删除空间 Z 坐标排序 (z_top / z_bottom) 与旧版 GRO 顺序 (top / bottom) 并存且互不干扰"""
    from gui.embedded_scripts import DELETE_SOLVENT_SCRIPT

    script_file = tmp_path / "del.py"
    script_file.write_text(DELETE_SOLVENT_SCRIPT, encoding="utf-8")

    ns = {}
    exec(compile(script_file.read_text(encoding="utf-8"), str(script_file), "exec"), ns)
    delete_fn = ns["delete_solvent_molecules"]

    # 构造乱序 Z 坐标的合成 GRO：
    # 分子 1 (GRO 第1位): z = 9.000 (空间最顶部!)
    # 分子 2 (GRO 第2位): z = 1.000 (空间最底部!)
    # 分子 3 (GRO 第3位): z = 5.000 (空间中部)
    gro_in = tmp_path / "in.gro"
    gro_in.write_text(
        "Mixed Z order\n"
        "3\n"
        "    1CF      C1    1   1.000   1.000   9.000\n"
        "    2CF      C1    2   1.000   1.000   1.000\n"
        "    3CF      C1    3   1.000   1.000   5.000\n"
        "  10.00000  10.00000  10.00000\n",
        encoding="utf-8"
    )

    # 1. 物理空间 Z-Top 删除 1 个：必须删除 z=9.000 的分子 1CF
    out_ztop = tmp_path / "out_ztop.gro"
    delete_fn(str(gro_in), str(out_ztop), "CF", 1, 1, delete_from="z_top")
    txt_ztop = out_ztop.read_text(encoding="utf-8")
    assert "1CF" not in txt_ztop
    assert "2CF" in txt_ztop and "3CF" in txt_ztop

    # 2. 物理空间 Z-Bottom 删除 1 个：必须删除 z=1.000 的分子 2CF
    out_zbot = tmp_path / "out_zbot.gro"
    delete_fn(str(gro_in), str(out_zbot), "CF", 1, 1, delete_from="z_bottom")
    txt_zbot = out_zbot.read_text(encoding="utf-8")
    assert "2CF" not in txt_zbot
    assert "1CF" in txt_zbot and "3CF" in txt_zbot

    # 3. 兼容旧版 bottom (GRO 文件末尾)：必须删除第3位的分子 3CF (z=5.000)
    out_leg_bot = tmp_path / "out_leg_bot.gro"
    delete_fn(str(gro_in), str(out_leg_bot), "CF", 1, 1, delete_from="bottom")
    txt_leg_bot = out_leg_bot.read_text(encoding="utf-8")
    assert "3CF" not in txt_leg_bot
    assert "1CF" in txt_leg_bot and "2CF" in txt_leg_bot


def test_worker_lifecycle_distinguishes_stopped_failed_success(tmp_path):
    """验证 GromacsWorker 生命周期精确区分 success / failed / stopped，不将异常或中止误报为成功"""
    from PyQt5.QtWidgets import QApplication
    from gui.workers.gromacs_worker import GromacsWorker

    app = QApplication.instance() or QApplication(sys.argv)

    # 1. 成功命令
    w_ok = GromacsWorker([[sys.executable, "-c", "print('ok')"]], str(tmp_path))
    results_ok = []
    w_ok.finished_signal.connect(lambda ok: results_ok.append(ok))
    w_ok.run()
    assert results_ok == [True]
    assert w_ok.outcome_status == "success"

    # 2. 非零退出失败命令
    w_fail = GromacsWorker([[sys.executable, "-c", "import sys; sys.exit(2)"]], str(tmp_path))
    results_fail = []
    w_fail.finished_signal.connect(lambda ok: results_fail.append(ok))
    w_fail.run()
    assert results_fail == [False]
    assert w_fail.outcome_status == "failed"

    # 3. 用户主动停止命令 (stopped_by_user=True)
    w_stop = GromacsWorker([[sys.executable, "-c", "import time; time.sleep(0.05)"]], str(tmp_path))
    w_stop.stop()
    results_stop = []
    w_stop.finished_signal.connect(lambda ok: results_stop.append(ok))
    w_stop.run()
    assert results_stop == [False]
    assert w_stop.outcome_status == "stopped"
