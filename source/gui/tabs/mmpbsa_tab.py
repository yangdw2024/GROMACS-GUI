# -*- coding: utf-8 -*-
"""
Part 6: MMPBSA 结合自由能计算独立页面组件
从 main_window.py 拆分抽离。
严格保持原有全部控件名称、默认值、数值范围、命令组装调用 (build_mmpbsa_command)
及统一任务调度机制不变。
"""

import os
from typing import Optional, Callable

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QSpinBox, QDoubleSpinBox, QGroupBox, QScrollArea
)

from simulation.analysis import build_mmpbsa_command
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
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self._get_work_dir = get_work_dir or (lambda: os.getcwd())
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

        # 1. 输入文件参数
        self.inp_group = QGroupBox(tr("mmpbsa_inp_group"))
        igrid = QGridLayout(self.inp_group)

        self.mmpbsa_tpr = QLineEdit("md.tpr")
        self.mmpbsa_xtc = QLineEdit("md.xtc")
        self.mmpbsa_index = QLineEdit("index.ndx")
        self.mmpbsa_top = QLineEdit("topol.top")

        igrid.addWidget(QLabel("运行输入:"), 0, 0)
        igrid.addWidget(self.mmpbsa_tpr, 0, 1)
        igrid.addWidget(QLabel("轨迹文件:"), 0, 2)
        igrid.addWidget(self.mmpbsa_xtc, 0, 3)

        igrid.addWidget(QLabel("索引文件:"), 1, 0)
        igrid.addWidget(self.mmpbsa_index, 1, 1)
        igrid.addWidget(QLabel("拓扑文件:"), 1, 2)
        igrid.addWidget(self.mmpbsa_top, 1, 3)

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

        self.mmpbsa_nt = QSpinBox()
        self.mmpbsa_nt.setRange(1, 64)
        self.mmpbsa_nt.setValue(4)

        sgrid.addWidget(QLabel("计算开始时间:"), 0, 0)
        sgrid.addWidget(self.mmpbsa_start, 0, 1)
        sgrid.addWidget(QLabel("计算结束时间:"), 0, 2)
        sgrid.addWidget(self.mmpbsa_end, 0, 3)

        sgrid.addWidget(QLabel("采样时间间隔:"), 1, 0)
        sgrid.addWidget(self.mmpbsa_interval, 1, 1)
        sgrid.addWidget(QLabel("并行线程数:"), 1, 2)
        sgrid.addWidget(self.mmpbsa_nt, 1, 3)

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

    def run_mmpbsa(self):
        wd = self._get_work_dir()
        if not wd:
            return

        files = {
            "tpr": self.mmpbsa_tpr.text().strip() or "md.tpr",
            "xtc": self.mmpbsa_xtc.text().strip() or "md.xtc",
            "ndx": self.mmpbsa_index.text().strip() or "index.ndx",
            "top": self.mmpbsa_top.text().strip() or "topol.top",
        }
        cmd, step_name = build_mmpbsa_command(files)

        self.log_requested.emit("=" * 60, "cmd")
        self.log_requested.emit(step_name, "cmd")
        self.log_requested.emit("提示: MMPBSA 需要安装 gmx_MMPBSA 包", "warning")
        self.log_requested.emit("  pip install gmx-MMPBSA", "warning")
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
            "start": self.mmpbsa_start.value(),
            "end": self.mmpbsa_end.value(),
            "interval": self.mmpbsa_interval.value(),
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
        if "start" in data:
            self.mmpbsa_start.setValue(float(data["start"]))
        if "end" in data:
            self.mmpbsa_end.setValue(float(data["end"]))
        if "interval" in data:
            self.mmpbsa_interval.setValue(float(data["interval"]))
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
