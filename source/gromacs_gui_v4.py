#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""兼容入口：代码已按职责拆分至 gui/ 包。

保留此文件以兼容旧启动脚本与 PyInstaller 打包配置，
新代码请使用 source/main.py 或从 gui 包导入。
"""

from gui.app_context import (
    _IS_FROZEN, _get_app_root, get_version_config, VERSION_CONFIG, _find_bundled_gmx,
    GMX_EXE, detect_cpu_cores, detect_total_memory_gb, detect_cpu_info,
    get_performance_recommendations, detect_all_gpus, detect_gpu_info,
    scan_gromacs_versions, get_gromacs_version_info
)
from gui.embedded_scripts import DELETE_SOLVENT_SCRIPT, DELETE_ADDITIVE_SCRIPT
from gui.dialogs.error_diagnosis import ErrorDiagnoser, ErrorDiagnosisDialog
from gui.workers.gromacs_worker import GromacsWorker
from gui.widgets.curve_widget import CurveWidget
from gui.workers.data_extractor import DataExtractorThread
from gui.dialogs.simulation_monitor import SimulationMonitorDialog
from gui.dialogs.help_dialog import HelpDialog
from gui.dialogs.custom_template import CustomTemplateDialog
from gui.dialogs.mdp_editor import MdpEditorDialog
from gui.main_window import GromacsGUI
from gui.app import run_main

if __name__ == "__main__":
    run_main()
