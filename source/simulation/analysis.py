#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GROMACS 命令构建器：分析、轨迹处理、结构处理工具

所有函数均为纯函数，输入参数（不含 Qt 引用），返回命令列表与步骤名。
零逻辑改动搬运自原 GromacsGUI 的 run_analysis / run_trajectory_tool / run_structure_tool。
"""
import os
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
# Part 6: MMPBSA 命令构建
# =============================================================================

def build_mmpbsa_command(files: dict) -> Tuple[List[str], str]:
    """构建 gmx_MMPBSA 命令

    files: {tpr, xtc, ndx, top}
    返回 (cmd, step_name)
    """
    tpr = files["tpr"]
    xtc = files["xtc"]
    ndx = files["ndx"]
    top = files["top"]

    step_name = "MMPBSA 结合自由能计算"
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
