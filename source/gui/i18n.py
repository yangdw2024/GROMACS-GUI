# -*- coding: utf-8 -*-
"""
GROMACS-GUI 国际化与双语翻译引擎 (i18n System: zh / en)
提供：
1. 集中管理的科研计算专业中英文术语词典 (TRANSLATIONS)
2. 零状态依赖翻译函数 tr(key, default=None) 与语言切换状态管理
3. ComboBox 稳定枚举数据 (itemData) 辅助工具，杜绝显示文案参与科学命令拼装逻辑
"""

from typing import Dict

_CURRENT_LANG = "zh"

# =============================================================================
# 科研中英文术语表 (Molecular Dynamics Scientific Glossary)
# =============================================================================
SCIENTIFIC_GLOSSARY = {
    "力场": "Force Field",
    "水模型": "Water Model",
    "盒子类型": "Box Type",
    "能量最小化": "Energy Minimization (EM)",
    "溶剂化": "Solvation",
    "添加离子": "Ion Addition (genion)",
    "NVT平衡": "NVT Equilibration",
    "NPT平衡": "NPT Equilibration",
    "生产模拟": "Production MD",
    "溶剂蒸发": "Solvent Evaporation (SA)",
    "退火模拟": "Simulated Annealing",
    "伞形采样": "Umbrella Sampling",
    "加权直方图分析": "WHAM Free Energy",
    "元动力学": "Metadynamics",
    "自适应偏置力": "Adaptive Biasing Force (ABF)",
    "周期性边界条件": "Periodic Boundary Conditions (PBC)",
    "径向分布函数": "Radial Distribution Function (RDF)",
    "均方位移": "Mean Squared Displacement (MSD)",
    "回旋半径": "Radius of Gyration (Rg)",
    "溶剂可及表面积": "Solvent Accessible Surface Area (SASA)",
    "结合自由能": "Binding Free Energy (MM/PBSA)",
}

TRANSLATIONS: Dict[str, Dict[str, str]] = {
    # ==================== 1. 应用外壳与顶部控制栏 ====================
    "brand_subtitle": {"zh": "GROMACS 动力学模拟与分析集成工具", "en": "Integrated MD Simulation & Analysis Suite"},
    "run_all": {"zh": "▶ 一键运行", "en": "▶ Run All"},
    "stop": {"zh": "■ 停止", "en": "■ Stop"},
    "mdp_editor": {"zh": "MDP编辑", "en": "MDP Editor"},
    "monitor": {"zh": "监控", "en": "Monitor"},
    "save": {"zh": "保存", "en": "Save"},
    "load": {"zh": "加载", "en": "Load"},
    "more": {"zh": "更多 ▾", "en": "More ▾"},
    "theme_to_light": {"zh": "☀️ 浅色", "en": "☀️ Light"},
    "theme_to_dark": {"zh": "🌙 深色", "en": "🌙 Dark"},
    "layout_to_classic": {"zh": "经典布局", "en": "Classic"},
    "layout_to_modern": {"zh": "现代布局", "en": "Modern"},
    "lang_switch_btn": {"zh": "EN", "en": "中文"},
    "lang_tooltip": {"zh": "切换界面语言 (中文 / English)", "en": "Switch UI Language (中文 / English)"},
    "workdir_label": {"zh": "工作目录:", "en": "Work Dir:"},
    "workdir_placeholder": {"zh": "请选择或输入模拟工作目录路径...", "en": "Select or enter simulation working directory..."},
    "browse": {"zh": "浏览...", "en": "Browse..."},
    "browse_short": {"zh": "浏览", "en": "Browse"},

    # ==================== 2. 系统配置抽屉 ====================
    "kernel_version": {"zh": "内核版本:", "en": "GMX Binary:"},
    "show_all_versions": {"zh": "显示全部版本", "en": "Show All Versions"},
    "version_mgmt": {"zh": "版本管理", "en": "Versions"},
    "update_pkg": {"zh": "更新包", "en": "Updates"},
    "threads_label": {"zh": "线程(-nt):", "en": "Threads (-nt):"},
    "mem_limit": {"zh": "内存限制", "en": "Mem Limit"},
    "enable_gpu": {"zh": "启用GPU", "en": "Enable GPU"},
    "auto_mode": {"zh": "自动", "en": "Auto"},
    "gpu_diag": {"zh": "GPU诊断", "en": "GPU Diag"},

    # ==================== 3. 左侧导航栏 ====================
    "nav_group_md": {"zh": "动力学与建模", "en": "DYNAMICS & MODELING"},
    "nav_group_ana": {"zh": "轨迹与后处理分析", "en": "TRAJECTORY & ANALYSIS"},
    "nav_group_script": {"zh": "自动化与脚本", "en": "AUTOMATION & SCRIPTS"},
    "nav_group_sys": {"zh": "系统与维护", "en": "SYSTEM & TOOLS"},
    "nav_part1": {"zh": "Part 1 · MD 模拟", "en": "Part 1 · MD Simulation"},
    "nav_part2": {"zh": "Part 2 · 结构处理", "en": "Part 2 · Structure Prep"},
    "nav_part3": {"zh": "Part 3 · 高级模拟", "en": "Part 3 · Adv. Sampling"},
    "nav_part4": {"zh": "Part 4 · 轨迹处理", "en": "Part 4 · Trajectory"},
    "nav_part5": {"zh": "Part 5 · 结果分析", "en": "Part 5 · Analysis"},
    "nav_part6": {"zh": "Part 6 · MMPBSA", "en": "Part 6 · MMPBSA"},
    "nav_part7": {"zh": "Part 7 · 自定义脚本", "en": "Part 7 · Custom Scripts"},
    "sys_cleanup": {"zh": "系统清理", "en": "System Cleanup"},
    "log_dir": {"zh": "日志目录", "en": "Log Directory"},
    "about_ver": {"zh": "版本与系统信息", "en": "Version & Info".replace("&", "&&")},

    # ==================== 4. 底部控制台与状态栏 ====================
    "terminal_title": {"zh": "▶ 运行终端", "en": "▶ Console"},
    "diag_btn": {"zh": "诊断", "en": "Diagnose"},
    "clear_btn": {"zh": "清空", "en": "Clear"},
    "export_btn": {"zh": "导出", "en": "Export"},
    "collapse_btn": {"zh": "▼ 折叠", "en": "▼ Collapse"},
    "expand_btn": {"zh": "▲ 展开", "en": "▲ Expand"},
    "status_ready_modern": {"zh": "就绪 (现代化工作台模式)", "en": "Ready (Modern Workbench)"},
    "status_ready_classic": {"zh": "就绪 (经典双栏模式)", "en": "Ready (Classic Tab View)"},
    "status_running": {"zh": "运行中...", "en": "Running..."},
    "status_ready": {"zh": "就绪", "en": "Ready"},

    # ==================== 5. 通用动作按钮 ====================
    "run_step": {"zh": "运行此步骤", "en": "Run Step"},
    "run_tool": {"zh": "运行", "en": "Run"},
    "gen_default_mdp": {"zh": "生成默认MDP", "en": "Default MDP"},
    "adv_editor": {"zh": "高级编辑器", "en": "MDP Editor"},

    # ==================== 6. Part 1: MD 模拟 ====================
    "md_global_group": {"zh": "全局模拟参数", "en": "Global Simulation Parameters"},
    "md_ff": {"zh": "力场:", "en": "Force Field:"},
    "md_water": {"zh": "水模型:", "en": "Water Model:"},
    "md_box_type": {"zh": "盒子类型:", "en": "Box Type:"},
    "md_box_mode": {"zh": "设置方式:", "en": "Sizing Mode:"},
    "md_ion_conc": {"zh": "离子浓度:", "en": "Ion Conc:"},
    "md_temp": {"zh": "温度:", "en": "Temperature:"},
    "md_press": {"zh": "压力:", "en": "Pressure:"},
    "md_dt": {"zh": "积分步长:", "en": "Time Step:"},
    "md_nsteps": {"zh": "模拟步数:", "en": "Steps:"},
    "md_engine": {"zh": "计算引擎:", "en": "Compute Engine:"},
    "md_nt": {"zh": "线程数:", "en": "Threads:"},
    "md_pdb": {"zh": "输入PDB:", "en": "Input PDB:"},
    "md_box_dist": {"zh": "盒子边距:", "en": "Box Margin:"},
    "md_princ": {"zh": "主惯性轴对齐 (-princ)", "en": "Align Principal Axes (-princ)"},
    "md_use_existing": {"zh": "使用已有拓扑", "en": "Use Existing Topology"},
    "md_skip_solvate": {"zh": "跳过溶剂化", "en": "Skip Solvate"},
    "md_skip_genion": {"zh": "跳过加离子", "en": "Skip Genion"},
    "md_skip_editconf": {"zh": "跳过盒子定义", "en": "Skip Editconf"},
    "md_phase_prep": {"zh": "📦 第一阶段: 结构准备 (Step 1-4)", "en": "📦 Phase 1: Structure Preparation (Step 1-4)"},
    "md_phase_em": {"zh": "⚡ 第二阶段: 能量最小化 (Step 5-6)", "en": "⚡ Phase 2: Energy Minimization (Step 5-6)"},
    "md_phase_equil": {"zh": "⚖️ 第三阶段: 平衡模拟 (Step 7-10)", "en": "⚖️ Phase 3: Equilibration (Step 7-10)"},
    "md_phase_prod": {"zh": "🚀 第四阶段: 生产模拟 (Step 11-12)", "en": "🚀 Phase 4: Production MD (Step 11-12)"},
    "md_phase_evap": {"zh": "🔥 第五阶段: 溶剂/添加剂蒸发", "en": "🔥 Phase 5: Solvent / Additive Evaporation (SA)"},
    "md_phase_anneal": {"zh": "🌡️ 第六阶段: 退火模拟 (Simulated Annealing)", "en": "🌡️ Phase 6: Simulated Annealing"},
    "md_evap_start": {"zh": "🚀 开始蒸发", "en": "🚀 Start Evaporation"},
    "md_anneal_start": {"zh": "🚀 开始退火模拟", "en": "🚀 Start Annealing"},
    "md_box_opt_margin": {"zh": "按边距 (-d)", "en": "By Margin (-d)"},
    "md_box_opt_dims": {"zh": "按盒子边长 (-box)", "en": "By Box Size (-box)"},
    "md_evap_mode_batch": {"zh": "分批蒸发溶剂（循环删除+NPT）", "en": "Batch Solvent Evaporation (Delete + NPT Loop)"},
    "md_evap_mode_all": {"zh": "一次性删除全部添加剂", "en": "Remove All Additive Molecules at Once"},

    # ==================== 7. Part 2: 结构处理 ====================
    "struc_common_group": {"zh": "结构处理参数", "en": "Structure Processing Parameters"},
    "struc_prep_group": {"zh": "🔧 核心结构准备", "en": "🔧 Core Structure Preparation"},
    "struc_convert_group": {"zh": "🔄 结构转换与验证", "en": "🔄 Conversion & Validation"},
    "struc_tip": {"zh": "💡 提示：轨迹分析工具（RMSD/RMSF/SASA/氢键/RDF等）已移至 Part 5 结果分析", "en": "💡 Tip: Trajectory analysis tools (RMSD/RMSF/SASA/H-Bond/RDF) are in Part 5."},

    # ==================== 8. Part 3: 高级模拟 ====================
    "adv_info": {"zh": "高级模拟方法需要特定的 MDP 参数和可能需要 PLUMED 插件支持。\n本版本 GROMACS 已内置 PLUMED 支持。", "en": "Enhanced sampling methods require dedicated MDP settings or PLUMED support.\nThis GROMACS build includes built-in PLUMED support."},
    "adv_umb_group": {"zh": "伞形采样 (Umbrella Sampling)", "en": "Umbrella Sampling"},
    "adv_wham_group": {"zh": "WHAM 自由能计算", "en": "WHAM Free Energy Analysis"},
    "adv_meta_group": {"zh": "元动力学 (Metadynamics) - PLUMED", "en": "Metadynamics (PLUMED)"},
    "adv_abf_group": {"zh": "自适应偏置力 (ABF)", "en": "Adaptive Biasing Force (ABF)"},
    "adv_umb_btn": {"zh": "生成伞形采样 MDP", "en": "Generate Umbrella MDPs"},
    "adv_wham_btn": {"zh": "▶ 运行 gmx wham", "en": "▶ Run gmx wham"},
    "adv_meta_gen_btn": {"zh": "生成 PLUMED 输入", "en": "Generate PLUMED Input"},
    "adv_meta_run_btn": {"zh": "▶ 运行元动力学模拟", "en": "▶ Run Metadynamics"},
    "adv_abf_btn": {"zh": "生成 ABF PLUMED", "en": "Generate ABF PLUMED"},

    # ==================== 9. Part 4: 轨迹处理 ====================
    "traj_common_group": {"zh": "轨迹处理参数", "en": "Trajectory Processing Parameters"},
    "traj_prep_group": {"zh": "🔄 轨迹预处理流水线", "en": "🔄 Trajectory Preprocessing Pipeline"},
    "traj_prep_desc": {"zh": "标准预处理五步法：PBC修复 → 体系居中 → 去除平动/转动 → 截取平衡段 → 降采样精简", "en": "5-Step Pipeline: PBC Repair → Centering → Rot+Trans Fitting → Time Slicing → Downsampling"},
    "traj_prep_btn": {"zh": "一键执行预处理流水线", "en": "▶ Run Preprocessing Pipeline"},

    # ==================== 10. Part 5: 结果分析 ====================
    "ana_common_group": {"zh": "通用分析参数", "en": "General Analysis Parameters"},
    "ana_file_group": {"zh": "📁 文件管理与校验", "en": "📁 File Check & Status"},
    "ana_energy_group": {"zh": "🌡️ 能量与热力学分析", "en": "🌡️ Energy & Thermodynamics"},
    "ana_struct_group": {"zh": "📐 结构稳定性分析", "en": "📐 Structural Stability"},
    "ana_interact_group": {"zh": "🔗 相互作用分析", "en": "🔗 Molecular Interactions"},
    "ana_fragment_group": {"zh": "🧩 片段分析", "en": "🧩 Fragment Analysis"},
    "ana_adv_group": {"zh": "📊 高级分析方法", "en": "📊 Advanced Analysis (PCA / Cluster)"},
    "ana_plot_group": {"zh": "📈 结果自动绘图", "en": "📈 Automated XVG Plotting"},
    "ana_ed_group": {"zh": "⚡ 能量分解分析", "en": "⚡ Energy Decomposition"},
    "ana_batch_group": {"zh": "📦 批量处理系统", "en": "📦 Batch Multi-System Analysis"},

    # ==================== 11. Part 6: MMPBSA ====================
    "mmpbsa_info": {"zh": "MMPBSA (Molecular Mechanics Poisson-Boltzmann Surface Area) 结合自由能计算。\n请确保已安装 gmx_MMPBSA 或相关脚本。", "en": "MMPBSA (Molecular Mechanics Poisson-Boltzmann Surface Area) binding free energy calculation.\nEnsure gmx_MMPBSA is installed in the target environment."},
    "mmpbsa_inp_group": {"zh": "输入文件参数", "en": "Input Files"},
    "mmpbsa_sam_group": {"zh": "采样与计算参数", "en": "Sampling & Parallel Settings"},
    "mmpbsa_img_group": {"zh": "结果图片输出设置", "en": "Plot Export Settings"},
    "mmpbsa_run_btn": {"zh": "▶ 运行 MMPBSA 计算", "en": "▶ Run MMPBSA Calculation"},

    # ==================== 12. Part 7: 自定义脚本 ====================
    "script_info": {"zh": "自定义脚本运行模块。可以编写 Windows PowerShell / Batch 脚本，调用 GROMACS 命令或执行其他自定义流程。\n提示: 脚本会在工作目录下执行，可使用 $env:GMX 或 %GMX% 获取gmx路径。", "en": "Custom Script Execution. Write PowerShell, Batch, or Shell commands to invoke GROMACS or custom automation pipelines.\nTip: Scripts run inside the working directory; access GMX path via $env:GMX or %GMX%."},
    "script_type_lbl": {"zh": "脚本类型:", "en": "Script Type:"},
    "script_save": {"zh": "保存脚本", "en": "Save Script"},
    "script_load": {"zh": "加载脚本", "en": "Load Script"},
    "script_clear": {"zh": "清空", "en": "Clear"},
    "script_run": {"zh": "▶ 运行脚本", "en": "▶ Run Script"},
    "script_edit_group": {"zh": "脚本编辑", "en": "Script Editor"},
    "script_tmpl_group": {"zh": "快速模板", "en": "Quick Templates"},
    "script_manage_tmpl": {"zh": "管理自定义模板", "en": "Manage Templates"},
}


def set_language(lang: str) -> str:
    global _CURRENT_LANG
    lang_norm = "en" if str(lang).lower().startswith("en") else "zh"
    _CURRENT_LANG = lang_norm
    return _CURRENT_LANG


def get_language() -> str:
    return _CURRENT_LANG


def tr(key: str, default: str = None, lang: str = None) -> str:
    active_lang = lang or _CURRENT_LANG
    entry = TRANSLATIONS.get(key)
    if entry:
        return entry.get(active_lang, entry.get("zh", default or key))
    return default if default is not None else key
