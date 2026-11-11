# -*- coding: utf-8 -*-
"""
Part 4: 轨迹预处理与轨迹工具独立页面组件
从 main_window.py 拆分抽离。
负责：
1. 基础轨迹文件输入 (XTC/TPR/NDX)
2. 轨迹预处理五步流水线 (PBC修复、体系居中、旋转/平移拟合、时间截取、降采样)
3. 常用轨迹工具 (trjconv, trjcat, trjorder, trjreshape, trjreduce, trjcluster, trjstrip)
4. 将生成命令通过统一信号 run_requested 上抛至主窗口任务调度器
"""

import os
import subprocess
from typing import Optional, Callable

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QDoubleSpinBox, QGroupBox, QScrollArea,
    QFileDialog, QMessageBox
)

from simulation.analysis import (
    build_trajectory_tool_command,
    build_preprocessing_commands
)

class TrajectoryTab(QWidget):
    """Part 4: 轨迹处理与预处理流水线独立页面组件

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
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self._get_work_dir = get_work_dir or (lambda: os.getcwd())
        self._get_gmx_path = get_gmx_path or (lambda: "gmx")
        self.traj_widgets = {}

        self._init_ui()

    def _browse_file(self, line_edit: QLineEdit, title: str = "选择文件", file_filter: str = "所有文件 (*.*)"):
        """通用文件浏览对话框，在工作目录内使用相对文件名，否则填完整路径"""
        wd = self._get_work_dir() or os.getcwd()
        fname, _ = QFileDialog.getOpenFileName(self, title, wd, file_filter)
        if fname:
            if fname.startswith(wd + os.sep) or fname.startswith(wd + "/"):
                line_edit.setText(os.path.basename(fname))
            else:
                line_edit.setText(fname)

    def _create_file_input(self, placeholder: str, default: str = "", filter_str: str = "所有文件 (*.*)", dialog_title: str = "选择文件"):
        """创建 输入框+浏览按钮 的水平布局组件, 返回 (line_edit, layout)"""
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

        # 1. 通用参数区
        common_group = QGroupBox("轨迹处理参数")
        cgrid = QGridLayout(common_group)

        self.traj_input, traj_input_layout = self._create_file_input(
            "md.xtc", "md.xtc", "轨迹文件 (*.xtc *.trr);;所有文件 (*.*)", "选择输入轨迹"
        )
        self.traj_tpr, traj_tpr_layout = self._create_file_input(
            "md.tpr", "md.tpr", "TPR文件 (*.tpr);;所有文件 (*.*)", "选择TPR文件"
        )
        self.traj_index, traj_idx_layout = self._create_file_input(
            "index.ndx (可选)", "", "索引文件 (*.ndx);;所有文件 (*.*)", "选择索引文件"
        )

        cgrid.addWidget(QLabel("输入轨迹:"), 0, 0)
        cgrid.addLayout(traj_input_layout, 0, 1)
        cgrid.addWidget(QLabel("TPR文件:"), 0, 2)
        cgrid.addLayout(traj_tpr_layout, 0, 3)

        cgrid.addWidget(QLabel("索引文件:"), 1, 0)
        cgrid.addLayout(traj_idx_layout, 1, 1)

        vbox.addWidget(common_group)

        # 2. 预处理流水线
        prep_group = QGroupBox("🔄 轨迹预处理流水线")
        prep_group.setProperty("role", "phaseGroup")
        prep_layout = QVBoxLayout(prep_group)
        prep_layout.setSpacing(8)

        prep_desc = QLabel(
            "标准预处理五步法：PBC修复 → 体系居中 → 去除平动/转动 → 截取平衡段 → 降采样精简"
        )
        prep_desc.setWordWrap(True)
        prep_desc.setProperty("role", "desc")
        prep_layout.addWidget(prep_desc)

        prep_grid = QGridLayout()
        prep_grid.setSpacing(6)

        # Step 1: PBC修复
        prep_grid.addWidget(QLabel("Step 1: PBC修复"), 0, 0)
        self.prep_pbc = QComboBox()
        self.prep_pbc.addItems(["mol (分子完整)", "res (残基完整)", "atom (原子完整)", "nojump (无跳跃)", "whole (全体系)", "cluster (团簇完整)"])
        prep_grid.addWidget(self.prep_pbc, 0, 1)

        # Step 2: 体系居中
        prep_grid.addWidget(QLabel("Step 2: 居中组:"), 0, 2)
        self.prep_center = QLineEdit("Protein")
        self.prep_center.setPlaceholderText("居中组名 (如 Protein, System)")
        prep_grid.addWidget(self.prep_center, 0, 3)

        # Step 3: 拟合
        prep_grid.addWidget(QLabel("Step 3: 拟合方式:"), 1, 0)
        self.prep_fit = QComboBox()
        self.prep_fit.addItems(["rot+trans (旋转+平移)", "trans (仅平移)", "rot (仅旋转)", "none (不拟合)"])
        prep_grid.addWidget(self.prep_fit, 1, 1)

        prep_grid.addWidget(QLabel("拟合参考组:"), 1, 2)
        self.prep_fit_ref = QLineEdit("Protein")
        self.prep_fit_ref.setPlaceholderText("拟合参考组")
        prep_grid.addWidget(self.prep_fit_ref, 1, 3)

        # Step 4: 截取时间
        prep_grid.addWidget(QLabel("Step 4: 起始时间 (ps):"), 2, 0)
        self.prep_b = QDoubleSpinBox()
        self.prep_b.setRange(0, 1000000)
        self.prep_b.setValue(0)
        self.prep_b.setDecimals(1)
        self.prep_b.setSuffix(" ps (0=从头)")
        prep_grid.addWidget(self.prep_b, 2, 1)

        prep_grid.addWidget(QLabel("结束时间 (ps):"), 2, 2)
        self.prep_e = QDoubleSpinBox()
        self.prep_e.setRange(0, 1000000)
        self.prep_e.setValue(0)
        self.prep_e.setDecimals(1)
        self.prep_e.setSuffix(" ps (0=到结尾)")
        prep_grid.addWidget(self.prep_e, 2, 3)

        # Step 5: 降采样
        prep_grid.addWidget(QLabel("Step 5: 降采样间隔:"), 3, 0)
        self.prep_dt = QDoubleSpinBox()
        self.prep_dt.setRange(0, 100000)
        self.prep_dt.setValue(0)
        self.prep_dt.setDecimals(1)
        self.prep_dt.setSuffix(" ps (0=不采样)")
        prep_grid.addWidget(self.prep_dt, 3, 1)

        prep_grid.addWidget(QLabel("输出文件名:"), 3, 2)
        self.prep_output = QLineEdit("md_clean.xtc")
        prep_grid.addWidget(self.prep_output, 3, 3)

        prep_layout.addLayout(prep_grid)

        # 运行按钮
        self.prep_run_btn = QPushButton("一键执行预处理流水线")
        self.prep_run_btn.setProperty("role", "browseBtn")
        self.prep_run_btn.clicked.connect(self.run_preprocessing_pipeline)
        prep_layout.addWidget(self.prep_run_btn)

        vbox.addWidget(prep_group)

        # 3. 各独立轨迹工具
        tools = [
            ("trjconv", "轨迹转换", "转换轨迹格式、去除PBC、拟合等", "md_fit.xtc"),
            ("trjcat", "轨迹合并", "合并多个轨迹文件", "combined.xtc"),
            ("trjorder", "轨迹排序", "按指定顺序重新排列原子", "ordered.xtc"),
            ("trjreshape", "轨迹重塑", "改变轨迹帧数或时间步", "reshaped.xtc"),
            ("trjreduce", "轨迹精简", "减少轨迹帧数", "reduced.xtc"),
            ("trjcluster", "轨迹聚类", "对轨迹进行聚类分析", "cluster.pdb"),
            ("trjstrip", "轨迹剥离", "移除溶剂等原子", "protein.xtc"),
        ]

        self.traj_widgets = {}
        for key, name, desc, default_out in tools:
            grp = QGroupBox(f"{name}")
            grp.setProperty("role", "toolCard")
            g = QGridLayout(grp)
            g.addWidget(QLabel(desc), 0, 0, 1, 4)

            out_edit = QLineEdit(default_out)
            opt_edit = QLineEdit()
            opt_edit.setPlaceholderText("如 -pbc mol -center -fit rot+trans")

            run_btn = QPushButton("运行")
            run_btn.setProperty("role", "actionBtn")

            g.addWidget(QLabel("输出文件:"), 1, 0)
            g.addWidget(out_edit, 1, 1)
            g.addWidget(QLabel("额外选项:"), 1, 2)
            g.addWidget(opt_edit, 1, 3)

            g.addWidget(run_btn, 2, 0, 1, 4)

            self.traj_widgets[key] = {
                "out": out_edit,
                "opt": opt_edit,
                "run_btn": run_btn
            }
            run_btn.clicked.connect(lambda checked=False, k=key: self.run_trajectory_tool(k))
            vbox.addWidget(grp)

        vbox.addStretch()

    def run_preprocessing_pipeline(self):
        """一键执行轨迹预处理五步法"""
        wd = self._get_work_dir()
        if not wd:
            self.log_requested.emit("错误: 工作目录未设置", "error")
            return

        gmx = self._get_gmx_path()
        xtc = self.traj_input.text().strip() or "md.xtc"
        tpr = self.traj_tpr.text().strip() or "md.tpr"
        ndx = self.traj_index.text().strip()

        # 检查输入文件
        if not os.path.exists(os.path.join(wd, xtc)):
            QMessageBox.warning(self, "警告", f"轨迹文件不存在: {xtc}")
            return
        if not os.path.exists(os.path.join(wd, tpr)):
            QMessageBox.warning(self, "警告", f"TPR文件不存在: {tpr}")
            return

        params = {
            "wd": wd, "xtc": xtc, "tpr": tpr, "ndx": ndx,
            "pbc_mode": self.prep_pbc.currentText().split()[0],
            "center_group": self.prep_center.text().strip(),
            "fit_mode": self.prep_fit.currentText().split()[0],
            "fit_ref": self.prep_fit_ref.text().strip(),
            "b": self.prep_b.value(), "e": self.prep_e.value(),
            "dt": self.prep_dt.value(),
            "output": self.prep_output.text().strip() or "md_clean.xtc",
        }
        commands = build_preprocessing_commands(gmx, params)

        self.log_requested.emit(f"开始轨迹预处理流水线: {xtc} → {params['output']}", "info")
        for i, (cmd, step_name, echo_prefix, out_file) in enumerate(commands, 1):
            self.log_requested.emit(f"[{i}/{len(commands)}] {step_name}", "info")
            if echo_prefix:
                cmd_str = echo_prefix + " ".join(cmd)
                self.log_requested.emit(f"执行: {cmd_str}", "cmd")
                try:
                    result = subprocess.run(
                        cmd_str, shell=True, cwd=wd,
                        capture_output=True, text=True, timeout=3600
                    )
                    if result.returncode == 0:
                        self.log_requested.emit(f"  ✓ {step_name} 完成", "success")
                    else:
                        err = result.stderr[:500] if result.stderr else "未知错误"
                        self.log_requested.emit(f"  ✗ {step_name} 失败: {err}", "error")
                        return
                except Exception as e:
                    self.log_requested.emit(f"  ✗ {step_name} 异常: {str(e)}", "error")
                    return
            else:
                self.run_requested.emit([cmd], wd, step_name)

            # 清理中间文件
            if out_file.startswith("_prep_") and os.path.exists(os.path.join(wd, out_file)):
                try:
                    os.remove(os.path.join(wd, out_file))
                except Exception:
                    pass

        self.log_requested.emit(f"预处理完成: {params['output']}", "success")

    def run_trajectory_tool(self, key: str):
        wd = self._get_work_dir()
        if not wd:
            self.log_requested.emit("错误: 工作目录未设置", "error")
            return

        gmx = self._get_gmx_path()
        files = {
            "wd": wd,
            "inp": self.traj_input.text().strip() or "md.xtc",
            "tpr": self.traj_tpr.text().strip() or "md.tpr",
            "ndx": self.traj_index.text().strip(),
        }
        if key not in self.traj_widgets:
            self.log_requested.emit(f"未知轨迹工具: {key}", "error")
            return

        w = self.traj_widgets[key]
        opt = w["opt"].text().strip()

        result = build_trajectory_tool_command(key, gmx, files, opt)
        if result is None:
            self.log_requested.emit(f"未知轨迹工具: {key}", "error")
            return
        cmd, step_name = result
        self.run_requested.emit([cmd], wd, step_name)

    def set_running_state(self, running: bool):
        if hasattr(self, "prep_run_btn"):
            self.prep_run_btn.setEnabled(not running)
        for w in self.traj_widgets.values():
            w["run_btn"].setEnabled(not running)

    def get_config(self) -> dict:
        cfg = {
            "traj_input": self.traj_input.text().strip(),
            "traj_tpr": self.traj_tpr.text().strip(),
            "traj_index": self.traj_index.text().strip(),
            "prep_pbc": self.prep_pbc.currentText(),
            "prep_center": self.prep_center.text().strip(),
            "prep_fit": self.prep_fit.currentText(),
            "prep_fit_ref": self.prep_fit_ref.text().strip(),
            "prep_b": self.prep_b.value(),
            "prep_e": self.prep_e.value(),
            "prep_dt": self.prep_dt.value(),
            "prep_output": self.prep_output.text().strip(),
            "tools": {}
        }
        for k, w in self.traj_widgets.items():
            cfg["tools"][k] = {
                "out": w["out"].text().strip(),
                "opt": w["opt"].text().strip()
            }
        return cfg

    def set_config(self, data: dict):
        if not isinstance(data, dict):
            return
        if "traj_input" in data:
            self.traj_input.setText(str(data["traj_input"]))
        if "traj_tpr" in data:
            self.traj_tpr.setText(str(data["traj_tpr"]))
        if "traj_index" in data:
            self.traj_index.setText(str(data["traj_index"]))
        if "prep_pbc" in data:
            idx = self.prep_pbc.findText(str(data["prep_pbc"]))
            if idx >= 0:
                self.prep_pbc.setCurrentIndex(idx)
        if "prep_center" in data:
            self.prep_center.setText(str(data["prep_center"]))
        if "prep_fit" in data:
            idx = self.prep_fit.findText(str(data["prep_fit"]))
            if idx >= 0:
                self.prep_fit.setCurrentIndex(idx)
        if "prep_fit_ref" in data:
            self.prep_fit_ref.setText(str(data["prep_fit_ref"]))
        if "prep_b" in data:
            self.prep_b.setValue(float(data["prep_b"]))
        if "prep_e" in data:
            self.prep_e.setValue(float(data["prep_e"]))
        if "prep_dt" in data:
            self.prep_dt.setValue(float(data["prep_dt"]))
        if "prep_output" in data:
            self.prep_output.setText(str(data["prep_output"]))
        if "tools" in data and isinstance(data["tools"], dict):
            for k, tool_data in data["tools"].items():
                if k in self.traj_widgets and isinstance(tool_data, dict):
                    if "out" in tool_data:
                        self.traj_widgets[k]["out"].setText(str(tool_data["out"]))
                    if "opt" in tool_data:
                        self.traj_widgets[k]["opt"].setText(str(tool_data["opt"]))
