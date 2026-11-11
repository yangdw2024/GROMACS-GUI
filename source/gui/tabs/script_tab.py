# -*- coding: utf-8 -*-
"""
Part 7: 自定义脚本独立页面组件
从 main_window.py 拆分抽离。
负责：
1. 脚本编辑器与类型切换 (PowerShell / Batch / Shell)
2. 内置 14 套标准与科研流程模板加载 (调用 gui.script_templates.get_script_template)
3. 自定义模板的加载与管理弹窗交互
4. 脚本保存与加载到本地文件
5. 构建脚本执行命令并通过统一信号 run_requested 上抛给主窗口调度机制
"""

import json
import os
import sys
from typing import Optional, Callable

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QGroupBox, QPlainTextEdit, QFileDialog, QDialog
)

from gui.script_templates import get_script_template
from gui.dialogs.custom_template import CustomTemplateDialog


class ScriptTab(QWidget):
    """自定义脚本页面组件

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
        self.custom_tmpl_btns = []

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        info = QLabel(
            "自定义脚本运行模块。可以编写 Windows PowerShell / Batch 脚本，"
            "调用 GROMACS 命令或执行其他自定义流程。\n"
            "提示: 脚本会在工作目录下执行，可使用 $env:GMX 或 %GMX% 获取gmx路径。"
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #555; font-size: 12px;")
        layout.addWidget(info)

        # 1. 顶部工具栏
        toolbar = QHBoxLayout()

        self.script_type = QComboBox()
        self.script_type.addItems(["PowerShell (.ps1)", "Batch (.bat)", "Shell 命令"])
        self.script_type.setCurrentIndex(2)
        toolbar.addWidget(QLabel("脚本类型:"))
        toolbar.addWidget(self.script_type)

        self.script_save_btn = QPushButton("保存脚本")
        self.script_save_btn.clicked.connect(self.save_script)
        self.script_load_btn = QPushButton("加载脚本")
        self.script_load_btn.clicked.connect(self.load_script)
        self.script_clear_btn = QPushButton("清空")
        self.script_clear_btn.clicked.connect(self.clear_editor)
        self.script_run_btn = QPushButton("▶ 运行脚本")
        self.script_run_btn.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 6px 16px; }"
            "QPushButton:hover { background-color: #45a049; }"
        )
        self.script_run_btn.clicked.connect(self.run_script)

        toolbar.addStretch(1)
        toolbar.addWidget(self.script_load_btn)
        toolbar.addWidget(self.script_save_btn)
        toolbar.addWidget(self.script_clear_btn)
        toolbar.addWidget(self.script_run_btn)
        layout.addLayout(toolbar)

        # 2. 脚本编辑器
        script_group = QGroupBox("脚本编辑")
        script_group.setStyleSheet("QGroupBox { font-weight: bold; color: #6A1B9A; }")
        sg_layout = QVBoxLayout(script_group)

        self.script_edit = QPlainTextEdit()
        gmx_p = self._get_gmx_path().replace("\\", "/")
        self.script_edit.setPlaceholderText(
            "# 示例: 运行一个简单的 GROMACS 命令\n"
            "# PowerShell 脚本示例:\n"
            f'$GMX = "{gmx_p}"\n'
            'Write-Host "Running gmx version..."\n'
            "& $GMX --version\n"
        )
        font = QFont("Consolas", 10)
        self.script_edit.setFont(font)
        self.script_edit.setMinimumHeight(400)
        sg_layout.addWidget(self.script_edit)
        layout.addWidget(script_group, stretch=1)

        # 3. 快速模板区
        self.tmpl_group = QGroupBox("快速模板")
        self.tmpl_group.setStyleSheet("QGroupBox { font-weight: bold; color: #E65100; }")
        tmpl_layout = QVBoxLayout(self.tmpl_group)

        tmpl_row1 = QHBoxLayout()
        tmpl_btn1 = QPushButton("能量最小化")
        tmpl_btn1.clicked.connect(lambda: self.load_script_template("em"))
        tmpl_btn2 = QPushButton("完整MD流程")
        tmpl_btn2.clicked.connect(lambda: self.load_script_template("full_md"))
        tmpl_btn3 = QPushButton("RMSD分析")
        tmpl_btn3.clicked.connect(lambda: self.load_script_template("rmsd"))
        tmpl_btn4 = QPushButton("RDF分析")
        tmpl_btn4.clicked.connect(lambda: self.load_script_template("rdf"))
        tmpl_row1.addWidget(tmpl_btn1)
        tmpl_row1.addWidget(tmpl_btn2)
        tmpl_row1.addWidget(tmpl_btn3)
        tmpl_row1.addWidget(tmpl_btn4)
        tmpl_row1.addStretch(1)

        tmpl_row2 = QHBoxLayout()
        tmpl_btn5 = QPushButton("氢键分析")
        tmpl_btn5.clicked.connect(lambda: self.load_script_template("hbond"))
        tmpl_btn6 = QPushButton("SASA分析")
        tmpl_btn6.clicked.connect(lambda: self.load_script_template("sasa"))
        tmpl_btn7 = QPushButton("PCA分析")
        tmpl_btn7.clicked.connect(lambda: self.load_script_template("pca"))
        tmpl_btn8 = QPushButton("NVT")
        tmpl_btn8.clicked.connect(lambda: self.load_script_template("nvt"))
        tmpl_btn9 = QPushButton("NPT")
        tmpl_btn9.clicked.connect(lambda: self.load_script_template("npt"))
        tmpl_btn10 = QPushButton("MD")
        tmpl_btn10.clicked.connect(lambda: self.load_script_template("md"))
        tmpl_row2.addWidget(tmpl_btn5)
        tmpl_row2.addWidget(tmpl_btn6)
        tmpl_row2.addWidget(tmpl_btn7)
        tmpl_row2.addWidget(tmpl_btn8)
        tmpl_row2.addWidget(tmpl_btn9)
        tmpl_row2.addWidget(tmpl_btn10)
        tmpl_row2.addStretch(1)

        self.tmpl_row3 = QHBoxLayout()
        tmpl_btn11 = QPushButton("ClFFCl EM+NPT")
        tmpl_btn11.clicked.connect(lambda: self.load_script_template("clffcl_em_npt"))
        tmpl_btn12 = QPushButton("ClFFCl SA蒸发")
        tmpl_btn12.clicked.connect(lambda: self.load_script_template("clffcl_sa"))
        tmpl_btn13 = QPushButton("ClFFCl MD-1")
        tmpl_btn13.clicked.connect(lambda: self.load_script_template("clffcl_md1"))
        tmpl_btn14 = QPushButton("ClFFCl evapDIO")
        tmpl_btn14.clicked.connect(lambda: self.load_script_template("clffcl_evapdio"))

        self.tmpl_btn_manage = QPushButton("管理自定义模板")
        self.tmpl_btn_manage.setStyleSheet(
            "QPushButton { background-color: #9C27B0; color: white; font-weight: bold; padding: 6px 16px; }"
            "QPushButton:hover { background-color: #7B1FA2; }"
        )
        self.tmpl_btn_manage.clicked.connect(self.manage_templates)

        self.tmpl_row3.addWidget(tmpl_btn11)
        self.tmpl_row3.addWidget(tmpl_btn12)
        self.tmpl_row3.addWidget(tmpl_btn13)
        self.tmpl_row3.addWidget(tmpl_btn14)

        self._load_custom_template_buttons(self.tmpl_row3)
        self.tmpl_row3.addWidget(self.tmpl_btn_manage)
        self.tmpl_row3.addStretch(1)

        tmpl_layout.addLayout(tmpl_row1)
        tmpl_layout.addLayout(tmpl_row2)
        tmpl_layout.addLayout(self.tmpl_row3)
        layout.addWidget(self.tmpl_group)

    def _load_custom_template_buttons(self, layout):
        if getattr(sys, 'frozen', False):
            base = os.path.dirname(sys.executable)
        else:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        templates_file = os.path.join(base, "templates.json")
        if os.path.isfile(templates_file):
            try:
                with open(templates_file, "r", encoding="utf-8") as f:
                    custom_templates = json.load(f)
                for template in custom_templates:
                    btn = QPushButton(template["name"])
                    btn.setStyleSheet(
                        "QPushButton { background-color: #7E57C2; color: white; font-weight: bold; padding: 6px 12px; }"
                        "QPushButton:hover { background-color: #5E35B1; }"
                    )
                    btn.clicked.connect(lambda checked, t=template: self.apply_custom_template(t))
                    self.custom_tmpl_btns.append(btn)
                    layout.addWidget(btn)
            except Exception:
                pass

    def apply_custom_template(self, template: dict):
        self.script_edit.setPlainText(template.get("content", ""))
        idx = self.script_type.findText(template.get("type", ""))
        if idx >= 0:
            self.script_type.setCurrentIndex(idx)

    def manage_templates(self):
        dialog = CustomTemplateDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            for btn in self.custom_tmpl_btns:
                self.tmpl_row3.removeWidget(btn)
                btn.deleteLater()
            self.custom_tmpl_btns.clear()
            self._load_custom_template_buttons(self.tmpl_row3)
            self.log_requested.emit("自定义模板已更新", "success")

    def load_script_template(self, key: str):
        gmx_norm = self._get_gmx_path().replace("\\", "/")
        script_type = self.script_type.currentText()
        text = get_script_template(script_type, key, gmx_norm)
        self.script_edit.setPlainText(text)

    def save_script(self):
        wd = self._get_work_dir() or os.getcwd()
        fname, _ = QFileDialog.getSaveFileName(self, "保存脚本", wd, "脚本文件 (*.ps1 *.bat *.txt);;所有文件 (*.*)")
        if fname:
            with open(fname, "w", encoding="utf-8") as f:
                f.write(self.script_edit.toPlainText())
            self.log_requested.emit(f"脚本已保存到: {fname}", "success")

    def load_script(self):
        wd = self._get_work_dir() or os.getcwd()
        fname, _ = QFileDialog.getOpenFileName(self, "加载脚本", wd, "脚本文件 (*.ps1 *.bat *.txt);;所有文件 (*.*)")
        if fname:
            with open(fname, "r", encoding="utf-8", errors="ignore") as f:
                self.script_edit.setPlainText(f.read())
            self.log_requested.emit(f"脚本已加载: {fname}", "info")

    def clear_editor(self):
        self.script_edit.clear()

    def run_script(self):
        wd = self._get_work_dir()
        if not wd:
            self.log_requested.emit("错误: 工作目录未设置", "error")
            return

        script_text = self.script_edit.toPlainText().strip()
        if not script_text:
            self.log_requested.emit("脚本内容为空，请先输入或加载脚本。", "error")
            return

        script_type = self.script_type.currentText()
        step_name = "自定义脚本"
        self.log_requested.emit("=" * 60, "cmd")
        self.log_requested.emit(f"运行 {script_type}", "cmd")
        self.log_requested.emit("=" * 60, "cmd")

        # 创建临时脚本文件
        tmp_dir = wd
        gmx_path = self._get_gmx_path()
        if "PowerShell" in script_type:
            script_file = os.path.join(tmp_dir, "_gmx_gui_script.ps1")
            with open(script_file, "w", encoding="utf-8") as f:
                f.write(script_text)
            cmd = [["powershell", "-ExecutionPolicy", "Bypass", "-File", script_file]]
        elif "Batch" in script_type:
            script_file = os.path.join(tmp_dir, "_gmx_gui_script.bat")
            with open(script_file, "w", encoding="utf-8") as f:
                f.write(f"@echo off\ncd /d \"{wd}\"\nset GMX={gmx_path}\n\n{script_text}")
            cmd = [script_file]
        else:
            # 直接作为命令行命令执行
            cmd = [["cmd", "/c", script_text]]

        # 上抛给主窗口统一任务调度器
        self.run_requested.emit(cmd, wd, step_name)

    # --- 配置兼容接口 ---
    def get_config(self) -> dict:
        return {
            "script_type": self.script_type.currentText(),
            "script_content": self.script_edit.toPlainText()
        }

    def set_config(self, data: dict):
        if not isinstance(data, dict):
            return
        if "script_type" in data:
            idx = self.script_type.findText(data["script_type"])
            if idx >= 0:
                self.script_type.setCurrentIndex(idx)
        if "script_content" in data and data["script_content"]:
            self.script_edit.setPlainText(data["script_content"])
