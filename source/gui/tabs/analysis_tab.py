# -*- coding: utf-8 -*-
"""
Part 5: 结果分析与可视化独立页面组件
从 main_window.py 拆分抽离。
负责：
1. 通用分析输入配置 (XTC / TPR / GRO / EDR / NDX, 起止时间与采样步长)
2. 轨迹文件与核心文件状态校验
3. 常用 GROMACS 分析工具：
   - 能量与热力学 (energy, density, msd)
   - 结构稳定性 (rms, rmsf, gyrate, distance, angle, pairdist)
   - 相互作用 (hbond, rdf, sasa, saltbr, do_dssp)
   - 高级分析方法 (covar, eigenvalue, principal, trajectory, cluster)
4. 片段分析系统：
   - 片段索引生成器 (make_ndx)
   - 批量片段-片段 RDF 分析
   - 最近邻距离分析 (pairdist)
5. 结果自动绘图系统 (matplotlib Agg 离屏出图)
6. 能量分解分析 (energy decomposition)
7. 多体系批量处理系统 (Batch Processing)
8. 命令统一通过信号 run_requested 上抛至主窗口统一任务调度器
"""

import os
import glob
import subprocess
from typing import Optional, Callable

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QSpinBox, QDoubleSpinBox, QGroupBox, QScrollArea,
    QTableWidget, QTableWidgetItem, QFileDialog, QMessageBox
)

from simulation.analysis import build_analysis_command

class AnalysisTab(QWidget):
    """Part 5: 结果分析与可视化独立页面组件

    Signals:
        run_requested(cmd, work_dir, step_name, stdin_input): 请求主调度器执行构建好的命令链
        log_requested(message, level): 请求向主日志视口追加日志
    """

    run_requested = pyqtSignal(object, str, str, object)
    log_requested = pyqtSignal(str, str)

    def __init__(
        self,
        get_work_dir: Optional[Callable[[], str]] = None,
        get_gmx_path: Optional[Callable[[], str]] = None,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self._get_work_dir = get_work_dir or (lambda: os.getcwd())
        self._get_gmx_path = get_gmx_path or (lambda: "gmx")
        self.analysis_widgets = {}

        self._init_ui()

    def _adjust_brightness(self, hex_color: str, factor: float) -> str:
        hex_color = hex_color.lstrip('#')
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        r = min(255, max(0, int(r * factor)))
        g = min(255, max(0, int(g * factor)))
        b = min(255, max(0, int(b * factor)))
        return f"#{r:02x}{g:02x}{b:02x}"

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

        # 1. 通用分析参数
        common_group = QGroupBox("通用分析参数")
        cgrid = QGridLayout(common_group)

        self.ana_input_xtc, ana_xtc_layout = self._create_file_input(
            "md.xtc", "md.xtc", "轨迹文件 (*.xtc *.trr *.gro);;所有文件 (*.*)", "选择轨迹文件"
        )
        self.ana_input_tpr, ana_tpr_layout = self._create_file_input(
            "md.tpr", "md.tpr", "TPR文件 (*.tpr);;所有文件 (*.*)", "选择TPR文件"
        )
        self.ana_input_gro, ana_gro_layout = self._create_file_input(
            "md.gro", "md.gro", "结构文件 (*.gro *.pdb);;所有文件 (*.*)", "选择结构文件"
        )
        self.ana_input_edr, ana_edr_layout = self._create_file_input(
            "md.edr", "md.edr", "能量文件 (*.edr);;所有文件 (*.*)", "选择能量文件"
        )
        self.ana_index, ana_idx_layout = self._create_file_input(
            "index.ndx (可选)", "", "索引文件 (*.ndx);;所有文件 (*.*)", "选择索引文件"
        )
        self.ana_b = QDoubleSpinBox()
        self.ana_b.setRange(0, 100000)
        self.ana_b.setValue(0)
        self.ana_b.setDecimals(1)
        self.ana_b.setSuffix(" ps")
        self.ana_e = QDoubleSpinBox()
        self.ana_e.setRange(0, 100000)
        self.ana_e.setValue(0)
        self.ana_e.setDecimals(1)
        self.ana_e.setSuffix(" ps (0=到结尾)")
        self.ana_dt = QDoubleSpinBox()
        self.ana_dt.setRange(0, 100000)
        self.ana_dt.setValue(0)
        self.ana_dt.setDecimals(1)
        self.ana_dt.setSuffix(" ps (0=全部)")

        cgrid.addWidget(QLabel("轨迹文件:"), 0, 0)
        cgrid.addLayout(ana_xtc_layout, 0, 1)
        cgrid.addWidget(QLabel("运行输入:"), 0, 2)
        cgrid.addLayout(ana_tpr_layout, 0, 3)

        cgrid.addWidget(QLabel("结构文件:"), 1, 0)
        cgrid.addLayout(ana_gro_layout, 1, 1)
        cgrid.addWidget(QLabel("能量文件:"), 1, 2)
        cgrid.addLayout(ana_edr_layout, 1, 3)

        cgrid.addWidget(QLabel("索引文件:"), 2, 0)
        cgrid.addLayout(ana_idx_layout, 2, 1)
        cgrid.addWidget(QLabel("起始时间:"), 2, 2)
        cgrid.addWidget(self.ana_b, 2, 3)

        cgrid.addWidget(QLabel("结束时间:"), 3, 0)
        cgrid.addWidget(self.ana_e, 3, 1)
        cgrid.addWidget(QLabel("时间间隔:"), 3, 2)
        cgrid.addWidget(self.ana_dt, 3, 3)

        vbox.addWidget(common_group)

        # 2. 文件管理与校验
        file_check_group = QGroupBox("📁 文件管理与校验")
        file_check_group.setProperty("role", "phaseGroup")
        file_check_layout = QVBoxLayout(file_check_group)
        file_check_layout.setSpacing(8)

        file_check_desc = QLabel("校验轨迹文件完整性，检查核心文件是否存在")
        file_check_desc.setWordWrap(True)
        file_check_desc.setProperty("role", "desc")
        file_check_layout.addWidget(file_check_desc)

        file_check_grid = QGridLayout()
        file_check_grid.setSpacing(6)

        self.file_check_btn = QPushButton("校验轨迹文件 (gmx check)")
        self.file_check_btn.setProperty("role", "actionBtn")
        self.file_check_btn.clicked.connect(self.run_file_check)
        file_check_grid.addWidget(self.file_check_btn, 0, 0)

        self.file_status_btn = QPushButton("检查文件状态")
        self.file_status_btn.setProperty("role", "secondaryTool")
        self.file_status_btn.clicked.connect(self.check_file_status)
        file_check_grid.addWidget(self.file_status_btn, 0, 1)

        file_check_layout.addLayout(file_check_grid)
        vbox.addWidget(file_check_group)

        self.analysis_widgets = {}

        # 3. 能量与热力学分析
        energy_group = QGroupBox("🌡️ 能量与热力学分析")
        energy_group.setProperty("role", "phaseGroup")
        energy_layout = QVBoxLayout(energy_group)
        energy_layout.setSpacing(6)

        energy_analyses = [
            ("energy", "能量分析", "分析温度、压力、密度、总能量、势能、动能等", "energy.xvg", "#E65100"),
            ("density", "密度分析", "计算密度分布", "density.xvg", "#EF6C00"),
            ("msd", "均方位移", "计算均方位移用于扩散系数", "msd.xvg", "#F57C00"),
        ]

        for key, name, desc, default_out, color in energy_analyses:
            grp = QGroupBox(f"{name}")
            grp.setProperty("role", "toolCard")
            g = QGridLayout(grp)
            g.addWidget(QLabel(desc), 0, 0, 1, 4)

            out_edit = QLineEdit(default_out)
            sel_edit = QLineEdit()
            sel_edit.setPlaceholderText("如 -select 'resname ALA'")
            ref_edit = QLineEdit()
            ref_edit.setPlaceholderText("参考结构 (可选)")

            run_btn = QPushButton("运行")
            run_btn.setProperty("role", "actionBtn")

            g.addWidget(QLabel("输出文件:"), 1, 0)
            g.addWidget(out_edit, 1, 1)
            g.addWidget(QLabel("选择组:"), 1, 2)
            g.addWidget(sel_edit, 1, 3)
            g.addWidget(run_btn, 2, 0, 1, 4)

            self.analysis_widgets[key] = {
                "out": out_edit,
                "sel": sel_edit,
                "ref": ref_edit,
                "run_btn": run_btn
            }
            run_btn.clicked.connect(lambda checked=False, k=key: self.run_analysis(k))
            energy_layout.addWidget(grp)

        vbox.addWidget(energy_group)

        # 4. 结构稳定性分析
        struct_group = QGroupBox("📐 结构稳定性分析")
        struct_group.setProperty("role", "phaseGroup")
        struct_layout = QVBoxLayout(struct_group)
        struct_layout.setSpacing(6)

        struct_analyses = [
            ("rms", "RMSD 分析", "计算根均方偏差", "rmsd.xvg", "#1976D2"),
            ("rmsf", "RMSF 分析", "计算根均方涨落", "rmsf.xvg", "#1565C0"),
            ("gyrate", "回旋半径", "计算回旋半径", "gyrate.xvg", "#0D47A1"),
            ("distance", "距离分析", "计算指定原子/残基间距离", "distance.xvg", "#1565C0"),
            ("angle", "角度分析", "计算键角或二面角", "angle.xvg", "#0D47A1"),
            ("pairdist", "配对距离分布", "计算配对距离分布", "pairdist.xvg", "#1976D2"),
        ]

        for key, name, desc, default_out, color in struct_analyses:
            grp = QGroupBox(f"{name}")
            grp.setProperty("role", "toolCard")
            g = QGridLayout(grp)
            g.addWidget(QLabel(desc), 0, 0, 1, 4)

            out_edit = QLineEdit(default_out)
            sel_edit = QLineEdit()
            sel_edit.setPlaceholderText("如 -select 'resname ALA'")
            ref_edit = QLineEdit()
            ref_edit.setPlaceholderText("参考结构 (可选)")

            run_btn = QPushButton("运行")
            run_btn.setProperty("role", "actionBtn")

            g.addWidget(QLabel("输出文件:"), 1, 0)
            g.addWidget(out_edit, 1, 1)
            g.addWidget(QLabel("选择组:"), 1, 2)
            g.addWidget(sel_edit, 1, 3)

            if key in ["rms", "rmsf", "distance", "angle", "cluster"]:
                g.addWidget(QLabel("参考/组2:"), 2, 0)
                g.addWidget(ref_edit, 2, 1)
                g.addWidget(run_btn, 2, 2, 1, 2)
            else:
                g.addWidget(run_btn, 2, 0, 1, 4)

            self.analysis_widgets[key] = {
                "out": out_edit,
                "sel": sel_edit,
                "ref": ref_edit,
                "run_btn": run_btn
            }
            run_btn.clicked.connect(lambda checked=False, k=key: self.run_analysis(k))
            struct_layout.addWidget(grp)

        vbox.addWidget(struct_group)

        # 5. 相互作用分析
        interact_group = QGroupBox("🔗 相互作用分析")
        interact_group.setProperty("role", "phaseGroup")
        interact_layout = QVBoxLayout(interact_group)
        interact_layout.setSpacing(6)

        interact_analyses = [
            ("hbond", "氢键分析", "分析氢键数量及寿命", "hbond.xvg", "#2E7D32"),
            ("rdf", "径向分布函数", "计算径向分布函数", "rdf.xvg", "#388E3C"),
            ("sasa", "溶剂可及表面积", "计算溶剂可及表面积", "sasa.xvg", "#1B5E20"),
            ("saltbr", "盐桥分析", "分析盐桥相互作用", "saltbr.xvg", "#2E7D32"),
            ("do_dssp", "二级结构分析", "分析二级结构含量变化", "dssp.xpm", "#388E3C"),
        ]

        for key, name, desc, default_out, color in interact_analyses:
            grp = QGroupBox(f"{name}")
            grp.setProperty("role", "toolCard")
            g = QGridLayout(grp)
            g.addWidget(QLabel(desc), 0, 0, 1, 4)

            out_edit = QLineEdit(default_out)
            sel_edit = QLineEdit()
            sel_edit.setPlaceholderText("如 -select 'resname ALA'")
            ref_edit = QLineEdit()
            ref_edit.setPlaceholderText("参考结构 (可选)")

            run_btn = QPushButton("运行")
            run_btn.setProperty("role", "actionBtn")

            g.addWidget(QLabel("输出文件:"), 1, 0)
            g.addWidget(out_edit, 1, 1)
            g.addWidget(QLabel("选择组:"), 1, 2)
            g.addWidget(sel_edit, 1, 3)
            g.addWidget(run_btn, 2, 0, 1, 4)

            self.analysis_widgets[key] = {
                "out": out_edit,
                "sel": sel_edit,
                "ref": ref_edit,
                "run_btn": run_btn
            }
            run_btn.clicked.connect(lambda checked=False, k=key: self.run_analysis(k))
            interact_layout.addWidget(grp)

        # 细化针对性提示
        if "energy" in self.analysis_widgets:
            self.analysis_widgets["energy"]["sel"].setPlaceholderText("能量项: Potential Temperature Pressure Density（留空默认 Potential）")
        if "rdf" in self.analysis_widgets:
            self.analysis_widgets["rdf"]["sel"].setPlaceholderText("如 -ref='group Protein' -sel='group Water' -seltype=mol_com -bin=0.01")
        if "pairdist" in self.analysis_widgets:
            self.analysis_widgets["pairdist"]["sel"].setPlaceholderText("如 -ref='group Protein' -sel='group Water' -type=min")
        if "cluster" in self.analysis_widgets:
            self.analysis_widgets["cluster"]["sel"].setPlaceholderText("如 -method=linkage -cutoff=0.2")
        if "density" in self.analysis_widgets:
            self.analysis_widgets["density"]["sel"].setPlaceholderText("如 -d=Z -sl=100")
        if "rms" in self.analysis_widgets:
            self.analysis_widgets["rms"]["sel"].setPlaceholderText("留空自动对所有原子计算")
            self.analysis_widgets["rms"]["ref"].setPlaceholderText("参考结构（默认TPR）")
        if "rmsf" in self.analysis_widgets:
            self.analysis_widgets["rmsf"]["sel"].setPlaceholderText("组名（留空使用所有原子）")
        if "gyrate" in self.analysis_widgets:
            self.analysis_widgets["gyrate"]["sel"].setPlaceholderText("组名（留空使用所有原子）")
        if "sasa" in self.analysis_widgets:
            self.analysis_widgets["sasa"]["sel"].setPlaceholderText("组名（留空使用所有原子）")
        if "hbond" in self.analysis_widgets:
            self.analysis_widgets["hbond"]["sel"].setPlaceholderText("供体/受体组（自动选择Protein-SOL）")
        if "distance" in self.analysis_widgets:
            self.analysis_widgets["distance"]["sel"].setPlaceholderText("组1（留空使用System）")
            self.analysis_widgets["distance"]["ref"].setPlaceholderText("组2（留空使用System）")
        if "angle" in self.analysis_widgets:
            self.analysis_widgets["angle"]["sel"].setPlaceholderText("留空使用前3个原子")
        if "msd" in self.analysis_widgets:
            self.analysis_widgets["msd"]["sel"].setPlaceholderText("如 -sel 'resname DON'（留空所有原子）")
            self.analysis_widgets["msd"]["ref"].setPlaceholderText("输入 molecules 启用按分子计算")
        if "do_dssp" in self.analysis_widgets:
            self.analysis_widgets["do_dssp"]["sel"].setPlaceholderText("蛋白质组（留空使用Protein）")
        if "saltbr" in self.analysis_widgets:
            self.analysis_widgets["saltbr"]["sel"].setPlaceholderText("蛋白质组（留空使用Protein）")

        vbox.addWidget(interact_group)

        # 6. 片段分析
        fragment_group = QGroupBox("🧩 片段分析")
        fragment_group.setProperty("role", "phaseGroup")
        fragment_layout = QVBoxLayout(fragment_group)
        fragment_layout.setSpacing(8)

        # 子模块A: 片段索引生成器
        ndx_gen_group = QGroupBox("片段索引生成器 (make_ndx)")
        ndx_gen_group.setProperty("role", "toolCard")
        ndx_gen_layout = QGridLayout(ndx_gen_group)
        ndx_gen_layout.setSpacing(5)

        ndx_gen_layout.addWidget(QLabel("分子类型:"), 0, 0)
        self.ndx_gen_type = QComboBox()
        self.ndx_gen_type.addItems(["给体 (Donor)", "受体 (Acceptor)", "溶剂 (Solvent)", "添加剂 (Additive)", "自定义"])
        ndx_gen_layout.addWidget(self.ndx_gen_type, 0, 1)

        ndx_gen_layout.addWidget(QLabel("分子数量:"), 0, 2)
        self.ndx_gen_nmol = QSpinBox()
        self.ndx_gen_nmol.setRange(1, 10000)
        self.ndx_gen_nmol.setValue(50)
        ndx_gen_layout.addWidget(self.ndx_gen_nmol, 0, 3)

        ndx_gen_layout.addWidget(QLabel("每分子原子数:"), 1, 0)
        self.ndx_gen_natom = QSpinBox()
        self.ndx_gen_natom.setRange(1, 10000)
        self.ndx_gen_natom.setValue(626)
        ndx_gen_layout.addWidget(self.ndx_gen_natom, 1, 1)

        ndx_gen_layout.addWidget(QLabel("起始原子偏移:"), 1, 2)
        self.ndx_gen_offset = QSpinBox()
        self.ndx_gen_offset.setRange(0, 1000000)
        self.ndx_gen_offset.setValue(0)
        ndx_gen_layout.addWidget(self.ndx_gen_offset, 1, 3)

        ndx_gen_layout.addWidget(QLabel("片段定义 (名称: 原子范围, 如 1-10,20-25):"), 2, 0, 1, 4)
        self.ndx_gen_table = QTableWidget()
        self.ndx_gen_table.setColumnCount(2)
        self.ndx_gen_table.setHorizontalHeaderLabels(["片段名称", "原子范围 (逗号分隔区间)"])
        self.ndx_gen_table.horizontalHeader().setStretchLastSection(True)
        self.ndx_gen_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.ndx_gen_table.setMinimumHeight(120)
        self.ndx_gen_table.setMaximumHeight(150)
        self.ndx_gen_table.setRowCount(2)
        self.ndx_gen_table.setItem(0, 0, QTableWidgetItem("s1_BDT"))
        self.ndx_gen_table.setItem(0, 1, QTableWidgetItem("1-22,24-27,30-31,34-37,39-42,45-46,50-51,81-89,91-92,94-121"))
        self.ndx_gen_table.setItem(1, 0, QTableWidgetItem("s1_BDD"))
        self.ndx_gen_table.setItem(1, 1, QTableWidgetItem("23,28-29,32-33,38,43-44,47-49,52-80,90,93,122-157"))
        ndx_gen_layout.addWidget(self.ndx_gen_table, 3, 0, 1, 4)

        ndx_table_btn_layout = QHBoxLayout()
        self.ndx_add_row_btn = QPushButton("+ 添加片段")
        self.ndx_del_row_btn = QPushButton("- 删除片段")
        self.ndx_clear_btn = QPushButton("清空")
        self.ndx_load_def_btn = QPushButton("从文件加载定义")
        ndx_table_btn_layout.addWidget(self.ndx_add_row_btn)
        ndx_table_btn_layout.addWidget(self.ndx_del_row_btn)
        ndx_table_btn_layout.addWidget(self.ndx_clear_btn)
        ndx_table_btn_layout.addWidget(self.ndx_load_def_btn)
        ndx_table_btn_layout.addStretch()
        ndx_gen_layout.addLayout(ndx_table_btn_layout, 4, 0, 1, 4)

        ndx_gen_layout.addWidget(QLabel("输出文件名:"), 5, 0)
        self.ndx_gen_output = QLineEdit("fragment.ndx")
        ndx_gen_layout.addWidget(self.ndx_gen_output, 5, 1, 1, 2)
        self.ndx_gen_btn = QPushButton("生成片段索引文件")
        self.ndx_gen_btn.setProperty("role", "browseBtn")
        ndx_gen_layout.addWidget(self.ndx_gen_btn, 5, 3)

        self.ndx_add_row_btn.clicked.connect(lambda: self.ndx_gen_table.insertRow(self.ndx_gen_table.rowCount()))
        self.ndx_del_row_btn.clicked.connect(self.remove_ndx_row)
        self.ndx_clear_btn.clicked.connect(lambda: self.ndx_gen_table.setRowCount(0))
        self.ndx_load_def_btn.clicked.connect(self.load_fragment_definition)
        self.ndx_gen_btn.clicked.connect(self.generate_fragment_ndx)

        fragment_layout.addWidget(ndx_gen_group)

        # 子模块B: 片段-片段 RDF 分析
        rdf_frag_group = QGroupBox("片段-片段 RDF 分析")
        rdf_frag_group.setProperty("role", "toolCard")
        rdf_frag_layout = QGridLayout(rdf_frag_group)
        rdf_frag_layout.setSpacing(5)

        rdf_frag_layout.addWidget(QLabel("索引文件:"), 0, 0)
        self.rdf_frag_ndx_input, rdf_frag_ndx_layout = self._create_file_input(
            "fragment.ndx", "fragment.ndx", "索引文件 (*.ndx);;所有文件 (*.*)", "选择索引文件"
        )
        rdf_frag_layout.addLayout(rdf_frag_ndx_layout, 0, 1, 1, 3)

        rdf_frag_layout.addWidget(QLabel("参考组 (Ref):"), 1, 0)
        self.rdf_frag_ref = QLineEdit()
        self.rdf_frag_ref.setPlaceholderText("如 All_s1_BDT (多个用逗号分隔)")
        rdf_frag_layout.addWidget(self.rdf_frag_ref, 1, 1)

        rdf_frag_layout.addWidget(QLabel("选择组 (Sel):"), 1, 2)
        self.rdf_frag_sel = QLineEdit()
        self.rdf_frag_sel.setPlaceholderText("如 All_BTP (多个用逗号分隔)")
        rdf_frag_layout.addWidget(self.rdf_frag_sel, 1, 3)

        rdf_frag_layout.addWidget(QLabel("计算类型:"), 2, 0)
        self.rdf_frag_seltype = QComboBox()
        self.rdf_frag_seltype.addItems([
            "mol_com (分子质心)",
            "atom (原子级)",
            "res_com (残基质心)",
            "mol_com_nointra (分子质心,排除分子内)"
        ])
        rdf_frag_layout.addWidget(self.rdf_frag_seltype, 2, 1)

        rdf_frag_layout.addWidget(QLabel("径向分辨率:"), 2, 2)
        self.rdf_frag_bin = QDoubleSpinBox()
        self.rdf_frag_bin.setRange(0.001, 1.0)
        self.rdf_frag_bin.setValue(0.01)
        self.rdf_frag_bin.setDecimals(3)
        self.rdf_frag_bin.setSuffix(" nm")
        rdf_frag_layout.addWidget(self.rdf_frag_bin, 2, 3)

        rdf_frag_layout.addWidget(QLabel("起始时间:"), 3, 0)
        self.rdf_frag_b = QDoubleSpinBox()
        self.rdf_frag_b.setRange(0, 100000)
        self.rdf_frag_b.setValue(0)
        self.rdf_frag_b.setDecimals(1)
        self.rdf_frag_b.setSuffix(" ps")
        rdf_frag_layout.addWidget(self.rdf_frag_b, 3, 1)

        rdf_frag_layout.addWidget(QLabel("结束时间:"), 3, 2)
        self.rdf_frag_e = QDoubleSpinBox()
        self.rdf_frag_e.setRange(0, 100000)
        self.rdf_frag_e.setValue(0)
        self.rdf_frag_e.setDecimals(1)
        self.rdf_frag_e.setSuffix(" ps (0=到结尾)")
        rdf_frag_layout.addWidget(self.rdf_frag_e, 3, 3)

        rdf_frag_layout.addWidget(QLabel("输出目录:"), 4, 0)
        self.rdf_frag_outdir = QLineEdit("fragment_RDF")
        rdf_frag_layout.addWidget(self.rdf_frag_outdir, 4, 1, 1, 2)

        self.rdf_frag_run_btn = QPushButton("批量计算片段RDF")
        self.rdf_frag_run_btn.setProperty("role", "browseBtn")
        rdf_frag_layout.addWidget(self.rdf_frag_run_btn, 4, 3)
        self.rdf_frag_run_btn.clicked.connect(self.run_fragment_rdf_batch)

        fragment_layout.addWidget(rdf_frag_group)

        # 子模块C: 最近邻距离分析
        pairdist_group = QGroupBox("最近邻距离分析 (pairdist)")
        pairdist_group.setProperty("role", "toolCard")
        pairdist_layout = QGridLayout(pairdist_group)
        pairdist_layout.setSpacing(5)

        pairdist_layout.addWidget(QLabel("参考组:"), 0, 0)
        self.pairdist_ref = QLineEdit()
        self.pairdist_ref.setPlaceholderText("如 All_s1_BDT")
        pairdist_layout.addWidget(self.pairdist_ref, 0, 1)

        pairdist_layout.addWidget(QLabel("选择组:"), 0, 2)
        self.pairdist_sel = QLineEdit()
        self.pairdist_sel.setPlaceholderText("如 All_BTP")
        pairdist_layout.addWidget(self.pairdist_sel, 0, 3)

        pairdist_layout.addWidget(QLabel("计算类型:"), 1, 0)
        self.pairdist_type = QComboBox()
        self.pairdist_type.addItems(["min (最近邻)", "max (最远邻)", "maxdist"])
        pairdist_layout.addWidget(self.pairdist_type, 1, 1)

        pairdist_layout.addWidget(QLabel("输出文件:"), 1, 2)
        self.pairdist_out = QLineEdit("pairdist.xvg")
        pairdist_layout.addWidget(self.pairdist_out, 1, 3)

        self.pairdist_run_btn = QPushButton("计算最近邻距离")
        self.pairdist_run_btn.setProperty("role", "browseBtn")
        pairdist_layout.addWidget(self.pairdist_run_btn, 2, 0, 1, 4)
        self.pairdist_run_btn.clicked.connect(self.run_pairdist_analysis)

        fragment_layout.addWidget(pairdist_group)
        vbox.addWidget(fragment_group)

        # 7. 高级分析方法
        advanced_group = QGroupBox("📊 高级分析方法")
        advanced_group.setProperty("role", "phaseGroup")
        advanced_layout = QVBoxLayout(advanced_group)
        advanced_layout.setSpacing(6)

        advanced_analyses = [
            ("covar", "协方差矩阵", "计算原子位置协方差矩阵", "covar.xvg", "#6A1B9A"),
            ("eigenvalue", "特征值分解", "计算协方差矩阵特征值", "eigenval.xvg", "#7B1FA2"),
            ("principal", "主成分分析", "执行主成分分析", "pc.xvg", "#6A1B9A"),
            ("trajectory", "轨迹投影", "将轨迹投影到主成分", "proj.xvg", "#7B1FA2"),
            ("cluster", "聚类分析", "基于 RMSD 对构象聚类", "cluster.xpm", "#6A1B9A"),
        ]

        for key, name, desc, default_out, color in advanced_analyses:
            grp = QGroupBox(f"{name}")
            grp.setProperty("role", "toolCard")
            g = QGridLayout(grp)
            g.addWidget(QLabel(desc), 0, 0, 1, 4)

            out_edit = QLineEdit(default_out)
            sel_edit = QLineEdit()
            sel_edit.setPlaceholderText("如 -select 'resname ALA'")
            ref_edit = QLineEdit()
            ref_edit.setPlaceholderText("参考结构 (可选)")

            run_btn = QPushButton("运行")
            run_btn.setProperty("role", "actionBtn")

            g.addWidget(QLabel("输出文件:"), 1, 0)
            g.addWidget(out_edit, 1, 1)
            g.addWidget(QLabel("选择组:"), 1, 2)
            g.addWidget(sel_edit, 1, 3)

            if key in ["rms", "rmsf", "distance", "angle", "cluster"]:
                g.addWidget(QLabel("参考/组2:"), 2, 0)
                g.addWidget(ref_edit, 2, 1)
                g.addWidget(run_btn, 2, 2, 1, 2)
            else:
                g.addWidget(run_btn, 2, 0, 1, 4)

            self.analysis_widgets[key] = {
                "out": out_edit,
                "sel": sel_edit,
                "ref": ref_edit,
                "run_btn": run_btn
            }
            run_btn.clicked.connect(lambda checked=False, k=key: self.run_analysis(k))
            advanced_layout.addWidget(grp)

        vbox.addWidget(advanced_group)

        # 8. 结果自动绘图
        plot_group = QGroupBox("📈 结果自动绘图")
        plot_group.setProperty("role", "phaseGroup")
        plot_layout = QVBoxLayout(plot_group)
        plot_layout.setSpacing(8)

        plot_desc = QLabel("自动读取xvg文件并生成符合期刊标准的科研图表")
        plot_desc.setWordWrap(True)
        plot_desc.setProperty("role", "desc")
        plot_layout.addWidget(plot_desc)

        plot_grid = QGridLayout()
        plot_grid.setSpacing(6)

        plot_grid.addWidget(QLabel("输入文件:"), 0, 0)
        self.plot_input, plot_input_layout = self._create_file_input(
            "*.xvg", "", "xvg文件 (*.xvg);;所有文件 (*.*)", "选择xvg文件"
        )
        plot_grid.addLayout(plot_input_layout, 0, 1, 1, 3)

        plot_grid.addWidget(QLabel("图表类型:"), 1, 0)
        self.plot_type = QComboBox()
        self.plot_type.addItems(["折线图 (Line)", "柱状图 (Bar)", "散点图 (Scatter)", "多曲线对比"])
        plot_grid.addWidget(self.plot_type, 1, 1)

        plot_grid.addWidget(QLabel("X轴标签:"), 1, 2)
        self.plot_xlabel = QLineEdit("Time (ns)")
        plot_grid.addWidget(self.plot_xlabel, 1, 3)

        plot_grid.addWidget(QLabel("Y轴标签:"), 2, 0)
        self.plot_ylabel = QLineEdit("Value")
        plot_grid.addWidget(self.plot_ylabel, 2, 1)

        plot_grid.addWidget(QLabel("图表标题:"), 2, 2)
        self.plot_title = QLineEdit("")
        plot_grid.addWidget(self.plot_title, 2, 3)

        plot_grid.addWidget(QLabel("输出图片:"), 3, 0)
        self.plot_output = QLineEdit("plot.png")
        plot_grid.addWidget(self.plot_output, 3, 1, 1, 2)

        self.plot_dpi = QSpinBox()
        self.plot_dpi.setRange(100, 600)
        self.plot_dpi.setValue(300)
        self.plot_dpi.setSuffix(" dpi")
        plot_grid.addWidget(self.plot_dpi, 3, 3)

        plot_layout.addLayout(plot_grid)

        self.plot_run_btn = QPushButton("生成图表")
        self.plot_run_btn.setProperty("role", "browseBtn")
        self.plot_run_btn.clicked.connect(self.generate_plot)
        plot_layout.addWidget(self.plot_run_btn)

        vbox.addWidget(plot_group)

        # 9. 能量分解分析
        energy_decomp_group = QGroupBox("⚡ 能量分解分析")
        energy_decomp_group.setProperty("role", "phaseGroup")
        energy_decomp_layout = QVBoxLayout(energy_decomp_group)
        energy_decomp_layout.setSpacing(8)

        energy_decomp_desc = QLabel("提取并分解能量项，分析组分间相互作用")
        energy_decomp_desc.setWordWrap(True)
        energy_decomp_desc.setProperty("role", "desc")
        energy_decomp_layout.addWidget(energy_decomp_desc)

        ed_grid = QGridLayout()
        ed_grid.setSpacing(6)

        ed_grid.addWidget(QLabel("能量项:"), 0, 0)
        self.ed_terms = QLineEdit("Potential Kinetic-Energy Pressure Temperature Density")
        self.ed_terms.setPlaceholderText("空格分隔的能量项名称")
        ed_grid.addWidget(self.ed_terms, 0, 1, 1, 3)

        ed_grid.addWidget(QLabel("输出文件:"), 1, 0)
        self.ed_output = QLineEdit("energy.xvg")
        ed_grid.addWidget(self.ed_output, 1, 1)

        ed_grid.addWidget(QLabel("分析范围:"), 1, 2)
        self.ed_range = QLineEdit("")
        self.ed_range.setPlaceholderText("如 -b 60000 -e 70000 (可选)")
        ed_grid.addWidget(self.ed_range, 1, 3)

        energy_decomp_layout.addLayout(ed_grid)

        self.ed_run_btn = QPushButton("提取能量数据")
        self.ed_run_btn.setProperty("role", "browseBtn")
        self.ed_run_btn.clicked.connect(self.run_energy_decomposition)
        energy_decomp_layout.addWidget(self.ed_run_btn)

        vbox.addWidget(energy_decomp_group)

        # 10. 批量处理系统
        batch_group = QGroupBox("📦 批量处理系统")
        batch_group.setProperty("role", "phaseGroup")
        batch_layout = QVBoxLayout(batch_group)
        batch_layout.setSpacing(8)

        batch_desc = QLabel("同时处理多个模拟体系的数据，自动执行全套分析流程")
        batch_desc.setWordWrap(True)
        batch_desc.setProperty("role", "desc")
        batch_layout.addWidget(batch_desc)

        batch_grid = QGridLayout()
        batch_grid.setSpacing(6)

        batch_grid.addWidget(QLabel("体系列表:"), 0, 0)
        self.batch_table = QTableWidget()
        self.batch_table.setColumnCount(3)
        self.batch_table.setHorizontalHeaderLabels(["工作目录", "TPR文件", "轨迹文件"])
        self.batch_table.horizontalHeader().setStretchLastSection(True)
        self.batch_table.setMinimumHeight(100)
        self.batch_table.setMaximumHeight(120)
        batch_grid.addWidget(self.batch_table, 0, 1, 1, 3)

        batch_btn_layout = QHBoxLayout()
        self.batch_add_btn = QPushButton("+ 添加体系")
        self.batch_del_btn = QPushButton("- 删除")
        self.batch_clear_btn = QPushButton("清空")
        self.batch_load_dir_btn = QPushButton("从目录加载")
        batch_btn_layout.addWidget(self.batch_add_btn)
        batch_btn_layout.addWidget(self.batch_del_btn)
        batch_btn_layout.addWidget(self.batch_clear_btn)
        batch_btn_layout.addWidget(self.batch_load_dir_btn)
        batch_btn_layout.addStretch()
        batch_grid.addLayout(batch_btn_layout, 1, 1, 1, 3)

        batch_grid.addWidget(QLabel("分析流程:"), 2, 0)
        self.batch_flow = QComboBox()
        self.batch_flow.addItems([
            "标准流程 (RMSD + RMSF + g(r) + MSD)",
            "结构稳定性 (RMSD + RMSF + Rg)",
            "相互作用 (g(r) + 氢键 + 最近邻)",
            "扩散动力学 (MSD + 密度)",
            "全套分析 (全部)"
        ])
        batch_grid.addWidget(self.batch_flow, 2, 1, 1, 2)

        self.batch_run_btn = QPushButton("开始批量处理")
        self.batch_run_btn.setProperty("role", "browseBtn")
        batch_grid.addWidget(self.batch_run_btn, 2, 3)

        batch_layout.addLayout(batch_grid)

        self.batch_add_btn.clicked.connect(self.add_batch_system)
        self.batch_del_btn.clicked.connect(self.remove_batch_system)
        self.batch_clear_btn.clicked.connect(lambda: self.batch_table.setRowCount(0))
        self.batch_load_dir_btn.clicked.connect(self.load_batch_from_directory)
        self.batch_run_btn.clicked.connect(self.run_batch_processing)

        vbox.addWidget(batch_group)
        vbox.addStretch()

    def run_file_check(self):
        """校验轨迹文件完整性"""
        wd = self._get_work_dir()
        if not wd:
            self.log_requested.emit("错误: 工作目录未设置", "error")
            return
        xtc = self.ana_input_xtc.text().strip() or "md.xtc"
        tpr = self.ana_input_tpr.text().strip() or "md.tpr"

        if not os.path.exists(os.path.join(wd, xtc)):
            QMessageBox.warning(self, "警告", f"轨迹文件不存在: {xtc}")
            return

        cmd = [self._get_gmx_path(), "check", "-f", xtc, "-s", tpr]
        self.run_requested.emit([cmd], wd, "轨迹文件校验", None)

    def check_file_status(self):
        """检查分析所需的核心文件是否存在"""
        wd = self._get_work_dir()
        if not wd:
            self.log_requested.emit("错误: 工作目录未设置", "error")
            return

        required_files = {
            "TPR文件": self.ana_input_tpr.text().strip() or "md.tpr",
            "轨迹文件": self.ana_input_xtc.text().strip() or "md.xtc",
            "索引文件": self.ana_index.text().strip() or "index.ndx",
            "参考结构": self.ana_input_gro.text().strip() or "ref.gro",
        }

        status_msg = ["=== 文件状态检查 ===", ""]
        all_ok = True
        for name, fname in required_files.items():
            path = os.path.join(wd, fname)
            exists = os.path.exists(path)
            size = os.path.getsize(path) if exists else 0
            status = "✅ 存在" if exists else "❌ 缺失"
            size_str = f" ({size/1024/1024:.1f} MB)" if exists else ""
            status_msg.append(f"{name}: {fname} {status}{size_str}")
            if not exists and name in ["TPR文件", "轨迹文件"]:
                all_ok = False

        status_msg.append("")
        status_msg.append("✅ 核心文件齐全，可以进行分析" if all_ok else "⚠️ 部分核心文件缺失，请检查")
        self.log_requested.emit("\n".join(status_msg), "info" if all_ok else "warning")

    def run_analysis(self, key: str, custom_wd: Optional[str] = None):
        wd = custom_wd or self._get_work_dir()
        if not wd:
            self.log_requested.emit("错误: 工作目录未设置", "error")
            return

        gmx = self._get_gmx_path()
        files = {
            "wd": wd,
            "tpr": self.ana_input_tpr.text().strip() or "md.tpr",
            "xtc": self.ana_input_xtc.text().strip() or "md.xtc",
            "gro": self.ana_input_gro.text().strip() or "md.gro",
            "edr": self.ana_input_edr.text().strip() or "md.edr",
            "ndx": self.ana_index.text().strip(),
        }
        if key not in self.analysis_widgets:
            self.log_requested.emit(f"未知分析类型: {key}", "error")
            return

        w = self.analysis_widgets[key]
        opts = {
            "b": self.ana_b.value(),
            "e": self.ana_e.value(),
            "dt": self.ana_dt.value(),
            "sel": w["sel"].text().strip(),
            "ref": w["ref"].text().strip(),
            "out": w["out"].text().strip(),
        }

        result = build_analysis_command(key, gmx, files, opts)
        if result is None:
            self.log_requested.emit(f"未知分析类型: {key}", "error")
            return
        cmd, step_name, stdin_in = result
        self.run_requested.emit([cmd], wd, step_name, stdin_in)

    def add_batch_system(self):
        wd = self._get_work_dir()
        if not wd:
            return
        row = self.batch_table.rowCount()
        self.batch_table.insertRow(row)
        self.batch_table.setItem(row, 0, QTableWidgetItem(wd))
        self.batch_table.setItem(row, 1, QTableWidgetItem(self.ana_input_tpr.text().strip() or "md.tpr"))
        self.batch_table.setItem(row, 2, QTableWidgetItem(self.ana_input_xtc.text().strip() or "md.xtc"))

    def remove_batch_system(self):
        row = self.batch_table.currentRow()
        if row >= 0:
            self.batch_table.removeRow(row)

    def load_batch_from_directory(self):
        base_dir = QFileDialog.getExistingDirectory(self, "选择包含多个模拟的父目录")
        if not base_dir:
            return

        found = 0
        for subdir in os.listdir(base_dir):
            subpath = os.path.join(base_dir, subdir)
            if not os.path.isdir(subpath):
                continue
            tpr_files = glob.glob(os.path.join(subpath, "*.tpr"))
            xtc_files = glob.glob(os.path.join(subpath, "*.xtc"))
            if tpr_files and xtc_files:
                row = self.batch_table.rowCount()
                self.batch_table.insertRow(row)
                self.batch_table.setItem(row, 0, QTableWidgetItem(subpath))
                self.batch_table.setItem(row, 1, QTableWidgetItem(os.path.basename(tpr_files[0])))
                self.batch_table.setItem(row, 2, QTableWidgetItem(os.path.basename(xtc_files[0])))
                found += 1

        self.log_requested.emit(f"从目录加载了 {found} 个模拟体系", "success")

    def run_batch_processing(self):
        row_count = self.batch_table.rowCount()
        if row_count == 0:
            QMessageBox.warning(self, "警告", "请先添加模拟体系！")
            return

        flow = self.batch_flow.currentText()
        self.log_requested.emit(f"开始批量处理: {flow} | 共 {row_count} 个体系", "info")

        analysis_flows = {
            "标准流程 (RMSD + RMSF + g(r) + MSD)": ["rms", "rmsf", "rdf", "msd"],
            "结构稳定性 (RMSD + RMSF + Rg)": ["rms", "rmsf", "gyrate"],
            "相互作用 (g(r) + 氢键 + 最近邻)": ["rdf", "hbond", "pairdist"],
            "扩散动力学 (MSD + 密度)": ["msd", "density"],
            "全套分析 (全部)": ["rms", "rmsf", "gyrate", "rdf", "hbond", "msd", "density", "sasa"]
        }
        selected_analyses = analysis_flows.get(flow, ["rms", "rmsf"])

        for i in range(row_count):
            wd_item = self.batch_table.item(i, 0)
            tpr_item = self.batch_table.item(i, 1)
            xtc_item = self.batch_table.item(i, 2)
            if not wd_item or not tpr_item or not xtc_item:
                continue

            wd = wd_item.text().strip()
            tpr = tpr_item.text().strip()
            xtc = xtc_item.text().strip()

            self.log_requested.emit(f"[{i+1}/{row_count}] 处理体系: {os.path.basename(wd)}", "info")

            old_tpr = self.ana_input_tpr.text()
            old_xtc = self.ana_input_xtc.text()

            self.ana_input_tpr.setText(tpr)
            self.ana_input_xtc.setText(xtc)

            for analysis in selected_analyses:
                self.log_requested.emit(f"  → {analysis}", "info")
                self.run_analysis(analysis, custom_wd=wd)

            self.ana_input_tpr.setText(old_tpr)
            self.ana_input_xtc.setText(old_xtc)

        self.log_requested.emit("批量处理完成！", "success")

    def run_energy_decomposition(self):
        wd = self._get_work_dir()
        if not wd:
            self.log_requested.emit("错误: 工作目录未设置", "error")
            return

        gmx = self._get_gmx_path()
        edr = self.ana_input_edr.text().strip() or "md.edr"
        terms = self.ed_terms.text().strip()
        output = self.ed_output.text().strip() or "energy.xvg"
        extra_range = self.ed_range.text().strip()

        if not os.path.exists(os.path.join(wd, edr)):
            QMessageBox.warning(self, "警告", f"能量文件不存在: {edr}")
            return

        cmd = [gmx, "energy", "-f", edr, "-o", output]
        if terms:
            term_list = [t.strip() for t in terms.split() if t.strip()]
            term_str = " ".join(term_list)
            cmd_str = f"echo '{term_str} 0' | {' '.join(cmd)}"
            if extra_range:
                cmd_str += " " + extra_range
            self.log_requested.emit(f"提取能量项: {term_str}", "info")
            try:
                result = subprocess.run(
                    cmd_str, shell=True, cwd=wd,
                    capture_output=True, text=True, timeout=300
                )
                if result.returncode == 0:
                    self.log_requested.emit(f"能量分析完成: {output}", "success")
                else:
                    err = result.stderr[:500] if result.stderr else "未知错误"
                    self.log_requested.emit(f"能量分析失败: {err}", "error")
            except Exception as e:
                self.log_requested.emit(f"能量分析异常: {str(e)}", "error")

    def remove_ndx_row(self):
        row = self.ndx_gen_table.currentRow()
        if row >= 0:
            self.ndx_gen_table.removeRow(row)

    def load_fragment_definition(self):
        wd = self._get_work_dir()
        if not wd:
            return
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择片段定义文件", wd,
            "文本文件 (*.txt *.dat);;所有文件 (*.*)"
        )
        if not file_path:
            return
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f if line.strip()]

            self.ndx_gen_table.setRowCount(0)
            i = 0
            while i < len(lines):
                name = lines[i]
                i += 1
                if i < len(lines):
                    ranges = lines[i]
                    row = self.ndx_gen_table.rowCount()
                    self.ndx_gen_table.insertRow(row)
                    self.ndx_gen_table.setItem(row, 0, QTableWidgetItem(name))
                    self.ndx_gen_table.setItem(row, 1, QTableWidgetItem(ranges))
                    i += 1

            self.log_requested.emit(f"已从 {os.path.basename(file_path)} 加载片段定义", "success")
        except Exception as e:
            self.log_requested.emit(f"加载片段定义失败: {str(e)}", "error")

    def _expand_ranges(self, rangestr: str) -> list:
        atoms = []
        for part in rangestr.split(','):
            part = part.strip()
            if not part:
                continue
            if '-' in part:
                a, b = map(int, part.split('-'))
                atoms.extend(range(a, b + 1))
            else:
                atoms.append(int(part))
        return atoms

    def generate_fragment_ndx(self):
        wd = self._get_work_dir()
        if not wd:
            self.log_requested.emit("错误: 工作目录未设置", "error")
            return

        nmol = self.ndx_gen_nmol.value()
        natom_per_mol = self.ndx_gen_natom.value()
        offset = self.ndx_gen_offset.value()
        output_file = self.ndx_gen_output.text().strip() or "fragment.ndx"

        groups = {}
        row_count = self.ndx_gen_table.rowCount()
        if row_count == 0:
            QMessageBox.warning(self, "警告", "请至少定义一个片段！")
            return

        for row in range(row_count):
            name_item = self.ndx_gen_table.item(row, 0)
            range_item = self.ndx_gen_table.item(row, 1)
            if not name_item or not range_item:
                continue
            name = name_item.text().strip()
            rangestr = range_item.text().strip()
            if not name or not rangestr:
                continue

            try:
                base_atoms = self._expand_ranges(rangestr)
            except Exception as e:
                self.log_requested.emit(f"片段 '{name}' 的原子范围解析失败: {str(e)}", "error")
                return

            all_atoms = []
            for mol in range(nmol):
                shift = offset + mol * natom_per_mol
                all_atoms.extend([x + shift for x in base_atoms])
            groups[name] = all_atoms

        output_path = os.path.join(wd, output_file)
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                for name, atoms in groups.items():
                    f.write(f"[ {name} ]\n")
                    for i in range(0, len(atoms), 15):
                        line = atoms[i:i+15]
                        f.write(" ".join(map(str, line)) + "\n")
                    f.write("\n")

            total_atoms = sum(len(atoms) for atoms in groups.values())
            self.log_requested.emit(
                f"片段索引文件生成成功: {output_file} | "
                f"共 {len(groups)} 个组, {total_atoms} 个原子", "success"
            )
            self.rdf_frag_ndx_input.setText(output_file)
        except Exception as e:
            self.log_requested.emit(f"生成索引文件失败: {str(e)}", "error")

    def run_fragment_rdf_batch(self):
        wd = self._get_work_dir()
        if not wd:
            self.log_requested.emit("错误: 工作目录未设置", "error")
            return

        gmx = self._get_gmx_path()
        xtc = self.ana_input_xtc.text().strip() or "md.xtc"
        tpr = self.ana_input_tpr.text().strip() or "md.tpr"
        ndx = self.rdf_frag_ndx_input.text().strip() or "fragment.ndx"

        ref_input = self.rdf_frag_ref.text().strip()
        sel_input = self.rdf_frag_sel.text().strip()

        if not ref_input or not sel_input:
            QMessageBox.warning(self, "警告", "请填写参考组和选择组！")
            return

        ref_groups = [g.strip() for g in ref_input.split(',') if g.strip()]
        sel_groups = [g.strip() for g in sel_input.split(',') if g.strip()]

        seltype_text = self.rdf_frag_seltype.currentText()
        if "mol_com_nointra" in seltype_text:
            seltype = "mol_com"
            nointra_flag = True
        else:
            seltype = seltype_text.split()[0]
            nointra_flag = False

        bin_val = self.rdf_frag_bin.value()
        b = self.rdf_frag_b.value()
        e = self.rdf_frag_e.value()
        outdir = self.rdf_frag_outdir.text().strip() or "fragment_RDF"

        outdir_path = os.path.join(wd, outdir)
        os.makedirs(outdir_path, exist_ok=True)

        commands = []
        for ref_group in ref_groups:
            for sel_group in sel_groups:
                outfile = os.path.join(outdir, f"rdf_{ref_group}_{sel_group}.xvg")
                if seltype == "mol_com":
                    ref_arg = f"mol_com of group {ref_group}"
                    sel_arg = f"mol_com of group {sel_group}"
                else:
                    ref_arg = f"group {ref_group}"
                    sel_arg = f"group {sel_group}"

                cmd = [gmx, "rdf", "-f", xtc, "-s", tpr, "-n", ndx,
                       "-ref", ref_arg, "-sel", sel_arg,
                       "-bin", str(bin_val), "-o", outfile]
                if b > 0:
                    cmd += ["-b", str(b)]
                if e > 0:
                    cmd += ["-e", str(e)]
                if nointra_flag:
                    cmd += ["-nointra"]

                step_name = f"片段RDF: {ref_group} <-> {sel_group}"
                commands.append((cmd, step_name))

        total = len(commands)
        self.log_requested.emit(f"开始批量计算片段RDF: 共 {total} 组 ({len(ref_groups)} ref x {len(sel_groups)} sel)", "info")

        for i, (cmd, step_name) in enumerate(commands, 1):
            self.log_requested.emit(f"[{i}/{total}] {step_name}", "info")
            self.run_requested.emit([cmd], wd, step_name, None)

    def run_pairdist_analysis(self):
        wd = self._get_work_dir()
        if not wd:
            self.log_requested.emit("错误: 工作目录未设置", "error")
            return

        gmx = self._get_gmx_path()
        xtc = self.ana_input_xtc.text().strip() or "md.xtc"
        tpr = self.ana_input_tpr.text().strip() or "md.tpr"
        ndx = self.rdf_frag_ndx_input.text().strip() or "fragment.ndx"

        ref_group = self.pairdist_ref.text().strip()
        sel_group = self.pairdist_sel.text().strip()

        if not ref_group or not sel_group:
            QMessageBox.warning(self, "警告", "请填写参考组和选择组！")
            return

        type_text = self.pairdist_type.currentText()
        pd_type = type_text.split()[0]
        out = self.pairdist_out.text().strip() or "pairdist.xvg"

        b = self.ana_b.value()
        e = self.ana_e.value()

        ref_arg = f"mol_com of group {ref_group}"
        sel_arg = f"mol_com of group {sel_group}"

        cmd = [gmx, "pairdist", "-f", xtc, "-s", tpr, "-n", ndx,
               "-ref", ref_arg, "-sel", sel_arg,
               "-type", pd_type, "-o", out]
        if b > 0:
            cmd += ["-b", str(b)]
        if e > 0:
            cmd += ["-e", str(e)]

        step_name = f"最近邻距离: {ref_group} <-> {sel_group} ({pd_type})"
        self.run_requested.emit([cmd], wd, step_name, None)

    def generate_plot(self):
        wd = self._get_work_dir()
        if not wd:
            self.log_requested.emit("错误: 工作目录未设置", "error")
            return

        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
        except ImportError:
            QMessageBox.warning(self, "警告", "未安装matplotlib！请运行: pip install matplotlib")
            return

        xvg_file = self.plot_input.text().strip()
        if not xvg_file or not os.path.exists(os.path.join(wd, xvg_file)):
            xvg_files = glob.glob(os.path.join(wd, "*.xvg"))
            if not xvg_files:
                QMessageBox.warning(self, "警告", "未找到xvg文件！")
                return
            xvg_file = os.path.basename(xvg_files[0])
            self.plot_input.setText(xvg_file)

        plot_type = self.plot_type.currentText()
        xlabel = self.plot_xlabel.text().strip()
        ylabel = self.plot_ylabel.text().strip()
        title = self.plot_title.text().strip()
        output = self.plot_output.text().strip() or "plot.png"
        dpi = self.plot_dpi.value()

        try:
            data = []
            legends = []
            with open(os.path.join(wd, xvg_file), 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('@') and 'legend' in line:
                        legend = line.split('legend')[-1].strip().strip('"')
                        legends.append(legend)
                    elif line and not line.startswith(('#', '@')):
                        parts = line.split()
                        if len(parts) >= 2:
                            try:
                                data.append([float(p) for p in parts])
                            except Exception:
                                pass

            if not data:
                QMessageBox.warning(self, "警告", "xvg文件中没有有效数据！")
                return

            data = list(zip(*data))
            x = data[0]

            fig, ax = plt.subplots(figsize=(8, 5), dpi=dpi)

            if "多曲线对比" in plot_type:
                for i, y in enumerate(data[1:], 1):
                    label = legends[i-1] if i-1 < len(legends) else f"Series {i}"
                    ax.plot(x, y, label=label, linewidth=1.5)
                ax.legend()
            elif "柱状图" in plot_type:
                ax.bar(x, data[1], color='#C2185B', alpha=0.8)
            elif "散点图" in plot_type:
                ax.scatter(x, data[1], color='#C2185B', alpha=0.6, s=20)
            else:
                ax.plot(x, data[1], color='#C2185B', linewidth=1.5)

            ax.set_xlabel(xlabel, fontsize=12)
            ax.set_ylabel(ylabel, fontsize=12)
            if title:
                ax.set_title(title, fontsize=14, fontweight='bold')
            ax.grid(True, linestyle='--', alpha=0.5)

            plt.tight_layout()
            output_path = os.path.join(wd, output)
            plt.savefig(output_path, dpi=dpi, bbox_inches='tight')
            plt.close()

            self.log_requested.emit(f"图表生成成功: {output} ({dpi}dpi)", "success")
        except Exception as e:
            self.log_requested.emit(f"绘图失败: {str(e)}", "error")

    def set_running_state(self, running: bool):
        for w in self.analysis_widgets.values():
            w["run_btn"].setEnabled(not running)
        self.file_check_btn.setEnabled(not running)
        self.file_status_btn.setEnabled(not running)
        self.plot_run_btn.setEnabled(not running)
        self.ed_run_btn.setEnabled(not running)
        self.batch_run_btn.setEnabled(not running)
        self.ndx_gen_btn.setEnabled(not running)
        self.rdf_frag_run_btn.setEnabled(not running)
        self.pairdist_run_btn.setEnabled(not running)

    def get_config(self) -> dict:
        cfg = {
            "ana_input_xtc": self.ana_input_xtc.text().strip(),
            "ana_input_tpr": self.ana_input_tpr.text().strip(),
            "ana_input_gro": self.ana_input_gro.text().strip(),
            "ana_input_edr": self.ana_input_edr.text().strip(),
            "ana_index": self.ana_index.text().strip(),
            "ana_b": self.ana_b.value(),
            "ana_e": self.ana_e.value(),
            "ana_dt": self.ana_dt.value(),
            "plot_type": self.plot_type.currentText(),
            "plot_xlabel": self.plot_xlabel.text().strip(),
            "plot_ylabel": self.plot_ylabel.text().strip(),
            "plot_title": self.plot_title.text().strip(),
            "plot_output": self.plot_output.text().strip(),
            "plot_dpi": self.plot_dpi.value(),
            "ed_terms": self.ed_terms.text().strip(),
            "ed_output": self.ed_output.text().strip(),
            "ed_range": self.ed_range.text().strip(),
            "tools": {}
        }
        for k, w in self.analysis_widgets.items():
            cfg["tools"][k] = {
                "out": w["out"].text().strip(),
                "sel": w["sel"].text().strip(),
                "ref": w["ref"].text().strip()
            }
        return cfg

    def set_config(self, data: dict):
        if not isinstance(data, dict):
            return
        if "ana_input_xtc" in data:
            self.ana_input_xtc.setText(str(data["ana_input_xtc"]))
        if "ana_input_tpr" in data:
            self.ana_input_tpr.setText(str(data["ana_input_tpr"]))
        if "ana_input_gro" in data:
            self.ana_input_gro.setText(str(data["ana_input_gro"]))
        if "ana_input_edr" in data:
            self.ana_input_edr.setText(str(data["ana_input_edr"]))
        if "ana_index" in data:
            self.ana_index.setText(str(data["ana_index"]))
        if "ana_b" in data:
            self.ana_b.setValue(float(data["ana_b"]))
        if "ana_e" in data:
            self.ana_e.setValue(float(data["ana_e"]))
        if "ana_dt" in data:
            self.ana_dt.setValue(float(data["ana_dt"]))
        if "plot_type" in data:
            idx = self.plot_type.findText(str(data["plot_type"]))
            if idx >= 0:
                self.plot_type.setCurrentIndex(idx)
        if "plot_xlabel" in data:
            self.plot_xlabel.setText(str(data["plot_xlabel"]))
        if "plot_ylabel" in data:
            self.plot_ylabel.setText(str(data["plot_ylabel"]))
        if "plot_title" in data:
            self.plot_title.setText(str(data["plot_title"]))
        if "plot_output" in data:
            self.plot_output.setText(str(data["plot_output"]))
        if "plot_dpi" in data:
            self.plot_dpi.setValue(int(data["plot_dpi"]))
        if "ed_terms" in data:
            self.ed_terms.setText(str(data["ed_terms"]))
        if "ed_output" in data:
            self.ed_output.setText(str(data["ed_output"]))
        if "ed_range" in data:
            self.ed_range.setText(str(data["ed_range"]))
        if "tools" in data and isinstance(data["tools"], dict):
            for k, tool_data in data["tools"].items():
                if k in self.analysis_widgets and isinstance(tool_data, dict):
                    if "out" in tool_data:
                        self.analysis_widgets[k]["out"].setText(str(tool_data["out"]))
                    if "sel" in tool_data:
                        self.analysis_widgets[k]["sel"].setText(str(tool_data["sel"]))
                    if "ref" in tool_data:
                        self.analysis_widgets[k]["ref"].setText(str(tool_data["ref"]))
