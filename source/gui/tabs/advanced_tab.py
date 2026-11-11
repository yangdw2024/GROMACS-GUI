# -*- coding: utf-8 -*-
"""
Part 3: 高级模拟独立页面组件
从 main_window.py 拆分抽离。
负责：
1. 伞形采样 (Umbrella Sampling)：参数配置与批次生成 MDP
2. WHAM 自由能计算：配置与命令构建执行
3. 元动力学 (Metadynamics - PLUMED)：PLUMED dat 输入文件生成与 mdrun 执行
4. 自适应偏置力 (ABF - PLUMED)：PLUMED dat 文件生成
5. 命令与任务通过统一信号 run_requested 上抛至主窗口统一调度器
"""

import os
from typing import Optional, Callable, List

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QSpinBox, QDoubleSpinBox, QGroupBox, QScrollArea
)

from simulation.mdp_builder import (
    build_umbrella_mdp_files,
    build_plumed_metad,
    build_plumed_abf
)
from gui.i18n import tr


class AdvancedTab(QWidget):
    """Part 3: 高级模拟方法 (伞形采样 / WHAM / 元动力学 / ABF) 独立页面组件

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
        get_mdrun_extra: Optional[Callable[[], List[str]]] = None,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self._get_work_dir = get_work_dir or (lambda: os.getcwd())
        self._get_gmx_path = get_gmx_path or (lambda: "gmx")
        self._get_mdrun_extra = get_mdrun_extra or (lambda: [])

        self._init_ui()

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

        self.info_label = QLabel(tr("adv_info"))
        self.info_label.setWordWrap(True)
        self.info_label.setProperty("role", "desc")
        vbox.addWidget(self.info_label)

        # 1. 伞形采样
        self.umbrella_group = QGroupBox(tr("adv_umb_group"))
        self.umbrella_group.setProperty("role", "phaseGroup")
        ugrid = QGridLayout(self.umbrella_group)

        self.umb_tpr = QLineEdit("md.tpr")
        self.umb_xtc = QLineEdit("md.xtc")
        self.umb_pull_coord = QComboBox()
        self.umb_pull_coord.addItems(["distance", "angle", "dihedral"])
        self.umb_pull_group1 = QLineEdit("Protein")
        self.umb_pull_group2 = QLineEdit("Ligand")
        self.umb_pull_force = QDoubleSpinBox()
        self.umb_pull_force.setRange(100, 10000)
        self.umb_pull_force.setValue(1000)
        self.umb_pull_force.setSuffix(" kJ/mol/nm^2")
        self.umb_pull_start = QDoubleSpinBox()
        self.umb_pull_start.setRange(0, 10)
        self.umb_pull_start.setValue(0)
        self.umb_pull_start.setDecimals(2)
        self.umb_pull_end = QDoubleSpinBox()
        self.umb_pull_end.setRange(0, 10)
        self.umb_pull_end.setValue(5)
        self.umb_pull_end.setDecimals(2)
        self.umb_pull_nwindows = QSpinBox()
        self.umb_pull_nwindows.setRange(2, 50)
        self.umb_pull_nwindows.setValue(10)

        ugrid.addWidget(QLabel("输入TPR:"), 0, 0)
        ugrid.addWidget(self.umb_tpr, 0, 1)
        ugrid.addWidget(QLabel("轨迹文件:"), 0, 2)
        ugrid.addWidget(self.umb_xtc, 0, 3)

        ugrid.addWidget(QLabel("拉动类型:"), 1, 0)
        ugrid.addWidget(self.umb_pull_coord, 1, 1)
        ugrid.addWidget(QLabel("组1:"), 1, 2)
        ugrid.addWidget(self.umb_pull_group1, 1, 3)

        ugrid.addWidget(QLabel("组2:"), 2, 0)
        ugrid.addWidget(self.umb_pull_group2, 2, 1)
        ugrid.addWidget(QLabel("力常数:"), 2, 2)
        ugrid.addWidget(self.umb_pull_force, 2, 3)

        ugrid.addWidget(QLabel("起始位置:"), 3, 0)
        ugrid.addWidget(self.umb_pull_start, 3, 1)
        ugrid.addWidget(QLabel("结束位置:"), 3, 2)
        ugrid.addWidget(self.umb_pull_end, 3, 3)

        ugrid.addWidget(QLabel("窗口数:"), 4, 0)
        ugrid.addWidget(self.umb_pull_nwindows, 4, 1)

        self.umb_run_btn = QPushButton(tr("adv_umb_btn"))
        self.umb_run_btn.setProperty("role", "accentBtn")
        self.umb_run_btn.clicked.connect(self.generate_umbrella_mdp)
        ugrid.addWidget(self.umb_run_btn, 5, 0, 1, 4)

        vbox.addWidget(self.umbrella_group)

        # 2. WHAM 分析
        self.wham_group = QGroupBox(tr("adv_wham_group"))
        self.wham_group.setProperty("role", "phaseGroup")
        wgrid = QGridLayout(self.wham_group)

        self.wham_files = QLineEdit("pull*.xvg")
        self.wham_temp = QDoubleSpinBox()
        self.wham_temp.setRange(1.0, 1000.0)
        self.wham_temp.setValue(300)
        self.wham_temp.setSuffix(" K")
        self.wham_out = QLineEdit("profile.xvg")

        wgrid.addWidget(QLabel("pull 文件模式:"), 0, 0)
        wgrid.addWidget(self.wham_files, 0, 1)
        wgrid.addWidget(QLabel("温度:"), 0, 2)
        wgrid.addWidget(self.wham_temp, 0, 3)

        wgrid.addWidget(QLabel("输出文件:"), 1, 0)
        wgrid.addWidget(self.wham_out, 1, 1)

        self.wham_run_btn = QPushButton(tr("adv_wham_btn"))
        self.wham_run_btn.setProperty("role", "actionBtn")
        self.wham_run_btn.clicked.connect(self.run_wham)
        wgrid.addWidget(self.wham_run_btn, 2, 0, 1, 4)

        vbox.addWidget(self.wham_group)

        # 3. 元动力学
        self.meta_group = QGroupBox(tr("adv_meta_group"))
        self.meta_group.setProperty("role", "phaseGroup")
        mgrid = QGridLayout(self.meta_group)

        self.meta_tpr = QLineEdit("md.tpr")
        self.meta_plumed = QLineEdit("plumed.dat")
        self.meta_biasfactor = QDoubleSpinBox()
        self.meta_biasfactor.setRange(1, 100)
        self.meta_biasfactor.setValue(10)
        self.meta_height = QDoubleSpinBox()
        self.meta_height.setRange(0.1, 10)
        self.meta_height.setValue(0.3)
        self.meta_height.setSuffix(" kJ/mol")
        self.meta_sigma = QDoubleSpinBox()
        self.meta_sigma.setRange(0.01, 1)
        self.meta_sigma.setValue(0.1)

        mgrid.addWidget(QLabel("输入TPR:"), 0, 0)
        mgrid.addWidget(self.meta_tpr, 0, 1)
        mgrid.addWidget(QLabel("PLUMED文件:"), 0, 2)
        mgrid.addWidget(self.meta_plumed, 0, 3)

        mgrid.addWidget(QLabel("偏置因子:"), 1, 0)
        mgrid.addWidget(self.meta_biasfactor, 1, 1)
        mgrid.addWidget(QLabel("高斯高度:"), 1, 2)
        mgrid.addWidget(self.meta_height, 1, 3)

        mgrid.addWidget(QLabel("高斯宽度:"), 2, 0)
        mgrid.addWidget(self.meta_sigma, 2, 1)

        self.meta_gen_btn = QPushButton(tr("adv_meta_gen_btn"))
        self.meta_gen_btn.setProperty("role", "accentBtn")
        self.meta_gen_btn.clicked.connect(self.generate_plumed_meta)
        mgrid.addWidget(self.meta_gen_btn, 3, 0, 1, 2)

        self.meta_run_btn = QPushButton(tr("adv_meta_run_btn"))
        self.meta_run_btn.setProperty("role", "primaryRun")
        self.meta_run_btn.clicked.connect(self.run_metadynamics)
        mgrid.addWidget(self.meta_run_btn, 3, 2, 1, 2)

        vbox.addWidget(self.meta_group)

        # 4. ABF 方法
        self.abf_group = QGroupBox(tr("adv_abf_group"))
        self.abf_group.setProperty("role", "phaseGroup")
        agrid = QGridLayout(self.abf_group)

        self.abf_tpr = QLineEdit("md.tpr")
        self.abf_plumed = QLineEdit("plumed_abf.dat")
        self.abf_min = QDoubleSpinBox()
        self.abf_min.setValue(0)
        self.abf_max = QDoubleSpinBox()
        self.abf_max.setValue(5)
        self.abf_nbins = QSpinBox()
        self.abf_nbins.setRange(10, 500)
        self.abf_nbins.setValue(100)

        agrid.addWidget(QLabel("输入TPR:"), 0, 0)
        agrid.addWidget(self.abf_tpr, 0, 1)
        agrid.addWidget(QLabel("PLUMED文件:"), 0, 2)
        agrid.addWidget(self.abf_plumed, 0, 3)

        agrid.addWidget(QLabel("最小值:"), 1, 0)
        agrid.addWidget(self.abf_min, 1, 1)
        agrid.addWidget(QLabel("最大值:"), 1, 2)
        agrid.addWidget(self.abf_max, 1, 3)

        agrid.addWidget(QLabel("分箱数:"), 2, 0)
        agrid.addWidget(self.abf_nbins, 2, 1)

        self.abf_gen_btn = QPushButton(tr("adv_abf_btn"))
        self.abf_gen_btn.setProperty("role", "accentBtn")
        self.abf_gen_btn.clicked.connect(self.generate_plumed_abf)
        agrid.addWidget(self.abf_gen_btn, 3, 0, 1, 4)

        vbox.addWidget(self.abf_group)
        vbox.addStretch()

    def generate_umbrella_mdp(self):
        wd = self._get_work_dir()
        if not wd:
            self.log_requested.emit("错误: 工作目录未设置", "error")
            return

        coord = self.umb_pull_coord.currentText()
        group1 = self.umb_pull_group1.text().strip()
        group2 = self.umb_pull_group2.text().strip()
        force = self.umb_pull_force.value()
        start = self.umb_pull_start.value()
        end = self.umb_pull_end.value()
        nwindows = self.umb_pull_nwindows.value()

        for fname, content in build_umbrella_mdp_files(
            coord, group1, group2, force, start, end, nwindows
        ):
            fpath = os.path.join(wd, fname)
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(content)

        self.log_requested.emit(f"已生成 {nwindows} 个伞形采样 MDP 文件", "success")

    def run_wham(self):
        wd = self._get_work_dir()
        if not wd:
            self.log_requested.emit("错误: 工作目录未设置", "error")
            return

        gmx = self._get_gmx_path()
        files = self.wham_files.text().strip()
        temp = self.wham_temp.value()
        out = self.wham_out.text().strip() or "profile.xvg"

        cmd = [gmx, "wham", "-it", files, "-o", out, "-temp", str(temp), "-b", "0", "-e", "0"]
        self.run_requested.emit([cmd], wd, "WHAM 自由能计算")

    def generate_plumed_meta(self):
        wd = self._get_work_dir()
        if not wd:
            self.log_requested.emit("错误: 工作目录未设置", "error")
            return

        biasfactor = self.meta_biasfactor.value()
        height = self.meta_height.value()
        sigma = self.meta_sigma.value()
        fname = self.meta_plumed.text().strip() or "plumed.dat"

        content = build_plumed_metad(biasfactor, height, sigma)
        fpath = os.path.join(wd, fname)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(content)
        self.log_requested.emit(f"已生成 PLUMED 输入文件: {fpath}", "success")

    def run_metadynamics(self):
        wd = self._get_work_dir()
        if not wd:
            self.log_requested.emit("错误: 工作目录未设置", "error")
            return

        gmx = self._get_gmx_path()
        extra = self._get_mdrun_extra()
        cmd = [gmx, "mdrun", "-deffnm", "md_meta", "-plumed", "plumed.dat"] + extra
        self.run_requested.emit([cmd], wd, "元动力学模拟")

    def generate_plumed_abf(self):
        wd = self._get_work_dir()
        if not wd:
            self.log_requested.emit("错误: 工作目录未设置", "error")
            return

        min_val = self.abf_min.value()
        max_val = self.abf_max.value()
        nbins = self.abf_nbins.value()
        fname = self.abf_plumed.text().strip() or "plumed_abf.dat"

        content = build_plumed_abf(min_val, max_val, nbins)
        fpath = os.path.join(wd, fname)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(content)
        self.log_requested.emit(f"已生成 ABF PLUMED 文件: {fpath}", "success")

    def set_running_state(self, running: bool):
        self.umb_run_btn.setEnabled(not running)
        self.wham_run_btn.setEnabled(not running)
        self.meta_run_btn.setEnabled(not running)
        self.meta_gen_btn.setEnabled(not running)
        self.abf_gen_btn.setEnabled(not running)

    def get_config(self) -> dict:
        return {
            "umb_tpr": self.umb_tpr.text().strip(),
            "umb_xtc": self.umb_xtc.text().strip(),
            "umb_pull_coord": self.umb_pull_coord.currentText(),
            "umb_pull_group1": self.umb_pull_group1.text().strip(),
            "umb_pull_group2": self.umb_pull_group2.text().strip(),
            "umb_pull_force": self.umb_pull_force.value(),
            "umb_pull_start": self.umb_pull_start.value(),
            "umb_pull_end": self.umb_pull_end.value(),
            "umb_pull_nwindows": self.umb_pull_nwindows.value(),
            "wham_files": self.wham_files.text().strip(),
            "wham_temp": self.wham_temp.value(),
            "wham_out": self.wham_out.text().strip(),
            "meta_tpr": self.meta_tpr.text().strip(),
            "meta_plumed": self.meta_plumed.text().strip(),
            "meta_biasfactor": self.meta_biasfactor.value(),
            "meta_height": self.meta_height.value(),
            "meta_sigma": self.meta_sigma.value(),
            "abf_tpr": self.abf_tpr.text().strip(),
            "abf_plumed": self.abf_plumed.text().strip(),
            "abf_min": self.abf_min.value(),
            "abf_max": self.abf_max.value(),
            "abf_nbins": self.abf_nbins.value(),
        }

    def set_config(self, data: dict):
        if not isinstance(data, dict):
            return
        if "umb_tpr" in data:
            self.umb_tpr.setText(str(data["umb_tpr"]))
        if "umb_xtc" in data:
            self.umb_xtc.setText(str(data["umb_xtc"]))
        if "umb_pull_coord" in data:
            idx = self.umb_pull_coord.findText(str(data["umb_pull_coord"]))
            if idx >= 0:
                self.umb_pull_coord.setCurrentIndex(idx)
        if "umb_pull_group1" in data:
            self.umb_pull_group1.setText(str(data["umb_pull_group1"]))
        if "umb_pull_group2" in data:
            self.umb_pull_group2.setText(str(data["umb_pull_group2"]))
        if "umb_pull_force" in data:
            self.umb_pull_force.setValue(float(data["umb_pull_force"]))
        if "umb_pull_start" in data:
            self.umb_pull_start.setValue(float(data["umb_pull_start"]))
        if "umb_pull_end" in data:
            self.umb_pull_end.setValue(float(data["umb_pull_end"]))
        if "umb_pull_nwindows" in data:
            self.umb_pull_nwindows.setValue(int(data["umb_pull_nwindows"]))

        if "wham_files" in data:
            self.wham_files.setText(str(data["wham_files"]))
        if "wham_temp" in data:
            self.wham_temp.setValue(float(data["wham_temp"]))
        if "wham_out" in data:
            self.wham_out.setText(str(data["wham_out"]))

        if "meta_tpr" in data:
            self.meta_tpr.setText(str(data["meta_tpr"]))
        if "meta_plumed" in data:
            self.meta_plumed.setText(str(data["meta_plumed"]))
        if "meta_biasfactor" in data:
            self.meta_biasfactor.setValue(float(data["meta_biasfactor"]))
        if "meta_height" in data:
            self.meta_height.setValue(float(data["meta_height"]))
        if "meta_sigma" in data:
            self.meta_sigma.setValue(float(data["meta_sigma"]))

        if "abf_tpr" in data:
            self.abf_tpr.setText(str(data["abf_tpr"]))
        if "abf_plumed" in data:
            self.abf_plumed.setText(str(data["abf_plumed"]))
        if "abf_min" in data:
            self.abf_min.setValue(float(data["abf_min"]))
        if "abf_max" in data:
            self.abf_max.setValue(float(data["abf_max"]))
        if "abf_nbins" in data:
            self.abf_nbins.setValue(int(data["abf_nbins"]))

    def retranslate_ui(self, lang: str):
        self.info_label.setText(tr("adv_info", lang=lang))
        self.umbrella_group.setTitle(tr("adv_umb_group", lang=lang))
        self.wham_group.setTitle(tr("adv_wham_group", lang=lang))
        self.meta_group.setTitle(tr("adv_meta_group", lang=lang))
        self.abf_group.setTitle(tr("adv_abf_group", lang=lang))
        self.umb_run_btn.setText(tr("adv_umb_btn", lang=lang))
        self.wham_run_btn.setText(tr("adv_wham_btn", lang=lang))
        self.meta_gen_btn.setText(tr("adv_meta_gen_btn", lang=lang))
        self.meta_run_btn.setText(tr("adv_meta_run_btn", lang=lang))
        self.abf_gen_btn.setText(tr("adv_abf_btn", lang=lang))
