#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GROMACS 命令构建器：分析、轨迹处理、结构处理工具

所有函数均为纯函数，输入参数（不含 Qt 引用），返回命令列表与步骤名。
零逻辑改动搬运自原 GromacsGUI 的 run_analysis / run_trajectory_tool / run_structure_tool。
"""
import importlib.util
import os
import re
import shutil
import sys
from typing import List, Optional, Tuple


# =============================================================================
# Part 5: 结果分析命令（run_analysis）
# =============================================================================

def build_analysis_command(
    key: str, gmx: str,
    files: dict, opts: dict
) -> Optional[Tuple[List[str], str, Optional[str]]]:
    """构建 GROMACS 分析工具的命令行参数

    files: {tpr, xtc, gro, edr, ndx, wd}
    opts:  {b, e, dt, sel, ref, out}

    返回 (cmd, step_name, stdin_in)；未知 key 返回 None。
    """
    wd = files["wd"]
    tpr = files["tpr"]
    xtc = files["xtc"]
    edr = files["edr"]
    ndx = files["ndx"]
    b = opts["b"]
    e = opts["e"]
    dt_val = opts["dt"]
    sel = opts["sel"]
    ref = opts["ref"]
    out = opts["out"]

    stdin_in = None

    def add_time_args(cmd):
        if b > 0:
            cmd += ["-b", str(b)]
        if e > 0:
            cmd += ["-e", str(e)]
        if dt_val > 0:
            cmd += ["-dt", str(dt_val)]
        if ndx and os.path.exists(os.path.join(wd, ndx)):
            cmd += ["-n", ndx]
        return cmd

    cmd = [gmx]
    step_name = ""

    if key == "energy":
        out = out or "energy.xvg"
        step_name = "能量分析"
        energy_terms = sel.strip() if sel.strip() else "Potential"
        term_list = [t.strip() for t in energy_terms.split() if t.strip()]
        stdin_in = "\n".join(term_list) + "\n0\n"
        cmd = add_time_args([gmx, "energy", "-f", edr, "-o", out])

    elif key == "rms":
        out = out or "rmsd.xvg"
        step_name = "RMSD 分析"
        ref_struct = ref or tpr
        cmd_base = [gmx, "rms", "-s", ref_struct, "-f", xtc, "-o", out, "-tu", "ns"]
        if sel and sel.startswith("-fit "):
            fit_group = sel.replace("-fit ", "").strip()
            cmd_base += ["-fit", "rot+trans"]
            if ndx:
                cmd_base += ["-n", ndx]
        cmd = add_time_args(cmd_base)
        stdin_in = "0\n0\n"

    elif key == "rmsf":
        out = out or "rmsf.xvg"
        step_name = "RMSF 分析"
        cmd_base = [gmx, "rmsf", "-s", tpr, "-f", xtc, "-o", out, "-res"]
        if sel:
            cmd_base += ["-sel", sel]
        cmd = add_time_args(cmd_base)
        stdin_in = "0\n"

    elif key == "gyrate":
        out = out or "gyrate.xvg"
        step_name = "回旋半径"
        cmd_base = [gmx, "gyrate", "-s", tpr, "-f", xtc, "-o", out]
        if sel:
            cmd_base += ["-sel", sel]
        cmd = add_time_args(cmd_base)
        stdin_in = "0\n"

    elif key == "hbond":
        out = out or "hbond.xvg"
        step_name = "氢键分析"
        cmd = add_time_args([gmx, "hbond", "-s", tpr, "-f", xtc, "-num", out])
        stdin_in = "1\n1\n"

    elif key == "rdf":
        out = out or "rdf.xvg"
        step_name = "径向分布函数"
        cmd_base = [gmx, "rdf", "-s", tpr, "-f", xtc, "-o", out]
        if sel:
            ref_group = None
            sel_group = None
            seltype_val = None
            bin_val = None
            for part in sel.split():
                if part.startswith("-ref=") or part.startswith("-ref"):
                    ref_group = part.split("=", 1)[1] if "=" in part else None
                elif part.startswith("-sel=") or part.startswith("-sel"):
                    sel_group = part.split("=", 1)[1] if "=" in part else None
                elif part.startswith("-seltype=") or part.startswith("-seltype"):
                    seltype_val = part.split("=", 1)[1] if "=" in part else None
                elif part.startswith("-bin=") or part.startswith("-bin"):
                    bin_val = part.split("=", 1)[1] if "=" in part else None
            if not ref_group and not sel_group and not sel.startswith("-"):
                sel_group = sel
            if ref_group:
                cmd_base += ["-ref", ref_group]
            if sel_group:
                cmd_base += ["-sel", sel_group]
            if seltype_val:
                cmd_base += ["-seltype", seltype_val]
            if bin_val:
                cmd_base += ["-bin", bin_val]
        if ref and not any(x in sel for x in ["-ref", "-sel"]):
            cmd_base += ["-ref", ref]
        cmd = add_time_args(cmd_base)
        stdin_in = "1\n1\n"

    elif key == "sasa":
        out = out or "sasa.xvg"
        step_name = "溶剂可及表面积"
        cmd = add_time_args([gmx, "sasa", "-s", tpr, "-f", xtc, "-o", out])
        stdin_in = "0\n"

    elif key == "density":
        out = out or "density.xvg"
        step_name = "密度分析"
        cmd_base = [gmx, "density", "-s", tpr, "-f", xtc, "-o", out]
        if sel:
            direction = None
            slices = None
            for part in sel.split():
                if part.startswith("-d=") or part.startswith("-d"):
                    direction = part.split("=", 1)[1] if "=" in part else None
                elif part.startswith("-sl=") or part.startswith("-sl"):
                    slices = part.split("=", 1)[1] if "=" in part else None
            if direction:
                cmd_base += ["-d", direction]
            if slices:
                cmd_base += ["-sl", slices]
        cmd = add_time_args(cmd_base)
        stdin_in = "0\n"

    elif key == "do_dssp":
        out = out or "dssp.xpm"
        step_name = "二级结构分析"
        cmd = add_time_args([gmx, "do_dssp", "-s", tpr, "-f", xtc, "-xpm", out, "-sc", "scount.xvg"])
        stdin_in = "0\n"

    elif key == "msd":
        out = out or "msd.xvg"
        step_name = "均方位移"
        cmd_base = [gmx, "msd", "-s", tpr, "-f", xtc, "-o", out, "-tu", "ns"]
        if sel:
            cmd_base += ["-sel", sel]
        if ref and "molecules" in ref.lower():
            cmd_base += ["-molecules"]
        cmd_base += ["-trestart", "10"]
        cmd = add_time_args(cmd_base)
        stdin_in = "0\n"

    elif key == "distance":
        out = out or "distance.xvg"
        step_name = "距离分析"
        cmd = add_time_args([gmx, "distance", "-s", tpr, "-f", xtc, "-oav", out])
        stdin_in = "0\n0\n"

    elif key == "angle":
        out = out or "angle.xvg"
        step_name = "角度分析"
        cmd = add_time_args([gmx, "angle", "-s", tpr, "-f", xtc, "-ov", out])
        stdin_in = "0\n0\n0\n"

    elif key == "covar":
        out = out or "covar.xvg"
        step_name = "协方差矩阵"
        cmd = add_time_args([gmx, "covar", "-s", tpr, "-f", xtc, "-o", out])
        stdin_in = "0\n"

    elif key == "eigenvalue":
        out = out or "eigenval.xvg"
        step_name = "特征值分解"
        cmd = add_time_args([gmx, "eigenvalue", "-f", "covar.xvg", "-o", out])

    elif key == "principal":
        out = out or "pc.xvg"
        step_name = "主成分分析"
        cmd = add_time_args([gmx, "principal", "-s", tpr, "-f", xtc, "-o", out])
        stdin_in = "0\n"

    elif key == "trajectory":
        out = out or "proj.xvg"
        step_name = "轨迹投影"
        cmd = add_time_args([gmx, "trajectory", "-s", tpr, "-f", xtc, "-o", out])

    elif key == "cluster":
        out = out or "cluster.xpm"
        step_name = "聚类分析"
        cmd_base = [gmx, "cluster", "-s", tpr, "-f", xtc, "-o", out]
        if sel:
            method = None
            cutoff = None
            for part in sel.split():
                if part.startswith("-method=") or part.startswith("-method"):
                    method = part.split("=", 1)[1] if "=" in part else None
                elif part.startswith("-cutoff=") or part.startswith("-cutoff"):
                    cutoff = part.split("=", 1)[1] if "=" in part else None
            if method:
                cmd_base += ["-method", method]
            if cutoff:
                cmd_base += ["-cutoff", cutoff]
        cmd = add_time_args(cmd_base)
        stdin_in = "0\n"

    elif key == "pairdist":
        out = out or "pairdist.xvg"
        step_name = "配对距离分布"
        cmd_base = [gmx, "pairdist", "-s", tpr, "-f", xtc, "-o", out]
        if sel:
            ref_group = None
            sel_group = None
            pd_type = None
            for part in sel.split():
                if part.startswith("-ref=") or part.startswith("-ref"):
                    ref_group = part.split("=", 1)[1] if "=" in part else None
                elif part.startswith("-sel=") or part.startswith("-sel"):
                    sel_group = part.split("=", 1)[1] if "=" in part else None
                elif part.startswith("-type=") or part.startswith("-type"):
                    pd_type = part.split("=", 1)[1] if "=" in part else None
            if not ref_group and not sel_group and not sel.startswith("-"):
                sel_group = sel
            if ref_group:
                cmd_base += ["-ref", ref_group]
            if sel_group:
                cmd_base += ["-sel", sel_group]
            if pd_type:
                cmd_base += ["-type", pd_type]
        cmd = add_time_args(cmd_base)
        stdin_in = "1\n1\n"

    elif key == "saltbr":
        out = out or "saltbr.xvg"
        step_name = "盐桥分析"
        cmd = add_time_args([gmx, "saltbr", "-s", tpr, "-f", xtc, "-o", out])

    else:
        return None

    return cmd, step_name, stdin_in


# =============================================================================
# Part 4: 轨迹处理工具命令（run_trajectory_tool）
# =============================================================================

def build_trajectory_tool_command(
    key: str, gmx: str,
    files: dict, opt: str
) -> Optional[Tuple[List[str], str]]:
    """构建 GROMACS 轨迹处理工具的命令行参数

    files: {inp, tpr, ndx, wd}
    opt:   额外选项字符串（如 "-pbc mol"）
    返回 (cmd, step_name)；未知 key 返回 None。
    """
    wd = files["wd"]
    inp = files["inp"]
    tpr = files["tpr"]
    ndx = files["ndx"]

    out = None
    step_name = ""

    if key == "trjconv":
        out = "md_fit.xtc"
        step_name = "轨迹转换"
        cmd = [gmx, "trjconv", "-s", tpr, "-f", inp, "-o", out]
        if ndx and os.path.exists(os.path.join(wd, ndx)):
            cmd += ["-n", ndx]
        if opt:
            cmd += opt.split()

    elif key == "trjcat":
        out = "combined.xtc"
        step_name = "轨迹合并"
        cmd = [gmx, "trjcat", "-f", inp, "-o", out]
        if opt:
            cmd += opt.split()

    elif key == "trjorder":
        out = "ordered.xtc"
        step_name = "轨迹排序"
        cmd = [gmx, "trjorder", "-s", tpr, "-f", inp, "-o", out]
        if opt:
            cmd += opt.split()

    elif key == "trjreshape":
        out = "reshaped.xtc"
        step_name = "轨迹重塑"
        cmd = [gmx, "trjreshape", "-f", inp, "-o", out]
        if opt:
            cmd += opt.split()

    elif key == "trjreduce":
        out = "reduced.xtc"
        step_name = "轨迹精简"
        cmd = [gmx, "trjreduce", "-f", inp, "-o", out]
        if opt:
            cmd += opt.split()

    elif key == "trjcluster":
        out = "cluster.pdb"
        step_name = "轨迹聚类"
        cmd = [gmx, "trjcluster", "-s", tpr, "-f", inp, "-o", out]
        if opt:
            cmd += opt.split()

    elif key == "trjstrip":
        out = "protein.xtc"
        step_name = "轨迹剥离"
        cmd = [gmx, "trjconv", "-s", tpr, "-f", inp, "-o", out]
        if ndx and os.path.exists(os.path.join(wd, ndx)):
            cmd += ["-n", ndx]
        if opt:
            cmd += opt.split()

    else:
        return None

    return cmd, step_name


# =============================================================================
# Part 2: 结构处理工具命令（run_structure_tool）
# =============================================================================

def build_structure_tool_command(
    key: str, gmx: str,
    files: dict, out: str, opt: str,
    md_ff: str = "", ndx_inp_val: str = ""
) -> Optional[Tuple[List[str], str]]:
    """构建 GROMACS 结构处理工具的命令行参数

    files: {inp, ndx, wd}
    md_ff: 力场名（仅 pdb2gmx 使用）
    ndx_inp_val: make_ndx 可选的 ndx 输入文件（仅 make_ndx 使用）
    返回 (cmd, step_name)；未知 key 返回 None。
    """
    wd = files["wd"]
    inp = files["inp"]
    ndx = files["ndx"]

    step_name = ""

    if key == "editconf":
        out = out or "protein_edit.gro"
        step_name = "编辑结构"
        cmd = [gmx, "editconf", "-f", inp, "-o", out]
        if opt:
            cmd += opt.split()

    elif key == "pdb2gmx":
        out = out or "protein.gro"
        step_name = "生成拓扑"
        cmd = [gmx, "pdb2gmx", "-f", inp, "-o", out, "-p", "topol.top", "-ff", md_ff]
        if opt:
            cmd += opt.split()

    elif key == "genconf":
        out = out or "protein_multi.gro"
        step_name = "生成构象"
        cmd = [gmx, "genconf", "-f", inp, "-o", out]
        if opt:
            cmd += opt.split()

    elif key == "gmx hbond":
        out = out or "hbond_analysis.xvg"
        step_name = "氢键分析"
        cmd = [gmx, "hbond", "-f", inp, "-num", out]
        if ndx and os.path.exists(os.path.join(wd, ndx)):
            cmd += ["-n", ndx]

    elif key == "gmx rms":
        out = out or "rmsd.xvg"
        step_name = "RMSD计算"
        cmd = [gmx, "rms", "-f", inp, "-o", out]
        if ndx and os.path.exists(os.path.join(wd, ndx)):
            cmd += ["-n", ndx]

    elif key == "gmx sasa":
        out = out or "sasa.xvg"
        step_name = "表面积计算"
        cmd = [gmx, "sasa", "-f", inp, "-o", out]
        if ndx and os.path.exists(os.path.join(wd, ndx)):
            cmd += ["-n", ndx]

    elif key == "gmx make_ndx":
        out = out or "index.ndx"
        step_name = "创建索引"
        if ndx_inp_val:
            inp = ndx_inp_val
        cmd = [gmx, "make_ndx", "-f", inp, "-o", out]
        if opt:
            cmd += opt.split()

    elif key == "gmx rmsf":
        out = out or "rmsf.xvg"
        step_name = "RMSF计算"
        cmd = [gmx, "rmsf", "-f", inp, "-o", out, "-res"]
        if ndx and os.path.exists(os.path.join(wd, ndx)):
            cmd += ["-n", ndx]
        if opt:
            cmd += opt.split()

    elif key == "gmx rdf":
        out = out or "rdf.xvg"
        step_name = "径向分布函数"
        cmd = [gmx, "rdf", "-f", inp, "-o", out]
        if ndx and os.path.exists(os.path.join(wd, ndx)):
            cmd += ["-n", ndx]
        if opt:
            cmd += opt.split()

    elif key == "gmx mindist":
        out = out or "mindist.xvg"
        step_name = "最小距离计算"
        cmd = [gmx, "mindist", "-f", inp, "-o", out]
        if ndx and os.path.exists(os.path.join(wd, ndx)):
            cmd += ["-n", ndx]
        if opt:
            cmd += opt.split()

    elif key == "gmx genrestr":
        out = out or "posre.itp"
        step_name = "生成位置限制"
        cmd = [gmx, "genrestr", "-f", inp, "-o", out]
        if ndx and os.path.exists(os.path.join(wd, ndx)):
            cmd += ["-n", ndx]
        if opt:
            cmd += opt.split()

    elif key == "gmx check":
        step_name = "结构验证"
        cmd = [gmx, "check", "-f", inp]
        if opt:
            cmd += opt.split()

    elif key == "gmx dump":
        step_name = "文件信息查看"
        cmd = [gmx, "dump", "-f", inp]
        if opt:
            cmd += opt.split()

    else:
        return None

    return cmd, step_name


# =============================================================================
# Part 4.5: 轨迹预处理流水线命令构建
# =============================================================================

def build_preprocessing_commands(gmx: str, params: dict) -> list:
    """构建轨迹预处理五步流水线的命令列表

    params: {wd, xtc, tpr, ndx, pbc_mode, center_group, fit_mode, fit_ref,
             b, e, dt, output}

    返回 [(cmd, step_name, echo_prefix, out_file), ...]
    """
    wd = params["wd"]
    xtc = params["xtc"]
    tpr = params["tpr"]
    ndx = params["ndx"]
    pbc_mode = params["pbc_mode"]
    center_group = params["center_group"]
    fit_mode = params["fit_mode"]
    fit_ref = params["fit_ref"]
    b = params["b"]
    e = params["e"]
    dt_val = params["dt"]
    output = params["output"]

    commands = []

    # Step 1: PBC修复
    step1_out = "_prep_step1.xtc"
    cmd1 = [gmx, "trjconv", "-f", xtc, "-s", tpr, "-o", step1_out, "-pbc", pbc_mode]
    if pbc_mode in ["mol", "res", "cluster"] and center_group:
        cmd1 += ["-center"]
    if ndx and os.path.exists(os.path.join(wd, ndx)):
        cmd1 += ["-n", ndx]
    commands.append((cmd1, "Step 1: PBC修复", "echo 0 0 | ", step1_out))

    # Step 2 & 3: 拟合
    current_input = step1_out
    if fit_mode != "none":
        step2_out = "_prep_step2.xtc"
        cmd2 = [gmx, "trjconv", "-f", current_input, "-s", tpr, "-o", step2_out, "-fit", fit_mode]
        if ndx and os.path.exists(os.path.join(wd, ndx)):
            cmd2 += ["-n", ndx]
        commands.append((cmd2, f"Step 2/3: {fit_mode}拟合", f"echo {fit_ref} 0 | ", step2_out))
        current_input = step2_out

    # Step 4: 截取平衡段 & Step 5: 降采样
    final_cmd = [gmx, "trjconv", "-f", current_input, "-s", tpr, "-o", output]
    if b > 0:
        final_cmd += ["-b", str(b)]
    if e > 0:
        final_cmd += ["-e", str(e)]
    if dt_val > 0:
        final_cmd += ["-dt", str(dt_val)]
    if ndx and os.path.exists(os.path.join(wd, ndx)):
        final_cmd += ["-n", ndx]
    commands.append((final_cmd, f"Step 4/5: 截取+降采样 → {output}", "echo 0 | ", output))

    return commands


# =============================================================================
# Part 6: MMPBSA 命令构建与环境校验 (治理 Issue #5)
# =============================================================================

def parse_ndx_groups(ndx_path: str) -> List[Tuple[int, str]]:
    """读取 GROMACS .ndx 索引文件，返回按 0-based 编号排列的 [(组号, 组名), ...]"""
    groups: List[Tuple[int, str]] = []
    if not ndx_path or not os.path.isfile(ndx_path):
        return groups
    with open(ndx_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            s = line.strip()
            m = re.match(r"^\[\s*(.+?)\s*\]$", s)
            if m:
                groups.append((len(groups), m.group(1)))
    return groups


def convert_ps_to_mmpbsa_frames(
    start_ps: float,
    end_ps: float,
    interval_ps: float,
    traj_dt_ps: float = 10.0,
) -> Tuple[int, Optional[int], int]:
    """将 GUI 的物理时间 (ps) 严谨换算为 gmx_MMPBSA 1-based 轨迹帧号 (startframe, endframe, interval)

    物理原则：
    - GUI 输入的 ps 时间绝不能直接当作帧索引；必须依据真实轨迹输出间隔 traj_dt_ps 换算。
    - startframe >= 1 (gmx_MMPBSA 1-based 索引: frame = 1 + round(start_ps / traj_dt_ps))
    - end_ps <= 0 表示计算至轨迹最后一帧，返回 endframe = None
    """
    if traj_dt_ps <= 0:
        raise ValueError(f"轨迹帧间隔 traj_dt_ps 必须为正数: {traj_dt_ps}")
    if start_ps < 0 or end_ps < 0:
        raise ValueError("起止时间不可为负数")
    if end_ps > 0 and end_ps < start_ps:
        raise ValueError(f"结束时间 ({end_ps} ps) 小于开始时间 ({start_ps} ps)")

    start_frame = 1 + max(0, int(round(start_ps / traj_dt_ps)))
    end_frame = None if end_ps <= 0 else max(start_frame, 1 + int(round(end_ps / traj_dt_ps)))
    frame_interval = max(1, int(round(interval_ps / traj_dt_ps))) if interval_ps > 0 else 1
    return start_frame, end_frame, frame_interval


def build_mmpbsa_input_file(params: dict) -> str:
    """根据采样起止帧、间隔、温度及绘图尺寸偏好生成标准的 gmx_MMPBSA 输入文件 (mmpbsa.in)"""
    start_frame = int(params.get("startframe", 1))
    end_frame = params.get("endframe")
    interval = max(1, int(params.get("interval", 1)))
    temperature = float(params.get("temperature", 298.15))
    sys_name = str(params.get("sys_name", "GROMACS_GUI_MMPBSA")).replace('"', "")

    general_lines = [
        "&general",
        f'  sys_name="{sys_name}",',
        f"  startframe={start_frame},",
    ]
    if end_frame is not None and int(end_frame) > 0:
        general_lines.append(f"  endframe={int(end_frame)},")
    general_lines.extend([
        f"  interval={interval},",
        f"  temperature={temperature:.2f},",
        "  verbose=2,",
        "/",
        "&gb",
        "  igb=5, saltcon=0.150,",
        "/",
        "",
    ])
    return "\n".join(general_lines)


def detect_gmx_mmpbsa_runner() -> Tuple[Optional[List[str]], str]:
    """探测外部 gmx_MMPBSA 可执行环境。

    优先查找独立的 gmx_MMPBSA 可执行程序；若未找到，则检测当前 Python 环境中是否安装了 GMXMMPBSA 包。
    返回 (runner_cmd_prefix, diagnostic_message)。
    """
    exe = shutil.which("gmx_MMPBSA")
    if exe:
        return [exe], f"检测到 gmx_MMPBSA 可执行程序: {exe}"

    if importlib.util.find_spec("GMXMMPBSA") is not None:
        return [sys.executable, "-m", "GMXMMPBSA.app"], f"检测到 Python GMXMMPBSA 模块 ({sys.executable})"

    return None, (
        "未检测到 gmx_MMPBSA 环境（既无 PATH 中的 gmx_MMPBSA 命令，也未在当前 Python 安装 GMXMMPBSA）。\n"
        "安装提示: conda install -c conda-forge gmx_mmpbsa 或 pip install gmx-MMPBSA"
    )


def build_mmpbsa_command(files: dict, options: Optional[dict] = None) -> Tuple[List[str], str]:
    """构建 gmx_MMPBSA 命令

    files: {tpr, xtc, ndx, top}
    options (可选):
      - input_file: mmpbsa.in 路径
      - receptor_group: 受体索引组号或名称 (如 "1" 或 "0")
      - ligand_group: 配体索引组号或名称 (如 "13" 或 "2")
      - nt: 并行进程数 (结合 mpiexec/mpirun 使用)
      - runner_prefix: 外部探测到的 gmx_MMPBSA 命令前缀
      - use_mpi: 是否启用 MPI 并行 (默认当 nt > 1 且检测到 mpirun 时自动启用)
      - output_dat: 输出结果文件名 (默认 FINAL_RESULTS_MMPBSA.dat)
    返回 (cmd, step_name)
    """
    tpr = files["tpr"]
    xtc = files["xtc"]
    ndx = files["ndx"]
    top = files["top"]

    step_name = "MMPBSA 结合自由能计算"

    if options is None:
        # 向后兼容无 options 的旧调用签名
        cmd = [
            "python", "-m", "GMXMMPBSA.app",
            "-cs", tpr,
            "-ci", ndx,
            "-cg", "1", "13",
            "-ct", xtc,
            "-cp", top,
            "-o", "FINAL_RESULTS_MMPBSA.dat",
            "-nogui"
        ]
        return cmd, step_name

    runner_prefix = list(options.get("runner_prefix") or ["python", "-m", "GMXMMPBSA.app"])
    rec_grp = str(options.get("receptor_group", "")).strip()
    lig_grp = str(options.get("ligand_group", "")).strip()
    if not rec_grp or not lig_grp:
        raise ValueError("必须明确指定受体索引组 (receptor_group) 和配体索引组 (ligand_group)，不允许盲目假定组 1/13")

    nt = max(1, int(options.get("nt", 1)))
    mpi_exe = options.get("mpi_exe") or shutil.which("mpirun") or shutil.which("mpiexec")
    use_mpi = options.get("use_mpi", True) and nt > 1 and bool(mpi_exe)

    prefix_cmd: List[str] = []
    if use_mpi and mpi_exe:
        prefix_cmd = [mpi_exe, "-np", str(nt)]
        if "-O" not in runner_prefix and "gmx_MMPBSA" in runner_prefix[0]:
            pass

    cmd = prefix_cmd + runner_prefix + [
        "-O",
        "-i", str(options.get("input_file", "mmpbsa.in")),
        "-cs", tpr,
        "-ci", ndx,
        "-cg", rec_grp, lig_grp,
        "-ct", xtc,
        "-cp", top,
        "-o", str(options.get("output_dat", "FINAL_RESULTS_MMPBSA.dat")),
        "-nogui"
    ]
    return cmd, step_name
