# -*- coding: utf-8 -*-
"""
Part 1: 基础与全流程 MD 模拟独立页面组件
从 main_window.py 拆分抽离。
负责：
1. 全局模拟参数 (力场、水模型、盒子类型与尺度、温度/压力/步长/总步数、引擎/线程)
2. 已有拓扑复用与步骤跳过状态机控制
3. Step 1-4 结构准备、EM 能量最小化、NVT/NPT 平衡、生产 MD 模拟卡片与多步全自动流
4. 第五阶段: 溶剂/添加剂蒸发 (SA 逐轮结构继承与检查点续跑)
5. 第六阶段: 退火模拟 (曲线表格编辑、退火 MDP 生成与执行)
6. 全部计算命令通过统一信号 run_requested 上抛至主窗口任务调度器
"""

import os
import sys
from typing import Optional, Callable, List

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QSpinBox, QDoubleSpinBox, QGroupBox, QScrollArea,
    QCheckBox, QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog
)

from simulation.mdp_builder import (
    build_simple_mdp, build_full_mdp, build_annealing_mdp
)
from simulation.md_runner import (
    build_md_step_command, build_annealing_commands,
    build_evap_loop_commands, build_full_md_pipeline,
    detect_existing_loops, check_evap_permissions, resolve_path,
    write_delete_script, setup_evap_work_files
)
from gui.embedded_scripts import DELETE_SOLVENT_SCRIPT, DELETE_ADDITIVE_SCRIPT
from gui.i18n import tr

class MdTab(QWidget):
    """Part 1: 分子动力学全流程模拟独立页面组件

    Signals:
        run_requested(cmd, work_dir, step_name): 请求主调度器执行构建好的命令链
        log_requested(message, level): 请求向主日志视口追加日志
    """

    run_requested = pyqtSignal(object, str, str)
    log_requested = pyqtSignal(str, str)

    def __init__(
        self,
        get_work_dir: Optional[Callable[[], str]] = None,
        get_gmx_path: Optional[Callable[[], str]] = None,
        get_mdrun_extra: Optional[Callable[[bool], List[str]]] = None,
        get_sys_cpu_cores: Optional[Callable[[], int]] = None,
        get_sys_gpu_info: Optional[Callable[[], dict]] = None,
        open_mdp_editor: Optional[Callable[[str], None]] = None,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self._get_work_dir = get_work_dir or (lambda: os.getcwd())
        self._get_gmx_path = get_gmx_path or (lambda: "gmx")
        self._get_mdrun_extra = get_mdrun_extra or (lambda is_em=False: [])
        self._get_sys_cpu_cores = get_sys_cpu_cores or (lambda: 4)
        self._get_sys_gpu_info = get_sys_gpu_info or (lambda: {"available": False})
        self._open_mdp_editor = open_mdp_editor or (lambda t: None)
        self.md_step_btns = {}

        self._init_ui()

    def _browse_file(self, line_edit: QLineEdit, title: str = "选择文件", file_filter: str = "所有文件 (*.*)"):
        wd = self._get_work_dir() or os.getcwd()
        fname, _ = QFileDialog.getOpenFileName(self, title, wd, file_filter)
        if fname:
            if fname.startswith(wd + os.sep) or fname.startswith(wd + "/"):
                line_edit.setText(os.path.basename(fname))
            else:
                line_edit.setText(fname)

    def _create_file_input(self, placeholder: str, default: str = "", filter_str: str = "所有文件 (*.*)", dialog_title: str = "选择文件"):
        layout = QHBoxLayout()
        layout.setSpacing(4)
        line_edit = QLineEdit()
        line_edit.setPlaceholderText(placeholder)
        if default:
            line_edit.setText(default)
        btn = QPushButton("浏览")
        btn.setFixedWidth(55)
        btn.setToolTip("浏览文件")
        btn.setProperty("role", "browseBtn")
        btn.clicked.connect(lambda: self._browse_file(line_edit, dialog_title, filter_str))
        layout.addWidget(line_edit, stretch=1)
        layout.addWidget(btn)
        return line_edit, layout

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        vbox = QVBoxLayout(content)
        vbox.setSpacing(12)
        vbox.setContentsMargins(8, 10, 8, 10)

        # 1. 全局模拟参数
        self.common_group = QGroupBox(tr("md_global_group"))
        ggrid = QGridLayout(self.common_group)
        ggrid.setSpacing(6)

        self.md_ff = QComboBox()
        self.md_ff.addItems([
            "amber03", "amber94", "amber96", "amber99", "amber99sb",
            "amber99sb-ildn", "amberGS", "amber14sb", "amber19sb",
            "charmm27", "gromos43a1", "gromos43a2", "gromos45a3",
            "gromos53a5", "gromos53a6", "gromos54a7", "oplsaa",
            "gaff (AmberTools-需预处理)", "gaff2 (AmberTools-需预处理)"
        ])

        self.md_water = QComboBox()
        self.md_water.addItems(["spc", "spce", "tip3p", "tip4p", "tip4pew", "tip5p", "opc", "opc3"])

        self.md_box_type = QComboBox()
        self.md_box_type.addItems(["cubic (立方体)", "triclinic (三斜)", "dodecahedron (十二面体)", "octahedron (八面体)", "rectangular (长方体)"])
        self.md_box_type.currentTextChanged.connect(self._on_box_type_changed)

        self.md_box_size_mode = QComboBox()
        self.md_box_size_mode.addItem("按边距 (-d)", "margin")
        self.md_box_size_mode.addItem("按盒子边长 (-box)", "box")
        self.md_box_size_mode.currentTextChanged.connect(self._on_box_size_mode_changed)

        self.md_box_size = QDoubleSpinBox()
        self.md_box_size.setRange(0.5, 50.0)
        self.md_box_size.setValue(1.0)
        self.md_box_size.setDecimals(2)
        self.md_box_size.setSuffix(" nm")

        self.md_box_a = QDoubleSpinBox()
        self.md_box_a.setRange(0.1, 500.0)
        self.md_box_a.setValue(5.0)
        self.md_box_a.setDecimals(2)
        self.md_box_a.setSuffix(" nm")
        self.md_box_a.setVisible(False)

        self.md_box_x = QDoubleSpinBox()
        self.md_box_x.setRange(0.5, 500.0)
        self.md_box_x.setValue(1.0)
        self.md_box_x.setDecimals(2)
        self.md_box_x.setSuffix(" nm")
        self.md_box_x.setVisible(False)

        self.md_box_y = QDoubleSpinBox()
        self.md_box_y.setRange(0.5, 500.0)
        self.md_box_y.setValue(1.5)
        self.md_box_y.setDecimals(2)
        self.md_box_y.setSuffix(" nm")
        self.md_box_y.setVisible(False)

        self.md_box_z = QDoubleSpinBox()
        self.md_box_z.setRange(0.5, 500.0)
        self.md_box_z.setValue(2.0)
        self.md_box_z.setDecimals(2)
        self.md_box_z.setSuffix(" nm")
        self.md_box_z.setVisible(False)

        self.md_angle_alpha = QDoubleSpinBox()
        self.md_angle_alpha.setRange(1.0, 179.0)
        self.md_angle_alpha.setValue(90.0)
        self.md_angle_alpha.setDecimals(1)
        self.md_angle_alpha.setSuffix(" °")
        self.md_angle_alpha.setVisible(False)

        self.md_angle_beta = QDoubleSpinBox()
        self.md_angle_beta.setRange(1.0, 179.0)
        self.md_angle_beta.setValue(90.0)
        self.md_angle_beta.setDecimals(1)
        self.md_angle_beta.setSuffix(" °")
        self.md_angle_beta.setVisible(False)

        self.md_angle_gamma = QDoubleSpinBox()
        self.md_angle_gamma.setRange(1.0, 179.0)
        self.md_angle_gamma.setValue(90.0)
        self.md_angle_gamma.setDecimals(1)
        self.md_angle_gamma.setSuffix(" °")
        self.md_angle_gamma.setVisible(False)

        self.md_princ = QCheckBox("主惯性轴对齐 (-princ)")
        self.md_princ.setChecked(False)
        self.md_princ.setToolTip("将蛋白质对齐到主惯性轴，使盒子更紧凑")

        self.md_ion_conc = QDoubleSpinBox()
        self.md_ion_conc.setRange(0.0, 5.0)
        self.md_ion_conc.setValue(0.15)
        self.md_ion_conc.setDecimals(3)
        self.md_ion_conc.setSuffix(" M")

        self.md_temp = QDoubleSpinBox()
        self.md_temp.setRange(1.0, 1000.0)
        self.md_temp.setValue(300.0)
        self.md_temp.setDecimals(1)
        self.md_temp.setSuffix(" K")

        self.md_pressure = QDoubleSpinBox()
        self.md_pressure.setRange(0.1, 100000.0)
        self.md_pressure.setValue(1.0)
        self.md_pressure.setDecimals(2)
        self.md_pressure.setSuffix(" bar")

        self.md_dt = QDoubleSpinBox()
        self.md_dt.setDecimals(4)
        self.md_dt.setRange(0.0001, 0.01)
        self.md_dt.setValue(0.002)
        self.md_dt.setSuffix(" ps")

        self.md_nsteps = QSpinBox()
        self.md_nsteps.setRange(100, 500000000)
        self.md_nsteps.setValue(50000000)
        self.md_nsteps.setSingleStep(100000)

        gpu_info = self._get_sys_gpu_info()
        cpu_cores = max(1, int(self._get_sys_cpu_cores()))

        self.md_engine = QComboBox()
        self.md_engine.addItems(["auto", "gpu", "cpu"])
        default_engine = "gpu" if gpu_info.get("available") else "cpu"
        self.md_engine.setCurrentText(default_engine)

        self.md_nt = QSpinBox()
        safe_cores = min(6, cpu_cores)
        self.md_nt.setRange(1, cpu_cores)
        self.md_nt.setValue(safe_cores)
        self.md_nt.setToolTip(f"建议GPU加速时使用4-12核，本机检测到{cpu_cores}个逻辑核心")

        self.md_pdb, md_pdb_layout = self._create_file_input(
            "protein.pdb", "protein.pdb",
            "PDB文件 (*.pdb *.gro);;所有文件 (*.*)",
            "选择输入PDB/GRO文件"
        )

        ggrid.addWidget(QLabel("力场:"), 0, 0)
        self.lbl_ff = ggrid.itemAtPosition(0, 0).widget()
        ggrid.addWidget(self.md_ff, 0, 1)
        ggrid.addWidget(QLabel("水模型:"), 0, 2)
        self.lbl_water = ggrid.itemAtPosition(0, 2).widget()
        ggrid.addWidget(self.md_water, 0, 3)

        ggrid.addWidget(QLabel("盒子类型:"), 1, 0)
        self.lbl_box_type = ggrid.itemAtPosition(1, 0).widget()
        ggrid.addWidget(self.md_box_type, 1, 1)
        self.lbl_box_mode = QLabel(tr("md_box_mode"))
        ggrid.addWidget(self.lbl_box_mode, 1, 2)
        ggrid.addWidget(self.md_box_size_mode, 1, 3)

        self.lbl_box_size = QLabel("盒子边距:")
        ggrid.addWidget(self.lbl_box_size, 6, 0)
        ggrid.addWidget(self.md_box_size, 6, 1, 1, 3)

        self.lbl_box_a = QLabel("盒子边长:")
        self.lbl_box_a.setVisible(False)
        ggrid.addWidget(self.lbl_box_a, 7, 0)
        self.md_box_a.setVisible(False)
        ggrid.addWidget(self.md_box_a, 7, 1, 1, 3)

        self.lbl_box_x = QLabel("X边长:")
        self.lbl_box_x.setVisible(False)
        ggrid.addWidget(self.lbl_box_x, 8, 0)
        self.md_box_x.setVisible(False)
        ggrid.addWidget(self.md_box_x, 8, 1)
        self.lbl_box_y = QLabel("Y边长:")
        self.lbl_box_y.setVisible(False)
        ggrid.addWidget(self.lbl_box_y, 8, 2)
        self.md_box_y.setVisible(False)
        ggrid.addWidget(self.md_box_y, 8, 3)

        self.lbl_box_z = QLabel("Z边长:")
        self.lbl_box_z.setVisible(False)
        ggrid.addWidget(self.lbl_box_z, 9, 0)
        self.md_box_z.setVisible(False)
        ggrid.addWidget(self.md_box_z, 9, 1)

        self.lbl_angle_alpha = QLabel("夹角α (bc):")
        self.lbl_angle_alpha.setVisible(False)
        ggrid.addWidget(self.lbl_angle_alpha, 10, 0)
        self.md_angle_alpha.setVisible(False)
        ggrid.addWidget(self.md_angle_alpha, 10, 1)
        self.lbl_angle_beta = QLabel("夹角β (ac):")
        self.lbl_angle_beta.setVisible(False)
        ggrid.addWidget(self.lbl_angle_beta, 10, 2)
        self.md_angle_beta.setVisible(False)
        ggrid.addWidget(self.md_angle_beta, 10, 3)

        self.lbl_angle_gamma = QLabel("夹角γ (ab):")
        self.lbl_angle_gamma.setVisible(False)
        ggrid.addWidget(self.lbl_angle_gamma, 11, 0)
        self.md_angle_gamma.setVisible(False)
        ggrid.addWidget(self.md_angle_gamma, 11, 1)
        ggrid.addWidget(self.md_princ, 11, 2, 1, 2)

        self.use_existing_top = QCheckBox("使用已有拓扑")
        self.use_existing_top.setChecked(False)
        self.use_existing_top.setToolTip("跳过pdb2gmx，直接使用已有的gro和top文件")
        ggrid.addWidget(self.use_existing_top, 12, 0, 1, 2)

        self.skip_solvate = QCheckBox("跳过溶剂化")
        self.skip_solvate.setChecked(False)
        self.skip_solvate.setToolTip("体系已包含溶剂，跳过solvate步骤")
        ggrid.addWidget(self.skip_solvate, 13, 0)

        self.skip_genion = QCheckBox("跳过加离子")
        self.skip_genion.setChecked(False)
        self.skip_genion.setToolTip("体系已带电平衡，跳过genion步骤")
        ggrid.addWidget(self.skip_genion, 13, 1)

        self.skip_editconf = QCheckBox("跳过盒子定义")
        self.skip_editconf.setChecked(False)
        self.skip_editconf.setToolTip("结构文件已有周期性盒子信息，跳过editconf步骤")
        ggrid.addWidget(self.skip_editconf, 14, 0)

        ggrid.addWidget(QLabel("离子浓度:"), 2, 0)
        self.lbl_ion = ggrid.itemAtPosition(2, 0).widget()
        ggrid.addWidget(self.md_ion_conc, 2, 1)
        self.lbl_temp = QLabel(tr("md_temp"))
        ggrid.addWidget(self.lbl_temp, 2, 2)
        ggrid.addWidget(self.md_temp, 2, 3)

        self.lbl_press = QLabel(tr("md_press"))
        ggrid.addWidget(self.lbl_press, 3, 0)
        ggrid.addWidget(self.md_pressure, 3, 1)
        self.lbl_dt = QLabel(tr("md_dt"))
        ggrid.addWidget(self.lbl_dt, 3, 2)
        ggrid.addWidget(self.md_dt, 3, 3)

        self.lbl_nsteps = QLabel(tr("md_nsteps"))
        ggrid.addWidget(self.lbl_nsteps, 4, 0)
        ggrid.addWidget(self.md_nsteps, 4, 1)
        self.lbl_engine = QLabel(tr("md_engine"))
        ggrid.addWidget(self.lbl_engine, 4, 2)
        ggrid.addWidget(self.md_engine, 4, 3)

        self.lbl_nt = QLabel(tr("md_nt"))
        ggrid.addWidget(self.lbl_nt, 5, 0)
        ggrid.addWidget(self.md_nt, 5, 1)
        ggrid.addWidget(QLabel("输入PDB:"), 5, 2)
        self.lbl_pdb = ggrid.itemAtPosition(5, 2).widget()
        ggrid.addLayout(md_pdb_layout, 5, 3)

        vbox.addWidget(self.common_group)

        self.md_step_btns = {}

        # === 第一阶段: 结构准备 ===
        self.prep_phase = QGroupBox(tr("md_phase_prep"))
        self.prep_phase.setProperty("role", "phaseGroup")
        prep_layout = QVBoxLayout(self.prep_phase)
        prep_layout.setSpacing(6)

        step1 = self._create_step_group(
            "Step 1: 生成拓扑 (pdb2gmx)",
            "从 PDB 文件生成拓扑结构",
            ["输入PDB:", "输出GRO:", "拓扑TOP:", "位置限制ITP:"],
            ["protein.gro", "topol.top", "posre.itp"]
        )
        self.step1_widget = step1
        prep_layout.addWidget(step1)

        self.step1_existing = QGroupBox("Step 1: 使用已有拓扑")
        self.step1_existing.setProperty("role", "toolCard")
        self.step1_existing.setVisible(False)
        se_layout = QGridLayout(self.step1_existing)
        se_layout.setSpacing(6)
        desc_se = QLabel("直接使用已有的结构和拓扑文件，跳过pdb2gmx")
        desc_se.setProperty("role", "desc")
        se_layout.addWidget(desc_se, 0, 0, 1, 4)

        se_layout.addWidget(QLabel("输入结构:"), 1, 0)
        self.se_gro_edit, se_gro_layout = self._create_file_input("选择已有结构文件", "input.gro", "结构文件 (*.gro *.pdb)", "选择GRO/PDB文件")
        se_layout.addLayout(se_gro_layout, 1, 1, 1, 3)

        se_layout.addWidget(QLabel("输入TOP:"), 2, 0)
        self.se_top_edit, se_top_layout = self._create_file_input("选择已有拓扑文件", "topol.top", "拓扑文件 (*.top)", "选择TOP文件")
        se_layout.addLayout(se_top_layout, 2, 1, 1, 3)

        self.se_run_btn = QPushButton("确认使用已有拓扑")
        self.se_run_btn.setProperty("role", "actionBtn")
        self.se_run_btn.clicked.connect(lambda: self.run_md_step("Step 1"))
        se_layout.addWidget(self.se_run_btn, 3, 0, 1, 4)

        prep_layout.addWidget(self.step1_existing)

        self.use_existing_top.toggled.connect(self._on_use_existing_toggled)
        self.skip_editconf.toggled.connect(self._on_skip_toggled)
        self.skip_solvate.toggled.connect(self._on_skip_toggled)
        self.skip_genion.toggled.connect(self._on_skip_toggled)

        step2 = self._create_editconf_step()
        prep_layout.addWidget(step2)

        step3 = self._create_step_group(
            "Step 3: 溶剂化 (solvate)",
            "向盒子中添加溶剂水分子",
            ["输入GRO:", "输出GRO:", "输出TOP:"],
            ["protein_solv.gro", "topol.top"]
        )
        prep_layout.addWidget(step3)

        step4 = self._create_step_group(
            "Step 4: 添加离子 (genion)",
            "用离子替换溶剂分子以中和体系",
            ["输入GRO:", "输出GRO:", "输出TOP:", "输入MDP:"],
            ["protein_ions.gro", "topol.top", "ions.mdp"]
        )
        prep_layout.addWidget(step4)

        vbox.addWidget(self.prep_phase)

        # === 第二阶段: 能量最小化 ===
        self.em_phase = QGroupBox(tr("md_phase_em"))
        self.em_phase.setProperty("role", "phaseGroup")
        em_layout = QVBoxLayout(self.em_phase)
        em_layout.setSpacing(6)

        step5 = self._create_step_group(
            "Step 5: grompp (EM)",
            "编译能量最小化输入文件",
            ["输入MDP:", "输入GRO:", "输出TPR:"],
            ["em.mdp", "ions.gro", "em.tpr"]
        )
        em_layout.addWidget(step5)

        step6 = self._create_step_group(
            "Step 6: 能量最小化 (mdrun EM)",
            "执行能量最小化消除不良接触",
            ["输入TPR:", "输出GRO:", "输出EDR:", "输出LOG:"],
            ["em.tpr", "em.gro", "em.edr", "em.log"]
        )
        em_layout.addWidget(step6)

        vbox.addWidget(self.em_phase)

        # === 第三阶段: 平衡模拟 ===
        self.equil_phase = QGroupBox(tr("md_phase_equil"))
        self.equil_phase.setProperty("role", "phaseGroup")
        equil_layout = QVBoxLayout(self.equil_phase)
        equil_layout.setSpacing(6)

        step7 = self._create_step_group(
            "Step 7: grompp (NVT)",
            "编译NVT平衡输入文件",
            ["输入MDP:", "输入GRO:", "输出TPR:"],
            ["nvt.mdp", "em.gro", "nvt.tpr"]
        )
        equil_layout.addWidget(step7)

        step8 = self._create_step_group(
            "Step 8: NVT 平衡 (mdrun NVT)",
            "恒定体积和温度下平衡",
            ["输入TPR:", "输出TRR/XTC:", "输出EDR:", "输出LOG:"],
            ["nvt.tpr", "nvt.xtc", "nvt.edr", "nvt.log"]
        )
        equil_layout.addWidget(step8)

        step9 = self._create_step_group(
            "Step 9: grompp (NPT)",
            "编译NPT平衡输入文件",
            ["输入MDP:", "输入GRO/CPR:", "输出TPR:"],
            ["npt.mdp", "nvt.gro", "npt.tpr"]
        )
        equil_layout.addWidget(step9)

        step10 = self._create_step_group(
            "Step 10: NPT 平衡 (mdrun NPT)",
            "恒定压力和温度下平衡",
            ["输入TPR:", "输出TRR/XTC:", "输出EDR:", "输出LOG:"],
            ["npt.tpr", "npt.xtc", "npt.edr", "npt.log"]
        )
        equil_layout.addWidget(step10)

        vbox.addWidget(self.equil_phase)

        # === 第四阶段: 生产模拟 ===
        self.prod_phase = QGroupBox(tr("md_phase_prod"))
        self.prod_phase.setProperty("role", "phaseGroup")
        prod_layout = QVBoxLayout(self.prod_phase)
        prod_layout.setSpacing(6)

        step11 = self._create_step_group(
            "Step 11: grompp (MD)",
            "编译生产模拟输入文件",
            ["输入MDP:", "输入GRO/CPR:", "输出TPR:"],
            ["md.mdp", "npt.gro", "md.tpr"]
        )
        prod_layout.addWidget(step11)

        step12 = self._create_step_group(
            "Step 12: 生产模拟 (mdrun MD)",
            "执行最终生产模拟",
            ["输入TPR:", "输出TRR/XTC:", "输出EDR:", "输出LOG:"],
            ["md.tpr", "md.xtc", "md.edr", "md.log"]
        )
        prod_layout.addWidget(step12)

        vbox.addWidget(self.prod_phase)

        # === 第五阶段: 溶剂/添加剂蒸发 ===
        self.evap_phase = QGroupBox(tr("md_phase_evap"))
        self.evap_phase.setProperty("role", "phaseGroup")
        evap_layout = QVBoxLayout(self.evap_phase)
        evap_layout.setSpacing(8)

        evap_config = QGroupBox("蒸发配置")
        evap_grid = QGridLayout(evap_config)
        evap_grid.setSpacing(6)

        evap_grid.addWidget(QLabel("蒸发模式:"), 0, 0)
        self.evap_mode = QComboBox()
        self.evap_mode.addItems(["分批蒸发溶剂（循环删除+NPT）", "一次性删除全部添加剂"])
        evap_grid.addWidget(self.evap_mode, 0, 1, 1, 3)

        evap_grid.addWidget(QLabel("输入GRO:"), 1, 0)
        self.evap_gro_edit, gro_layout = self._create_file_input("输入GRO文件", "npt2.gro", "结构文件 (*.gro *.pdb);;所有文件 (*.*)", "选择GRO文件")
        evap_grid.addLayout(gro_layout, 1, 1, 1, 3)

        evap_grid.addWidget(QLabel("拓扑TOP:"), 2, 0)
        self.evap_top_edit, top_layout = self._create_file_input("拓扑TOP文件", "topol.top", "拓扑文件 (*.top *.itp);;所有文件 (*.*)", "选择TOP文件")
        evap_grid.addLayout(top_layout, 2, 1, 1, 3)

        evap_grid.addWidget(QLabel("MDP文件:"), 3, 0)
        self.evap_mdp_edit, mdp_layout = self._create_file_input("NPT参数文件(MDP)", "npt-sa.mdp", "MDP文件 (*.mdp);;所有文件 (*.*)", "选择MDP文件")
        evap_grid.addLayout(mdp_layout, 3, 1, 1, 3)

        evap_grid.addWidget(QLabel("残基名:"), 4, 0)
        self.evap_resname = QLineEdit("CF")
        self.evap_resname.setFixedWidth(80)
        evap_grid.addWidget(self.evap_resname, 4, 1)

        evap_grid.addWidget(QLabel("原子数/分子:"), 4, 2)
        self.evap_atoms_per_mol = QSpinBox()
        self.evap_atoms_per_mol.setRange(1, 1000)
        self.evap_atoms_per_mol.setValue(5)
        evap_grid.addWidget(self.evap_atoms_per_mol, 4, 3)

        evap_grid.addWidget(QLabel("蒸发来源:"), 5, 0)
        self.evap_source = QComboBox()
        self.evap_source.addItems(["从底部删除（先蒸发最底下的组）", "从顶部删除（先蒸发最上面的组）"])
        evap_grid.addWidget(self.evap_source, 5, 1, 1, 3)

        self.evap_label_delete = QLabel("每轮删除数:")
        evap_grid.addWidget(self.evap_label_delete, 6, 0)
        self.evap_delete_num = QSpinBox()
        self.evap_delete_num.setRange(1, 100000)
        self.evap_delete_num.setValue(100)
        evap_grid.addWidget(self.evap_delete_num, 6, 1)

        self.evap_label_loops = QLabel("循环轮数:")
        evap_grid.addWidget(self.evap_label_loops, 6, 2)
        self.evap_loops = QSpinBox()
        self.evap_loops.setRange(1, 100000)
        self.evap_loops.setValue(500)
        evap_grid.addWidget(self.evap_loops, 6, 3)

        evap_grid.addWidget(QLabel("输出前缀:"), 7, 0)
        self.evap_prefix = QLineEdit("evap")
        evap_grid.addWidget(self.evap_prefix, 7, 1, 1, 3)

        self.evap_restart_check = QCheckBox("断点续跑")
        evap_grid.addWidget(self.evap_restart_check, 8, 0)

        self.evap_start_loop_label = QLabel("起始轮数:")
        self.evap_start_loop_label.setVisible(False)
        evap_grid.addWidget(self.evap_start_loop_label, 8, 1)

        self.evap_start_loop = QSpinBox()
        self.evap_start_loop.setRange(1, 100000)
        self.evap_start_loop.setValue(1)
        self.evap_start_loop.setVisible(False)
        evap_grid.addWidget(self.evap_start_loop, 8, 2)

        self.evap_mode.currentIndexChanged.connect(self._on_evap_mode_changed)
        self.evap_restart_check.stateChanged.connect(self._on_evap_restart_changed)

        self.evap_mode.setCurrentIndex(0)
        self._on_evap_mode_changed()

        evap_layout.addWidget(evap_config)

        tip = QLabel("💡 分批蒸发: 每轮删除N个溶剂分子后跑10ps NPT，循环指定轮数\n💡 删除全部添加剂: 一次性删除所有指定残基分子后跑NPT")
        tip.setProperty("role", "desc")
        tip.setWordWrap(True)
        evap_layout.addWidget(tip)

        self.evap_run_btn = QPushButton("🚀 开始蒸发")
        self.evap_run_btn.setProperty("role", "primaryRun")
        self.evap_run_btn.clicked.connect(self.run_evap_step)
        evap_layout.addWidget(self.evap_run_btn)

        vbox.addWidget(self.evap_phase)

        # === 第六阶段: 退火模拟 ===
        self.anneal_phase = QGroupBox(tr("md_phase_anneal"))
        self.anneal_phase.setProperty("role", "phaseGroup")
        anneal_layout = QVBoxLayout(self.anneal_phase)
        anneal_layout.setSpacing(8)

        anneal_config = QGroupBox("退火配置")
        anneal_grid = QGridLayout(anneal_config)
        anneal_grid.setSpacing(6)

        anneal_grid.addWidget(QLabel("输入GRO:"), 0, 0)
        self.anneal_gro_edit, ag_layout = self._create_file_input("输入GRO文件", "npt.gro", "结构文件 (*.gro *.pdb);;所有文件 (*.*)", "选择GRO文件")
        anneal_grid.addLayout(ag_layout, 0, 1, 1, 3)

        anneal_grid.addWidget(QLabel("拓扑TOP:"), 1, 0)
        self.anneal_top_edit, at_layout = self._create_file_input("拓扑TOP文件", "topol.top", "拓扑文件 (*.top *.itp);;所有文件 (*.*)", "选择TOP文件")
        anneal_grid.addLayout(at_layout, 1, 1, 1, 3)

        anneal_grid.addWidget(QLabel("输出前缀:"), 2, 0)
        self.anneal_prefix = QLineEdit("anneal")
        anneal_grid.addWidget(self.anneal_prefix, 2, 1)

        anneal_grid.addWidget(QLabel("退火模式:"), 2, 2)
        self.anneal_mode = QComboBox()
        self.anneal_mode.addItems(["single (单次退火)", "periodic (周期退火)"])
        anneal_grid.addWidget(self.anneal_mode, 2, 3)

        curve_label = QLabel("退火曲线 (时间-温度点对):")
        curve_label.setProperty("role", "desc")
        anneal_grid.addWidget(curve_label, 3, 0, 1, 4)

        self.anneal_table = QTableWidget(7, 2)
        self.anneal_table.setHorizontalHeaderLabels(["时间 (ps)", "温度 (K)"])
        self.anneal_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.anneal_table.setMinimumHeight(160)
        default_times = ["0", "100", "300", "500", "700", "900", "1000"]
        default_temps = ["300", "373", "373", "373", "373", "300", "300"]
        for i in range(7):
            self.anneal_table.setItem(i, 0, QTableWidgetItem(default_times[i]))
            self.anneal_table.setItem(i, 1, QTableWidgetItem(default_temps[i]))
        anneal_grid.addWidget(self.anneal_table, 4, 0, 1, 4)

        table_btn_layout = QHBoxLayout()
        add_row_btn = QPushButton("+ 添加行")
        add_row_btn.setProperty("role", "secondaryTool")
        add_row_btn.clicked.connect(lambda: self.anneal_table.insertRow(self.anneal_table.rowCount()))
        table_btn_layout.addWidget(add_row_btn)

        del_row_btn = QPushButton("- 删除选中行")
        del_row_btn.setProperty("role", "secondaryTool")
        del_row_btn.clicked.connect(lambda: self.anneal_table.removeRow(self.anneal_table.currentRow()) if self.anneal_table.currentRow() >= 0 else None)
        table_btn_layout.addWidget(del_row_btn)

        reset_curve_btn = QPushButton("↻ 重置默认曲线")
        reset_curve_btn.setProperty("role", "secondaryTool")
        reset_curve_btn.clicked.connect(self._reset_anneal_curve)
        table_btn_layout.addWidget(reset_curve_btn)

        table_btn_layout.addStretch()
        anneal_grid.addLayout(table_btn_layout, 5, 0, 1, 4)

        curve_tip = QLabel("💡 默认曲线: 300K → 373K (保温) → 300K，模拟1ns\n💡 时间点必须递增，点数需与温度点数一致\n💡 生成MDP后会自动执行 grompp + mdrun")
        curve_tip.setProperty("role", "desc")
        curve_tip.setWordWrap(True)
        anneal_grid.addWidget(curve_tip, 6, 0, 1, 4)

        anneal_layout.addWidget(anneal_config)

        self.anneal_run_btn = QPushButton("🚀 开始退火模拟")
        self.anneal_run_btn.setProperty("role", "primaryRun")
        self.anneal_run_btn.clicked.connect(self.run_anneal_step)
        anneal_layout.addWidget(self.anneal_run_btn)

        vbox.addWidget(self.anneal_phase)
        vbox.addStretch()

    def _on_evap_mode_changed(self):
        is_batch = self.evap_mode.currentIndex() == 0
        self.evap_label_delete.setVisible(is_batch)
        self.evap_delete_num.setVisible(is_batch)
        self.evap_label_loops.setVisible(is_batch)
        self.evap_loops.setVisible(is_batch)
        self.evap_restart_check.setVisible(is_batch)
        self.evap_start_loop_label.setVisible(is_batch and self.evap_restart_check.isChecked())
        self.evap_start_loop.setVisible(is_batch and self.evap_restart_check.isChecked())

    def _on_evap_restart_changed(self, state):
        is_checked = state == Qt.Checked
        self.evap_start_loop_label.setVisible(is_checked)
        self.evap_start_loop.setVisible(is_checked)
        if is_checked:
            self.evap_start_loop_label.show()
            self.evap_start_loop.show()

    def _create_editconf_step(self):
        title = "Step 2: 定义模拟盒子 (editconf)"
        group = QGroupBox(title)
        group.setProperty("role", "toolCard")
        layout = QGridLayout(group)
        layout.setSpacing(6)

        desc = QLabel("设置模拟盒子类型和大小")
        desc.setProperty("role", "desc")
        layout.addWidget(desc, 0, 0, 1, 4)

        row = 1
        input_gro_edit = QLineEdit("protein.gro")
        layout.addWidget(QLabel("输入GRO:"), row, 0)
        hlayout = QHBoxLayout()
        hlayout.addWidget(input_gro_edit, stretch=1)
        btn = QPushButton("浏览")
        btn.setFixedWidth(55)
        btn.setToolTip("浏览文件")
        btn.setProperty("role", "browseBtn")
        btn.clicked.connect(lambda: self._browse_file(input_gro_edit, "选择结构文件", "结构文件 (*.gro *.pdb);;所有文件 (*.*)"))
        hlayout.addWidget(btn)
        layout.addLayout(hlayout, row, 1, 1, 3)
        row += 1

        output_gro_edit = QLineEdit("protein_box.gro")
        layout.addWidget(QLabel("输出GRO:"), row, 0)
        hlayout = QHBoxLayout()
        hlayout.addWidget(output_gro_edit, stretch=1)
        btn = QPushButton("浏览")
        btn.setFixedWidth(55)
        btn.setToolTip("浏览文件")
        btn.setProperty("role", "browseBtn")
        btn.clicked.connect(lambda: self._browse_file(output_gro_edit, "保存结构文件", "结构文件 (*.gro *.pdb);;所有文件 (*.*)"))
        hlayout.addWidget(btn)
        layout.addLayout(hlayout, row, 1, 1, 3)
        row += 1

        layout.addWidget(QLabel("盒子类型:"), row, 0)
        box_type_combo = QComboBox()
        box_type_combo.addItems([
            "cubic (立方体)",
            "triclinic (三斜)",
            "dodecahedron (十二面体)",
            "octahedron (八面体)",
            "rectangular (长方体)"
        ])
        layout.addWidget(box_type_combo, row, 1, 1, 3)
        row += 1

        layout.addWidget(QLabel("设置方式:"), row, 0)
        size_mode_combo = QComboBox()
        size_mode_combo.addItem("按边距 (-d)", "margin")
        size_mode_combo.addItem("按盒子边长 (-box)", "box")
        layout.addWidget(size_mode_combo, row, 1, 1, 3)
        row += 1

        box_size_label = QLabel("盒子边距:")
        layout.addWidget(box_size_label, row, 0)
        box_size_spin = QDoubleSpinBox()
        box_size_spin.setRange(0.1, 100.0)
        box_size_spin.setValue(1.0)
        box_size_spin.setDecimals(2)
        box_size_spin.setSuffix(" nm")
        layout.addWidget(box_size_spin, row, 1, 1, 3)
        row += 1

        box_a_label = QLabel("边长a:")
        box_a_label.setVisible(False)
        layout.addWidget(box_a_label, row, 0)
        box_a_spin = QDoubleSpinBox()
        box_a_spin.setRange(0.1, 500.0)
        box_a_spin.setValue(5.0)
        box_a_spin.setDecimals(2)
        box_a_spin.setSuffix(" nm")
        box_a_spin.setVisible(False)
        layout.addWidget(box_a_spin, row, 1, 1, 3)
        row += 1

        box_x_label = QLabel("X边长:")
        box_x_label.setVisible(False)
        layout.addWidget(box_x_label, row, 0)
        box_x_spin = QDoubleSpinBox()
        box_x_spin.setRange(0.1, 500.0)
        box_x_spin.setValue(5.0)
        box_x_spin.setDecimals(2)
        box_x_spin.setSuffix(" nm")
        box_x_spin.setVisible(False)
        layout.addWidget(box_x_spin, row, 1)
        box_y_label = QLabel("Y边长:")
        box_y_label.setVisible(False)
        layout.addWidget(box_y_label, row, 2)
        box_y_spin = QDoubleSpinBox()
        box_y_spin.setRange(0.1, 500.0)
        box_y_spin.setValue(5.0)
        box_y_spin.setDecimals(2)
        box_y_spin.setSuffix(" nm")
        box_y_spin.setVisible(False)
        layout.addWidget(box_y_spin, row, 3)
        row += 1

        box_z_label = QLabel("Z边长:")
        box_z_label.setVisible(False)
        layout.addWidget(box_z_label, row, 0)
        box_z_spin = QDoubleSpinBox()
        box_z_spin.setRange(0.1, 500.0)
        box_z_spin.setValue(5.0)
        box_z_spin.setDecimals(2)
        box_z_spin.setSuffix(" nm")
        box_z_spin.setVisible(False)
        layout.addWidget(box_z_spin, row, 1)
        row += 1

        angle_alpha_label = QLabel("夹角α (bc):")
        angle_alpha_label.setVisible(False)
        layout.addWidget(angle_alpha_label, row, 0)
        angle_alpha_spin = QDoubleSpinBox()
        angle_alpha_spin.setRange(1.0, 179.0)
        angle_alpha_spin.setValue(90.0)
        angle_alpha_spin.setDecimals(1)
        angle_alpha_spin.setSuffix(" °")
        angle_alpha_spin.setVisible(False)
        layout.addWidget(angle_alpha_spin, row, 1)
        angle_beta_label = QLabel("夹角β (ac):")
        angle_beta_label.setVisible(False)
        layout.addWidget(angle_beta_label, row, 2)
        angle_beta_spin = QDoubleSpinBox()
        angle_beta_spin.setRange(1.0, 179.0)
        angle_beta_spin.setValue(90.0)
        angle_beta_spin.setDecimals(1)
        angle_beta_spin.setSuffix(" °")
        angle_beta_spin.setVisible(False)
        layout.addWidget(angle_beta_spin, row, 3)
        row += 1

        angle_gamma_label = QLabel("夹角γ (ab):")
        angle_gamma_label.setVisible(False)
        layout.addWidget(angle_gamma_label, row, 0)
        angle_gamma_spin = QDoubleSpinBox()
        angle_gamma_spin.setRange(1.0, 179.0)
        angle_gamma_spin.setValue(90.0)
        angle_gamma_spin.setDecimals(1)
        angle_gamma_spin.setSuffix(" °")
        angle_gamma_spin.setVisible(False)
        layout.addWidget(angle_gamma_spin, row, 1)
        row += 1

        center_check = QCheckBox("分子居中 (-c)")
        center_check.setChecked(True)
        center_check.setToolTip("将分子放在盒子中心")
        layout.addWidget(center_check, row, 0, 1, 2)
        princ_check = QCheckBox("主惯性轴对齐 (-princ)")
        princ_check.setChecked(False)
        princ_check.setToolTip("将分子对齐到主惯性轴，使盒子更紧凑")
        layout.addWidget(princ_check, row, 2, 1, 2)
        row += 1

        def _on_box_type_changed(text):
            is_rect = "rectangular" in text.lower()
            is_triclinic = "triclinic" in text.lower()
            is_box_mode = (size_mode_combo.currentData() == "box") or ("-box" in size_mode_combo.currentText().lower()) or ("边长" in size_mode_combo.currentText())
            is_single_val = is_box_mode and not is_rect and not is_triclinic
            show_xyz = is_rect and is_box_mode
            show_angles = is_triclinic and is_box_mode
            box_a_label.setText("盒子边长:" if not is_triclinic else "边长a:")
            box_a_label.setVisible(is_single_val or (is_triclinic and is_box_mode))
            box_a_spin.setVisible(is_single_val or (is_triclinic and is_box_mode))
            box_x_label.setVisible(show_xyz)
            box_x_spin.setVisible(show_xyz)
            box_y_label.setVisible(show_xyz)
            box_y_spin.setVisible(show_xyz)
            box_z_label.setVisible(show_xyz)
            box_z_spin.setVisible(show_xyz)
            angle_alpha_label.setVisible(show_angles)
            angle_alpha_spin.setVisible(show_angles)
            angle_beta_label.setVisible(show_angles)
            angle_beta_spin.setVisible(show_angles)
            angle_gamma_label.setVisible(show_angles)
            angle_gamma_spin.setVisible(show_angles)
            box_size_label.setVisible(not is_box_mode)
            box_size_spin.setVisible(not is_box_mode)

        def _on_size_mode_changed(text):
            _on_box_type_changed(box_type_combo.currentText())

        box_type_combo.currentTextChanged.connect(_on_box_type_changed)
        size_mode_combo.currentTextChanged.connect(_on_size_mode_changed)

        run_btn = QPushButton("运行此步骤")
        run_btn.setProperty("role", "actionBtn")
        layout.addWidget(run_btn, row, 0, 1, 2)
        row += 1

        key = "Step 2"
        self.md_step_btns[key] = {
            "group": group,
            "edits": [input_gro_edit, output_gro_edit],
            "run_btn": run_btn,
            "labels": ["输入GRO:", "输出GRO:"],
            "box_type_combo": box_type_combo,
            "size_mode_combo": size_mode_combo,
            "box_size_spin": box_size_spin,
            "box_a_spin": box_a_spin,
            "box_x_spin": box_x_spin,
            "box_y_spin": box_y_spin,
            "box_z_spin": box_z_spin,
            "angle_alpha_spin": angle_alpha_spin,
            "angle_beta_spin": angle_beta_spin,
            "angle_gamma_spin": angle_gamma_spin,
            "center_check": center_check,
            "princ_check": princ_check
        }
        run_btn.clicked.connect(lambda: self.run_md_step(key))
        return group

    def _create_step_group(self, title, description, labels, defaults):
        group = QGroupBox(title)
        group.setProperty("role", "toolCard")
        layout = QGridLayout(group)
        layout.setSpacing(6)

        desc = QLabel(description)
        desc.setProperty("role", "desc")
        layout.addWidget(desc, 0, 0, 1, 4)

        def _file_filter_for_label(lbl):
            low = lbl.lower()
            if "pdb" in low:
                return "PDB文件 (*.pdb *.gro);;所有文件 (*.*)", "选择PDB/GRO文件"
            if "gro" in low:
                return "结构文件 (*.gro *.pdb);;所有文件 (*.*)", "选择结构文件"
            if "top" in low:
                return "拓扑文件 (*.top *.itp);;所有文件 (*.*)", "选择拓扑文件"
            if "mdp" in low:
                return "MDP参数文件 (*.mdp);;所有文件 (*.*)", "选择MDP文件"
            if "tpr" in low:
                return "TPR输入文件 (*.tpr);;所有文件 (*.*)", "选择TPR文件"
            if "itp" in low:
                return "ITP拓扑文件 (*.itp *.top);;所有文件 (*.*)", "选择ITP文件"
            if "edr" in low:
                return "能量文件 (*.edr);;所有文件 (*.*)", "选择EDR文件"
            if "log" in low:
                return "日志文件 (*.log);;所有文件 (*.*)", "选择日志文件"
            if "xtc" in low or "trr" in low:
                return "轨迹文件 (*.xtc *.trr);;所有文件 (*.*)", "选择轨迹文件"
            return "所有文件 (*.*)", "选择文件"

        edits = []
        row = 1
        for i, lbl in enumerate(labels):
            le = QLineEdit()
            le.setPlaceholderText(defaults[i] if i < len(defaults) else "")
            if i < len(defaults):
                le.setText(defaults[i])
            edits.append(le)
            layout.addWidget(QLabel(lbl), row, 0)
            ffilter, ftitle = _file_filter_for_label(lbl)
            hlayout = QHBoxLayout()
            hlayout.addWidget(le, stretch=1)
            btn = QPushButton("浏览")
            btn.setFixedWidth(55)
            btn.setToolTip("浏览文件")
            btn.setProperty("role", "browseBtn")
            btn.clicked.connect(lambda checked=False, edit=le, ft=ftitle, ff=ffilter: self._browse_file(edit, ft, ff))
            hlayout.addWidget(btn)
            layout.addLayout(hlayout, row, 1, 1, 3)
            row += 1

        run_btn = QPushButton("运行此步骤")
        run_btn.setProperty("role", "actionBtn")
        layout.addWidget(run_btn, row, 0, 1, 2)

        if any("MDP" in l for l in labels):
            mdp_type_key = "ions"
            if "EM" in title:
                mdp_type_key = "em"
            elif "NVT" in title:
                mdp_type_key = "nvt"
            elif "NPT" in title:
                mdp_type_key = "npt"
            elif "生产" in title or "MD" in title.split(":")[0]:
                mdp_type_key = "md"

            mdp_btn = QPushButton("生成默认MDP")
            mdp_btn.setProperty("role", "secondaryTool")
            mdp_btn.clicked.connect(lambda checked=False, t=mdp_type_key: self.generate_mdp_template(t))
            layout.addWidget(mdp_btn, row, 2)

            adv_mdp_btn = QPushButton("高级编辑器")
            adv_mdp_btn.setProperty("role", "secondaryTool")
            adv_mdp_btn.clicked.connect(lambda checked=False, t=mdp_type_key: self._open_mdp_editor(t))
            adv_mdp_btn.setToolTip("打开高级MDP参数可视化编辑器")
            layout.addWidget(adv_mdp_btn, row, 3)

        row += 1

        key = title.split(":")[0].strip()
        is_mdrun = "mdrun" in title
        custom_out_check = None
        custom_out_edit = None
        custom_out_label = None

        if is_mdrun:
            custom_out_check = QCheckBox("自定义输出前缀")
            custom_out_check.setChecked(False)
            custom_out_check.setToolTip("勾选后可自定义输出文件名前缀，不勾选则使用输入TPR文件名作为前缀")
            layout.addWidget(custom_out_check, row, 0, 1, 2)
            row += 1

            custom_out_label = QLabel("输出前缀:")
            custom_out_label.setVisible(False)
            layout.addWidget(custom_out_label, row, 0)

            custom_out_edit = QLineEdit()
            custom_out_edit.setVisible(False)
            custom_out_edit.setPlaceholderText("输入输出文件名前缀")
            layout.addWidget(custom_out_edit, row, 1, 1, 3)
            row += 1

            restart_check = QCheckBox("断点续跑 (从CPT文件恢复)")
            restart_check.setChecked(False)
            restart_check.setToolTip("勾选后自动检测工作目录下的.cpt文件并续跑，适用于中断后恢复模拟")
            layout.addWidget(restart_check, row, 0, 1, 2)
            row += 1

            def _on_custom_out_toggled(checked):
                custom_out_label.setVisible(checked)
                custom_out_edit.setVisible(checked)
                for i, lbl in enumerate(labels):
                    if "输出" in lbl and i < len(edits):
                        edits[i].setVisible(checked)
                        lbl_widget = layout.itemAtPosition(i + 1, 0)
                        if lbl_widget and lbl_widget.widget():
                            lbl_widget.widget().setVisible(checked)

            custom_out_check.toggled.connect(_on_custom_out_toggled)

            for i, lbl in enumerate(labels):
                if "输出" in lbl and i < len(edits):
                    edits[i].setVisible(False)
                    lbl_widget = layout.itemAtPosition(i + 1, 0)
                    if lbl_widget and lbl_widget.widget():
                        lbl_widget.widget().setVisible(False)

        self.md_step_btns[key] = {
            "group": group,
            "edits": edits,
            "run_btn": run_btn,
            "labels": labels,
            "custom_out_check": custom_out_check,
            "custom_out_edit": custom_out_edit,
            "restart_check": restart_check if is_mdrun else None
        }
        run_btn.clicked.connect(lambda checked=False, k=key: self.run_md_step(k))
        return group

    def _on_box_size_mode_changed(self, text):
        self._on_box_type_changed(self.md_box_type.currentText())

    def _on_box_type_changed(self, text):
        is_rect = "rectangular" in text.lower()
        is_triclinic = "triclinic" in text.lower()
        is_box_mode = (self.md_box_size_mode.currentData() == "box") or ("-box" in self.md_box_size_mode.currentText().lower()) or ("边长" in self.md_box_size_mode.currentText())
        is_single_val = is_box_mode and not is_rect and not is_triclinic
        show_xyz = is_rect and is_box_mode
        show_angles = is_triclinic and is_box_mode

        self.lbl_box_size.setVisible(not is_box_mode)
        self.md_box_size.setVisible(not is_box_mode)

        self.lbl_box_a.setVisible(is_single_val)
        self.md_box_a.setVisible(is_single_val)
        if is_single_val:
            self.lbl_box_a.setText("盒子边长:")

        self.lbl_box_x.setVisible(show_xyz)
        self.md_box_x.setVisible(show_xyz)
        self.lbl_box_y.setVisible(show_xyz)
        self.md_box_y.setVisible(show_xyz)
        self.lbl_box_z.setVisible(show_xyz)
        self.md_box_z.setVisible(show_xyz)

        self.lbl_angle_alpha.setVisible(show_angles)
        self.md_angle_alpha.setVisible(show_angles)
        self.lbl_angle_beta.setVisible(show_angles)
        self.md_angle_beta.setVisible(show_angles)
        self.lbl_angle_gamma.setVisible(show_angles)
        self.md_angle_gamma.setVisible(show_angles)
        if is_triclinic and is_box_mode:
            self.lbl_box_a.setText("边长a:")

    def _get_box_params(self):
        bt_full = self.md_box_type.currentText()
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
        is_box_mode = (self.md_box_size_mode.currentData() == "box") or ("-box" in self.md_box_size_mode.currentText().lower()) or ("边长" in self.md_box_size_mode.currentText())
        params = []
        if self.md_princ.isChecked():
            params.append("-princ")
        if is_box_mode:
            if is_rect:
                x = self.md_box_x.value()
                y = self.md_box_y.value()
                z = self.md_box_z.value()
                params += ["-box", str(x), str(y), str(z)]
            elif is_triclinic:
                a = self.md_box_a.value()
                alpha = self.md_angle_alpha.value()
                beta = self.md_angle_beta.value()
                gamma = self.md_angle_gamma.value()
                params += ["-box", str(a), str(a), str(a), "-angles", str(alpha), str(beta), str(gamma)]
            else:
                a = self.md_box_a.value()
                params += ["-box", str(a), "-bt", bt]
        else:
            d = self.md_box_size.value()
            params += ["-c", "-d", str(d), "-bt", bt]
        return params

    def _on_use_existing_toggled(self, checked):
        self.step1_widget.setVisible(not checked)
        self.step1_existing.setVisible(checked)

        if hasattr(self, 'lbl_ff'):
            self.lbl_ff.setVisible(not checked)
        self.md_ff.setVisible(not checked)
        if hasattr(self, 'lbl_water'):
            self.lbl_water.setVisible(not checked)
        self.md_water.setVisible(not checked)

        if hasattr(self, 'lbl_box_type'):
            self.lbl_box_type.setVisible(not checked)
        self.md_box_type.setVisible(not checked)
        self.md_box_size_mode.setVisible(not checked)

        self.lbl_box_size.setVisible(not checked and (self.md_box_size_mode.currentData() != "box"))
        self.md_box_size.setVisible(not checked and (self.md_box_size_mode.currentData() != "box"))

        self.lbl_box_a.setVisible(not checked and self.lbl_box_a.isVisible())
        self.md_box_a.setVisible(not checked and self.md_box_a.isVisible())

        self.lbl_box_x.setVisible(not checked and self.lbl_box_x.isVisible())
        self.md_box_x.setVisible(not checked and self.md_box_x.isVisible())
        self.lbl_box_y.setVisible(not checked and self.lbl_box_y.isVisible())
        self.md_box_y.setVisible(not checked and self.md_box_y.isVisible())
        self.lbl_box_z.setVisible(not checked and self.lbl_box_z.isVisible())
        self.md_box_z.setVisible(not checked and self.md_box_z.isVisible())

        self.lbl_angle_alpha.setVisible(not checked and self.lbl_angle_alpha.isVisible())
        self.md_angle_alpha.setVisible(not checked and self.md_angle_alpha.isVisible())
        self.lbl_angle_beta.setVisible(not checked and self.lbl_angle_beta.isVisible())
        self.md_angle_beta.setVisible(not checked and self.md_angle_beta.isVisible())
        self.lbl_angle_gamma.setVisible(not checked and self.lbl_angle_gamma.isVisible())
        self.md_angle_gamma.setVisible(not checked and self.md_angle_gamma.isVisible())

        self.md_princ.setVisible(not checked)

        if hasattr(self, 'lbl_ion'):
            self.lbl_ion.setVisible(not checked)
        self.md_ion_conc.setVisible(not checked)

        if hasattr(self, 'lbl_pdb'):
            self.lbl_pdb.setVisible(not checked)
        self.md_pdb.setVisible(not checked)

        if checked:
            self.skip_editconf.setChecked(True)
            self.skip_solvate.setChecked(True)
            self.skip_genion.setChecked(True)
            if "Step 2" in self.md_step_btns:
                step2_info = self.md_step_btns["Step 2"]
                edits = step2_info["edits"]
                if edits:
                    edits[0].setText(self.se_gro_edit.text().strip() or "input.gro")
            if "Step 3" in self.md_step_btns:
                step3_info = self.md_step_btns["Step 3"]
                edits = step3_info["edits"]
                if edits:
                    edits[0].setText("protein_box.gro")
        self._update_skip_steps_visibility()

    def _on_skip_toggled(self, checked):
        self._update_skip_steps_visibility()

    def _update_skip_steps_visibility(self):
        if "Step 2" in self.md_step_btns:
            self.md_step_btns["Step 2"]["group"].setVisible(not self.skip_editconf.isChecked())
        if "Step 3" in self.md_step_btns:
            self.md_step_btns["Step 3"]["group"].setVisible(not self.skip_solvate.isChecked())
        if "Step 4" in self.md_step_btns:
            self.md_step_btns["Step 4"]["group"].setVisible(not self.skip_genion.isChecked())

    def run_md_step(self, step_key: str):
        try:
            wd = self._get_work_dir()
            if not wd:
                self.log_requested.emit("错误: 工作目录未设置", "error")
                return

            gmx = self._get_gmx_path()
            if not gmx or not os.path.isfile(gmx):
                self.log_requested.emit(f"错误: GROMACS可执行文件不存在 - {gmx}", "error")
                return

            if step_key not in self.md_step_btns:
                self.log_requested.emit(f"错误: 步骤不存在 - {step_key}", "error")
                return

            info = self.md_step_btns[step_key]
            edits = info["edits"]

            mdrun_widgets = {}
            box_widgets = {}
            custom_check = info.get("custom_out_check")
            custom_edit = info.get("custom_out_edit")
            restart_check = info.get("restart_check")
            if custom_check is not None:
                mdrun_widgets = {
                    "custom_out_checked": custom_check.isChecked(),
                    "custom_out": custom_edit.text().strip() if custom_edit else "",
                    "restart_checked": restart_check.isChecked() if restart_check else False,
                }
            if "box_type_combo" in info:
                box_widgets = {
                    "box_type": info["box_type_combo"].currentText(),
                    "size_mode": info["size_mode_combo"].currentText(),
                    "center": info["center_check"].isChecked(),
                    "princ": info["princ_check"].isChecked(),
                    "box_x": info["box_x_spin"].value(),
                    "box_y": info["box_y_spin"].value(),
                    "box_z": info["box_z_spin"].value(),
                    "box_a": info["box_a_spin"].value(),
                    "angle_alpha": info["angle_alpha_spin"].value(),
                    "angle_beta": info["angle_beta_spin"].value(),
                    "angle_gamma": info["angle_gamma_spin"].value(),
                    "box_size": info["box_size_spin"].value(),
                }

            state = {
                "ff": self.md_ff.currentText(),
                "water": self.md_water.currentText(),
                "ion_conc": self.md_ion_conc.value(),
                "pdb": self.md_pdb.text().strip() or "protein.pdb",
                "use_existing_top": self.use_existing_top.isChecked(),
                "se_gro": self.se_gro_edit.text().strip(),
                "se_top": self.se_top_edit.text().strip(),
                "edits": [e.text().strip() for e in edits],
                "box_widgets": box_widgets,
                "mdrun_widgets": mdrun_widgets,
                "mdrun_extra": self._get_mdrun_extra(is_em=(step_key == "Step 6")),
                "wd": wd,
            }

            result = build_md_step_command(step_key, gmx, state)
            kind = result[0]

            if kind == "unknown":
                self.log_requested.emit(f"未知步骤: {step_key}", "error")
                return

            if kind == "skip":
                struct_file, top = result[1], result[2]
                struct_path = os.path.join(wd, struct_file)
                top_path = os.path.join(wd, top)
                if not os.path.isfile(struct_path):
                    self.log_requested.emit(f"错误: 结构文件不存在 - {struct_path}", "error")
                    return
                if not os.path.isfile(top_path):
                    self.log_requested.emit(f"错误: TOP文件不存在 - {top_path}", "error")
                    return
                self.log_requested.emit(f"使用已有拓扑: STRUCT={struct_file}, TOP={top}", "info")
                self.log_requested.emit("已跳过pdb2gmx，直接使用现有文件", "success")
                return

            if kind == "multi":
                cmds, step_name = result[1], result[2]
                self.run_requested.emit(cmds, wd, step_name)
                return

            cmd = result[1]
            step_name = result[2]
            if len(result) > 3:
                dup_warning = result[3]
                restart_msg = result[4]
                deffnm = result[5]
                if dup_warning:
                    self.log_requested.emit(f"警告: {dup_warning}", "warning")
                if restart_msg == "found":
                    self.log_requested.emit(f"检测到检查点文件，将断点续跑: {deffnm}.cpt", "info")
                elif restart_msg == "not_found":
                    self.log_requested.emit(f"警告: 未找到检查点文件 {deffnm}.cpt，将从头开始", "warning")

            self.run_requested.emit([cmd], wd, step_name)
        except Exception as e:
            self.log_requested.emit(f"运行步骤 {step_key} 时发生错误: {str(e)}", "error")

    def run_evap_step(self):
        try:
            wd = self._get_work_dir()
            if not wd:
                self.log_requested.emit("错误: 工作目录未设置", "error")
                return

            gmx = self._get_gmx_path()
            if not gmx or not os.path.isfile(gmx):
                self.log_requested.emit(f"错误: GROMACS可执行文件不存在 - {gmx}", "error")
                return

            python_exe = sys.executable
            if getattr(sys, 'frozen', False):
                import shutil
                python_exe = shutil.which('python') or shutil.which('python3')
                if not python_exe:
                    self.log_requested.emit("错误: 无法找到Python解释器，请确保Python已添加到系统PATH", "error")
                    return
            if not python_exe or not os.path.isfile(python_exe):
                self.log_requested.emit(f"错误: 找不到Python解释器 - {python_exe}", "error")
                return

            mode_idx = self.evap_mode.currentIndex()
            input_gro = self.evap_gro_edit.text().strip()
            top_file = self.evap_top_edit.text().strip()
            mdp_file = self.evap_mdp_edit.text().strip()
            resname = self.evap_resname.text().strip()
            atoms_per_mol = self.evap_atoms_per_mol.value()
            prefix = self.evap_prefix.text().strip() or "evap"

            restart_check = self.evap_restart_check.isChecked()
            start_loop = self.evap_start_loop.value()

            if not restart_check:
                start_loop, max_existing = detect_existing_loops(wd, prefix)
                if max_existing is not None:
                    self.log_requested.emit(f"自动检测到已存在第{max_existing}轮，将从第{start_loop}轮开始", "info")

            ok, err_type = check_evap_permissions(wd)
            if not ok:
                if err_type == "not_exists":
                    self.log_requested.emit(f"错误: 工作目录不存在 - {wd}", "error")
                elif err_type == "permission_denied":
                    self.log_requested.emit(f"错误: 工作目录没有写入权限 - {wd}", "error")
                    self.log_requested.emit("建议: 1) 以管理员身份运行程序 2) 更换工作目录为用户文件夹 3) 检查目标目录权限设置", "warning")
                return

            if not input_gro:
                self.log_requested.emit("错误: 请指定输入GRO文件", "error")
                return
            if not top_file:
                self.log_requested.emit("错误: 请指定拓扑TOP文件", "error")
                return
            if not mdp_file:
                self.log_requested.emit("错误: 请指定MDP文件", "error")
                return
            if not resname:
                self.log_requested.emit("错误: 请指定残基名", "error")
                return

            for label, p in [("输入GRO", input_gro), ("拓扑TOP", top_file), ("MDP", mdp_file)]:
                if not os.path.isfile(resolve_path(wd, p)):
                    self.log_requested.emit(f"错误: {label}文件不存在 - {p}", "error")
                    return

            delete_script = write_delete_script(wd, mode_idx, DELETE_SOLVENT_SCRIPT, DELETE_ADDITIVE_SCRIPT)
            self.log_requested.emit(f"已写出脚本: {os.path.join(wd, delete_script)}", "info")

            file_info = setup_evap_work_files(wd, input_gro, top_file, prefix, start_loop, mode_idx)
            if "error" in file_info:
                err = file_info["error"]
                if err.startswith("missing_prev_gro:"):
                    prev_gro = err.split(":", 1)[1]
                    self.log_requested.emit(f"错误: 断点续跑失败，未找到上一轮的GRO文件 - {prev_gro}", "error")
                elif err == "missing_prev_top":
                    self.log_requested.emit(f"错误: 断点续跑失败，未找到可用拓扑文件", "error")
                    self.log_requested.emit("已查找: " + ", ".join(file_info["possible_tops"]), "error")
                return

            original_gro = file_info["original_gro"]
            original_top = file_info["original_top"]
            work_gro = file_info["work_gro"]
            work_top = file_info["work_top"]
            current_gro = file_info["current_gro"]
            current_top = file_info["current_top"]

            if mode_idx == 0:
                if start_loop == 1:
                    self.log_requested.emit(f"已备份原始文件: {original_gro}, {original_top}", "info")
                else:
                    self.log_requested.emit(f"断点续跑: 从第{start_loop}轮开始，使用 {prefix}_{start_loop - 1}.gro 和 {file_info['prev_top_basename']}", "info")
            else:
                self.log_requested.emit(f"已备份原始文件: {original_gro}, {original_top}", "info")

            all_cmds = []
            if mode_idx == 0:
                delete_num = self.evap_delete_num.value()
                loops = self.evap_loops.value()
                end_loop = start_loop + loops - 1

                self.log_requested.emit(f"开始蒸发溶剂: {resname}, 每轮删除{delete_num}个, 从第{start_loop}轮到第{end_loop}轮", "info")
                delete_from = "bottom" if self.evap_source.currentIndex() == 0 else "top"

                for i in range(start_loop, end_loop + 1):
                    loop_cmds, restart_cpt = build_evap_loop_commands(
                        loop_idx=i, prefix=prefix, gmx=gmx, python_exe=python_exe,
                        delete_script=delete_script, resname=resname,
                        delete_num=delete_num, atoms_per_mol=atoms_per_mol,
                        delete_from=delete_from, mdp_file=mdp_file,
                        work_gro=work_gro, work_top=work_top,
                        current_gro=current_gro, current_top=current_top,
                        mdrun_extra=self._get_mdrun_extra(False), wd=wd,
                        restart_check=restart_check, start_loop=start_loop,
                        mode="solvent"
                    )
                    if restart_cpt:
                        self.log_requested.emit(f"第{i}轮将从检查点文件续跑: {restart_cpt}", "info")
                    all_cmds.extend(loop_cmds)
            else:
                self.log_requested.emit(f"删除全部添加剂: {resname}", "info")
                self.log_requested.emit(f"文件命名: prefix={prefix}, deffnm={prefix}, current_gro={current_gro}, current_top={current_top}", "info")

                loop_cmds, _ = build_evap_loop_commands(
                    loop_idx=0, prefix=prefix, gmx=gmx, python_exe=python_exe,
                    delete_script=delete_script, resname=resname,
                    delete_num=0, atoms_per_mol=atoms_per_mol,
                    delete_from="", mdp_file=mdp_file,
                    work_gro=input_gro, work_top=top_file,
                    current_gro=current_gro, current_top=current_top,
                    mdrun_extra=self._get_mdrun_extra(False), wd=wd,
                    restart_check=False, start_loop=0,
                    mode="additive"
                )
                all_cmds.extend(loop_cmds)
                self.log_requested.emit(f"一次性删除模式命令列表 ({len(all_cmds)} 个):", "info")
                for i, c in enumerate(all_cmds):
                    self.log_requested.emit(f"  [{i+1}] {' '.join(c)}", "info")

            step_name = "溶剂/添加剂蒸发"
            self.log_requested.emit(f"共 {len(all_cmds)} 个命令待执行", "info")
            self.run_requested.emit(all_cmds, wd, step_name)
        except Exception as e:
            self.log_requested.emit(f"运行蒸发步骤时发生错误: {str(e)}", "error")

    def _reset_anneal_curve(self):
        self.anneal_table.setRowCount(7)
        default_times = ["0", "100", "300", "500", "700", "900", "1000"]
        default_temps = ["300", "373", "373", "373", "373", "300", "300"]
        for i in range(7):
            self.anneal_table.setItem(i, 0, QTableWidgetItem(default_times[i]))
            self.anneal_table.setItem(i, 1, QTableWidgetItem(default_temps[i]))
        self.log_requested.emit("退火曲线已重置为默认值", "info")

    def run_anneal_step(self):
        try:
            wd = self._get_work_dir()
            if not wd:
                self.log_requested.emit("错误: 工作目录未设置", "error")
                return

            gmx = self._get_gmx_path()
            if not gmx or not os.path.isfile(gmx):
                self.log_requested.emit(f"错误: GROMACS可执行文件不存在 - {gmx}", "error")
                return

            if not os.path.exists(wd):
                self.log_requested.emit(f"错误: 工作目录不存在 - {wd}", "error")
                return
            try:
                test_file = os.path.join(wd, "_test_write_permission.tmp")
                with open(test_file, "w") as f:
                    f.write("test")
                os.remove(test_file)
            except PermissionError:
                self.log_requested.emit(f"错误: 工作目录没有写入权限 - {wd}", "error")
                self.log_requested.emit("建议: 1) 以管理员身份运行程序 2) 更换工作目录为用户文件夹 3) 检查目标目录权限设置", "warning")
                return

            gro_file = self.anneal_gro_edit.text().strip()
            top_file = self.anneal_top_edit.text().strip()
            prefix = self.anneal_prefix.text().strip() or "anneal"
            mode_text = self.anneal_mode.currentText()
            annealing_mode = "single" if "single" in mode_text else "periodic"

            if not gro_file:
                self.log_requested.emit("错误: 请指定输入GRO文件", "error")
                return
            if not top_file:
                self.log_requested.emit("错误: 请指定拓扑TOP文件", "error")
                return

            gro_path = gro_file if os.path.isabs(gro_file) else os.path.join(wd, gro_file)
            top_path = top_file if os.path.isabs(top_file) else os.path.join(wd, top_file)
            if not os.path.isfile(gro_path):
                self.log_requested.emit(f"错误: GRO文件不存在 - {gro_path}", "error")
                return
            if not os.path.isfile(top_path):
                self.log_requested.emit(f"错误: TOP文件不存在 - {top_path}", "error")
                return

            times = []
            temps = []
            for row in range(self.anneal_table.rowCount()):
                t_item = self.anneal_table.item(row, 0)
                temp_item = self.anneal_table.item(row, 1)
                if t_item and temp_item:
                    t_val = t_item.text().strip()
                    temp_val = temp_item.text().strip()
                    if t_val and temp_val:
                        try:
                            float(t_val)
                            float(temp_val)
                            times.append(t_val)
                            temps.append(temp_val)
                        except ValueError:
                            self.log_requested.emit(f"错误: 第{row+1}行数据不是有效数字 (时间={t_val}, 温度={temp_val})", "error")
                            return

            if len(times) < 2:
                self.log_requested.emit("错误: 退火曲线至少需要2个时间-温度点对", "error")
                return

            if len(times) != len(temps):
                self.log_requested.emit("错误: 时间点数与温度点数不一致", "error")
                return

            for i in range(1, len(times)):
                if float(times[i]) <= float(times[i-1]):
                    self.log_requested.emit(f"错误: 时间点必须递增 (第{i}个点 {times[i]} <= {times[i-1]})", "error")
                    return

            npoints = len(times)
            time_str = " ".join(times)
            temp_str = " ".join(temps)

            total_time_ps = float(times[-1])
            nsteps = int(total_time_ps / 0.002)

            mdp_file = os.path.join(wd, f"{prefix}.mdp")
            mdp_content = build_annealing_mdp(prefix, times, temps, annealing_mode)

            with open(mdp_file, 'w', encoding='utf-8') as f:
                f.write(mdp_content)

            self.log_requested.emit(f"退火MDP文件已生成: {mdp_file}", "success")
            self.log_requested.emit(f"退火模式: {annealing_mode}, 点数: {npoints}", "info")
            self.log_requested.emit(f"时间点: {time_str}", "info")
            self.log_requested.emit(f"温度点: {temp_str}", "info")
            self.log_requested.emit(f"模拟时长: {total_time_ps}ps ({nsteps} steps)", "info")

            grompp_cmd, mdrun_cmd = build_annealing_commands(
                gmx, prefix, gro_path, top_path, mdp_file,
                self._get_mdrun_extra(False), wd
            )

            self.run_requested.emit([grompp_cmd, mdrun_cmd], wd, "退火模拟")

        except Exception as e:
            self.log_requested.emit(f"运行退火步骤时发生错误: {str(e)}", "error")

    def run_all_md(self):
        try:
            wd = self._get_work_dir()
            if not wd:
                self.log_requested.emit("错误: 工作目录未设置", "error")
                return

            gmx = self._get_gmx_path()
            if not gmx or not os.path.isfile(gmx):
                self.log_requested.emit(f"错误: GROMACS可执行文件不存在 - {gmx}", "error")
                return

            use_existing = self.use_existing_top.isChecked()
            if use_existing:
                first_struct = self.se_gro_edit.text().strip() or "input.gro"
                top = self.se_top_edit.text().strip() or "topol.top"
                struct_path = os.path.join(wd, first_struct)
                top_path = os.path.join(wd, top)
                if not os.path.isfile(struct_path):
                    self.log_requested.emit(f"错误: 结构文件不存在 - {struct_path}", "error")
                    return
                if not os.path.isfile(top_path):
                    self.log_requested.emit(f"错误: TOP文件不存在 - {top_path}", "error")
                    return
                self.log_requested.emit(f"使用已有拓扑: STRUCT={first_struct}, TOP={top}", "info")

            state = {
                "ff": self.md_ff.currentText(),
                "water": self.md_water.currentText(),
                "ion_conc": self.md_ion_conc.value(),
                "pdb": self.md_pdb.text().strip() or "protein.pdb",
                "use_existing_top": use_existing,
                "se_gro": self.se_gro_edit.text().strip(),
                "se_top": self.se_top_edit.text().strip(),
                "skip_editconf": self.skip_editconf.isChecked(),
                "skip_solvate": self.skip_solvate.isChecked(),
                "skip_genion": self.skip_genion.isChecked(),
                "box_params": self._get_box_params(),
                "extra_mdrun": self._get_mdrun_extra(False),
                "extra_em": self._get_mdrun_extra(True),
            }
            commands = build_full_md_pipeline(gmx, state)
            self.run_requested.emit(commands, wd, "完整MD流程")
        except Exception as e:
            self.log_requested.emit(f"运行完整MD流程时发生错误: {str(e)}", "error")

    def _get_full_mdp_template(self, mdp_type: str) -> str:
        dt = self.md_dt.value()
        nsteps = self.md_nsteps.value()
        temp = self.md_temp.value()
        press = self.md_pressure.value()
        return build_full_mdp(mdp_type, dt=dt, nsteps=nsteps, temp=temp, press=press)

    def generate_mdp_template(self, mdp_type: str):
        wd = self._get_work_dir()
        if not wd:
            return

        dt = self.md_dt.value()
        nsteps = self.md_nsteps.value()
        temp = self.md_temp.value()
        press = self.md_pressure.value()

        content = build_simple_mdp(mdp_type, dt=dt, nsteps=nsteps, temp=temp, press=press)
        fname = f"{mdp_type}.mdp"
        fpath = os.path.join(wd, fname)
        try:
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(content)
            self.log_requested.emit(f"已生成 MDP 模板: {fpath}", "success")
        except Exception as e:
            self.log_requested.emit(f"生成 MDP 模板失败: {e}", "error")

    def set_running_state(self, running: bool):
        for widgets in self.md_step_btns.values():
            widgets["run_btn"].setEnabled(not running)
        if hasattr(self, "se_run_btn"):
            self.se_run_btn.setEnabled(not running)
        if hasattr(self, "evap_run_btn"):
            self.evap_run_btn.setEnabled(not running)
        if hasattr(self, "anneal_run_btn"):
            self.anneal_run_btn.setEnabled(not running)


    def retranslate_ui(self, lang: str):
        self.common_group.setTitle(tr("md_global_group", lang=lang))
        self.prep_phase.setTitle(tr("md_phase_prep", lang=lang))
        self.em_phase.setTitle(tr("md_phase_em", lang=lang))
        self.equil_phase.setTitle(tr("md_phase_equil", lang=lang))
        self.prod_phase.setTitle(tr("md_phase_prod", lang=lang))
        self.evap_phase.setTitle(tr("md_phase_evap", lang=lang))
        self.anneal_phase.setTitle(tr("md_phase_anneal", lang=lang))

        self.lbl_ff.setText(tr("md_ff", lang=lang))
        self.lbl_water.setText(tr("md_water", lang=lang))
        self.lbl_box_type.setText(tr("md_box_type", lang=lang))
        self.lbl_box_mode.setText(tr("md_box_mode", lang=lang))
        self.lbl_ion.setText(tr("md_ion_conc", lang=lang))
        self.lbl_temp.setText(tr("md_temp", lang=lang))
        self.lbl_press.setText(tr("md_press", lang=lang))
        self.lbl_dt.setText(tr("md_dt", lang=lang))
        self.lbl_nsteps.setText(tr("md_nsteps", lang=lang))
        self.lbl_engine.setText(tr("md_engine", lang=lang))
        self.lbl_nt.setText(tr("md_nt", lang=lang))
        self.lbl_pdb.setText(tr("md_pdb", lang=lang))
        self.lbl_box_size.setText(tr("md_box_dist", lang=lang))

        self.md_princ.setText(tr("md_princ", lang=lang))
        self.use_existing_top.setText(tr("md_use_existing", lang=lang))
        self.skip_solvate.setText(tr("md_skip_solvate", lang=lang))
        self.skip_genion.setText(tr("md_skip_genion", lang=lang))
        self.skip_editconf.setText(tr("md_skip_editconf", lang=lang))

        self.md_box_size_mode.setItemText(0, tr("md_box_opt_margin", lang=lang))
        self.md_box_size_mode.setItemText(1, tr("md_box_opt_dims", lang=lang))
        self.evap_mode.setItemText(0, tr("md_evap_mode_batch", lang=lang))
        self.evap_mode.setItemText(1, tr("md_evap_mode_all", lang=lang))

        self.evap_run_btn.setText(tr("md_evap_start", lang=lang))
        self.anneal_run_btn.setText(tr("md_anneal_start", lang=lang))
        for widgets in self.md_step_btns.values():
            widgets["run_btn"].setText(tr("run_step", lang=lang))
