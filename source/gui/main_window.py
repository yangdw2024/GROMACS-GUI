#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主窗口（GromacsGUI）
"""

from datetime import datetime
from pathlib import Path
import json
import os
import platform
import subprocess
import sys
import threading
import time

from gui.app_context import (
    _get_app_root, VERSION_CONFIG, GMX_EXE, get_performance_recommendations,
    get_gromacs_version_info
)
from gui.script_templates import get_script_template


from core import (
    ConfigManager, AppLogger, ErrorHandler, ResourceMonitor, GromacsService,
    WorkflowEngine, EventBus, ReviewMechanism, CorrectionMechanism, AuditMechanism,
    AutoUpdater, VersionManager, CrashHandler
)


from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QGroupBox, QComboBox, QSpinBox, QDoubleSpinBox,
    QScrollArea, QFileDialog, QProgressBar, QSplitter, QTabWidget, QGridLayout,
    QMessageBox, QCheckBox, QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
    QPlainTextEdit, QDialog, QDialogButtonBox, QListWidget
)


from PyQt5.QtCore import Qt


from PyQt5.QtGui import QFont, QIcon, QColor, QTextCharFormat, QTextCursor, QPalette


from gui.dialogs.custom_template import CustomTemplateDialog


from gui.dialogs.error_diagnosis import ErrorDiagnoser, ErrorDiagnosisDialog


from gui.dialogs.mdp_editor import MdpEditorDialog


from gui.dialogs.simulation_monitor import SimulationMonitorDialog
from gui.tabs.script_tab import ScriptTab
from gui.tabs.mmpbsa_tab import MmpbsaTab
from gui.tabs.trajectory_tab import TrajectoryTab
from gui.tabs.structure_tab import StructureTab
from gui.tabs.advanced_tab import AdvancedTab
from gui.tabs.analysis_tab import AnalysisTab
from gui.tabs.md_tab import MdTab


from gui.workers.gromacs_worker import GromacsWorker
from gui.themes import (
    DARK_TOKENS, LIGHT_TOKENS, get_theme_tokens, build_palette, build_shell_stylesheet
)
from gui.i18n import tr, set_language as i18n_set_language, get_language as i18n_get_language


# =============================================================================
# 主窗口
# =============================================================================
class GromacsGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # ========== 核心机制初始化 ==========
        self.config = ConfigManager()
        self.logger = AppLogger("GROMACS_GUI", log_file="gromacs_gui.log")
        self.error_handler = ErrorHandler()
        self.resource_monitor = ResourceMonitor()
        self.event_bus = EventBus()
        self.review_mechanism = ReviewMechanism()
        self.correction_mechanism = CorrectionMechanism()
        self.audit_mechanism = AuditMechanism()
        self.auto_updater = AutoUpdater()
        self.workflow_engine = WorkflowEngine()
        self.gromacs_service = GromacsService()
        self.version_manager = VersionManager()
        self.crash_handler = CrashHandler()
        
        # 安装全局崩溃捕获
        self.crash_handler.install()
        self.crash_handler.add_listener(self._on_crash_report)
        
        # 注册事件处理器
        self._register_event_handlers()
        
        # 记录审计事件
        self.audit_mechanism.log_event("system", "startup", "GROMACS GUI v4.3 启动")
        
        # ========== 系统资源检测 ==========
        self.sys_cpu_info = self.resource_monitor.get_cpu_info()
        self.sys_cpu_cores = self.sys_cpu_info["cores"]
        self.sys_memory_gb = self.resource_monitor.get_total_memory_gb()
        self.sys_gpu_info = self.resource_monitor.get_gpu_info()
        
        if not self.sys_gpu_info["available"]:
            os.environ["GMX_DISABLE_GPU_DETECTION"] = "1"
            os.environ["CUDA_VISIBLE_DEVICES"] = ""
            self.logger.info("未检测到NVIDIA GPU，已启用CPU兼容模式 (GMX_DISABLE_GPU_DETECTION=1)")
        
        # 使用新版VersionManager扫描版本（显示所有版本）
        self.logger.info("正在扫描GROMACS版本（显示所有版本）...")
        self.sys_gmx_versions = self.version_manager.scan_versions(
            filter_invalid=False, deduplicate=False
        )
        
        # 记录版本扫描结果
        version_summary = self.version_manager.get_version_summary()
        self.logger.info(
            f"版本扫描完成: 总计{version_summary['total']}个, "
            f"有效{version_summary['valid']}个, "
            f"重复{version_summary['duplicates']}个, "
            f"无效{version_summary['invalid']}个"
        )
        
        # 默认优先使用性能最优版本（GPU > SIMD级别 > 版本号）
        if self.sys_gmx_versions:
            best_key = self.version_manager.select_best_version()
            if best_key:
                version_info = self.sys_gmx_versions[best_key]
                self.gmx_path = version_info.gmx_exe
                self.gmx_version_label = best_key
                self.version_manager.select_version(best_key)
                self.logger.info(f"自动选择最佳版本: {best_key}")
            else:
                self.gmx_path = GMX_EXE
                self.gmx_version_label = "gromacs-2026.3-AVX512-CUDA-sm120-fixed"
        else:
            self.gmx_path = GMX_EXE
            self.gmx_version_label = "gromacs-2026.3-AVX512-CUDA-sm120-fixed"

        self.worker = None
        self.current_theme = "dark"
        
        # 错误诊断相关
        self._error_diagnoser = ErrorDiagnoser()
        self._recent_errors = []
        self._current_command = ""
        self._last_diagnoses = []
        
        # 性能建议缓存
        self._perf_recommendations = []

        # 检查更新
        self._check_for_updates()

        self.init_ui()
        self._setup_log_colors()
        self._log_system_info()
        self._load_persistent_config()
        # 全局前置预检：程序启动时检查关键配置
        self.global_pre_check("startup")
    
    def _register_event_handlers(self):
        """注册事件处理器"""
        self.event_bus.subscribe("simulation.*", self._on_simulation_event)
        self.event_bus.subscribe("system.*", self._on_system_event)
        self.event_bus.subscribe("error.*", self._on_error_event)
        self.event_bus.subscribe("audit.*", self._on_audit_event)
    
    def _on_simulation_event(self, event, data):
        """处理模拟事件"""
        if event == "simulation.started":
            self.audit_mechanism.log_simulation_event("start", data.get("task", "unknown"))
            self.logger.info(f"模拟任务开始: {data.get('task', 'unknown')}")
        elif event == "simulation.completed":
            self.audit_mechanism.log_simulation_event("complete", data.get("task", "unknown"))
            self.logger.info(f"模拟任务完成: {data.get('task', 'unknown')}")
        elif event == "simulation.failed":
            self.audit_mechanism.log_simulation_event("failed", data.get("task", "unknown"))
            self.logger.error(f"模拟任务失败: {data.get('task', 'unknown')}, 错误: {data.get('error', '')}")
    
    def _on_system_event(self, event, data):
        """处理系统事件"""
        if event == "system.config_changed":
            self.audit_mechanism.log_config_change(data.get("key", ""), 
                                                   data.get("old_value", ""), 
                                                   data.get("new_value", ""))
            self.logger.info(f"配置变更: {data.get('key', '')}")
    
    def _on_error_event(self, event, data):
        """处理错误事件"""
        error_info = self.error_handler.handle_error(data.get("exception"), 
                                                     data.get("context", {}))
        self._recent_errors.append(error_info)
        if error_info.get("severity") in ("high", "critical"):
            self.logger.error(f"严重错误: {error_info.get('message', '')}")
    
    def _on_audit_event(self, event, data):
        """处理审计事件"""
        self.audit_mechanism.log_event(data.get("category", "system"),
                                       data.get("action", "unknown"),
                                       data.get("detail", ""))

    def _on_crash_report(self, report):
        """处理崩溃报告 - 弹出前端提示框（无头测试环境自动降级为仅记录日志，避免模态阻塞）"""
        if os.environ.get("QT_QPA_PLATFORM") == "offscreen" or self.testAttribute(Qt.WA_DontShowOnScreen):
            self.logger.critical(f"无头模式未捕获异常 [{report.crash_id}]: {report.exception_type}: {report.exception_message}")
            return
        try:
            from PyQt5.QtWidgets import QMessageBox
            msg = QMessageBox(self)
            msg.setWindowTitle("程序异常")
            msg.setIcon(QMessageBox.Critical)
            msg.setText(f"程序遇到未处理的异常: {report.exception_type}")
            msg.setInformativeText(
                f"异常信息: {report.exception_message}\n\n"
                f"崩溃ID: {report.crash_id}\n"
                f"时间: {report.timestamp}\n\n"
                f"崩溃日志已保存到:\n{self.crash_handler._crash_dir / f'crash_{report.crash_id}.log'}"
            )
            msg.setDetailedText(report.traceback[:2000])
            
            export_btn = msg.addButton("导出崩溃日志", QMessageBox.ActionRole)
            ok_btn = msg.addButton("确定", QMessageBox.AcceptRole)
            msg.exec_()
            
            if msg.clickedButton() == export_btn:
                output_path = self.crash_handler.export_crash_log(report.crash_id)
                if output_path:
                    self.logger.info(f"崩溃日志已导出: {output_path}")
                    QMessageBox.information(self, "导出成功", f"崩溃日志已导出到:\n{output_path}")
        except Exception as e:
            self.logger.error(f"崩溃报告弹窗失败: {e}")

    def _switch_gmx_version(self, version_name):
        """切换GROMACS版本，带交互提示"""
        self.logger.info(f"正在切换版本: {version_name}")
        
        # 校验版本
        ok, msg = self.version_manager.select_version(version_name)
        if not ok:
            self.logger.warning(f"版本切换失败: {msg}")
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "版本切换失败", msg)
            return False
        
        meta = self.version_manager._versions.get(version_name)
        if meta:
            self.gmx_path = meta.gmx_exe
            self.gmx_version_label = version_name
            self.logger.info(
                f"版本切换成功: {version_name} | "
                f"SIMD: {meta.simd} | GPU: {meta.gpu} | PLUMED: {meta.plumed}"
            )
            
            # 更新状态栏
            self.statusBar().showMessage(
                f"当前版本: {version_name} | SIMD: {meta.simd} | GPU: {meta.gpu} | PLUMED: {meta.plumed}",
                5000
            )
            return True
        return False

    def _show_version_manager_dialog(self):
        """显示版本管理对话框"""
        try:
            from PyQt5.QtWidgets import (
                QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, 
                QTableWidgetItem, QPushButton, QLabel, QMessageBox,
                QHeaderView, QGroupBox
            )
            
            dialog = QDialog(self)
            dialog.setWindowTitle("GROMACS版本管理")
            dialog.setMinimumSize(800, 500)
            
            layout = QVBoxLayout(dialog)
            
            # 统计信息
            summary = self.version_manager.get_version_summary()
            info_label = QLabel(
                f"有效版本: {summary['valid']} | "
                f"重复版本: {summary['duplicates']} | "
                f"GPU支持: {summary['gpu_supported']} | "
                f"PLUMED支持: {summary['plumed_supported']}"
            )
            layout.addWidget(info_label)
            
            # 版本列表
            table = QTableWidget()
            table.setColumnCount(6)
            table.setHorizontalHeaderLabels([
                "版本名称", "SIMD", "GPU", "PLUMED", "大小(MB)", "状态"
            ])
            table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            
            versions = self.version_manager._versions
            table.setRowCount(len(versions))
            
            for i, (name, meta) in enumerate(sorted(versions.items())):
                table.setItem(i, 0, QTableWidgetItem(name))
                table.setItem(i, 1, QTableWidgetItem(meta.simd))
                table.setItem(i, 2, QTableWidgetItem(meta.gpu))
                table.setItem(i, 3, QTableWidgetItem(meta.plumed))
                table.setItem(i, 4, QTableWidgetItem(str(meta.size_mb)))
                
                status = "有效" if meta.valid else f"无效: {meta.validity_detail}"
                if meta.is_duplicate:
                    status = f"重复 ({meta.duplicate_of})"
                table.setItem(i, 5, QTableWidgetItem(status))
            
            layout.addWidget(table)
            
            # 按钮
            btn_layout = QHBoxLayout()
            
            refresh_btn = QPushButton("刷新列表")
            refresh_btn.clicked.connect(lambda: dialog.close() or self._show_version_manager_dialog())
            btn_layout.addWidget(refresh_btn)
            
            cleanup_btn = QPushButton("清理重复/无效版本")
            cleanup_btn.clicked.connect(lambda: self._cleanup_versions(dialog))
            btn_layout.addWidget(cleanup_btn)
            
            btn_layout.addStretch()
            
            close_btn = QPushButton("关闭")
            close_btn.clicked.connect(dialog.close)
            btn_layout.addWidget(close_btn)
            
            layout.addLayout(btn_layout)
            dialog.exec_()
        except Exception as e:
            self.logger.error(f"版本管理对话框错误: {e}")

    def _cleanup_versions(self, parent_dialog=None):
        """清理重复和无效版本"""
        try:
            from PyQt5.QtWidgets import QMessageBox
            
            duplicates = self.version_manager.get_duplicate_versions()
            invalid = self.version_manager.get_invalid_versions()
            
            if not duplicates and not invalid:
                QMessageBox.information(self, "清理版本", "没有需要清理的重复或无效版本")
                return
            
            msg = []
            if duplicates:
                msg.append(f"重复版本 ({len(duplicates)}个):\n" + "\n".join(f"  - {d}" for d in duplicates))
            if invalid:
                msg.append(f"\n无效版本 ({len(invalid)}个):\n" + "\n".join(f"  - {n}: {r}" for n, r in invalid))
            
            reply = QMessageBox.question(
                self, "清理版本",
                f"确认删除以下版本?\n\n{chr(10).join(msg)}\n\n此操作不可撤销!",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                deleted = 0
                for name in list(duplicates):
                    ok, _ = self.version_manager.delete_version(name)
                    if ok:
                        deleted += 1
                for name, _ in list(invalid):
                    if name in self.version_manager._versions:
                        ok, _ = self.version_manager.delete_version(name)
                        if ok:
                            deleted += 1
                
                QMessageBox.information(self, "清理完成", f"已删除 {deleted} 个版本")
                self.logger.info(f"版本清理完成: 删除 {deleted} 个版本")
                
                # 重新扫描（显示所有版本）
                self.sys_gmx_versions = self.version_manager.scan_versions(
                    filter_invalid=False, deduplicate=False
                )
                if parent_dialog:
                    parent_dialog.close()
                    self._show_version_manager_dialog()
        except Exception as e:
            self.logger.error(f"清理版本失败: {e}")
    
    def _check_for_updates(self):
        """检查更新"""
        try:
            result = self.auto_updater.check_for_update()
            if result["update_available"]:
                self.logger.info(f"发现新版本: {result['latest_version']}")
                self.audit_mechanism.log_event("system", "update_available", 
                                               f"新版本可用: {result['latest_version']}")
        except Exception as e:
            self.logger.warning(f"检查更新失败: {e}")
    
    def _init_log_file(self):
        self.logger.info("GROMACS GUI 启动日志")
        self.logger.info(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info(f"Python版本: {sys.version}")
        self.logger.info(f"操作系统: {platform.system()} {platform.release()}")

    def _select_best_gmx_version(self, versions_dict):
        """选择性能最优的GROMACS版本
        优先级: GPU > SIMD级别 > PLUMED > 版本号
        AVX-512相比AVX-256有30-50%性能提升，优先选择
        """
        import re
        
        def simd_score(simd_str):
            """给SIMD指令集打分，分数越高越好"""
            s = simd_str.lower()
            if 'avx_512' in s or 'avx512' in s:
                return 100
            elif 'avx2' in s or 'avx_256' in s:
                return 80
            elif 'avx' in s:
                return 60
            elif 'sse4' in s:
                return 40
            elif 'sse2' in s:
                return 20
            return 0
        
        def version_score(label):
            """给版本号打分"""
            m = re.search(r'(\d{4})\.(\d+)', label)
            if m:
                return (int(m.group(1)), int(m.group(2)))
            return (0, 0)
        
        best_label = None
        best_score = (-1, -1, -1, -1, -1)  # (gpu, simd, plumed, version_major, version_minor)
        
        for label, path in versions_dict.items():
            info = get_gromacs_version_info(path)
            
            gpu_score = 100 if info["gpu"].lower() in ("cuda", "opencl", "yes", "enabled") else 0
            simd = simd_score(info.get("simd", ""))
            plumed_score = 10 if info.get("plumed", "否").lower() in ("yes", "enabled", "是") else 0
            v_major, v_minor = version_score(label)
            
            total = (gpu_score, simd, plumed_score, v_major, v_minor)
            if total > best_score:
                best_score = total
                best_label = label
        
        return best_label if best_label else list(versions_dict.keys())[0]

    # -------------------------------------------------------------------------
    # UI 初始化
    # -------------------------------------------------------------------------
    def _get_icon_path(self):
        if getattr(sys, 'frozen', False):
            base = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
            icon_names = [
                'resources/app_icon.ico',
                'app_icon.ico',
            ]
            base2 = os.path.dirname(sys.executable)
            icon_names2 = [
                'resources/app_icon.ico',
                'app_icon.ico',
                '../resources/app_icon.ico',
            ]
            for name in icon_names:
                path = os.path.normpath(os.path.join(base, name))
                if os.path.isfile(path):
                    return path
            for name in icon_names2:
                path = os.path.normpath(os.path.join(base2, name))
                if os.path.isfile(path):
                    return path
        else:
            base = os.path.dirname(os.path.abspath(__file__))
            icon_names = [
                '../resources/app_icon.ico',
                'resources/app_icon.ico',
                'app_icon.ico',
                '../../resources/app_icon.ico',
            ]
            for name in icon_names:
                path = os.path.normpath(os.path.join(base, name))
                if os.path.isfile(path):
                    return path
        return None

    def init_ui(self):
        self.setWindowTitle(f"{VERSION_CONFIG['display_name']} {VERSION_CONFIG['full_version']}")
        self.setGeometry(50, 50, 1280, 820)
        self.setMinimumSize(880, 620)
        self.ui_layout_mode = "modern"
        self.console_expanded = True
        self._sys_drawer_expanded = False
        self.nav_buttons = []

        # 设置窗口图标
        icon_path = self._get_icon_path()
        if icon_path:
            app = QApplication.instance()
            app.setWindowIcon(QIcon(icon_path))
            self.setWindowIcon(QIcon(icon_path))

        # 全局字体设置 - 统一字体大小，提升可读性
        app = QApplication.instance()
        base_font = QFont("Microsoft YaHei UI", 10)
        base_font.setStyleStrategy(QFont.PreferAntialias)
        app.setFont(base_font)

        central = QWidget()
        central.setObjectName("rootWidget")
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 1. 顶部精简状态栏 + 可折叠系统配置抽屉
        self.create_top_bar(main_layout)

        # 2. 主体水平分栏：左侧垂直导航工作台 + 中央/底部工作区
        self.main_h_splitter = QSplitter(Qt.Horizontal)
        self.main_h_splitter.setHandleWidth(1)
        main_layout.addWidget(self.main_h_splitter, stretch=1)

        # 左侧导航工作台
        self.left_nav_rail = self._create_left_nav_rail()
        self.main_h_splitter.addWidget(self.left_nav_rail)

        # 中央工作区与底部日志终端容器
        self.center_right_splitter = QSplitter(Qt.Vertical)
        self.center_right_splitter.setHandleWidth(1)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(6, 6, 6, 6)
        self.tab_widget = QTabWidget()
        self.tab_widget.setObjectName("mainTabWidget")
        self.tab_widget.tabBar().setObjectName("mainTabBar")
        self.md_tab = self.create_md_tab()
        self.tab_widget.addTab(self.md_tab, "Part 1: MD模拟")
        self.struc_tab = self.create_structure_tab()
        self.tab_widget.addTab(self.struc_tab, "Part 2: 结构处理")
        self.advanced_tab = self.create_advanced_tab()
        self.tab_widget.addTab(self.advanced_tab, "Part 3: 高级模拟")
        self.traj_tab = self.create_trajectory_tab()
        self.tab_widget.addTab(self.traj_tab, "Part 4: 轨迹处理")
        self.analysis_tab = self.create_analysis_tab()
        self.tab_widget.addTab(self.analysis_tab, "Part 5: 结果分析")
        self.mmpbsa_tab = self.create_mmpbsa_tab()
        self.tab_widget.addTab(self.mmpbsa_tab, "Part 6: MMPBSA")
        self.script_tab = self.create_script_tab()
        self.tab_widget.addTab(self.script_tab, "Part 7: 自定义脚本")
        self.tab_widget.tabBar().setVisible(False)
        self.tab_widget.currentChanged.connect(self._sync_nav_selection)
        left_layout.addWidget(self.tab_widget)
        self.center_right_splitter.addWidget(left_panel)

        self.right_panel = self.create_right_panel()
        self.center_right_splitter.addWidget(self.right_panel)
        self.center_right_splitter.setStretchFactor(0, 7)
        self.center_right_splitter.setStretchFactor(1, 3)
        self.center_right_splitter.setSizes([540, 220])

        self.main_h_splitter.addWidget(self.center_right_splitter)
        self.main_h_splitter.setStretchFactor(0, 0)
        self.main_h_splitter.setStretchFactor(1, 1)
        self.main_h_splitter.setSizes([228, 1052])
        self.main_h_splitter.setCollapsible(0, False)

        # 默认应用现代化深色主题
        self._apply_dark_theme()
        self._adapt_responsive_topbar(self.width())
        self.statusBar().showMessage("就绪 (现代化工作台模式)")

    # -------------------------------------------------------------------------
    # 颜色亮度调整辅助方法
    # -------------------------------------------------------------------------
    def _adjust_brightness(self, hex_color, factor):
        hex_color = hex_color.lstrip('#')
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        r = min(255, max(0, int(r * factor)))
        g = min(255, max(0, int(g * factor)))
        b = min(255, max(0, int(b * factor)))
        return f"#{r:02x}{g:02x}{b:02x}"

    # -------------------------------------------------------------------------
    # 顶部简洁状态栏 + 可展开系统配置抽屉 + 左侧导航工作台
    # -------------------------------------------------------------------------
    def _format_ver_badge_text(self, compact: bool = False):
        label = getattr(self, "gmx_version_label", "GROMACS")
        import re
        m = re.search(r"20\d{2}\.\d+", label)
        ver = m.group(0) if m else label[:10]
        if compact:
            return f"GMX {ver}"
        simd = "AVX512" if "avx512" in label.lower() else ("AVX2" if "avx2" in label.lower() else "")
        return f"GMX {ver}" + (f" · {simd}" if simd else "")

    def _format_gpu_badge_text(self, compact: bool = False):
        if self.sys_gpu_info.get("available") and self.sys_gpu_info.get("names"):
            name = self.sys_gpu_info["names"][0].replace("NVIDIA GeForce ", "").replace("NVIDIA ", "")
            if compact:
                short_gpu = name.replace("RTX ", "").split()[0]
                return f"GPU: {short_gpu}"
            return f"GPU: {name}"
        return "CPU" if compact else f"CPU: {self.sys_cpu_cores} 核"

    def _toggle_sys_config_drawer(self):
        self._sys_drawer_expanded = not getattr(self, "_sys_drawer_expanded", False)
        if hasattr(self, "sys_config_drawer"):
            self.sys_config_drawer.setVisible(self._sys_drawer_expanded)

    def _adapt_responsive_topbar(self, width: int):
        """窗口宽度变化时自适应调整顶部栏元素紧凑度与更多菜单，杜绝按钮重叠与截断"""
        if not hasattr(self, "more_tools_btn"):
            return
        is_compact = (width < 1180)
        is_narrow = (width < 960)

        if hasattr(self, "lbl_workdir_title"):
            self.lbl_workdir_title.setVisible(not is_narrow)
        if hasattr(self, "path_edit"):
            self.path_edit.setMinimumWidth(120 if is_narrow else 200)
        if hasattr(self, "brand_sub_label"):
            self.brand_sub_label.setVisible(not is_narrow)

        if hasattr(self, "ver_badge_btn"):
            self.ver_badge_btn.setText(self._format_ver_badge_text(compact=is_compact))
            self.ver_badge_btn.adjustSize()

        if hasattr(self, "gpu_badge_btn"):
            self.gpu_badge_btn.setText(self._format_gpu_badge_text(compact=is_compact))
            self.gpu_badge_btn.adjustSize()

        # 低频操作按钮响应式显隐（窄屏收纳至更多菜单）
        show_direct_tools = not is_compact
        for w in [self.mdp_editor_btn, self.monitor_btn, self.save_config_btn, self.load_config_btn]:
            if w is not None:
                w.setVisible(show_direct_tools)

        # 在更多菜单中动态调整对应项说明
        if hasattr(self, "layout_mode_action"):
            mode_text = "切换为经典双栏视图" if getattr(self, "ui_layout_mode", "modern") == "modern" else "切换为现代化工作台"
            self.layout_mode_action.setText(mode_text)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._adapt_responsive_topbar(event.size().width())

    def create_top_bar(self, parent_layout):
        # 1. 顶部主控条 (Row 1: 品牌标识 + 核心运行控制与常用工具，杜绝与路径条争抢水平空间)
        header_frame = QFrame()
        header_frame.setObjectName("topHeaderBar")
        bar1 = QHBoxLayout(header_frame)
        bar1.setContentsMargins(12, 6, 12, 6)
        bar1.setSpacing(6)

        # 左侧: 品牌标识
        title_icon = QLabel("GMX")
        title_icon.setFixedSize(36, 26)
        title_icon.setAlignment(Qt.AlignCenter)
        title_icon.setStyleSheet("""
            QLabel {
                background-color: #2563EB;
                color: #FFFFFF;
                font-weight: bold;
                font-size: 8.5pt;
                border-radius: 5px;
            }
        """)

        brand_vbox = QVBoxLayout()
        brand_vbox.setSpacing(0)
        title_label = QLabel(f"{VERSION_CONFIG['product_name']} v{VERSION_CONFIG['version_string']}")
        title_label.setObjectName("brandTitle")
        self.brand_sub_label = QLabel(VERSION_CONFIG["display_name"])
        self.brand_sub_label.setObjectName("brandSubtitle")
        brand_vbox.addWidget(title_label)
        brand_vbox.addWidget(self.brand_sub_label)

        bar1.addWidget(title_icon)
        bar1.addLayout(brand_vbox)
        bar1.addStretch(1)

        # 右侧: 核心高频操作按钮
        self.run_all_btn = QPushButton("▶ 一键运行")
        self.run_all_btn.setProperty("role", "primaryRun")
        self.run_all_btn.clicked.connect(self.run_all_md)
        self.run_all_btn.setToolTip("一键执行完整的分子动力学模拟流程")

        self.stop_btn = QPushButton("■ 停止")
        self.stop_btn.setProperty("role", "dangerStop")
        self.stop_btn.clicked.connect(self.stop_run)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setToolTip("停止当前正在运行的任务")

        # 宽屏直接展示的辅助工具按钮（窄屏自动隐藏并收纳于更多菜单）
        self.mdp_editor_btn = QPushButton("MDP编辑")
        self.mdp_editor_btn.setProperty("role", "secondaryTool")
        self.mdp_editor_btn.clicked.connect(self.open_mdp_editor)
        self.mdp_editor_btn.setToolTip("打开高级MDP参数可视化编辑器")

        self.monitor_btn = QPushButton("监控")
        self.monitor_btn.setProperty("role", "secondaryTool")
        self.monitor_btn.clicked.connect(self.open_monitor)
        self.monitor_btn.setToolTip("打开实时模拟监控面板（温度/压力/能量曲线）")

        self.save_config_btn = QPushButton("保存")
        self.save_config_btn.setProperty("role", "secondaryTool")
        self.save_config_btn.clicked.connect(self.save_config)
        self.save_config_btn.setToolTip("保存当前所有配置参数到JSON文件")

        self.load_config_btn = QPushButton("加载")
        self.load_config_btn.setProperty("role", "secondaryTool")
        self.load_config_btn.clicked.connect(self.load_config)
        self.load_config_btn.setToolTip("从JSON文件加载配置参数")

        self.theme_btn = QPushButton("☀️ 浅色")
        self.theme_btn.setProperty("role", "secondaryTool")
        self.theme_btn.clicked.connect(self.toggle_theme)
        self.theme_btn.setToolTip("切换深色/浅色主题")

        # “更多操作 ▾” 菜单按钮（保证任何分辨率和缩放下一键访问全部工具）
        from PyQt5.QtWidgets import QMenu, QToolButton
        self.more_tools_btn = QToolButton()
        self.more_tools_btn.setText("更多 ▾")
        self.more_tools_btn.setProperty("role", "secondaryTool")
        self.more_tools_btn.setPopupMode(QToolButton.InstantPopup)
        self.more_tools_btn.setToolTip("查看更多工具、配置及系统操作")

        self.more_tools_menu = QMenu(self)
        self.more_tools_menu.addAction("⚙ 高级 MDP 参数编辑器", self.open_mdp_editor)
        self.more_tools_menu.addAction("📈 实时曲线监控面板", self.open_monitor)
        self.more_tools_menu.addSeparator()
        self.more_tools_menu.addAction("💾 保存当前配置到 JSON", self.save_config)
        self.more_tools_menu.addAction("📂 从 JSON 加载配置", self.load_config)
        self.more_tools_menu.addSeparator()
        self.layout_mode_action = self.more_tools_menu.addAction("🔄 切换为经典双栏视图", self.toggle_layout_mode)
        self.more_tools_menu.addSeparator()
        self.more_tools_menu.addAction("🧹 系统缓存清理", self._on_system_cleanup)
        self.more_tools_menu.addAction("📁 打开分级日志目录", self._on_open_log_dir)
        self.more_tools_menu.addAction("ℹ 查看版本与系统信息", self.show_version)
        self.more_tools_btn.setMenu(self.more_tools_menu)

        self.layout_mode_btn = QPushButton("经典布局")
        self.layout_mode_btn.setProperty("role", "secondaryTool")
        self.layout_mode_btn.setToolTip("在现代化左导航工作台与经典双栏视图之间切换")
        self.layout_mode_btn.clicked.connect(self.toggle_layout_mode)

        self.lang_btn = QPushButton(tr("lang_switch_btn"))
        self.lang_btn.setProperty("role", "secondaryTool")
        self.lang_btn.setToolTip(tr("lang_tooltip"))
        self.lang_btn.clicked.connect(self.toggle_language)

        bar1.addWidget(self.run_all_btn)
        bar1.addWidget(self.stop_btn)
        bar1.addWidget(self.mdp_editor_btn)
        bar1.addWidget(self.monitor_btn)
        bar1.addWidget(self.save_config_btn)
        bar1.addWidget(self.load_config_btn)
        bar1.addWidget(self.more_tools_btn)
        bar1.addWidget(self.theme_btn)
        bar1.addWidget(self.layout_mode_btn)
        bar1.addWidget(self.lang_btn)

        parent_layout.addWidget(header_frame)

        # 2. 工作区路径与环境硬件胶囊条 (Row 2: 充裕路径展示 + 自适应计算环境胶囊)
        workdir_frame = QFrame()
        workdir_frame.setObjectName("workdirBar")
        bar2 = QHBoxLayout(workdir_frame)
        bar2.setContentsMargins(12, 5, 12, 5)
        bar2.setSpacing(8)

        self.lbl_workdir_title = QLabel("工作目录:")
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("请选择或输入模拟工作目录路径...")
        self.path_edit.setMinimumWidth(140)
        self.browse_btn = QPushButton("浏览...")
        self.browse_btn.setProperty("role", "secondaryTool")
        self.browse_btn.clicked.connect(self.browse_directory)

        self.ver_badge_btn = QPushButton(self._format_ver_badge_text())
        self.ver_badge_btn.setProperty("role", "envBadge")
        self.ver_badge_btn.setToolTip("点击展开/收起 GROMACS 版本、CPU 线程与 GPU 加速配置")
        self.ver_badge_btn.clicked.connect(self._toggle_sys_config_drawer)

        self.gpu_badge_btn = QPushButton(self._format_gpu_badge_text())
        self.gpu_badge_btn.setProperty("role", "gpuBadge")
        self.gpu_badge_btn.setToolTip("点击展开/收起硬件资源与 GPU 加速配置")
        self.gpu_badge_btn.clicked.connect(self._toggle_sys_config_drawer)

        bar2.addWidget(self.lbl_workdir_title)
        bar2.addWidget(self.path_edit, stretch=1)
        bar2.addWidget(self.browse_btn)
        bar2.addSpacing(8)
        bar2.addWidget(self.ver_badge_btn)
        bar2.addWidget(self.gpu_badge_btn)

        parent_layout.addWidget(workdir_frame)

        # 2. 可展开的系统与硬件配置抽屉（双行紧凑排版，880px 宽度下亦零重叠）
        self.sys_config_drawer = QFrame()
        self.sys_config_drawer.setObjectName("sysConfigDrawer")
        sys_config_vbox = QVBoxLayout(self.sys_config_drawer)
        sys_config_vbox.setContentsMargins(12, 6, 12, 6)
        sys_config_vbox.setSpacing(6)

        # Row A: GROMACS 内核版本与工具
        ver_row = QHBoxLayout()
        ver_row.setSpacing(6)

        self.ver_combo = QComboBox()
        default_idx = 0
        if self.sys_gmx_versions:
            for idx, label in enumerate(sorted(self.sys_gmx_versions.keys())):
                meta = self.sys_gmx_versions[label]
                self.ver_combo.addItem(label, meta.gmx_exe)
                if label == self.gmx_version_label:
                    default_idx = idx
        else:
            self.ver_combo.addItem(self.gmx_version_label, self.gmx_path)
        self.ver_combo.setCurrentIndex(default_idx)
        self.ver_combo.currentIndexChanged.connect(self._on_version_changed)
        self.ver_combo.setMinimumWidth(180)

        self.gmx_browse_btn = QPushButton("浏览...")
        self.gmx_browse_btn.setProperty("role", "secondaryTool")
        self.gmx_browse_btn.setToolTip("手动选择GROMACS的gmx.exe文件位置")
        self.gmx_browse_btn.clicked.connect(self._browse_gmx_exe)

        self.show_all_versions_cb = QCheckBox("显示全部版本")
        self.show_all_versions_cb.setChecked(True)
        self.show_all_versions_cb.stateChanged.connect(self._on_show_all_versions_changed)

        self.version_mgmt_btn = QPushButton("版本管理")
        self.version_mgmt_btn.setProperty("role", "secondaryTool")
        self.version_mgmt_btn.clicked.connect(self._on_version_management)

        self.open_update_pkg_btn = QPushButton("更新包")
        self.open_update_pkg_btn.setProperty("role", "secondaryTool")
        self.open_update_pkg_btn.clicked.connect(self._on_open_update_packages)

        ver_row.addWidget(QLabel("内核版本:"))
        ver_row.addWidget(self.ver_combo, stretch=1)
        ver_row.addWidget(self.gmx_browse_btn)
        ver_row.addWidget(self.show_all_versions_cb)
        ver_row.addWidget(self.version_mgmt_btn)
        ver_row.addWidget(self.open_update_pkg_btn)
        sys_config_vbox.addLayout(ver_row)

        # Row B: CPU 线程、内存上限与 GPU 加速
        res_row = QHBoxLayout()
        res_row.setSpacing(6)
        self.cfg_nt = QSpinBox()
        safe_cores = min(8, self.sys_cpu_cores)
        self.cfg_nt.setRange(1, self.sys_cpu_cores)
        self.cfg_nt.setValue(safe_cores)
        self.cfg_nt.setSuffix(" 核")
        self.cfg_mem_label = QLabel(f"总内存:{self.sys_memory_gb}G")
        self.cfg_mem_limit = QCheckBox("内存限制")
        self.cfg_mem_limit.setChecked(False)
        self.cfg_mem_value = QDoubleSpinBox()
        mem_default = min(8.0, float(self.sys_memory_gb))
        self.cfg_mem_value.setRange(0.5, float(self.sys_memory_gb))
        self.cfg_mem_value.setSuffix(" GB")
        self.cfg_mem_value.setValue(mem_default)
        self.cfg_mem_value.setSingleStep(0.5)
        self.cfg_mem_value.setDecimals(1)
        self.cfg_mem_value.setEnabled(False)
        self.cfg_mem_limit.toggled.connect(self.cfg_mem_value.setEnabled)

        res_row.addWidget(QLabel("线程(-nt):"))
        res_row.addWidget(self.cfg_nt)
        res_row.addWidget(self.cfg_mem_label)
        res_row.addWidget(self.cfg_mem_limit)
        res_row.addWidget(self.cfg_mem_value)
        res_row.addSpacing(8)

        self.cfg_gpu = QCheckBox("启用GPU")
        if self.sys_gpu_info["available"]:
            self.cfg_gpu.setChecked(True)
        else:
            self.cfg_gpu.setChecked(False)
            self.cfg_gpu.setEnabled(False)
        res_row.addWidget(self.cfg_gpu)

        self.cfg_gpu_id = QComboBox()
        self.cfg_gpu_id.setEnabled(False)
        if self.sys_gpu_info["available"]:
            for i, name in enumerate(self.sys_gpu_info["names"]):
                self.cfg_gpu_id.addItem(f"GPU {i}: {name}", i)
            self.cfg_gpu_id.setEnabled(True)
        res_row.addWidget(QLabel("ID:"))
        res_row.addWidget(self.cfg_gpu_id, stretch=1)

        self.cfg_gpu_auto = QCheckBox("自动")
        self.cfg_gpu_auto.setChecked(True)
        res_row.addWidget(self.cfg_gpu_auto)

        self.gpu_diagnose_btn = QPushButton("GPU诊断")
        self.gpu_diagnose_btn.setProperty("role", "secondaryTool")
        self.gpu_diagnose_btn.clicked.connect(self._on_gpu_diagnose)
        res_row.addWidget(self.gpu_diagnose_btn)

        sys_config_vbox.addLayout(res_row)

        self.sys_config_drawer.setVisible(False)
        parent_layout.addWidget(self.sys_config_drawer)

    def _create_left_nav_rail(self):
        """创建左侧垂直导航工作台（完整映射原有七大功能模块与系统工具）"""
        rail = QFrame()
        rail.setObjectName("leftNavRail")
        rail.setMinimumWidth(220)
        vbox = QVBoxLayout(rail)
        vbox.setContentsMargins(10, 12, 10, 10)
        vbox.setSpacing(4)

        nav_groups = [
            ("nav_group_md", [
                (0, "nav_part1", "全流程分子动力学、SA溶剂蒸发及退火模拟"),
                (1, "nav_part2", "生成拓扑、盒子编辑、索引制作与结构校验"),
                (2, "nav_part3", "伞形采样、WHAM、元动力学与 ABF 增强采样"),
            ]),
            ("nav_group_ana", [
                (3, "nav_part4", "PBC修复、居中拟合流水线及常规轨迹工具"),
                (4, "nav_part5", "热力学、结构稳定性、片段RDF及科研出图"),
                (5, "nav_part6", "基于 gmx_MMPBSA 的结合自由能计算"),
            ]),
            ("nav_group_script", [
                (6, "nav_part7", "PowerShell / Batch / Shell 自定义批处理脚本"),
            ]),
        ]

        self.nav_buttons = []
        self.nav_section_labels = []
        for group_key, items in nav_groups:
            sec_lbl = QLabel(tr(group_key))
            sec_lbl.setProperty("role", "navSectionHeader")
            vbox.addWidget(sec_lbl)
            self.nav_section_labels.append((group_key, sec_lbl))
            for tab_idx, text_key, tip in items:
                btn = QPushButton(tr(text_key))
                btn.setProperty("role", "navItem")
                btn.setProperty("i18n_key", text_key)
                btn.setProperty("active", "true" if tab_idx == 0 else "false")
                btn.setToolTip(tip)
                btn.setCursor(Qt.PointingHandCursor)
                btn.clicked.connect(lambda checked=False, idx=tab_idx: self._on_nav_item_clicked(idx))
                vbox.addWidget(btn)
                self.nav_buttons.append((tab_idx, btn))
            vbox.addSpacing(4)

        vbox.addStretch(1)

        # 底部系统维护快捷入口（收纳原顶栏低频按钮）
        self.sys_sec_lbl = QLabel(tr("nav_group_sys"))
        self.sys_sec_lbl.setProperty("role", "navSectionHeader")
        vbox.addWidget(self.sys_sec_lbl)

        self.cleanup_btn = QPushButton("系统清理")
        self.cleanup_btn.setProperty("role", "secondaryTool")
        self.cleanup_btn.clicked.connect(self._on_system_cleanup)
        self.cleanup_btn.setToolTip("一键清理缓存、日志和废弃临时文件")

        self.log_btn = QPushButton("日志目录")
        self.log_btn.setProperty("role", "secondaryTool")
        self.log_btn.clicked.connect(self._on_open_log_dir)
        self.log_btn.setToolTip("打开分级日志目录")

        self.version_btn = QPushButton("版本与系统信息")
        self.version_btn.setProperty("role", "secondaryTool")
        self.version_btn.clicked.connect(self.show_version)
        self.version_btn.setToolTip("查看软件版本和系统信息")

        vbox.addWidget(self.cleanup_btn)
        vbox.addWidget(self.log_btn)
        vbox.addWidget(self.version_btn)
        return rail

    def _on_nav_item_clicked(self, tab_idx: int):
        if hasattr(self, "tab_widget") and 0 <= tab_idx < self.tab_widget.count():
            self.tab_widget.setCurrentIndex(tab_idx)
        self._sync_nav_selection(tab_idx)

    def _sync_nav_selection(self, active_idx: int):
        for idx, btn in getattr(self, "nav_buttons", []):
            is_active = (idx == active_idx)
            btn.setProperty("active", "true" if is_active else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def toggle_layout_mode(self):
        """在现代化左导航布局与经典顶部 Tab 布局之间切换（回退机制）"""
        if getattr(self, "ui_layout_mode", "modern") == "modern":
            self.ui_layout_mode = "classic"
            self.left_nav_rail.setVisible(False)
            self.sys_config_drawer.setVisible(True)
            self.tab_widget.tabBar().setVisible(True)
            self.center_right_splitter.setOrientation(Qt.Horizontal)
            w = max(900, self.width())
            self.center_right_splitter.setSizes([int(w * 0.65), int(w * 0.35)])
            self.layout_mode_btn.setText("现代布局")
            self.statusBar().showMessage("已切换至经典布局模式（顶部标签页 + 右侧日志栏）")
        else:
            self.ui_layout_mode = "modern"
            self.left_nav_rail.setVisible(True)
            self.sys_config_drawer.setVisible(self._sys_drawer_expanded)
            self.tab_widget.tabBar().setVisible(False)
            self.center_right_splitter.setOrientation(Qt.Vertical)
            if getattr(self, "console_expanded", True):
                self.center_right_splitter.setSizes([540, 220])
            else:
                self.center_right_splitter.setSizes([720, 38])
            self.layout_mode_btn.setText("经典布局")
            self.statusBar().showMessage("已切换至现代化工作台模式（左导航 + 底部可折叠终端）")

    # -------------------------------------------------------------------------
    # Part 1: 分子动力学模拟
    # -------------------------------------------------------------------------
    def create_md_tab(self):
        tab = MdTab(
            get_work_dir=self._get_work_dir,
            get_gmx_path=lambda: self.gmx_path,
            get_mdrun_extra=lambda is_em=False: self._get_mdrun_extra(is_em=is_em),
            get_sys_cpu_cores=lambda: self.sys_cpu_cores,
            get_sys_gpu_info=lambda: self.sys_gpu_info,
            open_mdp_editor=self.open_mdp_editor,
            parent=self
        )
        tab.run_requested.connect(self.run_command)
        tab.log_requested.connect(self.add_log)

        # 属性别名绑定，保持 100% 向后兼容
        self.md_ff = tab.md_ff
        self.md_water = tab.md_water
        self.md_box_type = tab.md_box_type
        self.md_box_size_mode = tab.md_box_size_mode
        self.md_box_size = tab.md_box_size
        self.md_box_a = tab.md_box_a
        self.md_box_x = tab.md_box_x
        self.md_box_y = tab.md_box_y
        self.md_box_z = tab.md_box_z
        self.md_angle_alpha = tab.md_angle_alpha
        self.md_angle_beta = tab.md_angle_beta
        self.md_angle_gamma = tab.md_angle_gamma
        self.md_princ = tab.md_princ
        self.md_ion_conc = tab.md_ion_conc
        self.md_temp = tab.md_temp
        self.md_pressure = tab.md_pressure
        self.md_dt = tab.md_dt
        self.md_nsteps = tab.md_nsteps
        self.md_engine = tab.md_engine
        self.md_nt = tab.md_nt
        self.md_pdb = tab.md_pdb
        self.lbl_ff = tab.lbl_ff
        self.lbl_water = tab.lbl_water
        self.lbl_box_type = tab.lbl_box_type
        self.lbl_box_size = tab.lbl_box_size
        self.lbl_box_a = tab.lbl_box_a
        self.lbl_box_x = tab.lbl_box_x
        self.lbl_box_y = tab.lbl_box_y
        self.lbl_box_z = tab.lbl_box_z
        self.lbl_angle_alpha = tab.lbl_angle_alpha
        self.lbl_angle_beta = tab.lbl_angle_beta
        self.lbl_angle_gamma = tab.lbl_angle_gamma
        self.lbl_ion = tab.lbl_ion
        self.lbl_pdb = tab.lbl_pdb
        self.use_existing_top = tab.use_existing_top
        self.skip_solvate = tab.skip_solvate
        self.skip_genion = tab.skip_genion
        self.skip_editconf = tab.skip_editconf
        self.md_step_btns = tab.md_step_btns
        self.step1_widget = tab.step1_widget
        self.step1_existing = tab.step1_existing
        self.se_gro_edit = tab.se_gro_edit
        self.se_top_edit = tab.se_top_edit
        self.se_run_btn = tab.se_run_btn
        self.evap_mode = tab.evap_mode
        self.evap_gro_edit = tab.evap_gro_edit
        self.evap_top_edit = tab.evap_top_edit
        self.evap_mdp_edit = tab.evap_mdp_edit
        self.evap_resname = tab.evap_resname
        self.evap_atoms_per_mol = tab.evap_atoms_per_mol
        self.evap_source = tab.evap_source
        self.evap_label_delete = tab.evap_label_delete
        self.evap_delete_num = tab.evap_delete_num
        self.evap_label_loops = tab.evap_label_loops
        self.evap_loops = tab.evap_loops
        self.evap_prefix = tab.evap_prefix
        self.evap_restart_check = tab.evap_restart_check
        self.evap_start_loop_label = tab.evap_start_loop_label
        self.evap_start_loop = tab.evap_start_loop
        self.evap_run_btn = tab.evap_run_btn
        self.anneal_gro_edit = tab.anneal_gro_edit
        self.anneal_top_edit = tab.anneal_top_edit
        self.anneal_prefix = tab.anneal_prefix
        self.anneal_mode = tab.anneal_mode
        self.anneal_table = tab.anneal_table
        self.anneal_run_btn = tab.anneal_run_btn
        return tab

    # -------------------------------------------------------------------------
    # Part 3: 高级模拟 (已委托至 gui.tabs.advanced_tab.AdvancedTab)
    # -------------------------------------------------------------------------
    def create_advanced_tab(self):
        tab = AdvancedTab(
            get_work_dir=self._get_work_dir,
            get_gmx_path=lambda: self.gmx_path,
            get_mdrun_extra=lambda: self._get_mdrun_extra(),
            parent=self
        )
        tab.run_requested.connect(self.run_command)
        tab.log_requested.connect(self.add_log)

        # 属性别名绑定
        self.umb_tpr = tab.umb_tpr
        self.umb_xtc = tab.umb_xtc
        self.umb_pull_coord = tab.umb_pull_coord
        self.umb_pull_group1 = tab.umb_pull_group1
        self.umb_pull_group2 = tab.umb_pull_group2
        self.umb_pull_force = tab.umb_pull_force
        self.umb_pull_start = tab.umb_pull_start
        self.umb_pull_end = tab.umb_pull_end
        self.umb_pull_nwindows = tab.umb_pull_nwindows
        self.umb_run_btn = tab.umb_run_btn

        self.wham_files = tab.wham_files
        self.wham_temp = tab.wham_temp
        self.wham_out = tab.wham_out
        self.wham_run_btn = tab.wham_run_btn

        self.meta_tpr = tab.meta_tpr
        self.meta_plumed = tab.meta_plumed
        self.meta_biasfactor = tab.meta_biasfactor
        self.meta_height = tab.meta_height
        self.meta_sigma = tab.meta_sigma
        self.meta_gen_btn = tab.meta_gen_btn
        self.meta_run_btn = tab.meta_run_btn

        self.abf_tpr = tab.abf_tpr
        self.abf_plumed = tab.abf_plumed
        self.abf_min = tab.abf_min
        self.abf_max = tab.abf_max
        self.abf_nbins = tab.abf_nbins
        self.abf_gen_btn = tab.abf_gen_btn
        return tab

    # -------------------------------------------------------------------------
    # Part 5: 结果分析与可视化 (已委托至 gui.tabs.analysis_tab.AnalysisTab)
    # -------------------------------------------------------------------------
    def create_analysis_tab(self):
        tab = AnalysisTab(
            get_work_dir=self._get_work_dir,
            get_gmx_path=lambda: self.gmx_path,
            parent=self
        )
        tab.run_requested.connect(self.run_command)
        tab.log_requested.connect(self.add_log)

        # 属性别名绑定
        self.ana_input_xtc = tab.ana_input_xtc
        self.ana_input_tpr = tab.ana_input_tpr
        self.ana_input_gro = tab.ana_input_gro
        self.ana_input_edr = tab.ana_input_edr
        self.ana_index = tab.ana_index
        self.ana_b = tab.ana_b
        self.ana_e = tab.ana_e
        self.ana_dt = tab.ana_dt
        self.analysis_widgets = tab.analysis_widgets
        self.file_check_btn = tab.file_check_btn
        self.file_status_btn = tab.file_status_btn
        self.ndx_gen_type = tab.ndx_gen_type
        self.ndx_gen_nmol = tab.ndx_gen_nmol
        self.ndx_gen_natom = tab.ndx_gen_natom
        self.ndx_gen_offset = tab.ndx_gen_offset
        self.ndx_gen_table = tab.ndx_gen_table
        self.ndx_gen_output = tab.ndx_gen_output
        self.ndx_add_row_btn = tab.ndx_add_row_btn
        self.ndx_del_row_btn = tab.ndx_del_row_btn
        self.ndx_clear_btn = tab.ndx_clear_btn
        self.ndx_load_def_btn = tab.ndx_load_def_btn
        self.ndx_gen_btn = tab.ndx_gen_btn
        self.rdf_frag_ndx_input = tab.rdf_frag_ndx_input
        self.rdf_frag_ref = tab.rdf_frag_ref
        self.rdf_frag_sel = tab.rdf_frag_sel
        self.rdf_frag_seltype = tab.rdf_frag_seltype
        self.rdf_frag_bin = tab.rdf_frag_bin
        self.rdf_frag_b = tab.rdf_frag_b
        self.rdf_frag_e = tab.rdf_frag_e
        self.rdf_frag_outdir = tab.rdf_frag_outdir
        self.rdf_frag_run_btn = tab.rdf_frag_run_btn
        self.pairdist_ref = tab.pairdist_ref
        self.pairdist_sel = tab.pairdist_sel
        self.pairdist_type = tab.pairdist_type
        self.pairdist_out = tab.pairdist_out
        self.pairdist_run_btn = tab.pairdist_run_btn
        self.plot_input = tab.plot_input
        self.plot_type = tab.plot_type
        self.plot_xlabel = tab.plot_xlabel
        self.plot_ylabel = tab.plot_ylabel
        self.plot_title = tab.plot_title
        self.plot_output = tab.plot_output
        self.plot_dpi = tab.plot_dpi
        self.plot_run_btn = tab.plot_run_btn
        self.ed_terms = tab.ed_terms
        self.ed_output = tab.ed_output
        self.ed_range = tab.ed_range
        self.ed_run_btn = tab.ed_run_btn
        self.batch_table = tab.batch_table
        self.batch_flow = tab.batch_flow
        self.batch_add_btn = tab.batch_add_btn
        self.batch_del_btn = tab.batch_del_btn
        self.batch_clear_btn = tab.batch_clear_btn
        self.batch_load_dir_btn = tab.batch_load_dir_btn
        self.batch_run_btn = tab.batch_run_btn
        return tab

    def _run_file_check(self):
        if hasattr(self, "analysis_tab"):
            self.analysis_tab.run_file_check()

    def _check_file_status(self):
        if hasattr(self, "analysis_tab"):
            self.analysis_tab.check_file_status()

    def _run_batch_processing(self):
        if hasattr(self, "analysis_tab"):
            self.analysis_tab.run_batch_processing()

    def _run_energy_decomposition(self):
        if hasattr(self, "analysis_tab"):
            self.analysis_tab.run_energy_decomposition()

    def _generate_fragment_ndx(self):
        if hasattr(self, "analysis_tab"):
            self.analysis_tab.generate_fragment_ndx()

    def _expand_ranges(self, rangestr):
        if hasattr(self, "analysis_tab"):
            return self.analysis_tab._expand_ranges(rangestr)
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

    def _run_fragment_rdf_batch(self):
        if hasattr(self, "analysis_tab"):
            self.analysis_tab.run_fragment_rdf_batch()

    def _run_pairdist_analysis(self):
        if hasattr(self, "analysis_tab"):
            self.analysis_tab.run_pairdist_analysis()

    def _generate_plot(self):
        if hasattr(self, "analysis_tab"):
            self.analysis_tab.generate_plot()

    # -------------------------------------------------------------------------
    # Part 4: 轨迹处理工具 (已委托至 gui.tabs.trajectory_tab.TrajectoryTab)
    # -------------------------------------------------------------------------
    def create_trajectory_tab(self):
        tab = TrajectoryTab(
            get_work_dir=self._get_work_dir,
            get_gmx_path=lambda: self.gmx_path,
            parent=self
        )
        tab.run_requested.connect(self.run_command)
        tab.log_requested.connect(self.add_log)

        # 属性别名绑定，保证原有代码与测试 100% 兼容
        self.traj_input = tab.traj_input
        self.traj_tpr = tab.traj_tpr
        self.traj_index = tab.traj_index
        self.prep_pbc = tab.prep_pbc
        self.prep_center = tab.prep_center
        self.prep_fit = tab.prep_fit
        self.prep_fit_ref = tab.prep_fit_ref
        self.prep_b = tab.prep_b
        self.prep_e = tab.prep_e
        self.prep_dt = tab.prep_dt
        self.prep_output = tab.prep_output
        self.prep_run_btn = tab.prep_run_btn
        self.traj_widgets = tab.traj_widgets
        return tab

    # -------------------------------------------------------------------------
    # Part 2: 结构处理工具 (已委托至 gui.tabs.structure_tab.StructureTab)
    # -------------------------------------------------------------------------
    def create_structure_tab(self):
        tab = StructureTab(
            get_work_dir=self._get_work_dir,
            get_gmx_path=lambda: self.gmx_path,
            get_md_ff=lambda: self.md_ff.currentText() if hasattr(self, "md_ff") else "",
            parent=self
        )
        tab.run_requested.connect(self.run_command)
        tab.log_requested.connect(self.add_log)

        # 属性别名绑定，保证原有代码与测试 100% 兼容
        self.struc_input = tab.struc_input
        self.struc_index = tab.struc_index
        self.struc_widgets = tab.struc_widgets
        return tab

    # -------------------------------------------------------------------------
    # Part 6: MMPBSA (已委托至 gui.tabs.mmpbsa_tab.MmpbsaTab)
    # -------------------------------------------------------------------------
    def create_mmpbsa_tab(self):
        tab = MmpbsaTab(
            get_work_dir=self._get_work_dir,
            parent=self
        )
        tab.run_requested.connect(self.run_command)
        tab.log_requested.connect(self.add_log)

        # 暴露原有属性别名，保持 100% 向后兼容
        self.mmpbsa_tpr = tab.mmpbsa_tpr
        self.mmpbsa_xtc = tab.mmpbsa_xtc
        self.mmpbsa_index = tab.mmpbsa_index
        self.mmpbsa_top = tab.mmpbsa_top
        self.mmpbsa_start = tab.mmpbsa_start
        self.mmpbsa_end = tab.mmpbsa_end
        self.mmpbsa_interval = tab.mmpbsa_interval
        self.mmpbsa_nt = tab.mmpbsa_nt
        self.mmpbsa_fmt = tab.mmpbsa_fmt
        self.mmpbsa_width = tab.mmpbsa_width
        self.mmpbsa_height = tab.mmpbsa_height
        self.mmpbsa_run_btn = tab.mmpbsa_run_btn
        return tab

    # -------------------------------------------------------------------------
    # 底部可折叠运行日志与进度终端 (兼容经典右侧面板模式)
    # -------------------------------------------------------------------------
    def create_right_panel(self):
        panel = QFrame()
        panel.setObjectName("bottomConsoleDrawer")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QFrame()
        header.setObjectName("consoleHeaderBar")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 4, 12, 4)
        header_layout.setSpacing(8)

        self.console_title_lbl = QLabel(tr("terminal_title"))
        self.console_title_lbl.setStyleSheet("font-weight: bold;")
        header_layout.addWidget(self.console_title_lbl)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setMinimumWidth(90)
        self.progress_bar.setMaximumHeight(18)
        header_layout.addWidget(self.progress_bar)

        header_layout.addStretch(1)

        self.diagnosis_btn = QPushButton("诊断")
        self.diagnosis_btn.setProperty("role", "secondaryTool")
        self.diagnosis_btn.clicked.connect(self.show_error_diagnosis)
        self.diagnosis_btn.setToolTip("查看最近错误的诊断结果和修复建议")

        self.clear_log_btn = QPushButton("清空")
        self.clear_log_btn.setProperty("role", "secondaryTool")
        self.clear_log_btn.clicked.connect(self.clear_log)

        self.export_log_btn = QPushButton("导出")
        self.export_log_btn.setProperty("role", "secondaryTool")
        self.export_log_btn.clicked.connect(self.export_log)

        self.toggle_console_btn = QPushButton("▼ 折叠")
        self.toggle_console_btn.setProperty("role", "secondaryTool")
        self.toggle_console_btn.setToolTip("折叠或展开底部日志视口，释放中央工作区面积")
        self.toggle_console_btn.clicked.connect(self.toggle_console_drawer)

        header_layout.addWidget(self.diagnosis_btn)
        header_layout.addWidget(self.clear_log_btn)
        header_layout.addWidget(self.export_log_btn)
        header_layout.addWidget(self.toggle_console_btn)
        layout.addWidget(header)

        self.log_text = QTextEdit()
        self.log_text.setObjectName("consoleLogView")
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 10))
        self.log_text.setLineWrapMode(QTextEdit.WidgetWidth)
        layout.addWidget(self.log_text, stretch=1)
        # 默认折叠日志终端时进度条在顶头始终可见，未运行时初始隐藏
        self.progress_bar.setVisible(False)
        return panel

    def toggle_console_drawer(self):
        self.console_expanded = not getattr(self, "console_expanded", True)
        self.log_text.setVisible(self.console_expanded)
        if hasattr(self, "toggle_console_btn"):
            self.toggle_console_btn.setText(
                tr("expand_btn") if not self.console_expanded else tr("collapse_btn")
            )
        if hasattr(self, "center_right_splitter") and getattr(self, "ui_layout_mode", "modern") == "modern":
            total_h = max(400, self.center_right_splitter.height())
            if self.console_expanded:
                self.center_right_splitter.setSizes([int(total_h * 0.7), int(total_h * 0.3)])
            else:
                self.center_right_splitter.setSizes([total_h - 36, 36])

    def _setup_log_colors(self):
        self._color_info = QColor("#4FC3F7")
        self._color_success = QColor("#69F0AE")
        self._color_warning = QColor("#FFB74D")
        self._color_error = QColor("#EF5350")
        self._color_cmd = QColor("#CE93D8")
        self._color_default = QColor("#E0E0E0")

    def toggle_language(self):
        new_lang = "en" if i18n_get_language() == "zh" else "zh"
        self.set_language(new_lang)

    def set_language(self, lang: str):
        active_lang = i18n_set_language(lang)
        self.current_lang = active_lang
        self.retranslate_ui(active_lang)

    def retranslate_ui(self, lang: str):
        # 1. 顶部操作栏
        self.brand_sub_label.setText(tr("brand_subtitle", lang=lang))
        self.run_all_btn.setText(tr("run_all", lang=lang))
        self.stop_btn.setText(tr("stop", lang=lang))
        self.mdp_editor_btn.setText(tr("mdp_editor", lang=lang))
        self.monitor_btn.setText(tr("monitor", lang=lang))
        self.save_config_btn.setText(tr("save", lang=lang))
        self.load_config_btn.setText(tr("load", lang=lang))
        self.more_tools_btn.setText(tr("more", lang=lang))
        if getattr(self, "current_theme", "dark") == "dark":
            self.theme_btn.setText(tr("theme_to_light", lang=lang))
        else:
            self.theme_btn.setText(tr("theme_to_dark", lang=lang))
        if getattr(self, "ui_layout_mode", "modern") == "modern":
            self.layout_mode_btn.setText(tr("layout_to_classic", lang=lang))
        else:
            self.layout_mode_btn.setText(tr("layout_to_modern", lang=lang))
        self.lang_btn.setText(tr("lang_switch_btn", lang=lang))
        self.lang_btn.setToolTip(tr("lang_tooltip", lang=lang))

        self.lbl_workdir_title.setText(tr("workdir_label", lang=lang))
        self.path_edit.setPlaceholderText(tr("workdir_placeholder", lang=lang))
        self.browse_btn.setText(tr("browse", lang=lang))

        # 2. 硬件配置抽屉
        self.gmx_browse_btn.setText(tr("browse", lang=lang))
        self.show_all_versions_cb.setText(tr("show_all_versions", lang=lang))
        self.version_mgmt_btn.setText(tr("version_mgmt", lang=lang))
        self.open_update_pkg_btn.setText(tr("update_pkg", lang=lang))
        self.cfg_mem_limit.setText(tr("mem_limit", lang=lang))
        self.cfg_gpu.setText(tr("enable_gpu", lang=lang))
        self.cfg_gpu_auto.setText(tr("auto_mode", lang=lang))
        self.gpu_diagnose_btn.setText(tr("gpu_diag", lang=lang))

        # 3. 左侧导航与系统工具
        for group_key, sec_lbl in getattr(self, "nav_section_labels", []):
            sec_lbl.setText(tr(group_key, lang=lang))
        for tab_idx, btn in getattr(self, "nav_buttons", []):
            key = btn.property("i18n_key")
            if key:
                btn.setText(tr(key, lang=lang))
            if hasattr(self, "tab_widget") and 0 <= tab_idx < self.tab_widget.count():
                self.tab_widget.setTabText(tab_idx, tr(key, lang=lang).replace(" · ", ": "))

        if hasattr(self, "sys_sec_lbl"):
            self.sys_sec_lbl.setText(tr("nav_group_sys", lang=lang))
        self.cleanup_btn.setText(tr("sys_cleanup", lang=lang))
        self.log_btn.setText(tr("log_dir", lang=lang))
        self.version_btn.setText(tr("about_ver", lang=lang))

        # 4. 底部控制台与状态栏
        if hasattr(self, "console_title_lbl"):
            self.console_title_lbl.setText(tr("terminal_title", lang=lang))
        self.diagnosis_btn.setText(tr("diag_btn", lang=lang))
        self.clear_log_btn.setText(tr("clear_btn", lang=lang))
        self.export_log_btn.setText(tr("export_btn", lang=lang))
        if hasattr(self, "toggle_console_btn"):
            self.toggle_console_btn.setText(
                tr("collapse_btn", lang=lang) if getattr(self, "console_expanded", True) else tr("expand_btn", lang=lang)
            )
        if getattr(self, "ui_layout_mode", "modern") == "modern":
            self.statusBar().showMessage(tr("status_ready_modern", lang=lang))
        else:
            self.statusBar().showMessage(tr("status_ready_classic", lang=lang))

        # 5. 全部七大页面组件级联翻译
        for tab_attr in ["md_tab", "struc_tab", "advanced_tab", "traj_tab", "analysis_tab", "mmpbsa_tab", "script_tab"]:
            tab_obj = getattr(self, tab_attr, None)
            if tab_obj and hasattr(tab_obj, "retranslate_ui"):
                tab_obj.retranslate_ui(lang)

        self._adapt_responsive_topbar(self.width())

    def toggle_theme(self):
        if self.current_theme == "dark":
            self._apply_light_theme()
        else:
            self._apply_dark_theme()

    def _apply_dark_theme(self):
        self.current_theme = "dark"
        self.theme_btn.setText(tr("theme_to_light"))
        tokens = get_theme_tokens("dark")
        app = QApplication.instance()
        app.setPalette(build_palette(tokens))
        app.setStyleSheet(build_shell_stylesheet(tokens))
        self._update_groupbox_styles_dark()

    def _apply_light_theme(self):
        self.current_theme = "light"
        self.theme_btn.setText(tr("theme_to_dark"))
        tokens = get_theme_tokens("light")
        app = QApplication.instance()
        app.setPalette(build_palette(tokens))
        app.setStyleSheet(build_shell_stylesheet(tokens))
        self._update_groupbox_styles_light()

    def _update_groupbox_styles_dark(self):
        self._repolish_all()

    def _update_groupbox_styles_light(self):
        self._repolish_all()

    def _repolish_all(self):
        app = QApplication.instance()
        if app:
            style = app.style()
            for w in self.findChildren(QGroupBox) + self.findChildren(QLabel) + self.findChildren(QPushButton):
                style.unpolish(w)
                style.polish(w)

    def _log_system_info(self):
        """启动时在日志中记录系统信息"""
        self.add_log("=" * 60, "cmd")
        self.add_log("系统配置检测完成", "success")
        self.add_log(f"  CPU:       {self.sys_cpu_info['name']}", "info")
        self.add_log(f"  CPU核心数: {self.sys_cpu_cores} 核", "info")
        self.add_log(f"  系统内存:  {self.sys_memory_gb} GB", "info")
        
        simd_support = self.sys_cpu_info.get("simd_support", [])
        if simd_support:
            self.add_log(f"  CPU指令集: {', '.join(simd_support).upper()}", "info")
        if self.sys_cpu_info.get("avx512"):
            self.add_log("  AVX-512:   支持 ✅", "success")
        elif self.sys_cpu_info.get("avx2"):
            self.add_log("  AVX2:      支持 ✅", "success")

        all_gpus = self.sys_gpu_info.get("all_gpus", [])
        if all_gpus:
            self.add_log("  所有显卡:", "info")
            for i, gpu in enumerate(all_gpus):
                mem = gpu.get("memory", "未知")
                name = gpu.get("name", "未知")
                self.add_log(f"    显卡 {i+1}: {name} ({mem})", "info")

        if self.sys_gpu_info["available"]:
            self.add_log("  NVIDIA GPU (可用于GROMACS加速):", "success")
            for i, name in enumerate(self.sys_gpu_info["names"]):
                mem = self.sys_gpu_info["memories"][i] if i < len(self.sys_gpu_info["memories"]) else "未知"
                self.add_log(f"    GPU {self.sys_gpu_info['ids'][i]}: {name} ({mem})", "success")
            self.add_log(f"  CUDA:      {self.sys_gpu_info['cuda_version']}", "info")
        else:
            self.add_log("  NVIDIA GPU: 未检测到（GROMACS无法使用GPU加速）", "warning")

        self.add_log(f"  GROMACS版本: {self.gmx_version_label}", "info")
        if os.path.isfile(self.gmx_path):
            ginfo = get_gromacs_version_info(self.gmx_path)
            self.add_log(f"    版本号:   {ginfo['version']}", "info")
            self.add_log(f"    GPU支持:  {ginfo['gpu']}", "info")
            self.add_log(f"    PLUMED:   {ginfo['plumed']}", "info")
            self.add_log(f"    SIMD:     {ginfo['simd']}", "info")
            self.add_log(f"    精度:     {ginfo['precision']}", "info")
            self.add_log(f"    OpenMP:   {ginfo['openmp']}", "info")
            
            self._perf_recommendations = get_performance_recommendations(
                self.sys_cpu_info, ginfo, self.sys_gpu_info
            )
            if self._perf_recommendations:
                self.add_log("", "info")
                self.add_log("  🚀 性能优化建议:", "warning")
                for i, rec in enumerate(self._perf_recommendations):
                    level_icon = "🔴" if rec["level"] == "high" else "🟡" if rec["level"] == "medium" else "🔵"
                    self.add_log(f"    {level_icon} {i+1}. {rec['title']}", "warning")
                    self.add_log(f"       {rec['description']}", "info")
                    for j, sug in enumerate(rec["suggestions"]):
                        self.add_log(f"       建议{j+1}: {sug}", "info")
        else:
            self.add_log(f"    路径: {self.gmx_path}", "warning")
            self.add_log("    ⚠ 未找到GROMACS可执行文件！", "error")
            self.add_log("    请点击\"浏览...\"按钮手动选择gmx.exe文件位置", "warning")
        self.add_log("=" * 60, "cmd")

    def _load_persistent_config(self):
        """从app_config加载持久化配置到UI控件"""
        try:
            # 加载内存限制
            mem_enabled = self.config.get("simulation.mem_limit_enabled", False)
            mem_value = self.config.get("simulation.mem_limit_gb", 8.0)
            self.cfg_mem_limit.setChecked(mem_enabled)
            # 限制在有效范围内
            max_mem = float(self.sys_memory_gb)
            mem_value = max(0.5, min(mem_value, max_mem))
            self.cfg_mem_value.setValue(mem_value)
            self.cfg_mem_value.setEnabled(mem_enabled)

            # 加载GPU设置
            gpu_enabled = self.config.get("simulation.use_gpu", False)
            if self.sys_gpu_info["available"]:
                self.cfg_gpu.setChecked(gpu_enabled)
                gpu_id = self.config.get("simulation.gpu_id", 0)
                if gpu_id < self.cfg_gpu_id.count():
                    self.cfg_gpu_id.setCurrentIndex(gpu_id)
            else:
                self.cfg_gpu.setChecked(False)
                self.cfg_gpu.setEnabled(False)
                self.cfg_gpu_id.setEnabled(False)

            # 加载线程数
            nt = self.config.get("simulation.nt", 6)
            self.cfg_nt.setValue(nt)

            # 加载工作目录
            work_dir = self.config.get("system.work_dir", "")
            if work_dir and os.path.isdir(work_dir):
                self.path_edit.setText(work_dir)

            self.add_log("持久化配置已加载", "info")
        except Exception as e:
            self.add_log(f"加载持久化配置失败: {e}", "warning")

    def _save_persistent_config(self):
        """保存UI控件当前值到app_config"""
        try:
            self.config.set("simulation.mem_limit_enabled", self.cfg_mem_limit.isChecked(), auto_save=False)
            self.config.set("simulation.mem_limit_gb", self.cfg_mem_value.value(), auto_save=False)
            self.config.set("simulation.use_gpu", self.cfg_gpu.isChecked(), auto_save=False)
            self.config.set("simulation.gpu_id", self.cfg_gpu_id.currentIndex(), auto_save=False)
            self.config.set("simulation.nt", self.cfg_nt.value(), auto_save=False)
            self.config.set("system.work_dir", self.path_edit.text().strip(), auto_save=False)
            self.config._save()
        except Exception:
            pass

    def closeEvent(self, event):
        """窗口关闭时保存持久化配置"""
        self._save_persistent_config()
        super().closeEvent(event)

    def global_pre_check(self, check_type: str = "run") -> bool:
        """全局前置预检：在关键操作前检查所有风险项

        Args:
            check_type: 'run'=模拟运行前, 'version'=版本切换前, 'startup'=程序启动时

        Returns:
            True=全部通过, False=有阻断性问题
        """
        issues = []

        if check_type in ("run", "startup"):
            # 1. GROMACS版本完整性校验
            gmx_path = self.gmx_path
            if not gmx_path or not os.path.isfile(gmx_path):
                issues.append(f"GROMACS可执行文件不存在: {gmx_path}")
            elif os.path.getsize(gmx_path) < 1024:
                issues.append(f"GROMACS可执行文件异常（文件过小）: {gmx_path}")

            # 2. 工作目录读写权限（仅在运行前检查，启动时不强制要求）
            if check_type == "run":
                work_dir = self._get_work_dir()
                if work_dir and os.path.isdir(work_dir):
                    test_file = os.path.join(work_dir, ".gromacs_gui_write_test")
                    try:
                        with open(test_file, "w") as f:
                            f.write("test")
                        os.remove(test_file)
                    except (PermissionError, OSError):
                        issues.append(f"工作目录无写入权限: {work_dir}")
                elif work_dir:
                    issues.append(f"工作目录不存在: {work_dir}")

        if check_type == "run":
            # 3. 内存参数合法性
            mem_limit = self.cfg_mem_value.value()
            if mem_limit < 0.5:
                issues.append(f"内存限制值异常: {mem_limit} GB（最小0.5 GB）")
            if mem_limit > float(self.sys_memory_gb):
                issues.append(f"内存限制({mem_limit} GB)超过系统物理内存({self.sys_memory_gb} GB)")

            # 4. 线程数合法性
            nt = self.cfg_nt.value()
            if nt < 1:
                issues.append(f"线程数异常: {nt}（最小1）")

            # 5. 版本有效性
            version_name = self.ver_combo.currentText()
            if version_name in self.sys_gmx_versions:
                meta = self.sys_gmx_versions[version_name]
                if not meta.valid:
                    issues.append(f"当前版本无效: {version_name} - {getattr(meta, 'validity_detail', '未知原因')}")

        if check_type == "version":
            # 版本切换前检查
            gmx_path = self.gmx_path
            if gmx_path and os.path.isfile(gmx_path) and os.path.getsize(gmx_path) < 1024:
                issues.append(f"目标版本可执行文件异常: {gmx_path}")

        if issues:
            # 启动时只记录日志，不弹窗拦截（让用户可以继续使用程序）
            if check_type == "startup":
                self.add_log(f"[启动提示] 检测到 {len(issues)} 个待配置项（不影响程序启动）", "warning")
                for issue in issues:
                    self.add_log(f"  - {issue}", "warning")
                return True
            # 运行前/版本切换前弹窗拦截
            msg = "预检发现以下问题，操作已拦截：\n\n"
            for i, issue in enumerate(issues, 1):
                msg += f"{i}. {issue}\n"
            msg += "\n请修正后再试。"
            self.add_log(f"[预检拦截] {check_type}: {len(issues)}个问题", "error")
            QMessageBox.warning(self, "前置预检拦截", msg)
            return False

        return True

    def _on_open_log_dir(self):
        """打开日志目录，区分ERROR日志和全量日志"""
        import subprocess
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QDialogButtonBox

        log_dir = _get_app_root() / "source" / "logs"
        if not log_dir.exists():
            log_dir = _get_app_root() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        dlg = QDialog(self)
        dlg.setWindowTitle("打开日志目录")
        dlg.setMinimumWidth(320)
        layout = QVBoxLayout(dlg)

        layout.addWidget(QLabel("选择要打开的日志目录："))

        btn_layout = QHBoxLayout()

        def _open_error():
            # ERROR日志目录
            subprocess.run(["explorer", "/select,", str(log_dir)], check=False)
            self.add_log(f"已打开ERROR日志目录: {log_dir}", "info")

        def _open_all():
            subprocess.run(["explorer", str(log_dir)], check=False)
            self.add_log(f"已打开全量日志目录: {log_dir}", "info")

        error_btn = QPushButton("ERROR日志目录")
        error_btn.setToolTip("ERROR日志永久保留\n用于定位崩溃和严重问题")
        error_btn.clicked.connect(_open_error)

        all_btn = QPushButton("全量日志目录")
        all_btn.setToolTip("包含所有级别的日志文件\nINFO/DEBUG/WARNING按天数自动清理")
        all_btn.clicked.connect(_open_all)

        btn_layout.addWidget(error_btn)
        btn_layout.addWidget(all_btn)
        layout.addLayout(btn_layout)

        close_box = QDialogButtonBox(QDialogButtonBox.Close)
        close_box.rejected.connect(dlg.reject)
        layout.addWidget(close_box)

        dlg.exec_()

    def _on_open_update_packages(self):
        """打开更新包目录并支持拖拽导入更新"""
        import subprocess
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, \
            QDialogButtonBox, QListWidget, QListWidgetItem, QFileDialog, QMessageBox
        from PyQt5.QtCore import Qt

        # 更新包目录
        pkg_dir = _get_app_root() / "config" / "update_packages"
        pkg_dir.mkdir(parents=True, exist_ok=True)

        dlg = QDialog(self)
        dlg.setWindowTitle("更新包管理")
        dlg.setMinimumSize(550, 400)
        dlg.setAcceptDrops(True)
        layout = QVBoxLayout(dlg)

        layout.addWidget(QLabel("更新包目录: " + str(pkg_dir)))

        # 现有更新包列表
        pkg_list = QListWidget()
        zip_files = list(pkg_dir.glob("*.zip"))
        for z in sorted(zip_files, key=lambda p: p.stat().st_mtime, reverse=True):
            size_mb = z.stat().st_size / (1024 * 1024)
            item = QListWidgetItem(f"{z.name}  ({size_mb:.1f} MB)")
            item.setData(0x100, str(z))
            pkg_list.addItem(item)
        layout.addWidget(pkg_list)

        # 按钮行
        btn_layout = QHBoxLayout()
        open_dir_btn = QPushButton("打开目录")
        apply_btn = QPushButton("应用选中更新")
        generate_btn = QPushButton("生成更新包")

        def _open_dir():
            subprocess.run(["explorer", str(pkg_dir)], check=False)

        def _apply_selected():
            selected = pkg_list.currentItem()
            if not selected:
                QMessageBox.warning(dlg, "提示", "请先选择一个更新包")
                return
            zip_path = selected.data(0x100)
            # 调用auto_updater进行更新
            try:
                success = self.auto_updater.download_update(zip_path)
                if success:
                    QMessageBox.information(self, "更新成功", "更新已应用，请重启程序")
                else:
                    QMessageBox.warning(self, "更新失败", "更新包应用失败，请检查日志")
            except Exception as e:
                QMessageBox.warning(self, "更新失败", f"应用更新包失败: {e}")

        def _generate_package():
            from PyQt5.QtWidgets import QInputDialog
            old_manifest = _get_app_root() / "config" / "backup" / "latest_manifest.json"
            # 尝试找最新的manifest
            backup_dir = _get_app_root() / "config" / "backup"
            manifests = sorted(backup_dir.rglob("manifest.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            old_manifest_path = str(manifests[0].parent) if manifests else None

            pkg_path, pkg_size, info = self.auto_updater.generate_update_package(
                old_manifest_path=old_manifest_path
            )
            if pkg_path:
                # 刷新列表
                pkg_list.clear()
                for z in sorted(pkg_dir.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True):
                    size_mb = z.stat().st_size / (1024 * 1024)
                    item = QListWidgetItem(f"{z.name}  ({size_mb:.1f} MB)")
                    item.setData(0x100, str(z))
                    pkg_list.addItem(item)
                QMessageBox.information(dlg, "生成成功",
                    f"更新包已生成\n类型: {info['type']}\n大小: {pkg_size/1024:.1f} KB\n缩减: {info['size_reduction_pct']}%")
            else:
                QMessageBox.warning(dlg, "生成失败", info.get("error", "未知错误"))

        open_dir_btn.clicked.connect(_open_dir)
        apply_btn.clicked.connect(_apply_selected)
        generate_btn.clicked.connect(_generate_package)
        btn_layout.addWidget(open_dir_btn)
        btn_layout.addWidget(apply_btn)
        btn_layout.addWidget(generate_btn)
        layout.addLayout(btn_layout)

        # 关闭按钮
        close_box = QDialogButtonBox(QDialogButtonBox.Close)
        close_box.rejected.connect(dlg.reject)
        layout.addWidget(close_box)

        dlg.exec_()

    def _on_version_management(self):
        """版本管理对话框：批量导入/导出GROMACS版本"""
        from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget,
                                      QListWidgetItem, QPushButton, QFileDialog,
                                      QDialogButtonBox, QGroupBox, QLabel, QProgressBar)
        from PyQt5.QtCore import Qt
        import threading

        dlg = QDialog(self)
        dlg.setWindowTitle("版本管理 - 导入/导出")
        dlg.setMinimumSize(550, 480)
        layout = QVBoxLayout(dlg)

        # 版本列表标题行
        header_layout = QHBoxLayout()
        list_label = QLabel("当前已扫描的GROMACS版本：")
        header_layout.addWidget(list_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        ver_list = QListWidget()
        for name, meta in sorted(self.sys_gmx_versions.items()):
            item = QListWidgetItem(f"{name}  ({meta.size_mb:.0f} MB, {'有效' if meta.valid else '无效'})")
            item.setData(0x100, name)  # 存储版本名
            item.setCheckState(Qt.Unchecked)  # 复选框默认未勾选
            ver_list.addItem(item)
        layout.addWidget(ver_list)

        # 全选/清空按钮行
        select_layout = QHBoxLayout()
        select_all_btn = QPushButton("全选")
        clear_all_btn = QPushButton("清空勾选")
        def _select_all():
            for i in range(ver_list.count()):
                ver_list.item(i).setCheckState(Qt.Checked)
        def _clear_all():
            for i in range(ver_list.count()):
                ver_list.item(i).setCheckState(Qt.Unchecked)
        select_all_btn.clicked.connect(_select_all)
        clear_all_btn.clicked.connect(_clear_all)
        select_layout.addWidget(select_all_btn)
        select_layout.addWidget(clear_all_btn)
        select_layout.addStretch()
        layout.addLayout(select_layout)

        # 操作按钮行
        btn_layout = QHBoxLayout()

        export_btn = QPushButton("导出勾选版本")
        export_btn.setToolTip("将勾选的版本打包为ZIP压缩包导出到指定目录")
        import_btn = QPushButton("导入版本")
        import_btn.setToolTip("从外部ZIP压缩包导入GROMACS版本")
        refresh_btn = QPushButton("刷新列表")

        # 进度条
        progress = QProgressBar()
        progress.setVisible(False)

        def _do_export():
            # 获取所有勾选的版本
            checked_names = []
            for i in range(ver_list.count()):
                item = ver_list.item(i)
                if item.checkState() == Qt.Checked:
                    checked_names.append(item.data(0x100))
            if not checked_names:
                QMessageBox.warning(dlg, "提示", "请至少勾选1个版本进行导出")
                return
            export_dir = QFileDialog.getExistingDirectory(dlg, "选择导出目录")
            if not export_dir:
                return
            progress.setVisible(True)
            progress.setRange(0, len(checked_names))
            progress.setValue(0)
            export_btn.setEnabled(False)
            import_btn.setEnabled(False)

            def _export_thread():
                exported, errors = self.version_manager.export_versions(checked_names, export_dir)
                from PyQt5.QtCore import QMetaObject
                QMetaObject.invokeMethod(dlg, "accept", Qt.QueuedConnection)
                result_msg = f"导出完成: 成功 {exported}/{len(checked_names)} 个"
                if errors:
                    result_msg += "\n\n问题:\n" + "\n".join(errors)
                QMessageBox.information(self, "导出结果", result_msg)

            t = threading.Thread(target=_export_thread, daemon=True)
            t.start()

        def _do_import():
            zip_files, _ = QFileDialog.getOpenFileNames(
                dlg, "选择GROMACS版本压缩包", "", "ZIP文件 (*.zip)"
            )
            if not zip_files:
                return
            progress.setVisible(True)
            progress.setRange(0, len(zip_files))
            progress.setValue(0)
            export_btn.setEnabled(False)
            import_btn.setEnabled(False)

            def _import_thread():
                imported, conflicts = self.version_manager.import_versions(zip_files)
                from PyQt5.QtCore import QMetaObject, Qt
                QMetaObject.invokeMethod(dlg, "accept", Qt.QueuedConnection)
                result_msg = f"导入完成: 成功 {imported}/{len(zip_files)} 个"
                if conflicts:
                    result_msg += "\n\n提示:\n" + "\n".join(conflicts)
                QMessageBox.information(self, "导入结果", result_msg)
                # 刷新版本列表
                self._refresh_version_list()

            t = threading.Thread(target=_import_thread, daemon=True)
            t.start()

        def _do_refresh():
            self.sys_gmx_versions = self.version_manager.scan_versions(
                filter_invalid=False, deduplicate=False
            )
            ver_list.clear()
            for name, meta in sorted(self.sys_gmx_versions.items()):
                item = QListWidgetItem(f"{name}  ({meta.size_mb:.0f} MB, {'有效' if meta.valid else '无效'})")
                item.setData(0x100, name)
                ver_list.addItem(item)
            self.add_log(f"版本列表已刷新: {len(self.sys_gmx_versions)} 个版本", "info")

        export_btn.clicked.connect(_do_export)
        import_btn.clicked.connect(_do_import)
        refresh_btn.clicked.connect(_do_refresh)
        btn_layout.addWidget(export_btn)
        btn_layout.addWidget(import_btn)
        btn_layout.addWidget(refresh_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        layout.addWidget(progress)

        # 关闭按钮
        close_box = QDialogButtonBox(QDialogButtonBox.Close)
        close_box.rejected.connect(dlg.reject)
        layout.addWidget(close_box)

        dlg.exec_()

    def _refresh_version_list(self):
        """刷新版本下拉列表"""
        self.sys_gmx_versions = self.version_manager.scan_versions(
            filter_invalid=False, deduplicate=False
        )
        # 断开信号防止clear()触发版本切换
        self.ver_combo.currentIndexChanged.disconnect(self._on_version_changed)
        try:
            self.ver_combo.clear()
            if self.sys_gmx_versions:
                for label in sorted(self.sys_gmx_versions.keys()):
                    meta = self.sys_gmx_versions[label]
                    self.ver_combo.addItem(label, meta.gmx_exe)
                idx = self.ver_combo.findText(self.gmx_version_label)
                if idx >= 0:
                    self.ver_combo.setCurrentIndex(idx)
        finally:
            self.ver_combo.currentIndexChanged.connect(self._on_version_changed)
        self.add_log(f"版本下拉列表已刷新: {len(self.sys_gmx_versions)} 个版本", "info")

    def _on_show_all_versions_changed(self, state):
        """显示所有版本开关切换回调"""
        show_all = (state == 2)  # Qt.Checked
        self.logger.info(f"版本显示模式切换: {'全部' if show_all else '仅有效'}")
        # 重新扫描版本（始终显示所有版本）
        self.sys_gmx_versions = self.version_manager.scan_versions(
            filter_invalid=False, deduplicate=False
        )
        # 刷新下拉列表（断开信号防止clear()触发版本切换）
        self.ver_combo.currentIndexChanged.disconnect(self._on_version_changed)
        try:
            self.ver_combo.clear()
            if self.sys_gmx_versions:
                for label in sorted(self.sys_gmx_versions.keys()):
                    meta = self.sys_gmx_versions[label]
                    self.ver_combo.addItem(label, meta.gmx_exe)
                # 尝试保持当前选择
                idx = self.ver_combo.findText(self.gmx_version_label)
                if idx >= 0:
                    self.ver_combo.setCurrentIndex(idx)
            else:
                self.ver_combo.addItem(self.gmx_version_label, self.gmx_path)
        finally:
            self.ver_combo.currentIndexChanged.connect(self._on_version_changed)
        self.add_log(f"版本列表已刷新: {'显示全部' if show_all else '仅有效版本'} ({len(self.sys_gmx_versions)}个)", "info")

    def _on_version_changed(self, index):
        """GROMACS版本切换回调 - 使用新版VersionManager"""
        # 全局前置预检：版本切换前检查目标版本完整性
        if not self.global_pre_check("version"):
            # 回退到上一个版本
            return

        version_name = self.ver_combo.currentText()
        new_path = self.ver_combo.itemData(index)
        
        self.add_log(f"正在切换版本: {version_name}...", "info")
        
        # 使用新版版本切换方法
        if hasattr(self, 'version_manager') and self.version_manager:
            ok = self._switch_gmx_version(version_name)
            if not ok:
                self.add_log(f"版本切换失败: {version_name}", "error")
                return
            meta = self.version_manager._versions.get(version_name)
            if meta:
                version_str = meta.version or "未知"
                gpu_str = meta.gpu or "未知"
                plumed_str = meta.plumed or "未知"
                simd_str = meta.simd or "未知"

                self.add_log(f"GROMACS版本已切换为: {version_name}", "success")
                if hasattr(self, "ver_badge_btn"):
                    self.ver_badge_btn.setText(self._format_ver_badge_text())
                self.add_log(
                    f"  版本号: {version_str}, GPU: {gpu_str}, "
                    f"PLUMED: {plumed_str}, SIMD: {simd_str}", "info"
                )
                if meta.plumed_status in ("broken_library", "missing_files"):
                    self.add_log(f"  ⚠ PLUMED状态异常: {meta.plumed_detail}", "warning")
                
                gpu_supported = meta.gpu and meta.gpu.lower() in ("cuda", "opencl", "yes", "enabled")
                gpu_available = self.sys_gpu_info["available"]
                
                if gpu_supported and gpu_available:
                    self.cfg_gpu.setEnabled(True)
                    self.cfg_gpu.setChecked(True)
                    self.cfg_gpu_id.setEnabled(True)
                    recommended_nt = min(8, max(4, self.sys_cpu_cores // 2))
                    self.cfg_nt.setValue(recommended_nt)
                    self.add_log(f"  自动调整CPU线程数为: {recommended_nt} (GPU加速模式)", "info")
                elif gpu_supported and not gpu_available:
                    self.cfg_gpu.setEnabled(False)
                    self.cfg_gpu.setChecked(False)
                    self.cfg_gpu_id.setEnabled(False)
                    recommended_nt = min(self.sys_cpu_cores, 16)
                    self.cfg_nt.setValue(recommended_nt)
                    self.add_log(f"  GPU不可用，自动调整CPU线程数为: {recommended_nt}", "info")
                else:
                    self.cfg_gpu.setEnabled(False)
                    self.cfg_gpu.setChecked(False)
                    self.cfg_gpu_id.setEnabled(False)
                    recommended_nt = min(self.sys_cpu_cores, 24)
                    self.cfg_nt.setValue(recommended_nt)
                    self.add_log(f"  当前版本不支持GPU加速，自动调整CPU线程数为: {recommended_nt}", "warning")
        elif new_path and os.path.isfile(new_path):
            old_path = self.gmx_path
            self.gmx_path = new_path
            self.gmx_version_label = version_name
            self.add_log(f"GROMACS版本已切换为: {self.gmx_version_label}", "success")
            ginfo = get_gromacs_version_info(self.gmx_path)
            self.add_log(f"  版本号: {ginfo['version']}, GPU: {ginfo['gpu']}, PLUMED: {ginfo['plumed']}, SIMD: {ginfo['simd']}", "info")
            
            gpu_supported = ginfo["gpu"].lower() in ("cuda", "opencl", "yes", "enabled")
            gpu_available = self.sys_gpu_info["available"]
            
            if gpu_supported and gpu_available:
                self.cfg_gpu.setEnabled(True)
                self.cfg_gpu.setChecked(True)
                self.cfg_gpu_id.setEnabled(True)
                recommended_nt = min(8, max(4, self.sys_cpu_cores // 2))
                self.cfg_nt.setValue(recommended_nt)
                self.add_log(f"  自动调整CPU线程数为: {recommended_nt} (GPU加速模式)", "info")
            elif gpu_supported and not gpu_available:
                self.cfg_gpu.setEnabled(False)
                self.cfg_gpu.setChecked(False)
                self.cfg_gpu_id.setEnabled(False)
                recommended_nt = min(self.sys_cpu_cores, 16)
                self.cfg_nt.setValue(recommended_nt)
                self.add_log(f"  GPU不可用，自动调整CPU线程数为: {recommended_nt}", "info")
            else:
                self.cfg_gpu.setEnabled(False)
                self.cfg_gpu.setChecked(False)
                self.cfg_gpu_id.setEnabled(False)
                recommended_nt = min(self.sys_cpu_cores, 24)
                self.cfg_nt.setValue(recommended_nt)
                self.add_log(f"  当前版本不支持GPU加速，自动调整CPU线程数为: {recommended_nt}", "warning")
            
            if "avx_512" in ginfo["simd"].lower() or "avx512" in ginfo["simd"].lower():
                self.add_log(f"  ✅ 当前版本使用AVX-512指令集，性能最优", "success")
            elif "avx2" in ginfo["simd"].lower():
                self.add_log(f"  当前版本使用AVX2指令集", "info")
            
            perf_recs = get_performance_recommendations(self.sys_cpu_info, ginfo, self.sys_gpu_info)
            high_recs = [r for r in perf_recs if r["level"] == "high"]
            if high_recs:
                self.add_log(f"  ⚠ 发现 {len(high_recs)} 个性能优化机会，详见系统信息", "warning")

    def _browse_gmx_exe(self):
        """手动浏览选择gmx.exe文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择GROMACS的gmx.exe文件", "", "可执行文件 (gmx.exe);;所有文件 (*.*)"
        )
        if file_path:
            if os.path.isfile(file_path) and file_path.lower().endswith("gmx.exe"):
                self.gmx_path = file_path
                # 从路径提取版本标签
                parent_dir = os.path.basename(os.path.dirname(os.path.dirname(file_path)))
                self.gmx_version_label = parent_dir if parent_dir else "自定义GROMACS"
                # 添加到下拉框
                existing_idx = self.ver_combo.findData(file_path)
                if existing_idx >= 0:
                    self.ver_combo.setCurrentIndex(existing_idx)
                else:
                    self.ver_combo.addItem(self.gmx_version_label, file_path)
                    self.ver_combo.setCurrentIndex(self.ver_combo.count() - 1)
                self.add_log(f"已手动选择GROMACS: {self.gmx_version_label}", "success")
                self.add_log(f"  路径: {file_path}", "info")
                ginfo = get_gromacs_version_info(self.gmx_path)
                self.add_log(f"  版本号: {ginfo['version']}, GPU支持: {ginfo['gpu']}, PLUMED: {ginfo['plumed']}", "info")
                # 保存到全局配置
                if hasattr(self, 'global_config'):
                    self.global_config["gmx_path"] = file_path
            else:
                QMessageBox.warning(self, "提示", "请选择有效的gmx.exe文件")

    def _on_gpu_diagnose(self):
        """GPU诊断功能 - 检测NVIDIA、CUDA、GROMACS GPU支持"""
        self.add_log("=" * 60, "cmd")
        self.add_log("GPU加速诊断报告", "diagnosis")
        self.add_log("=" * 60, "cmd")
        
        issues = []
        warnings = []
        success_items = []
        
        # 1. 检测NVIDIA GPU
        self.add_log("", "info")
        self.add_log("【1/5】NVIDIA GPU检测", "info")
        nvidia_available = False
        nvidia_info = {}
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=index,name,driver_version,memory.total", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                nvidia_available = True
                lines = [l.strip() for l in result.stdout.strip().split("\n") if l.strip()]
                nvidia_info["count"] = len(lines)
                nvidia_info["cards"] = []
                for line in lines:
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 4:
                        nvidia_info["cards"].append({
                            "index": parts[0],
                            "name": parts[1],
                            "driver": parts[2],
                            "memory": parts[3]
                        })
                for card in nvidia_info["cards"]:
                    self.add_log(f"  ✓ GPU {card['index']}: {card['name']} ({card['memory']})", "success")
                    self.add_log(f"      驱动版本: {card['driver']}", "info")
                success_items.append("检测到NVIDIA GPU")
            else:
                self.add_log("  ✗ nvidia-smi命令执行失败", "error")
                self.add_log(f"      错误: {result.stderr.strip()}", "error")
                issues.append("NVIDIA GPU未检测到（nvidia-smi不可用）")
        except FileNotFoundError:
            self.add_log("  ✗ nvidia-smi未找到", "error")
            self.add_log("      可能原因: NVIDIA显卡驱动未安装或未正确配置", "warning")
            issues.append("NVIDIA显卡驱动未安装或未配置")
        except Exception as e:
            self.add_log(f"  ✗ 检测失败: {str(e)}", "error")
            issues.append(f"GPU检测异常: {str(e)}")
        
        # 2. 检测CUDA版本
        self.add_log("", "info")
        self.add_log("【2/5】CUDA版本检测", "info")
        cuda_version = "未知"
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=compute_cap", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                cc_lines = [l.strip() for l in result.stdout.strip().split("\n") if l.strip()]
                if cc_lines:
                    cc = cc_lines[0]
                    self.add_log(f"  ✓ CUDA计算能力: {cc}", "success")
                    success_items.append(f"CUDA计算能力 {cc}")
                    if float(cc) < 3.5:
                        warnings.append(f"CUDA计算能力 {cc} 较低，可能影响性能")
        except Exception as e:
            self.add_log(f"  ⚠ CUDA信息检测失败: {str(e)}", "warning")
            warnings.append("CUDA信息检测失败")
        
        # 3. 检测GROMACS是否支持GPU
        self.add_log("", "info")
        self.add_log("【3/5】GROMACS GPU支持检测", "info")
        gmx_path = self.gmx_path
        if os.path.isfile(gmx_path):
            ginfo = get_gromacs_version_info(gmx_path)
            self.add_log(f"  GROMACS版本: {ginfo['version']}", "info")
            self.add_log(f"  GPU支持: {ginfo['gpu']}", "info")
            self.add_log(f"  PLUMED支持: {ginfo['plumed']}", "info")
            
            if ginfo["gpu"].lower() in ("cuda", "opencl", "yes", "enabled"):
                self.add_log("  ✓ GROMACS编译时包含GPU支持", "success")
                success_items.append("GROMACS支持GPU")
            else:
                self.add_log("  ✗ GROMACS编译时未包含GPU支持", "error")
                issues.append("GROMACS编译时未包含GPU支持")
                self.add_log("    建议: 使用支持CUDA的GROMACS版本", "warning")
        else:
            self.add_log(f"  ✗ GROMACS可执行文件不存在: {gmx_path}", "error")
            issues.append("GROMACS可执行文件不存在")
        
        # 4. 测试GROMACS GPU支持状态（通过mdrun帮助信息验证）
        self.add_log("", "info")
        self.add_log("【4/5】GROMACS GPU运行测试", "info")
        if os.path.isfile(gmx_path) and nvidia_available:
            self.add_log("  正在检查mdrun GPU参数支持...", "info")
            try:
                result = subprocess.run(
                    [gmx_path, "mdrun", "-h"],
                    capture_output=True, text=True, timeout=15,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                mdrun_help = result.stdout + result.stderr
                gpu_params = []
                for param in ["-nb", "-pme", "-gpu_id", "-update", "-bonded"]:
                    if param in mdrun_help:
                        gpu_params.append(param)
                if gpu_params:
                    self.add_log(f"  ✓ mdrun支持GPU相关参数: {', '.join(gpu_params)}", "success")
                    success_items.append("mdrun支持GPU参数")
                else:
                    self.add_log("  ⚠ mdrun未检测到GPU相关参数", "warning")
                    warnings.append("mdrun GPU参数检测不完整")
                # 额外检查：尝试运行简短mdrun（-h返回0即认为可执行）
                if result.returncode == 0:
                    self.add_log("  ✓ mdrun可正常执行", "success")
                    success_items.append("mdrun可正常执行")
                else:
                    self.add_log("  ⚠ mdrun执行返回非零状态", "warning")
            except Exception as e:
                self.add_log(f"  ⚠ GPU支持检查失败: {str(e)}", "warning")
                warnings.append(f"GPU支持检查失败: {str(e)}")
        else:
            self.add_log("  ⚠ 跳过测试（GROMACS或NVIDIA GPU不可用）", "warning")
        
        # 5. 当前配置检查
        self.add_log("", "info")
        self.add_log("【5/5】当前配置检查", "info")
        gpu_enabled = self.cfg_gpu.isChecked()
        self.add_log(f"  GPU加速启用: {'是' if gpu_enabled else '否'}", "info")
        if gpu_enabled:
            gpu_id = self.cfg_gpu_id.currentData()
            self.add_log(f"  GPU ID: {gpu_id}", "info")
            auto_mode = self.cfg_gpu_auto.isChecked()
            self.add_log(f"  自动模式: {'是' if auto_mode else '否'}", "info")
            nt = self.cfg_nt.value()
            self.add_log(f"  CPU线程数: {nt}", "info")
            
            if nvidia_available:
                if nt > 8:
                    warnings.append(f"线程数 {nt} 较多，GPU模式下建议4-6线程")
                else:
                    success_items.append(f"线程数 {nt} 合理")
        else:
            self.add_log("  ⚠ GPU加速未启用，所有计算将使用CPU", "warning")
            warnings.append("GPU加速未启用")
        
        # 汇总报告
        self.add_log("", "info")
        self.add_log("=" * 60, "cmd")
        self.add_log("诊断汇总", "diagnosis")
        self.add_log("=" * 60, "cmd")
        
        if issues:
            self.add_log(f"  问题 ({len(issues)}):", "error")
            for i, issue in enumerate(issues, 1):
                self.add_log(f"    {i}. {issue}", "error")
        
        if warnings:
            self.add_log(f"  警告 ({len(warnings)}):", "warning")
            for i, warning in enumerate(warnings, 1):
                self.add_log(f"    {i}. {warning}", "warning")
        
        if success_items:
            self.add_log(f"  正常 ({len(success_items)}):", "success")
            for i, item in enumerate(success_items, 1):
                self.add_log(f"    {i}. {item}", "success")
        
        if not issues and not warnings:
            self.add_log("  ✓ 所有检测通过，GPU加速配置正常！", "success")
        
        self.add_log("=" * 60, "cmd")

    def _on_box_size_mode_changed(self, text):
        if hasattr(self, "md_tab"):
            self.md_tab._on_box_size_mode_changed(text)

    def _on_box_type_changed(self, text):
        if hasattr(self, "md_tab"):
            self.md_tab._on_box_type_changed(text)

    def _get_box_params(self):
        if hasattr(self, "md_tab"):
            return self.md_tab._get_box_params()
        return []

    def _get_mdrun_extra(self, is_em=False):
        """构建 mdrun 额外参数列表 (-nt, -nb gpu 等)
        is_em=True 时为能量最小化模式，EM不支持GPU PME和GPU update
        完整GPU卸载: -nb gpu -pme gpu -bonded gpu -update gpu -dlb yes -pin on
        """
        nt = self.cfg_nt.value()
        extra = ["-nt", str(nt), "-pin", "on"]

        # EM不支持动态负载均衡（无积分器），MD步骤启用DLB提升并行效率
        if not is_em:
            extra += ["-dlb", "yes"]

        if self.cfg_gpu.isChecked() and self.cfg_gpu.isEnabled():
            gpu_id = self.cfg_gpu_id.currentData()
            if gpu_id is not None:
                extra += ["-gpu_id", str(gpu_id)]
            if is_em:
                if self.cfg_gpu_auto.isChecked():
                    extra += ["-nb", "gpu", "-pme", "cpu"]
                else:
                    extra += ["-nb", "gpu", "-pme", "cpu", "-bonded", "gpu", "-update", "cpu"]
            else:
                extra += ["-nb", "gpu", "-pme", "gpu", "-bonded", "gpu", "-update", "gpu"]
        else:
            # 无论系统是否有GPU，只要用户未启用GPU加速，就强制CPU-only参数
            extra += ["-nb", "cpu", "-pme", "cpu", "-bonded", "cpu", "-update", "cpu"]

        return extra

    # -------------------------------------------------------------------------
    # 日志相关
    # -------------------------------------------------------------------------
    def add_log(self, text, level="info"):
        if not text:
            return
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        level_label = level.upper().ljust(7)
        
        # 使用core logger记录
        if level == "error":
            self.logger.error(text)
        elif level == "warning":
            self.logger.warning(text)
        elif level == "success":
            self.logger.info(text)
        elif level == "cmd":
            self.logger.debug(text)
        else:
            self.logger.info(text)
        
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.End)

        fmt = QTextCharFormat()
        if level == "success":
            fmt.setForeground(self._color_success)
        elif level == "warning":
            fmt.setForeground(self._color_warning)
        elif level == "error":
            fmt.setForeground(self._color_error)
        elif level == "cmd":
            fmt.setForeground(self._color_cmd)
        elif level == "diagnosis":
            fmt.setForeground(QColor("#9C27B0"))
            fmt.setFontWeight(QFont.Bold)
        else:
            fmt.setForeground(self._color_info)

        cursor.setCharFormat(fmt)
        display_timestamp = datetime.now().strftime("%H:%M:%S")
        cursor.insertText(f"[{display_timestamp}] {text}\n")
        self.log_text.setTextCursor(cursor)
        self.log_text.ensureCursorVisible()

        if level == "error":
            self._recent_errors.append(text)

    def clear_log(self):
        self.log_text.clear()

    def export_log(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "导出日志", f"gromacs_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "Text Files (*.txt);;All Files (*)"
        )
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(self.log_text.toPlainText())
                self.add_log(f"日志已导出到: {path}", "success")
            except Exception as e:
                self.add_log(f"导出日志失败: {e}", "error")

    # -------------------------------------------------------------------------
    # 通用交互
    # -------------------------------------------------------------------------
    def browse_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "选择工作目录", "")
        if directory:
            self.path_edit.setText(directory)
            self.add_log(f"工作目录已设置为: {directory}", "info")

    def _browse_file(self, line_edit, title="选择文件", file_filter="所有文件 (*.*)"):
        """通用文件浏览对话框，将选择的文件名（不含路径）填入line_edit"""
        wd = self._get_work_dir() or os.getcwd()
        fname, _ = QFileDialog.getOpenFileName(self, title, wd, file_filter)
        if fname:
            # 如果文件在工作目录内，只填文件名，否则填完整路径
            if fname.startswith(wd + os.sep) or fname.startswith(wd + "/"):
                line_edit.setText(os.path.basename(fname))
            else:
                line_edit.setText(fname)

    def _create_file_input(self, placeholder, default="", filter_str="所有文件 (*.*)", dialog_title="选择文件"):
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

    def _on_system_cleanup(self):
        """系统清理：分选项安全清理缓存和过期日志"""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QCheckBox, QSpinBox, QDialogButtonBox as DlgBtnBox

        dlg = QDialog(self)
        dlg.setWindowTitle("系统清理")
        dlg.setMinimumWidth(380)
        layout = QVBoxLayout(dlg)

        # 选项1: 临时缓存清理
        cb_cache = QCheckBox("清理临时缓存（__pycache__、.pyc、spec、旧exe、残留文件）")
        cb_cache.setChecked(True)
        layout.addWidget(cb_cache)

        # 选项2: 过期日志清理
        cb_logs = QCheckBox("清理过期日志（INFO/DEBUG/WARNING超过指定天数，ERROR永久保留）")
        cb_logs.setChecked(True)
        layout.addWidget(cb_logs)

        # 日志天数自定义
        days_layout = QHBoxLayout()
        days_layout.addWidget(QLabel("日志保留天数:"))
        days_spin = QSpinBox()
        days_spin.setRange(1, 365)
        days_spin.setValue(30)
        days_layout.addWidget(days_spin)
        days_layout.addStretch()
        layout.addLayout(days_layout)

        # 确定/取消
        btn_box = DlgBtnBox(DlgBtnBox.Ok | DlgBtnBox.Cancel)
        btn_box.accepted.connect(dlg.accept)
        btn_box.rejected.connect(dlg.reject)
        layout.addWidget(btn_box)

        if dlg.exec_() != QDialog.Accepted:
            return

        do_cache = cb_cache.isChecked()
        do_logs = cb_logs.isChecked()
        log_days = days_spin.value()

        if not do_cache and not do_logs:
            return

        import shutil
        app_root = _get_app_root()
        cleaned_files = 0
        freed_bytes = 0

        # 备份配置文件
        try:
            config_file = app_root / "config" / "app_config.json"
            if config_file.exists():
                backup_path = app_root / "config" / "app_config.json.backup"
                shutil.copy2(str(config_file), str(backup_path))
                self.add_log("已备份配置文件", "info")
        except Exception as e:
            self.add_log(f"配置文件备份失败: {e}", "error")
            QMessageBox.warning(self, "清理失败", f"配置文件备份失败: {e}")
            return

        if do_cache:
            # 清理 __pycache__ 和 .pyc
            for root, dirs, files in os.walk(str(app_root)):
                dirs[:] = [d for d in dirs if d.lower() not in ("gromacs", "miniconda3", "dist", "release")]
                for d in list(dirs):
                    if d == "__pycache__":
                        p = Path(root) / d
                        try:
                            size = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
                            shutil.rmtree(str(p))
                            cleaned_files += 1
                            freed_bytes += size
                            dirs.remove(d)
                        except Exception:
                            pass
                for f in files:
                    if f.endswith(".pyc"):
                        fp = Path(root) / f
                        try:
                            size = fp.stat().st_size
                            fp.unlink()
                            cleaned_files += 1
                            freed_bytes += size
                        except Exception:
                            pass

            # 清理temp中的日志和编译临时文件
            temp_dir = app_root / "temp"
            if temp_dir.exists():
                for pattern in ["*.log", "*.spec", "*_test.exe"]:
                    for f in temp_dir.glob(pattern):
                        try:
                            size = f.stat().st_size
                            f.unlink()
                            cleaned_files += 1
                            freed_bytes += size
                        except Exception:
                            pass

            # 清理残留def文件
            for residual in ["dl.def", "dl.exp", "dl.lib"]:
                rp = app_root / residual
                if rp.exists():
                    try:
                        size = rp.stat().st_size
                        rp.unlink()
                        cleaned_files += 1
                        freed_bytes += size
                    except Exception:
                        pass

        if do_logs:
            # 清理过期的分级日志文件（INFO/DEBUG/WARNING超过log_days天，ERROR永久保留）
            import time
            now = time.time()
            log_dir = app_root / "source" / "logs"
            if not log_dir.exists():
                log_dir = app_root / "logs"
            if log_dir.exists():
                for level_prefix in ["info_", "debug_", "warning_"]:
                    for log_file in log_dir.glob(f"{level_prefix}*.log"):
                        try:
                            if (now - log_file.stat().st_mtime) > log_days * 86400:
                                size = log_file.stat().st_size
                                log_file.unlink()
                                cleaned_files += 1
                                freed_bytes += size
                        except Exception:
                            pass
                # 旧版gromacs_gui_*.log也按天数清理
                for log_file in log_dir.glob("gromacs_gui_*.log"):
                    try:
                        if (now - log_file.stat().st_mtime) > log_days * 86400:
                            size = log_file.stat().st_size
                            log_file.unlink()
                            cleaned_files += 1
                            freed_bytes += size
                    except Exception:
                        pass

        freed_mb = round(freed_bytes / (1024 * 1024), 2)
        self.add_log(f"系统清理完成: 清理 {cleaned_files} 个文件/目录, 释放 {freed_mb} MB", "info")
        QMessageBox.information(
            self, "清理完成",
            f"清理文件/目录数: {cleaned_files}\n释放磁盘空间: {freed_mb} MB\n"
            f"{'缓存已清理' if do_cache else ''}"
            f"{'，' if do_cache and do_logs else ''}"
            f"{f'过期日志已清理（>{log_days}天）' if do_logs else ''}\n\n"
            f"ERROR日志永久保留"
        )

    def show_version(self):
        ginfo = get_gromacs_version_info(self.gmx_path)
        gpu_text = "未检测到"
        if self.sys_gpu_info["available"]:
            gpu_text = "<br>".join([f"  {n}" for n in self.sys_gpu_info["names"]])
            gpu_text += f"<br>  CUDA: {self.sys_gpu_info['cuda_version']}"

        versions_text = "<br>".join([f"  {k}" for k in sorted(self.sys_gmx_versions.keys())]) if self.sys_gmx_versions else "  gromacs-2026.1-plumed-CUDA"

        QMessageBox.about(
            self, "版本信息",
            f"<h2>{VERSION_CONFIG['display_name']} {VERSION_CONFIG['full_version']}</h2>"
            f"<p>基于 PyQt5 开发的全面升级版 GROMACS 图形化界面。</p>"
            f"<p><b>功能模块:</b></p>"
            f"<ul>"
            f"<li>Part 1: 完整 MD 流程 (pdb2gmx → editconf → solvate → genion → grompp → mdrun)</li>"
            f"<li>Part 2: 结构处理工具 (editconf/pdb2gmx/make_ndx/genrestr等)</li>"
            f"<li>Part 3: 高级模拟 (伞形采样、WHAM、元动力学、ABF)</li>"
            f"<li>Part 4: 轨迹处理工具 (trjconv/trjcat/trjorder等)</li>"
            f"<li>Part 5: 20+ 种结果分析与可视化工具</li>"
            f"<li>Part 6: MMPBSA 结合自由能计算</li>"
            f"<li>Part 7: 自定义脚本 (PowerShell/Batch/Shell)</li>"
            f"</ul>"
            f"<p><b>系统配置:</b></p>"
            f"<ul>"
            f"<li>CPU: {self.sys_cpu_cores} 核</li>"
            f"<li>内存: {self.sys_memory_gb} GB</li>"
            f"<li>GPU:<br>{gpu_text}</li>"
            f"</ul>"
            f"<p><b>当前GROMACS:</b> {self.gmx_version_label}</p>"
            f"<p>  版本号: {ginfo['version']}<br>"
            f"  GPU支持: {ginfo['gpu']}<br>"
            f"  PLUMED: {ginfo['plumed']}</p>"
            f"<p><b>可用版本:</b><br>{versions_text}</p>"
            f"<p><b>特色:</b> 支持多版本切换、自动GPU检测、智能线程分配</p>"
        )

    def _get_work_dir(self):
        wd = self.path_edit.text().strip()
        if not wd:
            self.add_log("错误: 请先选择工作目录", "error")
            return None
        if not os.path.isdir(wd):
            self.add_log(f"错误: 工作目录不存在: {wd}", "error")
            return None
        return wd

    def _set_running_state(self, running):
        self.run_all_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)
        self.progress_bar.setVisible(running)
        if running:
            self.progress_bar.setValue(0)
        # 运行时锁定系统配置，防止中途更改
        self.ver_combo.setEnabled(not running)
        self.cfg_nt.setEnabled(not running)
        self.cfg_mem_limit.setEnabled(not running)
        self.cfg_mem_value.setEnabled(not running and self.cfg_mem_limit.isChecked())
        self.cfg_gpu.setEnabled(not running and bool(self.sys_gpu_info["available"]))
        self.cfg_gpu_auto.setEnabled(not running)
        for widgets in self.md_step_btns.values():
            widgets["run_btn"].setEnabled(not running)
        if hasattr(self, "md_tab"):
            self.md_tab.set_running_state(running)
        for widgets in self.analysis_widgets.values():
            widgets["run_btn"].setEnabled(not running)
        for widgets in self.traj_widgets.values():
            widgets["run_btn"].setEnabled(not running)
        if hasattr(self, "prep_run_btn"):
            self.prep_run_btn.setEnabled(not running)
        if hasattr(self, "traj_tab"):
            self.traj_tab.set_running_state(running)
        for widgets in self.struc_widgets.values():
            widgets["run_btn"].setEnabled(not running)
        if hasattr(self, "struc_tab"):
            self.struc_tab.set_running_state(running)
        self.mmpbsa_run_btn.setEnabled(not running)
        self.umb_run_btn.setEnabled(not running)
        self.wham_run_btn.setEnabled(not running)
        self.meta_run_btn.setEnabled(not running)
        self.meta_gen_btn.setEnabled(not running)
        self.abf_gen_btn.setEnabled(not running)
        if hasattr(self, "advanced_tab"):
            self.advanced_tab.set_running_state(running)
        if hasattr(self, "analysis_tab"):
            self.analysis_tab.set_running_state(running)
        self.statusBar().showMessage("运行中..." if running else "就绪")

    # -------------------------------------------------------------------------
    # 命令执行框架
    # -------------------------------------------------------------------------
    def run_command(self, cmd, work_dir, step_name="", stdin_input=None):
        # 全局前置预检：模拟运行前检查
        if not self.global_pre_check("run"):
            return

        try:
            if self.worker and self.worker.isRunning():
                self.add_log("已有任务在运行，请先停止", "warning")
                return

            self.add_log(f"{'='*60}", "cmd")
            if step_name:
                self.add_log(f"开始执行: {step_name}", "cmd")
            self.add_log(f"工作目录: {work_dir}", "cmd")
            self.add_log(f"{'='*60}", "cmd")

            self._recent_errors.clear()
            self._last_diagnoses = []
            if isinstance(cmd, list):
                if len(cmd) > 0 and isinstance(cmd[0], list):
                    self._current_command = " | ".join(" ".join(c) for c in cmd)
                else:
                    self._current_command = " ".join(str(c) for c in cmd)
            else:
                self._current_command = str(cmd)

            mem_limit_gb = None
            if self.cfg_mem_limit.isChecked():
                mem_limit_gb = self.cfg_mem_value.value()

            env = None
            if not self.sys_gpu_info["available"]:
                env = os.environ.copy()
                env["GMX_DISABLE_GPU_DETECTION"] = "1"
                env["CUDA_VISIBLE_DEVICES"] = ""
                self.add_log("无GPU检测：已启用CPU兼容模式 (GMX_DISABLE_GPU_DETECTION=1)", "info")

            # 修复：传递stdin_input给GromacsWorker
            self.worker = GromacsWorker(cmd, work_dir, step_name=step_name, env=env, mem_limit_gb=mem_limit_gb, stdin_input=stdin_input)
            self.worker.log_signal.connect(self.add_log)
            self.worker.finished_signal.connect(self.on_finished)
            self.worker.step_finished_signal.connect(self.on_step_finished)
            self._set_running_state(True)
            self.worker.start()
        except Exception as e:
            self.add_log(f"启动命令执行时发生错误: {str(e)}", "error")
            self._set_running_state(False)

    def on_step_finished(self, step_name, success):
        if success:
            self.add_log(f"[步骤完成] {step_name}", "success")
        else:
            self.add_log(f"[步骤失败] {step_name}", "error")

    def on_finished(self, success):
        self.add_log(f"{'='*60}", "cmd")
        if success:
            self.add_log("任务成功完成!", "success")
        else:
            self.add_log("任务失败或被中断!", "error")
            self._run_error_diagnosis()
        self.add_log(f"{'='*60}", "cmd")
        self._set_running_state(False)
        self.worker = None

    def _run_error_diagnosis(self):
        if not self._recent_errors:
            return

        all_error_text = "\n".join(self._recent_errors)
        self._last_diagnoses = self._error_diagnoser.diagnose(all_error_text, self._current_command)

        if self._last_diagnoses:
            self.add_log("", "diagnosis")
            self.add_log("=" * 60, "diagnosis")
            self.add_log("【错误诊断结果】", "diagnosis")
            self.add_log("=" * 60, "diagnosis")

            for diag in self._last_diagnoses:
                severity_icon = ""
                if diag["severity"] == "high":
                    severity_icon = "🔴"
                elif diag["severity"] == "medium":
                    severity_icon = "🟠"
                else:
                    severity_icon = "🟡"

                self.add_log(f"", "diagnosis")
                self.add_log(f"{severity_icon} 错误类型: {diag['error_type']}", "diagnosis")
                self.add_log(f"   描述: {diag['description']}", "diagnosis")
                self.add_log(f"   建议:", "diagnosis")
                for i, suggestion in enumerate(diag["suggestions"]):
                    self.add_log(f"      {i + 1}. {suggestion}", "info")

            self.add_log("=" * 60, "diagnosis")
            self.add_log("点击日志区域的'查看错误诊断'按钮查看详细信息", "diagnosis")
            self.add_log("=" * 60, "diagnosis")

            self._show_diagnosis_dialog()

    def _show_diagnosis_dialog(self):
        if self._last_diagnoses:
            dlg = ErrorDiagnosisDialog(self, self._last_diagnoses)
            dlg.exec_()

    def show_error_diagnosis(self):
        if not self._last_diagnoses:
            if self._recent_errors:
                all_error_text = "\n".join(self._recent_errors)
                self._last_diagnoses = self._error_diagnoser.diagnose(all_error_text, self._current_command)
            else:
                QMessageBox.information(self, "提示", "当前没有可诊断的错误信息")
                return
        self._show_diagnosis_dialog()

    def stop_run(self):
        if self.worker and self.worker.isRunning():
            self.add_log("正在停止当前任务...", "warning")
            self.worker.stop()
        else:
            self.add_log("当前没有运行中的任务", "info")

    # -------------------------------------------------------------------------
    # Part 1: MD 各步骤执行 (已委托至 gui.tabs.md_tab.MdTab)
    # -------------------------------------------------------------------------
    def _on_use_existing_toggled(self, checked):
        if hasattr(self, "md_tab"):
            self.md_tab._on_use_existing_toggled(checked)

    def _on_skip_toggled(self, checked):
        if hasattr(self, "md_tab"):
            self.md_tab._on_skip_toggled(checked)

    def _update_skip_steps_visibility(self):
        if hasattr(self, "md_tab"):
            self.md_tab._update_skip_steps_visibility()

    def run_md_step(self, step_key):
        if hasattr(self, "md_tab"):
            self.md_tab.run_md_step(step_key)

    def run_evap_step(self):
        if hasattr(self, "md_tab"):
            self.md_tab.run_evap_step()

    def _reset_anneal_curve(self):
        if hasattr(self, "md_tab"):
            self.md_tab._reset_anneal_curve()

    def run_anneal_step(self):
        if hasattr(self, "md_tab"):
            self.md_tab.run_anneal_step()

    def run_all_md(self):
        if hasattr(self, "md_tab"):
            self.md_tab.run_all_md()

    def _get_full_mdp_template(self, mdp_type):
        if hasattr(self, "md_tab"):
            return self.md_tab._get_full_mdp_template(mdp_type)
        return ""

    def open_monitor(self):
        wd = self._get_work_dir()
        dlg = SimulationMonitorDialog(self, wd, self.gmx_path)
        dlg.exec_()

    def open_mdp_editor(self, mdp_type="md"):
        wd = self._get_work_dir()
        default_content = ""
        template_map = {
            "em": "EM-1 (最速下降法)",
            "nvt": "NPT-1 (初始平衡)",
            "npt": "NPT-1 (初始平衡)",
            "md": "MD (生产模拟, 10ns)",
            "ions": "EM-1 (最速下降法)",
            "sa": "SA溶剂蒸发 (10ps/轮)",
            "annealing": "退火 (温度循环)",
        }
        if mdp_type and mdp_type in template_map:
            template_name = template_map[mdp_type]
            template_dict = MdpEditorDialog.MDP_TEMPLATES.get(template_name, {})
            if template_dict:
                lines = []
                for key, value in template_dict.items():
                    lines.append(f"{key} = {value}")
                default_content = "\n".join(lines)

        dlg = MdpEditorDialog(self, default_content)
        if wd:
            dlg.set_default_dir(wd)
        if dlg.exec_() == QDialog.Accepted:
            mdp_content = dlg.get_mdp_content()
            self.add_log("MDP编辑器已确认，可将内容保存为MDP文件", "success")

    def save_config(self):
        try:
            wd = self._get_work_dir() or os.getcwd()
            filepath, _ = QFileDialog.getSaveFileName(
                self, "保存配置文件", wd,
                "JSON配置文件 (*.json);;所有文件 (*.*)"
            )
            if not filepath:
                return

            config = {
                "version": "1.0",
                "global": {
                    "gmx_path": self.gmx_path,
                    "work_dir": self.path_edit.text().strip(),
                    "num_threads": self.cfg_nt.value(),
                    "gpu_enabled": self.cfg_gpu.isChecked(),
                    "gpu_id": self.cfg_gpu_id.currentIndex(),
                    "gpu_auto": self.cfg_gpu_auto.isChecked(),
                    "box_type": self.md_box_type.currentText(),
                    "size_mode": self.md_box_size_mode.currentText(),
                    "box_size": self.md_box_size.value(),
                    "box_a": self.md_box_a.value(),
                    "box_x": self.md_box_x.value(),
                    "box_y": self.md_box_y.value(),
                    "box_z": self.md_box_z.value(),
                    "angle_alpha": self.md_angle_alpha.value(),
                    "angle_beta": self.md_angle_beta.value(),
                    "angle_gamma": self.md_angle_gamma.value(),
                    "ff": self.md_ff.currentText(),
                    "water": self.md_water.currentText(),
                    "ion_conc": self.md_ion_conc.value(),
                    "temp": self.md_temp.value(),
                    "pressure": self.md_pressure.value(),
                    "dt": self.md_dt.value(),
                    "nsteps": self.md_nsteps.value(),
                    "engine": self.md_engine.currentText(),
                    "md_nt": self.md_nt.value(),
                    "pdb": self.md_pdb.text().strip(),
                    "use_existing_top": self.use_existing_top.isChecked(),
                    "mem_limit_enabled": self.cfg_mem_limit.isChecked(),
                    "mem_limit_gb": self.cfg_mem_value.value(),
                    "se_gro": self.se_gro_edit.text().strip(),
                    "se_top": self.se_top_edit.text().strip(),
                    "skip_editconf": self.skip_editconf.isChecked(),
                    "skip_solvate": self.skip_solvate.isChecked(),
                    "skip_genion": self.skip_genion.isChecked(),
                },
                "part1_steps": {},
                "script_type": self.script_type.currentData() or self.script_type.currentText() if hasattr(self, 'script_type') else "PowerShell (.ps1)",
                "language": i18n_get_language()
            }

            for step_key, step_info in self.md_step_btns.items():
                step_data = {
                    "labels": step_info["labels"],
                    "values": [edit.text().strip() for edit in step_info["edits"]]
                }
                if "box_type_combo" in step_info:
                    step_data["box_type"] = step_info["box_type_combo"].currentText()
                if "size_mode_combo" in step_info:
                    step_data["size_mode"] = step_info["size_mode_combo"].currentText()
                if "box_size_spin" in step_info:
                    step_data["box_size"] = step_info["box_size_spin"].value()
                if "box_a_spin" in step_info:
                    step_data["box_a"] = step_info["box_a_spin"].value()
                if "box_x_spin" in step_info:
                    step_data["box_x"] = step_info["box_x_spin"].value()
                if "box_y_spin" in step_info:
                    step_data["box_y"] = step_info["box_y_spin"].value()
                if "box_z_spin" in step_info:
                    step_data["box_z"] = step_info["box_z_spin"].value()
                if "angle_alpha_spin" in step_info:
                    step_data["angle_alpha"] = step_info["angle_alpha_spin"].value()
                if "angle_beta_spin" in step_info:
                    step_data["angle_beta"] = step_info["angle_beta_spin"].value()
                if "angle_gamma_spin" in step_info:
                    step_data["angle_gamma"] = step_info["angle_gamma_spin"].value()
                if "center_check" in step_info:
                    step_data["center_check"] = step_info["center_check"].isChecked()
                if "princ_check" in step_info:
                    step_data["princ_check"] = step_info["princ_check"].isChecked()
                if "custom_out_check" in step_info and step_info["custom_out_check"] is not None:
                    step_data["custom_out_check"] = step_info["custom_out_check"].isChecked()
                if "custom_out_edit" in step_info and step_info["custom_out_edit"]:
                    step_data["custom_out_edit"] = step_info["custom_out_edit"].text().strip()
                if "restart_check" in step_info and step_info["restart_check"] is not None:
                    step_data["restart_check"] = step_info["restart_check"].isChecked()
                config["part1_steps"][step_key] = step_data

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            self.add_log(f"配置已保存到: {filepath}", "success")
        except Exception as e:
            self.add_log(f"保存配置失败: {str(e)}", "error")
            QMessageBox.critical(self, "错误", f"保存配置失败: {str(e)}")

    def load_config(self):
        try:
            wd = self._get_work_dir() or os.getcwd()
            filepath, _ = QFileDialog.getOpenFileName(
                self, "加载配置文件", wd,
                "JSON配置文件 (*.json);;所有文件 (*.*)"
            )
            if not filepath:
                return

            with open(filepath, "r", encoding="utf-8") as f:
                config = json.load(f)

            if config.get("version") != "1.0":
                QMessageBox.warning(self, "警告", "配置文件版本不兼容，请使用V1.0版本的配置文件")
                return

            global_config = config.get("global", {})

            self.gmx_path = global_config.get("gmx_path", self.gmx_path)
            self.path_edit.setText(global_config.get("work_dir", ""))

            self.cfg_nt.setValue(global_config.get("num_threads", self.cfg_nt.value()))
            if self.sys_gpu_info["available"]:
                self.cfg_gpu.setChecked(global_config.get("gpu_enabled", False))
                self.cfg_gpu_id.setCurrentIndex(global_config.get("gpu_id", 0))
                self.cfg_gpu_auto.setChecked(global_config.get("gpu_auto", True))
            else:
                self.cfg_gpu.setChecked(False)
                self.cfg_gpu.setEnabled(False)
                self.cfg_gpu_id.setEnabled(False)

            self.md_box_type.setCurrentText(global_config.get("box_type", "cubic (立方体)"))
            self.md_box_size_mode.setCurrentText(global_config.get("size_mode", "按边距 (-d)"))
            self.md_box_size.setValue(global_config.get("box_size", 1.0))
            self.md_box_a.setValue(global_config.get("box_a", 5.0))
            self.md_box_x.setValue(global_config.get("box_x", 1.0))
            self.md_box_y.setValue(global_config.get("box_y", 1.5))
            self.md_box_z.setValue(global_config.get("box_z", 2.0))
            self.md_angle_alpha.setValue(global_config.get("angle_alpha", 90.0))
            self.md_angle_beta.setValue(global_config.get("angle_beta", 90.0))
            self.md_angle_gamma.setValue(global_config.get("angle_gamma", 90.0))

            self.md_ff.setCurrentText(global_config.get("ff", "amber99sb-ildn"))
            self.md_water.setCurrentText(global_config.get("water", "tip3p"))
            self.md_ion_conc.setValue(global_config.get("ion_conc", 0.15))
            self.md_temp.setValue(global_config.get("temp", 300.0))
            self.md_pressure.setValue(global_config.get("pressure", 1.0))
            self.md_dt.setValue(global_config.get("dt", 0.002))
            self.md_nsteps.setValue(global_config.get("nsteps", 50000000))
            self.md_engine.setCurrentText(global_config.get("engine", "auto"))
            self.md_nt.setValue(global_config.get("md_nt", self.md_nt.value()))
            self.md_pdb.setText(global_config.get("pdb", ""))

            self.use_existing_top.setChecked(global_config.get("use_existing_top", False))
            self.cfg_mem_limit.setChecked(global_config.get("mem_limit_enabled", False))
            self.cfg_mem_value.setEnabled(self.cfg_mem_limit.isChecked())
            mem_val = global_config.get("mem_limit_gb", 8.0)
            mem_val = max(0.5, min(mem_val, float(self.sys_memory_gb)))
            self.cfg_mem_value.setValue(mem_val)
            self.se_gro_edit.setText(global_config.get("se_gro", "input.gro"))
            self.se_top_edit.setText(global_config.get("se_top", "topol.top"))
            self.skip_editconf.setChecked(global_config.get("skip_editconf", False))
            self.skip_solvate.setChecked(global_config.get("skip_solvate", False))
            self.skip_genion.setChecked(global_config.get("skip_genion", False))

            self._on_box_type_changed(self.md_box_type.currentText())
            self._on_use_existing_toggled(self.use_existing_top.isChecked())
            self._update_skip_steps_visibility()

            part1_steps = config.get("part1_steps", {})
            for step_key, step_data in part1_steps.items():
                if step_key in self.md_step_btns:
                    step_info = self.md_step_btns[step_key]
                    values = step_data.get("values", [])
                    for i, edit in enumerate(step_info["edits"]):
                        if i < len(values):
                            edit.setText(values[i])
                    if "box_type_combo" in step_info and "box_type" in step_data:
                        step_info["box_type_combo"].setCurrentText(step_data["box_type"])
                    if "size_mode_combo" in step_info and "size_mode" in step_data:
                        step_info["size_mode_combo"].setCurrentText(step_data["size_mode"])
                    if "box_size_spin" in step_info and "box_size" in step_data:
                        step_info["box_size_spin"].setValue(step_data["box_size"])
                    if "box_a_spin" in step_info and "box_a" in step_data:
                        step_info["box_a_spin"].setValue(step_data["box_a"])
                    if "box_x_spin" in step_info and "box_x" in step_data:
                        step_info["box_x_spin"].setValue(step_data["box_x"])
                    if "box_y_spin" in step_info and "box_y" in step_data:
                        step_info["box_y_spin"].setValue(step_data["box_y"])
                    if "box_z_spin" in step_info and "box_z" in step_data:
                        step_info["box_z_spin"].setValue(step_data["box_z"])
                    if "angle_alpha_spin" in step_info and "angle_alpha" in step_data:
                        step_info["angle_alpha_spin"].setValue(step_data["angle_alpha"])
                    if "angle_beta_spin" in step_info and "angle_beta" in step_data:
                        step_info["angle_beta_spin"].setValue(step_data["angle_beta"])
                    if "angle_gamma_spin" in step_info and "angle_gamma" in step_data:
                        step_info["angle_gamma_spin"].setValue(step_data["angle_gamma"])
                    if "center_check" in step_info and "center_check" in step_data:
                        step_info["center_check"].setChecked(step_data["center_check"])
                    if "princ_check" in step_info and "princ_check" in step_data:
                        step_info["princ_check"].setChecked(step_data["princ_check"])
                    if "custom_out_check" in step_info and step_info["custom_out_check"] is not None and "custom_out_check" in step_data:
                        step_info["custom_out_check"].setChecked(step_data["custom_out_check"])
                    if "custom_out_edit" in step_info and step_info["custom_out_edit"] and "custom_out_edit" in step_data:
                        step_info["custom_out_edit"].setText(step_data["custom_out_edit"])
                    if "restart_check" in step_info and step_info["restart_check"] is not None and "restart_check" in step_data:
                        step_info["restart_check"].setChecked(step_data["restart_check"])

            if hasattr(self, 'script_type') and "script_type" in config:
                val = str(config["script_type"])
                idx = self.script_type.findData(val)
                if idx < 0:
                    idx = self.script_type.findText(val)
                if idx >= 0:
                    self.script_type.setCurrentIndex(idx)

            if "language" in config:
                self.set_language(config["language"])

            self.add_log(f"配置已从 {filepath} 加载", "success")
        except Exception as e:
            self.add_log(f"加载配置失败: {str(e)}", "error")
            QMessageBox.critical(self, "错误", f"加载配置失败: {str(e)}")

    def generate_mdp_template(self, mdp_type):
        if hasattr(self, "md_tab"):
            self.md_tab.generate_mdp_template(mdp_type)

    # -------------------------------------------------------------------------
    # Part 3: 高级模拟执行 (已委托至 gui.tabs.advanced_tab.AdvancedTab)
    # -------------------------------------------------------------------------
    def generate_umbrella_mdp(self):
        if hasattr(self, "advanced_tab"):
            self.advanced_tab.generate_umbrella_mdp()

    def run_wham(self):
        if hasattr(self, "advanced_tab"):
            self.advanced_tab.run_wham()

    def generate_plumed_meta(self):
        if hasattr(self, "advanced_tab"):
            self.advanced_tab.generate_plumed_meta()

    def run_metadynamics(self):
        if hasattr(self, "advanced_tab"):
            self.advanced_tab.run_metadynamics()

    def generate_plumed_abf(self):
        if hasattr(self, "advanced_tab"):
            self.advanced_tab.generate_plumed_abf()

    # -------------------------------------------------------------------------
    # Part 5: 分析执行 (已委托至 gui.tabs.analysis_tab.AnalysisTab)
    # -------------------------------------------------------------------------
    def run_analysis(self, key):
        if hasattr(self, "analysis_tab"):
            self.analysis_tab.run_analysis(key)

    # -------------------------------------------------------------------------
    # Part 4: 轨迹预处理流水线方法 (已委托至 gui.tabs.trajectory_tab.TrajectoryTab)
    # -------------------------------------------------------------------------
    def _run_preprocessing_pipeline(self):
        if hasattr(self, "traj_tab"):
            self.traj_tab.run_preprocessing_pipeline()

    # -------------------------------------------------------------------------
    # Part 4: 轨迹处理工具执行 (已委托至 gui.tabs.trajectory_tab.TrajectoryTab)
    # -------------------------------------------------------------------------
    def run_trajectory_tool(self, key):
        if hasattr(self, "traj_tab"):
            self.traj_tab.run_trajectory_tool(key)

    # -------------------------------------------------------------------------
    # Part 2: 结构处理工具执行 (已委托至 gui.tabs.structure_tab.StructureTab)
    # -------------------------------------------------------------------------
    def run_structure_tool(self, key):
        if hasattr(self, "struc_tab"):
            self.struc_tab.run_structure_tool(key)

    # -------------------------------------------------------------------------
    # Part 6: MMPBSA 执行 (已委托至 gui.tabs.mmpbsa_tab.MmpbsaTab)
    # -------------------------------------------------------------------------
    def run_mmpbsa(self):
        if hasattr(self, "mmpbsa_tab"):
            self.mmpbsa_tab.run_mmpbsa()

    # -------------------------------------------------------------------------
    # Part 7: 自定义脚本 (已委托至 gui.tabs.script_tab.ScriptTab)
    # -------------------------------------------------------------------------
    def create_script_tab(self):
        tab = ScriptTab(
            get_work_dir=self._get_work_dir,
            get_gmx_path=lambda: self.gmx_path,
            parent=self
        )
        tab.run_requested.connect(self.run_command)
        tab.log_requested.connect(self.add_log)

        # 暴露原有属性别名，保证 100% 向后兼容旧访问代码与测试
        self.script_type = tab.script_type
        self.script_edit = tab.script_edit
        self.script_save_btn = tab.script_save_btn
        self.script_load_btn = tab.script_load_btn
        self.script_clear_btn = tab.script_clear_btn
        self.script_run_btn = tab.script_run_btn
        self.custom_tmpl_btns = tab.custom_tmpl_btns
        return tab

    def _apply_custom_template(self, template):
        if hasattr(self, "script_tab"):
            self.script_tab.apply_custom_template(template)

    def _on_manage_templates(self):
        if hasattr(self, "script_tab"):
            self.script_tab.manage_templates()

    def _load_script_template(self, key):
        if hasattr(self, "script_tab"):
            self.script_tab.load_script_template(key)

    def _save_script(self):
        if hasattr(self, "script_tab"):
            self.script_tab.save_script()

    def _load_script(self):
        if hasattr(self, "script_tab"):
            self.script_tab.load_script()

    def run_script(self):
        if hasattr(self, "script_tab"):
            self.script_tab.run_script()
