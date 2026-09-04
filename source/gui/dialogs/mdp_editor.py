#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
高级 MDP 参数编辑器对话框
"""

from datetime import datetime
import os

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox,
    QSpinBox, QDoubleSpinBox, QFileDialog, QSplitter, QTabWidget, QMessageBox,
    QPlainTextEdit, QDialog, QFormLayout
)


from PyQt5.QtCore import Qt


from PyQt5.QtGui import QFont


# =============================================================================
# 高级MDP参数编辑器对话框
# =============================================================================
class MdpEditorDialog(QDialog):
    MDP_TEMPLATES = {
        "EM-1 (最速下降法)": {
            "integrator": "steep",
            "nsteps": "100000",
            "emtol": "100.0",
            "emstep": "0.01",
            "cutoff-scheme": "Verlet",
            "nstlist": "40",
            "ns-type": "grid",
            "rlist": "1.5",
            "pbc": "xyz",
            "coulombtype": "PME",
            "rcoulomb": "1.5",
            "pme_order": "4",
            "fourierspacing": "0.12",
            "ewald-rtol": "1e-5",
            "vdw-type": "cut-off",
            "rvdw": "1.5",
            "DispCorr": "EnerPres",
            "nstenergy": "1000",
            "nstlog": "1000",
            "energygrps": "System",
        },
        "EM-2 (共轭梯度法)": {
            "integrator": "cg",
            "nsteps": "50000",
            "emtol": "50.0",
            "emstep": "0.01",
            "cutoff-scheme": "Verlet",
            "nstlist": "40",
            "ns-type": "grid",
            "rlist": "1.5",
            "pbc": "xyz",
            "coulombtype": "PME",
            "rcoulomb": "1.5",
            "pme_order": "4",
            "fourierspacing": "0.12",
            "ewald-rtol": "1e-5",
            "vdw-type": "cut-off",
            "rvdw": "1.5",
            "DispCorr": "EnerPres",
            "nstenergy": "1000",
            "nstlog": "1000",
            "energygrps": "System",
        },
        "NPT-1 (初始平衡)": {
            "integrator": "md",
            "dt": "0.002",
            "nsteps": "500000",
            "tinit": "0.0",
            "cutoff-scheme": "Verlet",
            "nstlist": "100",
            "ns-type": "grid",
            "rlist": "1.5",
            "pbc": "xyz",
            "coulombtype": "PME",
            "rcoulomb": "1.5",
            "pme_order": "4",
            "fourierspacing": "0.12",
            "ewald-rtol": "1e-5",
            "vdw-type": "cut-off",
            "rvdw": "1.5",
            "DispCorr": "EnerPres",
            "tcoupl": "V-rescale",
            "tc-grps": "system",
            "tau_t": "0.5",
            "ref_t": "300",
            "pcoupl": "C-rescale",
            "pcoupltype": "isotropic",
            "tau_p": "0.5",
            "ref_p": "100",
            "compressibility": "4.5e-5",
            "gen_vel": "yes",
            "gen_temp": "300",
            "gen_seed": "-1",
            "constraints": "h-bonds",
            "constraint_algorithm": "lincs",
            "lincs_iter": "1",
            "lincs_order": "4",
            "continuation": "no",
            "nstxout": "50000",
            "nstvout": "50000",
            "nstfout": "50000",
            "nstenergy": "50000",
            "nstlog": "50000",
            "nstcheckpoint": "50000",
            "nstxtcout": "50000",
            "xtc-precision": "1000",
            "energygrps": "System",
        },
        "NPT-2 (进一步平衡, 2ns)": {
            "integrator": "md",
            "dt": "0.002",
            "nsteps": "1000000",
            "tinit": "0.0",
            "cutoff-scheme": "Verlet",
            "nstlist": "100",
            "ns-type": "grid",
            "rlist": "1.5",
            "pbc": "xyz",
            "coulombtype": "PME",
            "rcoulomb": "1.5",
            "pme_order": "4",
            "fourierspacing": "0.12",
            "ewald-rtol": "1e-5",
            "vdw-type": "cut-off",
            "rvdw": "1.5",
            "DispCorr": "EnerPres",
            "tcoupl": "V-rescale",
            "tc-grps": "system",
            "tau_t": "0.5",
            "ref_t": "300",
            "pcoupl": "C-rescale",
            "pcoupltype": "isotropic",
            "tau_p": "1.0",
            "ref_p": "1.0",
            "compressibility": "4.5e-5",
            "gen_vel": "no",
            "constraints": "h-bonds",
            "constraint_algorithm": "lincs",
            "lincs_iter": "1",
            "lincs_order": "4",
            "continuation": "yes",
            "nstxout": "100000",
            "nstvout": "100000",
            "nstfout": "100000",
            "nstenergy": "100000",
            "nstlog": "100000",
            "nstcheckpoint": "100000",
            "nstxtcout": "100000",
            "xtc-precision": "1000",
            "energygrps": "System",
        },
        "MD (生产模拟, 10ns)": {
            "integrator": "md",
            "dt": "0.002",
            "nsteps": "5000000",
            "tinit": "0.0",
            "cutoff-scheme": "Verlet",
            "nstlist": "100",
            "ns-type": "grid",
            "rlist": "1.5",
            "pbc": "xyz",
            "coulombtype": "PME",
            "rcoulomb": "1.5",
            "pme_order": "4",
            "fourierspacing": "0.12",
            "ewald-rtol": "1e-5",
            "vdw-type": "cut-off",
            "rvdw": "1.5",
            "DispCorr": "EnerPres",
            "tcoupl": "V-rescale",
            "tc-grps": "system",
            "tau_t": "0.5",
            "ref_t": "300",
            "pcoupl": "Parrinello-Rahman",
            "pcoupltype": "isotropic",
            "tau_p": "1.0",
            "ref_p": "1.0",
            "compressibility": "4.5e-5",
            "gen_vel": "no",
            "constraints": "h-bonds",
            "constraint_algorithm": "lincs",
            "lincs_iter": "1",
            "lincs_order": "4",
            "continuation": "yes",
            "nstxout": "100000",
            "nstvout": "100000",
            "nstfout": "100000",
            "nstenergy": "100000",
            "nstlog": "100000",
            "nstcheckpoint": "100000",
            "nstxtcout": "100000",
            "xtc-precision": "1000",
            "energygrps": "System",
        },
        "SA溶剂蒸发 (10ps/轮)": {
            "integrator": "md",
            "dt": "0.002",
            "nsteps": "5000",
            "tinit": "0.0",
            "cutoff-scheme": "Verlet",
            "nstlist": "100",
            "ns-type": "grid",
            "rlist": "1.5",
            "pbc": "xyz",
            "coulombtype": "PME",
            "rcoulomb": "1.5",
            "pme_order": "4",
            "fourierspacing": "0.12",
            "ewald-rtol": "1e-5",
            "vdw-type": "cut-off",
            "rvdw": "1.5",
            "DispCorr": "EnerPres",
            "tcoupl": "V-rescale",
            "tc-grps": "system",
            "tau_t": "0.5",
            "ref_t": "300",
            "pcoupl": "Parrinello-Rahman",
            "pcoupltype": "isotropic",
            "tau_p": "1.0",
            "ref_p": "1",
            "compressibility": "4.5e-5",
            "gen_vel": "no",
            "constraints": "h-bonds",
            "constraint_algorithm": "lincs",
            "lincs_iter": "1",
            "lincs_order": "4",
            "continuation": "yes",
            "nstxout": "1000",
            "nstvout": "1000",
            "nstfout": "1000",
            "nstenergy": "1000",
            "nstxtcout": "1000",
            "xtc-precision": "1000",
        },
        "evapDIO (删添加剂, 1ns)": {
            "integrator": "md",
            "dt": "0.002",
            "nsteps": "500000",
            "tinit": "0.0",
            "cutoff-scheme": "Verlet",
            "nstlist": "100",
            "ns-type": "grid",
            "rlist": "1.5",
            "pbc": "xyz",
            "coulombtype": "PME",
            "rcoulomb": "1.5",
            "pme_order": "4",
            "fourierspacing": "0.12",
            "ewald-rtol": "1e-5",
            "vdw-type": "cut-off",
            "rvdw": "1.5",
            "DispCorr": "EnerPres",
            "tcoupl": "V-rescale",
            "tc-grps": "system",
            "tau_t": "0.5",
            "ref_t": "300",
            "pcoupl": "Parrinello-Rahman",
            "pcoupltype": "isotropic",
            "tau_p": "1.0",
            "ref_p": "1",
            "compressibility": "4.5e-5",
            "gen_vel": "no",
            "constraints": "h-bonds",
            "constraint_algorithm": "lincs",
            "lincs_iter": "1",
            "lincs_order": "4",
            "continuation": "yes",
            "nstxout": "10000",
            "nstvout": "10000",
            "nstfout": "10000",
            "nstenergy": "1000",
            "nstxtcout": "1000",
            "xtc-precision": "1000",
        },
        "退火 (温度循环)": {
            "integrator": "md",
            "dt": "0.002",
            "nsteps": "500000",
            "tinit": "0.0",
            "cutoff-scheme": "Verlet",
            "nstlist": "100",
            "ns-type": "grid",
            "rlist": "1.5",
            "pbc": "xyz",
            "coulombtype": "PME",
            "rcoulomb": "1.5",
            "pme_order": "4",
            "fourierspacing": "0.12",
            "ewald-rtol": "1e-5",
            "vdw-type": "cut-off",
            "rvdw": "1.5",
            "DispCorr": "EnerPres",
            "tcoupl": "V-rescale",
            "tc-grps": "system",
            "tau_t": "0.5",
            "ref_t": "300",
            "annealing": "single",
            "annealing_npoints": "7",
            "annealing_time": "0 100 300 500 700 900 1000",
            "annealing_temp": "300 373 373 373 373 300 300",
            "pcoupl": "Parrinello-Rahman",
            "pcoupltype": "isotropic",
            "tau_p": "1.0",
            "ref_p": "1.0",
            "compressibility": "4.5e-5",
            "gen_vel": "no",
            "constraints": "h-bonds",
            "constraint_algorithm": "lincs",
            "lincs_iter": "1",
            "lincs_order": "4",
            "continuation": "yes",
            "nstxout": "10000",
            "nstvout": "10000",
            "nstfout": "10000",
            "nstenergy": "10000",
            "nstlog": "10000",
            "nstcheckpoint": "10000",
            "nstxtcout": "10000",
            "xtc-precision": "1000",
            "energygrps": "System",
        },
        "MD2 (最终生产模拟)": {
            "integrator": "md",
            "dt": "0.002",
            "nsteps": "5000000",
            "tinit": "0.0",
            "cutoff-scheme": "Verlet",
            "nstlist": "100",
            "ns-type": "grid",
            "rlist": "1.5",
            "pbc": "xyz",
            "coulombtype": "PME",
            "rcoulomb": "1.5",
            "pme_order": "4",
            "fourierspacing": "0.12",
            "ewald-rtol": "1e-5",
            "vdw-type": "cut-off",
            "rvdw": "1.5",
            "DispCorr": "EnerPres",
            "tcoupl": "V-rescale",
            "tc-grps": "system",
            "tau_t": "0.5",
            "ref_t": "300",
            "pcoupl": "Parrinello-Rahman",
            "pcoupltype": "isotropic",
            "tau_p": "1.0",
            "ref_p": "1.0",
            "compressibility": "4.5e-5",
            "gen_vel": "no",
            "constraints": "h-bonds",
            "constraint_algorithm": "lincs",
            "lincs_iter": "1",
            "lincs_order": "4",
            "continuation": "yes",
            "nstxout": "100000",
            "nstvout": "100000",
            "nstfout": "100000",
            "nstenergy": "100000",
            "nstlog": "100000",
            "nstcheckpoint": "100000",
            "nstxtcout": "100000",
            "xtc-precision": "1000",
            "energygrps": "System",
        },
    }

    def __init__(self, parent=None, mdp_content=""):
        super().__init__(parent)
        self.setWindowTitle("高级MDP参数编辑器")
        self.resize(1100, 750)
        self._params = {}
        self._updating = False
        self._default_dir = ""
        self._create_ui()
        if mdp_content:
            self.parse_mdp(mdp_content)
        else:
            self._on_param_changed()

    def _create_ui(self):
        main_layout = QHBoxLayout(self)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        template_layout = QHBoxLayout()
        template_label = QLabel("常用模板:")
        self.template_combo = QComboBox()
        self.template_combo.addItem("--- 选择模板 ---")
        for name in self.MDP_TEMPLATES.keys():
            self.template_combo.addItem(name)
        self.template_combo.currentIndexChanged.connect(self._on_template_selected)
        template_layout.addWidget(template_label)
        template_layout.addWidget(self.template_combo, 1)
        left_layout.addLayout(template_layout)

        self.tab_widget = QTabWidget()
        self._create_run_tab()
        self._create_output_tab()
        self._create_nblist_tab()
        self._create_coulomb_tab()
        self._create_vdw_tab()
        self._create_tcoupl_tab()
        self._create_pcoupl_tab()
        self._create_genvel_tab()
        self._create_annealing_tab()
        left_layout.addWidget(self.tab_widget, 1)

        button_layout = QHBoxLayout()
        self.btn_load = QPushButton("从文件加载")
        self.btn_save = QPushButton("保存到文件")
        self.btn_reset = QPushButton("重置")
        self.btn_ok = QPushButton("确定")
        self.btn_cancel = QPushButton("取消")
        self.btn_load.clicked.connect(self._on_load_file)
        self.btn_save.clicked.connect(self._on_save_file)
        self.btn_reset.clicked.connect(self._on_reset)
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)
        button_layout.addWidget(self.btn_load)
        button_layout.addWidget(self.btn_save)
        button_layout.addStretch()
        button_layout.addWidget(self.btn_reset)
        button_layout.addWidget(self.btn_ok)
        button_layout.addWidget(self.btn_cancel)
        left_layout.addLayout(button_layout)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        preview_label = QLabel("实时预览 (MDP内容)")
        self.preview_edit = QPlainTextEdit()
        self.preview_edit.setReadOnly(True)
        self.preview_edit.setFont(QFont("Consolas", 9))
        right_layout.addWidget(preview_label)
        right_layout.addWidget(self.preview_edit, 1)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([600, 500])
        main_layout.addWidget(splitter)

    def _create_run_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)

        self.integrator_combo = QComboBox()
        self.integrator_combo.addItems(["md", "steep", "cg", "sd", "bd", "md-vv", "md-vv-avek"])
        self.integrator_combo.currentIndexChanged.connect(self._on_param_changed)

        self.dt_spin = QDoubleSpinBox()
        self.dt_spin.setRange(0.0001, 10.0)
        self.dt_spin.setSingleStep(0.001)
        self.dt_spin.setDecimals(4)
        self.dt_spin.setValue(0.002)
        self.dt_spin.valueChanged.connect(self._on_param_changed)

        self.nsteps_spin = QSpinBox()
        self.nsteps_spin.setRange(0, 1000000000)
        self.nsteps_spin.setSingleStep(1000)
        self.nsteps_spin.setValue(50000)
        self.nsteps_spin.valueChanged.connect(self._on_param_changed)

        self.tinit_spin = QDoubleSpinBox()
        self.tinit_spin.setRange(0.0, 1000000.0)
        self.tinit_spin.setSingleStep(0.1)
        self.tinit_spin.setDecimals(3)
        self.tinit_spin.setValue(0.0)
        self.tinit_spin.valueChanged.connect(self._on_param_changed)

        self.emtol_spin = QDoubleSpinBox()
        self.emtol_spin.setRange(0.0, 100000.0)
        self.emtol_spin.setSingleStep(10.0)
        self.emtol_spin.setDecimals(1)
        self.emtol_spin.setValue(1000.0)
        self.emtol_spin.valueChanged.connect(self._on_param_changed)

        self.emstep_spin = QDoubleSpinBox()
        self.emstep_spin.setRange(0.0001, 1.0)
        self.emstep_spin.setSingleStep(0.001)
        self.emstep_spin.setDecimals(4)
        self.emstep_spin.setValue(0.01)
        self.emstep_spin.valueChanged.connect(self._on_param_changed)

        layout.addRow("积分器 (integrator):", self.integrator_combo)
        layout.addRow("时间步长 (dt, ps):", self.dt_spin)
        layout.addRow("模拟步数 (nsteps):", self.nsteps_spin)
        layout.addRow("初始时间 (tinit, ps):", self.tinit_spin)
        layout.addRow("能量最小化容差 (emtol, kJ/mol):", self.emtol_spin)
        layout.addRow("能量最小化步长 (emstep, nm):", self.emstep_spin)

        self.tab_widget.addTab(tab, "运行参数")

    def _create_output_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)

        self.nstxout_spin = self._create_int_spin(0, 1000000, 0)
        self.nstvout_spin = self._create_int_spin(0, 1000000, 0)
        self.nstfout_spin = self._create_int_spin(0, 1000000, 0)
        self.nstenergy_spin = self._create_int_spin(0, 1000000, 1000)
        self.nstlog_spin = self._create_int_spin(0, 1000000, 1000)
        self.nstcheckpoint_spin = self._create_int_spin(0, 1000000, 10000)
        self.nstxtcout_spin = self._create_int_spin(0, 1000000, 5000)
        self.xtc_precision_spin = self._create_int_spin(1, 100000, 1000)

        layout.addRow("坐标输出频率 (nstxout):", self.nstxout_spin)
        layout.addRow("速度输出频率 (nstvout):", self.nstvout_spin)
        layout.addRow("力输出频率 (nstfout):", self.nstfout_spin)
        layout.addRow("能量输出频率 (nstenergy):", self.nstenergy_spin)
        layout.addRow("日志输出频率 (nstlog):", self.nstlog_spin)
        layout.addRow("检查点频率 (nstcheckpoint):", self.nstcheckpoint_spin)
        layout.addRow("XTC轨迹频率 (nstxtcout):", self.nstxtcout_spin)
        layout.addRow("XTC精度 (xtc-precision):", self.xtc_precision_spin)

        self.tab_widget.addTab(tab, "输出控制")

    def _create_int_spin(self, min_val, max_val, default):
        spin = QSpinBox()
        spin.setRange(min_val, max_val)
        spin.setSingleStep(100)
        spin.setValue(default)
        spin.valueChanged.connect(self._on_param_changed)
        return spin

    def _create_nblist_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)

        self.cutoff_scheme_combo = QComboBox()
        self.cutoff_scheme_combo.addItems(["Verlet", "group"])
        self.cutoff_scheme_combo.currentIndexChanged.connect(self._on_param_changed)

        self.nstlist_spin = QSpinBox()
        self.nstlist_spin.setRange(0, 1000)
        self.nstlist_spin.setSingleStep(1)
        self.nstlist_spin.setValue(10)
        self.nstlist_spin.valueChanged.connect(self._on_param_changed)

        self.ns_type_combo = QComboBox()
        self.ns_type_combo.addItems(["grid", "simple"])
        self.ns_type_combo.currentIndexChanged.connect(self._on_param_changed)

        self.rlist_spin = QDoubleSpinBox()
        self.rlist_spin.setRange(0.1, 10.0)
        self.rlist_spin.setSingleStep(0.1)
        self.rlist_spin.setDecimals(3)
        self.rlist_spin.setValue(1.0)
        self.rlist_spin.valueChanged.connect(self._on_param_changed)

        self.pbc_combo = QComboBox()
        self.pbc_combo.addItems(["xyz", "xy", "no"])
        self.pbc_combo.currentIndexChanged.connect(self._on_param_changed)

        layout.addRow("截断方案 (cutoff-scheme):", self.cutoff_scheme_combo)
        layout.addRow("近邻列表更新频率 (nstlist):", self.nstlist_spin)
        layout.addRow("近邻搜索类型 (ns-type):", self.ns_type_combo)
        layout.addRow("近邻列表截断 (rlist, nm):", self.rlist_spin)
        layout.addRow("周期性边界 (pbc):", self.pbc_combo)

        self.tab_widget.addTab(tab, "近邻列表")

    def _create_coulomb_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)

        self.coulombtype_combo = QComboBox()
        self.coulombtype_combo.addItems([
            "PME", "Ewald", "Cut-off", "Reaction-Field",
            "Generalized-Reaction-Field", "Shift", "User", "PME-Switch", "PME-User"
        ])
        self.coulombtype_combo.currentIndexChanged.connect(self._on_param_changed)

        self.rcoulomb_spin = QDoubleSpinBox()
        self.rcoulomb_spin.setRange(0.1, 10.0)
        self.rcoulomb_spin.setSingleStep(0.1)
        self.rcoulomb_spin.setDecimals(3)
        self.rcoulomb_spin.setValue(1.0)
        self.rcoulomb_spin.valueChanged.connect(self._on_param_changed)

        self.pme_order_spin = QSpinBox()
        self.pme_order_spin.setRange(3, 12)
        self.pme_order_spin.setSingleStep(1)
        self.pme_order_spin.setValue(4)
        self.pme_order_spin.valueChanged.connect(self._on_param_changed)

        self.fourierspacing_spin = QDoubleSpinBox()
        self.fourierspacing_spin.setRange(0.01, 2.0)
        self.fourierspacing_spin.setSingleStep(0.01)
        self.fourierspacing_spin.setDecimals(3)
        self.fourierspacing_spin.setValue(0.16)
        self.fourierspacing_spin.valueChanged.connect(self._on_param_changed)

        self.ewald_rtol_spin = QDoubleSpinBox()
        self.ewald_rtol_spin.setRange(1e-9, 1e-2)
        self.ewald_rtol_spin.setSingleStep(1e-6)
        self.ewald_rtol_spin.setDecimals(8)
        self.ewald_rtol_spin.setValue(1e-5)
        self.ewald_rtol_spin.valueChanged.connect(self._on_param_changed)

        layout.addRow("静电类型 (coulombtype):", self.coulombtype_combo)
        layout.addRow("静电截断 (rcoulomb, nm):", self.rcoulomb_spin)
        layout.addRow("PME插值阶数 (pme_order):", self.pme_order_spin)
        layout.addRow("傅里叶网格间距 (fourierspacing):", self.fourierspacing_spin)
        layout.addRow("Ewald相对容差 (ewald-rtol):", self.ewald_rtol_spin)

        self.tab_widget.addTab(tab, "静电相互作用")

    def _create_vdw_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)

        self.vdw_type_combo = QComboBox()
        self.vdw_type_combo.addItems([
            "cut-off", "PME", "Shift", "Switch", "User",
            "Tabulated", "GB", "Not-allocated"
        ])
        self.vdw_type_combo.currentIndexChanged.connect(self._on_param_changed)

        self.rvdw_spin = QDoubleSpinBox()
        self.rvdw_spin.setRange(0.1, 10.0)
        self.rvdw_spin.setSingleStep(0.1)
        self.rvdw_spin.setDecimals(3)
        self.rvdw_spin.setValue(1.0)
        self.rvdw_spin.valueChanged.connect(self._on_param_changed)

        self.dispcorr_combo = QComboBox()
        self.dispcorr_combo.addItems(["no", "EnerPres", "Ener", "AllEner", "AllEnerPres"])
        self.dispcorr_combo.currentIndexChanged.connect(self._on_param_changed)

        layout.addRow("范德华类型 (vdw-type):", self.vdw_type_combo)
        layout.addRow("范德华截断 (rvdw, nm):", self.rvdw_spin)
        layout.addRow("长程色散校正 (DispCorr):", self.dispcorr_combo)

        self.tab_widget.addTab(tab, "范德华相互作用")

    def _create_tcoupl_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)

        self.tcoupl_combo = QComboBox()
        self.tcoupl_combo.addItems([
            "no", "berendsen", "nose-hoover", "V-rescale", "andersen", "andersen-massive"
        ])
        self.tcoupl_combo.currentIndexChanged.connect(self._on_param_changed)

        self.tc_grps_edit = QLineEdit("System")
        self.tc_grps_edit.textChanged.connect(self._on_param_changed)

        self.tau_t_edit = QLineEdit("0.1")
        self.tau_t_edit.textChanged.connect(self._on_param_changed)

        self.ref_t_edit = QLineEdit("300")
        self.ref_t_edit.textChanged.connect(self._on_param_changed)

        layout.addRow("温度耦合方式 (tcoupl):", self.tcoupl_combo)
        layout.addRow("温度耦合组 (tc-grps):", self.tc_grps_edit)
        layout.addRow("耦合时间常数 (tau_t, ps):", self.tau_t_edit)
        layout.addRow("参考温度 (ref_t, K):", self.ref_t_edit)

        hint = QLabel("提示: 多组参数之间用空格分隔")
        hint.setStyleSheet("color: gray; font-size: 11px;")
        layout.addRow(hint)

        self.tab_widget.addTab(tab, "温度耦合")

    def _create_pcoupl_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)

        self.pcoupl_combo = QComboBox()
        self.pcoupl_combo.addItems([
            "no", "Berendsen", "Parrinello-Rahman", "MTTK", "C-rescale"
        ])
        self.pcoupl_combo.currentIndexChanged.connect(self._on_param_changed)

        self.pcoupltype_combo = QComboBox()
        self.pcoupltype_combo.addItems([
            "isotropic", "semiisotropic", "anisotropic", "surface-tension"
        ])
        self.pcoupltype_combo.currentIndexChanged.connect(self._on_param_changed)

        self.tau_p_edit = QLineEdit("2.0")
        self.tau_p_edit.textChanged.connect(self._on_param_changed)

        self.ref_p_edit = QLineEdit("1.0")
        self.ref_p_edit.textChanged.connect(self._on_param_changed)

        self.compressibility_edit = QLineEdit("4.5e-5")
        self.compressibility_edit.textChanged.connect(self._on_param_changed)

        self.refcoord_scaling_combo = QComboBox()
        self.refcoord_scaling_combo.addItems(["no", "com", "all"])
        self.refcoord_scaling_combo.currentIndexChanged.connect(self._on_param_changed)

        layout.addRow("压力耦合方式 (pcoupl):", self.pcoupl_combo)
        layout.addRow("压力耦合类型 (pcoupltype):", self.pcoupltype_combo)
        layout.addRow("耦合时间常数 (tau_p, ps):", self.tau_p_edit)
        layout.addRow("参考压力 (ref_p, bar):", self.ref_p_edit)
        layout.addRow("等温压缩系数 (compressibility):", self.compressibility_edit)
        layout.addRow("参考坐标缩放 (refcoord_scaling):", self.refcoord_scaling_combo)

        self.tab_widget.addTab(tab, "压力耦合")

    def _create_genvel_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)

        self.gen_vel_combo = QComboBox()
        self.gen_vel_combo.addItems(["no", "yes"])
        self.gen_vel_combo.currentIndexChanged.connect(self._on_param_changed)

        self.gen_temp_spin = QDoubleSpinBox()
        self.gen_temp_spin.setRange(0.0, 10000.0)
        self.gen_temp_spin.setSingleStep(10.0)
        self.gen_temp_spin.setDecimals(2)
        self.gen_temp_spin.setValue(300.0)
        self.gen_temp_spin.valueChanged.connect(self._on_param_changed)

        self.gen_seed_spin = QSpinBox()
        self.gen_seed_spin.setRange(-1, 2147483647)
        self.gen_seed_spin.setValue(-1)
        self.gen_seed_spin.valueChanged.connect(self._on_param_changed)

        self.constraints_combo = QComboBox()
        self.constraints_combo.addItems(["none", "h-bonds", "all-bonds", "h-angles", "all-angles"])
        self.constraints_combo.currentIndexChanged.connect(self._on_param_changed)

        self.constraint_algorithm_combo = QComboBox()
        self.constraint_algorithm_combo.addItems(["LINCS", "SHAKE"])
        self.constraint_algorithm_combo.currentIndexChanged.connect(self._on_param_changed)

        self.lincs_iter_spin = QSpinBox()
        self.lincs_iter_spin.setRange(1, 100)
        self.lincs_iter_spin.setValue(1)
        self.lincs_iter_spin.valueChanged.connect(self._on_param_changed)

        self.lincs_order_spin = QSpinBox()
        self.lincs_order_spin.setRange(1, 20)
        self.lincs_order_spin.setValue(4)
        self.lincs_order_spin.valueChanged.connect(self._on_param_changed)

        self.continuation_combo = QComboBox()
        self.continuation_combo.addItems(["no", "yes"])
        self.continuation_combo.currentIndexChanged.connect(self._on_param_changed)

        layout.addRow("生成速度 (gen_vel):", self.gen_vel_combo)
        layout.addRow("生成温度 (gen_temp, K):", self.gen_temp_spin)
        layout.addRow("随机种子 (gen_seed):", self.gen_seed_spin)
        layout.addRow("约束 (constraints):", self.constraints_combo)
        layout.addRow("约束算法 (constraint_algorithm):", self.constraint_algorithm_combo)
        layout.addRow("LINCS迭代次数 (lincs_iter):", self.lincs_iter_spin)
        layout.addRow("LINCS阶数 (lincs_order):", self.lincs_order_spin)
        layout.addRow("续跑模式 (continuation):", self.continuation_combo)

        self.tab_widget.addTab(tab, "速度生成 & 约束")

    def _create_annealing_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)

        self.annealing_combo = QComboBox()
        self.annealing_combo.addItems(["no", "single", "periodic"])
        self.annealing_combo.currentIndexChanged.connect(self._on_param_changed)

        self.annealing_npoints_spin = QSpinBox()
        self.annealing_npoints_spin.setRange(0, 100)
        self.annealing_npoints_spin.setValue(0)
        self.annealing_npoints_spin.valueChanged.connect(self._on_param_changed)

        self.annealing_time_edit = QLineEdit()
        self.annealing_time_edit.setPlaceholderText("例如: 0 100 200")
        self.annealing_time_edit.textChanged.connect(self._on_param_changed)

        self.annealing_temp_edit = QLineEdit()
        self.annealing_temp_edit.setPlaceholderText("例如: 300 400 500")
        self.annealing_temp_edit.textChanged.connect(self._on_param_changed)

        self.energygrps_edit = QLineEdit()
        self.energygrps_edit.setPlaceholderText("例如: Protein SOL")
        self.energygrps_edit.textChanged.connect(self._on_param_changed)

        layout.addRow("退火模式 (annealing):", self.annealing_combo)
        layout.addRow("退火点数 (annealing_npoints):", self.annealing_npoints_spin)
        layout.addRow("退火时间点 (annealing_time, ps):", self.annealing_time_edit)
        layout.addRow("退火温度点 (annealing_temp, K):", self.annealing_temp_edit)
        layout.addRow("能量组 (energygrps):", self.energygrps_edit)

        self.tab_widget.addTab(tab, "退火 & 能量组")

    def _on_param_changed(self):
        if self._updating:
            return
        self._update_preview()

    def _update_preview(self):
        mdp_text = self.generate_mdp()
        self.preview_edit.setPlainText(mdp_text)

    def parse_mdp(self, content):
        self._updating = True
        self._params.clear()
        for line in content.split("\n"):
            line = line.strip()
            if not line or line.startswith(";") or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                if ";" in value:
                    value = value.split(";")[0].strip()
                self._params[key] = value
        self._apply_params_to_ui()
        self._updating = False
        self._update_preview()

    def _apply_params_to_ui(self):
        p = self._params

        if "integrator" in p:
            idx = self.integrator_combo.findText(p["integrator"])
            if idx >= 0:
                self.integrator_combo.setCurrentIndex(idx)
        if "dt" in p:
            self.dt_spin.setValue(float(p["dt"]))
        if "nsteps" in p:
            self.nsteps_spin.setValue(int(p["nsteps"]))
        if "tinit" in p:
            self.tinit_spin.setValue(float(p["tinit"]))
        if "emtol" in p:
            self.emtol_spin.setValue(float(p["emtol"]))
        if "emstep" in p:
            self.emstep_spin.setValue(float(p["emstep"]))

        if "nstxout" in p:
            self.nstxout_spin.setValue(int(p["nstxout"]))
        if "nstvout" in p:
            self.nstvout_spin.setValue(int(p["nstvout"]))
        if "nstfout" in p:
            self.nstfout_spin.setValue(int(p["nstfout"]))
        if "nstenergy" in p:
            self.nstenergy_spin.setValue(int(p["nstenergy"]))
        if "nstlog" in p:
            self.nstlog_spin.setValue(int(p["nstlog"]))
        if "nstcheckpoint" in p:
            self.nstcheckpoint_spin.setValue(int(p["nstcheckpoint"]))
        if "nstxtcout" in p:
            self.nstxtcout_spin.setValue(int(p["nstxtcout"]))
        if "xtc-precision" in p:
            self.xtc_precision_spin.setValue(int(p["xtc-precision"]))

        if "cutoff-scheme" in p:
            idx = self.cutoff_scheme_combo.findText(p["cutoff-scheme"])
            if idx >= 0:
                self.cutoff_scheme_combo.setCurrentIndex(idx)
        if "nstlist" in p:
            self.nstlist_spin.setValue(int(p["nstlist"]))
        if "ns-type" in p:
            idx = self.ns_type_combo.findText(p["ns-type"])
            if idx >= 0:
                self.ns_type_combo.setCurrentIndex(idx)
        if "rlist" in p:
            self.rlist_spin.setValue(float(p["rlist"]))
        if "pbc" in p:
            idx = self.pbc_combo.findText(p["pbc"])
            if idx >= 0:
                self.pbc_combo.setCurrentIndex(idx)

        if "coulombtype" in p:
            idx = self.coulombtype_combo.findText(p["coulombtype"])
            if idx >= 0:
                self.coulombtype_combo.setCurrentIndex(idx)
        if "rcoulomb" in p:
            self.rcoulomb_spin.setValue(float(p["rcoulomb"]))
        if "pme_order" in p:
            self.pme_order_spin.setValue(int(p["pme_order"]))
        if "fourierspacing" in p:
            self.fourierspacing_spin.setValue(float(p["fourierspacing"]))
        if "ewald-rtol" in p:
            self.ewald_rtol_spin.setValue(float(p["ewald-rtol"]))

        if "vdw-type" in p:
            idx = self.vdw_type_combo.findText(p["vdw-type"])
            if idx >= 0:
                self.vdw_type_combo.setCurrentIndex(idx)
        if "rvdw" in p:
            self.rvdw_spin.setValue(float(p["rvdw"]))
        if "DispCorr" in p:
            idx = self.dispcorr_combo.findText(p["DispCorr"])
            if idx >= 0:
                self.dispcorr_combo.setCurrentIndex(idx)

        if "tcoupl" in p:
            idx = self.tcoupl_combo.findText(p["tcoupl"])
            if idx >= 0:
                self.tcoupl_combo.setCurrentIndex(idx)
        if "tc-grps" in p:
            self.tc_grps_edit.setText(p["tc-grps"])
        if "tau_t" in p:
            self.tau_t_edit.setText(p["tau_t"])
        if "ref_t" in p:
            self.ref_t_edit.setText(p["ref_t"])

        if "pcoupl" in p:
            idx = self.pcoupl_combo.findText(p["pcoupl"])
            if idx >= 0:
                self.pcoupl_combo.setCurrentIndex(idx)
        if "pcoupltype" in p:
            idx = self.pcoupltype_combo.findText(p["pcoupltype"])
            if idx >= 0:
                self.pcoupltype_combo.setCurrentIndex(idx)
        if "tau_p" in p:
            self.tau_p_edit.setText(p["tau_p"])
        if "ref_p" in p:
            self.ref_p_edit.setText(p["ref_p"])
        if "compressibility" in p:
            self.compressibility_edit.setText(p["compressibility"])
        if "refcoord_scaling" in p:
            idx = self.refcoord_scaling_combo.findText(p["refcoord_scaling"])
            if idx >= 0:
                self.refcoord_scaling_combo.setCurrentIndex(idx)

        if "gen_vel" in p:
            idx = self.gen_vel_combo.findText(p["gen_vel"])
            if idx >= 0:
                self.gen_vel_combo.setCurrentIndex(idx)
        if "gen_temp" in p:
            self.gen_temp_spin.setValue(float(p["gen_temp"]))
        if "gen_seed" in p:
            self.gen_seed_spin.setValue(int(p["gen_seed"]))
        if "constraints" in p:
            idx = self.constraints_combo.findText(p["constraints"])
            if idx >= 0:
                self.constraints_combo.setCurrentIndex(idx)
        if "constraint_algorithm" in p:
            idx = self.constraint_algorithm_combo.findText(p["constraint_algorithm"])
            if idx >= 0:
                self.constraint_algorithm_combo.setCurrentIndex(idx)
        if "lincs_iter" in p:
            self.lincs_iter_spin.setValue(int(p["lincs_iter"]))
        if "lincs_order" in p:
            self.lincs_order_spin.setValue(int(p["lincs_order"]))
        if "continuation" in p:
            idx = self.continuation_combo.findText(p["continuation"])
            if idx >= 0:
                self.continuation_combo.setCurrentIndex(idx)

        if "annealing" in p:
            idx = self.annealing_combo.findText(p["annealing"])
            if idx >= 0:
                self.annealing_combo.setCurrentIndex(idx)
        if "annealing_npoints" in p:
            self.annealing_npoints_spin.setValue(int(p["annealing_npoints"]))
        if "annealing_time" in p:
            self.annealing_time_edit.setText(p["annealing_time"])
        if "annealing_temp" in p:
            self.annealing_temp_edit.setText(p["annealing_temp"])
        if "energygrps" in p:
            self.energygrps_edit.setText(p["energygrps"])

    def generate_mdp(self):
        lines = []
        lines.append("; Generated by GROMACS GUI MDP Editor")
        lines.append("; " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        lines.append("")

        lines.append("; ============================================================")
        lines.append("; 运行参数")
        lines.append("; ============================================================")
        lines.append("integrator = " + self.integrator_combo.currentText())
        lines.append("dt = " + str(self.dt_spin.value()))
        lines.append("nsteps = " + str(self.nsteps_spin.value()))
        lines.append("tinit = " + str(self.tinit_spin.value()))
        integrator = self.integrator_combo.currentText().lower()
        if integrator in ["steep", "cg"]:
            lines.append("emtol = " + str(self.emtol_spin.value()))
            lines.append("emstep = " + str(self.emstep_spin.value()))
        lines.append("")

        lines.append("; ============================================================")
        lines.append("; 输出控制")
        lines.append("; ============================================================")
        lines.append("nstxout = " + str(self.nstxout_spin.value()))
        lines.append("nstvout = " + str(self.nstvout_spin.value()))
        lines.append("nstfout = " + str(self.nstfout_spin.value()))
        lines.append("nstenergy = " + str(self.nstenergy_spin.value()))
        lines.append("nstlog = " + str(self.nstlog_spin.value()))
        lines.append("nstcheckpoint = " + str(self.nstcheckpoint_spin.value()))
        lines.append("nstxtcout = " + str(self.nstxtcout_spin.value()))
        lines.append("xtc-precision = " + str(self.xtc_precision_spin.value()))
        lines.append("")

        lines.append("; ============================================================")
        lines.append("; 近邻列表")
        lines.append("; ============================================================")
        lines.append("cutoff-scheme = " + self.cutoff_scheme_combo.currentText())
        lines.append("nstlist = " + str(self.nstlist_spin.value()))
        lines.append("ns-type = " + self.ns_type_combo.currentText())
        lines.append("rlist = " + str(self.rlist_spin.value()))
        lines.append("pbc = " + self.pbc_combo.currentText())
        lines.append("")

        lines.append("; ============================================================")
        lines.append("; 静电相互作用")
        lines.append("; ============================================================")
        lines.append("coulombtype = " + self.coulombtype_combo.currentText())
        lines.append("rcoulomb = " + str(self.rcoulomb_spin.value()))
        ct = self.coulombtype_combo.currentText().lower()
        if ct in ["pme", "ewald", "pme-switch", "pme-user"]:
            lines.append("pme_order = " + str(self.pme_order_spin.value()))
            lines.append("fourierspacing = " + str(self.fourierspacing_spin.value()))
            lines.append("ewald-rtol = " + str(self.ewald_rtol_spin.value()))
        lines.append("")

        lines.append("; ============================================================")
        lines.append("; 范德华相互作用")
        lines.append("; ============================================================")
        lines.append("vdw-type = " + self.vdw_type_combo.currentText())
        lines.append("rvdw = " + str(self.rvdw_spin.value()))
        lines.append("DispCorr = " + self.dispcorr_combo.currentText())
        lines.append("")

        lines.append("; ============================================================")
        lines.append("; 温度耦合")
        lines.append("; ============================================================")
        lines.append("tcoupl = " + self.tcoupl_combo.currentText())
        tcoupl = self.tcoupl_combo.currentText().lower()
        if tcoupl != "no":
            lines.append("tc-grps = " + self.tc_grps_edit.text().strip())
            lines.append("tau_t = " + self.tau_t_edit.text().strip())
            lines.append("ref_t = " + self.ref_t_edit.text().strip())
        lines.append("")

        lines.append("; ============================================================")
        lines.append("; 压力耦合")
        lines.append("; ============================================================")
        lines.append("pcoupl = " + self.pcoupl_combo.currentText())
        pcoupl = self.pcoupl_combo.currentText().lower()
        if pcoupl != "no":
            lines.append("pcoupltype = " + self.pcoupltype_combo.currentText())
            lines.append("tau_p = " + self.tau_p_edit.text().strip())
            lines.append("ref_p = " + self.ref_p_edit.text().strip())
            lines.append("compressibility = " + self.compressibility_edit.text().strip())
            lines.append("refcoord_scaling = " + self.refcoord_scaling_combo.currentText())
        lines.append("")

        lines.append("; ============================================================")
        lines.append("; 速度生成 & 约束")
        lines.append("; ============================================================")
        lines.append("gen_vel = " + self.gen_vel_combo.currentText())
        if self.gen_vel_combo.currentText().lower() == "yes":
            lines.append("gen_temp = " + str(self.gen_temp_spin.value()))
            lines.append("gen_seed = " + str(self.gen_seed_spin.value()))
        lines.append("constraints = " + self.constraints_combo.currentText())
        if self.constraints_combo.currentText().lower() != "none":
            lines.append("constraint_algorithm = " + self.constraint_algorithm_combo.currentText())
            ca = self.constraint_algorithm_combo.currentText().lower()
            if "lincs" in ca:
                lines.append("lincs_iter = " + str(self.lincs_iter_spin.value()))
                lines.append("lincs_order = " + str(self.lincs_order_spin.value()))
        lines.append("continuation = " + self.continuation_combo.currentText())
        lines.append("")

        lines.append("; ============================================================")
        lines.append("; 退火 & 能量组")
        lines.append("; ============================================================")
        lines.append("annealing = " + self.annealing_combo.currentText())
        if self.annealing_combo.currentText().lower() != "no":
            lines.append("annealing_npoints = " + str(self.annealing_npoints_spin.value()))
            at = self.annealing_time_edit.text().strip()
            atp = self.annealing_temp_edit.text().strip()
            if at:
                lines.append("annealing_time = " + at)
            if atp:
                lines.append("annealing_temp = " + atp)
        eg = self.energygrps_edit.text().strip()
        if eg:
            lines.append("energygrps = " + eg)
        lines.append("")

        return "\n".join(lines)

    def load_from_file(self, filepath):
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            self.parse_mdp(content)
            return True
        except Exception as e:
            QMessageBox.critical(self, "加载失败", "无法加载文件:\n" + str(e))
            return False

    def save_to_file(self, filepath):
        try:
            content = self.generate_mdp()
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            return True
        except Exception as e:
            QMessageBox.critical(self, "保存失败", "无法保存文件:\n" + str(e))
            return False

    def _on_load_file(self):
        start_dir = self._default_dir if self._default_dir else ""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "加载MDP文件", start_dir, "MDP文件 (*.mdp);;所有文件 (*.*)"
        )
        if filepath:
            self.load_from_file(filepath)

    def _on_save_file(self):
        start_dir = os.path.join(self._default_dir, "untitled.mdp") if self._default_dir else "untitled.mdp"
        filepath, _ = QFileDialog.getSaveFileName(
            self, "保存MDP文件", start_dir, "MDP文件 (*.mdp);;所有文件 (*.*)"
        )
        if filepath:
            self.save_to_file(filepath)

    def _on_reset(self):
        self._updating = True
        self.integrator_combo.setCurrentIndex(0)
        self.dt_spin.setValue(0.002)
        self.nsteps_spin.setValue(50000)
        self.tinit_spin.setValue(0.0)
        self.emtol_spin.setValue(1000.0)
        self.emstep_spin.setValue(0.01)
        self.nstxout_spin.setValue(0)
        self.nstvout_spin.setValue(0)
        self.nstfout_spin.setValue(0)
        self.nstenergy_spin.setValue(1000)
        self.nstlog_spin.setValue(1000)
        self.nstcheckpoint_spin.setValue(10000)
        self.nstxtcout_spin.setValue(5000)
        self.xtc_precision_spin.setValue(1000)
        self.cutoff_scheme_combo.setCurrentIndex(0)
        self.nstlist_spin.setValue(10)
        self.ns_type_combo.setCurrentIndex(0)
        self.rlist_spin.setValue(1.0)
        self.pbc_combo.setCurrentIndex(0)
        self.coulombtype_combo.setCurrentIndex(0)
        self.rcoulomb_spin.setValue(1.0)
        self.pme_order_spin.setValue(4)
        self.fourierspacing_spin.setValue(0.16)
        self.ewald_rtol_spin.setValue(1e-5)
        self.vdw_type_combo.setCurrentIndex(0)
        self.rvdw_spin.setValue(1.0)
        self.dispcorr_combo.setCurrentIndex(0)
        self.tcoupl_combo.setCurrentIndex(0)
        self.tc_grps_edit.setText("System")
        self.tau_t_edit.setText("0.1")
        self.ref_t_edit.setText("300")
        self.pcoupl_combo.setCurrentIndex(0)
        self.pcoupltype_combo.setCurrentIndex(0)
        self.tau_p_edit.setText("2.0")
        self.ref_p_edit.setText("1.0")
        self.compressibility_edit.setText("4.5e-5")
        self.refcoord_scaling_combo.setCurrentIndex(0)
        self.gen_vel_combo.setCurrentIndex(0)
        self.gen_temp_spin.setValue(300.0)
        self.gen_seed_spin.setValue(-1)
        self.constraints_combo.setCurrentIndex(0)
        self.constraint_algorithm_combo.setCurrentIndex(0)
        self.lincs_iter_spin.setValue(1)
        self.lincs_order_spin.setValue(4)
        self.continuation_combo.setCurrentIndex(0)
        self.annealing_combo.setCurrentIndex(0)
        self.annealing_npoints_spin.setValue(0)
        self.annealing_time_edit.clear()
        self.annealing_temp_edit.clear()
        self.energygrps_edit.clear()
        self.template_combo.setCurrentIndex(0)
        self._updating = False
        self._update_preview()

    def _on_template_selected(self, index):
        if index <= 0:
            return
        template_name = self.template_combo.itemText(index)
        if template_name in self.MDP_TEMPLATES:
            template = self.MDP_TEMPLATES[template_name]
            mdp_lines = []
            for key, value in template.items():
                mdp_lines.append(f"{key} = {value}")
            self.parse_mdp("\n".join(mdp_lines))

    def get_mdp_content(self):
        return self.generate_mdp()

    def set_default_dir(self, dirpath):
        self._default_dir = dirpath
