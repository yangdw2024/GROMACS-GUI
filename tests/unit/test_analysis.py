#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analysis.py 单元测试：验证三类 GROMACS 命令构建器输出与原 GUI 一致
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))

from simulation.analysis import (
    build_analysis_command, build_trajectory_tool_command,
    build_structure_tool_command, build_preprocessing_commands,
    build_mmpbsa_command
)


# =============================================================================
# 分析工具 build_analysis_command
# =============================================================================

def _base_files(tmp_path, ndx_exists=False):
    ndx = "index.ndx" if ndx_exists else ""
    if ndx_exists:
        (tmp_path / ndx).touch()
    return {
        "wd": str(tmp_path),
        "tpr": "md.tpr",
        "xtc": "md.xtc",
        "gro": "md.gro",
        "edr": "md.edr",
        "ndx": ndx,
    }


def _base_opts(**overrides):
    opts = {"b": 0, "e": 0, "dt": 0, "sel": "", "ref": "", "out": ""}
    opts.update(overrides)
    return opts


def test_energy_default_terms():
    files = {"wd": "/tmp", "tpr": "", "xtc": "", "gro": "", "edr": "md.edr", "ndx": ""}
    opts = _base_opts()
    cmd, step, stdin = build_analysis_command("energy", "gmx", files, opts)
    assert step == "能量分析"
    assert cmd[:3] == ["gmx", "energy", "-f"]
    assert cmd[-1] == "energy.xvg"
    assert stdin == "Potential\n0\n"


def test_energy_custom_terms():
    files = {"wd": "/tmp", "tpr": "", "xtc": "", "gro": "", "edr": "md.edr", "ndx": ""}
    opts = _base_opts(sel="Temperature Pressure")
    cmd, step, stdin = build_analysis_command("energy", "gmx", files, opts)
    assert stdin == "Temperature\nPressure\n0\n"


def test_rmsd_structure():
    files = {"wd": "/tmp", "tpr": "md.tpr", "xtc": "md.xtc", "gro": "", "edr": "", "ndx": ""}
    opts = _base_opts()
    cmd, step, stdin = build_analysis_command("rms", "gmx", files, opts)
    assert step == "RMSD 分析"
    assert cmd == ["gmx", "rms", "-s", "md.tpr", "-f", "md.xtc", "-o", "rmsd.xvg", "-tu", "ns"]
    assert stdin == "0\n0\n"


def test_rmsd_with_ref():
    files = {"wd": "/tmp", "tpr": "md.tpr", "xtc": "md.xtc", "gro": "", "edr": "", "ndx": ""}
    opts = _base_opts(ref="em.gro")
    cmd, step, stdin = build_analysis_command("rms", "gmx", files, opts)
    assert "-s" in cmd
    assert "em.gro" in cmd


def test_rdf_with_seltype():
    files = {"wd": "/tmp", "tpr": "md.tpr", "xtc": "md.xtc", "gro": "", "edr": "", "ndx": ""}
    # 原代码 rdf 解析用 elif 链，-seltype 会被 -sel 分支吞入 sel_group（保留原行为）
    opts = _base_opts(sel="-ref=Protein -seltype=mol_com")
    cmd, step, stdin = build_analysis_command("rdf", "gmx", files, opts)
    assert "-ref" in cmd and "Protein" in cmd
    assert "-sel" in cmd and "mol_com" in cmd


def test_rdf_sel_only():
    files = {"wd": "/tmp", "tpr": "md.tpr", "xtc": "md.xtc", "gro": "", "edr": "", "ndx": ""}
    opts = _base_opts(sel="-sel=SOL")
    cmd, step, stdin = build_analysis_command("rdf", "gmx", files, opts)
    assert "-sel" in cmd and "SOL" in cmd


def test_rdf_simple_sel():
    files = {"wd": "/tmp", "tpr": "md.tpr", "xtc": "md.xtc", "gro": "", "edr": "", "ndx": ""}
    opts = _base_opts(sel="SOL")
    cmd, step, stdin = build_analysis_command("rdf", "gmx", files, opts)
    assert "-sel" in cmd and "SOL" in cmd


def test_msd_has_trestart():
    files = {"wd": "/tmp", "tpr": "md.tpr", "xtc": "md.xtc", "gro": "", "edr": "", "ndx": ""}
    opts = _base_opts()
    cmd, step, stdin = build_analysis_command("msd", "gmx", files, opts)
    assert "-trestart" in cmd
    assert "10" in cmd


def test_distance_uses_oav():
    files = {"wd": "/tmp", "tpr": "md.tpr", "xtc": "md.xtc", "gro": "", "edr": "", "ndx": ""}
    opts = _base_opts()
    cmd, step, stdin = build_analysis_command("distance", "gmx", files, opts)
    assert "-oav" in cmd


def test_angle_uses_ov():
    files = {"wd": "/tmp", "tpr": "md.tpr", "xtc": "md.xtc", "gro": "", "edr": "", "ndx": ""}
    opts = _base_opts()
    cmd, step, stdin = build_analysis_command("angle", "gmx", files, opts)
    assert "-ov" in cmd


def test_eigenvalue_no_stdin():
    files = {"wd": "/tmp", "tpr": "md.tpr", "xtc": "md.xtc", "gro": "", "edr": "", "ndx": ""}
    opts = _base_opts()
    cmd, step, stdin = build_analysis_command("eigenvalue", "gmx", files, opts)
    assert stdin is None
    assert "covar.xvg" in cmd


def test_time_args_applied(tmp_path):
    files = _base_files(tmp_path, ndx_exists=True)
    opts = _base_opts(b=10, e=100, dt=2)
    cmd, step, stdin = build_analysis_command("gyrate", "gmx", files, opts)
    assert "-b" in cmd and "10" in cmd
    assert "-e" in cmd and "100" in cmd
    assert "-dt" in cmd and "2" in cmd
    assert "-n" in cmd and "index.ndx" in cmd


def test_unknown_analysis_returns_none():
    files = {"wd": "/tmp", "tpr": "", "xtc": "", "gro": "", "edr": "", "ndx": ""}
    opts = _base_opts()
    assert build_analysis_command("nonexistent", "gmx", files, opts) is None


# =============================================================================
# 轨迹工具 build_trajectory_tool_command
# =============================================================================

def test_trjconv_basic(tmp_path):
    files = {"wd": str(tmp_path), "inp": "md.xtc", "tpr": "md.tpr", "ndx": ""}
    cmd, step = build_trajectory_tool_command("trjconv", "gmx", files, "-pbc mol")
    assert step == "轨迹转换"
    assert cmd == ["gmx", "trjconv", "-s", "md.tpr", "-f", "md.xtc", "-o", "md_fit.xtc", "-pbc", "mol"]


def test_trjstrip_uses_trjconv(tmp_path):
    files = {"wd": str(tmp_path), "inp": "md.xtc", "tpr": "md.tpr", "ndx": ""}
    cmd, step = build_trajectory_tool_command("trjstrip", "gmx", files, "")
    assert "trjconv" in cmd
    assert "protein.xtc" in cmd


def test_trjconv_with_ndx(tmp_path):
    (tmp_path / "index.ndx").touch()
    files = {"wd": str(tmp_path), "inp": "md.xtc", "tpr": "md.tpr", "ndx": "index.ndx"}
    cmd, step = build_trajectory_tool_command("trjconv", "gmx", files, "")
    assert "-n" in cmd and "index.ndx" in cmd


def test_unknown_trajectory_returns_none(tmp_path):
    files = {"wd": str(tmp_path), "inp": "md.xtc", "tpr": "md.tpr", "ndx": ""}
    assert build_trajectory_tool_command("fake", "gmx", files, "") is None


# =============================================================================
# 结构工具 build_structure_tool_command
# =============================================================================

def test_pdb2gmx_uses_ff(tmp_path):
    files = {"wd": str(tmp_path), "inp": "protein.pdb", "ndx": ""}
    cmd, step = build_structure_tool_command(
        "pdb2gmx", "gmx", files, "", "", md_ff="amber99sb-ildn"
    )
    assert step == "生成拓扑"
    assert "-ff" in cmd and "amber99sb-ildn" in cmd
    assert "-p" in cmd and "topol.top" in cmd


def test_editconf_with_opt(tmp_path):
    files = {"wd": str(tmp_path), "inp": "protein.gro", "ndx": ""}
    cmd, step = build_structure_tool_command(
        "editconf", "gmx", files, "", "-d 1.0 -bt cubic"
    )
    assert step == "编辑结构"
    assert "-d" in cmd and "1.0" in cmd
    assert "-bt" in cmd and "cubic" in cmd


def test_make_ndx_with_ndx_inp(tmp_path):
    files = {"wd": str(tmp_path), "inp": "protein.pdb", "ndx": ""}
    cmd, step = build_structure_tool_command(
        "gmx make_ndx", "gmx", files, "", "", ndx_inp_val="conf.gro"
    )
    assert step == "创建索引"
    assert "-f" in cmd and "conf.gro" in cmd


def test_hbond_ndx(tmp_path):
    (tmp_path / "index.ndx").touch()
    files = {"wd": str(tmp_path), "inp": "md.xtc", "ndx": "index.ndx"}
    cmd, step = build_structure_tool_command("gmx hbond", "gmx", files, "", "")
    assert "-n" in cmd and "index.ndx" in cmd


def test_check_no_out(tmp_path):
    files = {"wd": str(tmp_path), "inp": "md.tpr", "ndx": ""}
    cmd, step = build_structure_tool_command("gmx check", "gmx", files, "", "")
    assert step == "结构验证"
    assert "-o" not in cmd


def test_unknown_structure_returns_none(tmp_path):
    files = {"wd": str(tmp_path), "inp": "protein.pdb", "ndx": ""}
    assert build_structure_tool_command("fake", "gmx", files, "", "") is None


# =============================================================================
# 预处理流水线 build_preprocessing_commands
# =============================================================================

def test_preprocessing_default_steps(tmp_path):
    params = {
        "wd": str(tmp_path), "xtc": "md.xtc", "tpr": "md.tpr", "ndx": "",
        "pbc_mode": "mol", "center_group": "Protein",
        "fit_mode": "rot+trans", "fit_ref": "0",
        "b": 0, "e": 0, "dt": 0, "output": "md_clean.xtc",
    }
    cmds = build_preprocessing_commands("gmx", params)
    assert len(cmds) == 3
    # Step 1: PBC + center
    assert cmds[0][0][0:3] == ["gmx", "trjconv", "-f"]
    assert "-center" in cmds[0][0]
    assert "-pbc" in cmds[0][0] and "mol" in cmds[0][0]
    # Step 2: fit
    assert "-fit" in cmds[1][0] and "rot+trans" in cmds[1][0]
    # Step 3: output
    assert cmds[2][0][-1] == "md_clean.xtc"


def test_preprocessing_no_fit(tmp_path):
    params = {
        "wd": str(tmp_path), "xtc": "md.xtc", "tpr": "md.tpr", "ndx": "",
        "pbc_mode": "nojump", "center_group": "",
        "fit_mode": "none", "fit_ref": "0",
        "b": 10, "e": 100, "dt": 2, "output": "out.xtc",
    }
    cmds = build_preprocessing_commands("gmx", params)
    # no fit → only 2 steps
    assert len(cmds) == 2
    final = cmds[1][0]
    assert "-b" in final and "10" in final
    assert "-e" in final and "100" in final
    assert "-dt" in final and "2" in final


def test_preprocessing_with_ndx(tmp_path):
    (tmp_path / "index.ndx").touch()
    params = {
        "wd": str(tmp_path), "xtc": "md.xtc", "tpr": "md.tpr", "ndx": "index.ndx",
        "pbc_mode": "mol", "center_group": "",
        "fit_mode": "none", "fit_ref": "0",
        "b": 0, "e": 0, "dt": 0, "output": "out.xtc",
    }
    cmds = build_preprocessing_commands("gmx", params)
    for cmd, _, _, _ in cmds:
        assert "-n" in cmd and "index.ndx" in cmd


# =============================================================================
# MMPBSA build_mmpbsa_command
# =============================================================================

def test_mmpbsa_command():
    files = {"tpr": "md.tpr", "xtc": "md.xtc", "ndx": "index.ndx", "top": "topol.top"}
    cmd, step = build_mmpbsa_command(files)
    assert step == "MMPBSA 结合自由能计算"
    assert cmd[0:3] == ["python", "-m", "GMXMMPBSA.app"]
    assert "-cs" in cmd and "md.tpr" in cmd
    assert "-ci" in cmd and "index.ndx" in cmd
    assert "-ct" in cmd and "md.xtc" in cmd
    assert "-cp" in cmd and "topol.top" in cmd
    assert "-nogui" in cmd
