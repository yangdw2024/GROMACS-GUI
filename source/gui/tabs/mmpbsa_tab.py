# -*- coding: utf-8 -*-
"""
Part 6: MMPBSA 结合自由能计算独立页面组件 (已完整治理 Issue #5)
负责：
1. 输入文件配置 (tpr, xtc, ndx, top) 及实际 NDX 组自动解析与受体/配体索引组选择；
2. 采样参数与时间->帧精确换算 (start_ps, end_ps, interval_ps, traj_dt_ps) 并生成 mmpbsa.in；
3. 并行计算控制 (MPI mpirun -np) 与结果图表参数导出规格 (mmpbsa_plot_spec.json)；
4. 外部 gmx_MMPBSA 环境前置探测与缺失阻断；
5. 非蛋白/有机电子材料体系实验性提示声明。
"""

import json
import os
from typing import Optional, Callable

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QSpinBox, QDoubleSpinBox, QGroupBox, QScrollArea
)

from simulation.analysis import (
    build_mmpbsa_command,
    build_mmpbsa_input_file,
    convert_ps_to_mmpbsa_frames,
    detect_gmx_mmpbsa_runner,
    parse_ndx_groups,
)
from gui.i18n import tr


class MmpbsaTab(QWidget):
    """MMPBSA 结合自由能计算页面组件

    Signals:
        run_requested(cmd, work_dir, step_name): 请求主调度器执行构建好的命令链
        log_requested(message, level): 请求向主日志视口追加日志
    """

    run_requested = pyqtSignal(object, str, str)
    log_requested = pyqtSignal(str, str)

    def __init__(
        self,
        get_work_dir: Optional[Callable[[], str]] = None,
        detect_runner: Optional[Callable[[], tuple]] = None,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self._get_work_dir = get_work_dir or (lambda: os.getcwd())
        self._detect_runner = detect_runner or detect_gmx_mmpbsa_runner
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        vbox = QVBoxLayout(content)
        vbox.setSpacing(14)
        vbox.setContentsMargins(8, 10, 8, 10)

        self.info_label = QLabel(tr("mmpbsa_info"))
        self.info_label.setWordWrap(True)
        self.info_label.setProperty("role", "desc")
        vbox.addWidget(self.info_label)

        self.exp_banner = QLabel(
            "⚠️ 科学适用性提示（实验性支持）：用于有机高分子/小分子给受体体系时，请先核实 "
            "NDX 受体/配体索引组编号、拓扑电荷及隐式溶剂介电常数，勿直接沿用蛋白默认组 (1, 13)。"
        )
        self.exp_banner.setWordWrap(True)
        self.exp_banner.setProperty("role", "warningBanner")
        vbox.addWidget(self.exp_banner)

        # 1. 输入文件与索引组
        self.inp_group = QGroupBox(tr("mmpbsa_inp_group"))
        igrid = QGridLayout(self.inp_group)

        self.mmpbsa_tpr = QLineEdit("md.tpr")
        self.mmpbsa_xtc = QLineEdit("md.xtc")
        self.mmpbsa_index = QLineEdit("index.ndx")
        self.mmpbsa_top = QLineEdit("topol.top")

        self.mmpbsa_rec_group = QLineEdit("1")
        self.mmpbsa_rec_group.setToolTip("受体索引组编号或名称（从 NDX 解析确认）")
        self.mmpbsa_lig_group = QLineEdit("13")
        self.mmpbsa_lig_group.setToolTip("配体索引组编号或名称（从 NDX 解析确认）")
        self.mmpbsa_scan_ndx_btn = QPushButton("扫描 NDX 索引组")
        self.mmpbsa_scan_ndx_btn.setProperty("role", "secondaryTool")
        self.mmpbsa_scan_ndx_btn.clicked.connect(self.scan_ndx_groups)

        igrid.addWidget(QLabel("运行输入:"), 0, 0)
        igrid.addWidget(self.mmpbsa_tpr, 0, 1)
        igrid.addWidget(QLabel("轨迹文件:"), 0, 2)
        igrid.addWidget(self.mmpbsa_xtc, 0, 3)

        igrid.addWidget(QLabel("索引文件:"), 1, 0)
        igrid.addWidget(self.mmpbsa_index, 1, 1)
        igrid.addWidget(QLabel("拓扑文件:"), 1, 2)
        igrid.addWidget(self.mmpbsa_top, 1, 3)

        igrid.addWidget(QLabel("受体组 (-cg 1):"), 2, 0)
        igrid.addWidget(self.mmpbsa_rec_group, 2, 1)
        igrid.addWidget(QLabel("配体组 (-cg 2):"), 2, 2)
        igrid.addWidget(self.mmpbsa_lig_group, 2, 3)
        igrid.addWidget(self.mmpbsa_scan_ndx_btn, 3, 0, 1, 4)

        vbox.addWidget(self.inp_group)

        # 2. 采样与计算参数
        self.sam_group = QGroupBox(tr("mmpbsa_sam_group"))
        sgrid = QGridLayout(self.sam_group)

        self.mmpbsa_start = QDoubleSpinBox()
        self.mmpbsa_start.setRange(0, 1000000)
        self.mmpbsa_start.setValue(0)
        self.mmpbsa_start.setDecimals(1)
        self.mmpbsa_start.setSuffix(" ps")

        self.mmpbsa_end = QDoubleSpinBox()
        self.mmpbsa_end.setRange(0, 1000000)
        self.mmpbsa_end.setValue(0)
        self.mmpbsa_end.setDecimals(1)
        self.mmpbsa_end.setSuffix(" ps (0=到结尾)")

        self.mmpbsa_interval = QDoubleSpinBox()
        self.mmpbsa_interval.setRange(1, 100000)
        self.mmpbsa_interval.setValue(1000)
        self.mmpbsa_interval.setDecimals(0)
        self.mmpbsa_interval.setSuffix(" ps")

        self.mmpbsa_traj_dt = QDoubleSpinBox()
        self.mmpbsa_traj_dt.setDecimals(2)
        self.mmpbsa_traj_dt.setRange(0.01, 100000.0)
        self.mmpbsa_traj_dt.setValue(10.0)
        self.mmpbsa_traj_dt.setSuffix(" ps/帧")
        self.mmpbsa_traj_dt.setToolTip("用于将 ps 采样时间准确换算为 gmx_MMPBSA 的 1-based 帧索引")

        self.mmpbsa_nt = QSpinBox()
        self.mmpbsa_nt.setRange(1, 64)
        self.mmpbsa_nt.setValue(4)

        sgrid.addWidget(QLabel("计算开始时间:"), 0, 0)
        sgrid.addWidget(self.mmpbsa_start, 0, 1)
        sgrid.addWidget(QLabel("计算结束时间:"), 0, 2)
        sgrid.addWidget(self.mmpbsa_end, 0, 3)

        sgrid.addWidget(QLabel("采样时间间隔:"), 1, 0)
        sgrid.addWidget(self.mmpbsa_interval, 1, 1)
        sgrid.addWidget(QLabel("轨迹帧间隔:"), 1, 2)
        sgrid.addWidget(self.mmpbsa_traj_dt, 1, 3)

        sgrid.addWidget(QLabel("并行线程数:"), 2, 0)
        sgrid.addWidget(self.mmpbsa_nt, 2, 1)

        vbox.addWidget(self.sam_group)

        # 3. 结果图片输出设置
        self.img_group = QGroupBox(tr("mmpbsa_img_group"))
        imgrid = QGridLayout(self.img_group)

        self.mmpbsa_fmt = QComboBox()
        self.mmpbsa_fmt.addItems(["png", "pdf", "svg", "jpg", "tiff"])

        self.mmpbsa_width = QDoubleSpinBox()
        self.mmpbsa_width.setRange(1, 50)
        self.mmpbsa_width.setValue(8)
        self.mmpbsa_width.setDecimals(1)
        self.mmpbsa_width.setSuffix(" inch")

        self.mmpbsa_height = QDoubleSpinBox()
        self.mmpbsa_height.setRange(1, 50)
        self.mmpbsa_height.setValue(6)
        self.mmpbsa_height.setDecimals(1)
        self.mmpbsa_height.setSuffix(" inch")

        imgrid.addWidget(QLabel("图片格式:"), 0, 0)
        imgrid.addWidget(self.mmpbsa_fmt, 0, 1)
        imgrid.addWidget(QLabel("图片宽度:"), 0, 2)
        imgrid.addWidget(self.mmpbsa_width, 0, 3)

        imgrid.addWidget(QLabel("图片高度:"), 1, 0)
        imgrid.addWidget(self.mmpbsa_height, 1, 1)

        vbox.addWidget(self.img_group)

        # 4. 运行按钮
        run_layout = QHBoxLayout()
        self.mmpbsa_run_btn = QPushButton(tr("mmpbsa_run_btn"))
        self.mmpbsa_run_btn.setProperty("role", "primaryRun")
        self.mmpbsa_run_btn.setMinimumHeight(34)
        self.mmpbsa_run_btn.clicked.connect(self.run_mmpbsa)
        run_layout.addStretch()
        run_layout.addWidget(self.mmpbsa_run_btn)
        run_layout.addStretch()
        vbox.addLayout(run_layout)

        vbox.addStretch()

    def scan_ndx_groups(self):
        wd = self._get_work_dir()
        if not wd:
            return []
        ndx_name = self.mmpbsa_index.text().strip() or "index.ndx"
        ndx_path = ndx_name if os.path.isabs(ndx_name) else os.path.join(wd, ndx_name)
        groups = parse_ndx_groups(ndx_path)
        if not groups:
            self.log_requested.emit(f"未在 {ndx_path} 找到有效的索引组，请确认文件路径。", "warning")
            return []
        summary = ", ".join(f"{idx}:{name}" for idx, name in groups)
        self.log_requested.emit(f"NDX 索引组扫描完成 ({len(groups)} 组): {summary}", "info")
        return groups

    def run_mmpbsa(self):
        wd = self._get_work_dir()
        if not wd:
            return

        # 1. 前置环境检测
        runner_prefix, env_msg = self._detect_runner()
        if not runner_prefix:
            self.log_requested.emit(env_msg, "error")
            return

        files = {
            "tpr": self.mmpbsa_tpr.text().strip() or "md.tpr",
            "xtc": self.mmpbsa_xtc.text().strip() or "md.xtc",
            "ndx": self.mmpbsa_index.text().strip() or "index.ndx",
            "top": self.mmpbsa_top.text().strip() or "topol.top",
        }

        rec_grp = self.mmpbsa_rec_group.text().strip()
        lig_grp = self.mmpbsa_lig_group.text().strip()
        if not rec_grp or not lig_grp:
            self.log_requested.emit("错误: 请明确填写受体与配体索引组编号。", "error")
            return

        # 若 NDX 存在且用户输入为数字，校验证实索引组号有效
        ndx_path = files["ndx"] if os.path.isabs(files["ndx"]) else os.path.join(wd, files["ndx"])
        if os.path.isfile(ndx_path):
            groups = parse_ndx_groups(ndx_path)
            valid_ids = {str(idx) for idx, _ in groups}
            valid_names = {name for _, name in groups}
            for label, val in [("受体组", rec_grp), ("配体组", lig_grp)]:
                if val not in valid_ids and val not in valid_names:
                    self.log_requested.emit(
                        f"错误: {label} '{val}' 不存在于 {files['ndx']} 中（可用组号: 0~{max(0, len(groups)-1)}）。",
                        "error"
                    )
                    return

        # 2. 时间 -> 帧数严格换算并写出 mmpbsa.in
        try:
            start_f, end_f, interval_f = convert_ps_to_mmpbsa_frames(
                self.mmpbsa_start.value(),
                self.mmpbsa_end.value(),
                self.mmpbsa_interval.value(),
                self.mmpbsa_traj_dt.value()
            )
        except ValueError as exc:
            self.log_requested.emit(f"采样参数错误: {exc}", "error")
            return

        mmpbsa_in_content = build_mmpbsa_input_file({
            "startframe": start_f,
            "endframe": end_f,
            "interval": interval_f,
        })
        mmpbsa_in_path = os.path.join(wd, "mmpbsa.in")
        with open(mmpbsa_in_path, "w", encoding="utf-8") as f:
            f.write(mmpbsa_in_content)

        # 保存绘图导出偏好设置，供后处理读取
        plot_spec_path = os.path.join(wd, "mmpbsa_plot_spec.json")
        with open(plot_spec_path, "w", encoding="utf-8") as f:
            json.dump({
                "format": self.mmpbsa_fmt.currentText(),
                "width_inch": self.mmpbsa_width.value(),
                "height_inch": self.mmpbsa_height.value(),
            }, f, indent=2)

        options = {
            "input_file": "mmpbsa.in",
            "receptor_group": rec_grp,
            "ligand_group": lig_grp,
            "nt": self.mmpbsa_nt.value(),
            "runner_prefix": runner_prefix,
        }
        cmd, step_name = build_mmpbsa_command(files, options=options)

        self.log_requested.emit("=" * 60, "cmd")
        self.log_requested.emit(f"{step_name} | {env_msg}", "cmd")
        self.log_requested.emit(
            f"帧参数换算: startframe={start_f}, endframe={end_f or 'END'}, interval={interval_f} "
            f"(traj_dt={self.mmpbsa_traj_dt.value()} ps/frame), -cg {rec_grp} {lig_grp}",
            "info"
        )
        self.log_requested.emit("=" * 60, "cmd")

        self.run_requested.emit([cmd], wd, step_name)

    def set_running_state(self, running: bool):
        self.mmpbsa_run_btn.setEnabled(not running)

    def get_config(self) -> dict:
        return {
            "tpr": self.mmpbsa_tpr.text().strip(),
            "xtc": self.mmpbsa_xtc.text().strip(),
            "ndx": self.mmpbsa_index.text().strip(),
            "top": self.mmpbsa_top.text().strip(),
            "rec_group": self.mmpbsa_rec_group.text().strip(),
            "lig_group": self.mmpbsa_lig_group.text().strip(),
            "start": self.mmpbsa_start.value(),
            "end": self.mmpbsa_end.value(),
            "interval": self.mmpbsa_interval.value(),
            "traj_dt": self.mmpbsa_traj_dt.value(),
            "nt": self.mmpbsa_nt.value(),
            "fmt": self.mmpbsa_fmt.currentText(),
            "width": self.mmpbsa_width.value(),
            "height": self.mmpbsa_height.value(),
        }

    def set_config(self, data: dict):
        if not isinstance(data, dict):
            return
        if "tpr" in data:
            self.mmpbsa_tpr.setText(str(data["tpr"]))
        if "xtc" in data:
            self.mmpbsa_xtc.setText(str(data["xtc"]))
        if "ndx" in data:
            self.mmpbsa_index.setText(str(data["ndx"]))
        if "top" in data:
            self.mmpbsa_top.setText(str(data["top"]))
        if "rec_group" in data:
            self.mmpbsa_rec_group.setText(str(data["rec_group"]))
        if "lig_group" in data:
            self.mmpbsa_lig_group.setText(str(data["lig_group"]))
        if "start" in data:
            self.mmpbsa_start.setValue(float(data["start"]))
        if "end" in data:
            self.mmpbsa_end.setValue(float(data["end"]))
        if "interval" in data:
            self.mmpbsa_interval.setValue(float(data["interval"]))
        if "traj_dt" in data:
            self.mmpbsa_traj_dt.setValue(float(data["traj_dt"]))
        if "nt" in data:
            self.mmpbsa_nt.setValue(int(data["nt"]))
        if "fmt" in data:
            idx = self.mmpbsa_fmt.findText(str(data["fmt"]))
            if idx >= 0:
                self.mmpbsa_fmt.setCurrentIndex(idx)
        if "width" in data:
            self.mmpbsa_width.setValue(float(data["width"]))
        if "height" in data:
            self.mmpbsa_height.setValue(float(data["height"]))

    def retranslate_ui(self, lang: str):
        self.info_label.setText(tr("mmpbsa_info", lang=lang))
        self.inp_group.setTitle(tr("mmpbsa_inp_group", lang=lang))
        self.sam_group.setTitle(tr("mmpbsa_sam_group", lang=lang))
        self.img_group.setTitle(tr("mmpbsa_img_group", lang=lang))
        self.mmpbsa_run_btn.setText(tr("mmpbsa_run_btn", lang=lang))
