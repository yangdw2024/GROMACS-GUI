# -*- coding: utf-8 -*-
"""
Part 2: 结构处理工具独立页面组件
从 main_window.py 拆分抽离。
负责：
1. 结构输入与索引文件选择 (PDB/GRO/NDX)
2. 核心结构准备：gmx make_ndx (含快捷原子组选择表达式)、pdb2gmx、editconf、genrestr、genconf
3. 结构转换与验证：格式转换/盒子编辑、gmx check 结构校验、gmx dump 信息查看
4. 显式接口解耦：通过 get_md_ff 注入获取力场参数，不跨层直接访问父对象
5. 命令构建并通过统一信号 run_requested 上抛至主窗口任务调度器
"""

import os
from typing import Optional, Callable

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QPushButton, QGroupBox, QScrollArea, QFileDialog
)

from simulation.analysis import build_structure_tool_command


class StructureTab(QWidget):
    """Part 2: 结构处理工具独立页面组件

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
        get_md_ff: Optional[Callable[[], str]] = None,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self._get_work_dir = get_work_dir or (lambda: os.getcwd())
        self._get_gmx_path = get_gmx_path or (lambda: "gmx")
        self._get_md_ff = get_md_ff or (lambda: "")
        self.struc_widgets = {}

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
        btn.setStyleSheet("""
            QPushButton {
                background-color: #546E7A;
                color: white;
                padding: 3px 8px;
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #455A64;
            }
        """)
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

        # 通用参数
        common_group = QGroupBox("结构处理参数")
        common_group.setStyleSheet("QGroupBox { font-weight: bold; color: #1565C0; }")
        cgrid = QGridLayout(common_group)

        self.struc_input, struc_input_layout = self._create_file_input(
            "protein.pdb", "protein.pdb", "结构文件 (*.gro *.pdb);;所有文件 (*.*)", "选择输入结构"
        )
        self.struc_index, struc_idx_layout = self._create_file_input(
            "index.ndx (可选)", "", "索引文件 (*.ndx);;所有文件 (*.*)", "选择索引文件"
        )

        cgrid.addWidget(QLabel("输入结构:"), 0, 0)
        cgrid.addLayout(struc_input_layout, 0, 1)
        cgrid.addWidget(QLabel("索引文件:"), 0, 2)
        cgrid.addLayout(struc_idx_layout, 0, 3)

        vbox.addWidget(common_group)

        self.struc_widgets = {}

        # === 第一组: 核心结构准备 ===
        prep_group = QGroupBox("🔧 核心结构准备")
        prep_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #E65100;
                margin-top: 8px;
                padding-top: 8px;
                border: 2px solid #E65100;
                border-radius: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        prep_layout = QVBoxLayout(prep_group)
        prep_layout.setSpacing(8)

        # 创建索引 (gmx make_ndx)
        ndx_grp = QGroupBox("📌 创建索引文件 (gmx make_ndx)")
        ndx_grp.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #BF360C;
                margin-top: 6px;
                border: 1px solid #FF8A65;
                border-radius: 6px;
                background-color: rgba(255, 138, 101, 0.1);
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        ndx_g = QGridLayout(ndx_grp)
        ndx_g.addWidget(QLabel("创建索引文件，用于后续模拟和分析中选择特定原子组"), 0, 0, 1, 4)

        ndx_out_edit = QLineEdit("index.ndx")
        ndx_opt_edit = QLineEdit()
        ndx_opt_edit.setPlaceholderText("如 -select 'resname ALA'")

        ndx_run_btn = QPushButton("运行创建索引")
        ndx_run_btn.setStyleSheet("""
            QPushButton {
                background-color: #E65100;
                color: white;
                font-weight: bold;
                padding: 6px 16px;
                border-radius: 6px;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #BF360C; }
        """)

        ndx_struc_edit, ndx_struc_layout = self._create_file_input(
            "input.gro", "", "结构文件 (*.gro *.pdb);;所有文件 (*.*)", "选择输入结构"
        )
        ndx_g.addWidget(QLabel("输入结构:"), 1, 0)
        ndx_g.addLayout(ndx_struc_layout, 1, 1)
        ndx_g.addWidget(QLabel("输出文件:"), 1, 2)
        ndx_g.addWidget(ndx_out_edit, 1, 3)

        ndx_g.addWidget(QLabel("快捷选择:"), 2, 0)
        ndx_btn_layout = QHBoxLayout()
        ndx_btns = [
            ("蛋白质", "-select 'protein'"),
            ("配体", "-select 'resname LIG'"),
            ("水", "-select 'resname SOL'"),
            ("离子", "-select 'resname NA CL'"),
            ("主链", "-select 'backbone'"),
            ("侧链", "-select 'sidechain'"),
        ]
        for btn_name, select_expr in ndx_btns:
            btn = QPushButton(btn_name)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #FF8A65;
                    color: white;
                    font-weight: bold;
                    padding: 4px 10px;
                    border-radius: 4px;
                    font-size: 12px;
                }
                QPushButton:hover { background-color: #FF7043; }
            """)
            btn.clicked.connect(lambda checked=False, expr=select_expr: ndx_opt_edit.setText(expr))
            ndx_btn_layout.addWidget(btn)
        ndx_g.addLayout(ndx_btn_layout, 2, 1, 1, 3)

        ndx_g.addWidget(QLabel("自定义选择:"), 3, 0)
        ndx_custom_edit = QLineEdit()
        ndx_custom_edit.setPlaceholderText("如 -select 'resname ALA' 或 -select 'index 0'")
        ndx_apply_btn = QPushButton("应用")
        ndx_apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF8A65;
                color: white;
                font-weight: bold;
                padding: 4px 10px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #FF7043; }
        """)
        ndx_apply_btn.clicked.connect(lambda: ndx_opt_edit.setText(ndx_custom_edit.text()))
        ndx_g.addWidget(ndx_custom_edit, 3, 1, 1, 2)
        ndx_g.addWidget(ndx_apply_btn, 3, 3)

        ndx_g.addWidget(QLabel("额外选项:"), 4, 0)
        ndx_g.addWidget(ndx_opt_edit, 4, 1, 1, 2)
        ndx_g.addWidget(ndx_run_btn, 4, 3)

        self.struc_widgets["gmx make_ndx"] = {
            "out": ndx_out_edit,
            "opt": ndx_opt_edit,
            "run_btn": ndx_run_btn,
            "ndx_struc": ndx_struc_edit,
            "custom": ndx_custom_edit
        }
        ndx_run_btn.clicked.connect(lambda: self.run_structure_tool("gmx make_ndx"))
        prep_layout.addWidget(ndx_grp)

        prep_tools = [
            ("editconf", "编辑结构 (editconf)", "修改盒子参数、旋转、平移、居中对齐等", "protein_edit.gro", "#00897B"),
            ("pdb2gmx", "生成拓扑 (pdb2gmx)", "从PDB结构生成GROMACS拓扑文件", "protein.gro", "#00897B"),
            ("gmx genrestr", "生成位置限制 (genrestr)", "生成位置限制文件 (posre.itp)", "posre.itp", "#00897B"),
            ("genconf", "生成构象 (genconf)", "生成多个结构副本或旋转构象", "protein_multi.gro", "#00897B"),
        ]

        for key, name, desc, default_out, color in prep_tools:
            grp = QGroupBox(name)
            grp.setStyleSheet("""
                QGroupBox {
                    font-weight: bold;
                    color: #00695C;
                    margin-top: 4px;
                    border: 1px solid #4DB6AC;
                    border-radius: 6px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px;
                }
            """)
            g = QGridLayout(grp)
            g.addWidget(QLabel(desc), 0, 0, 1, 4)

            out_edit = QLineEdit(default_out)
            opt_edit = QLineEdit()
            opt_edit.setPlaceholderText("额外命令行选项 (可选)")

            run_btn = QPushButton("运行")
            run_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color};
                    color: white;
                    font-weight: bold;
                    padding: 4px 12px;
                    border-radius: 4px;
                }}
                QPushButton:hover {{ background-color: #004D40; }}
            """)

            g.addWidget(QLabel("输出文件:"), 1, 0)
            g.addWidget(out_edit, 1, 1)
            g.addWidget(QLabel("额外选项:"), 1, 2)
            g.addWidget(opt_edit, 1, 3)
            g.addWidget(run_btn, 2, 0, 1, 4)

            self.struc_widgets[key] = {
                "out": out_edit,
                "opt": opt_edit,
                "run_btn": run_btn
            }
            run_btn.clicked.connect(lambda checked=False, k=key: self.run_structure_tool(k))
            prep_layout.addWidget(grp)

        vbox.addWidget(prep_group)

        # === 第二组: 结构转换与验证 ===
        convert_group = QGroupBox("🔄 结构转换与验证")
        convert_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #1565C0;
                margin-top: 8px;
                padding-top: 8px;
                border: 2px solid #1976D2;
                border-radius: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        convert_layout = QVBoxLayout(convert_group)
        convert_layout.setSpacing(8)

        convert_tools = [
            ("editconf", "格式转换/盒子编辑", "PDB↔GRO转换、修改盒子、居中、旋转平移等", "output.gro", "#1976D2"),
            ("gmx check", "结构验证 (check)", "检查结构文件的完整性和合理性", "check_report.txt", "#1565C0"),
            ("gmx dump", "文件信息查看 (dump)", "查看GRO/TPR等文件的详细信息", "dump_output.txt", "#0D47A1"),
        ]

        for key, name, desc, default_out, color in convert_tools:
            grp = QGroupBox(name)
            grp.setStyleSheet("""
                QGroupBox {
                    font-weight: bold;
                    color: #0D47A1;
                    margin-top: 4px;
                    border: 1px solid #64B5F6;
                    border-radius: 6px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px;
                }
            """)
            g = QGridLayout(grp)
            g.addWidget(QLabel(desc), 0, 0, 1, 4)

            out_edit = QLineEdit(default_out)
            opt_edit = QLineEdit()
            opt_edit.setPlaceholderText("额外命令行选项，如 -box 10 10 10 -center 0 0 0")
            opt_edit.setToolTip("高级用户可在此添加额外的GROMACS命令行参数\n例如：-box 10 10 10 设置盒子边长\n-rotate 90 0 0 旋转结构\n-translate 1 1 1 平移结构\n-center 居中结构")

            run_btn = QPushButton("运行")
            run_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color};
                    color: white;
                    font-weight: bold;
                    padding: 4px 12px;
                    border-radius: 4px;
                }}
                QPushButton:hover {{ background-color: #0D47A1; }}
            """)

            g.addWidget(QLabel("输出文件:"), 1, 0)
            g.addWidget(out_edit, 1, 1)
            g.addWidget(QLabel("额外选项:"), 1, 2)
            g.addWidget(opt_edit, 1, 3)
            g.addWidget(run_btn, 2, 0, 1, 4)

            self.struc_widgets[key] = {
                "out": out_edit,
                "opt": opt_edit,
                "run_btn": run_btn
            }
            run_btn.clicked.connect(lambda checked=False, k=key: self.run_structure_tool(k))
            convert_layout.addWidget(grp)

        vbox.addWidget(convert_group)

        # 提示信息
        tip_label = QLabel("💡 提示：轨迹分析工具（RMSD/RMSF/SASA/氢键/RDF等）已移至 Part 5 结果分析")
        tip_label.setStyleSheet("""
            QLabel {
                background-color: rgba(255, 193, 7, 0.15);
                color: #F57C00;
                padding: 8px 12px;
                border-radius: 6px;
                border: 1px solid #FFB74D;
                font-weight: bold;
            }
        """)
        vbox.addWidget(tip_label)
        vbox.addStretch()

    def run_structure_tool(self, key: str):
        wd = self._get_work_dir()
        if not wd:
            self.log_requested.emit("错误: 工作目录未设置", "error")
            return

        gmx = self._get_gmx_path()
        files = {
            "wd": wd,
            "inp": self.struc_input.text().strip() or "protein.pdb",
            "ndx": self.struc_index.text().strip(),
        }
        if key not in self.struc_widgets:
            self.log_requested.emit(f"未知结构工具: {key}", "error")
            return

        w = self.struc_widgets[key]
        out = w["out"].text().strip()
        opt = w["opt"].text().strip()

        # pdb2gmx 需要力场，make_ndx 可选 ndx 输入
        md_ff = self._get_md_ff()
        ndx_inp_val = w.get("ndx_struc", None)
        if ndx_inp_val is not None:
            ndx_inp_val = ndx_inp_val.text().strip()

        result = build_structure_tool_command(
            key, gmx, files, out, opt, md_ff=md_ff, ndx_inp_val=ndx_inp_val
        )
        if result is None:
            self.log_requested.emit(f"未知结构工具: {key}", "error")
            return
        cmd, step_name = result
        self.run_requested.emit([cmd], wd, step_name)

    def set_running_state(self, running: bool):
        for w in self.struc_widgets.values():
            w["run_btn"].setEnabled(not running)

    def get_config(self) -> dict:
        cfg = {
            "struc_input": self.struc_input.text().strip(),
            "struc_index": self.struc_index.text().strip(),
            "tools": {}
        }
        for k, w in self.struc_widgets.items():
            cfg["tools"][k] = {
                "out": w["out"].text().strip(),
                "opt": w["opt"].text().strip()
            }
            if "ndx_struc" in w:
                cfg["tools"][k]["ndx_struc"] = w["ndx_struc"].text().strip()
            if "custom" in w:
                cfg["tools"][k]["custom"] = w["custom"].text().strip()
        return cfg

    def set_config(self, data: dict):
        if not isinstance(data, dict):
            return
        if "struc_input" in data:
            self.struc_input.setText(str(data["struc_input"]))
        if "struc_index" in data:
            self.struc_index.setText(str(data["struc_index"]))
        if "tools" in data and isinstance(data["tools"], dict):
            for k, tool_data in data["tools"].items():
                if k in self.struc_widgets and isinstance(tool_data, dict):
                    if "out" in tool_data:
                        self.struc_widgets[k]["out"].setText(str(tool_data["out"]))
                    if "opt" in tool_data:
                        self.struc_widgets[k]["opt"].setText(str(tool_data["opt"]))
                    if "ndx_struc" in tool_data and "ndx_struc" in self.struc_widgets[k]:
                        self.struc_widgets[k]["ndx_struc"].setText(str(tool_data["ndx_struc"]))
                    if "custom" in tool_data and "custom" in self.struc_widgets[k]:
                        self.struc_widgets[k]["custom"].setText(str(tool_data["custom"]))
