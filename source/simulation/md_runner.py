#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GROMACS MD 模拟步骤命令构建器

纯函数，输入参数字典，返回命令列表与步骤名。
零逻辑改动搬运自原 GromacsGUI.run_md_step / run_evap_step / run_anneal_step。
"""
import os
import shutil
from typing import List, Optional, Tuple


# =============================================================================
# 辅助：构建 mdrun 命令（Step 6/8/10/12 共用）
# =============================================================================

def build_mdrun_command(
    gmx: str, tpr: str, step_widgets: dict,
    wd: str, extra: List[str], is_em: bool = False
) -> Tuple[List[str], Optional[str], Optional[str], str]:
    """构建 mdrun 命令

    step_widgets: {custom_out_checked, custom_out, restart_checked}
    返回 (cmd, dup_warning, restart_msg, deffnm)
      dup_warning: 重复扩展名修正提示，无则 None
      restart_msg: "found" / "not_found" / None（未勾选重启）
    """
    dup_warning = None
    if tpr.endswith(".tpr.tpr"):
        tpr = tpr[:-4]
        dup_warning = f"检测到重复扩展名，已自动修正为 {tpr}"

    if step_widgets.get("custom_out_checked") and step_widgets.get("custom_out"):
        deffnm = step_widgets["custom_out"]
    else:
        deffnm = os.path.splitext(tpr)[0]

    extra = list(extra)
    restart_msg = None
    if step_widgets.get("restart_checked"):
        cpt_file = os.path.join(wd, f"{deffnm}.cpt")
        if os.path.isfile(cpt_file):
            extra += ["-cpi", f"{deffnm}.cpt", "-append"]
            restart_msg = "found"
        else:
            restart_msg = "not_found"

    base = ["mdrun", "-deffnm", deffnm]
    if is_em:
        base = ["mdrun", "-v", "-deffnm", deffnm]
    cmd = [gmx] + base + extra
    return cmd, dup_warning, restart_msg, deffnm


# =============================================================================
# 辅助：构建 grompp 命令（Step 5/7/9/11 共用）
# =============================================================================

def build_grompp_command(
    gmx: str, mdp: str, ingro: str, tpr: str, top: str,
    with_r: bool = False
) -> List[str]:
    cmd = [gmx, "grompp", "-f", mdp, "-c", ingro]
    if with_r:
        cmd += ["-r", ingro]
    cmd += ["-p", top, "-o", tpr, "-maxwarn", "2"]
    return cmd


# =============================================================================
# Step 2: editconf 盒子构建
# =============================================================================

def build_editconf_command(
    gmx: str, ingro: str, outgro: str, box_widgets: dict
) -> List[str]:
    bt_full = box_widgets["box_type"]
    if "cubic" in bt_full.lower():
        bt = "cubic"
    elif "triclinic" in bt_full.lower():
        bt = "triclinic"
    elif "dodecahedron" in bt_full.lower():
        bt = "dodecahedron"
    elif "octahedron" in bt_full.lower():
        bt = "octahedron"
    else:
        bt = "triclinic"
    is_rect = "rectangular" in bt_full.lower()
    is_triclinic = "triclinic" in bt_full.lower()
    is_box_mode = "边长" in box_widgets["size_mode"]

    params = []
    if box_widgets.get("center"):
        params.append("-c")
    if box_widgets.get("princ"):
        params.append("-princ")
    if is_box_mode:
        if is_rect:
            x = box_widgets["box_x"]
            y = box_widgets["box_y"]
            z = box_widgets["box_z"]
            params += ["-box", str(x), str(y), str(z)]
        elif is_triclinic:
            a = box_widgets["box_a"]
            alpha = box_widgets["angle_alpha"]
            beta = box_widgets["angle_beta"]
            gamma = box_widgets["angle_gamma"]
            params += ["-box", str(a), str(a), str(a),
                       "-angles", str(alpha), str(beta), str(gamma)]
        else:
            a = box_widgets["box_a"]
            params += ["-box", str(a), "-bt", bt]
    else:
        params += ["-bt", bt]
        d = box_widgets["box_size"]
        params += ["-d", str(d)]

    return [gmx, "editconf", "-f", ingro, "-o", outgro] + params


# =============================================================================
# 主入口：根据 step_key 构建命令
# =============================================================================

def build_md_step_command(step_key: str, gmx: str, state: dict):
    """构建单个 MD 步骤的命令

    state 字段:
      ff, water, ion_conc, pdb
      use_existing_top, se_gro, se_top
      edits: list[str]   步骤输入框值
      box_widgets: dict  Step 2 专用
      mdrun_widgets: dict  Step 6/8/10/12 专用
      mdrun_extra: list
      wd: str

    返回:
      ("single", cmd, step_name)        — 单命令，调用方 run_command([cmd], wd, step_name)
      ("multi", [cmd1, cmd2], step_name) — 多命令（genion）
      ("skip", None, None)              — 跳过（已有拓扑）
      ("unknown", None, None)           — 未知步骤
    """
    edits = state["edits"]

    def get_val(idx):
        return edits[idx].strip() if idx < len(edits) else ""

    ff = state["ff"]
    water = state["water"]
    ion_conc = state["ion_conc"]
    pdb = state["pdb"]
    use_existing = state["use_existing_top"]
    se_gro = state["se_gro"]
    se_top = state["se_top"]
    wd = state["wd"]

    if step_key == "Step 1":
        if use_existing:
            struct_file = se_gro or "input.gro"
            top = se_top or "topol.top"
            return ("skip", struct_file, top)
        gro = get_val(1) or "protein.gro"
        top = get_val(2) or "topol.top"
        posre = get_val(3) or "posre.itp"
        inp = get_val(0) or pdb
        cmd = [gmx, "pdb2gmx", "-f", inp, "-o", gro, "-p", top,
               "-i", posre, "-ff", ff, "-water", water, "-ignh"]
        return ("single", cmd, "pdb2gmx")

    elif step_key == "Step 2":
        ingro = get_val(0) or "protein.gro"
        outgro = get_val(1) or "protein_box.gro"
        cmd = build_editconf_command(gmx, ingro, outgro, state["box_widgets"])
        return ("single", cmd, "editconf")

    elif step_key == "Step 3":
        ingro = get_val(0) or "protein_box.gro"
        outgro = get_val(1) or "protein_solv.gro"
        top = get_val(2) or "topol.top"
        cmd = [gmx, "solvate", "-cp", ingro, "-o", outgro, "-p", top]
        return ("single", cmd, "solvate")

    elif step_key == "Step 4":
        ingro = get_val(0) or "protein_solv.gro"
        outgro = get_val(1) or "protein_ions.gro"
        top = get_val(2) or "topol.top"
        mdp = get_val(3) or "ions.mdp"
        tpr = "ions.tpr"
        cmd1 = [gmx, "grompp", "-f", mdp, "-c", ingro, "-p", top,
                "-o", tpr, "-maxwarn", "2"]
        cmd2 = [gmx, "genion", "-s", tpr, "-o", outgro, "-p", top,
                "-pname", "NA", "-nname", "CL", "-neutral",
                "-conc", str(ion_conc), "-quiet"]
        return ("multi", [cmd1, cmd2], "genion")

    elif step_key == "Step 5":
        mdp = get_val(0) or "em.mdp"
        default_gro = (se_gro or "input.gro") if use_existing else "protein_ions.gro"
        ingro = get_val(1) or default_gro
        tpr = get_val(2) or "em.tpr"
        top = se_top if use_existing else "topol.top"
        cmd = build_grompp_command(gmx, mdp, ingro, tpr, top, with_r=False)
        return ("single", cmd, "grompp (EM)")

    elif step_key == "Step 6":
        tpr = get_val(0) or "em.tpr"
        cmd, dup_warning, restart_msg, deffnm = build_mdrun_command(
            gmx, tpr, state["mdrun_widgets"], wd,
            state["mdrun_extra"], is_em=True
        )
        return ("single", cmd, "mdrun (EM)", dup_warning, restart_msg, deffnm)

    elif step_key == "Step 7":
        mdp = get_val(0) or "nvt.mdp"
        default_gro = (se_gro or "input.gro") if use_existing else "em.gro"
        ingro = get_val(1) or default_gro
        tpr = get_val(2) or "nvt.tpr"
        top = se_top if use_existing else "topol.top"
        cmd = build_grompp_command(gmx, mdp, ingro, tpr, top, with_r=True)
        return ("single", cmd, "grompp (NVT)")

    elif step_key == "Step 8":
        tpr = get_val(0) or "nvt.tpr"
        cmd, dup_warning, restart_msg, deffnm = build_mdrun_command(
            gmx, tpr, state["mdrun_widgets"], wd,
            state["mdrun_extra"], is_em=False
        )
        return ("single", cmd, "mdrun (NVT)", dup_warning, restart_msg, deffnm)

    elif step_key == "Step 9":
        mdp = get_val(0) or "npt.mdp"
        ingro = get_val(1) or "nvt.gro"
        tpr = get_val(2) or "npt.tpr"
        top = se_top if use_existing else "topol.top"
        cmd = build_grompp_command(gmx, mdp, ingro, tpr, top, with_r=True)
        return ("single", cmd, "grompp (NPT)")

    elif step_key == "Step 10":
        tpr = get_val(0) or "npt.tpr"
        cmd, dup_warning, restart_msg, deffnm = build_mdrun_command(
            gmx, tpr, state["mdrun_widgets"], wd,
            state["mdrun_extra"], is_em=False
        )
        return ("single", cmd, "mdrun (NPT)", dup_warning, restart_msg, deffnm)

    elif step_key == "Step 11":
        mdp = get_val(0) or "md.mdp"
        ingro = get_val(1) or "npt.gro"
        tpr = get_val(2) or "md.tpr"
        top = se_top if use_existing else "topol.top"
        cmd = build_grompp_command(gmx, mdp, ingro, tpr, top, with_r=True)
        return ("single", cmd, "grompp (MD)")

    elif step_key == "Step 12":
        tpr = get_val(0) or "md.tpr"
        cmd, dup_warning, restart_msg, deffnm = build_mdrun_command(
            gmx, tpr, state["mdrun_widgets"], wd,
            state["mdrun_extra"], is_em=False
        )
        return ("single", cmd, "mdrun (MD)", dup_warning, restart_msg, deffnm)

    else:
        return ("unknown", None, None)


# =============================================================================
# 退火模拟命令构建
# =============================================================================

def build_annealing_commands(
    gmx: str, prefix: str, gro_path: str, top_path: str,
    mdp_file: str, mdrun_extra: List[str], wd: str
) -> Tuple[List[str], List[str]]:
    """构建退火模拟的 grompp + mdrun 命令

    返回 (grompp_cmd, mdrun_cmd)
    """
    tpr_file = os.path.join(wd, f"{prefix}.tpr")
    grompp_cmd = [
        gmx, "grompp",
        "-f", mdp_file,
        "-c", gro_path,
        "-p", top_path,
        "-o", tpr_file,
        "-maxwarn", "200"
    ]
    deffnm = os.path.join(wd, prefix)
    mdrun_cmd = [gmx, "mdrun", "-v", "-deffnm", deffnm] + list(mdrun_extra)
    return grompp_cmd, mdrun_cmd


# =============================================================================
# 蒸发模拟单轮命令构建
# =============================================================================

def _move_cmd(src: str, dst: str) -> List[str]:
    """跨平台 move 命令"""
    import platform
    if platform.system() == "Windows":
        return ["cmd", "/c", "move", "/Y", src, dst]
    return ["mv", src, dst]


def _copy_cmd(src: str, dst: str) -> List[str]:
    """跨平台 copy 命令"""
    import platform
    if platform.system() == "Windows":
        return ["cmd", "/c", "copy", "/Y", src, dst]
    return ["cp", src, dst]


def _is_valid_gro_file(gro_path: str) -> bool:
    """检查 GRO 文件是否存在且为标准合法 GROMACS GRO 格式（头部原子数 == 实际原子行数、每行长度 >= 44、非空盒子行）。"""
    if not os.path.isfile(gro_path):
        return False
    try:
        with open(gro_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        if len(lines) < 3:
            return False
        num_atoms = int(lines[1].strip())
        if num_atoms < 0 or len(lines) - 3 != num_atoms:
            return False
        for i in range(2, 2 + num_atoms):
            if len(lines[i].rstrip("\r\n")) < 44:
                return False
        box_parts = lines[-1].strip().split()
        if len(box_parts) < 3:
            return False
        for bp in box_parts[:3]:
            float(bp)
        return True
    except Exception:
        return False


def _read_top_solvent_count(top_path: str, solvent: str) -> Optional[int]:
    """解析 TOP 文件 [ molecules ] 节中指定溶剂的总分子数；若文件无效或未找到则返回 None。"""
    if not os.path.isfile(top_path) or not solvent:
        return None
    try:
        with open(top_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        in_molecules = False
        total = 0
        found = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("[") and "]" in stripped:
                sec = stripped.split("]", 1)[0].lstrip("[").strip().lower()
                in_molecules = (sec == "molecules")
                continue
            if in_molecules and stripped and not stripped.startswith(";"):
                code = line.split(";", 1)[0].strip()
                parts = code.split()
                if len(parts) >= 2 and parts[0] == solvent:
                    cnt = int(parts[1])
                    if cnt < 0:
                        return None
                    total += cnt
                    found = True
        return total if found else None
    except Exception:
        return None


def _is_valid_top_file(top_path: str) -> bool:
    """检查 TOP 文件是否存在且包含有效的 [ molecules ] 节。"""
    if not os.path.isfile(top_path) or os.path.getsize(top_path) == 0:
        return False
    try:
        with open(top_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        in_molecules = False
        has_entry = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("[") and "]" in stripped:
                sec = stripped.split("]", 1)[0].lstrip("[").strip().lower()
                in_molecules = (sec == "molecules")
                continue
            if in_molecules and stripped and not stripped.startswith(";"):
                code = line.split(";", 1)[0].strip()
                parts = code.split()
                if len(parts) >= 2:
                    if int(parts[1]) < 0:
                        return False
                    has_entry = True
        return has_entry
    except Exception:
        return False


def build_evap_loop_commands(
    loop_idx: int, prefix: str, gmx: str, python_exe: str,
    delete_script: str, resname: str, delete_num: int,
    atoms_per_mol: int, delete_from: str, mdp_file: str,
    work_gro: str, work_top: str, current_gro: str, current_top: str,
    mdrun_extra: List[str], wd: str,
    restart_check: bool = False, start_loop: int = 1,
    mode: str = "solvent"
) -> Tuple[List[List[str]], Optional[str]]:
    """构建蒸发单轮命令列表

    mode: "solvent"（逐轮删除）或 "additive"（一次性删除全部）
    返回 (commands, restart_cpt_msg)
    """
    new_gro = f"{prefix}_new.gro"
    if mode == "additive":
        tpr_file = f"{prefix}.tpr"
        deffnm = prefix
        pending_top = f"{prefix}_new.top"
    else:
        tpr_file = f"{prefix}_{loop_idx}.tpr"
        deffnm = f"{prefix}_{loop_idx}"
        pending_top = f"{deffnm}_pending.top"

    if mode == "solvent":
        del_cmd = [
            python_exe, delete_script,
            "--solvent", resname,
            "--delete-num", str(delete_num),
            "--atoms-per-mol", str(atoms_per_mol),
            "--loop", str(loop_idx),
            "--delete-from", delete_from,
            "--input", work_gro,
            "--output", new_gro,
            "--topology", work_top,
            "--topology-output", pending_top,
        ]
    else:
        del_cmd = [
            python_exe, delete_script,
            "--additive", resname,
            "--atoms-per-mol", str(atoms_per_mol),
            "--input", work_gro,
            "--output", new_gro,
            "--topology", work_top,
            "--topology-output", pending_top,
        ]

    mdrun_cmd = [gmx, "mdrun", "-v", "-deffnm", deffnm] + list(mdrun_extra)
    restart_msg = None

    curr_cpt = f"{deffnm}.cpt"
    curr_cpt_path = os.path.join(wd, curr_cpt)
    curr_tpr_path = os.path.join(wd, tpr_file)
    curr_gro_path = os.path.join(wd, f"{deffnm}.gro")
    pending_top_path = os.path.join(wd, pending_top)
    loop_top_path = os.path.join(wd, f"{deffnm}.top")

    # 检查是否为“同一轮中断后从本轮 checkpoint 恢复”：
    # 当 restart_check=True 且 loop_idx == start_loop 且存在本轮 .cpt（且本轮尚未生成完整的完成态 .gro）时进入严格校验
    in_round_cpt_resume = (
        mode == "solvent"
        and restart_check
        and loop_idx == start_loop
        and os.path.isfile(curr_cpt_path)
        and not _is_valid_gro_file(curr_gro_path)
    )

    commands = []
    if in_round_cpt_resume:
        # 路径 3（同一轮中断恢复）：强制验证 TPR、CPT 与本轮正确拓扑状态，校验失败立即抛错停止并保留现场
        if os.path.getsize(curr_cpt_path) == 0:
            raise ValueError(f"同轮恢复校验失败: 检查点文件为空 ({curr_cpt})")
        if not os.path.isfile(curr_tpr_path) or os.path.getsize(curr_tpr_path) == 0:
            raise ValueError(
                f"同轮恢复校验失败: 检测到检查点 {curr_cpt}，但缺失有效的本轮运行输入文件 {tpr_file}，已停止并保留现场"
            )

        # 查找本轮专属拓扑（优先 pending_top，其次本轮已保存的 loop_top），严禁静默回退使用上一轮的 work_top
        resume_top_rel = None
        resume_top_abs = None
        if os.path.isfile(pending_top_path):
            resume_top_rel = pending_top
            resume_top_abs = pending_top_path
        elif os.path.isfile(loop_top_path):
            resume_top_rel = f"{deffnm}.top"
            resume_top_abs = loop_top_path
        else:
            raise ValueError(
                f"同轮恢复校验失败: 检测到 {curr_cpt}，但缺失本轮待提交拓扑 {pending_top}，拒绝静默使用上一轮拓扑，已停止并保留现场"
            )

        cand_count = _read_top_solvent_count(resume_top_abs, resname)
        if cand_count is None:
            raise ValueError(
                f"同轮恢复校验失败: 无法在 {resume_top_rel} 的 [ molecules ] 中读取有效的 {resname} 分子数"
            )

        # 若存在上一轮基准拓扑（{prefix}_{loop_idx-1}.top、{prefix}_original.top 或 work_top），校验分子数差值必须等于 delete_num
        base_top_candidates = []
        if loop_idx == 1:
            base_top_candidates.append(os.path.join(wd, f"{prefix}_original.top"))
        else:
            base_top_candidates.append(os.path.join(wd, f"{prefix}_{loop_idx - 1}.top"))
        base_top_candidates.append(os.path.join(wd, work_top))

        for base_top in base_top_candidates:
            if os.path.isfile(base_top) and os.path.abspath(base_top) != os.path.abspath(resume_top_abs):
                base_count = _read_top_solvent_count(base_top, resname)
                if base_count is not None:
                    expected_count = max(0, base_count - delete_num)
                    if cand_count != expected_count:
                        raise ValueError(
                            f"同轮恢复校验失败: {resume_top_rel} 中 {resname} 分子数 ({cand_count}) "
                            f"与预期 ({base_count} - {delete_num} = {expected_count}) 不一致，已停止并保留现场"
                        )
                    break

        # 保留已有 TPR 与 CPT，跳过 delete_solvent 与 grompp，直接恢复本轮 mdrun
        mdrun_cmd.extend(["-cpi", curr_cpt, "-append"])
        restart_msg = curr_cpt
        commands.append(mdrun_cmd)
        if resume_top_rel == pending_top:
            commands.append(_move_cmd(pending_top, work_top))
        elif resume_top_rel != work_top:
            commands.append(_copy_cmd(resume_top_rel, work_top))
    else:
        # 路径 1 / 2（连续新一轮计算 / 从已完成上一轮继续新一轮）：
        # grompp 使用 pending_top，待 mdrun 成功后再将 pending_top 提交至 work_top，确保中断时 pending_top 留存供同轮恢复校验
        commands.extend([
            del_cmd,
            _move_cmd(new_gro, work_gro),
            [gmx, "grompp", "-f", mdp_file, "-c", work_gro,
             "-p", pending_top, "-o", tpr_file, "-maxwarn", "200"],
            mdrun_cmd,
            _move_cmd(pending_top, work_top),
        ])

    # mdrun 完成后：将本轮输出结构更新至 work_gro 供下一轮继承，并保存本轮专属拓扑与 current 备份
    commands.append(_copy_cmd(f"{deffnm}.gro", work_gro))
    commands.append(_copy_cmd(f"{deffnm}.gro", current_gro))
    commands.append(_copy_cmd(work_top, f"{deffnm}.top"))
    commands.append(_copy_cmd(work_top, current_top))

    return commands, restart_msg


# =============================================================================
# 完整 MD 流水线（run_all_md）
# =============================================================================

def build_full_md_pipeline(gmx: str, state: dict) -> List[List[str]]:
    """构建完整 MD 流程的命令列表

    state: {ff, water, ion_conc, pdb, use_existing_top, se_gro, se_top,
            skip_editconf, skip_solvate, skip_genion, box_params,
            extra_mdrun, extra_em}
    """
    ff = state["ff"]
    water = state["water"]
    ion_conc = state["ion_conc"]
    pdb = state["pdb"]
    top = "topol.top"

    commands = []
    first_struct = "protein.gro"

    if state["use_existing_top"]:
        first_struct = state["se_gro"] or "input.gro"
        top = state["se_top"] or "topol.top"
    else:
        commands.append([gmx, "pdb2gmx", "-f", pdb, "-o", first_struct, "-p", top,
                         "-i", "posre.itp", "-ff", ff, "-water", water, "-ignh"])

    current_gro = first_struct
    if not state["skip_editconf"]:
        commands.append([gmx, "editconf", "-f", first_struct,
                         "-o", "protein_box.gro"] + state["box_params"])
        current_gro = "protein_box.gro"
    if not state["skip_solvate"]:
        commands.append([gmx, "solvate", "-cp", current_gro,
                         "-o", "protein_solv.gro", "-p", top])
        current_gro = "protein_solv.gro"

    if not state["skip_genion"]:
        commands.append([gmx, "grompp", "-f", "ions.mdp", "-c", current_gro,
                         "-p", top, "-o", "ions.tpr", "-maxwarn", "2"])
        commands.append([gmx, "genion", "-s", "ions.tpr", "-o", "protein_ions.gro",
                         "-p", top, "-pname", "NA", "-nname", "CL", "-neutral",
                         "-conc", f"{ion_conc:.3f}", "-quiet"])
        current_gro = "protein_ions.gro"

    commands.append([gmx, "grompp", "-f", "em.mdp", "-c", current_gro,
                     "-p", top, "-o", "em.tpr", "-maxwarn", "2"])
    commands.append([gmx, "mdrun", "-v", "-deffnm", "em"] + state["extra_em"])
    commands.append([gmx, "grompp", "-f", "nvt.mdp", "-c", "em.gro", "-r", "em.gro",
                     "-p", top, "-o", "nvt.tpr", "-maxwarn", "2"])
    commands.append([gmx, "mdrun", "-deffnm", "nvt"] + state["extra_mdrun"])
    commands.append([gmx, "grompp", "-f", "npt.mdp", "-c", "nvt.gro", "-r", "nvt.gro",
                     "-p", top, "-o", "npt.tpr", "-maxwarn", "2"])
    commands.append([gmx, "mdrun", "-deffnm", "npt"] + state["extra_mdrun"])
    commands.append([gmx, "grompp", "-f", "md.mdp", "-c", "npt.gro", "-r", "npt.gro",
                     "-p", top, "-o", "md.tpr", "-maxwarn", "2"])
    commands.append([gmx, "mdrun", "-deffnm", "md"] + state["extra_mdrun"])

    return commands


# =============================================================================
# 蒸发步骤：文件管理辅助函数
# =============================================================================

def detect_existing_loops(wd: str, prefix: str, allow_legacy: bool = False) -> Tuple[int, Optional[int]]:
    """扫描工作目录，检测已成功完成的蒸发轮次。

    返回 (start_loop, max_existing)：
      - 默认严格模式 (allow_legacy=False)：必须同时具备完整合法的 {prefix}_{N}.gro（满足标准 GROMACS GRO 行宽与原子数）、
        合法的配对拓扑 {prefix}_{N}.top，且不存在未提交的 {prefix}_{N}_pending.top；绝不将非空无效文本或未配对 TOP 的轮次误判为已完成。
      - 显式旧版兼容模式 (allow_legacy=True)：仅在显式开启时用于识别仅有合法 {prefix}_{N}.gro 且存在 {prefix}_current.top 的旧版目录，
        同样要求 GRO 必须通过严格格式校验。
      - 若存在已完成轮次，start_loop = max(N)+1, max_existing = max(N)
      - 否则 start_loop = 1, max_existing = None
    """
    if not os.path.isdir(wd):
        return 1, None

    candidates = []
    for f in os.listdir(wd):
        if f.startswith(f"{prefix}_") and f.endswith(".gro"):
            suffix = f[len(prefix) + 1:-4]
            if suffix.isdigit():
                candidates.append(int(suffix))

    valid_loops = []
    for loop_num in candidates:
        gro_p = os.path.join(wd, f"{prefix}_{loop_num}.gro")
        top_p = os.path.join(wd, f"{prefix}_{loop_num}.top")
        pending_p = os.path.join(wd, f"{prefix}_{loop_num}_pending.top")

        # 无论新旧模式，GRO 必须是完整合法的标准 GRO 文件，且不能残留未提交的 pending_top
        if not _is_valid_gro_file(gro_p) or os.path.isfile(pending_p):
            continue

        if _is_valid_top_file(top_p):
            valid_loops.append(loop_num)
        elif allow_legacy and _is_valid_top_file(os.path.join(wd, f"{prefix}_current.top")):
            valid_loops.append(loop_num)

    if valid_loops:
        return max(valid_loops) + 1, max(valid_loops)
    return 1, None


def check_evap_permissions(wd: str) -> Tuple[bool, Optional[str]]:
    """检查工作目录是否存在且有写入权限。

    返回 (ok, error_type)：
      - ok=True, error_type=None：正常
      - ok=False, error_type="not_exists"：目录不存在
      - ok=False, error_type="permission_denied"：无写入权限
    """
    if not os.path.exists(wd):
        return False, "not_exists"
    try:
        test_file = os.path.join(wd, "_test_write_permission.tmp")
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
        return True, None
    except PermissionError:
        return False, "permission_denied"


def resolve_path(wd: str, p: str) -> str:
    """解析相对/绝对路径"""
    return p if os.path.isabs(p) else os.path.join(wd, p)


def write_delete_script(wd: str, mode_idx: int,
                        solvent_script: str, additive_script: str) -> str:
    """写出删除分子脚本到工作目录，返回脚本文件名。

    mode_idx: 0=溶剂模式, 其他=添加剂模式
    """
    if mode_idx == 0:
        script_path = os.path.join(wd, "delete_solvent.py")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(solvent_script)
        return "delete_solvent.py"
    else:
        script_path = os.path.join(wd, "delete_additive_all.py")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(additive_script)
        return "delete_additive_all.py"


def setup_evap_work_files(
    wd: str, input_gro: str, top_file: str, prefix: str,
    start_loop: int, mode_idx: int
) -> Optional[dict]:
    """设置蒸发工作文件（备份原始文件、复制工作文件）。

    处理断点续跑逻辑：
      - start_loop == 1：从输入文件备份并复制到工作文件
      - start_loop > 1：从上一轮的 GRO/TOP 复制到工作文件

    返回字典 {original_gro, original_top, work_gro, work_top,
               current_gro, current_top, prev_top_basename}
    失败时返回 None。
    """
    resolve = lambda p: resolve_path(wd, p)

    original_gro = f"{prefix}_original.gro"
    original_top = f"{prefix}_original.top"
    work_gro = f"{prefix}_work.gro"
    work_top = f"{prefix}_work.top"
    current_gro = f"{prefix}_current.gro"
    current_top = f"{prefix}_current.top"

    result = {
        "original_gro": original_gro,
        "original_top": original_top,
        "work_gro": work_gro,
        "work_top": work_top,
        "current_gro": current_gro,
        "current_top": current_top,
        "prev_top_basename": None,
    }

    if mode_idx == 0:
        if start_loop == 1:
            shutil.copy(resolve(input_gro), os.path.join(wd, original_gro))
            shutil.copy(resolve(top_file), os.path.join(wd, original_top))
            shutil.copy(resolve(input_gro), os.path.join(wd, work_gro))
            shutil.copy(resolve(top_file), os.path.join(wd, work_top))
        else:
            prev_loop = start_loop - 1
            prev_gro = f"{prefix}_{prev_loop}.gro"
            possible_tops = [
                os.path.join(wd, f"{prefix}_{prev_loop}.top"),
                os.path.join(wd, f"{prefix}_current.top"),
                resolve(top_file),
            ]
            prev_top = None
            for pt in possible_tops:
                if os.path.isfile(pt):
                    prev_top = pt
                    break

            if not os.path.isfile(os.path.join(wd, prev_gro)):
                result["error"] = f"missing_prev_gro:{prev_gro}"
                return result
            if prev_top is None:
                result["error"] = "missing_prev_top"
                result["possible_tops"] = possible_tops
                return result
            shutil.copy(os.path.join(wd, prev_gro), os.path.join(wd, work_gro))
            shutil.copy(prev_top, os.path.join(wd, work_top))
            result["prev_top_basename"] = os.path.basename(prev_top)
    else:
        # 添加剂模式：一次性删除，备份原始文件
        shutil.copy(resolve(input_gro), os.path.join(wd, original_gro))
        shutil.copy(resolve(top_file), os.path.join(wd, original_top))

    return result
