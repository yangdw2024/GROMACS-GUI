#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
md_runner.py 单元测试：验证 MD 12 步命令构建与原 GUI 一致
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "source"))

from simulation.md_runner import (
    build_md_step_command, build_mdrun_command,
    build_grompp_command, build_editconf_command,
    build_annealing_commands, build_evap_loop_commands,
    build_full_md_pipeline,
    detect_existing_loops, check_evap_permissions, resolve_path,
    write_delete_script, setup_evap_work_files
)


def _base_state(**overrides):
    state = {
        "ff": "amber99sb-ildn", "water": "tip3p",
        "ion_conc": 0.15, "pdb": "protein.pdb",
        "use_existing_top": False, "se_gro": "", "se_top": "",
        "edits": [], "box_widgets": {}, "mdrun_widgets": {},
        "mdrun_extra": [], "wd": "/tmp",
    }
    state.update(overrides)
    return state


# =============================================================================
# Step 1: pdb2gmx
# =============================================================================

def test_step1_pdb2gmx():
    state = _base_state(edits=["", "protein.gro", "topol.top", "posre.itp"])
    result = build_md_step_command("Step 1", "gmx", state)
    assert result[0] == "single"
    cmd = result[1]
    assert cmd[:4] == ["gmx", "pdb2gmx", "-f", "protein.pdb"]
    assert "-ff" in cmd and "amber99sb-ildn" in cmd
    assert "-water" in cmd and "tip3p" in cmd
    assert "-ignh" in cmd


def test_step1_skip_existing(tmp_path):
    state = _base_state(
        use_existing_top=True, se_gro="input.gro", se_top="topol.top",
        wd=str(tmp_path)
    )
    result = build_md_step_command("Step 1", "gmx", state)
    assert result[0] == "skip"
    assert result[1] == "input.gro"
    assert result[2] == "topol.top"


# =============================================================================
# Step 2: editconf
# =============================================================================

def test_step2_editconf_cubic_box():
    box = {
        "box_type": "cubic", "size_mode": "边长",
        "center": True, "princ": False,
        "box_x": 0, "box_y": 0, "box_z": 0,
        "box_a": 5.0, "angle_alpha": 90, "angle_beta": 90, "angle_gamma": 90,
        "box_size": 1.0,
    }
    state = _base_state(edits=["protein.gro", "protein_box.gro"], box_widgets=box)
    result = build_md_step_command("Step 2", "gmx", state)
    assert result[0] == "single"
    cmd = result[1]
    assert "editconf" in cmd
    assert "-c" in cmd
    assert "-box" in cmd and "5.0" in cmd
    assert "-bt" in cmd and "cubic" in cmd


def test_step2_editconf_distance_mode():
    box = {
        "box_type": "dodecahedron", "size_mode": "距离",
        "center": False, "princ": False,
        "box_x": 0, "box_y": 0, "box_z": 0,
        "box_a": 0, "angle_alpha": 90, "angle_beta": 90, "angle_gamma": 90,
        "box_size": 1.5,
    }
    state = _base_state(edits=["protein.gro", "out.gro"], box_widgets=box)
    cmd = build_md_step_command("Step 2", "gmx", state)[1]
    assert "-bt" in cmd and "dodecahedron" in cmd
    assert "-d" in cmd and "1.5" in cmd


# =============================================================================
# Step 3: solvate
# =============================================================================

def test_step3_solvate():
    state = _base_state(edits=["protein_box.gro", "protein_solv.gro", "topol.top"])
    result = build_md_step_command("Step 3", "gmx", state)
    assert result[0] == "single"
    cmd = result[1]
    assert cmd == ["gmx", "solvate", "-cp", "protein_box.gro",
                   "-o", "protein_solv.gro", "-p", "topol.top"]


# =============================================================================
# Step 4: genion (multi-command)
# =============================================================================

def test_step4_genion_multi():
    state = _base_state(edits=["protein_solv.gro", "protein_ions.gro", "topol.top", "ions.mdp"])
    result = build_md_step_command("Step 4", "gmx", state)
    assert result[0] == "multi"
    cmds, step_name = result[1], result[2]
    assert step_name == "genion"
    assert len(cmds) == 2
    assert "grompp" in cmds[0]
    assert "genion" in cmds[1]
    assert "-conc" in cmds[1] and "0.15" in cmds[1]


# =============================================================================
# Step 5/7/9/11: grompp
# =============================================================================

def test_step5_grompp_em():
    state = _base_state(edits=["em.mdp", "", "em.tpr"])
    result = build_md_step_command("Step 5", "gmx", state)
    assert result[2] == "grompp (EM)"
    cmd = result[1]
    assert "grompp" in cmd
    assert "-f" in cmd and "em.mdp" in cmd
    assert "-r" not in cmd  # EM 不用 -r


def test_step7_grompp_nvt_with_r():
    state = _base_state(edits=["nvt.mdp", "", "nvt.tpr"])
    cmd = build_md_step_command("Step 7", "gmx", state)[1]
    assert "-r" in cmd  # NVT 用 -r


def test_grompp_helper():
    cmd = build_grompp_command("gmx", "md.mdp", "npt.gro", "md.tpr", "topol.top", with_r=True)
    assert cmd == ["gmx", "grompp", "-f", "md.mdp", "-c", "npt.gro",
                   "-r", "npt.gro", "-p", "topol.top", "-o", "md.tpr", "-maxwarn", "2"]


# =============================================================================
# Step 6/8/10/12: mdrun
# =============================================================================

def test_step6_mdrun_em():
    mdrun = {"custom_out_checked": False, "custom_out": "", "restart_checked": False}
    state = _base_state(edits=["em.tpr"], mdrun_widgets=mdrun, mdrun_extra=["-ntmpi", "1"])
    result = build_md_step_command("Step 6", "gmx", state)
    assert result[2] == "mdrun (EM)"
    cmd = result[1]
    assert "mdrun" in cmd
    assert "-v" in cmd  # EM 有 -v
    assert "-deffnm" in cmd and "em" in cmd


def test_step8_mdrun_nvt_no_v():
    mdrun = {"custom_out_checked": False, "custom_out": "", "restart_checked": False}
    state = _base_state(edits=["nvt.tpr"], mdrun_widgets=mdrun, mdrun_extra=[])
    cmd = build_md_step_command("Step 8", "gmx", state)[1]
    assert "-v" not in cmd  # NVT 无 -v


def test_mdrun_dup_extension_warning(tmp_path):
    mdrun = {"custom_out_checked": False, "custom_out": "", "restart_checked": False}
    cmd, dup_warning, restart_msg, deffnm = build_mdrun_command(
        "gmx", "em.tpr.tpr", mdrun, str(tmp_path), [], is_em=True
    )
    assert dup_warning is not None
    assert "em.tpr" in dup_warning
    assert deffnm == "em"


def test_mdrun_custom_output():
    mdrun = {"custom_out_checked": True, "custom_out": "my_run", "restart_checked": False}
    cmd, _, _, deffnm = build_mdrun_command("gmx", "md.tpr", mdrun, "/tmp", [])
    assert deffnm == "my_run"


def test_mdrun_restart_found(tmp_path):
    (tmp_path / "md.cpt").touch()
    mdrun = {"custom_out_checked": False, "custom_out": "", "restart_checked": True}
    cmd, _, restart_msg, deffnm = build_mdrun_command(
        "gmx", "md.tpr", mdrun, str(tmp_path), []
    )
    assert restart_msg == "found"
    assert "-cpi" in cmd and "md.cpt" in cmd
    assert "-append" in cmd


def test_mdrun_restart_not_found(tmp_path):
    mdrun = {"custom_out_checked": False, "custom_out": "", "restart_checked": True}
    cmd, _, restart_msg, deffnm = build_mdrun_command(
        "gmx", "md.tpr", mdrun, str(tmp_path), []
    )
    assert restart_msg == "not_found"
    assert "-cpi" not in cmd


# =============================================================================
# 边界
# =============================================================================

def test_unknown_step():
    state = _base_state()
    assert build_md_step_command("Step 99", "gmx", state)[0] == "unknown"


# =============================================================================
# 退火模拟
# =============================================================================

def test_annealing_commands(tmp_path):
    grompp, mdrun = build_annealing_commands(
        "gmx", "anneal", "input.gro", "topol.top",
        "anneal.mdp", ["-ntmpi", "1"], str(tmp_path)
    )
    assert grompp[0:3] == ["gmx", "grompp", "-f"]
    assert "-maxwarn" in grompp and "200" in grompp
    assert "mdrun" in mdrun
    assert "-deffnm" in mdrun


# =============================================================================
# 蒸发单轮
# =============================================================================

def test_evap_loop_solvent(tmp_path):
    cmds, restart = build_evap_loop_commands(
        loop_idx=3, prefix="evap", gmx="gmx", python_exe="python",
        delete_script="del.py", resname="SOL", delete_num=10,
        atoms_per_mol=3, delete_from="bottom", mdp_file="npt.mdp",
        work_gro="evap_work.gro", work_top="evap_work.top",
        current_gro="evap_current.gro", current_top="evap_current.top",
        mdrun_extra=["-ntmpi", "1"], wd=str(tmp_path),
        restart_check=False, start_loop=1, mode="solvent"
    )
    assert len(cmds) == 7
    assert "--solvent" in cmds[0] and "SOL" in cmds[0]
    assert "--delete-num" in cmds[0] and "10" in cmds[0]
    assert "--loop" in cmds[0] and "3" in cmds[0]
    assert "grompp" in cmds[3]
    assert "mdrun" in cmds[4]
    assert "evap_3" in " ".join(cmds[4])


def test_evap_loop_additive(tmp_path):
    cmds, _ = build_evap_loop_commands(
        loop_idx=0, prefix="evap", gmx="gmx", python_exe="python",
        delete_script="del.py", resname="NA", delete_num=0,
        atoms_per_mol=1, delete_from="", mdp_file="npt.mdp",
        work_gro="in.gro", work_top="top.top",
        current_gro="cur.gro", current_top="cur.top",
        mdrun_extra=[], wd=str(tmp_path),
        restart_check=False, start_loop=0, mode="additive"
    )
    assert "--additive" in cmds[0] and "NA" in cmds[0]
    assert "--delete-num" not in cmds[0]
    # additive 模式 deffnm 用 prefix，不带循环编号
    assert "evap.tpr" in cmds[3]
    assert "evap" in " ".join(cmds[4]) and "evap_0" not in " ".join(cmds[4])


def test_evap_loop_restart_found(tmp_path):
    (tmp_path / "evap_2.cpt").touch()
    cmds, restart = build_evap_loop_commands(
        loop_idx=3, prefix="evap", gmx="gmx", python_exe="python",
        delete_script="del.py", resname="SOL", delete_num=10,
        atoms_per_mol=3, delete_from="bottom", mdp_file="npt.mdp",
        work_gro="w.gro", work_top="w.top",
        current_gro="c.gro", current_top="c.top",
        mdrun_extra=[], wd=str(tmp_path),
        restart_check=True, start_loop=1, mode="solvent"
    )
    assert restart == "evap_2.cpt"
    assert "-cpi" in cmds[4] and "evap_2.cpt" in cmds[4]


# =============================================================================
# 完整 MD 流水线
# =============================================================================

def test_full_md_pipeline_default():
    state = {
        "ff": "amber99sb-ildn", "water": "tip3p", "ion_conc": 0.15,
        "pdb": "protein.pdb", "use_existing_top": False,
        "se_gro": "", "se_top": "",
        "skip_editconf": False, "skip_solvate": False, "skip_genion": False,
        "box_params": ["-bt", "cubic", "-d", "1.0"],
        "extra_mdrun": [], "extra_em": ["-ntmpi", "1"],
    }
    cmds = build_full_md_pipeline("gmx", state)
    # pdb2gmx, editconf, solvate, grompp(ions), genion, grompp(em), mdrun(em),
    # grompp(nvt), mdrun(nvt), grompp(npt), mdrun(npt), grompp(md), mdrun(md)
    assert len(cmds) == 13
    assert "pdb2gmx" in cmds[0]
    assert "editconf" in cmds[1]
    assert "solvate" in cmds[2]
    assert "genion" in cmds[4]
    assert "-conc" in cmds[4] and "0.150" in cmds[4]


def test_full_md_pipeline_use_existing():
    state = {
        "ff": "amber99sb-ildn", "water": "tip3p", "ion_conc": 0.15,
        "pdb": "protein.pdb", "use_existing_top": True,
        "se_gro": "input.gro", "se_top": "topol.top",
        "skip_editconf": True, "skip_solvate": True, "skip_genion": True,
        "box_params": [], "extra_mdrun": [], "extra_em": [],
    }
    cmds = build_full_md_pipeline("gmx", state)
    # 跳过 pdb2gmx/editconf/solvate/genion，直接 em→nvt→npt→md
    assert len(cmds) == 8
    assert cmds[0][0] == "gmx" and "grompp" in cmds[0]
    assert "em.tpr" in cmds[0]


# =============================================================================
# 蒸发步骤文件管理辅助函数
# =============================================================================

def test_detect_existing_loops_empty(tmp_path):
    start, mx = detect_existing_loops(str(tmp_path), "evap")
    assert start == 1
    assert mx is None


def test_detect_existing_loops_with_files(tmp_path):
    for i in [1, 2, 5]:
        (tmp_path / f"evap_{i}.gro").write_text("x")
    (tmp_path / "evap_other.gro").write_text("x")
    (tmp_path / "other_3.gro").write_text("x")
    start, mx = detect_existing_loops(str(tmp_path), "evap")
    assert start == 6
    assert mx == 5


def test_check_evap_permissions_ok(tmp_path):
    ok, err = check_evap_permissions(str(tmp_path))
    assert ok is True
    assert err is None


def test_check_evap_permissions_not_exists(tmp_path):
    ok, err = check_evap_permissions(str(tmp_path / "nonexistent"))
    assert ok is False
    assert err == "not_exists"


def test_resolve_path(tmp_path):
    wd = str(tmp_path)
    assert resolve_path(wd, "relative.gro") == os.path.join(wd, "relative.gro")
    abs_p = os.path.join(wd, "abs.gro")
    assert resolve_path(wd, abs_p) == abs_p


def test_write_delete_script_solvent(tmp_path):
    name = write_delete_script(str(tmp_path), 0, "SOL_SCRIPT", "ADD_SCRIPT")
    assert name == "delete_solvent.py"
    assert (tmp_path / "delete_solvent.py").read_text() == "SOL_SCRIPT"


def test_write_delete_script_additive(tmp_path):
    name = write_delete_script(str(tmp_path), 1, "SOL_SCRIPT", "ADD_SCRIPT")
    assert name == "delete_additive_all.py"
    assert (tmp_path / "delete_additive_all.py").read_text() == "ADD_SCRIPT"


def test_setup_evap_work_files_solvent_start1(tmp_path):
    wd = str(tmp_path)
    (tmp_path / "input.gro").write_text("gro")
    (tmp_path / "top.top").write_text("top")
    info = setup_evap_work_files(wd, "input.gro", "top.top", "evap", 1, 0)
    assert "error" not in info
    assert info["work_gro"] == "evap_work.gro"
    assert (tmp_path / "evap_original.gro").exists()
    assert (tmp_path / "evap_work.gro").read_text() == "gro"


def test_setup_evap_work_files_solvent_restart(tmp_path):
    wd = str(tmp_path)
    (tmp_path / "evap_2.gro").write_text("gro2")
    (tmp_path / "evap_current.top").write_text("top_curr")
    info = setup_evap_work_files(wd, "input.gro", "top.top", "evap", 3, 0)
    assert "error" not in info
    assert info["prev_top_basename"] == "evap_current.top"
    assert (tmp_path / "evap_work.gro").read_text() == "gro2"


def test_setup_evap_work_files_solvent_restart_missing_gro(tmp_path):
    wd = str(tmp_path)
    info = setup_evap_work_files(wd, "input.gro", "top.top", "evap", 3, 0)
    assert "error" in info
    assert info["error"].startswith("missing_prev_gro:")


def test_setup_evap_work_files_additive(tmp_path):
    wd = str(tmp_path)
    (tmp_path / "input.gro").write_text("gro")
    (tmp_path / "top.top").write_text("top")
    info = setup_evap_work_files(wd, "input.gro", "top.top", "evap", 0, 1)
    assert "error" not in info
    assert (tmp_path / "evap_original.gro").exists()
