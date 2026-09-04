#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一次性拆分脚本：将 gromacs_gui_v4.py 按职责拆分为 gui/ 包
原则：只搬移，不改逻辑。每段原样切片，仅自动生成 import 头。
"""
import re
from pathlib import Path

SRC = Path(r"D:\YDW\Trae_Gromacs\source\gromacs_gui_v4.py")
OUT = SRC.parent

text = SRC.read_text(encoding="utf-8")
lines = text.split("\n")  # 0-based; 原文件行号 N 对应 lines[N-1]


def seg(a, b):
    """取 1-based 闭区间 [a,b]，去掉首尾空行"""
    chunk = lines[a - 1:b]
    while chunk and chunk[0].strip() == "":
        chunk.pop(0)
    while chunk and chunk[-1].strip() == "":
        chunk.pop()
    return "\n".join(chunk) + "\n"


# ---------------- 段定义 ----------------
SEGMENTS = {
    "setup_paths": seg(35, 47),     # _setup_runtime_paths + _IS_FROZEN
    "helpers": seg(69, 466),        # 版本配置/GMX检测/硬件检测（466=return info，勿截）
    "error_diagnosis": seg(469, 906),
    "embedded": seg(909, 1177),
    "gromacs_worker": seg(1180, 1432),
    "curve_widget": seg(1435, 1574),
    "data_extractor": seg(1577, 1746),
    "simulation_monitor": seg(1749, 1981),
    "help_dialog": seg(1984, 2251),
    "custom_template": seg(2254, 2464),
    "mdp_editor": seg(2467, 3645),
    "main_window": seg(3648, 13203),
    "entry_funcs": seg(13210, 13363),   # _get_config_path/_check_license/_setup_exc/_check_single
    "entry_main": seg(13366, 13405),    # __main__ 块内容
}

# help_dialog 段头部注释在原文件中误标为"自定义模板管理对话框"，修正之
SEGMENTS["help_dialog"] = SEGMENTS["help_dialog"].replace(
    "# 自定义模板管理对话框", "# 帮助对话框", 1)

# ---------------- 名字池与 import 语句 ----------------
STDLIB = ["sys", "os", "subprocess", "threading", "time", "platform", "json"]
# datetime 在原文件中为 from datetime import datetime
FROM_IMPORTS = {"datetime": "from datetime import datetime"}
CORE = ["ConfigManager", "AppLogger", "ErrorHandler", "ResourceMonitor",
        "GromacsService", "WorkflowEngine", "EventBus", "ReviewMechanism",
        "CorrectionMechanism", "AuditMechanism", "AutoUpdater",
        "VersionManager", "CrashHandler"]
QTW = ["QApplication", "QMainWindow", "QWidget", "QVBoxLayout", "QHBoxLayout",
       "QLabel", "QLineEdit", "QPushButton", "QTextEdit", "QGroupBox",
       "QComboBox", "QSpinBox", "QDoubleSpinBox", "QScrollArea", "QFileDialog",
       "QProgressBar", "QSplitter", "QTabWidget", "QGridLayout", "QMessageBox",
       "QCheckBox", "QTableWidget", "QTableWidgetItem", "QHeaderView", "QFrame",
       "QSizePolicy", "QPlainTextEdit", "QDialog", "QDialogButtonBox",
       "QToolButton", "QListWidget", "QFormLayout"]
QTC = ["Qt", "pyqtSignal", "QThread", "QTimer", "QSize", "QRect", "QPointF"]
QTG = ["QFont", "QIcon", "QColor", "QTextCharFormat", "QTextCursor",
       "QPalette", "QPainter", "QPen", "QBrush"]
HELPERS = ["_IS_FROZEN", "_get_app_root", "get_version_config", "VERSION_CONFIG",
           "_find_bundled_gmx", "GMX_EXE", "detect_cpu_cores",
           "detect_total_memory_gb", "detect_cpu_info",
           "get_performance_recommendations", "detect_all_gpus", "detect_gpu_info",
           "scan_gromacs_versions", "get_gromacs_version_info"]
CLASSES = {
    "ErrorDiagnoser": "gui.dialogs.error_diagnosis",
    "ErrorDiagnosisDialog": "gui.dialogs.error_diagnosis",
    "GromacsWorker": "gui.workers.gromacs_worker",
    "CurveWidget": "gui.widgets.curve_widget",
    "DataExtractorThread": "gui.workers.data_extractor",
    "SimulationMonitorDialog": "gui.dialogs.simulation_monitor",
    "HelpDialog": "gui.dialogs.help_dialog",
    "CustomTemplateDialog": "gui.dialogs.custom_template",
    "MdpEditorDialog": "gui.dialogs.mdp_editor",
    "GromacsGUI": "gui.main_window",
}
CONSTS = {"DELETE_SOLVENT_SCRIPT": "gui.embedded_scripts",
          "DELETE_ADDITIVE_SCRIPT": "gui.embedded_scripts"}


def used(body, names):
    return [n for n in names if re.search(r"\b" + re.escape(n) + r"\b", body)]


def multi_import(module, names, width=88):
    """生成 from X import (a, b, c)，超宽时换行"""
    one = "from %s import %s" % (module, ", ".join(names))
    if len(one) <= width:
        return one + "\n"
    out = "from %s import (\n" % module
    cur = "    "
    for i, n in enumerate(names):
        piece = n + ("," if i < len(names) - 1 else "")
        if len(cur) + len(piece) + 1 > width:
            out += cur.rstrip() + "\n"
            cur = "    "
        cur += piece + " "
    out += cur.rstrip() + "\n)\n"
    return out


def build_imports(body, skip=()):
    """按段内容自动生成 import 头（app_context 优先于 core，保证冻结模式路径初始化顺序）
    skip: 本模块自身定义的名字，不生成导入"""
    parts = []
    u_std = [n for n in used(body, STDLIB) if n not in skip]
    if "Path" not in skip and re.search(r"\bPath\b", body):
        u_std.append("PATH_MARKER")
    u_from = [n for n in used(body, list(FROM_IMPORTS)) if n not in skip]
    std_lines = []
    for n in u_std:
        std_lines.append("import %s" % n if n != "PATH_MARKER"
                         else "from pathlib import Path")
    for n in u_from:
        std_lines.append(FROM_IMPORTS[n])
    if std_lines:
        parts.append("\n".join(sorted(set(std_lines))))

    u_h = [n for n in used(body, HELPERS) if n not in skip]
    if u_h:
        parts.append(multi_import("gui.app_context", u_h))

    u_c = [n for n in used(body, CORE) if n not in skip]
    if u_c:
        parts.append(multi_import("core", u_c))

    u_qw = used(body, QTW)
    if u_qw:
        parts.append(multi_import("PyQt5.QtWidgets", u_qw))
    u_qc = used(body, QTC)
    if u_qc:
        parts.append(multi_import("PyQt5.QtCore", u_qc))
    u_qg = used(body, QTG)
    if u_qg:
        parts.append(multi_import("PyQt5.QtGui", u_qg))

    u_const = [n for n in used(body, list(CONSTS)) if n not in skip]
    if u_const:
        parts.append(multi_import("gui.embedded_scripts", u_const))

    u_cls = [n for n in used(body, list(CLASSES)) if n not in skip]
    if u_cls:
        by_mod = {}
        for c in u_cls:
            by_mod.setdefault(CLASSES[c], []).append(c)
        for mod in sorted(by_mod):
            parts.append(multi_import(mod, by_mod[mod]))

    return "\n\n".join(parts)


def write(rel, content):
    p = OUT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print("written:", rel, "(%d lines)" % content.count("\n"))


HEADER = '#!/usr/bin/env python3\n# -*- coding: utf-8 -*-\n'

# ---------------- 1. gui/app_context.py ----------------
app_ctx = HEADER + '"""\n应用上下文：运行时路径初始化、版本配置、GROMACS 检测、硬件检测\n"""\n\nimport sys\nimport os\nimport subprocess\nimport platform\nimport json\nfrom pathlib import Path\n\n' \
    + SEGMENTS["setup_paths"] + "\n\n" + SEGMENTS["helpers"]
write("gui/app_context.py", app_ctx)

# ---------------- 2. gui/embedded_scripts.py ----------------
emb = HEADER + '"""\n嵌入的独立命令行脚本（溶剂/添加剂删除）\n\n这两个脚本以字符串形式嵌入，运行时写出为独立 .py 文件执行。\n各自必须自包含（含各自的 import 与 gro 读写函数），不做共享导入。\n"""\n\n' + SEGMENTS["embedded"]
write("gui/embedded_scripts.py", emb)

# ---------------- 3. workers / widgets / dialogs ----------------
MODULES = [
    ("gui/workers/gromacs_worker.py", "gromacs_worker",
     "GROMACS 命令执行线程（GromacsWorker）", ["GromacsWorker"]),
    ("gui/widgets/curve_widget.py", "curve_widget",
     "自绘实时曲线控件（CurveWidget）", ["CurveWidget"]),
    ("gui/workers/data_extractor.py", "data_extractor",
     "数据提取线程（DataExtractorThread）", ["DataExtractorThread"]),
    ("gui/dialogs/error_diagnosis.py", "error_diagnosis",
     "错误诊断器与错误诊断对话框",
     ["ErrorDiagnoser", "ErrorDiagnosisDialog"]),
    ("gui/dialogs/simulation_monitor.py", "simulation_monitor",
     "实时模拟监控面板", ["SimulationMonitorDialog"]),
    ("gui/dialogs/help_dialog.py", "help_dialog",
     "帮助对话框", ["HelpDialog"]),
    ("gui/dialogs/custom_template.py", "custom_template",
     "自定义模板管理对话框", ["CustomTemplateDialog"]),
    ("gui/dialogs/mdp_editor.py", "mdp_editor",
     "高级 MDP 参数编辑器对话框", ["MdpEditorDialog"]),
    ("gui/main_window.py", "main_window",
     "主窗口（GromacsGUI）", ["GromacsGUI"]),
]
for rel, key, doc, defines in MODULES:
    body = SEGMENTS[key]
    write(rel, HEADER + '"""\n%s\n"""\n\n' % doc + build_imports(body, skip=defines)
          + "\n\n" + body)

# ---------------- 4. gui/app.py（入口逻辑） ----------------
entry_body = SEGMENTS["entry_funcs"] + "\n\n"
# __main__ 块包成 run_main() 函数（整体缩进 4 格，纯机械操作）
main_block = "\n".join(
    ("    " + l) if l.strip() else l
    for l in SEGMENTS["entry_main"].split("\n"))
entry_body += "def run_main():\n" + main_block + "\n\n\nif __name__ == \"__main__\":\n    run_main()\n"

all_entry = SEGMENTS["entry_funcs"] + "\n\n" + SEGMENTS["entry_main"]
imports = build_imports(all_entry)
write("gui/app.py", HEADER + '"""\n程序启动引导：使用协议、崩溃处理、单实例锁、主循环\n"""\n\n' + imports + "\n\n" + entry_body)

# ---------------- 5. 包 __init__ ----------------
write("gui/__init__.py", '"""GUI 层：主窗口、对话框、控件、工作线程"""\n')
write("gui/dialogs/__init__.py", '"""对话框模块"""\n')
write("gui/widgets/__init__.py", '"""自定义控件"""\n')
write("gui/workers/__init__.py", '"""后台工作线程"""\n')

# ---------------- 6. source/main.py（新入口） ----------------
write("main.py", HEADER + '"""GROMACS GUI 程序入口"""\n\nfrom gui.app import run_main\n\nif __name__ == "__main__":\n    run_main()\n')

# ---------------- 7. gromacs_gui_v4.py 兼容 shim ----------------
shim = HEADER + '"""兼容入口：代码已按职责拆分至 gui/ 包。\n\n保留此文件以兼容旧启动脚本与 PyInstaller 打包配置，\n新代码请使用 source/main.py 或从 gui 包导入。\n"""\n\n' \
    + multi_import("gui.app_context", HELPERS) \
    + multi_import("gui.embedded_scripts", list(CONSTS)) \
    + multi_import("gui.dialogs.error_diagnosis", ["ErrorDiagnoser", "ErrorDiagnosisDialog"]) \
    + multi_import("gui.workers.gromacs_worker", ["GromacsWorker"]) \
    + multi_import("gui.widgets.curve_widget", ["CurveWidget"]) \
    + multi_import("gui.workers.data_extractor", ["DataExtractorThread"]) \
    + multi_import("gui.dialogs.simulation_monitor", ["SimulationMonitorDialog"]) \
    + multi_import("gui.dialogs.help_dialog", ["HelpDialog"]) \
    + multi_import("gui.dialogs.custom_template", ["CustomTemplateDialog"]) \
    + multi_import("gui.dialogs.mdp_editor", ["MdpEditorDialog"]) \
    + multi_import("gui.main_window", ["GromacsGUI"]) \
    + 'from gui.app import run_main\n\nif __name__ == "__main__":\n    run_main()\n'
write("gromacs_gui_v4.py", shim)

print("\nDONE")
