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


from gui.embedded_scripts import DELETE_SOLVENT_SCRIPT, DELETE_ADDITIVE_SCRIPT


from gui.dialogs.custom_template import CustomTemplateDialog


from gui.dialogs.error_diagnosis import ErrorDiagnoser, ErrorDiagnosisDialog


from gui.dialogs.mdp_editor import MdpEditorDialog


from gui.dialogs.simulation_monitor import SimulationMonitorDialog


from gui.workers.gromacs_worker import GromacsWorker


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
        """处理崩溃报告 - 弹出前端提示框"""
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
        self.setGeometry(50, 50, 1200, 750)
        self.setMinimumSize(800, 600)

        # 设置窗口图标
        icon_path = self._get_icon_path()
        if icon_path:
            app = QApplication.instance()
            app.setWindowIcon(QIcon(icon_path))
            self.setWindowIcon(QIcon(icon_path))

        # 全局字体设置 - 统一字体大小，提升可读性
        app = QApplication.instance()
        base_font = QFont("Microsoft YaHei", 10)
        base_font.setStyleStrategy(QFont.PreferAntialias)
        app.setFont(base_font)

        # 全局样式表 - 统一控件外观
        app.setStyleSheet("""
            QToolTip {
                background-color: #2B2B2B;
                color: #FFFFFF;
                border: 1px solid #555;
                padding: 4px;
                border-radius: 4px;
                font-size: 12px;
            }
            QTabWidget::pane {
                border: 1px solid #555;
                border-radius: 4px;
                top: -1px;
            }
            QTabBar::tab {
                background-color: #3A3A3A;
                color: #BBB;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-weight: bold;
                font-size: 10pt;
                min-height: 28px;
                min-width: 115px;
            }
            QTabBar::tab:selected {
                background-color: #2A82DA;
                color: white;
            }
            QTabBar::tab:hover:!selected {
                background-color: #4A4A4A;
                color: #DDD;
            }
            QGroupBox {
                font-weight: bold;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 6px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 6px;
            }
            QPushButton {
                border-radius: 4px;
                padding: 5px 12px;
                font-weight: bold;
            }
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                padding: 4px 6px;
                border-radius: 4px;
                border: 1px solid #666;
            }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
                border: 1px solid #2A82DA;
            }
            QScrollArea {
                border: none;
            }
        """)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(8, 8, 8, 8)

        self.create_top_bar(main_layout)

        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter, stretch=1)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self.tab_widget = QTabWidget()
        self.tab_widget.addTab(self.create_md_tab(), "Part 1: MD模拟")
        self.tab_widget.addTab(self.create_structure_tab(), "Part 2: 结构处理")
        self.tab_widget.addTab(self.create_advanced_tab(), "Part 3: 高级模拟")
        self.tab_widget.addTab(self.create_trajectory_tab(), "Part 4: 轨迹处理")
        self.tab_widget.addTab(self.create_analysis_tab(), "Part 5: 结果分析")
        self.tab_widget.addTab(self.create_mmpbsa_tab(), "Part 6: MMPBSA")
        self.tab_widget.addTab(self.create_script_tab(), "Part 7: 自定义脚本")
        left_layout.addWidget(self.tab_widget)
        splitter.addWidget(left_panel)

        right_panel = self.create_right_panel()
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([720, 480])

        self.statusBar().showMessage("就绪")

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
    # 顶部工具栏
    # -------------------------------------------------------------------------
    def create_top_bar(self, parent_layout):
        def create_colored_button(text, color_hex, hover_hex=None, disabled_hex=None):
            btn = QPushButton(text)
            if hover_hex is None:
                hover_hex = self._adjust_brightness(color_hex, 1.1)
            if disabled_hex is None:
                disabled_hex = self._adjust_brightness(color_hex, 0.6)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color_hex};
                    color: white;
                    font-weight: bold;
                    min-height: 32px;
                    padding: 6px 16px;
                    border-radius: 6px;
                    border: none;
                }}
                QPushButton:hover {{
                    background-color: {hover_hex};
                }}
                QPushButton:pressed {{
                    background-color: {self._adjust_brightness(color_hex, 0.9)};
                }}
                QPushButton:disabled {{
                    background-color: {disabled_hex};
                    color: #e0e0e0;
                }}
            """)
            return btn

        # ============================================================
        # 第一行: 顶部操作栏
        # 左侧: 应用图标 + 标题
        # 右侧: 8个彩色功能按钮
        # ============================================================
        bar1 = QHBoxLayout()
        bar1.setSpacing(10)

        # 左侧: 应用标题
        title_layout = QHBoxLayout()
        title_layout.setSpacing(10)

        title_icon = QLabel()
        title_icon.setFixedSize(36, 36)
        title_icon.setStyleSheet("""
            QLabel {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #2196F3, stop:1 #00BCD4);
                border-radius: 8px;
            }
        """)
        title_icon.setAlignment(Qt.AlignCenter)
        title_icon.setText("🧬")
        title_icon.setFont(QFont("Arial", 18))

        title_label = QLabel(f"{VERSION_CONFIG['display_name']} {VERSION_CONFIG['full_version']}")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #1565C0;
            }
        """)

        title_layout.addWidget(title_icon)
        title_layout.addWidget(title_label)
        title_layout.addStretch(1)
        bar1.addLayout(title_layout, stretch=1)

        # 右侧: 8个彩色功能按钮
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(8)

        self.run_all_btn = create_colored_button("一键运行全部", "#4CAF50")
        self.run_all_btn.clicked.connect(self.run_all_md)
        self.run_all_btn.setToolTip("一键执行完整的分子动力学模拟流程")

        self.stop_btn = create_colored_button("停止运行", "#F44336")
        self.stop_btn.clicked.connect(self.stop_run)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setToolTip("停止当前正在运行的任务")

        self.mdp_editor_btn = create_colored_button("MDP编辑器", "#9C27B0")
        self.mdp_editor_btn.clicked.connect(self.open_mdp_editor)
        self.mdp_editor_btn.setToolTip("打开高级MDP参数可视化编辑器")

        self.monitor_btn = create_colored_button("实时监控", "#00BCD4")
        self.monitor_btn.clicked.connect(self.open_monitor)
        self.monitor_btn.setToolTip("打开实时模拟监控面板（温度/压力/能量曲线）")

        self.save_config_btn = create_colored_button("保存配置", "#FF9800")
        self.save_config_btn.clicked.connect(self.save_config)
        self.save_config_btn.setToolTip("保存当前所有配置参数到JSON文件")

        self.load_config_btn = create_colored_button("加载配置", "#2196F3")
        self.load_config_btn.clicked.connect(self.load_config)
        self.load_config_btn.setToolTip("从JSON文件加载配置参数")

        self.theme_btn = create_colored_button("主题切换", "#607D8B")
        self.theme_btn.clicked.connect(self.toggle_theme)
        self.theme_btn.setToolTip("切换深色/浅色主题")

        self.version_btn = create_colored_button("版本信息", "#9E9E9E")
        self.version_btn.clicked.connect(self.show_version)
        self.version_btn.setToolTip("查看软件版本和系统信息")

        self.cleanup_btn = create_colored_button("系统清理", "#795548")
        self.cleanup_btn.clicked.connect(self._on_system_cleanup)
        self.cleanup_btn.setToolTip("一键清理缓存、日志和废弃临时文件")

        buttons_layout.addWidget(self.run_all_btn)
        buttons_layout.addWidget(self.stop_btn)
        buttons_layout.addWidget(self.mdp_editor_btn)
        buttons_layout.addWidget(self.monitor_btn)
        buttons_layout.addWidget(self.save_config_btn)
        buttons_layout.addWidget(self.load_config_btn)
        buttons_layout.addWidget(self.theme_btn)
        buttons_layout.addWidget(self.version_btn)
        buttons_layout.addWidget(self.cleanup_btn)

        self.log_btn = create_colored_button("日志目录", "#607D8B")
        self.log_btn.clicked.connect(self._on_open_log_dir)
        self.log_btn.setToolTip("打开分级日志目录\nERROR日志永久保留，其他级别按天数自动清理")
        buttons_layout.addWidget(self.log_btn)

        bar1.addLayout(buttons_layout)
        parent_layout.addLayout(bar1)

        # ============================================================
        # 第二行: 系统配置栏
        # 左侧: GROMACS版本 + 计算资源 + GPU加速
        # 右侧: 工作目录
        # ============================================================
        bar2 = QHBoxLayout()
        bar2.setSpacing(10)

        # 左侧: 系统配置组
        sys_config_group = QGroupBox("系统配置")
        sys_config_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #1565C0;
                border: 1px solid #BBDEFB;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 4px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        sys_config_layout = QHBoxLayout(sys_config_group)
        sys_config_layout.setSpacing(15)

        # GROMACS版本区域 - 使用网格布局避免小屏幕重叠
        ver_grid = QGridLayout()
        ver_grid.setSpacing(6)
        
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
        self.ver_combo.setMinimumWidth(150)
        
        self.gmx_browse_btn = QPushButton("浏览...")
        self.gmx_browse_btn.setToolTip("手动选择GROMACS的gmx.exe文件位置\n如果程序未自动检测到GROMACS，请点击此按钮")
        self.gmx_browse_btn.clicked.connect(self._browse_gmx_exe)
        
        self.show_all_versions_cb = QCheckBox("显示所有版本")
        self.show_all_versions_cb.setToolTip("显示所有目录，包括无效和重复版本")
        self.show_all_versions_cb.setChecked(True)
        self.show_all_versions_cb.stateChanged.connect(self._on_show_all_versions_changed)
        
        self.version_mgmt_btn = QPushButton("版本管理")
        self.version_mgmt_btn.setToolTip("批量导入/导出GROMACS版本")
        self.version_mgmt_btn.setMaximumWidth(70)
        self.version_mgmt_btn.clicked.connect(self._on_version_management)
        
        self.open_update_pkg_btn = QPushButton("更新包")
        self.open_update_pkg_btn.setToolTip("打开更新包目录\n支持手动拖拽ZIP文件进行增量/全量更新")
        self.open_update_pkg_btn.setMaximumWidth(55)
        self.open_update_pkg_btn.clicked.connect(self._on_open_update_packages)
        
        ver_grid.addWidget(QLabel("GROMACS版本:"), 0, 0)
        ver_grid.addWidget(self.ver_combo, 0, 1, 1, 2)
        ver_grid.addWidget(self.gmx_browse_btn, 0, 3)
        ver_grid.addWidget(self.show_all_versions_cb, 1, 0)
        ver_grid.addWidget(self.version_mgmt_btn, 1, 1)
        ver_grid.addWidget(self.open_update_pkg_btn, 1, 2)
        
        sys_config_layout.addLayout(ver_grid)

        line1 = QFrame()
        line1.setFrameShape(QFrame.VLine)
        line1.setStyleSheet("color: #E0E0E0;")
        sys_config_layout.addWidget(line1)

        # 计算资源
        cpu_layout = QHBoxLayout()
        cpu_layout.setSpacing(6)
        self.cfg_nt = QSpinBox()
        safe_cores = min(8, self.sys_cpu_cores)
        self.cfg_nt.setRange(1, self.sys_cpu_cores)
        self.cfg_nt.setValue(safe_cores)
        self.cfg_nt.setSuffix(" 核")
        self.cfg_nt.setToolTip(f"本机检测到 {self.sys_cpu_cores} 个逻辑核心\n"
                               f"默认使用 {safe_cores} 核\n"
                               f"建议GPU加速时使用4-12核，CPU主要负责I/O和调度\n"
                               f"对于Ryzen 9700X等8核CPU，推荐使用8-12线程")
        self.cfg_mem_label = QLabel(f"总内存: {self.sys_memory_gb} GB")
        self.cfg_mem_label.setStyleSheet("color: #666;")
        self.cfg_mem_limit = QCheckBox("内存限制")
        self.cfg_mem_limit.setChecked(False)
        self.cfg_mem_limit.setToolTip(
            "限制GROMACS进程使用的系统内存(RAM)，防止系统卡死\n"
            "注意：GPU显存(VRAM)不受此限制，由GROMACS自动分配\n"
            "  - GPU显存：存放原子坐标、力场参数、PME网格等计算数据\n"
            "  - 系统内存：grompp预处理、轨迹写入、I/O缓存等\n"
            f"本机总内存: {self.sys_memory_gb} GB")
        self.cfg_mem_value = QDoubleSpinBox()
        # 范围：0.5 GB ~ 系统总内存，默认8 GB
        mem_default = min(8.0, float(self.sys_memory_gb))
        self.cfg_mem_value.setRange(0.5, float(self.sys_memory_gb))
        self.cfg_mem_value.setSuffix(" GB")
        self.cfg_mem_value.setValue(mem_default)
        self.cfg_mem_value.setSingleStep(0.5)
        self.cfg_mem_value.setDecimals(1)
        self.cfg_mem_value.setEnabled(False)
        self.cfg_mem_value.setToolTip(
            f"可选范围: 0.5 ~ {self.sys_memory_gb} GB\n"
            f"默认值: {mem_default} GB\n"
            "超过此限制的GROMACS进程会被系统终止")
        self.cfg_mem_limit.toggled.connect(self.cfg_mem_value.setEnabled)
        cpu_layout.addWidget(QLabel("线程数(-nt):"))
        cpu_layout.addWidget(self.cfg_nt)
        cpu_layout.addSpacing(10)
        cpu_layout.addWidget(self.cfg_mem_label)
        cpu_layout.addSpacing(10)
        cpu_layout.addWidget(self.cfg_mem_limit)
        cpu_layout.addWidget(self.cfg_mem_value)
        sys_config_layout.addLayout(cpu_layout)

        # 分隔线
        line2 = QFrame()
        line2.setFrameShape(QFrame.VLine)
        line2.setStyleSheet("color: #E0E0E0;")
        sys_config_layout.addWidget(line2)

        # GPU加速
        gpu_layout = QHBoxLayout()
        gpu_layout.setSpacing(6)
        self.cfg_gpu = QCheckBox("启用GPU")
        if self.sys_gpu_info["available"]:
            self.cfg_gpu.setChecked(True)
            gpu_names = ", ".join(self.sys_gpu_info["names"][:2])
            gpu_mems = ", ".join(self.sys_gpu_info["memories"][:2])
            self.cfg_gpu.setToolTip(f"GPU: {gpu_names}\n显存: {gpu_mems}\n驱动: {self.sys_gpu_info['driver']}\n{self.sys_gpu_info['cuda_version']}")
        else:
            self.cfg_gpu.setChecked(False)
            self.cfg_gpu.setEnabled(False)
            self.cfg_gpu.setToolTip("未检测到NVIDIA GPU")
        gpu_layout.addWidget(self.cfg_gpu)

        self.cfg_gpu_id = QComboBox()
        self.cfg_gpu_id.setEnabled(False)
        if self.sys_gpu_info["available"]:
            for i, name in enumerate(self.sys_gpu_info["names"]):
                self.cfg_gpu_id.addItem(f"GPU {i}: {name}", i)
            self.cfg_gpu_id.setEnabled(True)
        gpu_layout.addWidget(QLabel("GPU ID:"))
        gpu_layout.addWidget(self.cfg_gpu_id)

        self.cfg_gpu_auto = QCheckBox("自动模式")
        self.cfg_gpu_auto.setChecked(True)
        self.cfg_gpu_auto.setToolTip("自动模式: GROMACS自行决定最佳GPU/CPU分配")
        gpu_layout.addWidget(self.cfg_gpu_auto)
        
        self.gpu_diagnose_btn = QPushButton("GPU诊断")
        self.gpu_diagnose_btn.setToolTip("检测GPU加速是否正确配置，诊断可能的问题")
        self.gpu_diagnose_btn.clicked.connect(self._on_gpu_diagnose)
        gpu_layout.addWidget(self.gpu_diagnose_btn)
        
        sys_config_layout.addLayout(gpu_layout)

        bar2.addWidget(sys_config_group, stretch=2)

        # 右侧: 工作目录
        path_group = QGroupBox("工作目录")
        path_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #2E7D32;
                border: 1px solid #C8E6C9;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 4px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        path_layout = QHBoxLayout(path_group)
        path_layout.setSpacing(8)
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("请选择或输入工作目录...")
        self.path_edit.setStyleSheet("""
            QLineEdit {
                padding: 6px 10px;
                border: 1px solid #BDBDBD;
                border-radius: 4px;
                min-height: 24px;
            }
            QLineEdit:focus {
                border-color: #2196F3;
            }
        """)
        self.browse_btn = QPushButton("浏览...")
        self.browse_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-weight: bold;
                min-height: 32px;
                padding: 6px 16px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #1565C0;
            }
        """)
        self.browse_btn.clicked.connect(self.browse_directory)
        path_layout.addWidget(QLabel("路径:"))
        path_layout.addWidget(self.path_edit, stretch=1)
        path_layout.addWidget(self.browse_btn)
        bar2.addWidget(path_group, stretch=3)

        parent_layout.addLayout(bar2)

    # -------------------------------------------------------------------------
    # Part 1: 分子动力学模拟
    # -------------------------------------------------------------------------
    def create_md_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        vbox = QVBoxLayout(content)
        vbox.setSpacing(12)
        vbox.setContentsMargins(8, 10, 8, 10)

        common_group = QGroupBox("全局模拟参数")
        common_group.setStyleSheet("QGroupBox { font-weight: bold; color: #1565C0; }")
        ggrid = QGridLayout(common_group)
        ggrid.setSpacing(6)

        self.md_ff = QComboBox()
        self.md_ff.addItems([
            "amber03", "amber94", "amber96", "amber99", "amber99sb",
            "amber99sb-ildn", "amberGS", "amber14sb", "amber19sb",
            "charmm27", "gromos43a1", "gromos43a2", "gromos45a3",
            "gromos53a5", "gromos53a6", "gromos54a7", "oplsaa",
            "gaff (AmberTools-需预处理)", "gaff2 (AmberTools-需预处理)"
        ])

        self.md_water = QComboBox()
        self.md_water.addItems(["spc", "spce", "tip3p", "tip4p", "tip4pew", "tip5p", "opc", "opc3"])

        self.md_box_type = QComboBox()
        self.md_box_type.addItems(["cubic (立方体)", "triclinic (三斜)", "dodecahedron (十二面体)", "octahedron (八面体)", "rectangular (长方体)"])
        self.md_box_type.currentTextChanged.connect(self._on_box_type_changed)

        self.md_box_size_mode = QComboBox()
        self.md_box_size_mode.addItems(["按边距 (-d)", "按盒子边长 (-box)"])
        self.md_box_size_mode.currentTextChanged.connect(self._on_box_size_mode_changed)

        self.md_box_size = QDoubleSpinBox()
        self.md_box_size.setRange(0.5, 50.0)
        self.md_box_size.setValue(1.0)
        self.md_box_size.setDecimals(2)
        self.md_box_size.setSuffix(" nm")

        self.md_box_a = QDoubleSpinBox()
        self.md_box_a.setRange(0.1, 500.0)
        self.md_box_a.setValue(5.0)
        self.md_box_a.setDecimals(2)
        self.md_box_a.setSuffix(" nm")
        self.md_box_a.setVisible(False)

        self.md_box_x = QDoubleSpinBox()
        self.md_box_x.setRange(0.5, 500.0)
        self.md_box_x.setValue(1.0)
        self.md_box_x.setDecimals(2)
        self.md_box_x.setSuffix(" nm")
        self.md_box_x.setVisible(False)

        self.md_box_y = QDoubleSpinBox()
        self.md_box_y.setRange(0.5, 500.0)
        self.md_box_y.setValue(1.5)
        self.md_box_y.setDecimals(2)
        self.md_box_y.setSuffix(" nm")
        self.md_box_y.setVisible(False)

        self.md_box_z = QDoubleSpinBox()
        self.md_box_z.setRange(0.5, 500.0)
        self.md_box_z.setValue(2.0)
        self.md_box_z.setDecimals(2)
        self.md_box_z.setSuffix(" nm")
        self.md_box_z.setVisible(False)

        self.md_angle_alpha = QDoubleSpinBox()
        self.md_angle_alpha.setRange(1.0, 179.0)
        self.md_angle_alpha.setValue(90.0)
        self.md_angle_alpha.setDecimals(1)
        self.md_angle_alpha.setSuffix(" °")
        self.md_angle_alpha.setVisible(False)

        self.md_angle_beta = QDoubleSpinBox()
        self.md_angle_beta.setRange(1.0, 179.0)
        self.md_angle_beta.setValue(90.0)
        self.md_angle_beta.setDecimals(1)
        self.md_angle_beta.setSuffix(" °")
        self.md_angle_beta.setVisible(False)

        self.md_angle_gamma = QDoubleSpinBox()
        self.md_angle_gamma.setRange(1.0, 179.0)
        self.md_angle_gamma.setValue(90.0)
        self.md_angle_gamma.setDecimals(1)
        self.md_angle_gamma.setSuffix(" °")
        self.md_angle_gamma.setVisible(False)

        self.md_princ = QCheckBox("主惯性轴对齐 (-princ)")
        self.md_princ.setChecked(False)
        self.md_princ.setToolTip("将蛋白质对齐到主惯性轴，使盒子更紧凑")

        self.md_ion_conc = QDoubleSpinBox()
        self.md_ion_conc.setRange(0.0, 5.0)
        self.md_ion_conc.setValue(0.15)
        self.md_ion_conc.setDecimals(3)
        self.md_ion_conc.setSuffix(" M")

        self.md_temp = QDoubleSpinBox()
        self.md_temp.setRange(1.0, 1000.0)
        self.md_temp.setValue(300.0)
        self.md_temp.setDecimals(1)
        self.md_temp.setSuffix(" K")

        self.md_pressure = QDoubleSpinBox()
        self.md_pressure.setRange(0.1, 100000.0)
        self.md_pressure.setValue(1.0)
        self.md_pressure.setDecimals(2)
        self.md_pressure.setSuffix(" bar")

        self.md_dt = QDoubleSpinBox()
        self.md_dt.setRange(0.0001, 0.01)
        self.md_dt.setValue(0.002)
        self.md_dt.setDecimals(4)
        self.md_dt.setSuffix(" ps")

        self.md_nsteps = QSpinBox()
        self.md_nsteps.setRange(100, 500000000)
        self.md_nsteps.setValue(50000000)
        self.md_nsteps.setSingleStep(100000)

        self.md_engine = QComboBox()
        self.md_engine.addItems(["auto", "gpu", "cpu"])
        # 根据GPU检测设置默认引擎
        default_engine = "gpu" if self.sys_gpu_info["available"] else "cpu"
        self.md_engine.setCurrentText(default_engine)

        self.md_nt = QSpinBox()
        safe_cores = min(6, self.sys_cpu_cores)
        self.md_nt.setRange(1, self.sys_cpu_cores)
        self.md_nt.setValue(safe_cores)
        self.md_nt.setToolTip(f"建议GPU加速时使用4-12核，本机检测到{self.sys_cpu_cores}个逻辑核心")

        self.md_pdb, md_pdb_layout = self._create_file_input(
            "protein.pdb", "protein.pdb",
            "PDB文件 (*.pdb *.gro);;所有文件 (*.*)",
            "选择输入PDB/GRO文件"
        )

        ggrid.addWidget(QLabel("力场:"), 0, 0)
        self.lbl_ff = ggrid.itemAtPosition(0, 0).widget()
        ggrid.addWidget(self.md_ff, 0, 1)
        ggrid.addWidget(QLabel("水模型:"), 0, 2)
        self.lbl_water = ggrid.itemAtPosition(0, 2).widget()
        ggrid.addWidget(self.md_water, 0, 3)

        ggrid.addWidget(QLabel("盒子类型:"), 1, 0)
        self.lbl_box_type = ggrid.itemAtPosition(1, 0).widget()
        ggrid.addWidget(self.md_box_type, 1, 1)
        ggrid.addWidget(QLabel("设置方式:"), 1, 2)
        ggrid.addWidget(self.md_box_size_mode, 1, 3)

        self.lbl_box_size = QLabel("盒子边距:")
        ggrid.addWidget(self.lbl_box_size, 6, 0)
        ggrid.addWidget(self.md_box_size, 6, 1, 1, 3)

        self.lbl_box_a = QLabel("盒子边长:")
        self.lbl_box_a.setVisible(False)
        ggrid.addWidget(self.lbl_box_a, 7, 0)
        self.md_box_a.setVisible(False)
        ggrid.addWidget(self.md_box_a, 7, 1, 1, 3)

        self.lbl_box_x = QLabel("X边长:")
        self.lbl_box_x.setVisible(False)
        ggrid.addWidget(self.lbl_box_x, 8, 0)
        self.md_box_x.setVisible(False)
        ggrid.addWidget(self.md_box_x, 8, 1)
        self.lbl_box_y = QLabel("Y边长:")
        self.lbl_box_y.setVisible(False)
        ggrid.addWidget(self.lbl_box_y, 8, 2)
        self.md_box_y.setVisible(False)
        ggrid.addWidget(self.md_box_y, 8, 3)

        self.lbl_box_z = QLabel("Z边长:")
        self.lbl_box_z.setVisible(False)
        ggrid.addWidget(self.lbl_box_z, 9, 0)
        self.md_box_z.setVisible(False)
        ggrid.addWidget(self.md_box_z, 9, 1)

        self.lbl_angle_alpha = QLabel("夹角α (bc):")
        self.lbl_angle_alpha.setVisible(False)
        ggrid.addWidget(self.lbl_angle_alpha, 10, 0)
        self.md_angle_alpha.setVisible(False)
        ggrid.addWidget(self.md_angle_alpha, 10, 1)
        self.lbl_angle_beta = QLabel("夹角β (ac):")
        self.lbl_angle_beta.setVisible(False)
        ggrid.addWidget(self.lbl_angle_beta, 10, 2)
        self.md_angle_beta.setVisible(False)
        ggrid.addWidget(self.md_angle_beta, 10, 3)

        self.lbl_angle_gamma = QLabel("夹角γ (ab):")
        self.lbl_angle_gamma.setVisible(False)
        ggrid.addWidget(self.lbl_angle_gamma, 11, 0)
        self.md_angle_gamma.setVisible(False)
        ggrid.addWidget(self.md_angle_gamma, 11, 1)
        ggrid.addWidget(self.md_princ, 11, 2, 1, 2)

        self.use_existing_top = QCheckBox("使用已有拓扑")
        self.use_existing_top.setChecked(False)
        self.use_existing_top.setToolTip("跳过pdb2gmx，直接使用已有的gro和top文件")
        ggrid.addWidget(self.use_existing_top, 12, 0, 1, 2)

        self.skip_solvate = QCheckBox("跳过溶剂化")
        self.skip_solvate.setChecked(False)
        self.skip_solvate.setToolTip("体系已包含溶剂，跳过solvate步骤")
        ggrid.addWidget(self.skip_solvate, 13, 0)

        self.skip_genion = QCheckBox("跳过加离子")
        self.skip_genion.setChecked(False)
        self.skip_genion.setToolTip("体系已带电平衡，跳过genion步骤")
        ggrid.addWidget(self.skip_genion, 13, 1)

        self.skip_editconf = QCheckBox("跳过盒子定义")
        self.skip_editconf.setChecked(False)
        self.skip_editconf.setToolTip("结构文件已有周期性盒子信息，跳过editconf步骤")
        ggrid.addWidget(self.skip_editconf, 14, 0)

        ggrid.addWidget(QLabel("离子浓度:"), 2, 0)
        self.lbl_ion = ggrid.itemAtPosition(2, 0).widget()
        ggrid.addWidget(self.md_ion_conc, 2, 1)
        ggrid.addWidget(QLabel("温度:"), 2, 2)
        ggrid.addWidget(self.md_temp, 2, 3)

        ggrid.addWidget(QLabel("压力:"), 3, 0)
        ggrid.addWidget(self.md_pressure, 3, 1)
        ggrid.addWidget(QLabel("积分步长:"), 3, 2)
        ggrid.addWidget(self.md_dt, 3, 3)

        ggrid.addWidget(QLabel("模拟步数:"), 4, 0)
        ggrid.addWidget(self.md_nsteps, 4, 1)
        ggrid.addWidget(QLabel("计算引擎:"), 4, 2)
        ggrid.addWidget(self.md_engine, 4, 3)

        ggrid.addWidget(QLabel("线程数:"), 5, 0)
        ggrid.addWidget(self.md_nt, 5, 1)
        ggrid.addWidget(QLabel("输入PDB:"), 5, 2)
        self.lbl_pdb = ggrid.itemAtPosition(5, 2).widget()
        ggrid.addLayout(md_pdb_layout, 5, 3)

        vbox.addWidget(common_group)

        self.md_step_btns = {}

        # === 第一阶段: 结构准备 ===
        prep_phase = QGroupBox("📦 第一阶段: 结构准备 (Step 1-4)")
        prep_phase.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #6A1B9A;
                margin-top: 8px;
                padding-top: 8px;
                border: 2px solid #7B1FA2;
                border-radius: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        prep_layout = QVBoxLayout(prep_phase)
        prep_layout.setSpacing(6)

        step1 = self._create_step_group(
            "Step 1: 生成拓扑 (pdb2gmx)",
            "从 PDB 文件生成拓扑结构",
            ["输入PDB:", "输出GRO:", "拓扑TOP:", "位置限制ITP:"],
            ["protein.gro", "topol.top", "posre.itp"]
        )
        self.step1_widget = step1
        prep_layout.addWidget(step1)

        self.step1_existing = QGroupBox("Step 1: 使用已有拓扑")
        self.step1_existing.setStyleSheet("QGroupBox { font-weight: bold; color: #2E7D32; margin-top: 8px; }")
        self.step1_existing.setVisible(False)
        se_layout = QGridLayout(self.step1_existing)
        se_layout.setSpacing(6)
        desc_se = QLabel("直接使用已有的结构和拓扑文件，跳过pdb2gmx")
        desc_se.setStyleSheet("color: #555;")
        se_layout.addWidget(desc_se, 0, 0, 1, 4)

        se_layout.addWidget(QLabel("输入结构:"), 1, 0)
        self.se_gro_edit, se_gro_layout = self._create_file_input("选择已有结构文件", "input.gro", "结构文件 (*.gro *.pdb)", "选择GRO/PDB文件")
        se_layout.addLayout(se_gro_layout, 1, 1, 1, 3)

        se_layout.addWidget(QLabel("输入TOP:"), 2, 0)
        self.se_top_edit, se_top_layout = self._create_file_input("选择已有拓扑文件", "topol.top", "拓扑文件 (*.top)", "选择TOP文件")
        se_layout.addLayout(se_top_layout, 2, 1, 1, 3)

        self.se_run_btn = QPushButton("确认使用已有拓扑")
        self.se_run_btn.setStyleSheet(
            "QPushButton { background-color: #2196F3; color: white; font-weight: bold; padding: 4px 12px; }"
            "QPushButton:hover { background-color: #1976D2; }"
        )
        self.se_run_btn.clicked.connect(lambda: self.run_md_step("Step 1"))
        se_layout.addWidget(self.se_run_btn, 3, 0, 1, 4)

        prep_layout.addWidget(self.step1_existing)

        self.use_existing_top.toggled.connect(self._on_use_existing_toggled)
        self.skip_editconf.toggled.connect(self._on_skip_toggled)
        self.skip_solvate.toggled.connect(self._on_skip_toggled)
        self.skip_genion.toggled.connect(self._on_skip_toggled)

        step2 = self._create_editconf_step()
        prep_layout.addWidget(step2)

        step3 = self._create_step_group(
            "Step 3: 溶剂化 (solvate)",
            "向盒子中添加溶剂水分子",
            ["输入GRO:", "输出GRO:", "输出TOP:"],
            ["protein_solv.gro", "topol.top"]
        )
        prep_layout.addWidget(step3)

        step4 = self._create_step_group(
            "Step 4: 添加离子 (genion)",
            "用离子替换溶剂分子以中和体系",
            ["输入GRO:", "输出GRO:", "输出TOP:", "输入MDP:"],
            ["protein_ions.gro", "topol.top", "ions.mdp"]
        )
        prep_layout.addWidget(step4)

        vbox.addWidget(prep_phase)

        # === 第二阶段: 能量最小化 ===
        em_phase = QGroupBox("⚡ 第二阶段: 能量最小化 (Step 5-6)")
        em_phase.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #E65100;
                margin-top: 8px;
                padding-top: 8px;
                border: 2px solid #EF6C00;
                border-radius: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        em_layout = QVBoxLayout(em_phase)
        em_layout.setSpacing(6)

        step5 = self._create_step_group(
            "Step 5: grompp (EM)",
            "编译能量最小化输入文件",
            ["输入MDP:", "输入GRO:", "输出TPR:"],
            ["em.mdp", "ions.gro", "em.tpr"]
        )
        em_layout.addWidget(step5)

        step6 = self._create_step_group(
            "Step 6: 能量最小化 (mdrun EM)",
            "执行能量最小化消除不良接触",
            ["输入TPR:", "输出GRO:", "输出EDR:", "输出LOG:"],
            ["em.tpr", "em.gro", "em.edr", "em.log"]
        )
        em_layout.addWidget(step6)

        vbox.addWidget(em_phase)

        # === 第三阶段: 平衡模拟 ===
        equil_phase = QGroupBox("⚖️ 第三阶段: 平衡模拟 (Step 7-10)")
        equil_phase.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #00695C;
                margin-top: 8px;
                padding-top: 8px;
                border: 2px solid #00796B;
                border-radius: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        equil_layout = QVBoxLayout(equil_phase)
        equil_layout.setSpacing(6)

        step7 = self._create_step_group(
            "Step 7: grompp (NVT)",
            "编译NVT平衡输入文件",
            ["输入MDP:", "输入GRO:", "输出TPR:"],
            ["nvt.mdp", "em.gro", "nvt.tpr"]
        )
        equil_layout.addWidget(step7)

        step8 = self._create_step_group(
            "Step 8: NVT 平衡 (mdrun NVT)",
            "恒定体积和温度下平衡",
            ["输入TPR:", "输出TRR/XTC:", "输出EDR:", "输出LOG:"],
            ["nvt.tpr", "nvt.xtc", "nvt.edr", "nvt.log"]
        )
        equil_layout.addWidget(step8)

        step9 = self._create_step_group(
            "Step 9: grompp (NPT)",
            "编译NPT平衡输入文件",
            ["输入MDP:", "输入GRO/CPR:", "输出TPR:"],
            ["npt.mdp", "nvt.gro", "npt.tpr"]
        )
        equil_layout.addWidget(step9)

        step10 = self._create_step_group(
            "Step 10: NPT 平衡 (mdrun NPT)",
            "恒定压力和温度下平衡",
            ["输入TPR:", "输出TRR/XTC:", "输出EDR:", "输出LOG:"],
            ["npt.tpr", "npt.xtc", "npt.edr", "npt.log"]
        )
        equil_layout.addWidget(step10)

        vbox.addWidget(equil_phase)

        # === 第四阶段: 生产模拟 ===
        prod_phase = QGroupBox("🚀 第四阶段: 生产模拟 (Step 11-12)")
        prod_phase.setStyleSheet("""
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
        prod_layout = QVBoxLayout(prod_phase)
        prod_layout.setSpacing(6)

        step11 = self._create_step_group(
            "Step 11: grompp (MD)",
            "编译生产模拟输入文件",
            ["输入MDP:", "输入GRO/CPR:", "输出TPR:"],
            ["md.mdp", "npt.gro", "md.tpr"]
        )
        prod_layout.addWidget(step11)

        step12 = self._create_step_group(
            "Step 12: 生产模拟 (mdrun MD)",
            "执行最终生产模拟",
            ["输入TPR:", "输出TRR/XTC:", "输出EDR:", "输出LOG:"],
            ["md.tpr", "md.xtc", "md.edr", "md.log"]
        )
        prod_layout.addWidget(step12)

        vbox.addWidget(prod_phase)

        # === 第五阶段: 溶剂/添加剂蒸发 ===
        evap_phase = QGroupBox("🔥 第五阶段: 溶剂/添加剂蒸发")
        evap_phase.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #BF360C;
                margin-top: 8px;
                padding-top: 8px;
                border: 2px solid #D84315;
                border-radius: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        evap_layout = QVBoxLayout(evap_phase)
        evap_layout.setSpacing(8)

        # 蒸发配置
        evap_config = QGroupBox("蒸发配置")
        evap_grid = QGridLayout(evap_config)
        evap_grid.setSpacing(6)

        # 模式选择
        evap_grid.addWidget(QLabel("蒸发模式:"), 0, 0)
        self.evap_mode = QComboBox()
        self.evap_mode.addItems(["分批蒸发溶剂（循环删除+NPT）", "一次性删除全部添加剂"])
        evap_grid.addWidget(self.evap_mode, 0, 1, 1, 3)

        # 输入GRO
        evap_grid.addWidget(QLabel("输入GRO:"), 1, 0)
        self.evap_gro_edit, gro_layout = self._create_file_input("输入GRO文件", "npt2.gro", "结构文件 (*.gro *.pdb);;所有文件 (*.*)", "选择GRO文件")
        evap_grid.addLayout(gro_layout, 1, 1, 1, 3)

        # 拓扑TOP
        evap_grid.addWidget(QLabel("拓扑TOP:"), 2, 0)
        self.evap_top_edit, top_layout = self._create_file_input("拓扑TOP文件", "topol.top", "拓扑文件 (*.top *.itp);;所有文件 (*.*)", "选择TOP文件")
        evap_grid.addLayout(top_layout, 2, 1, 1, 3)

        # MDP文件
        evap_grid.addWidget(QLabel("MDP文件:"), 3, 0)
        self.evap_mdp_edit, mdp_layout = self._create_file_input("NPT参数文件(MDP)", "npt-sa.mdp", "MDP文件 (*.mdp);;所有文件 (*.*)", "选择MDP文件")
        evap_grid.addLayout(mdp_layout, 3, 1, 1, 3)

        # 残基名 + 原子数
        evap_grid.addWidget(QLabel("残基名:"), 4, 0)
        self.evap_resname = QLineEdit("CF")
        self.evap_resname.setFixedWidth(80)
        evap_grid.addWidget(self.evap_resname, 4, 1)

        evap_grid.addWidget(QLabel("原子数/分子:"), 4, 2)
        self.evap_atoms_per_mol = QSpinBox()
        self.evap_atoms_per_mol.setRange(1, 1000)
        self.evap_atoms_per_mol.setValue(5)
        evap_grid.addWidget(self.evap_atoms_per_mol, 4, 3)

        # 蒸发来源（新增）
        evap_grid.addWidget(QLabel("蒸发来源:"), 5, 0)
        self.evap_source = QComboBox()
        self.evap_source.addItems(["从底部删除（先蒸发最底下的组）", "从顶部删除（先蒸发最上面的组）"])
        evap_grid.addWidget(self.evap_source, 5, 1, 1, 3)

        # 分批模式参数
        self.evap_label_delete = QLabel("每轮删除数:")
        evap_grid.addWidget(self.evap_label_delete, 6, 0)
        self.evap_delete_num = QSpinBox()
        self.evap_delete_num.setRange(1, 100000)
        self.evap_delete_num.setValue(100)
        evap_grid.addWidget(self.evap_delete_num, 6, 1)

        self.evap_label_loops = QLabel("循环轮数:")
        evap_grid.addWidget(self.evap_label_loops, 6, 2)
        self.evap_loops = QSpinBox()
        self.evap_loops.setRange(1, 100000)
        self.evap_loops.setValue(500)
        evap_grid.addWidget(self.evap_loops, 6, 3)

        # 输出前缀
        evap_grid.addWidget(QLabel("输出前缀:"), 7, 0)
        self.evap_prefix = QLineEdit("evap")
        evap_grid.addWidget(self.evap_prefix, 7, 1, 1, 3)

        # 断点续跑
        self.evap_restart_check = QCheckBox("断点续跑")
        evap_grid.addWidget(self.evap_restart_check, 8, 0)

        self.evap_start_loop_label = QLabel("起始轮数:")
        self.evap_start_loop_label.setVisible(False)
        evap_grid.addWidget(self.evap_start_loop_label, 8, 1)

        self.evap_start_loop = QSpinBox()
        self.evap_start_loop.setRange(1, 100000)
        self.evap_start_loop.setValue(1)
        self.evap_start_loop.setVisible(False)
        evap_grid.addWidget(self.evap_start_loop, 8, 2)

        # 模式切换信号
        self.evap_mode.currentIndexChanged.connect(self._on_evap_mode_changed)
        self.evap_restart_check.stateChanged.connect(self._on_evap_restart_changed)

        # 默认选中分批蒸发模式（索引0），确保断点续跑控件可见
        self.evap_mode.setCurrentIndex(0)
        self._on_evap_mode_changed()

        evap_layout.addWidget(evap_config)

        # 提示
        tip = QLabel("💡 分批蒸发: 每轮删除N个溶剂分子后跑10ps NPT，循环指定轮数\n💡 删除全部添加剂: 一次性删除所有指定残基分子后跑NPT")
        tip.setStyleSheet("color: #666; font-size: 11px;")
        tip.setWordWrap(True)
        evap_layout.addWidget(tip)

        # 运行按钮
        evap_run_btn = QPushButton("🚀 开始蒸发")
        evap_run_btn.setStyleSheet("""
            QPushButton {
                background-color: #D84315;
                color: white;
                padding: 8px 16px;
                border-radius: 6px;
                font-size: 12pt;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #BF360C; }
        """)
        evap_run_btn.clicked.connect(self.run_evap_step)
        evap_layout.addWidget(evap_run_btn)

        vbox.addWidget(evap_phase)

        # === 第六阶段: 退火模拟 ===
        anneal_phase = QGroupBox("🌡️ 第六阶段: 退火模拟 (Simulated Annealing)")
        anneal_phase.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #4A148C;
                margin-top: 8px;
                padding-top: 8px;
                border: 2px solid #6A1B9A;
                border-radius: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        anneal_layout = QVBoxLayout(anneal_phase)
        anneal_layout.setSpacing(8)

        # 退火配置
        anneal_config = QGroupBox("退火配置")
        anneal_grid = QGridLayout(anneal_config)
        anneal_grid.setSpacing(6)

        # 输入GRO
        anneal_grid.addWidget(QLabel("输入GRO:"), 0, 0)
        self.anneal_gro_edit, ag_layout = self._create_file_input("输入GRO文件", "npt.gro", "结构文件 (*.gro *.pdb);;所有文件 (*.*)", "选择GRO文件")
        anneal_grid.addLayout(ag_layout, 0, 1, 1, 3)

        # 拓扑TOP
        anneal_grid.addWidget(QLabel("拓扑TOP:"), 1, 0)
        self.anneal_top_edit, at_layout = self._create_file_input("拓扑TOP文件", "topol.top", "拓扑文件 (*.top *.itp);;所有文件 (*.*)", "选择TOP文件")
        anneal_grid.addLayout(at_layout, 1, 1, 1, 3)

        # 输出前缀
        anneal_grid.addWidget(QLabel("输出前缀:"), 2, 0)
        self.anneal_prefix = QLineEdit("anneal")
        anneal_grid.addWidget(self.anneal_prefix, 2, 1)

        # 退火模式
        anneal_grid.addWidget(QLabel("退火模式:"), 2, 2)
        self.anneal_mode = QComboBox()
        self.anneal_mode.addItems(["single (单次退火)", "periodic (周期退火)"])
        anneal_grid.addWidget(self.anneal_mode, 2, 3)

        # 退火曲线表格
        curve_label = QLabel("退火曲线 (时间-温度点对):")
        curve_label.setStyleSheet("font-weight: bold; color: #4A148C;")
        anneal_grid.addWidget(curve_label, 3, 0, 1, 4)

        # 创建退火点表格
        from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView
        self.anneal_table = QTableWidget(7, 2)
        self.anneal_table.setHorizontalHeaderLabels(["时间 (ps)", "温度 (K)"])
        self.anneal_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.anneal_table.setMinimumHeight(160)
        # 默认填充ClFFCl退火参数
        default_times = ["0", "100", "300", "500", "700", "900", "1000"]
        default_temps = ["300", "373", "373", "373", "373", "300", "300"]
        for i in range(7):
            self.anneal_table.setItem(i, 0, QTableWidgetItem(default_times[i]))
            self.anneal_table.setItem(i, 1, QTableWidgetItem(default_temps[i]))
        anneal_grid.addWidget(self.anneal_table, 4, 0, 1, 4)

        # 表格操作按钮
        table_btn_layout = QHBoxLayout()
        add_row_btn = QPushButton("+ 添加行")
        add_row_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; padding: 3px 10px; border-radius: 4px; } QPushButton:hover { background-color: #388E3C; }")
        add_row_btn.clicked.connect(lambda: self.anneal_table.insertRow(self.anneal_table.rowCount()))
        table_btn_layout.addWidget(add_row_btn)

        del_row_btn = QPushButton("- 删除选中行")
        del_row_btn.setStyleSheet("QPushButton { background-color: #f44336; color: white; padding: 3px 10px; border-radius: 4px; } QPushButton:hover { background-color: #d32f2f; }")
        del_row_btn.clicked.connect(lambda: self.anneal_table.removeRow(self.anneal_table.currentRow()) if self.anneal_table.currentRow() >= 0 else None)
        table_btn_layout.addWidget(del_row_btn)

        reset_curve_btn = QPushButton("↻ 重置默认曲线")
        reset_curve_btn.setStyleSheet("QPushButton { background-color: #FF9800; color: white; padding: 3px 10px; border-radius: 4px; } QPushButton:hover { background-color: #F57C00; }")
        reset_curve_btn.clicked.connect(self._reset_anneal_curve)
        table_btn_layout.addWidget(reset_curve_btn)

        table_btn_layout.addStretch()
        anneal_grid.addLayout(table_btn_layout, 5, 0, 1, 4)

        # 退火曲线说明
        curve_tip = QLabel("💡 默认曲线: 300K → 373K (保温) → 300K，模拟1ns\n💡 时间点必须递增，点数需与温度点数一致\n💡 生成MDP后会自动执行 grompp + mdrun")
        curve_tip.setStyleSheet("color: #666; font-size: 11px;")
        curve_tip.setWordWrap(True)
        anneal_grid.addWidget(curve_tip, 6, 0, 1, 4)

        anneal_layout.addWidget(anneal_config)

        # 运行按钮
        anneal_run_btn = QPushButton("🚀 开始退火模拟")
        anneal_run_btn.setStyleSheet("""
            QPushButton {
                background-color: #6A1B9A;
                color: white;
                padding: 8px 16px;
                border-radius: 6px;
                font-size: 12pt;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #4A148C; }
        """)
        anneal_run_btn.clicked.connect(self.run_anneal_step)
        anneal_layout.addWidget(anneal_run_btn)

        vbox.addWidget(anneal_phase)

        vbox.addStretch()
        return tab

    def _on_evap_mode_changed(self):
        """蒸发模式切换时显示/隐藏分批参数"""
        is_batch = self.evap_mode.currentIndex() == 0
        self.evap_label_delete.setVisible(is_batch)
        self.evap_delete_num.setVisible(is_batch)
        self.evap_label_loops.setVisible(is_batch)
        self.evap_loops.setVisible(is_batch)
        self.evap_restart_check.setVisible(is_batch)
        self.evap_start_loop_label.setVisible(is_batch and self.evap_restart_check.isChecked())
        self.evap_start_loop.setVisible(is_batch and self.evap_restart_check.isChecked())

    def _on_evap_restart_changed(self, state):
        """断点续跑复选框状态变化时显示/隐藏起始轮数输入"""
        is_checked = state == Qt.Checked
        self.evap_start_loop_label.setVisible(is_checked)
        self.evap_start_loop.setVisible(is_checked)
        if is_checked:
            self.evap_start_loop_label.show()
            self.evap_start_loop.show()

    def _create_editconf_step(self):
        title = "Step 2: 定义模拟盒子 (editconf)"
        group = QGroupBox(title)
        group.setStyleSheet("QGroupBox { font-weight: bold; color: #2E7D32; margin-top: 8px; }")
        layout = QGridLayout(group)
        layout.setSpacing(6)

        desc = QLabel("设置模拟盒子类型和大小")
        desc.setStyleSheet("color: #555;")
        layout.addWidget(desc, 0, 0, 1, 4)

        row = 1
        input_gro_edit = QLineEdit()
        input_gro_edit.setText("protein.gro")
        layout.addWidget(QLabel("输入GRO:"), row, 0)
        hlayout = QHBoxLayout()
        hlayout.addWidget(input_gro_edit, stretch=1)
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
            QPushButton:hover { background-color: #455A64; }
        """)
        btn.clicked.connect(lambda: self._browse_file(input_gro_edit, "选择结构文件", "结构文件 (*.gro *.pdb);;所有文件 (*.*)"))
        hlayout.addWidget(btn)
        layout.addLayout(hlayout, row, 1, 1, 3)
        row += 1

        output_gro_edit = QLineEdit()
        output_gro_edit.setText("protein_box.gro")
        layout.addWidget(QLabel("输出GRO:"), row, 0)
        hlayout = QHBoxLayout()
        hlayout.addWidget(output_gro_edit, stretch=1)
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
            QPushButton:hover { background-color: #455A64; }
        """)
        btn.clicked.connect(lambda: self._browse_file(output_gro_edit, "保存结构文件", "结构文件 (*.gro *.pdb);;所有文件 (*.*)"))
        hlayout.addWidget(btn)
        layout.addLayout(hlayout, row, 1, 1, 3)
        row += 1

        layout.addWidget(QLabel("盒子类型:"), row, 0)
        box_type_combo = QComboBox()
        box_type_combo.addItems([
            "cubic (立方体)",
            "triclinic (三斜)",
            "dodecahedron (十二面体)",
            "octahedron (八面体)",
            "rectangular (长方体)"
        ])
        layout.addWidget(box_type_combo, row, 1, 1, 3)
        row += 1

        layout.addWidget(QLabel("设置方式:"), row, 0)
        size_mode_combo = QComboBox()
        size_mode_combo.addItems(["按边距 (-d)", "按盒子边长 (-box)"])
        layout.addWidget(size_mode_combo, row, 1, 1, 3)
        row += 1

        box_size_label = QLabel("盒子边距:")
        layout.addWidget(box_size_label, row, 0)
        box_size_spin = QDoubleSpinBox()
        box_size_spin.setRange(0.1, 100.0)
        box_size_spin.setValue(1.0)
        box_size_spin.setDecimals(2)
        box_size_spin.setSuffix(" nm")
        layout.addWidget(box_size_spin, row, 1, 1, 3)
        row += 1

        box_a_label = QLabel("边长a:")
        box_a_label.setVisible(False)
        layout.addWidget(box_a_label, row, 0)
        box_a_spin = QDoubleSpinBox()
        box_a_spin.setRange(0.1, 500.0)
        box_a_spin.setValue(5.0)
        box_a_spin.setDecimals(2)
        box_a_spin.setSuffix(" nm")
        box_a_spin.setVisible(False)
        layout.addWidget(box_a_spin, row, 1, 1, 3)
        row += 1

        box_x_label = QLabel("X边长:")
        box_x_label.setVisible(False)
        layout.addWidget(box_x_label, row, 0)
        box_x_spin = QDoubleSpinBox()
        box_x_spin.setRange(0.1, 500.0)
        box_x_spin.setValue(5.0)
        box_x_spin.setDecimals(2)
        box_x_spin.setSuffix(" nm")
        box_x_spin.setVisible(False)
        layout.addWidget(box_x_spin, row, 1)
        box_y_label = QLabel("Y边长:")
        box_y_label.setVisible(False)
        layout.addWidget(box_y_label, row, 2)
        box_y_spin = QDoubleSpinBox()
        box_y_spin.setRange(0.1, 500.0)
        box_y_spin.setValue(5.0)
        box_y_spin.setDecimals(2)
        box_y_spin.setSuffix(" nm")
        box_y_spin.setVisible(False)
        layout.addWidget(box_y_spin, row, 3)
        row += 1

        box_z_label = QLabel("Z边长:")
        box_z_label.setVisible(False)
        layout.addWidget(box_z_label, row, 0)
        box_z_spin = QDoubleSpinBox()
        box_z_spin.setRange(0.1, 500.0)
        box_z_spin.setValue(5.0)
        box_z_spin.setDecimals(2)
        box_z_spin.setSuffix(" nm")
        box_z_spin.setVisible(False)
        layout.addWidget(box_z_spin, row, 1)
        row += 1

        angle_alpha_label = QLabel("夹角α (bc):")
        angle_alpha_label.setVisible(False)
        layout.addWidget(angle_alpha_label, row, 0)
        angle_alpha_spin = QDoubleSpinBox()
        angle_alpha_spin.setRange(1.0, 179.0)
        angle_alpha_spin.setValue(90.0)
        angle_alpha_spin.setDecimals(1)
        angle_alpha_spin.setSuffix(" °")
        angle_alpha_spin.setVisible(False)
        layout.addWidget(angle_alpha_spin, row, 1)
        angle_beta_label = QLabel("夹角β (ac):")
        angle_beta_label.setVisible(False)
        layout.addWidget(angle_beta_label, row, 2)
        angle_beta_spin = QDoubleSpinBox()
        angle_beta_spin.setRange(1.0, 179.0)
        angle_beta_spin.setValue(90.0)
        angle_beta_spin.setDecimals(1)
        angle_beta_spin.setSuffix(" °")
        angle_beta_spin.setVisible(False)
        layout.addWidget(angle_beta_spin, row, 3)
        row += 1

        angle_gamma_label = QLabel("夹角γ (ab):")
        angle_gamma_label.setVisible(False)
        layout.addWidget(angle_gamma_label, row, 0)
        angle_gamma_spin = QDoubleSpinBox()
        angle_gamma_spin.setRange(1.0, 179.0)
        angle_gamma_spin.setValue(90.0)
        angle_gamma_spin.setDecimals(1)
        angle_gamma_spin.setSuffix(" °")
        angle_gamma_spin.setVisible(False)
        layout.addWidget(angle_gamma_spin, row, 1)
        row += 1

        center_check = QCheckBox("分子居中 (-c)")
        center_check.setChecked(True)
        center_check.setToolTip("将分子放在盒子中心")
        layout.addWidget(center_check, row, 0, 1, 2)
        princ_check = QCheckBox("主惯性轴对齐 (-princ)")
        princ_check.setChecked(False)
        princ_check.setToolTip("将分子对齐到主惯性轴，使盒子更紧凑")
        layout.addWidget(princ_check, row, 2, 1, 2)
        row += 1

        def _on_box_type_changed(text):
            is_rect = "rectangular" in text.lower()
            is_triclinic = "triclinic" in text.lower()
            is_box_mode = "边长" in size_mode_combo.currentText()
            is_single_val = is_box_mode and not is_rect and not is_triclinic
            show_xyz = is_rect and is_box_mode
            show_angles = is_triclinic and is_box_mode
            box_a_label.setText("盒子边长:" if not is_triclinic else "边长a:")
            box_a_label.setVisible(is_single_val or (is_triclinic and is_box_mode))
            box_a_spin.setVisible(is_single_val or (is_triclinic and is_box_mode))
            box_x_label.setVisible(show_xyz)
            box_x_spin.setVisible(show_xyz)
            box_y_label.setVisible(show_xyz)
            box_y_spin.setVisible(show_xyz)
            box_z_label.setVisible(show_xyz)
            box_z_spin.setVisible(show_xyz)
            angle_alpha_label.setVisible(show_angles)
            angle_alpha_spin.setVisible(show_angles)
            angle_beta_label.setVisible(show_angles)
            angle_beta_spin.setVisible(show_angles)
            angle_gamma_label.setVisible(show_angles)
            angle_gamma_spin.setVisible(show_angles)
            box_size_label.setVisible(not is_box_mode)
            box_size_spin.setVisible(not is_box_mode)
            if is_single_val:
                box_a_label.setText("盒子边长:")
            elif is_triclinic and is_box_mode:
                box_a_label.setText("边长a:")

        def _on_size_mode_changed(text):
            _on_box_type_changed(box_type_combo.currentText())

        box_type_combo.currentTextChanged.connect(_on_box_type_changed)
        size_mode_combo.currentTextChanged.connect(_on_size_mode_changed)

        run_btn = QPushButton("运行此步骤")
        run_btn.setStyleSheet(
            "QPushButton { background-color: #2196F3; color: white; font-weight: bold; padding: 4px 12px; }"
            "QPushButton:hover { background-color: #1976D2; }"
        )
        layout.addWidget(run_btn, row, 0, 1, 2)
        row += 1

        key = "Step 2"
        self.md_step_btns[key] = {
            "group": group,
            "edits": [input_gro_edit, output_gro_edit],
            "run_btn": run_btn,
            "labels": ["输入GRO:", "输出GRO:"],
            "box_type_combo": box_type_combo,
            "size_mode_combo": size_mode_combo,
            "box_size_spin": box_size_spin,
            "box_a_spin": box_a_spin,
            "box_x_spin": box_x_spin,
            "box_y_spin": box_y_spin,
            "box_z_spin": box_z_spin,
            "angle_alpha_spin": angle_alpha_spin,
            "angle_beta_spin": angle_beta_spin,
            "angle_gamma_spin": angle_gamma_spin,
            "center_check": center_check,
            "princ_check": princ_check
        }
        run_btn.clicked.connect(lambda: self.run_md_step(key))
        return group

    def _create_step_group(self, title, description, labels, defaults):
        group = QGroupBox(title)
        group.setStyleSheet("QGroupBox { font-weight: bold; color: #2E7D32; margin-top: 8px; }")
        layout = QGridLayout(group)
        layout.setSpacing(6)

        desc = QLabel(description)
        desc.setStyleSheet("color: #555;")
        layout.addWidget(desc, 0, 0, 1, 4)

        # 根据标签后缀推断文件类型过滤器
        def _file_filter_for_label(lbl):
            low = lbl.lower()
            if "pdb" in low:
                return "PDB文件 (*.pdb *.gro);;所有文件 (*.*)", "选择PDB/GRO文件"
            if "gro" in low:
                return "结构文件 (*.gro *.pdb);;所有文件 (*.*)", "选择结构文件"
            if "top" in low:
                return "拓扑文件 (*.top *.itp);;所有文件 (*.*)", "选择拓扑文件"
            if "mdp" in low:
                return "MDP参数文件 (*.mdp);;所有文件 (*.*)", "选择MDP文件"
            if "tpr" in low:
                return "TPR输入文件 (*.tpr);;所有文件 (*.*)", "选择TPR文件"
            if "itp" in low:
                return "ITP拓扑文件 (*.itp *.top);;所有文件 (*.*)", "选择ITP文件"
            if "edr" in low:
                return "能量文件 (*.edr);;所有文件 (*.*)", "选择EDR文件"
            if "log" in low:
                return "日志文件 (*.log);;所有文件 (*.*)", "选择日志文件"
            if "xtc" in low or "trr" in low:
                return "轨迹文件 (*.xtc *.trr);;所有文件 (*.*)", "选择轨迹文件"
            return "所有文件 (*.*)", "选择文件"

        edits = []
        row = 1
        for i, lbl in enumerate(labels):
            le = QLineEdit()
            le.setPlaceholderText(defaults[i] if i < len(defaults) else "")
            if i < len(defaults):
                le.setText(defaults[i])
            edits.append(le)
            layout.addWidget(QLabel(lbl), row, 0)
            # 为文件输入框添加浏览按钮
            ffilter, ftitle = _file_filter_for_label(lbl)
            hlayout = QHBoxLayout()
            hlayout.addWidget(le, stretch=1)
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
                QPushButton:hover { background-color: #455A64; }
            """)
            btn.clicked.connect(lambda checked, edit=le, ft=ftitle, ff=ffilter: self._browse_file(edit, ft, ff))
            hlayout.addWidget(btn)
            layout.addLayout(hlayout, row, 1, 1, 3)
            row += 1

        run_btn = QPushButton("运行此步骤")
        run_btn.setStyleSheet(
            "QPushButton { background-color: #2196F3; color: white; font-weight: bold; padding: 5px 14px; min-height: 28px; }"
            "QPushButton:hover { background-color: #1976D2; }"
        )
        layout.addWidget(run_btn, row, 0, 1, 2)

        if any("MDP" in l for l in labels):
            mdp_type_key = "ions"
            if "EM" in title:
                mdp_type_key = "em"
            elif "NVT" in title:
                mdp_type_key = "nvt"
            elif "NPT" in title:
                mdp_type_key = "npt"
            elif "生产" in title or "MD" in title.split(":")[0]:
                mdp_type_key = "md"

            mdp_btn = QPushButton("生成默认MDP")
            mdp_btn.setStyleSheet(
                "QPushButton { background-color: #FF9800; color: white; padding: 5px 14px; min-height: 28px; }"
                "QPushButton:hover { background-color: #F57C00; }"
            )
            mdp_btn.clicked.connect(lambda t=mdp_type_key: self.generate_mdp_template(t))
            layout.addWidget(mdp_btn, row, 2)

            adv_mdp_btn = QPushButton("高级编辑器")
            adv_mdp_btn.setStyleSheet(
                "QPushButton { background-color: #9C27B0; color: white; padding: 5px 14px; min-height: 28px; }"
                "QPushButton:hover { background-color: #7B1FA2; }"
            )
            adv_mdp_btn.clicked.connect(lambda t=mdp_type_key: self.open_mdp_editor(t))
            adv_mdp_btn.setToolTip("打开高级MDP参数可视化编辑器")
            layout.addWidget(adv_mdp_btn, row, 3)

        row += 1

        key = title.split(":")[0].strip()
        is_mdrun = "mdrun" in title
        custom_out_check = None
        custom_out_edit = None
        custom_out_label = None

        if is_mdrun:
            custom_out_check = QCheckBox("自定义输出前缀")
            custom_out_check.setChecked(False)
            custom_out_check.setToolTip("勾选后可自定义输出文件名前缀，不勾选则使用输入TPR文件名作为前缀")
            layout.addWidget(custom_out_check, row, 0, 1, 2)
            row += 1

            custom_out_label = QLabel("输出前缀:")
            custom_out_label.setVisible(False)
            layout.addWidget(custom_out_label, row, 0)

            custom_out_edit = QLineEdit()
            custom_out_edit.setVisible(False)
            custom_out_edit.setPlaceholderText("输入输出文件名前缀")
            layout.addWidget(custom_out_edit, row, 1, 1, 3)
            row += 1

            restart_check = QCheckBox("断点续跑 (从CPT文件恢复)")
            restart_check.setChecked(False)
            restart_check.setToolTip("勾选后自动检测工作目录下的.cpt文件并续跑，适用于中断后恢复模拟")
            layout.addWidget(restart_check, row, 0, 1, 2)
            row += 1

            def _on_custom_out_toggled(checked):
                custom_out_label.setVisible(checked)
                custom_out_edit.setVisible(checked)
                for i, lbl in enumerate(labels):
                    if "输出" in lbl and i < len(edits):
                        edits[i].setVisible(checked)
                        lbl_widget = layout.itemAtPosition(i + 1, 0)
                        if lbl_widget and lbl_widget.widget():
                            lbl_widget.widget().setVisible(checked)

            custom_out_check.toggled.connect(_on_custom_out_toggled)

            for i, lbl in enumerate(labels):
                if "输出" in lbl and i < len(edits):
                    edits[i].setVisible(False)
                    lbl_widget = layout.itemAtPosition(i + 1, 0)
                    if lbl_widget and lbl_widget.widget():
                        lbl_widget.widget().setVisible(False)

        self.md_step_btns[key] = {
            "group": group,
            "edits": edits,
            "run_btn": run_btn,
            "labels": labels,
            "custom_out_check": custom_out_check,
            "custom_out_edit": custom_out_edit,
            "restart_check": restart_check if is_mdrun else None
        }
        run_btn.clicked.connect(lambda checked, k=key: self.run_md_step(k))
        return group

    # -------------------------------------------------------------------------
    # Part 3: 高级模拟
    # -------------------------------------------------------------------------
    def create_advanced_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        vbox = QVBoxLayout(content)
        vbox.setSpacing(12)
        vbox.setContentsMargins(8, 10, 8, 10)

        info = QLabel(
            "高级模拟方法需要特定的 MDP 参数和可能需要 PLUMED 插件支持。\n"
            "本版本 GROMACS 已内置 PLUMED 支持。"
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #555; font-size: 12px;")
        vbox.addWidget(info)

        # 伞形采样
        umbrella_group = QGroupBox("伞形采样 (Umbrella Sampling)")
        umbrella_group.setStyleSheet("QGroupBox { font-weight: bold; color: #7B1FA2; }")
        ugrid = QGridLayout(umbrella_group)

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

        self.umb_run_btn = QPushButton("生成伞形采样 MDP")
        self.umb_run_btn.setStyleSheet(
            "QPushButton { background-color: #7B1FA2; color: white; font-weight: bold; padding: 6px 16px; }"
            "QPushButton:hover { background-color: #6A1B9A; }"
        )
        self.umb_run_btn.clicked.connect(self.generate_umbrella_mdp)
        ugrid.addWidget(self.umb_run_btn, 5, 0, 1, 4)

        vbox.addWidget(umbrella_group)

        # WHAM 分析
        wham_group = QGroupBox("WHAM 自由能计算")
        wham_group.setStyleSheet("QGroupBox { font-weight: bold; color: #4527A0; }")
        wgrid = QGridLayout(wham_group)

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

        self.wham_run_btn = QPushButton("运行 gmx wham")
        self.wham_run_btn.setStyleSheet(
            "QPushButton { background-color: #4527A0; color: white; font-weight: bold; padding: 6px 16px; }"
            "QPushButton:hover { background-color: #311B92; }"
        )
        self.wham_run_btn.clicked.connect(self.run_wham)
        wgrid.addWidget(self.wham_run_btn, 2, 0, 1, 4)

        vbox.addWidget(wham_group)

        # 元动力学
        meta_group = QGroupBox("元动力学 (Metadynamics) - PLUMED")
        meta_group.setStyleSheet("QGroupBox { font-weight: bold; color: #BF360C; }")
        mgrid = QGridLayout(meta_group)

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

        self.meta_gen_btn = QPushButton("生成 PLUMED 输入")
        self.meta_gen_btn.setStyleSheet(
            "QPushButton { background-color: #BF360C; color: white; font-weight: bold; padding: 6px 16px; }"
            "QPushButton:hover { background-color: #A02708; }"
        )
        self.meta_gen_btn.clicked.connect(self.generate_plumed_meta)
        mgrid.addWidget(self.meta_gen_btn, 3, 0, 1, 2)

        self.meta_run_btn = QPushButton("运行元动力学模拟")
        self.meta_run_btn.setStyleSheet(
            "QPushButton { background-color: #E65100; color: white; font-weight: bold; padding: 6px 16px; }"
            "QPushButton:hover { background-color: #BF360C; }"
        )
        self.meta_run_btn.clicked.connect(self.run_metadynamics)
        mgrid.addWidget(self.meta_run_btn, 3, 2, 1, 2)

        vbox.addWidget(meta_group)

        # ABF 方法
        abf_group = QGroupBox("自适应偏置力 (ABF)")
        abf_group.setStyleSheet("QGroupBox { font-weight: bold; color: #006064; }")
        agrid = QGridLayout(abf_group)

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

        self.abf_gen_btn = QPushButton("生成 ABF PLUMED")
        self.abf_gen_btn.setStyleSheet(
            "QPushButton { background-color: #006064; color: white; font-weight: bold; padding: 6px 16px; }"
            "QPushButton:hover { background-color: #004D40; }"
        )
        self.abf_gen_btn.clicked.connect(self.generate_plumed_abf)
        agrid.addWidget(self.abf_gen_btn, 3, 0, 1, 4)

        vbox.addWidget(abf_group)

        vbox.addStretch()
        return tab

    # -------------------------------------------------------------------------
    # Part 5: 结果分析与可视化
    # -------------------------------------------------------------------------
    def create_analysis_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        vbox = QVBoxLayout(content)
        vbox.setSpacing(12)
        vbox.setContentsMargins(8, 10, 8, 10)

        common_group = QGroupBox("通用分析参数")
        common_group.setStyleSheet("QGroupBox { font-weight: bold; color: #1565C0; }")
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

        # === 文件管理与校验 (新增) ===
        file_check_group = QGroupBox("📁 文件管理与校验")
        file_check_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold; color: #37474F;
                margin-top: 8px; padding-top: 8px;
                border: 2px solid #455A64; border-radius: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin; left: 10px; padding: 0 5px;
            }
        """)
        file_check_layout = QVBoxLayout(file_check_group)
        file_check_layout.setSpacing(8)

        file_check_desc = QLabel("校验轨迹文件完整性，检查核心文件是否存在")
        file_check_desc.setWordWrap(True)
        file_check_desc.setStyleSheet("color: #263238; font-size: 11px;")
        file_check_layout.addWidget(file_check_desc)

        file_check_grid = QGridLayout()
        file_check_grid.setSpacing(6)

        self.file_check_btn = QPushButton("校验轨迹文件 (gmx check)")
        self.file_check_btn.setStyleSheet("""
            QPushButton {
                background-color: #455A64; color: white; font-weight: bold;
                padding: 4px 12px; border-radius: 4px;
            }
            QPushButton:hover { background-color: #37474F; }
        """)
        self.file_check_btn.clicked.connect(self._run_file_check)
        file_check_grid.addWidget(self.file_check_btn, 0, 0)

        self.file_status_btn = QPushButton("检查文件状态")
        self.file_status_btn.setStyleSheet("""
            QPushButton {
                background-color: #78909C; color: white; font-weight: bold;
                padding: 4px 12px; border-radius: 4px;
            }
            QPushButton:hover { background-color: #546E7A; }
        """)
        self.file_status_btn.clicked.connect(self._check_file_status)
        file_check_grid.addWidget(self.file_status_btn, 0, 1)

        file_check_layout.addLayout(file_check_grid)
        vbox.addWidget(file_check_group)

        self.analysis_widgets = {}

        # === 第一组: 能量与热力学分析 ===
        energy_group = QGroupBox("🌡️ 能量与热力学分析")
        energy_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #E65100;
                margin-top: 8px;
                padding-top: 8px;
                border: 2px solid #EF6C00;
                border-radius: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        energy_layout = QVBoxLayout(energy_group)
        energy_layout.setSpacing(6)

        energy_analyses = [
            ("energy", "能量分析", "分析温度、压力、密度、总能量、势能、动能等", "energy.xvg", "#E65100"),
            ("density", "密度分析", "计算密度分布", "density.xvg", "#EF6C00"),
            ("msd", "均方位移", "计算均方位移用于扩散系数", "msd.xvg", "#F57C00"),
        ]

        for key, name, desc, default_out, color in energy_analyses:
            grp = QGroupBox(f"{name}")
            grp.setStyleSheet(f"""
                QGroupBox {{
                    font-weight: bold;
                    color: #BF360C;
                    margin-top: 4px;
                    border: 1px solid #FFAB91;
                    border-radius: 6px;
                }}
                QGroupBox::title {{
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px;
                }}
            """)
            g = QGridLayout(grp)
            g.addWidget(QLabel(desc), 0, 0, 1, 4)

            out_edit = QLineEdit(default_out)
            sel_edit = QLineEdit()
            sel_edit.setPlaceholderText("如 -select 'resname ALA'")
            ref_edit = QLineEdit()
            ref_edit.setPlaceholderText("参考结构 (可选)")

            run_btn = QPushButton("运行")
            run_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color};
                    color: white;
                    font-weight: bold;
                    padding: 4px 12px;
                    border-radius: 4px;
                }}
                QPushButton:hover {{ background-color: {self._adjust_brightness(color, 0.9)}; }}
            """)

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
            run_btn.clicked.connect(lambda checked, k=key: self.run_analysis(k))
            energy_layout.addWidget(grp)

        vbox.addWidget(energy_group)

        # === 第二组: 结构稳定性分析 ===
        struct_group = QGroupBox("📐 结构稳定性分析")
        struct_group.setStyleSheet("""
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
            grp.setStyleSheet(f"""
                QGroupBox {{
                    font-weight: bold;
                    color: #0D47A1;
                    margin-top: 4px;
                    border: 1px solid #64B5F6;
                    border-radius: 6px;
                }}
                QGroupBox::title {{
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px;
                }}
            """)
            g = QGridLayout(grp)
            g.addWidget(QLabel(desc), 0, 0, 1, 4)

            out_edit = QLineEdit(default_out)
            sel_edit = QLineEdit()
            sel_edit.setPlaceholderText("如 -select 'resname ALA'")
            ref_edit = QLineEdit()
            ref_edit.setPlaceholderText("参考结构 (可选)")

            run_btn = QPushButton("运行")
            run_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color};
                    color: white;
                    font-weight: bold;
                    padding: 4px 12px;
                    border-radius: 4px;
                }}
                QPushButton:hover {{ background-color: {self._adjust_brightness(color, 0.9)}; }}
            """)

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
            run_btn.clicked.connect(lambda checked, k=key: self.run_analysis(k))
            struct_layout.addWidget(grp)

        vbox.addWidget(struct_group)

        # === 第三组: 相互作用分析 ===
        interact_group = QGroupBox("🔗 相互作用分析")
        interact_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #2E7D32;
                margin-top: 8px;
                padding-top: 8px;
                border: 2px solid #388E3C;
                border-radius: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
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
            grp.setStyleSheet(f"""
                QGroupBox {{
                    font-weight: bold;
                    color: #1B5E20;
                    margin-top: 4px;
                    border: 1px solid #81C784;
                    border-radius: 6px;
                }}
                QGroupBox::title {{
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px;
                }}
            """)
            g = QGridLayout(grp)
            g.addWidget(QLabel(desc), 0, 0, 1, 4)

            out_edit = QLineEdit(default_out)
            sel_edit = QLineEdit()
            sel_edit.setPlaceholderText("如 -select 'resname ALA'")
            ref_edit = QLineEdit()
            ref_edit.setPlaceholderText("参考结构 (可选)")

            run_btn = QPushButton("运行")
            run_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color};
                    color: white;
                    font-weight: bold;
                    padding: 4px 12px;
                    border-radius: 4px;
                }}
                QPushButton:hover {{ background-color: {self._adjust_brightness(color, 0.9)}; }}
            """)

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
            run_btn.clicked.connect(lambda checked, k=key: self.run_analysis(k))
            interact_layout.addWidget(grp)

        # 为特定分析工具设置更有针对性的placeholder
        # 这些是用户最常问的"不知道该填什么"的字段
        if "energy" in self.analysis_widgets:
            self.analysis_widgets["energy"]["sel"].setPlaceholderText(
                "能量项（空格分隔）: Potential Temperature Pressure Density（留空默认 Potential）"
            )
        if "rdf" in self.analysis_widgets:
            self.analysis_widgets["rdf"]["sel"].setPlaceholderText(
                "如 -ref='group Protein' -sel='group Water' -seltype=mol_com -bin=0.01（留空自动选择前两组）"
            )
        if "pairdist" in self.analysis_widgets:
            self.analysis_widgets["pairdist"]["sel"].setPlaceholderText(
                "如 -ref='group Protein' -sel='group Water' -type=min（留空自动选择前两组）"
            )
        if "cluster" in self.analysis_widgets:
            self.analysis_widgets["cluster"]["sel"].setPlaceholderText(
                "如 -method=linkage -cutoff=0.2（方法: gromos/linkage/jarvis-patrick）"
            )
        if "density" in self.analysis_widgets:
            self.analysis_widgets["density"]["sel"].setPlaceholderText(
                "如 -d=Z -sl=100（方向X/Y/Z, 切片数）"
            )
        if "rms" in self.analysis_widgets:
            self.analysis_widgets["rms"]["sel"].setPlaceholderText(
                "留空自动对所有原子计算（先拟合再计算）"
            )
            self.analysis_widgets["rms"]["ref"].setPlaceholderText(
                "参考结构（默认使用TPR作为参考）"
            )
        if "rmsf" in self.analysis_widgets:
            self.analysis_widgets["rmsf"]["sel"].setPlaceholderText(
                "组名或选择表达式（留空使用所有原子）"
            )
        if "gyrate" in self.analysis_widgets:
            self.analysis_widgets["gyrate"]["sel"].setPlaceholderText(
                "组名或选择表达式（留空使用所有原子）"
            )
        if "sasa" in self.analysis_widgets:
            self.analysis_widgets["sasa"]["sel"].setPlaceholderText(
                "组名（留空使用所有原子）"
            )
        if "hbond" in self.analysis_widgets:
            self.analysis_widgets["hbond"]["sel"].setPlaceholderText(
                "供体/受体组（自动选择Protein-SOL）"
            )
        if "distance" in self.analysis_widgets:
            self.analysis_widgets["distance"]["sel"].setPlaceholderText(
                "组1（留空使用System）"
            )
            self.analysis_widgets["distance"]["ref"].setPlaceholderText(
                "组2（留空使用System）"
            )
        if "angle" in self.analysis_widgets:
            self.analysis_widgets["angle"]["sel"].setPlaceholderText(
                "留空使用前3个原子"
            )
        if "msd" in self.analysis_widgets:
            self.analysis_widgets["msd"]["sel"].setPlaceholderText(
                "如 -sel 'resname DON'（留空使用所有原子）"
            )
            self.analysis_widgets["msd"]["ref"].setPlaceholderText(
                "输入 molecules 启用按分子计算"
            )
        if "principal" in self.analysis_widgets:
            self.analysis_widgets["principal"]["sel"].setPlaceholderText(
                "原子组（留空使用C-alpha或所有原子）"
            )
        if "covar" in self.analysis_widgets:
            self.analysis_widgets["covar"]["sel"].setPlaceholderText(
                "原子组（留空使用C-alpha）"
            )
        if "do_dssp" in self.analysis_widgets:
            self.analysis_widgets["do_dssp"]["sel"].setPlaceholderText(
                "蛋白质组（留空使用Protein）"
            )
        if "saltbr" in self.analysis_widgets:
            self.analysis_widgets["saltbr"]["sel"].setPlaceholderText(
                "蛋白质组（留空使用Protein）"
            )

        vbox.addWidget(interact_group)

        # === 第四组: 片段分析 (新增) ===
        fragment_group = QGroupBox("🧩 片段分析")
        fragment_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #006064;
                margin-top: 8px;
                padding-top: 8px;
                border: 2px solid #00838F;
                border-radius: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        fragment_layout = QVBoxLayout(fragment_group)
        fragment_layout.setSpacing(8)

        # 子模块A: 片段索引生成器
        ndx_gen_group = QGroupBox("片段索引生成器 (make_ndx)")
        ndx_gen_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold; color: #004D40;
                margin-top: 4px; border: 1px solid #4DB6AC;
                border-radius: 6px;
            }
            QGroupBox::title {
                subcontrol-origin: margin; left: 10px; padding: 0 5px;
            }
        """)
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

        # 片段定义表格
        ndx_gen_layout.addWidget(QLabel("片段定义 (名称: 原子范围, 如 1-10,20-25):"), 2, 0, 1, 4)
        self.ndx_gen_table = QTableWidget()
        self.ndx_gen_table.setColumnCount(2)
        self.ndx_gen_table.setHorizontalHeaderLabels(["片段名称", "原子范围 (逗号分隔区间)"])
        self.ndx_gen_table.horizontalHeader().setStretchLastSection(True)
        self.ndx_gen_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.ndx_gen_table.setMinimumHeight(120)
        self.ndx_gen_table.setMaximumHeight(150)
        # 默认填充示例数据
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
        self.ndx_gen_btn.setStyleSheet("""
            QPushButton {
                background-color: #00838F; color: white; font-weight: bold;
                padding: 4px 12px; border-radius: 4px;
            }
            QPushButton:hover { background-color: #006064; }
        """)
        ndx_gen_layout.addWidget(self.ndx_gen_btn, 5, 3)

        # 连接按钮信号
        self.ndx_add_row_btn.clicked.connect(lambda: self.ndx_gen_table.insertRow(self.ndx_gen_table.rowCount()))
        self.ndx_del_row_btn.clicked.connect(self._remove_ndx_row)
        self.ndx_clear_btn.clicked.connect(lambda: self.ndx_gen_table.setRowCount(0))
        self.ndx_load_def_btn.clicked.connect(self._load_fragment_definition)
        self.ndx_gen_btn.clicked.connect(self._generate_fragment_ndx)

        fragment_layout.addWidget(ndx_gen_group)

        # 子模块B: 片段-片段 RDF 分析 (增强版)
        rdf_frag_group = QGroupBox("片段-片段 RDF 分析")
        rdf_frag_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold; color: #004D40;
                margin-top: 4px; border: 1px solid #4DB6AC;
                border-radius: 6px;
            }
            QGroupBox::title {
                subcontrol-origin: margin; left: 10px; padding: 0 5px;
            }
        """)
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
        self.rdf_frag_run_btn.setStyleSheet("""
            QPushButton {
                background-color: #00695C; color: white; font-weight: bold;
                padding: 4px 12px; border-radius: 4px;
            }
            QPushButton:hover { background-color: #004D40; }
        """)
        rdf_frag_layout.addWidget(self.rdf_frag_run_btn, 4, 3)
        self.rdf_frag_run_btn.clicked.connect(self._run_fragment_rdf_batch)

        fragment_layout.addWidget(rdf_frag_group)

        # 子模块C: 最近邻距离分析 (pairdist增强)
        pairdist_group = QGroupBox("最近邻距离分析 (pairdist)")
        pairdist_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold; color: #004D40;
                margin-top: 4px; border: 1px solid #4DB6AC;
                border-radius: 6px;
            }
            QGroupBox::title {
                subcontrol-origin: margin; left: 10px; padding: 0 5px;
            }
        """)
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
        self.pairdist_run_btn.setStyleSheet("""
            QPushButton {
                background-color: #00695C; color: white; font-weight: bold;
                padding: 4px 12px; border-radius: 4px;
            }
            QPushButton:hover { background-color: #004D40; }
        """)
        pairdist_layout.addWidget(self.pairdist_run_btn, 2, 0, 1, 4)
        self.pairdist_run_btn.clicked.connect(self._run_pairdist_analysis)

        fragment_layout.addWidget(pairdist_group)
        vbox.addWidget(fragment_group)

        # === 第五组: 高级分析方法 ===
        advanced_group = QGroupBox("📊 高级分析方法")
        advanced_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #6A1B9A;
                margin-top: 8px;
                padding-top: 8px;
                border: 2px solid #7B1FA2;
                border-radius: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
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
            grp.setStyleSheet(f"""
                QGroupBox {{
                    font-weight: bold;
                    color: #4A148C;
                    margin-top: 4px;
                    border: 1px solid #BA68C8;
                    border-radius: 6px;
                }}
                QGroupBox::title {{
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px;
                }}
            """)
            g = QGridLayout(grp)
            g.addWidget(QLabel(desc), 0, 0, 1, 4)

            out_edit = QLineEdit(default_out)
            sel_edit = QLineEdit()
            sel_edit.setPlaceholderText("如 -select 'resname ALA'")
            ref_edit = QLineEdit()
            ref_edit.setPlaceholderText("参考结构 (可选)")

            run_btn = QPushButton("运行")
            run_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color};
                    color: white;
                    font-weight: bold;
                    padding: 4px 12px;
                    border-radius: 4px;
                }}
                QPushButton:hover {{ background-color: {self._adjust_brightness(color, 0.9)}; }}
            """)

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
            run_btn.clicked.connect(lambda checked, k=key: self.run_analysis(k))
            advanced_layout.addWidget(grp)

        vbox.addWidget(advanced_group)

        # === 第六组: 结果自动绘图 (新增) ===
        plot_group = QGroupBox("📈 结果自动绘图")
        plot_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold; color: #AD1457;
                margin-top: 8px; padding-top: 8px;
                border: 2px solid #C2185B; border-radius: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin; left: 10px; padding: 0 5px;
            }
        """)
        plot_layout = QVBoxLayout(plot_group)
        plot_layout.setSpacing(8)

        plot_desc = QLabel("自动读取xvg文件并生成符合期刊标准的科研图表")
        plot_desc.setWordWrap(True)
        plot_desc.setStyleSheet("color: #880E4F; font-size: 11px;")
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
        self.plot_run_btn.setStyleSheet("""
            QPushButton {
                background-color: #C2185B; color: white; font-weight: bold;
                padding: 4px 12px; border-radius: 4px;
            }
            QPushButton:hover { background-color: #880E4F; }
        """)
        self.plot_run_btn.clicked.connect(self._generate_plot)
        plot_layout.addWidget(self.plot_run_btn)

        vbox.addWidget(plot_group)

        # === 第七组: 能量分解分析 (新增) ===
        energy_decomp_group = QGroupBox("⚡ 能量分解分析")
        energy_decomp_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold; color: #5D4037;
                margin-top: 8px; padding-top: 8px;
                border: 2px solid #795548; border-radius: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin; left: 10px; padding: 0 5px;
            }
        """)
        energy_decomp_layout = QVBoxLayout(energy_decomp_group)
        energy_decomp_layout.setSpacing(8)

        energy_decomp_desc = QLabel("提取并分解能量项，分析组分间相互作用")
        energy_decomp_desc.setWordWrap(True)
        energy_decomp_desc.setStyleSheet("color: #3E2723; font-size: 11px;")
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
        self.ed_run_btn.setStyleSheet("""
            QPushButton {
                background-color: #795548; color: white; font-weight: bold;
                padding: 4px 12px; border-radius: 4px;
            }
            QPushButton:hover { background-color: #5D4037; }
        """)
        self.ed_run_btn.clicked.connect(self._run_energy_decomposition)
        energy_decomp_layout.addWidget(self.ed_run_btn)

        vbox.addWidget(energy_decomp_group)

        # === 第八组: 批量处理系统 (新增) ===
        batch_group = QGroupBox("📦 批量处理系统")
        batch_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold; color: #BF360C;
                margin-top: 8px; padding-top: 8px;
                border: 2px solid #E64A19; border-radius: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin; left: 10px; padding: 0 5px;
            }
        """)
        batch_layout = QVBoxLayout(batch_group)
        batch_layout.setSpacing(8)

        batch_desc = QLabel("同时处理多个模拟体系的数据，自动执行全套分析流程")
        batch_desc.setWordWrap(True)
        batch_desc.setStyleSheet("color: #BF360C; font-size: 11px;")
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
        self.batch_run_btn.setStyleSheet("""
            QPushButton {
                background-color: #E64A19; color: white; font-weight: bold;
                padding: 4px 12px; border-radius: 4px;
            }
            QPushButton:hover { background-color: #BF360C; }
        """)
        batch_grid.addWidget(self.batch_run_btn, 2, 3)

        batch_layout.addLayout(batch_grid)

        # 连接按钮信号
        self.batch_add_btn.clicked.connect(self._add_batch_system)
        self.batch_del_btn.clicked.connect(self._remove_batch_system)
        self.batch_clear_btn.clicked.connect(lambda: self.batch_table.setRowCount(0))
        self.batch_load_dir_btn.clicked.connect(self._load_batch_from_directory)
        self.batch_run_btn.clicked.connect(self._run_batch_processing)

        vbox.addWidget(batch_group)

        vbox.addStretch()
        return tab

    # -------------------------------------------------------------------------
    # Part 5: 片段分析功能方法 (新增)
    # -------------------------------------------------------------------------

    def _run_file_check(self):
        """校验轨迹文件完整性"""
        wd = self._get_work_dir()
        if not wd:
            return
        xtc = self.ana_input_xtc.text().strip() or "md.xtc"
        tpr = self.ana_input_tpr.text().strip() or "md.tpr"

        if not os.path.exists(os.path.join(wd, xtc)):
            QMessageBox.warning(self, "警告", f"轨迹文件不存在: {xtc}")
            return

        cmd = [self.gmx_path, "check", "-f", xtc, "-s", tpr]
        self.run_command([cmd], wd, "轨迹文件校验")

    def _check_file_status(self):
        """检查分析所需的核心文件是否存在"""
        wd = self._get_work_dir()
        if not wd:
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
        self.add_log("\n".join(status_msg), "info" if all_ok else "warning")

    def _add_batch_system(self):
        """添加一个模拟体系到批量处理列表"""
        wd = self._get_work_dir()
        if not wd:
            return
        row = self.batch_table.rowCount()
        self.batch_table.insertRow(row)
        self.batch_table.setItem(row, 0, QTableWidgetItem(wd))
        self.batch_table.setItem(row, 1, QTableWidgetItem(self.ana_input_tpr.text().strip() or "md.tpr"))
        self.batch_table.setItem(row, 2, QTableWidgetItem(self.ana_input_xtc.text().strip() or "md.xtc"))

    def _remove_batch_system(self):
        """从批量处理列表中删除选中的体系"""
        row = self.batch_table.currentRow()
        if row >= 0:
            self.batch_table.removeRow(row)

    def _load_batch_from_directory(self):
        """从目录自动查找模拟数据"""
        base_dir = QFileDialog.getExistingDirectory(self, "选择包含多个模拟的父目录")
        if not base_dir:
            return

        import glob
        found = 0
        for subdir in os.listdir(base_dir):
            subpath = os.path.join(base_dir, subdir)
            if not os.path.isdir(subpath):
                continue
            # 查找常见的模拟文件
            tpr_files = glob.glob(os.path.join(subpath, "*.tpr"))
            xtc_files = glob.glob(os.path.join(subpath, "*.xtc"))
            if tpr_files and xtc_files:
                row = self.batch_table.rowCount()
                self.batch_table.insertRow(row)
                self.batch_table.setItem(row, 0, QTableWidgetItem(subpath))
                self.batch_table.setItem(row, 1, QTableWidgetItem(os.path.basename(tpr_files[0])))
                self.batch_table.setItem(row, 2, QTableWidgetItem(os.path.basename(xtc_files[0])))
                found += 1

        self.add_log(f"从目录加载了 {found} 个模拟体系", "success")

    def _run_batch_processing(self):
        """执行批量分析处理"""
        row_count = self.batch_table.rowCount()
        if row_count == 0:
            QMessageBox.warning(self, "警告", "请先添加模拟体系！")
            return

        flow = self.batch_flow.currentText()
        self.add_log(f"开始批量处理: {flow} | 共 {row_count} 个体系", "info")

        # 定义不同流程的分析命令
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

            self.add_log(f"[{i+1}/{row_count}] 处理体系: {os.path.basename(wd)}", "info")

            # 临时切换工作目录和输入文件
            old_wd = self.work_dir.text()
            old_tpr = self.ana_input_tpr.text()
            old_xtc = self.ana_input_xtc.text()

            self.work_dir.setText(wd)
            self.ana_input_tpr.setText(tpr)
            self.ana_input_xtc.setText(xtc)

            for analysis in selected_analyses:
                self.add_log(f"  → {analysis}", "info")
                self.run_analysis(analysis)

            # 恢复原始设置
            self.work_dir.setText(old_wd)
            self.ana_input_tpr.setText(old_tpr)
            self.ana_input_xtc.setText(old_xtc)

        self.add_log("批量处理完成！", "success")

    def _run_energy_decomposition(self):
        """运行能量分解分析"""
        wd = self._get_work_dir()
        if not wd:
            return

        gmx = self.gmx_path
        edr = self.ana_input_edr.text().strip() or "md.edr"
        terms = self.ed_terms.text().strip()
        output = self.ed_output.text().strip() or "energy.xvg"
        extra_range = self.ed_range.text().strip()

        if not os.path.exists(os.path.join(wd, edr)):
            QMessageBox.warning(self, "警告", f"能量文件不存在: {edr}")
            return

        # 构建命令
        cmd = [gmx, "energy", "-f", edr, "-o", output]

        # 处理能量项选择
        if terms:
            # 使用echo管道输入能量项编号或名称
            term_list = [t.strip() for t in terms.split() if t.strip()]
            term_str = " ".join(term_list)
            cmd_str = f"echo '{term_str} 0' | {' '.join(cmd)}"
            if extra_range:
                cmd_str += " " + extra_range
            self.add_log(f"提取能量项: {term_str}", "info")
            import subprocess
            try:
                result = subprocess.run(
                    cmd_str, shell=True, cwd=wd,
                    capture_output=True, text=True, timeout=300
                )
                if result.returncode == 0:
                    self.add_log(f"能量分析完成: {output}", "success")
                else:
                    err = result.stderr[:500] if result.stderr else "未知错误"
                    self.add_log(f"能量分析失败: {err}", "error")
            except Exception as e:
                self.add_log(f"能量分析异常: {str(e)}", "error")

    def _remove_ndx_row(self):
        """删除片段表格中选中的行"""
        row = self.ndx_gen_table.currentRow()
        if row >= 0:
            self.ndx_gen_table.removeRow(row)

    def _load_fragment_definition(self):
        """从文件加载片段定义（如 p4PM6-split.txt 格式）"""
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

            self.add_log(f"已从 {os.path.basename(file_path)} 加载片段定义", "success")
        except Exception as e:
            self.add_log(f"加载片段定义失败: {str(e)}", "error")

    def _expand_ranges(self, rangestr):
        """解析原子范围字符串，如 '1-10,20-25,30' -> [1,2,...,10,20,21,...,25,30]"""
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

    def _generate_fragment_ndx(self):
        """生成片段索引文件（核心功能）"""
        wd = self._get_work_dir()
        if not wd:
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
                self.add_log(f"片段 '{name}' 的原子范围解析失败: {str(e)}", "error")
                return

            all_atoms = []
            for mol in range(nmol):
                shift = offset + mol * natom_per_mol
                all_atoms.extend([x + shift for x in base_atoms])
            groups[name] = all_atoms

        output_path = os.path.join(wd, output_file)
        try:
            with open(output_path, 'w') as f:
                for name, atoms in groups.items():
                    f.write(f"[ {name} ]\n")
                    for i in range(0, len(atoms), 15):
                        line = atoms[i:i+15]
                        f.write(" ".join(map(str, line)) + "\n")
                    f.write("\n")

            total_atoms = sum(len(atoms) for atoms in groups.values())
            self.add_log(
                f"片段索引文件生成成功: {output_file} | "
                f"共 {len(groups)} 个组, {total_atoms} 个原子", "success"
            )
            # 自动填充RDF分析中的索引文件
            self.rdf_frag_ndx_input.setText(output_file)
        except Exception as e:
            self.add_log(f"生成索引文件失败: {str(e)}", "error")

    def _run_fragment_rdf_batch(self):
        """批量计算片段-片段RDF"""
        wd = self._get_work_dir()
        if not wd:
            return

        gmx = self.gmx_path
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

        # 创建输出目录
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
        self.add_log(f"开始批量计算片段RDF: 共 {total} 组 ({len(ref_groups)} ref x {len(sel_groups)} sel)", "info")

        # 逐个执行
        for i, (cmd, step_name) in enumerate(commands, 1):
            self.add_log(f"[{i}/{total}] {step_name}", "info")
            self.run_command([cmd], wd, step_name)

    def _run_pairdist_analysis(self):
        """运行增强版pairdist分析（最近邻距离）"""
        wd = self._get_work_dir()
        if not wd:
            return

        gmx = self.gmx_path
        xtc = self.ana_input_xtc.text().strip() or "md.xtc"
        tpr = self.ana_input_tpr.text().strip() or "md.tpr"
        ndx = self.rdf_frag_ndx_input.text().strip() or "fragment.ndx"

        ref_group = self.pairdist_ref.text().strip()
        sel_group = self.pairdist_sel.text().strip()

        if not ref_group or not sel_group:
            QMessageBox.warning(self, "警告", "请填写参考组和选择组！")
            return

        type_text = self.pairdist_type.currentText()
        pd_type = type_text.split()[0]  # min / max / maxdist
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
        self.run_command([cmd], wd, step_name)

    def _generate_plot(self):
        """自动读取xvg文件并生成科研图表"""
        wd = self._get_work_dir()
        if not wd:
            return

        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        xvg_file = self.plot_input.text().strip()
        if not xvg_file or not os.path.exists(os.path.join(wd, xvg_file)):
            # 尝试通配符匹配
            import glob
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
            # 读取xvg文件数据
            data = []
            legends = []
            with open(os.path.join(wd, xvg_file), 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('@') and 'legend' in line:
                        # 提取图例
                        legend = line.split('legend')[-1].strip().strip('"')
                        legends.append(legend)
                    elif line and not line.startswith(('#', '@')):
                        parts = line.split()
                        if len(parts) >= 2:
                            try:
                                data.append([float(p) for p in parts])
                            except:
                                pass

            if not data:
                QMessageBox.warning(self, "警告", "xvg文件中没有有效数据！")
                return

            data = list(zip(*data))
            x = data[0]

            # 创建图表
            fig, ax = plt.subplots(figsize=(8, 5), dpi=dpi)

            if "多曲线对比" in plot_type:
                for i, y in enumerate(data[1:], 1):
                    label = legends[i-1] if i-1 < len(legends) else f"Series {i}"
                    ax.plot(x, y, label=label, linewidth=1.2)
                ax.legend(loc='best', frameon=True, fontsize=9)
            elif "柱状图" in plot_type:
                ax.bar(x, data[1], width=0.8, color='#1976D2', edgecolor='black', linewidth=0.5)
            elif "散点图" in plot_type:
                ax.scatter(x, data[1], s=20, color='#C2185B', alpha=0.6, edgecolors='black', linewidth=0.3)
            else:
                # 折线图
                for i, y in enumerate(data[1:], 1):
                    label = legends[i-1] if i-1 < len(legends) else f"Series {i}"
                    ax.plot(x, y, label=label, linewidth=1.2, color='#1565C0')
                if len(data) > 2 or legends:
                    ax.legend(loc='best', frameon=True, fontsize=9)

            # 设置样式
            ax.set_xlabel(xlabel, fontsize=11, fontweight='bold')
            ax.set_ylabel(ylabel, fontsize=11, fontweight='bold')
            if title:
                ax.set_title(title, fontsize=12, fontweight='bold')
            ax.grid(True, linestyle='--', alpha=0.5)
            ax.tick_params(labelsize=9)

            # 移除顶部和右侧边框
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)

            plt.tight_layout()
            output_path = os.path.join(wd, output)
            plt.savefig(output_path, dpi=dpi, bbox_inches='tight')
            plt.close()

            self.add_log(f"图表生成成功: {output} ({dpi}dpi)", "success")
        except ImportError:
            QMessageBox.warning(self, "警告", "未安装matplotlib！请运行: pip install matplotlib")
        except Exception as e:
            self.add_log(f"绘图失败: {str(e)}", "error")

    # -------------------------------------------------------------------------
    # Part 4: 轨迹处理工具
    # -------------------------------------------------------------------------
    def create_trajectory_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        vbox = QVBoxLayout(content)
        vbox.setSpacing(12)
        vbox.setContentsMargins(8, 10, 8, 10)

        common_group = QGroupBox("轨迹处理参数")
        common_group.setStyleSheet("QGroupBox { font-weight: bold; color: #1565C0; }")
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

        # === 预处理流水线 (新增) ===
        prep_group = QGroupBox("🔄 轨迹预处理流水线")
        prep_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold; color: #1565C0;
                margin-top: 8px; padding-top: 8px;
                border: 2px solid #1976D2; border-radius: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin; left: 10px; padding: 0 5px;
            }
        """)
        prep_layout = QVBoxLayout(prep_group)
        prep_layout.setSpacing(8)

        # 说明标签
        prep_desc = QLabel(
            "标准预处理五步法：PBC修复 → 体系居中 → 去除平动/转动 → 截取平衡段 → 降采样精简"
        )
        prep_desc.setWordWrap(True)
        prep_desc.setStyleSheet("color: #0D47A1; font-size: 11px;")
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
        self.prep_run_btn.setStyleSheet("""
            QPushButton {
                background-color: #1565C0; color: white; font-weight: bold;
                padding: 6px 16px; border-radius: 4px; font-size: 12px;
            }
            QPushButton:hover { background-color: #0D47A1; }
        """)
        self.prep_run_btn.clicked.connect(self._run_preprocessing_pipeline)
        prep_layout.addWidget(self.prep_run_btn)

        vbox.addWidget(prep_group)

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
            grp.setStyleSheet("QGroupBox { font-weight: bold; color: #311B92; margin-top: 4px; }")
            g = QGridLayout(grp)
            g.addWidget(QLabel(desc), 0, 0, 1, 4)

            out_edit = QLineEdit(default_out)
            opt_edit = QLineEdit()
            opt_edit.setPlaceholderText("如 -pbc mol -center -fit rot+trans")

            run_btn = QPushButton("运行")
            run_btn.setStyleSheet(
                "QPushButton { background-color: #5E35B1; color: white; font-weight: bold; padding: 4px 12px; }"
                "QPushButton:hover { background-color: #512DA8; }"
            )

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
            run_btn.clicked.connect(lambda checked, k=key: self.run_trajectory_tool(k))
            vbox.addWidget(grp)

        vbox.addStretch()
        return tab

    # -------------------------------------------------------------------------
    # Part 2: 结构处理工具
    # -------------------------------------------------------------------------
    def create_structure_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        vbox = QVBoxLayout(content)
        vbox.setSpacing(12)
        vbox.setContentsMargins(8, 10, 8, 10)

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

        # --- 创建索引 (最突出的位置) ---
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
            btn.clicked.connect(lambda checked, expr=select_expr: ndx_opt_edit.setText(expr))
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

        # --- 其他结构准备工具 ---
        prep_tools = [
            ("editconf", "编辑结构 (editconf)", "修改盒子参数、旋转、平移、居中对齐等", "protein_edit.gro", "#00897B"),
            ("pdb2gmx", "生成拓扑 (pdb2gmx)", "从PDB结构生成GROMACS拓扑文件", "protein.gro", "#00897B"),
            ("gmx genrestr", "生成位置限制 (genrestr)", "生成位置限制文件 (posre.itp)", "posre.itp", "#00897B"),
            ("genconf", "生成构象 (genconf)", "生成多个结构副本或旋转构象", "protein_multi.gro", "#00897B"),
        ]

        for key, name, desc, default_out, color in prep_tools:
            grp = QGroupBox(name)
            grp.setStyleSheet(f"""
                QGroupBox {{
                    font-weight: bold;
                    color: #00695C;
                    margin-top: 4px;
                    border: 1px solid #4DB6AC;
                    border-radius: 6px;
                }}
                QGroupBox::title {{
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px;
                }}
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
                QPushButton:hover {{ background-color: {self._adjust_brightness(color, 0.9)}; }}
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
            run_btn.clicked.connect(lambda checked, k=key: self.run_structure_tool(k))
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
            grp.setStyleSheet(f"""
                QGroupBox {{
                    font-weight: bold;
                    color: #0D47A1;
                    margin-top: 4px;
                    border: 1px solid #64B5F6;
                    border-radius: 6px;
                }}
                QGroupBox::title {{
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px;
                }}
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
                QPushButton:hover {{ background-color: {self._adjust_brightness(color, 0.9)}; }}
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
            run_btn.clicked.connect(lambda checked, k=key: self.run_structure_tool(k))
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
        tip_label.setWordWrap(True)
        vbox.addWidget(tip_label)

        vbox.addStretch()
        return tab

    # -------------------------------------------------------------------------
    # Part 6: MMPBSA
    # -------------------------------------------------------------------------
    def create_mmpbsa_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        vbox = QVBoxLayout(content)
        vbox.setSpacing(14)
        vbox.setContentsMargins(8, 10, 8, 10)

        info = QLabel(
            "MMPBSA (Molecular Mechanics Poisson-Boltzmann Surface Area) "
            "结合自由能计算。\n请确保已安装 gmx_MMPBSA 或相关脚本。"
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #555; font-size: 12px;")
        vbox.addWidget(info)

        inp_group = QGroupBox("输入文件参数")
        inp_group.setStyleSheet("QGroupBox { font-weight: bold; color: #1565C0; }")
        igrid = QGridLayout(inp_group)

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

        vbox.addWidget(inp_group)

        sam_group = QGroupBox("采样与计算参数")
        sam_group.setStyleSheet("QGroupBox { font-weight: bold; color: #2E7D32; }")
        sgrid = QGridLayout(sam_group)

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

        vbox.addWidget(sam_group)

        img_group = QGroupBox("结果图片输出设置")
        img_group.setStyleSheet("QGroupBox { font-weight: bold; color: #E65100; }")
        imgrid = QGridLayout(img_group)

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

        vbox.addWidget(img_group)

        run_layout = QHBoxLayout()
        self.mmpbsa_run_btn = QPushButton("运行 MMPBSA 计算")
        self.mmpbsa_run_btn.setStyleSheet(
            "QPushButton { background-color: #9C27B0; color: white; font-weight: bold; font-size: 14px; padding: 10px 24px; }"
            "QPushButton:hover { background-color: #7B1FA2; }"
        )
        self.mmpbsa_run_btn.clicked.connect(self.run_mmpbsa)
        run_layout.addStretch()
        run_layout.addWidget(self.mmpbsa_run_btn)
        run_layout.addStretch()
        vbox.addLayout(run_layout)

        vbox.addStretch()
        return tab

    # -------------------------------------------------------------------------
    # 右侧面板
    # -------------------------------------------------------------------------
    def create_right_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        log_group = QGroupBox("实时运行日志")
        log_group.setStyleSheet("QGroupBox { font-weight: bold; color: #333; }")
        log_layout = QVBoxLayout(log_group)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 10))
        self.log_text.setLineWrapMode(QTextEdit.WidgetWidth)
        log_layout.addWidget(self.log_text)

        layout.addWidget(log_group, stretch=1)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p% - %v/%m")
        layout.addWidget(self.progress_bar)

        btn_layout = QHBoxLayout()
        self.clear_log_btn = QPushButton("清除日志")
        self.clear_log_btn.clicked.connect(self.clear_log)
        self.export_log_btn = QPushButton("导出日志")
        self.export_log_btn.clicked.connect(self.export_log)
        self.diagnosis_btn = QPushButton("查看错误诊断")
        self.diagnosis_btn.setStyleSheet(
            "QPushButton { background-color: #9C27B0; color: white; font-weight: bold; padding: 6px 16px; }"
            "QPushButton:hover { background-color: #7B1FA2; }"
            "QPushButton:disabled { background-color: #BA68C8; }"
        )
        self.diagnosis_btn.clicked.connect(self.show_error_diagnosis)
        self.diagnosis_btn.setToolTip("查看最近错误的诊断结果和修复建议")
        btn_layout.addStretch()
        btn_layout.addWidget(self.diagnosis_btn)
        btn_layout.addWidget(self.clear_log_btn)
        btn_layout.addWidget(self.export_log_btn)
        layout.addLayout(btn_layout)

        return panel

    def _setup_log_colors(self):
        self._color_info = QColor("#4FC3F7")
        self._color_success = QColor("#69F0AE")
        self._color_warning = QColor("#FFB74D")
        self._color_error = QColor("#EF5350")
        self._color_cmd = QColor("#CE93D8")
        self._color_default = QColor("#E0E0E0")

    def toggle_theme(self):
        if self.current_theme == "dark":
            self._apply_light_theme()
        else:
            self._apply_dark_theme()

    def _apply_dark_theme(self):
        self.current_theme = "dark"
        self.theme_btn.setText("浅色主题")
        self.theme_btn.setStyleSheet(
            "QPushButton { background-color: #2A82DA; color: white; font-weight: bold; padding: 6px 16px; }"
            "QPushButton:hover { background-color: #1E6BB8; }"
        )

        app = QApplication.instance()
        app.setStyleSheet("")

        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(53, 53, 53))
        palette.setColor(QPalette.WindowText, Qt.white)
        palette.setColor(QPalette.Base, QColor(35, 35, 35))
        palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
        palette.setColor(QPalette.ToolTipBase, Qt.white)
        palette.setColor(QPalette.ToolTipText, Qt.white)
        palette.setColor(QPalette.Text, Qt.white)
        palette.setColor(QPalette.Button, QColor(53, 53, 53))
        palette.setColor(QPalette.ButtonText, Qt.white)
        palette.setColor(QPalette.BrightText, Qt.red)
        palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.HighlightedText, Qt.black)
        app.setPalette(palette)

        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #444;
            }
        """)

        self._update_groupbox_styles_dark()

    def _apply_light_theme(self):
        self.current_theme = "light"
        self.theme_btn.setText("深色主题")
        self.theme_btn.setStyleSheet(
            "QPushButton { background-color: #FFFFFF; color: #1E6BB8; font-weight: bold; padding: 6px 16px; border: 1px solid #2A82DA; }"
            "QPushButton:hover { background-color: #E3F2FD; }"
        )

        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(245, 245, 245))
        palette.setColor(QPalette.WindowText, QColor(33, 33, 33))
        palette.setColor(QPalette.Base, QColor(255, 255, 255))
        palette.setColor(QPalette.AlternateBase, QColor(240, 240, 240))
        palette.setColor(QPalette.ToolTipBase, QColor(255, 255, 255))
        palette.setColor(QPalette.ToolTipText, QColor(33, 33, 33))
        palette.setColor(QPalette.Text, QColor(33, 33, 33))
        palette.setColor(QPalette.Button, QColor(230, 230, 230))
        palette.setColor(QPalette.ButtonText, QColor(33, 33, 33))
        palette.setColor(QPalette.BrightText, Qt.red)
        palette.setColor(QPalette.Highlight, QColor(25, 118, 210))
        palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
        palette.setColor(QPalette.PlaceholderText, QColor(128, 128, 128))
        QApplication.instance().setPalette(palette)

        app = QApplication.instance()
        app.setStyleSheet("""
            QMainWindow {
                background-color: #F5F5F5;
            }
            QWidget {
                color: #212121;
            }
            QGroupBox {
                font-weight: bold;
                color: #0D47A1;
                margin-top: 8px;
                border: 1px solid #BBDEFB;
                border-radius: 4px;
                padding-top: 8px;
                background-color: #FAFAFA;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
                color: #0D47A1;
            }
            QLineEdit {
                background-color: #FFFFFF;
                color: #212121;
                border: 1px solid #BDBDBD;
                border-radius: 3px;
                padding: 4px;
                selection-background-color: #1976D2;
            }
            QLineEdit:focus {
                border: 1px solid #1976D2;
            }
            QComboBox {
                background-color: #FFFFFF;
                color: #212121;
                border: 1px solid #BDBDBD;
                border-radius: 3px;
                padding: 4px;
                min-width: 80px;
            }
            QComboBox:focus {
                border: 1px solid #1976D2;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QComboBox QAbstractItemView {
                background-color: #FFFFFF;
                color: #212121;
                selection-background-color: #BBDEFB;
                selection-color: #0D47A1;
            }
            QSpinBox, QDoubleSpinBox {
                background-color: #FFFFFF;
                color: #212121;
                border: 1px solid #BDBDBD;
                border-radius: 3px;
                padding: 4px;
            }
            QLabel {
                color: #424242;
            }
            QCheckBox {
                color: #424242;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QRadioButton {
                color: #424242;
            }
            QTabWidget::pane {
                border: 1px solid #BDBDBD;
                background-color: #FAFAFA;
            }
            QTabBar::tab {
                background-color: #E0E0E0;
                color: #616161;
                padding: 8px 16px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: #FAFAFA;
                color: #0D47A1;
                font-weight: bold;
            }
            QTabBar::tab:hover:!selected {
                background-color: #EEEEEE;
            }
            QScrollArea {
                border: none;
            }
            QTextEdit {
                background-color: #FFFFFF;
                color: #212121;
                border: 1px solid #BDBDBD;
                border-radius: 3px;
            }
            QPlainTextEdit {
                background-color: #FFFFFF;
                color: #212121;
                border: 1px solid #BDBDBD;
                border-radius: 3px;
            }
            QListWidget {
                background-color: #FFFFFF;
                color: #212121;
                border: 1px solid #BDBDBD;
                border-radius: 3px;
            }
            QListWidget::item:selected {
                background-color: #BBDEFB;
                color: #0D47A1;
            }
            QProgressBar {
                border: 1px solid #BDBDBD;
                border-radius: 4px;
                text-align: center;
                color: #212121;
            }
            QProgressBar::chunk {
                background-color: #1976D2;
                border-radius: 3px;
            }
            QMenuBar {
                background-color: #F5F5F5;
                color: #212121;
            }
            QMenuBar::item:selected {
                background-color: #BBDEFB;
                color: #0D47A1;
            }
            QMenu {
                background-color: #FFFFFF;
                color: #212121;
                border: 1px solid #BDBDBD;
            }
            QMenu::item:selected {
                background-color: #BBDEFB;
                color: #0D47A1;
            }
            QToolTip {
                background-color: #FFF8E1;
                color: #212121;
                border: 1px solid #FFC107;
                padding: 4px;
            }
        """)

        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #FFFFFF;
                color: #333333;
                border: 1px solid #CCCCCC;
            }
        """)

        self._update_groupbox_styles_light()

    def _update_groupbox_styles_dark(self):
        widgets = self.findChildren(QGroupBox)
        for w in widgets:
            current_style = w.styleSheet()
            if "border:" in current_style and "border-radius" in current_style:
                continue
            dark_group_style = "QGroupBox { font-weight: bold; color: #90CAF9; margin-top: 8px; }"
            w.setStyleSheet(dark_group_style)

    def _update_groupbox_styles_light(self):
        widgets = self.findChildren(QGroupBox)
        for w in widgets:
            current_style = w.styleSheet()
            if "border:" in current_style and "border-radius" in current_style:
                continue
            light_group_style = "QGroupBox { font-weight: bold; color: #1565C0; margin-top: 8px; }"
            w.setStyleSheet(light_group_style)

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
        """盒子设置方式切换回调"""
        self._on_box_type_changed(self.md_box_type.currentText())

    def _on_box_type_changed(self, text):
        """盒子类型切换回调"""
        is_rect = "rectangular" in text.lower()
        is_triclinic = "triclinic" in text.lower()
        is_box_mode = "边长" in self.md_box_size_mode.currentText()
        is_single_val = is_box_mode and not is_rect and not is_triclinic
        show_xyz = is_rect and is_box_mode
        show_angles = is_triclinic and is_box_mode

        self.lbl_box_size.setVisible(not is_box_mode)
        self.md_box_size.setVisible(not is_box_mode)

        self.lbl_box_a.setVisible(is_single_val)
        self.md_box_a.setVisible(is_single_val)
        if is_single_val:
            self.lbl_box_a.setText("盒子边长:")

        self.lbl_box_x.setVisible(show_xyz)
        self.md_box_x.setVisible(show_xyz)
        self.lbl_box_y.setVisible(show_xyz)
        self.md_box_y.setVisible(show_xyz)
        self.lbl_box_z.setVisible(show_xyz)
        self.md_box_z.setVisible(show_xyz)

        self.lbl_angle_alpha.setVisible(show_angles)
        self.md_angle_alpha.setVisible(show_angles)
        self.lbl_angle_beta.setVisible(show_angles)
        self.md_angle_beta.setVisible(show_angles)
        self.lbl_angle_gamma.setVisible(show_angles)
        self.md_angle_gamma.setVisible(show_angles)
        if is_triclinic and is_box_mode:
            self.lbl_box_a.setText("边长a:")

    def _get_box_params(self):
        """获取editconf盒子参数 -bt 和 -box/-d"""
        bt_full = self.md_box_type.currentText()
        if "cubic" in bt_full.lower():
            bt = "cubic"
        elif "triclinic" in bt_full.lower():
            bt = "triclinic"
        elif "dodecahedron" in bt_full.lower():
            bt = "dodecahedron"
        elif "octahedron" in bt_full.lower():
            bt = "octahedron"
        else:
            bt = "triclinic"
        is_rect = "rectangular" in bt_full.lower()
        is_triclinic = "triclinic" in bt_full.lower()
        is_box_mode = "边长" in self.md_box_size_mode.currentText()
        params = []
        if self.md_princ.isChecked():
            params.append("-princ")
        if is_box_mode:
            if is_rect:
                x = self.md_box_x.value()
                y = self.md_box_y.value()
                z = self.md_box_z.value()
                params += ["-box", str(x), str(y), str(z)]
            elif is_triclinic:
                a = self.md_box_a.value()
                alpha = self.md_angle_alpha.value()
                beta = self.md_angle_beta.value()
                gamma = self.md_angle_gamma.value()
                params += ["-box", str(a), str(a), str(a), "-angles", str(alpha), str(beta), str(gamma)]
            else:
                a = self.md_box_a.value()
                params += ["-box", str(a), "-bt", bt]
        else:
            d = self.md_box_size.value()
            params += ["-c", "-d", str(d), "-bt", bt]
        return params

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
        for widgets in self.analysis_widgets.values():
            widgets["run_btn"].setEnabled(not running)
        for widgets in self.traj_widgets.values():
            widgets["run_btn"].setEnabled(not running)
        for widgets in self.struc_widgets.values():
            widgets["run_btn"].setEnabled(not running)
        self.mmpbsa_run_btn.setEnabled(not running)
        self.umb_run_btn.setEnabled(not running)
        self.wham_run_btn.setEnabled(not running)
        self.meta_run_btn.setEnabled(not running)
        self.meta_gen_btn.setEnabled(not running)
        self.abf_gen_btn.setEnabled(not running)
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
    # Part 1: MD 各步骤执行
    # -------------------------------------------------------------------------
    def _on_use_existing_toggled(self, checked):
        self.step1_widget.setVisible(not checked)
        self.step1_existing.setVisible(checked)
        
        # 当使用已有拓扑时，隐藏不相关的全局参数
        # 隐藏力场和水模型（第0行）
        if hasattr(self, 'lbl_ff'):
            self.lbl_ff.setVisible(not checked)
        self.md_ff.setVisible(not checked)
        if hasattr(self, 'lbl_water'):
            self.lbl_water.setVisible(not checked)
        self.md_water.setVisible(not checked)
        
        # 隐藏盒子类型和设置方式（第1行）
        if hasattr(self, 'lbl_box_type'):
            self.lbl_box_type.setVisible(not checked)
        self.md_box_type.setVisible(not checked)
        self.md_box_size_mode.setVisible(not checked)
        
        # 隐藏盒子边距
        self.lbl_box_size.setVisible(not checked and not self.md_box_size_mode.currentText().startswith("按盒子"))
        self.md_box_size.setVisible(not checked and not self.md_box_size_mode.currentText().startswith("按盒子"))
        
        # 隐藏盒子边长a
        self.lbl_box_a.setVisible(not checked and self.lbl_box_a.isVisible())
        self.md_box_a.setVisible(not checked and self.md_box_a.isVisible())
        
        # 隐藏盒子XYZ边长
        self.lbl_box_x.setVisible(not checked and self.lbl_box_x.isVisible())
        self.md_box_x.setVisible(not checked and self.md_box_x.isVisible())
        self.lbl_box_y.setVisible(not checked and self.lbl_box_y.isVisible())
        self.md_box_y.setVisible(not checked and self.md_box_y.isVisible())
        self.lbl_box_z.setVisible(not checked and self.lbl_box_z.isVisible())
        self.md_box_z.setVisible(not checked and self.md_box_z.isVisible())
        
        # 隐藏三斜角度
        self.lbl_angle_alpha.setVisible(not checked and self.lbl_angle_alpha.isVisible())
        self.md_angle_alpha.setVisible(not checked and self.md_angle_alpha.isVisible())
        self.lbl_angle_beta.setVisible(not checked and self.lbl_angle_beta.isVisible())
        self.md_angle_beta.setVisible(not checked and self.md_angle_beta.isVisible())
        self.lbl_angle_gamma.setVisible(not checked and self.lbl_angle_gamma.isVisible())
        self.md_angle_gamma.setVisible(not checked and self.md_angle_gamma.isVisible())
        
        self.md_princ.setVisible(not checked)
        
        # 隐藏离子浓度（第2行部分）
        if hasattr(self, 'lbl_ion'):
            self.lbl_ion.setVisible(not checked)
        self.md_ion_conc.setVisible(not checked)
        
        # 隐藏输入PDB（第5行部分）
        if hasattr(self, 'lbl_pdb'):
            self.lbl_pdb.setVisible(not checked)
        self.md_pdb.setVisible(not checked)
        
        # 当使用已有拓扑时，自动勾选跳过选项
        if checked:
            self.skip_editconf.setChecked(True)
            self.skip_solvate.setChecked(True)
            self.skip_genion.setChecked(True)
        
        if checked:
            if hasattr(self, 'md_step_btns') and "Step 2" in self.md_step_btns:
                step2_info = self.md_step_btns["Step 2"]
                edits = step2_info["edits"]
                if edits:
                    edits[0].setText(self.se_gro_edit.text().strip() or "input.gro")
            if hasattr(self, 'md_step_btns') and "Step 3" in self.md_step_btns:
                step3_info = self.md_step_btns["Step 3"]
                edits = step3_info["edits"]
                if edits:
                    edits[0].setText("protein_box.gro")
        self._update_skip_steps_visibility()

    def _on_skip_toggled(self, checked):
        self._update_skip_steps_visibility()

    def _update_skip_steps_visibility(self):
        if not hasattr(self, 'md_step_btns'):
            return
        if "Step 2" in self.md_step_btns:
            self.md_step_btns["Step 2"]["group"].setVisible(not self.skip_editconf.isChecked())
        if "Step 3" in self.md_step_btns:
            self.md_step_btns["Step 3"]["group"].setVisible(not self.skip_solvate.isChecked())
        if "Step 4" in self.md_step_btns:
            self.md_step_btns["Step 4"]["group"].setVisible(not self.skip_genion.isChecked())

    def run_md_step(self, step_key):
        try:
            wd = self._get_work_dir()
            if not wd:
                return

            gmx = self.gmx_path
            if not gmx or not os.path.isfile(gmx):
                self.add_log(f"错误: GROMACS可执行文件不存在 - {gmx}", "error")
                return

            if step_key not in self.md_step_btns:
                self.add_log(f"错误: 步骤不存在 - {step_key}", "error")
                return

            info = self.md_step_btns[step_key]
            edits = info["edits"]
            labels = info["labels"]

            def get_val(idx):
                return edits[idx].text().strip() if idx < len(edits) else ""

            def make_cmd(base):
                return [gmx] + base

            ff = self.md_ff.currentText()
            water = self.md_water.currentText()
            box_type = self.md_box_type.currentText()
            box_size = self.md_box_size.value()
            ion_conc = self.md_ion_conc.value()
            pdb = self.md_pdb.text().strip() or "protein.pdb"

            cmd = []
            step_name = step_key

            if step_key == "Step 1":
                if self.use_existing_top.isChecked():
                    struct_file = self.se_gro_edit.text().strip() or "input.gro"
                    top = self.se_top_edit.text().strip() or "topol.top"
                    struct_path = os.path.join(wd, struct_file)
                    top_path = os.path.join(wd, top)
                    if not os.path.isfile(struct_path):
                        self.add_log(f"错误: 结构文件不存在 - {struct_path}", "error")
                        return
                    if not os.path.isfile(top_path):
                        self.add_log(f"错误: TOP文件不存在 - {top_path}", "error")
                        return
                    self.add_log(f"使用已有拓扑: STRUCT={struct_file}, TOP={top}", "info")
                    self.add_log("已跳过pdb2gmx，直接使用现有文件", "success")
                    return
                gro = get_val(1) or "protein.gro"
                top = get_val(2) or "topol.top"
                posre = get_val(3) or "posre.itp"
                inp = get_val(0) or pdb
                cmd = make_cmd([
                    "pdb2gmx", "-f", inp, "-o", gro, "-p", top,
                    "-i", posre, "-ff", ff, "-water", water, "-ignh"
                ])
                step_name = "pdb2gmx"

            elif step_key == "Step 2":
                ingro = get_val(0) or "protein.gro"
                outgro = get_val(1) or "protein_box.gro"
                info = self.md_step_btns[step_key]
                bt_full = info["box_type_combo"].currentText()
                if "cubic" in bt_full.lower():
                    bt = "cubic"
                elif "triclinic" in bt_full.lower():
                    bt = "triclinic"
                elif "dodecahedron" in bt_full.lower():
                    bt = "dodecahedron"
                elif "octahedron" in bt_full.lower():
                    bt = "octahedron"
                else:
                    bt = "triclinic"
                is_rect = "rectangular" in bt_full.lower()
                is_triclinic = "triclinic" in bt_full.lower()
                is_box_mode = "边长" in info["size_mode_combo"].currentText()
                params = []
                if info["center_check"].isChecked():
                    params.append("-c")
                if info["princ_check"].isChecked():
                    params.append("-princ")
                if is_box_mode:
                    if is_rect:
                        x = info["box_x_spin"].value()
                        y = info["box_y_spin"].value()
                        z = info["box_z_spin"].value()
                        params += ["-box", str(x), str(y), str(z)]
                    elif is_triclinic:
                        a = info["box_a_spin"].value()
                        alpha = info["angle_alpha_spin"].value()
                        beta = info["angle_beta_spin"].value()
                        gamma = info["angle_gamma_spin"].value()
                        params += ["-box", str(a), str(a), str(a), "-angles", str(alpha), str(beta), str(gamma)]
                    else:
                        a = info["box_a_spin"].value()
                        params += ["-box", str(a), "-bt", bt]
                else:
                    params += ["-bt", bt]
                    d = info["box_size_spin"].value()
                    params += ["-d", str(d)]
                cmd = make_cmd([
                    "editconf", "-f", ingro, "-o", outgro
                ] + params)
                step_name = "editconf"

            elif step_key == "Step 3":
                ingro = get_val(0) or "protein_box.gro"
                outgro = get_val(1) or "protein_solv.gro"
                top = get_val(2) or "topol.top"
                cmd = make_cmd([
                    "solvate", "-cp", ingro, "-o", outgro, "-p", top
                ])
                step_name = "solvate"

            elif step_key == "Step 4":
                ingro = get_val(0) or "protein_solv.gro"
                outgro = get_val(1) or "protein_ions.gro"
                top = get_val(2) or "topol.top"
                mdp = get_val(3) or "ions.mdp"
                tpr = "ions.tpr"
                conc_str = str(ion_conc)
                cmd1 = make_cmd([
                    "grompp", "-f", mdp, "-c", ingro, "-p", top,
                    "-o", tpr, "-maxwarn", "2"
                ])
                cmd2 = make_cmd([
                    "genion", "-s", tpr, "-o", outgro, "-p", top,
                    "-pname", "NA", "-nname", "CL", "-neutral",
                    "-conc", conc_str, "-quiet"
                ])
                self.run_command([cmd1, cmd2], wd, step_name="genion")
                return

            elif step_key == "Step 5":
                mdp = get_val(0) or "em.mdp"
                default_gro = self.se_gro_edit.text().strip() or "input.gro" if self.use_existing_top.isChecked() else "protein_ions.gro"
                ingro = get_val(1) or default_gro
                tpr = get_val(2) or "em.tpr"
                top = self.se_top_edit.text().strip() if self.use_existing_top.isChecked() else "topol.top"
                cmd = make_cmd([
                    "grompp", "-f", mdp, "-c", ingro, "-p", top,
                    "-o", tpr, "-maxwarn", "2"
                ])
                step_name = "grompp (EM)"

            elif step_key == "Step 6":
                tpr = get_val(0) or "em.tpr"
                if tpr.endswith(".tpr.tpr"):
                    tpr = tpr[:-4]
                    self.add_log(f"警告: 检测到重复扩展名，已自动修正为 {tpr}", "warning")
                info = self.md_step_btns[step_key]
                custom_check = info.get("custom_out_check")
                custom_edit = info.get("custom_out_edit")
                if custom_check and custom_check.isChecked() and custom_edit and custom_edit.text().strip():
                    deffnm = custom_edit.text().strip()
                else:
                    deffnm = os.path.splitext(tpr)[0]
                extra = self._get_mdrun_extra(is_em=True)
                restart_check = info.get("restart_check")
                if restart_check and restart_check.isChecked():
                    cpt_file = os.path.join(wd, f"{deffnm}.cpt")
                    if os.path.isfile(cpt_file):
                        extra += ["-cpi", f"{deffnm}.cpt", "-append"]
                        self.add_log(f"检测到检查点文件，将断点续跑: {deffnm}.cpt", "info")
                    else:
                        self.add_log(f"警告: 未找到检查点文件 {deffnm}.cpt，将从头开始", "warning")
                cmd = make_cmd([
                    "mdrun", "-v", "-deffnm", deffnm
                ] + extra)
                step_name = "mdrun (EM)"

            elif step_key == "Step 7":
                mdp = get_val(0) or "nvt.mdp"
                default_gro = self.se_gro_edit.text().strip() or "input.gro" if self.use_existing_top.isChecked() else "em.gro"
                ingro = get_val(1) or default_gro
                tpr = get_val(2) or "nvt.tpr"
                top = self.se_top_edit.text().strip() if self.use_existing_top.isChecked() else "topol.top"
                cmd = make_cmd([
                    "grompp", "-f", mdp, "-c", ingro, "-r", ingro,
                    "-p", top, "-o", tpr, "-maxwarn", "2"
                ])
                step_name = "grompp (NVT)"

            elif step_key == "Step 8":
                tpr = get_val(0) or "nvt.tpr"
                if tpr.endswith(".tpr.tpr"):
                    tpr = tpr[:-4]
                    self.add_log(f"警告: 检测到重复扩展名，已自动修正为 {tpr}", "warning")
                info = self.md_step_btns[step_key]
                custom_check = info.get("custom_out_check")
                custom_edit = info.get("custom_out_edit")
                if custom_check and custom_check.isChecked() and custom_edit and custom_edit.text().strip():
                    deffnm = custom_edit.text().strip()
                else:
                    deffnm = os.path.splitext(tpr)[0]
                extra = self._get_mdrun_extra()
                restart_check = info.get("restart_check")
                if restart_check and restart_check.isChecked():
                    cpt_file = os.path.join(wd, f"{deffnm}.cpt")
                    if os.path.isfile(cpt_file):
                        extra += ["-cpi", f"{deffnm}.cpt", "-append"]
                        self.add_log(f"检测到检查点文件，将断点续跑: {deffnm}.cpt", "info")
                    else:
                        self.add_log(f"警告: 未找到检查点文件 {deffnm}.cpt，将从头开始", "warning")
                cmd = make_cmd([
                    "mdrun", "-deffnm", deffnm
                ] + extra)
                step_name = "mdrun (NVT)"

            elif step_key == "Step 9":
                mdp = get_val(0) or "npt.mdp"
                ingro = get_val(1) or "nvt.gro"
                tpr = get_val(2) or "npt.tpr"
                top = self.se_top_edit.text().strip() if self.use_existing_top.isChecked() else "topol.top"
                cmd = make_cmd([
                    "grompp", "-f", mdp, "-c", ingro, "-r", ingro,
                    "-p", top, "-o", tpr, "-maxwarn", "2"
                ])
                step_name = "grompp (NPT)"

            elif step_key == "Step 10":
                tpr = get_val(0) or "npt.tpr"
                if tpr.endswith(".tpr.tpr"):
                    tpr = tpr[:-4]
                    self.add_log(f"警告: 检测到重复扩展名，已自动修正为 {tpr}", "warning")
                info = self.md_step_btns[step_key]
                custom_check = info.get("custom_out_check")
                custom_edit = info.get("custom_out_edit")
                if custom_check and custom_check.isChecked() and custom_edit and custom_edit.text().strip():
                    deffnm = custom_edit.text().strip()
                else:
                    deffnm = os.path.splitext(tpr)[0]
                extra = self._get_mdrun_extra()
                restart_check = info.get("restart_check")
                if restart_check and restart_check.isChecked():
                    cpt_file = os.path.join(wd, f"{deffnm}.cpt")
                    if os.path.isfile(cpt_file):
                        extra += ["-cpi", f"{deffnm}.cpt", "-append"]
                        self.add_log(f"检测到检查点文件，将断点续跑: {deffnm}.cpt", "info")
                    else:
                        self.add_log(f"警告: 未找到检查点文件 {deffnm}.cpt，将从头开始", "warning")
                cmd = make_cmd([
                    "mdrun", "-deffnm", deffnm
                ] + extra)
                step_name = "mdrun (NPT)"

            elif step_key == "Step 11":
                mdp = get_val(0) or "md.mdp"
                ingro = get_val(1) or "npt.gro"
                tpr = get_val(2) or "md.tpr"
                top = self.se_top_edit.text().strip() if self.use_existing_top.isChecked() else "topol.top"
                cmd = make_cmd([
                    "grompp", "-f", mdp, "-c", ingro, "-r", ingro,
                    "-p", top, "-o", tpr, "-maxwarn", "2"
                ])
                step_name = "grompp (MD)"

            elif step_key == "Step 12":
                tpr = get_val(0) or "md.tpr"
                if tpr.endswith(".tpr.tpr"):
                    tpr = tpr[:-4]
                    self.add_log(f"警告: 检测到重复扩展名，已自动修正为 {tpr}", "warning")
                info = self.md_step_btns[step_key]
                custom_check = info.get("custom_out_check")
                custom_edit = info.get("custom_out_edit")
                if custom_check and custom_check.isChecked() and custom_edit and custom_edit.text().strip():
                    deffnm = custom_edit.text().strip()
                else:
                    deffnm = os.path.splitext(tpr)[0]
                extra = self._get_mdrun_extra()
                restart_check = info.get("restart_check")
                if restart_check and restart_check.isChecked():
                    cpt_file = os.path.join(wd, f"{deffnm}.cpt")
                    if os.path.isfile(cpt_file):
                        extra += ["-cpi", f"{deffnm}.cpt", "-append"]
                        self.add_log(f"检测到检查点文件，将断点续跑: {deffnm}.cpt", "info")
                    else:
                        self.add_log(f"警告: 未找到检查点文件 {deffnm}.cpt，将从头开始", "warning")
                cmd = make_cmd([
                    "mdrun", "-deffnm", deffnm
                ] + extra)
                step_name = "mdrun (MD)"

            else:
                self.add_log(f"未知步骤: {step_key}", "error")
                return

            self.run_command([cmd], wd, step_name)
        except Exception as e:
            self.add_log(f"运行步骤 {step_key} 时发生错误: {str(e)}", "error")

    def run_evap_step(self):
        """第五阶段: 溶剂/添加剂蒸发 - 循环删除分子并跑NPT"""
        try:
            wd = self._get_work_dir()
            if not wd:
                return

            gmx = self.gmx_path
            if not gmx or not os.path.isfile(gmx):
                self.add_log(f"错误: GROMACS可执行文件不存在 - {gmx}", "error")
                return

            python_exe = sys.executable
            if getattr(sys, 'frozen', False):
                import shutil
                python_exe = shutil.which('python') or shutil.which('python3')
                if not python_exe:
                    self.add_log("错误: 无法找到Python解释器，请确保Python已添加到系统PATH", "error")
                    return
            if not python_exe or not os.path.isfile(python_exe):
                self.add_log(f"错误: 找不到Python解释器 - {python_exe}", "error")
                return

            # 获取参数
            mode_idx = self.evap_mode.currentIndex()
            input_gro = self.evap_gro_edit.text().strip()
            top_file = self.evap_top_edit.text().strip()
            mdp_file = self.evap_mdp_edit.text().strip()
            resname = self.evap_resname.text().strip()
            atoms_per_mol = self.evap_atoms_per_mol.value()
            prefix = self.evap_prefix.text().strip() or "evap"

            # 断点续跑相关
            restart_check = self.evap_restart_check.isChecked()
            start_loop = self.evap_start_loop.value()

            # 自动检测最后一轮（未勾选断点续跑时）
            if not restart_check:
                existing_loops = []
                for f in os.listdir(wd):
                    if f.startswith(f"{prefix}_") and f.endswith(".gro"):
                        # 匹配 evap_X.gro 格式
                        suffix = f[len(prefix)+1:-4]
                        if suffix.isdigit():
                            existing_loops.append(int(suffix))
                if existing_loops:
                    start_loop = max(existing_loops) + 1
                    self.add_log(f"自动检测到已存在第{max(existing_loops)}轮，将从第{start_loop}轮开始", "info")
                else:
                    start_loop = 1

            # 检查工作目录权限
            if not os.path.exists(wd):
                self.add_log(f"错误: 工作目录不存在 - {wd}", "error")
                return
            try:
                test_file = os.path.join(wd, "_test_write_permission.tmp")
                with open(test_file, "w") as f:
                    f.write("test")
                os.remove(test_file)
            except PermissionError:
                self.add_log(f"错误: 工作目录没有写入权限 - {wd}", "error")
                self.add_log("建议: 1) 以管理员身份运行程序 2) 更换工作目录为用户文件夹 3) 检查目标目录权限设置", "warning")
                return

            # 检查输入
            if not input_gro:
                self.add_log("错误: 请指定输入GRO文件", "error")
                return
            if not top_file:
                self.add_log("错误: 请指定拓扑TOP文件", "error")
                return
            if not mdp_file:
                self.add_log("错误: 请指定MDP文件", "error")
                return
            if not resname:
                self.add_log("错误: 请指定残基名", "error")
                return

            # 校验文件存在（支持相对/绝对路径）
            def _resolve(p):
                return p if os.path.isabs(p) else os.path.join(wd, p)

            for label, p in [("输入GRO", input_gro), ("拓扑TOP", top_file), ("MDP", mdp_file)]:
                if not os.path.isfile(_resolve(p)):
                    self.add_log(f"错误: {label}文件不存在 - {p}", "error")
                    return

            # 写出删除分子脚本到工作目录（纯ASCII，无编码问题）
            if mode_idx == 0:
                sol_script_path = os.path.join(wd, "delete_solvent.py")
                with open(sol_script_path, "w", encoding="utf-8") as f:
                    f.write(DELETE_SOLVENT_SCRIPT)
                self.add_log(f"已写出脚本: {sol_script_path}", "info")
                delete_script = "delete_solvent.py"
            else:
                add_script_path = os.path.join(wd, "delete_additive_all.py")
                with open(add_script_path, "w", encoding="utf-8") as f:
                    f.write(DELETE_ADDITIVE_SCRIPT)
                self.add_log(f"已写出脚本: {add_script_path}", "info")
                delete_script = "delete_additive_all.py"

            # 文件管理命名（参考用户脚本）
            original_gro = f"{prefix}_original.gro"
            original_top = f"{prefix}_original.top"
            work_gro = f"{prefix}_work.gro"
            work_top = f"{prefix}_work.top"
            current_gro = f"{prefix}_current.gro"
            current_top = f"{prefix}_current.top"

            all_cmds = []

            if mode_idx == 0:
                delete_num = self.evap_delete_num.value()
                loops = self.evap_loops.value()
                end_loop = start_loop + loops - 1

                self.add_log(f"开始蒸发溶剂: {resname}, 每轮删除{delete_num}个, 从第{start_loop}轮到第{end_loop}轮", "info")

                import shutil

                if start_loop == 1:
                    shutil.copy(_resolve(input_gro), os.path.join(wd, original_gro))
                    shutil.copy(_resolve(top_file), os.path.join(wd, original_top))
                    self.add_log(f"已备份原始文件: {original_gro}, {original_top}", "info")
                    shutil.copy(_resolve(input_gro), os.path.join(wd, work_gro))
                    shutil.copy(_resolve(top_file), os.path.join(wd, work_top))
                else:
                    prev_loop = start_loop - 1
                    prev_gro = f"{prefix}_{prev_loop}.gro"
                    # 修复：断点续跑时拓扑文件有多种可能来源，依次查找
                    # 1. evap_current.top（程序运行过程中生成的当前拓扑）
                    # 2. evap_{prev_loop}.top（上一轮的最终拓扑）
                    # 3. 用户指定的输入拓扑文件
                    possible_tops = [
                        os.path.join(wd, f"{prefix}_current.top"),
                        os.path.join(wd, f"{prefix}_{prev_loop}.top"),
                        _resolve(top_file),
                    ]
                    prev_top = None
                    for pt in possible_tops:
                        if os.path.isfile(pt):
                            prev_top = pt
                            break

                    if not os.path.isfile(os.path.join(wd, prev_gro)):
                        self.add_log(f"错误: 断点续跑失败，未找到第{prev_loop}轮的GRO文件 - {prev_gro}", "error")
                        return
                    if prev_top is None:
                        self.add_log(f"错误: 断点续跑失败，未找到可用拓扑文件", "error")
                        self.add_log("已查找: " + ", ".join(possible_tops), "error")
                        return
                    shutil.copy(os.path.join(wd, prev_gro), os.path.join(wd, work_gro))
                    shutil.copy(prev_top, os.path.join(wd, work_top))
                    self.add_log(f"断点续跑: 从第{start_loop}轮开始，使用 {prev_gro} 和 {os.path.basename(prev_top)}", "info")

                delete_from = "bottom" if self.evap_source.currentIndex() == 0 else "top"

                for i in range(start_loop, end_loop + 1):
                    new_gro = f"{prefix}_new.gro"
                    new_top = f"{prefix}_new.top"
                    tpr_file = f"{prefix}_{i}.tpr"
                    deffnm = f"{prefix}_{i}"

                    del_cmd = [
                        python_exe, delete_script,
                        "--solvent", resname,
                        "--delete-num", str(delete_num),
                        "--atoms-per-mol", str(atoms_per_mol),
                        "--loop", str(i),
                        "--delete-from", delete_from,
                        "--input", work_gro,
                        "--output", new_gro,
                        "--topology", work_top,
                        "--topology-output", new_top,
                    ]
                    all_cmds.append(del_cmd)

                    mv_gro_cmd = ["cmd", "/c", "move", "/Y", new_gro, work_gro] if platform.system() == "Windows" else ["mv", new_gro, work_gro]
                    all_cmds.append(mv_gro_cmd)
                    mv_top_cmd = ["cmd", "/c", "move", "/Y", new_top, work_top] if platform.system() == "Windows" else ["mv", new_top, work_top]
                    all_cmds.append(mv_top_cmd)

                    grompp_cmd = [
                        gmx, "grompp",
                        "-f", mdp_file,
                        "-c", work_gro,
                        "-p", work_top,
                        "-o", tpr_file,
                        "-maxwarn", "200"
                    ]
                    all_cmds.append(grompp_cmd)

                    mdrun_cmd = [gmx, "mdrun", "-v", "-deffnm", deffnm] + self._get_mdrun_extra()
                    if restart_check and i > start_loop:
                        prev_cpt = f"{prefix}_{i-1}.cpt"
                        if os.path.isfile(os.path.join(wd, prev_cpt)):
                            mdrun_cmd.extend(["-cpi", prev_cpt])
                            self.add_log(f"第{i}轮将从检查点文件续跑: {prev_cpt}", "info")
                    all_cmds.append(mdrun_cmd)

                    cp_gro_cmd = ["cmd", "/c", "copy", "/Y", f"{deffnm}.gro", current_gro] if platform.system() == "Windows" else ["cp", f"{deffnm}.gro", current_gro]
                    all_cmds.append(cp_gro_cmd)
                    cp_top_cmd = ["cmd", "/c", "copy", "/Y", work_top, current_top] if platform.system() == "Windows" else ["cp", work_top, current_top]
                    all_cmds.append(cp_top_cmd)

            else:
                # 一次性删除全部添加剂
                self.add_log(f"删除全部添加剂: {resname}", "info")
                new_gro = f"{prefix}_new.gro"
                new_top = f"{prefix}_new.top"
                tpr_file = f"{prefix}.tpr"
                deffnm = prefix

                self.add_log(f"文件命名: prefix={prefix}, deffnm={deffnm}, current_gro={current_gro}, current_top={current_top}", "info")

                import shutil
                shutil.copy(_resolve(input_gro), os.path.join(wd, original_gro))
                shutil.copy(_resolve(top_file), os.path.join(wd, original_top))
                self.add_log(f"已备份原始文件: {original_gro}, {original_top}", "info")

                del_cmd = [
                    python_exe, delete_script,
                    "--additive", resname,
                    "--atoms-per-mol", str(atoms_per_mol),
                    "--input", input_gro,
                    "--output", new_gro,
                    "--topology", top_file,
                    "--topology-output", new_top,
                ]
                all_cmds.append(del_cmd)

                mv_gro_cmd = ["cmd", "/c", "move", "/Y", new_gro, work_gro] if platform.system() == "Windows" else ["mv", new_gro, work_gro]
                all_cmds.append(mv_gro_cmd)
                mv_top_cmd = ["cmd", "/c", "move", "/Y", new_top, work_top] if platform.system() == "Windows" else ["mv", new_top, work_top]
                all_cmds.append(mv_top_cmd)

                grompp_cmd = [
                    gmx, "grompp",
                    "-f", mdp_file,
                    "-c", work_gro,
                    "-p", work_top,
                    "-o", tpr_file,
                    "-maxwarn", "200"
                ]
                all_cmds.append(grompp_cmd)

                mdrun_cmd = [gmx, "mdrun", "-v", "-deffnm", deffnm] + self._get_mdrun_extra()
                all_cmds.append(mdrun_cmd)

                cp_gro_cmd = ["cmd", "/c", "copy", "/Y", f"{deffnm}.gro", current_gro] if platform.system() == "Windows" else ["cp", f"{deffnm}.gro", current_gro]
                all_cmds.append(cp_gro_cmd)
                cp_top_cmd = ["cmd", "/c", "copy", "/Y", work_top, current_top] if platform.system() == "Windows" else ["cp", work_top, current_top]
                all_cmds.append(cp_top_cmd)
                
                self.add_log(f"一次性删除模式命令列表 ({len(all_cmds)} 个):", "info")
                for i, c in enumerate(all_cmds):
                    self.add_log(f"  [{i+1}] {' '.join(c)}", "info")

            step_name = "溶剂/添加剂蒸发"
            self.add_log(f"共 {len(all_cmds)} 个命令待执行", "info")
            self.run_command(all_cmds, wd, step_name)
        except Exception as e:
            self.add_log(f"运行蒸发步骤时发生错误: {str(e)}", "error")

    def _reset_anneal_curve(self):
        """重置退火曲线为默认值"""
        self.anneal_table.setRowCount(7)
        default_times = ["0", "100", "300", "500", "700", "900", "1000"]
        default_temps = ["300", "373", "373", "373", "373", "300", "300"]
        for i in range(7):
            self.anneal_table.setItem(i, 0, QTableWidgetItem(default_times[i]))
            self.anneal_table.setItem(i, 1, QTableWidgetItem(default_temps[i]))
        self.add_log("退火曲线已重置为默认值", "info")

    def run_anneal_step(self):
        """第六阶段: 退火模拟 - 生成MDP + grompp + mdrun"""
        try:
            wd = self._get_work_dir()
            if not wd:
                return

            gmx = self.gmx_path
            if not gmx or not os.path.isfile(gmx):
                self.add_log(f"错误: GROMACS可执行文件不存在 - {gmx}", "error")
                return

            # 检查工作目录权限
            if not os.path.exists(wd):
                self.add_log(f"错误: 工作目录不存在 - {wd}", "error")
                return
            try:
                test_file = os.path.join(wd, "_test_write_permission.tmp")
                with open(test_file, "w") as f:
                    f.write("test")
                os.remove(test_file)
            except PermissionError:
                self.add_log(f"错误: 工作目录没有写入权限 - {wd}", "error")
                self.add_log("建议: 1) 以管理员身份运行程序 2) 更换工作目录为用户文件夹 3) 检查目标目录权限设置", "warning")
                return

            # 获取参数
            gro_file = self.anneal_gro_edit.text().strip()
            top_file = self.anneal_top_edit.text().strip()
            prefix = self.anneal_prefix.text().strip() or "anneal"
            mode_text = self.anneal_mode.currentText()
            annealing_mode = "single" if "single" in mode_text else "periodic"

            if not gro_file:
                self.add_log("错误: 请指定输入GRO文件", "error")
                return
            if not top_file:
                self.add_log("错误: 请指定拓扑TOP文件", "error")
                return

            # 检查文件是否存在
            gro_path = gro_file if os.path.isabs(gro_file) else os.path.join(wd, gro_file)
            top_path = top_file if os.path.isabs(top_file) else os.path.join(wd, top_file)
            if not os.path.isfile(gro_path):
                self.add_log(f"错误: GRO文件不存在 - {gro_path}", "error")
                return
            if not os.path.isfile(top_path):
                self.add_log(f"错误: TOP文件不存在 - {top_path}", "error")
                return

            # 从表格读取退火曲线
            times = []
            temps = []
            for row in range(self.anneal_table.rowCount()):
                t_item = self.anneal_table.item(row, 0)
                temp_item = self.anneal_table.item(row, 1)
                if t_item and temp_item:
                    t_val = t_item.text().strip()
                    temp_val = temp_item.text().strip()
                    if t_val and temp_val:
                        try:
                            float(t_val)
                            float(temp_val)
                            times.append(t_val)
                            temps.append(temp_val)
                        except ValueError:
                            self.add_log(f"错误: 第{row+1}行数据不是有效数字 (时间={t_val}, 温度={temp_val})", "error")
                            return

            if len(times) < 2:
                self.add_log("错误: 退火曲线至少需要2个时间-温度点对", "error")
                return

            if len(times) != len(temps):
                self.add_log("错误: 时间点数与温度点数不一致", "error")
                return

            # 检查时间是否递增
            for i in range(1, len(times)):
                if float(times[i]) <= float(times[i-1]):
                    self.add_log(f"错误: 时间点必须递增 (第{i}个点 {times[i]} <= {times[i-1]})", "error")
                    return

            npoints = len(times)
            time_str = " ".join(times)
            temp_str = " ".join(temps)

            # 计算总模拟时间(取最后一个时间点)
            total_time_ps = float(times[-1])
            nsteps = int(total_time_ps / 0.002)  # dt=0.002ps

            # 生成MDP文件
            mdp_file = os.path.join(wd, f"{prefix}.mdp")
            mdp_content = f"""; {prefix}.mdp - 退火模拟 (Simulated Annealing)
; 由 GROMACS GUI V3 自动生成

; Run parameters
integrator  = md
dt          = 0.002
nsteps      = {nsteps}    ; {total_time_ps}ps

; Output parameters
nstxout             = 1000
nstvout             = 1000
nstfout             = 1000
nstxout-compressed  = 1000
nstenergy           = 1000
nstlog              = 1000
nstcheckpoint       = 1000

; Bond parameters
constraint_algorithm    = lincs
constraints             = h-bonds
continuation            = yes
lincs_iter              = 1
lincs_order             = 4

; Neighbor searching
cutoff-scheme   = Verlet
nstlist         = 100
ns_type         = grid
rlist           = 1.5
pbc             = xyz

; Electrostatics
coulombtype     = PME
pme_order       = 4
fourierspacing  = 0.12
rcoulomb        = 1.5

; van der Waals
vdw-type        = Cut-off
rvdw            = 1.5
DispCorr        = EnerPres

; Temperature coupling
tcoupl          = V-rescale
tc-grps         = system
tau_t           = 0.5
ref_t           = {temps[0]}

; Simulated Annealing
annealing           = {annealing_mode}
annealing_npoints   = {npoints}
annealing_time      = {time_str}
annealing_temp      = {temp_str}

; Pressure coupling
Pcoupl          = Parrinello-Rahman
Pcoupltype      = isotropic
tau_p           = 1.0
compressibility = 4.5e-5
ref_p           = 1.0

; Velocity generation
gen_vel         = no
"""

            with open(mdp_file, 'w', encoding='utf-8') as f:
                f.write(mdp_content)

            self.add_log(f"退火MDP文件已生成: {mdp_file}", "success")
            self.add_log(f"退火模式: {annealing_mode}, 点数: {npoints}", "info")
            self.add_log(f"时间点: {time_str}", "info")
            self.add_log(f"温度点: {temp_str}", "info")
            self.add_log(f"模拟时长: {total_time_ps}ps ({nsteps} steps)", "info")

            # 构建命令序列: grompp -> mdrun
            tpr_file = os.path.join(wd, f"{prefix}.tpr")

            # grompp 命令
            grompp_cmd = [
                gmx, "grompp",
                "-f", mdp_file,
                "-c", gro_path,
                "-p", top_path,
                "-o", tpr_file,
                "-maxwarn", "200"
            ]

            # mdrun 命令
            deffnm = os.path.join(wd, prefix)
            mdrun_cmd = [gmx, "mdrun", "-v", "-deffnm", deffnm] + self._get_mdrun_extra()

            step_name = "退火模拟"
            self.run_command([grompp_cmd, mdrun_cmd], wd, step_name)

        except Exception as e:
            self.add_log(f"运行退火步骤时发生错误: {str(e)}", "error")

    def run_all_md(self):
        try:
            wd = self._get_work_dir()
            if not wd:
                return

            gmx = self.gmx_path
            if not gmx or not os.path.isfile(gmx):
                self.add_log(f"错误: GROMACS可执行文件不存在 - {gmx}", "error")
                return
            ff = self.md_ff.currentText()
            water = self.md_water.currentText()
            ion_conc = self.md_ion_conc.value()
            pdb = self.md_pdb.text().strip() or "protein.pdb"
            top = "topol.top"

            extra_mdrun = self._get_mdrun_extra()
            extra_em = self._get_mdrun_extra(is_em=True)

            commands = []
            first_struct = "protein.gro"

            if self.use_existing_top.isChecked():
                first_struct = self.se_gro_edit.text().strip() or "input.gro"
                top = self.se_top_edit.text().strip() or "topol.top"
                struct_path = os.path.join(wd, first_struct)
                top_path = os.path.join(wd, top)
                if not os.path.isfile(struct_path):
                    self.add_log(f"错误: 结构文件不存在 - {struct_path}", "error")
                    return
                if not os.path.isfile(top_path):
                    self.add_log(f"错误: TOP文件不存在 - {top_path}", "error")
                    return
                self.add_log(f"使用已有拓扑: STRUCT={first_struct}, TOP={top}", "info")
            else:
                commands.append([gmx, "pdb2gmx", "-f", pdb, "-o", first_struct, "-p", top,
                                 "-i", "posre.itp", "-ff", ff, "-water", water, "-ignh"])

            current_gro = first_struct
            if not self.skip_editconf.isChecked():
                box_params = self._get_box_params()
                commands.append([gmx, "editconf", "-f", first_struct, "-o", "protein_box.gro"] + box_params)
                current_gro = "protein_box.gro"
            if not self.skip_solvate.isChecked():
                commands.append([gmx, "solvate", "-cp", current_gro, "-o", "protein_solv.gro", "-p", top])
                current_gro = "protein_solv.gro"

            if not self.skip_genion.isChecked():
                commands.append([gmx, "grompp", "-f", "ions.mdp", "-c", current_gro,
                                 "-p", top, "-o", "ions.tpr", "-maxwarn", "2"])
                commands.append([gmx, "genion", "-s", "ions.tpr", "-o", "protein_ions.gro",
                                 "-p", top, "-pname", "NA", "-nname", "CL", "-neutral",
                                 "-conc", f"{ion_conc:.3f}", "-quiet"])
                current_gro = "protein_ions.gro"

            commands.append([gmx, "grompp", "-f", "em.mdp", "-c", current_gro,
                             "-p", top, "-o", "em.tpr", "-maxwarn", "2"])
            commands.append([gmx, "mdrun", "-v", "-deffnm", "em"] + extra_em)
            commands.append([gmx, "grompp", "-f", "nvt.mdp", "-c", "em.gro", "-r", "em.gro",
                             "-p", top, "-o", "nvt.tpr", "-maxwarn", "2"])
            commands.append([gmx, "mdrun", "-deffnm", "nvt"] + extra_mdrun)
            commands.append([gmx, "grompp", "-f", "npt.mdp", "-c", "nvt.gro", "-r", "nvt.gro",
                             "-p", top, "-o", "npt.tpr", "-maxwarn", "2"])
            commands.append([gmx, "mdrun", "-deffnm", "npt"] + extra_mdrun)
            commands.append([gmx, "grompp", "-f", "md.mdp", "-c", "npt.gro", "-r", "npt.gro",
                             "-p", top, "-o", "md.tpr", "-maxwarn", "2"])
            commands.append([gmx, "mdrun", "-deffnm", "md"] + extra_mdrun)

            self.run_command(commands, wd, step_name="完整MD流程")
        except Exception as e:
            self.add_log(f"运行完整MD流程时发生错误: {str(e)}", "error")

    def _get_full_mdp_template(self, mdp_type):
        dt = self.md_dt.value()
        nsteps = self.md_nsteps.value()
        temp = self.md_temp.value()
        press = self.md_pressure.value()

        templates = {
            "ions": f"""; ions.mdp - 离子位置限制能量最小化
integrator    = steep
nsteps        = 1000
emtol         = 1000.0
emstep        = 0.01

cutoff-scheme = Verlet
nstlist       = 10
ns-type       = grid
rlist         = 1.0
pbc           = xyz

coulombtype   = PME
rcoulomb      = 1.0
pme_order     = 4
fourierspacing = 0.16

vdw-type      = cut-off
rvdw          = 1.0
DispCorr      = EnerPres

constraints   = none
""",
            "em": f"""; em.mdp - 能量最小化
integrator    = steep
emtol         = 1000.0
emstep        = 0.01
nsteps        = 50000

cutoff-scheme = Verlet
nstlist       = 10
ns-type       = grid
rlist         = 1.0
pbc           = xyz

coulombtype   = PME
rcoulomb      = 1.0
pme_order     = 4
fourierspacing = 0.16

vdw-type      = cut-off
rvdw          = 1.0
DispCorr      = EnerPres

nstenergy     = 1000
nstlog        = 1000
constraints   = none
""",
            "nvt": f"""; nvt.mdp - 恒温恒容平衡
define        = -DPOSRES
integrator    = md
dt            = {dt}
nsteps        = {int(50000/dt*1000)}
tinit         = 0.0

cutoff-scheme = Verlet
nstlist       = 10
ns-type       = grid
rlist         = 1.0
pbc           = xyz

coulombtype   = PME
rcoulomb      = 1.0
pme_order     = 4
fourierspacing = 0.16

vdw-type      = cut-off
rvdw          = 1.0
DispCorr      = EnerPres

tcoupl        = V-rescale
tc-grps       = System
tau_t         = 0.1
ref_t         = {temp}

gen_vel       = yes
gen_temp      = {temp}
gen_seed      = -1

constraints   = h-bonds
constraint_algorithm = lincs
lincs_iter    = 1
lincs_order   = 4
continuation  = no

nstxout       = 0
nstvout       = 0
nstfout       = 0
nstenergy     = 1000
nstlog        = 1000
nstcheckpoint = 10000
nstxtcout     = 5000
xtc-precision = 1000
""",
            "npt": f"""; npt.mdp - 恒温恒压平衡
define        = -DPOSRES
integrator    = md
dt            = {dt}
nsteps        = {int(100000/dt*1000)}
tinit         = 0.0

cutoff-scheme = Verlet
nstlist       = 10
ns-type       = grid
rlist         = 1.0
pbc           = xyz

coulombtype   = PME
rcoulomb      = 1.0
pme_order     = 4
fourierspacing = 0.16

vdw-type      = cut-off
rvdw          = 1.0
DispCorr      = EnerPres

tcoupl        = V-rescale
tc-grps       = System
tau_t         = 0.1
ref_t         = {temp}

pcoupl        = C-rescale
pcoupltype    = isotropic
tau_p         = 2.0
ref_p         = {press}
compressibility = 4.5e-5
refcoord_scaling = com

gen_vel       = no
constraints   = h-bonds
constraint_algorithm = lincs
lincs_iter    = 1
lincs_order   = 4
continuation  = yes

nstxout       = 0
nstvout       = 0
nstfout       = 0
nstenergy     = 1000
nstlog        = 1000
nstcheckpoint = 10000
nstxtcout     = 5000
xtc-precision = 1000
""",
            "md": f"""; md.mdp - 生产模拟
integrator    = md
dt            = {dt}
nsteps        = {nsteps}
tinit         = 0.0

cutoff-scheme = Verlet
nstlist       = 10
ns-type       = grid
rlist         = 1.0
pbc           = xyz

coulombtype   = PME
rcoulomb      = 1.0
pme_order     = 4
fourierspacing = 0.16

vdw-type      = cut-off
rvdw          = 1.0
DispCorr      = EnerPres

tcoupl        = V-rescale
tc-grps       = System
tau_t         = 0.1
ref_t         = {temp}

pcoupl        = Parrinello-Rahman
pcoupltype    = isotropic
tau_p         = 2.0
ref_p         = {press}
compressibility = 4.5e-5
refcoord_scaling = com

gen_vel       = no
constraints   = h-bonds
constraint_algorithm = lincs
lincs_iter    = 1
lincs_order   = 4
continuation  = yes

nstxout       = 0
nstvout       = 0
nstfout       = 0
nstenergy     = 5000
nstlog        = 5000
nstcheckpoint = 50000
nstxtcout     = 10000
xtc-precision = 1000

energygrps    = System
""",
            "sa": f"""; sa.mdp - SA溶剂蒸发
integrator    = md
dt            = 0.002
nsteps        = 50000
tinit         = 0.0

cutoff-scheme = Verlet
nstlist       = 100
ns-type       = grid
rlist         = 1.5
pbc           = xyz

coulombtype   = PME
rcoulomb      = 1.5
pme_order     = 4
fourierspacing = 0.12
ewald-rtol    = 1e-5

vdw-type      = cut-off
rvdw          = 1.5
DispCorr      = EnerPres

tcoupl        = V-rescale
tc-grps       = System
tau_t         = 0.5
ref_t         = 300

pcoupl        = Parrinello-Rahman
pcoupltype    = isotropic
tau_p         = 1.0
ref_p         = 1.0
compressibility = 4.5e-5

gen_vel       = no
constraints   = h-bonds
constraint_algorithm = lincs
lincs_iter    = 1
lincs_order   = 4
continuation  = yes

nstxout       = 0
nstvout       = 0
nstfout       = 0
nstenergy     = 1000
nstlog        = 1000
nstcheckpoint = 10000
nstxtcout     = 1000
xtc-precision = 1000

energygrps    = System
""",
            "annealing": f"""; annealing.mdp - 模拟退火
integrator    = md
dt            = 0.002
nsteps        = 500000
tinit         = 0.0

cutoff-scheme = Verlet
nstlist       = 100
ns-type       = grid
rlist         = 1.5
pbc           = xyz

coulombtype   = PME
rcoulomb      = 1.5
pme_order     = 4
fourierspacing = 0.12
ewald-rtol    = 1e-5

vdw-type      = cut-off
rvdw          = 1.5
DispCorr      = EnerPres

tcoupl        = V-rescale
tc-grps       = System
tau_t         = 0.5
ref_t         = 300

annealing     = single
annealing_npoints = 7
annealing_time = 0 100 300 500 700 900 1000
annealing_temp = 300 373 373 373 373 300 300

pcoupl        = Parrinello-Rahman
pcoupltype    = isotropic
tau_p         = 1.0
ref_p         = 1.0
compressibility = 4.5e-5

gen_vel       = no
constraints   = h-bonds
constraint_algorithm = lincs
lincs_iter    = 1
lincs_order   = 4
continuation  = yes

nstxout       = 0
nstvout       = 0
nstfout       = 0
nstenergy     = 10000
nstlog        = 10000
nstcheckpoint = 10000
nstxtcout     = 10000
xtc-precision = 1000

energygrps    = System
""",
        }
        return templates.get(mdp_type, "")

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
                "script_type": self.script_type.currentText() if hasattr(self, 'script_type') else "PowerShell (.ps1)"
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
                if "custom_out_check" in step_info:
                    step_data["custom_out_check"] = step_info["custom_out_check"].isChecked()
                if "custom_out_edit" in step_info and step_info["custom_out_edit"]:
                    step_data["custom_out_edit"] = step_info["custom_out_edit"].text().strip()
                if "restart_check" in step_info:
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
                    if "custom_out_check" in step_info and "custom_out_check" in step_data:
                        step_info["custom_out_check"].setChecked(step_data["custom_out_check"])
                    if "custom_out_edit" in step_info and step_info["custom_out_edit"] and "custom_out_edit" in step_data:
                        step_info["custom_out_edit"].setText(step_data["custom_out_edit"])
                    if "restart_check" in step_info and "restart_check" in step_data:
                        step_info["restart_check"].setChecked(step_data["restart_check"])

            if hasattr(self, 'script_type') and "script_type" in config:
                self.script_type.setCurrentText(config["script_type"])

            self.add_log(f"配置已从 {filepath} 加载", "success")
        except Exception as e:
            self.add_log(f"加载配置失败: {str(e)}", "error")
            QMessageBox.critical(self, "错误", f"加载配置失败: {str(e)}")

    def generate_mdp_template(self, mdp_type):
        wd = self._get_work_dir()
        if not wd:
            return

        dt = self.md_dt.value()
        nsteps = self.md_nsteps.value()
        temp = self.md_temp.value()
        press = self.md_pressure.value()

        templates = {
            "ions": """; ions.mdp
integrator  = steep
nsteps       = 1000
coulombtype  = PME
rcoulomb     = 1.0
rvdw         = 1.0
pbc          = xyz
""",
            "em": f"""; em.mdp
integrator  = steep
emtol       = 1000.0
emstep      = 0.01
nsteps      = 50000
nstlist     = 1
coulombtype = PME
rcoulomb    = 1.0
rvdw        = 1.0
pbc         = xyz
""",
            "nvt": f"""; nvt.mdp
define      = -DPOSRES
integrator  = md
dt          = {dt}
nsteps      = {int(1000/dt*1000)}
coulombtype = PME
rcoulomb    = 1.0
rvdw        = 1.0
pbc         = xyz
constraints = h-bonds
tcoupl      = V-rescale
tc-grps     = Protein Non-Protein
tau_t       = 0.1 0.1
ref_t       = {temp} {temp}
nstxout     = 5000
nstvout     = 5000
nstenergy   = 5000
nstlog      = 5000
continuation = no
""",
            "npt": f"""; npt.mdp
define      = -DPOSRES
integrator  = md
dt          = {dt}
nsteps      = {int(1000/dt*1000)}
coulombtype = PME
rcoulomb    = 1.0
rvdw        = 1.0
pbc         = xyz
constraints = h-bonds
tcoupl      = V-rescale
tc-grps     = Protein Non-Protein
tau_t       = 0.1 0.1
ref_t       = {temp} {temp}
pcoupl      = Parrinello-Rahman
pcoupltype  = isotropic
tau_p       = 2.0
ref_p       = {press}
compressibility = 4.5e-5
continuation = yes
nstxout     = 5000
nstvout     = 5000
nstenergy   = 5000
nstlog      = 5000
""",
            "md": f"""; md.mdp
integrator  = md
dt          = {dt}
nsteps      = {nsteps}
coulombtype = PME
rcoulomb    = 1.0
rvdw        = 1.0
pbc         = xyz
constraints = h-bonds
tcoupl      = V-rescale
tc-grps     = Protein Non-Protein
tau_t       = 0.1 0.1
ref_t       = {temp} {temp}
pcoupl      = Parrinello-Rahman
pcoupltype  = isotropic
tau_p       = 2.0
ref_p       = {press}
compressibility = 4.5e-5
continuation = yes
nstxout     = 5000
nstvout     = 5000
nstenergy   = 5000
nstlog      = 5000
""",
        }

        content = templates.get(mdp_type, "")
        fname = f"{mdp_type}.mdp"
        fpath = os.path.join(wd, fname)
        try:
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(content)
            self.add_log(f"已生成 MDP 模板: {fpath}", "success")
        except Exception as e:
            self.add_log(f"生成 MDP 模板失败: {e}", "error")

    # -------------------------------------------------------------------------
    # Part 3: 高级模拟执行
    # -------------------------------------------------------------------------
    def generate_umbrella_mdp(self):
        wd = self._get_work_dir()
        if not wd:
            return

        coord = self.umb_pull_coord.currentText()
        group1 = self.umb_pull_group1.text().strip()
        group2 = self.umb_pull_group2.text().strip()
        force = self.umb_pull_force.value()
        start = self.umb_pull_start.value()
        end = self.umb_pull_end.value()
        nwindows = self.umb_pull_nwindows.value()

        delta = (end - start) / (nwindows - 1) if nwindows > 1 else 0

        for i in range(nwindows):
            pos = start + i * delta
            content = f"""; umbrella_{i}.mdp
integrator  = md
dt          = 0.002
nsteps      = 500000
coulombtype = PME
rcoulomb    = 1.0
rvdw        = 1.0
pbc         = xyz
constraints = h-bonds
tcoupl      = V-rescale
tc-grps     = Protein Non-Protein
tau_t       = 0.1 0.1
ref_t       = 300 300
pcoupl      = Parrinello-Rahman
pcoupltype  = isotropic
tau_p       = 2.0
ref_p       = 1.0
compressibility = 4.5e-5
continuation = yes

pull = yes
pull_ngroups = 1
pull_ncoords = 1
pull_group0 = {group1}
pull_group1 = {group2}
pull_coord1_type = {coord}
pull_coord1_geometry = distance
pull_coord1_groups = 0 1
pull_coord1_k = {force}
pull_coord1_init = {pos}
pull_coord1_rate = 0
pull_coord1_target = {pos}
pull_coord1_print_com = yes

nstxout     = 5000
nstvout     = 5000
nstenergy   = 5000
nstlog      = 5000
nstxout-compressed = 5000
"""
            fname = f"umbrella_{i}.mdp"
            fpath = os.path.join(wd, fname)
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(content)

        self.add_log(f"已生成 {nwindows} 个伞形采样 MDP 文件", "success")

    def run_wham(self):
        wd = self._get_work_dir()
        if not wd:
            return

        gmx = self.gmx_path
        files = self.wham_files.text().strip()
        temp = self.wham_temp.value()
        out = self.wham_out.text().strip() or "profile.xvg"

        cmd = [gmx, "wham", "-it", files, "-o", out, "-temp", str(temp), "-b", "0", "-e", "0"]
        self.run_command([cmd], wd, step_name="WHAM 自由能计算")

    def generate_plumed_meta(self):
        wd = self._get_work_dir()
        if not wd:
            return

        biasfactor = self.meta_biasfactor.value()
        height = self.meta_height.value()
        sigma = self.meta_sigma.value()
        fname = self.meta_plumed.text().strip() or "plumed.dat"

        content = f"""# Metadynamics with PLUMED
d1: DISTANCE ATOMS=1,100

METAD ARG=d1 SIGMA={sigma} HEIGHT={height} BIASFACTOR={biasfactor} TEMP=300
PRINT ARG=d1 FILE=COLVAR STRIDE=100
"""
        fpath = os.path.join(wd, fname)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(content)
        self.add_log(f"已生成 PLUMED 输入文件: {fpath}", "success")

    def run_metadynamics(self):
        wd = self._get_work_dir()
        if not wd:
            return

        gmx = self.gmx_path
        tpr = self.meta_tpr.text().strip() or "md.tpr"

        extra = self._get_mdrun_extra()
        cmd = [gmx, "mdrun", "-deffnm", "md_meta", "-plumed", "plumed.dat"] + extra
        self.run_command([cmd], wd, step_name="元动力学模拟")

    def generate_plumed_abf(self):
        wd = self._get_work_dir()
        if not wd:
            return

        min_val = self.abf_min.value()
        max_val = self.abf_max.value()
        nbins = self.abf_nbins.value()
        fname = self.abf_plumed.text().strip() or "plumed_abf.dat"

        content = f"""# ABF with PLUMED
d1: DISTANCE ATOMS=1,100

ABF ARG=d1 MIN={min_val} MAX={max_val} NBINS={nbins}
PRINT ARG=d1 FILE=COLVAR STRIDE=100
"""
        fpath = os.path.join(wd, fname)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(content)
        self.add_log(f"已生成 ABF PLUMED 文件: {fpath}", "success")

    # -------------------------------------------------------------------------
    # Part 5: 分析执行
    # -------------------------------------------------------------------------
    def run_analysis(self, key):
        wd = self._get_work_dir()
        if not wd:
            return

        gmx = self.gmx_path
        xtc = self.ana_input_xtc.text().strip() or "md.xtc"
        tpr = self.ana_input_tpr.text().strip() or "md.tpr"
        gro = self.ana_input_gro.text().strip() or "md.gro"
        edr = self.ana_input_edr.text().strip() or "md.edr"
        ndx = self.ana_index.text().strip()
        b = self.ana_b.value()
        e = self.ana_e.value()
        dt_val = self.ana_dt.value()

        w = self.analysis_widgets[key]
        out = w["out"].text().strip()
        sel = w["sel"].text().strip()
        ref = w["ref"].text().strip()

        # 修复：stdin_in用于为需要交互式组选择的命令提供输入
        # 例如: gmx rms需要选择拟合组和计算组，gmx msd需要选择分析组
        # 不需要stdin的命令保持 None，让Popen使用默认stdin
        stdin_in = None

        def add_time_args(cmd):
            if b > 0:
                cmd += ["-b", str(b)]
            if e > 0:
                cmd += ["-e", str(e)]
            if dt_val > 0:
                cmd += ["-dt", str(dt_val)]
            if ndx and os.path.exists(os.path.join(wd, ndx)):
                cmd += ["-n", ndx]
            return cmd

        cmd = [gmx]
        step_name = ""

        if key == "energy":
            out = out or "energy.xvg"
            step_name = "能量分析"
            # 修复：gmx energy 需要交互式输入能量项
            # sel字段为空时使用默认的 Potential
            # 支持多个能量项（空格分隔），以"0"结束选择
            energy_terms = sel.strip() if sel.strip() else "Potential"
            term_list = [t.strip() for t in energy_terms.split() if t.strip()]
            stdin_in = "\n".join(term_list) + "\n0\n"
            cmd = add_time_args([gmx, "energy", "-f", edr, "-o", out])
            self.add_log(f"提取能量项: {' '.join(term_list)}", "info")

        elif key == "rms":
            out = out or "rmsd.xvg"
            step_name = "RMSD 分析"
            ref_struct = ref or tpr
            cmd_base = [gmx, "rms", "-s", ref_struct, "-f", xtc, "-o", out, "-tu", "ns"]
            # 增强：支持拟合组选择（通过sel输入 -fit 组名）
            if sel and sel.startswith("-fit "):
                fit_group = sel.replace("-fit ", "").strip()
                cmd_base += ["-fit", "rot+trans"]
                # 拟合组需要索引文件
                if ndx:
                    cmd_base += ["-n", ndx]
            cmd = add_time_args(cmd_base)
            # 修复：gmx rms 交互式选择拟合组和计算组
            # 输入两次"0"表示对所有原子进行拟合和计算
            stdin_in = "0\n0\n"

        elif key == "rmsf":
            out = out or "rmsf.xvg"
            step_name = "RMSF 分析"
            cmd_base = [gmx, "rmsf", "-s", tpr, "-f", xtc, "-o", out, "-res"]
            # 增强：支持原子组选择
            if sel:
                # 如果sel是数字，作为组编号；否则作为选择表达式
                cmd_base += ["-sel", sel]
            cmd = add_time_args(cmd_base)
            # 修复：gmx rmsf 交互式选择组（留空使用所有原子）
            stdin_in = "0\n"

        elif key == "gyrate":
            out = out or "gyrate.xvg"
            step_name = "回旋半径"
            cmd_base = [gmx, "gyrate", "-s", tpr, "-f", xtc, "-o", out]
            # 增强：支持原子组选择
            if sel:
                cmd_base += ["-sel", sel]
            cmd = add_time_args(cmd_base)
            # 修复：gmx gyrate 交互式选择组
            stdin_in = "0\n"

        elif key == "hbond":
            out = out or "hbond.xvg"
            step_name = "氢键分析"
            cmd = add_time_args([gmx, "hbond", "-s", tpr, "-f", xtc, "-num", out])
            # 修复：gmx hbond 交互式选择供体和受体组
            stdin_in = "1\n1\n"

        elif key == "rdf":
            out = out or "rdf.xvg"
            step_name = "径向分布函数"
            cmd_base = [gmx, "rdf", "-s", tpr, "-f", xtc, "-o", out]
            # 增强：支持参考组、选择组、计算类型
            if sel:
                # 解析选择参数，格式如: -ref "group Protein" -sel "group Water" -seltype mol_com
                ref_group = None
                sel_group = None
                seltype_val = None
                bin_val = None
                for part in sel.split():
                    if part.startswith("-ref=") or part.startswith("-ref"):
                        ref_group = part.split("=", 1)[1] if "=" in part else None
                    elif part.startswith("-sel=") or part.startswith("-sel"):
                        sel_group = part.split("=", 1)[1] if "=" in part else None
                    elif part.startswith("-seltype=") or part.startswith("-seltype"):
                        seltype_val = part.split("=", 1)[1] if "=" in part else None
                    elif part.startswith("-bin=") or part.startswith("-bin"):
                        bin_val = part.split("=", 1)[1] if "=" in part else None
                # 简化用法：如果sel不是参数格式，直接当作选择组
                if not ref_group and not sel_group and not sel.startswith("-"):
                    sel_group = sel
                if ref_group:
                    cmd_base += ["-ref", ref_group]
                if sel_group:
                    cmd_base += ["-sel", sel_group]
                if seltype_val:
                    cmd_base += ["-seltype", seltype_val]
                if bin_val:
                    cmd_base += ["-bin", bin_val]
            # 如果用户设置了参考结构ref，用作ref组
            if ref and not any(x in sel for x in ["-ref", "-sel"]):
                cmd_base += ["-ref", ref]
            cmd = add_time_args(cmd_base)
            # 修复：gmx rdf 交互式选择参考组和选择组
            # 不带参数时需要选择两组
            stdin_in = "1\n1\n"

        elif key == "sasa":
            out = out or "sasa.xvg"
            step_name = "溶剂可及表面积"
            cmd = add_time_args([gmx, "sasa", "-s", tpr, "-f", xtc, "-o", out])
            # 修复：gmx sasa 交互式选择组
            stdin_in = "0\n"

        elif key == "density":
            out = out or "density.xvg"
            step_name = "密度分析"
            cmd_base = [gmx, "density", "-s", tpr, "-f", xtc, "-o", out]
            # 增强：支持组选择和方向选择
            if sel:
                # 解析参数：-d Z (方向) 或 -sl 数量 (切片数)
                direction = None
                slices = None
                for part in sel.split():
                    if part.startswith("-d=") or part.startswith("-d"):
                        direction = part.split("=", 1)[1] if "=" in part else None
                    elif part.startswith("-sl=") or part.startswith("-sl"):
                        slices = part.split("=", 1)[1] if "=" in part else None
                if direction:
                    cmd_base += ["-d", direction]
                if slices:
                    cmd_base += ["-sl", slices]
            cmd = add_time_args(cmd_base)
            # 修复：gmx density 交互式选择组
            stdin_in = "0\n"

        elif key == "do_dssp":
            out = out or "dssp.xpm"
            step_name = "二级结构分析"
            cmd = add_time_args([gmx, "do_dssp", "-s", tpr, "-f", xtc, "-xpm", out, "-sc", "scount.xvg"])
            # 修复：gmx do_dssp 交互式选择组
            stdin_in = "0\n"

        elif key == "msd":
            out = out or "msd.xvg"
            step_name = "均方位移"
            cmd_base = [gmx, "msd", "-s", tpr, "-f", xtc, "-o", out, "-tu", "ns"]
            # 增强：支持分子类型选择（通过sel输入组名）
            if sel:
                cmd_base += ["-sel", sel]
            # 增强：支持计算扩散系数（-molecules 按分子计算）
            if ref and "molecules" in ref.lower():
                cmd_base += ["-molecules"]
            # 修复：-trestart 必须 >= 轨迹时间步，避免 "Increase -trestart" 错误
            # 默认轨迹 dt=0.002 ns (2 ps)，设置 trestart=10 ns
            cmd_base += ["-trestart", "10"]
            cmd = add_time_args(cmd_base)
            # 修复：gmx msd 交互式选择组
            stdin_in = "0\n"

        elif key == "distance":
            out = out or "distance.xvg"
            step_name = "距离分析"
            # 修复：GROMACS 2026.3 移除了 -o 参数，改用 -oav (平均距离随时间)
            cmd = add_time_args([gmx, "distance", "-s", tpr, "-f", xtc, "-oav", out])
            # 修复：gmx distance 交互式选择组（用 -select 或通过位置对）
            stdin_in = "0\n0\n"

        elif key == "angle":
            out = out or "angle.xvg"
            step_name = "角度分析"
            # 修复：GROMACS 2026.3 移除了 -o 参数，改用 -od (分布) 或 -ov (平均)
            cmd = add_time_args([gmx, "angle", "-s", tpr, "-f", xtc, "-ov", out])
            # 修复：gmx angle 交互式选择3个原子
            stdin_in = "0\n0\n0\n"

        elif key == "covar":
            out = out or "covar.xvg"
            step_name = "协方差矩阵"
            cmd = add_time_args([gmx, "covar", "-s", tpr, "-f", xtc, "-o", out])
            # 修复：gmx covar 交互式选择组
            stdin_in = "0\n"

        elif key == "eigenvalue":
            out = out or "eigenval.xvg"
            step_name = "特征值分解"
            cmd = add_time_args([gmx, "eigenvalue", "-f", "covar.xvg", "-o", out])
            # eigenvalue 不需要交互式输入

        elif key == "principal":
            out = out or "pc.xvg"
            step_name = "主成分分析"
            cmd = add_time_args([gmx, "principal", "-s", tpr, "-f", xtc, "-o", out])
            # 修复：gmx principal 交互式选择组
            stdin_in = "0\n"

        elif key == "trajectory":
            out = out or "proj.xvg"
            step_name = "轨迹投影"
            cmd = add_time_args([gmx, "trajectory", "-s", tpr, "-f", xtc, "-o", out])
            # trajectory 不需要交互式输入

        elif key == "cluster":
            out = out or "cluster.xpm"
            step_name = "聚类分析"
            cmd_base = [gmx, "cluster", "-s", tpr, "-f", xtc, "-o", out]
            # 增强：支持聚类方法和距离阈值
            if sel:
                # 解析参数：-method linkage -cutoff 0.2
                method = None
                cutoff = None
                for part in sel.split():
                    if part.startswith("-method=") or part.startswith("-method"):
                        method = part.split("=", 1)[1] if "=" in part else None
                    elif part.startswith("-cutoff=") or part.startswith("-cutoff"):
                        cutoff = part.split("=", 1)[1] if "=" in part else None
                if method:
                    cmd_base += ["-method", method]
                if cutoff:
                    cmd_base += ["-cutoff", cutoff]
            cmd = add_time_args(cmd_base)
            # 修复：gmx cluster 交互式选择组
            stdin_in = "0\n"

        elif key == "pairdist":
            out = out or "pairdist.xvg"
            step_name = "配对距离分布"
            cmd_base = [gmx, "pairdist", "-s", tpr, "-f", xtc, "-o", out]
            # 增强：支持参考组、选择组、计算类型
            if sel:
                ref_group = None
                sel_group = None
                pd_type = None
                for part in sel.split():
                    if part.startswith("-ref=") or part.startswith("-ref"):
                        ref_group = part.split("=", 1)[1] if "=" in part else None
                    elif part.startswith("-sel=") or part.startswith("-sel"):
                        sel_group = part.split("=", 1)[1] if "=" in part else None
                    elif part.startswith("-type=") or part.startswith("-type"):
                        pd_type = part.split("=", 1)[1] if "=" in part else None
                if not ref_group and not sel_group and not sel.startswith("-"):
                    sel_group = sel
                if ref_group:
                    cmd_base += ["-ref", ref_group]
                if sel_group:
                    cmd_base += ["-sel", sel_group]
                if pd_type:
                    cmd_base += ["-type", pd_type]
            cmd = add_time_args(cmd_base)
            # 修复：gmx pairdist 交互式选择参考组和选择组
            stdin_in = "1\n1\n"

        elif key == "saltbr":
            out = out or "saltbr.xvg"
            step_name = "盐桥分析"
            cmd = add_time_args([gmx, "saltbr", "-s", tpr, "-f", xtc, "-o", out])
            # saltbr 不需要交互式输入

        else:
            self.add_log(f"未知分析类型: {key}", "error")
            return

        self.run_command([cmd], wd, step_name, stdin_input=stdin_in)

    # -------------------------------------------------------------------------
    # Part 4: 轨迹预处理流水线方法 (新增)
    # -------------------------------------------------------------------------

    def _run_preprocessing_pipeline(self):
        """一键执行轨迹预处理五步法"""
        wd = self._get_work_dir()
        if not wd:
            return

        gmx = self.gmx_path
        xtc = self.traj_input.text().strip() or "md.xtc"
        tpr = self.traj_tpr.text().strip() or "md.tpr"
        ndx = self.traj_index.text().strip()

        pbc_text = self.prep_pbc.currentText()
        pbc_mode = pbc_text.split()[0]  # mol/res/atom/nojump/whole/cluster
        center_group = self.prep_center.text().strip()
        fit_text = self.prep_fit.currentText()
        fit_mode = fit_text.split()[0]  # rot+trans/trans/rot/none
        fit_ref = self.prep_fit_ref.text().strip()
        b = self.prep_b.value()
        e = self.prep_e.value()
        dt_val = self.prep_dt.value()
        output = self.prep_output.text().strip() or "md_clean.xtc"

        # 检查输入文件
        if not os.path.exists(os.path.join(wd, xtc)):
            QMessageBox.warning(self, "警告", f"轨迹文件不存在: {xtc}")
            return
        if not os.path.exists(os.path.join(wd, tpr)):
            QMessageBox.warning(self, "警告", f"TPR文件不存在: {tpr}")
            return

        commands = []

        # Step 1: PBC修复
        step1_out = "_prep_step1.xtc"
        cmd1 = [gmx, "trjconv", "-f", xtc, "-s", tpr, "-o", step1_out, "-pbc", pbc_mode]
        if pbc_mode in ["mol", "res", "cluster"] and center_group:
            cmd1 += ["-center"]
        if ndx and os.path.exists(os.path.join(wd, ndx)):
            cmd1 += ["-n", ndx]
        # PBC修复需要选择输出组，使用echo管道
        commands.append((cmd1, "Step 1: PBC修复", f"echo 0 0 | ", step1_out))

        # Step 2 & 3: 拟合（同时去除平动/转动）
        current_input = step1_out
        if fit_mode != "none":
            step2_out = "_prep_step2.xtc"
            cmd2 = [gmx, "trjconv", "-f", current_input, "-s", tpr, "-o", step2_out, "-fit", fit_mode]
            if ndx and os.path.exists(os.path.join(wd, ndx)):
                cmd2 += ["-n", ndx]
            commands.append((cmd2, f"Step 2/3: {fit_mode}拟合", f"echo {fit_ref} 0 | ", step2_out))
            current_input = step2_out

        # Step 4: 截取平衡段 & Step 5: 降采样
        final_cmd = [gmx, "trjconv", "-f", current_input, "-s", tpr, "-o", output]
        if b > 0:
            final_cmd += ["-b", str(b)]
        if e > 0:
            final_cmd += ["-e", str(e)]
        if dt_val > 0:
            final_cmd += ["-dt", str(dt_val)]
        if ndx and os.path.exists(os.path.join(wd, ndx)):
            final_cmd += ["-n", ndx]
        commands.append((final_cmd, f"Step 4/5: 截取+降采样 → {output}", "echo 0 | ", output))

        # 执行流水线
        self.add_log(f"开始轨迹预处理流水线: {xtc} → {output}", "info")
        for i, (cmd, step_name, echo_prefix, out_file) in enumerate(commands, 1):
            self.add_log(f"[{i}/{len(commands)}] {step_name}", "info")
            # 将echo前缀加入命令，使用shell执行管道
            if echo_prefix:
                cmd_str = echo_prefix + " ".join(cmd)
                self.add_log(f"执行: {cmd_str}", "cmd")
                import subprocess
                try:
                    result = subprocess.run(
                        cmd_str, shell=True, cwd=wd,
                        capture_output=True, text=True, timeout=3600
                    )
                    if result.returncode == 0:
                        self.add_log(f"  ✓ {step_name} 完成", "success")
                    else:
                        err = result.stderr[:500] if result.stderr else "未知错误"
                        self.add_log(f"  ✗ {step_name} 失败: {err}", "error")
                        return
                except Exception as e:
                    self.add_log(f"  ✗ {step_name} 异常: {str(e)}", "error")
                    return
            else:
                self.run_command([cmd], wd, step_name)

            # 清理中间文件
            if out_file.startswith("_prep_") and os.path.exists(os.path.join(wd, out_file)):
                try:
                    os.remove(os.path.join(wd, out_file))
                except:
                    pass

        self.add_log(f"预处理完成: {output}", "success")

    # -------------------------------------------------------------------------
    # Part 4: 轨迹处理工具执行
    # -------------------------------------------------------------------------
    def run_trajectory_tool(self, key):
        wd = self._get_work_dir()
        if not wd:
            return

        gmx = self.gmx_path
        inp = self.traj_input.text().strip() or "md.xtc"
        tpr = self.traj_tpr.text().strip() or "md.tpr"
        ndx = self.traj_index.text().strip()

        w = self.traj_widgets[key]
        out = w["out"].text().strip()
        opt = w["opt"].text().strip()

        cmd = [gmx]
        step_name = ""

        if key == "trjconv":
            out = out or "md_fit.xtc"
            step_name = "轨迹转换"
            cmd = [gmx, "trjconv", "-s", tpr, "-f", inp, "-o", out]
            if ndx and os.path.exists(os.path.join(wd, ndx)):
                cmd += ["-n", ndx]
            if opt:
                cmd += opt.split()

        elif key == "trjcat":
            out = out or "combined.xtc"
            step_name = "轨迹合并"
            cmd = [gmx, "trjcat", "-f", inp, "-o", out]
            if opt:
                cmd += opt.split()

        elif key == "trjorder":
            out = out or "ordered.xtc"
            step_name = "轨迹排序"
            cmd = [gmx, "trjorder", "-s", tpr, "-f", inp, "-o", out]
            if opt:
                cmd += opt.split()

        elif key == "trjreshape":
            out = out or "reshaped.xtc"
            step_name = "轨迹重塑"
            cmd = [gmx, "trjreshape", "-f", inp, "-o", out]
            if opt:
                cmd += opt.split()

        elif key == "trjreduce":
            out = out or "reduced.xtc"
            step_name = "轨迹精简"
            cmd = [gmx, "trjreduce", "-f", inp, "-o", out]
            if opt:
                cmd += opt.split()

        elif key == "trjcluster":
            out = out or "cluster.pdb"
            step_name = "轨迹聚类"
            cmd = [gmx, "trjcluster", "-s", tpr, "-f", inp, "-o", out]
            if opt:
                cmd += opt.split()

        elif key == "trjstrip":
            out = out or "protein.xtc"
            step_name = "轨迹剥离"
            cmd = [gmx, "trjconv", "-s", tpr, "-f", inp, "-o", out]
            if ndx and os.path.exists(os.path.join(wd, ndx)):
                cmd += ["-n", ndx]
            if opt:
                cmd += opt.split()

        else:
            self.add_log(f"未知轨迹工具: {key}", "error")
            return

        self.run_command([cmd], wd, step_name)

    # -------------------------------------------------------------------------
    # Part 2: 结构处理工具执行
    # -------------------------------------------------------------------------
    def run_structure_tool(self, key):
        wd = self._get_work_dir()
        if not wd:
            return

        gmx = self.gmx_path
        inp = self.struc_input.text().strip() or "protein.pdb"
        ndx = self.struc_index.text().strip()

        w = self.struc_widgets[key]
        out = w["out"].text().strip()
        opt = w["opt"].text().strip()

        cmd = [gmx]
        step_name = ""

        if key == "editconf":
            out = out or "protein_edit.gro"
            step_name = "编辑结构"
            cmd = [gmx, "editconf", "-f", inp, "-o", out]
            if opt:
                cmd += opt.split()

        elif key == "pdb2gmx":
            out = out or "protein.gro"
            step_name = "生成拓扑"
            cmd = [gmx, "pdb2gmx", "-f", inp, "-o", out, "-p", "topol.top", "-ff", self.md_ff.currentText()]
            if opt:
                cmd += opt.split()

        elif key == "genconf":
            out = out or "protein_multi.gro"
            step_name = "生成构象"
            cmd = [gmx, "genconf", "-f", inp, "-o", out]
            if opt:
                cmd += opt.split()

        elif key == "gmx hbond":
            out = out or "hbond_analysis.xvg"
            step_name = "氢键分析"
            cmd = [gmx, "hbond", "-f", inp, "-num", out]
            if ndx and os.path.exists(os.path.join(wd, ndx)):
                cmd += ["-n", ndx]

        elif key == "gmx rms":
            out = out or "rmsd.xvg"
            step_name = "RMSD计算"
            cmd = [gmx, "rms", "-f", inp, "-o", out]
            if ndx and os.path.exists(os.path.join(wd, ndx)):
                cmd += ["-n", ndx]

        elif key == "gmx sasa":
            out = out or "sasa.xvg"
            step_name = "表面积计算"
            cmd = [gmx, "sasa", "-f", inp, "-o", out]
            if ndx and os.path.exists(os.path.join(wd, ndx)):
                cmd += ["-n", ndx]

        elif key == "gmx make_ndx":
            out = out or "index.ndx"
            step_name = "创建索引"
            ndx_inp = w.get("ndx_struc", None)
            if ndx_inp:
                ndx_inp_val = ndx_inp.text().strip()
                if ndx_inp_val:
                    inp = ndx_inp_val
            cmd = [gmx, "make_ndx", "-f", inp, "-o", out]
            if opt:
                cmd += opt.split()

        elif key == "gmx rmsf":
            out = out or "rmsf.xvg"
            step_name = "RMSF计算"
            cmd = [gmx, "rmsf", "-f", inp, "-o", out, "-res"]
            if ndx and os.path.exists(os.path.join(wd, ndx)):
                cmd += ["-n", ndx]
            if opt:
                cmd += opt.split()

        elif key == "gmx rdf":
            out = out or "rdf.xvg"
            step_name = "径向分布函数"
            cmd = [gmx, "rdf", "-f", inp, "-o", out]
            if ndx and os.path.exists(os.path.join(wd, ndx)):
                cmd += ["-n", ndx]
            if opt:
                cmd += opt.split()

        elif key == "gmx mindist":
            out = out or "mindist.xvg"
            step_name = "最小距离计算"
            cmd = [gmx, "mindist", "-f", inp, "-o", out]
            if ndx and os.path.exists(os.path.join(wd, ndx)):
                cmd += ["-n", ndx]
            if opt:
                cmd += opt.split()

        elif key == "gmx genrestr":
            out = out or "posre.itp"
            step_name = "生成位置限制"
            cmd = [gmx, "genrestr", "-f", inp, "-o", out]
            if ndx and os.path.exists(os.path.join(wd, ndx)):
                cmd += ["-n", ndx]
            if opt:
                cmd += opt.split()

        elif key == "gmx check":
            step_name = "结构验证"
            cmd = [gmx, "check", "-f", inp]
            if opt:
                cmd += opt.split()

        elif key == "gmx dump":
            step_name = "文件信息查看"
            cmd = [gmx, "dump", "-f", inp]
            if opt:
                cmd += opt.split()

        else:
            self.add_log(f"未知结构工具: {key}", "error")
            return

        self.run_command([cmd], wd, step_name)

    # -------------------------------------------------------------------------
    # Part 6: MMPBSA 执行
    # -------------------------------------------------------------------------
    def run_mmpbsa(self):
        wd = self._get_work_dir()
        if not wd:
            return

        tpr = self.mmpbsa_tpr.text().strip() or "md.tpr"
        xtc = self.mmpbsa_xtc.text().strip() or "md.xtc"
        ndx = self.mmpbsa_index.text().strip() or "index.ndx"
        top = self.mmpbsa_top.text().strip() or "topol.top"

        step_name = "MMPBSA 结合自由能计算"
        self.add_log("=" * 60, "cmd")
        self.add_log(step_name, "cmd")
        self.add_log("提示: MMPBSA 需要安装 gmx_MMPBSA 包", "warning")
        self.add_log("  pip install gmx-MMPBSA", "warning")
        self.add_log("=" * 60, "cmd")

        cmd = [
            "python", "-m", "GMXMMPBSA.app",
            "-cs", tpr,
            "-ci", ndx,
            "-cg", "1", "13",
            "-ct", xtc,
            "-cp", top,
            "-o", "FINAL_RESULTS_MMPBSA.dat",
            "-nogui"
        ]

        self.run_command([cmd], wd, step_name)

    # -------------------------------------------------------------------------
    # Part 7: 自定义脚本
    # -------------------------------------------------------------------------
    def create_script_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        info = QLabel(
            "自定义脚本运行模块。可以编写 Windows PowerShell / Batch 脚本，"
            "调用 GROMACS 命令或执行其他自定义流程。\n"
            "提示: 脚本会在工作目录下执行，可使用 $env:GMX 或 %GMX% 获取gmx路径。"
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #555; font-size: 12px;")
        layout.addWidget(info)

        # 工具栏
        toolbar = QHBoxLayout()

        self.script_type = QComboBox()
        self.script_type.addItems(["PowerShell (.ps1)", "Batch (.bat)", "Shell 命令"])
        self.script_type.setCurrentIndex(2)
        toolbar.addWidget(QLabel("脚本类型:"))
        toolbar.addWidget(self.script_type)

        self.script_save_btn = QPushButton("保存脚本")
        self.script_save_btn.clicked.connect(self._save_script)
        self.script_load_btn = QPushButton("加载脚本")
        self.script_load_btn.clicked.connect(self._load_script)
        self.script_clear_btn = QPushButton("清空")
        self.script_clear_btn.clicked.connect(lambda: self.script_edit.clear())
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

        # 脚本编辑器
        script_group = QGroupBox("脚本编辑")
        script_group.setStyleSheet("QGroupBox { font-weight: bold; color: #6A1B9A; }")
        sg_layout = QVBoxLayout(script_group)

        self.script_edit = QPlainTextEdit()
        self.script_edit.setPlaceholderText(
            "# 示例: 运行一个简单的 GROMACS 命令\n"
            "# PowerShell 脚本示例:\n"
            "$GMX = \"" + self.gmx_path.replace("\\", "/") + "\"\n"
            "Write-Host \"Running gmx version...\"\n"
            "& $GMX --version\n"
        )
        font = QFont("Consolas", 10)
        self.script_edit.setFont(font)
        self.script_edit.setMinimumHeight(400)
        sg_layout.addWidget(self.script_edit)

        layout.addWidget(script_group, stretch=1)

        # 示例模板
        tmpl_group = QGroupBox("快速模板")
        tmpl_group.setStyleSheet("QGroupBox { font-weight: bold; color: #E65100; }")
        tmpl_layout = QVBoxLayout(tmpl_group)

        tmpl_row1 = QHBoxLayout()
        tmpl_btn1 = QPushButton("能量最小化")
        tmpl_btn1.clicked.connect(lambda: self._load_script_template("em"))
        tmpl_btn2 = QPushButton("完整MD流程")
        tmpl_btn2.clicked.connect(lambda: self._load_script_template("full_md"))
        tmpl_btn3 = QPushButton("RMSD分析")
        tmpl_btn3.clicked.connect(lambda: self._load_script_template("rmsd"))
        tmpl_btn4 = QPushButton("RDF分析")
        tmpl_btn4.clicked.connect(lambda: self._load_script_template("rdf"))
        tmpl_row1.addWidget(tmpl_btn1)
        tmpl_row1.addWidget(tmpl_btn2)
        tmpl_row1.addWidget(tmpl_btn3)
        tmpl_row1.addWidget(tmpl_btn4)
        tmpl_row1.addStretch(1)

        tmpl_row2 = QHBoxLayout()
        tmpl_btn5 = QPushButton("氢键分析")
        tmpl_btn5.clicked.connect(lambda: self._load_script_template("hbond"))
        tmpl_btn6 = QPushButton("SASA分析")
        tmpl_btn6.clicked.connect(lambda: self._load_script_template("sasa"))
        tmpl_btn7 = QPushButton("PCA分析")
        tmpl_btn7.clicked.connect(lambda: self._load_script_template("pca"))
        tmpl_btn8 = QPushButton("NVT")
        tmpl_btn8.clicked.connect(lambda: self._load_script_template("nvt"))
        tmpl_btn9 = QPushButton("NPT")
        tmpl_btn9.clicked.connect(lambda: self._load_script_template("npt"))
        tmpl_btn10 = QPushButton("MD")
        tmpl_btn10.clicked.connect(lambda: self._load_script_template("md"))
        tmpl_row2.addWidget(tmpl_btn5)
        tmpl_row2.addWidget(tmpl_btn6)
        tmpl_row2.addWidget(tmpl_btn7)
        tmpl_row2.addWidget(tmpl_btn8)
        tmpl_row2.addWidget(tmpl_btn9)
        tmpl_row2.addWidget(tmpl_btn10)
        tmpl_row2.addStretch(1)

        tmpl_row3 = QHBoxLayout()
        tmpl_btn11 = QPushButton("ClFFCl EM+NPT")
        tmpl_btn11.clicked.connect(lambda: self._load_script_template("clffcl_em_npt"))
        tmpl_btn12 = QPushButton("ClFFCl SA蒸发")
        tmpl_btn12.clicked.connect(lambda: self._load_script_template("clffcl_sa"))
        tmpl_btn13 = QPushButton("ClFFCl MD-1")
        tmpl_btn13.clicked.connect(lambda: self._load_script_template("clffcl_md1"))
        tmpl_btn14 = QPushButton("ClFFCl evapDIO")
        tmpl_btn14.clicked.connect(lambda: self._load_script_template("clffcl_evapdio"))

        tmpl_btn_manage = QPushButton("管理自定义模板")
        tmpl_btn_manage.setStyleSheet(
            "QPushButton { background-color: #9C27B0; color: white; font-weight: bold; padding: 6px 16px; }"
            "QPushButton:hover { background-color: #7B1FA2; }"
        )
        tmpl_btn_manage.clicked.connect(self._on_manage_templates)

        tmpl_row3.addWidget(tmpl_btn11)
        tmpl_row3.addWidget(tmpl_btn12)
        tmpl_row3.addWidget(tmpl_btn13)
        tmpl_row3.addWidget(tmpl_btn14)

        self.custom_tmpl_btns = []
        self._load_custom_template_buttons(tmpl_row3)

        tmpl_row3.addWidget(tmpl_btn_manage)
        tmpl_row3.addStretch(1)

        tmpl_layout.addLayout(tmpl_row1)
        tmpl_layout.addLayout(tmpl_row2)
        tmpl_layout.addLayout(tmpl_row3)
        layout.addWidget(tmpl_group)

        return tab

    def _load_custom_template_buttons(self, layout):
        if getattr(sys, 'frozen', False):
            base = os.path.dirname(sys.executable)
        else:
            base = os.path.dirname(os.path.abspath(__file__))
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
                    btn.clicked.connect(lambda checked, t=template: self._apply_custom_template(t))
                    self.custom_tmpl_btns.append(btn)
                    layout.addWidget(btn)
            except Exception:
                pass

    def _apply_custom_template(self, template):
        self.script_edit.setPlainText(template["content"])
        idx = self.script_type.findText(template["type"])
        if idx >= 0:
            self.script_type.setCurrentIndex(idx)

    def _on_manage_templates(self):
        dialog = CustomTemplateDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            tmpl_group = self.tab_widget.widget(6).findChild(QGroupBox, "")
            if tmpl_group:
                tmpl_layout = tmpl_group.layout()
                for btn in self.custom_tmpl_btns:
                    tmpl_layout.removeWidget(btn)
                    btn.deleteLater()
                self.custom_tmpl_btns.clear()
                self._load_custom_template_buttons(tmpl_layout)
            self.add_log("自定义模板已更新", "success")

    def _load_script_template(self, key):
        gmx_norm = self.gmx_path.replace("\\", "/")
        script_type = self.script_type.currentText()
        
        if "PowerShell" in script_type:
            if key == "em":
                text = (
                    "# 能量最小化脚本模板 (PowerShell)\n"
                    "$GMX = \"" + gmx_norm + "\"\n"
                    "Set-Location $PSScriptRoot\n\n"
                    "# 1. 生成拓扑 (如果已有topol.top可跳过)\n"
                    "# & $GMX pdb2gmx -f protein.pdb -o protein.gro -p topol.top -ff amber99sb-ildn -water tip3p -ignh\n\n"
                    "# 2. 构建盒子\n"
                    "& $GMX editconf -f protein.gro -o protein_box.gro -c -d 1.0 -bt cubic\n\n"
                    "# 3. 溶剂化\n"
                    "& $GMX solvate -cp protein_box.gro -o protein_solv.gro -p topol.top\n\n"
                    "# 4. 能量最小化\n"
                    "& $GMX grompp -f em.mdp -c protein_solv.gro -p topol.top -o em.tpr -maxwarn 2\n"
                    "& $GMX mdrun -deffnm em -v\n\n"
                    "Write-Host \"能量最小化完成!\"\n"
                )
            elif key == "full_md":
                text = (
                    "# 完整MD流程脚本模板 (EM -> NVT -> NPT -> MD)\n"
                    "$GMX = \"" + gmx_norm + "\"\n"
                    "Set-Location $PSScriptRoot\n\n"
                    "$steps = @(\n"
                    "    @{name='EM';  mdp='em.mdp';  prev='protein_solv.gro'; out='em'},\n"
                    "    @{name='NVT'; mdp='nvt.mdp'; prev='em.gro';       out='nvt'},\n"
                    "    @{name='NPT'; mdp='npt.mdp'; prev='nvt.gro';      out='npt'},\n"
                    "    @{name='MD';  mdp='md.mdp';  prev='npt.gro';      out='md'}\n"
                    ")\n\n"
                    "foreach ($s in $steps) {\n"
                    "    Write-Host \"==== 运行 $($s.name) ====\" -ForegroundColor Cyan\n"
                    "    & $GMX grompp -f $s.mdp -c $s.prev -r $s.prev -p topol.top -o \"$($s.out).tpr\" -maxwarn 2\n"
                    "    if ($LASTEXITCODE -ne 0) { Write-Error \"grompp 失败\"; exit 1 }\n"
                    "    & $GMX mdrun -deffnm $s.out -v\n"
                    "    if ($LASTEXITCODE -ne 0) { Write-Error \"mdrun 失败\"; exit 1 }\n"
                    "    Write-Host \"$($s.name) 完成\" -ForegroundColor Green\n"
                    "}\n\n"
                    "Write-Host \"所有MD步骤完成!\" -ForegroundColor Green\n"
                )
            elif key == "clffcl_em_npt":
                text = (
                    "# ClFFCl EM+NPT流程模板 (PowerShell)\n"
                    "# 流程: EM-1 → EM-2 → NPT-1 → NPT-2\n"
                    "# 使用文件: ydw-em_01.mdp (steep), ydw-em_02.mdp (cg), ydw-npt_01.mdp (1ns), ydw-npt_02.mdp (2ns)\n"
                    "# 输入: ydw-PM6-ClFFCl.pdb, p4PM6-ClFFCl-mix.top\n"
                    "$GMX = \"" + gmx_norm + "\"\n"
                    "Set-Location $PSScriptRoot\n\n"
                    "# ==== Step 1: 能量最小化 EM-1 (steep) ====\n"
                    "Write-Host \"==== 运行 EM-1 ====\" -ForegroundColor Cyan\n"
                    "& $GMX grompp -f ydw-em_01.mdp -c ydw-PM6-ClFFCl.pdb -p p4PM6-ClFFCl-mix.top -o ClFFCl_em1.tpr -maxwarn 200\n"
                    "if ($LASTEXITCODE -ne 0) { Write-Error \"EM-1 grompp 失败\"; exit 1 }\n"
                    "& $GMX mdrun -v -deffnm ClFFCl_em1 -nt 6 -pin on -nb gpu -pme cpu\n"
                    "if ($LASTEXITCODE -ne 0) { Write-Error \"EM-1 mdrun 失败\"; exit 1 }\n"
                    "Write-Host \"EM-1 完成\" -ForegroundColor Green\n\n"
                    "# ==== Step 2: 能量最小化 EM-2 (cg) ====\n"
                    "Write-Host \"==== 运行 EM-2 ====\" -ForegroundColor Cyan\n"
                    "& $GMX grompp -f ydw-em_02.mdp -c ClFFCl_em1.gro -p p4PM6-ClFFCl-mix.top -o ClFFCl_em2.tpr -maxwarn 200\n"
                    "if ($LASTEXITCODE -ne 0) { Write-Error \"EM-2 grompp 失败\"; exit 1 }\n"
                    "& $GMX mdrun -v -deffnm ClFFCl_em2 -nt 6 -pin on -nb gpu -pme cpu\n"
                    "if ($LASTEXITCODE -ne 0) { Write-Error \"EM-2 mdrun 失败\"; exit 1 }\n"
                    "Write-Host \"EM-2 完成\" -ForegroundColor Green\n\n"
                    "# ==== Step 3: NPT 平衡 1 (1ns) ====\n"
                    "Write-Host \"==== 运行 NPT-1 ====\" -ForegroundColor Cyan\n"
                    "& $GMX grompp -f ydw-npt_01.mdp -c ClFFCl_em2.gro -p p4PM6-ClFFCl-mix.top -o ClFFCl_npt1.tpr -maxwarn 200\n"
                    "if ($LASTEXITCODE -ne 0) { Write-Error \"NPT-1 grompp 失败\"; exit 1 }\n"
                    "& $GMX mdrun -v -deffnm ClFFCl_npt1 -nt 6 -pin on -gpu_id 0 -nb gpu -pme gpu -bonded gpu -update gpu\n"
                    "if ($LASTEXITCODE -ne 0) { Write-Error \"NPT-1 mdrun 失败\"; exit 1 }\n"
                    "Write-Host \"NPT-1 完成\" -ForegroundColor Green\n\n"
                    "# ==== Step 4: NPT 平衡 2 (2ns) ====\n"
                    "Write-Host \"==== 运行 NPT-2 ====\" -ForegroundColor Cyan\n"
                    "& $GMX grompp -f ydw-npt_02.mdp -c ClFFCl_npt1.gro -p p4PM6-ClFFCl-mix.top -o ClFFCl_npt2.tpr -maxwarn 200\n"
                    "if ($LASTEXITCODE -ne 0) { Write-Error \"NPT-2 grompp 失败\"; exit 1 }\n"
                    "& $GMX mdrun -v -deffnm ClFFCl_npt2 -nt 6 -pin on -gpu_id 0 -nb gpu -pme gpu -bonded gpu -update gpu\n"
                    "if ($LASTEXITCODE -ne 0) { Write-Error \"NPT-2 mdrun 失败\"; exit 1 }\n"
                    "Write-Host \"NPT-2 完成\" -ForegroundColor Green\n\n"
                    "Write-Host \"所有步骤完成!\" -ForegroundColor Green\n"
                )
            elif key == "clffcl_sa":
                text = (
                    "# ClFFCl SA溶剂蒸发流程模板 (PowerShell)\n"
                    "# 流程: 逐步删除CF溶剂分子，每轮运行10ps NPT\n"
                    "# 使用文件: ydw-npt-sa.mdp\n"
                    "# 输入: ClFFCl_npt2.gro, p4PM6-ClFFCl-mix.top\n"
                    "$GMX = \"" + gmx_norm + "\"\n"
                    "Set-Location $PSScriptRoot\n\n"
                    "# 配置参数\n"
                    "$inputGro = \"ClFFCl_npt2.gro\"\n"
                    "$topFile = \"p4PM6-ClFFCl-mix.top\"\n"
                    "$mdpFile = \"ydw-npt-sa.mdp\"\n"
                    "$prefix = \"ClFFCl_sa\"\n"
                    "$loops = 500\n"
                    "$deleteNum = 100\n"
                    "$atomsPerSolvent = 5\n\n"
                    "# 检查输入文件\n"
                    "if (-not (Test-Path $inputGro)) { Write-Error \"输入文件不存在: $inputGro\"; exit 1 }\n"
                    "if (-not (Test-Path $topFile)) { Write-Error \"拓扑文件不存在: $topFile\"; exit 1 }\n"
                    "if (-not (Test-Path $mdpFile)) { Write-Error \"MDP文件不存在: $mdpFile\"; exit 1 }\n\n"
                    "# 备份原始文件\n"
                    "Copy-Item $inputGro \"${prefix}_original.gro\" -Force\n"
                    "Copy-Item $topFile \"${prefix}_original.top\" -Force\n"
                    "Write-Host \"已备份原始文件\" -ForegroundColor Green\n\n"
                    "$workGro = \"${prefix}_work.gro\"\n"
                    "$workTop = \"${prefix}_work.top\"\n"
                    "$currentGro = \"${prefix}_current.gro\"\n"
                    "$currentTop = \"${prefix}_current.top\"\n"
                    "Copy-Item $inputGro $workGro -Force\n"
                    "Copy-Item $topFile $workTop -Force\n\n"
                    "for ($i = 1; $i -le $loops; $i++) {\n"
                    "    Write-Host \"==== SA 第 $i/$loops 轮 ====\" -ForegroundColor Cyan\n"
                    "\n"
                    "    $newGro = \"${prefix}_new.gro\"\n"
                    "    $newTop = \"${prefix}_new.top\"\n"
                    "\n"
                    "    Write-Host \"删除 $deleteNum 个CF溶剂分子...\" -ForegroundColor Yellow\n"
                    "    python delete_solvent.py --solvent CF --delete-num $deleteNum --atoms-per-mol $atomsPerSolvent --loop $i --input $workGro --output $newGro --topology $workTop --topology-output $newTop\n"
                    "    if ($LASTEXITCODE -ne 0) { Write-Error \"删除溶剂失败\"; exit 1 }\n"
                    "\n"
                    "    Move-Item $newGro $workGro -Force\n"
                    "    Move-Item $newTop $workTop -Force\n"
                    "\n"
                    "    Write-Host \"grompp...\" -ForegroundColor Yellow\n"
                    "    & $GMX grompp -f $mdpFile -c $workGro -p $workTop -o \"${prefix}_$i.tpr\" -maxwarn 200\n"
                    "    if ($LASTEXITCODE -ne 0) { Write-Error \"grompp 失败\"; exit 1 }\n"
                    "\n"
                    "    Write-Host \"mdrun (10ps)...\" -ForegroundColor Yellow\n"
                    "    & $GMX mdrun -v -deffnm \"${prefix}_$i\" -nt 6 -pin on -gpu_id 0 -nb gpu -pme gpu -bonded gpu -update gpu\n"
                    "    if ($LASTEXITCODE -ne 0) { Write-Error \"mdrun 失败\"; exit 1 }\n"
                    "\n"
                    "    Copy-Item \"${prefix}_$i.gro\" $currentGro -Force\n"
                    "    Copy-Item $workTop $currentTop -Force\n"
                    "    Write-Host \"第 $i 轮完成\" -ForegroundColor Green\n"
                    "}\n\n"
                    "Write-Host \"SA溶剂蒸发完成!\" -ForegroundColor Green\n"
                    "Write-Host \"最终结构: $currentGro\" -ForegroundColor Yellow\n"
                    "Write-Host \"最终拓扑: $currentTop\" -ForegroundColor Yellow\n"
                )
            elif key == "clffcl_evapdio":
                text = (
                    "# ClFFCl evapDIO流程模板 (PowerShell)\n"
                    "# 流程: 删除DIO添加剂 → 运行1ns NPT平衡 → 退火 → MD2\n"
                    "# 使用文件: ydw-evapDIO.mdp, ydw-ta.mdp, ydw-md_02.mdp\n"
                    "# 输入: ClFFCl_md.gro, ClFFCl_sa_current.top\n"
                    "$GMX = \"" + gmx_norm + "\"\n"
                    "Set-Location $PSScriptRoot\n\n"
                    "# 配置参数\n"
                    "$inputGro = \"ClFFCl_md.gro\"\n"
                    "$inputTop = \"ClFFCl_sa_current.top\"\n"
                    "$mdpFile = \"ydw-evapDIO.mdp\"\n"
                    "$prefix = \"ClFFCl_evapDIO\"\n\n"
                    "# 检查输入文件\n"
                    "if (-not (Test-Path $inputGro)) { Write-Error \"输入文件不存在: $inputGro\"; exit 1 }\n"
                    "if (-not (Test-Path $inputTop)) { Write-Error \"拓扑文件不存在: $inputTop\"; exit 1 }\n"
                    "if (-not (Test-Path $mdpFile)) { Write-Error \"MDP文件不存在: $mdpFile\"; exit 1 }\n\n"
                    "# ==== Step 1: 删除DIO添加剂 ====\n"
                    "Write-Host \"==== 删除DIO添加剂 ====\" -ForegroundColor Cyan\n"
                    "$outGro = \"${prefix}_DA.gro\"\n"
                    "$outTop = \"${prefix}.top\"\n"
                    "python delete_additive_all.py --additive DIO --atoms-per-mol 6 --input $inputGro --output $outGro --topology $inputTop --topology-output $outTop\n"
                    "if ($LASTEXITCODE -ne 0) { Write-Error \"删除DIO失败\"; exit 1 }\n"
                    "Write-Host \"DIO删除完成\" -ForegroundColor Green\n\n"
                    "# ==== Step 2: 1ns NPT平衡 ====\n"
                    "Write-Host \"==== 运行1ns NPT平衡 ====\" -ForegroundColor Cyan\n"
                    "& $GMX grompp -f $mdpFile -c \"${prefix}_DA.gro\" -p \"${prefix}.top\" -o \"${prefix}.tpr\" -maxwarn 200\n"
                    "if ($LASTEXITCODE -ne 0) { Write-Error \"grompp 失败\"; exit 1 }\n"
                    "& $GMX mdrun -v -deffnm $prefix -nt 6 -pin on -gpu_id 0 -nb gpu -pme gpu -bonded gpu -update gpu\n"
                    "if ($LASTEXITCODE -ne 0) { Write-Error \"mdrun 失败\"; exit 1 }\n"
                    "Write-Host \"evapDIO NPT完成\" -ForegroundColor Green\n\n"
                    "# ==== Step 3: 退火过程 ====\n"
                    "Write-Host \"==== 运行退火 ====\" -ForegroundColor Cyan\n"
                    "& $GMX grompp -f ydw-ta.mdp -c \"${prefix}.gro\" -p \"${prefix}.top\" -o \"${prefix}_anneal.tpr\" -maxwarn 200\n"
                    "if ($LASTEXITCODE -ne 0) { Write-Error \"退火 grompp 失败\"; exit 1 }\n"
                    "& $GMX mdrun -v -deffnm \"${prefix}_anneal\" -nt 6 -pin on -gpu_id 0 -nb gpu -pme gpu -bonded gpu -update gpu\n"
                    "if ($LASTEXITCODE -ne 0) { Write-Error \"退火 mdrun 失败\"; exit 1 }\n"
                    "Write-Host \"退火完成\" -ForegroundColor Green\n\n"
                    "# ==== Step 4: MD2 生产模拟 ====\n"
                    "Write-Host \"==== 运行MD2 ====\" -ForegroundColor Cyan\n"
                    "& $GMX grompp -f ydw-md_02.mdp -c \"${prefix}_anneal.gro\" -p \"${prefix}.top\" -o \"${prefix}_md2.tpr\" -maxwarn 200\n"
                    "if ($LASTEXITCODE -ne 0) { Write-Error \"MD2 grompp 失败\"; exit 1 }\n"
                    "& $GMX mdrun -v -deffnm \"${prefix}_md2\" -nt 6 -pin on -gpu_id 0 -nb gpu -pme gpu -bonded gpu -update gpu\n"
                    "if ($LASTEXITCODE -ne 0) { Write-Error \"MD2 mdrun 失败\"; exit 1 }\n"
                    "Write-Host \"MD2完成\" -ForegroundColor Green\n\n"
                    "Write-Host \"evapDIO+退火+MD2流程全部完成!\" -ForegroundColor Green\n"
                )
            elif key == "rmsd":
                text = (
                    "# RMSD分析脚本模板\n"
                    "$GMX = \"" + gmx_norm + "\"\n"
                    "Set-Location $PSScriptRoot\n\n"
                    "# 先做轨迹拟合 (去除平动转动)\n"
                    "echo '4' | & $GMX trjconv -s md.tpr -f md.xtc -o md_fit.xtc -fit rot+trans\n\n"
                    "# 计算RMSD (骨架原子)\n"
                    "echo '4 4' | & $GMX rms -s md.tpr -f md_fit.xtc -o rmsd.xvg -tu ns\n\n"
                    "# 计算RMSF\n"
                    "echo '3' | & $GMX rmsf -s md.tpr -f md_fit.xtc -o rmsf.xvg -res\n\n"
                    "Write-Host \"RMSD/RMSF分析完成!\"\n"
                )
            elif key == "clffcl_md1":
                text = (
                    "# ClFFCl MD-1生产模拟流程模板 (PowerShell)\n"
                    "# 流程: 基于ClFFCl_npt2.gro运行10ns生产模拟\n"
                    "# 使用文件: ydw-md_01.mdp (10ns)\n"
                    "# 输入: ClFFCl_npt2.gro, p4PM6-ClFFCl-mix.top\n"
                    "$GMX = \"" + gmx_norm + "\"\n"
                    "Set-Location $PSScriptRoot\n\n"
                    "# ==== Step 1: MD-1 生产模拟 (10ns) ====\n"
                    "Write-Host \"==== 运行 MD-1 (10ns) ====\" -ForegroundColor Cyan\n"
                    "& $GMX grompp -f ydw-md_01.mdp -c ClFFCl_npt2.gro -p p4PM6-ClFFCl-mix.top -o ClFFCl_md.tpr -maxwarn 200\n"
                    "if ($LASTEXITCODE -ne 0) { Write-Error \"MD-1 grompp 失败\"; exit 1 }\n"
                    "& $GMX mdrun -v -deffnm ClFFCl_md -nt 6 -pin on -gpu_id 0 -nb gpu -pme gpu -bonded gpu -update gpu\n"
                    "if ($LASTEXITCODE -ne 0) { Write-Error \"MD-1 mdrun 失败\"; exit 1 }\n"
                    "Write-Host \"MD-1 (10ns)完成\" -ForegroundColor Green\n\n"
                    "Write-Host \"ClFFCl MD-1生产模拟完成!\" -ForegroundColor Green\n"
                )
            elif key == "nvt":
                text = (
                    "# NVT恒温平衡脚本模板 (PowerShell)\n"
                    "$GMX = \"" + gmx_norm + "\"\n"
                    "Set-Location $PSScriptRoot\n\n"
                    "# NVT 恒温平衡\n"
                    "Write-Host \"==== 运行 NVT 恒温平衡 ====\" -ForegroundColor Cyan\n"
                    "& $GMX grompp -f nvt.mdp -c em.gro -r em.gro -p topol.top -o nvt.tpr -maxwarn 2\n"
                    "if ($LASTEXITCODE -ne 0) { Write-Error \"grompp 失败\"; exit 1 }\n"
                    "& $GMX mdrun -deffnm nvt -v\n"
                    "if ($LASTEXITCODE -ne 0) { Write-Error \"mdrun 失败\"; exit 1 }\n"
                    "Write-Host \"NVT恒温平衡完成!\" -ForegroundColor Green\n"
                )
            elif key == "npt":
                text = (
                    "# NPT恒压平衡脚本模板 (PowerShell)\n"
                    "$GMX = \"" + gmx_norm + "\"\n"
                    "Set-Location $PSScriptRoot\n\n"
                    "# NPT 恒压平衡\n"
                    "Write-Host \"==== 运行 NPT 恒压平衡 ====\" -ForegroundColor Cyan\n"
                    "& $GMX grompp -f npt.mdp -c nvt.gro -r nvt.gro -p topol.top -o npt.tpr -maxwarn 2\n"
                    "if ($LASTEXITCODE -ne 0) { Write-Error \"grompp 失败\"; exit 1 }\n"
                    "& $GMX mdrun -deffnm npt -v\n"
                    "if ($LASTEXITCODE -ne 0) { Write-Error \"mdrun 失败\"; exit 1 }\n"
                    "Write-Host \"NPT恒压平衡完成!\" -ForegroundColor Green\n"
                )
            elif key == "md":
                text = (
                    "# MD生产模拟脚本模板 (PowerShell)\n"
                    "$GMX = \"" + gmx_norm + "\"\n"
                    "Set-Location $PSScriptRoot\n\n"
                    "# MD 生产模拟\n"
                    "Write-Host \"==== 运行 MD 生产模拟 ====\" -ForegroundColor Cyan\n"
                    "& $GMX grompp -f md.mdp -c npt.gro -r npt.gro -p topol.top -o md.tpr -maxwarn 2\n"
                    "if ($LASTEXITCODE -ne 0) { Write-Error \"grompp 失败\"; exit 1 }\n"
                    "& $GMX mdrun -deffnm md -v\n"
                    "if ($LASTEXITCODE -ne 0) { Write-Error \"mdrun 失败\"; exit 1 }\n"
                    "Write-Host \"MD生产模拟完成!\" -ForegroundColor Green\n"
                )
            elif key == "rdf":
                text = (
                    "# RDF径向分布函数分析脚本模板 (PowerShell)\n"
                    "$GMX = \"" + gmx_norm + "\"\n"
                    "Set-Location $PSScriptRoot\n\n"
                    "# 计算径向分布函数 (蛋白-溶剂)\n"
                    "echo '1 11' | & $GMX rdf -s md.tpr -f md.xtc -o rdf.xvg -ref 'Protein' -sel 'Water'\n\n"
                    "# 计算配位数\n"
                    "echo '1 11' | & $GMX rdf -s md.tpr -f md.xtc -o rdf_coord.xvg -ref 'Protein' -sel 'Water' -cn\n\n"
                    "Write-Host \"RDF分析完成!\"\n"
                )
            elif key == "hbond":
                text = (
                    "# 氢键分析脚本模板 (PowerShell)\n"
                    "$GMX = \"" + gmx_norm + "\"\n"
                    "Set-Location $PSScriptRoot\n\n"
                    "# 计算氢键 (蛋白-蛋白)\n"
                    "echo '1 1' | & $GMX hbond -s md.tpr -f md.xtc -num hbond.xvg\n\n"
                    "# 计算氢键 (蛋白-溶剂)\n"
                    "echo '1 11' | & $GMX hbond -s md.tpr -f md.xtc -num hbond_solv.xvg\n\n"
                    "# 氢键寿命分析\n"
                    "echo '1 1' | & $GMX hbond -s md.tpr -f md.xtc -ac hbond_analysis.xvg\n\n"
                    "Write-Host \"氢键分析完成!\"\n"
                )
            elif key == "sasa":
                text = (
                    "# SASA溶剂可及面积分析脚本模板 (PowerShell)\n"
                    "$GMX = \"" + gmx_norm + "\"\n"
                    "Set-Location $PSScriptRoot\n\n"
                    "# 计算整体SASA\n"
                    "echo '1' | & $GMX sasa -s md.tpr -f md.xtc -o sasa.xvg -surface 1 -output 1\n\n"
                    "# 按残基计算SASA\n"
                    "echo '3' | & $GMX sasa -s md.tpr -f md.xtc -o sasa_res.xvg -surface 1 -output 2\n\n"
                    "# 计算极性/非极性SASA\n"
                    "echo '1' | & $GMX sasa -s md.tpr -f md.xtc -o sasa_pol.xvg -surface 2 -output 1\n\n"
                    "Write-Host \"SASA分析完成!\"\n"
                )
            elif key == "pca":
                text = (
                    "# PCA主成分分析脚本模板 (PowerShell)\n"
                    "# 注意：需要先做轨迹拟合\n"
                    "$GMX = \"" + gmx_norm + "\"\n"
                    "Set-Location $PSScriptRoot\n\n"
                    "# 步骤1: 轨迹拟合 (去除平动转动)\n"
                    "Write-Host \"==== 轨迹拟合 ====\" -ForegroundColor Cyan\n"
                    "echo '4' | & $GMX trjconv -s md.tpr -f md.xtc -o md_fit.xtc -fit rot+trans\n\n"
                    "# 步骤2: 计算协方差矩阵\n"
                    "Write-Host \"==== 计算协方差矩阵 ====\" -ForegroundColor Cyan\n"
                    "echo '4' | & $GMX covar -s md.tpr -f md_fit.xtc -o eigenvectors.trr -xpm covar.xpm\n\n"
                    "# 步骤3: 对角化协方差矩阵\n"
                    "Write-Host \"==== 对角化协方差矩阵 ====\" -ForegroundColor Cyan\n"
                    "& $GMX anaeig -s md.tpr -f eigenvectors.trr -o eigenvalues.xvg -v eigenvectors.trr -n 10\n\n"
                    "# 步骤4: 投影到主成分\n"
                    "Write-Host \"==== 投影到主成分 ====\" -ForegroundColor Cyan\n"
                    "echo '4' | & $GMX anaeig -s md.tpr -f md_fit.xtc -proj pcaprojection.xvg\n\n"
                    "# 步骤5: 生成PC1和PC2的结构\n"
                    "Write-Host \"==== 生成主成分结构 ====\" -ForegroundColor Cyan\n"
                    "echo '4' | & $GMX anaeig -s md.tpr -f md_fit.xtc -first 1 -last 2 -o pca_pc1_pc2.trr\n\n"
                    "Write-Host \"PCA分析完成!\" -ForegroundColor Green\n"
                )
            else:
                text = ""
        
        elif "Batch" in script_type:
            gmx_batch = gmx_norm.replace("/", "\\")
            if key == "em":
                text = (
                    "@echo off\n"
                    "REM 能量最小化脚本模板 (Batch)\n"
                    "set GMX=" + gmx_batch + "\n"
                    "cd /d %~dp0\n\n"
                    "REM 1. 生成拓扑 (如果已有topol.top可跳过)\n"
                    "REM %GMX% pdb2gmx -f protein.pdb -o protein.gro -p topol.top -ff amber99sb-ildn -water tip3p -ignh\n\n"
                    "REM 2. 构建盒子\n"
                    "%GMX% editconf -f protein.gro -o protein_box.gro -c -d 1.0 -bt cubic\n\n"
                    "REM 3. 溶剂化\n"
                    "%GMX% solvate -cp protein_box.gro -o protein_solv.gro -p topol.top\n\n"
                    "REM 4. 能量最小化\n"
                    "%GMX% grompp -f em.mdp -c protein_solv.gro -p topol.top -o em.tpr -maxwarn 2\n"
                    "if errorlevel 1 goto error\n"
                    "%GMX% mdrun -deffnm em -v\n"
                    "if errorlevel 1 goto error\n\n"
                    "echo 能量最小化完成!\n"
                    "goto end\n"
                    ":error\n"
                    "echo 执行失败!\n"
                    ":end\n"
                )
            elif key == "full_md":
                text = (
                    "@echo off\n"
                    "REM 完整MD流程脚本模板 (EM -> NVT -> NPT -> MD)\n"
                    "set GMX=" + gmx_batch + "\n"
                    "cd /d %~dp0\n\n"
                    "REM EM 能量最小化\n"
                    "echo ==== 运行 EM ====\n"
                    "%GMX% grompp -f em.mdp -c protein_solv.gro -r protein_solv.gro -p topol.top -o em.tpr -maxwarn 2\n"
                    "if errorlevel 1 goto error\n"
                    "%GMX% mdrun -deffnm em -v\n"
                    "if errorlevel 1 goto error\n"
                    "echo EM 完成\n\n"
                    "REM NVT 恒温平衡\n"
                    "echo ==== 运行 NVT ====\n"
                    "%GMX% grompp -f nvt.mdp -c em.gro -r em.gro -p topol.top -o nvt.tpr -maxwarn 2\n"
                    "if errorlevel 1 goto error\n"
                    "%GMX% mdrun -deffnm nvt -v\n"
                    "if errorlevel 1 goto error\n"
                    "echo NVT 完成\n\n"
                    "REM NPT 恒压平衡\n"
                    "echo ==== 运行 NPT ====\n"
                    "%GMX% grompp -f npt.mdp -c nvt.gro -r nvt.gro -p topol.top -o npt.tpr -maxwarn 2\n"
                    "if errorlevel 1 goto error\n"
                    "%GMX% mdrun -deffnm npt -v\n"
                    "if errorlevel 1 goto error\n"
                    "echo NPT 完成\n\n"
                    "REM MD 生产模拟\n"
                    "echo ==== 运行 MD ====\n"
                    "%GMX% grompp -f md.mdp -c npt.gro -r npt.gro -p topol.top -o md.tpr -maxwarn 2\n"
                    "if errorlevel 1 goto error\n"
                    "%GMX% mdrun -deffnm md -v\n"
                    "if errorlevel 1 goto error\n"
                    "echo MD 完成\n\n"
                    "echo 所有MD步骤完成!\n"
                    "goto end\n"
                    ":error\n"
                    "echo 执行失败!\n"
                    ":end\n"
                )
            elif key == "rmsd":
                text = (
                    "@echo off\n"
                    "REM RMSD分析脚本模板\n"
                    "set GMX=" + gmx_batch + "\n"
                    "cd /d %~dp0\n\n"
                    "REM 先做轨迹拟合 (去除平动转动)\n"
                    "echo 4 | %GMX% trjconv -s md.tpr -f md.xtc -o md_fit.xtc -fit rot+trans\n\n"
                    "REM 计算RMSD (骨架原子)\n"
                    "echo 4 4 | %GMX% rms -s md.tpr -f md_fit.xtc -o rmsd.xvg -tu ns\n\n"
                    "REM 计算RMSF\n"
                    "echo 3 | %GMX% rmsf -s md.tpr -f md_fit.xtc -o rmsf.xvg -res\n\n"
                    "echo RMSD/RMSF分析完成!\n"
                )
            elif key == "clffcl_em_npt":
                text = (
                    "@echo off\n"
                    "REM ClFFCl EM+NPT流程模板 (Batch)\n"
                    "REM 流程: EM-1 → EM-2 → NPT-1 → NPT-2\n"
                    "REM 使用文件: ydw-em_01.mdp (steep), ydw-em_02.mdp (cg), ydw-npt_01.mdp (1ns), ydw-npt_02.mdp (2ns)\n"
                    "REM 输入: ydw-PM6-ClFFCl.pdb, p4PM6-ClFFCl-mix.top\n"
                    "set GMX=" + gmx_batch + "\n"
                    "cd /d %~dp0\n\n"
                    "REM ==== Step 1: 能量最小化 EM-1 (steep) ====\n"
                    "echo ==== 运行 EM-1 ====\n"
                    "%GMX% grompp -f ydw-em_01.mdp -c ydw-PM6-ClFFCl.pdb -p p4PM6-ClFFCl-mix.top -o ClFFCl_em1.tpr -maxwarn 200\n"
                    "if errorlevel 1 goto error\n"
                    "%GMX% mdrun -v -deffnm ClFFCl_em1 -nt 6 -pin on -nb gpu -pme cpu\n"
                    "if errorlevel 1 goto error\n"
                    "echo EM-1 完成\n\n"
                    "REM ==== Step 2: 能量最小化 EM-2 (cg) ====\n"
                    "echo ==== 运行 EM-2 ====\n"
                    "%GMX% grompp -f ydw-em_02.mdp -c ClFFCl_em1.gro -p p4PM6-ClFFCl-mix.top -o ClFFCl_em2.tpr -maxwarn 200\n"
                    "if errorlevel 1 goto error\n"
                    "%GMX% mdrun -v -deffnm ClFFCl_em2 -nt 6 -pin on -nb gpu -pme cpu\n"
                    "if errorlevel 1 goto error\n"
                    "echo EM-2 完成\n\n"
                    "REM ==== Step 3: NPT 平衡 1 (1ns) ====\n"
                    "echo ==== 运行 NPT-1 ====\n"
                    "%GMX% grompp -f ydw-npt_01.mdp -c ClFFCl_em2.gro -p p4PM6-ClFFCl-mix.top -o ClFFCl_npt1.tpr -maxwarn 200\n"
                    "if errorlevel 1 goto error\n"
                    "%GMX% mdrun -v -deffnm ClFFCl_npt1 -nt 6 -pin on -gpu_id 0 -nb gpu -pme gpu -bonded gpu -update gpu\n"
                    "if errorlevel 1 goto error\n"
                    "echo NPT-1 完成\n\n"
                    "REM ==== Step 4: NPT 平衡 2 (2ns) ====\n"
                    "echo ==== 运行 NPT-2 ====\n"
                    "%GMX% grompp -f ydw-npt_02.mdp -c ClFFCl_npt1.gro -p p4PM6-ClFFCl-mix.top -o ClFFCl_npt2.tpr -maxwarn 200\n"
                    "if errorlevel 1 goto error\n"
                    "%GMX% mdrun -v -deffnm ClFFCl_npt2 -nt 6 -pin on -gpu_id 0 -nb gpu -pme gpu -bonded gpu -update gpu\n"
                    "if errorlevel 1 goto error\n"
                    "echo NPT-2 完成\n\n"
                    "echo 所有步骤完成!\n"
                    "goto end\n"
                    ":error\n"
                    "echo 执行失败!\n"
                    ":end\n"
                )
            elif key == "clffcl_sa":
                text = (
                    "@echo off\n"
                    "REM ClFFCl SA溶剂蒸发流程模板 (Batch)\n"
                    "REM 流程: 逐步删除CF溶剂分子，每轮运行10ps NPT\n"
                    "REM 使用文件: ydw-npt-sa.mdp\n"
                    "REM 输入: ClFFCl_npt2.gro, p4PM6-ClFFCl-mix.top\n"
                    "set GMX=" + gmx_batch + "\n"
                    "cd /d %~dp0\n\n"
                    "set inputGro=ClFFCl_npt2.gro\n"
                    "set topFile=p4PM6-ClFFCl-mix.top\n"
                    "set mdpFile=ydw-npt-sa.mdp\n"
                    "set prefix=ClFFCl_sa\n"
                    "set loops=500\n"
                    "set deleteNum=100\n"
                    "set atomsPerSolvent=5\n"
                    "REM 备份原始文件\n"
                    "copy /Y %inputGro% %prefix%_original.gro\n"
                    "copy /Y %topFile% %prefix%_original.top\n"
                    "echo 已备份原始文件\n\n"
                    "set workGro=%prefix%_work.gro\n"
                    "set workTop=%prefix%_work.top\n"
                    "set currentGro=%prefix%_current.gro\n"
                    "set currentTop=%prefix%_current.top\n"
                    "copy /Y %inputGro% %workGro%\n"
                    "copy /Y %topFile% %workTop%\n\n"
                    "for /l %%i in (1,1,%loops%) do (\n"
                    "    echo ==== SA 第 %%i/%loops% 轮 ====\n"
                    "    set newGro=%prefix%_new.gro\n"
                    "    set newTop=%prefix%_new.top\n"
                    "    echo 删除 %deleteNum% 个CF溶剂分子...\n"
                    "    python delete_solvent.py --solvent CF --delete-num %deleteNum% --atoms-per-mol %atomsPerSolvent% --loop %%i --input %workGro% --output %newGro% --topology %workTop% --topology-output %newTop%\n"
                    "    if errorlevel 1 goto error\n"
                    "    move /Y %newGro% %workGro%\n"
                    "    move /Y %newTop% %workTop%\n"
                    "    echo grompp...\n"
                    "    %GMX% grompp -f %mdpFile% -c %workGro% -p %workTop% -o %prefix%_%%i.tpr -maxwarn 200\n"
                    "    if errorlevel 1 goto error\n"
                    "    echo mdrun (10ps)...\n"
                    "    %GMX% mdrun -v -deffnm %prefix%_%%i -nt 6 -pin on -gpu_id 0 -nb gpu -pme gpu -bonded gpu -update gpu\n"
                    "    if errorlevel 1 goto error\n"
                    "    copy /Y %prefix%_%%i.gro %currentGro%\n"
                    "    copy /Y %workTop% %currentTop%\n"
                    "    echo 第 %%i 轮完成\n"
                    ")\n\n"
                    "echo SA溶剂蒸发完成!\n"
                    "echo 最终结构: %currentGro%\n"
                    "echo 最终拓扑: %currentTop%\n"
                    "goto end\n"
                    ":error\n"
                    "echo 执行失败!\n"
                    ":end\n"
                )
            elif key == "clffcl_evapdio":
                text = (
                    "@echo off\n"
                    "REM ClFFCl evapDIO流程模板 (Batch)\n"
                    "REM 流程: 删除DIO添加剂 → 运行1ns NPT平衡 → 退火 → MD2\n"
                    "REM 使用文件: ydw-evapDIO.mdp, ydw-ta.mdp, ydw-md_02.mdp\n"
                    "REM 输入: ClFFCl_md.gro, ClFFCl_sa_current.top\n"
                    "set GMX=" + gmx_batch + "\n"
                    "cd /d %~dp0\n\n"
                    "set inputGro=ClFFCl_md.gro\n"
                    "set inputTop=ClFFCl_sa_current.top\n"
                    "set mdpFile=ydw-evapDIO.mdp\n"
                    "set prefix=ClFFCl_evapDIO\n\n"
                    "REM ==== Step 1: 删除DIO添加剂 ====\n"
                    "echo ==== 删除DIO添加剂 ====\n"
                    "set outGro=%prefix%_DA.gro\n"
                    "set outTop=%prefix%.top\n"
                    "python delete_additive_all.py --additive DIO --atoms-per-mol 6 --input %inputGro% --output %outGro% --topology %inputTop% --topology-output %outTop%\n"
                    "if errorlevel 1 goto error\n"
                    "echo DIO删除完成\n\n"
                    "REM ==== Step 2: 1ns NPT平衡 ====\n"
                    "echo ==== 运行1ns NPT平衡 ====\n"
                    "%GMX% grompp -f %mdpFile% -c %prefix%_DA.gro -p %prefix%.top -o %prefix%.tpr -maxwarn 200\n"
                    "if errorlevel 1 goto error\n"
                    "%GMX% mdrun -v -deffnm %prefix% -nt 6 -pin on -gpu_id 0 -nb gpu -pme gpu -bonded gpu -update gpu\n"
                    "if errorlevel 1 goto error\n"
                    "echo evapDIO NPT完成\n\n"
                    "REM ==== Step 3: 退火过程 ====\n"
                    "echo ==== 运行退火 ====\n"
                    "%GMX% grompp -f ydw-ta.mdp -c %prefix%.gro -p %prefix%.top -o %prefix%_anneal.tpr -maxwarn 200\n"
                    "if errorlevel 1 goto error\n"
                    "%GMX% mdrun -v -deffnm %prefix%_anneal -nt 6 -pin on -gpu_id 0 -nb gpu -pme gpu -bonded gpu -update gpu\n"
                    "if errorlevel 1 goto error\n"
                    "echo 退火完成\n\n"
                    "REM ==== Step 4: MD2 生产模拟 ====\n"
                    "echo ==== 运行MD2 ====\n"
                    "%GMX% grompp -f ydw-md_02.mdp -c %prefix%_anneal.gro -p %prefix%.top -o %prefix%_md2.tpr -maxwarn 200\n"
                    "if errorlevel 1 goto error\n"
                    "%GMX% mdrun -v -deffnm %prefix%_md2 -nt 6 -pin on -gpu_id 0 -nb gpu -pme gpu -bonded gpu -update gpu\n"
                    "if errorlevel 1 goto error\n"
                    "echo MD2完成\n\n"
                    "echo evapDIO流程完成!\n"
                    "goto end\n"
                    ":error\n"
                    "echo 执行失败!\n"
                    ":end\n"
                )
            elif key == "clffcl_md1":
                text = (
                    "@echo off\n"
                    "REM ClFFCl MD-1生产模拟流程模板 (Batch)\n"
                    "REM 流程: 基于ClFFCl_npt2.gro运行10ns生产模拟\n"
                    "REM 使用文件: ydw-md_01.mdp (10ns)\n"
                    "REM 输入: ClFFCl_npt2.gro, p4PM6-ClFFCl-mix.top\n"
                    "set GMX=" + gmx_batch + "\n"
                    "cd /d %~dp0\n\n"
                    "REM ==== Step 1: MD-1 生产模拟 (10ns) ====\n"
                    "echo ==== 运行 MD-1 (10ns) ====\n"
                    "%GMX% grompp -f ydw-md_01.mdp -c ClFFCl_npt2.gro -p p4PM6-ClFFCl-mix.top -o ClFFCl_md.tpr -maxwarn 200\n"
                    "if errorlevel 1 goto error\n"
                    "%GMX% mdrun -v -deffnm ClFFCl_md -nt 6 -pin on -gpu_id 0 -nb gpu -pme gpu -bonded gpu -update gpu\n"
                    "if errorlevel 1 goto error\n"
                    "echo MD-1 (10ns)完成\n\n"
                    "echo ClFFCl MD-1生产模拟完成!\n"
                    "goto end\n"
                    ":error\n"
                    "echo 执行失败!\n"
                    ":end\n"
                )
            elif key == "nvt":
                text = (
                    "@echo off\n"
                    "REM NVT恒温平衡脚本模板 (Batch)\n"
                    "set GMX=" + gmx_batch + "\n"
                    "cd /d %~dp0\n\n"
                    "REM NVT 恒温平衡\n"
                    "echo ==== 运行 NVT 恒温平衡 ====\n"
                    "%GMX% grompp -f nvt.mdp -c em.gro -r em.gro -p topol.top -o nvt.tpr -maxwarn 2\n"
                    "if errorlevel 1 goto error\n"
                    "%GMX% mdrun -deffnm nvt -v\n"
                    "if errorlevel 1 goto error\n"
                    "echo NVT恒温平衡完成!\n"
                    "goto end\n"
                    ":error\n"
                    "echo 执行失败!\n"
                    ":end\n"
                )
            elif key == "npt":
                text = (
                    "@echo off\n"
                    "REM NPT恒压平衡脚本模板 (Batch)\n"
                    "set GMX=" + gmx_batch + "\n"
                    "cd /d %~dp0\n\n"
                    "REM NPT 恒压平衡\n"
                    "echo ==== 运行 NPT 恒压平衡 ====\n"
                    "%GMX% grompp -f npt.mdp -c nvt.gro -r nvt.gro -p topol.top -o npt.tpr -maxwarn 2\n"
                    "if errorlevel 1 goto error\n"
                    "%GMX% mdrun -deffnm npt -v\n"
                    "if errorlevel 1 goto error\n"
                    "echo NPT恒压平衡完成!\n"
                    "goto end\n"
                    ":error\n"
                    "echo 执行失败!\n"
                    ":end\n"
                )
            elif key == "md":
                text = (
                    "@echo off\n"
                    "REM MD生产模拟脚本模板 (Batch)\n"
                    "set GMX=" + gmx_batch + "\n"
                    "cd /d %~dp0\n\n"
                    "REM MD 生产模拟\n"
                    "echo ==== 运行 MD 生产模拟 ====\n"
                    "%GMX% grompp -f md.mdp -c npt.gro -r npt.gro -p topol.top -o md.tpr -maxwarn 2\n"
                    "if errorlevel 1 goto error\n"
                    "%GMX% mdrun -deffnm md -v\n"
                    "if errorlevel 1 goto error\n"
                    "echo MD生产模拟完成!\n"
                    "goto end\n"
                    ":error\n"
                    "echo 执行失败!\n"
                    ":end\n"
                )
            elif key == "rdf":
                text = (
                    "@echo off\n"
                    "REM RDF径向分布函数分析脚本模板 (Batch)\n"
                    "set GMX=" + gmx_batch + "\n"
                    "cd /d %~dp0\n\n"
                    "REM 计算径向分布函数 (蛋白-溶剂)\n"
                    "echo 1 11 | %GMX% rdf -s md.tpr -f md.xtc -o rdf.xvg -ref 'Protein' -sel 'Water'\n\n"
                    "REM 计算配位数\n"
                    "echo 1 11 | %GMX% rdf -s md.tpr -f md.xtc -o rdf_coord.xvg -ref 'Protein' -sel 'Water' -cn\n\n"
                    "echo RDF分析完成!\n"
                )
            elif key == "hbond":
                text = (
                    "@echo off\n"
                    "REM 氢键分析脚本模板 (Batch)\n"
                    "set GMX=" + gmx_batch + "\n"
                    "cd /d %~dp0\n\n"
                    "REM 计算氢键 (蛋白-蛋白)\n"
                    "echo 1 1 | %GMX% hbond -s md.tpr -f md.xtc -num hbond.xvg\n\n"
                    "REM 计算氢键 (蛋白-溶剂)\n"
                    "echo 1 11 | %GMX% hbond -s md.tpr -f md.xtc -num hbond_solv.xvg\n\n"
                    "REM 氢键寿命分析\n"
                    "echo 1 1 | %GMX% hbond -s md.tpr -f md.xtc -ac hbond_analysis.xvg\n\n"
                    "echo 氢键分析完成!\n"
                )
            elif key == "sasa":
                text = (
                    "@echo off\n"
                    "REM SASA溶剂可及面积分析脚本模板 (Batch)\n"
                    "set GMX=" + gmx_batch + "\n"
                    "cd /d %~dp0\n\n"
                    "REM 计算整体SASA\n"
                    "echo 1 | %GMX% sasa -s md.tpr -f md.xtc -o sasa.xvg -surface 1 -output 1\n\n"
                    "REM 按残基计算SASA\n"
                    "echo 3 | %GMX% sasa -s md.tpr -f md.xtc -o sasa_res.xvg -surface 1 -output 2\n\n"
                    "REM 计算极性/非极性SASA\n"
                    "echo 1 | %GMX% sasa -s md.tpr -f md.xtc -o sasa_pol.xvg -surface 2 -output 1\n\n"
                    "echo SASA分析完成!\n"
                )
            elif key == "pca":
                text = (
                    "@echo off\n"
                    "REM PCA主成分分析脚本模板 (Batch)\n"
                    "REM 注意：需要先做轨迹拟合\n"
                    "set GMX=" + gmx_batch + "\n"
                    "cd /d %~dp0\n\n"
                    "REM 步骤1: 轨迹拟合 (去除平动转动)\n"
                    "echo ==== 轨迹拟合 ====\n"
                    "echo 4 | %GMX% trjconv -s md.tpr -f md.xtc -o md_fit.xtc -fit rot+trans\n\n"
                    "REM 步骤2: 计算协方差矩阵\n"
                    "echo ==== 计算协方差矩阵 ====\n"
                    "echo 4 | %GMX% covar -s md.tpr -f md_fit.xtc -o eigenvectors.trr -xpm covar.xpm\n\n"
                    "REM 步骤3: 对角化协方差矩阵\n"
                    "echo ==== 对角化协方差矩阵 ====\n"
                    "%GMX% anaeig -s md.tpr -f eigenvectors.trr -o eigenvalues.xvg -v eigenvectors.trr -n 10\n\n"
                    "REM 步骤4: 投影到主成分\n"
                    "echo ==== 投影到主成分 ====\n"
                    "echo 4 | %GMX% anaeig -s md.tpr -f md_fit.xtc -proj pcaprojection.xvg\n\n"
                    "echo PCA分析完成!\n"
                )
            else:
                text = ""
        
        elif "Shell" in script_type:
            if key == "em":
                text = "# 能量最小化脚本模板 (Shell命令)\n"
                text += "# 一行一条命令，依次执行\n\n"
                text += "# 1. 生成拓扑 (如果已有topol.top可跳过)\n"
                text += "# " + gmx_norm + " pdb2gmx -f protein.pdb -o protein.gro -p topol.top -ff amber99sb-ildn -water tip3p -ignh\n\n"
                text += "# 2. 构建盒子\n"
                text += gmx_norm + " editconf -f protein.gro -o protein_box.gro -c -d 1.0 -bt cubic\n\n"
                text += "# 3. 溶剂化\n"
                text += gmx_norm + " solvate -cp protein_box.gro -o protein_solv.gro -p topol.top\n\n"
                text += "# 4. 能量最小化\n"
                text += gmx_norm + " grompp -f em.mdp -c protein_solv.gro -p topol.top -o em.tpr -maxwarn 2\n"
                text += gmx_norm + " mdrun -deffnm em -v\n"
            elif key == "full_md":
                text = "# 完整MD流程脚本模板 (Shell命令)\n"
                text += "# 一行一条命令，依次执行\n\n"
                text += "# EM 能量最小化\n"
                text += gmx_norm + " grompp -f em.mdp -c protein_solv.gro -r protein_solv.gro -p topol.top -o em.tpr -maxwarn 2\n"
                text += gmx_norm + " mdrun -deffnm em -v\n\n"
                text += "# NVT 恒温平衡\n"
                text += gmx_norm + " grompp -f nvt.mdp -c em.gro -r em.gro -p topol.top -o nvt.tpr -maxwarn 2\n"
                text += gmx_norm + " mdrun -deffnm nvt -v\n\n"
                text += "# NPT 恒压平衡\n"
                text += gmx_norm + " grompp -f npt.mdp -c nvt.gro -r nvt.gro -p topol.top -o npt.tpr -maxwarn 2\n"
                text += gmx_norm + " mdrun -deffnm npt -v\n\n"
                text += "# MD 生产模拟\n"
                text += gmx_norm + " grompp -f md.mdp -c npt.gro -r npt.gro -p topol.top -o md.tpr -maxwarn 2\n"
                text += gmx_norm + " mdrun -deffnm md -v\n"
            elif key == "clffcl_em_npt":
                text = "# ClFFCl EM+NPT流程模板 (Shell命令)\n"
                text += "# 流程: EM-1 → EM-2 → NPT-1 → NPT-2\n"
                text += "# 使用文件: ydw-em_01.mdp (steep), ydw-em_02.mdp (cg), ydw-npt_01.mdp (1ns), ydw-npt_02.mdp (2ns)\n"
                text += "# 输入: ydw-PM6-ClFFCl.pdb, p4PM6-ClFFCl-mix.top\n\n"
                text += "# ==== Step 1: 能量最小化 EM-1 (steep) ====\n"
                text += gmx_norm + " grompp -f ydw-em_01.mdp -c ydw-PM6-ClFFCl.pdb -p p4PM6-ClFFCl-mix.top -o ClFFCl_em1.tpr -maxwarn 200\n"
                text += gmx_norm + " mdrun -v -deffnm ClFFCl_em1 -nt 6 -pin on -nb gpu -pme cpu\n\n"

                text += "# ==== Step 2: 能量最小化 EM-2 (cg) ====\n"
                text += gmx_norm + " grompp -f ydw-em_02.mdp -c ClFFCl_em1.gro -p p4PM6-ClFFCl-mix.top -o ClFFCl_em2.tpr -maxwarn 200\n"
                text += gmx_norm + " mdrun -v -deffnm ClFFCl_em2 -nt 6 -pin on -nb gpu -pme cpu\n\n"

                text += "# ==== Step 3: NPT 平衡 1 (1ns) ====\n"
                text += gmx_norm + " grompp -f ydw-npt_01.mdp -c ClFFCl_em2.gro -p p4PM6-ClFFCl-mix.top -o ClFFCl_npt1.tpr -maxwarn 200\n"
                text += gmx_norm + " mdrun -v -deffnm ClFFCl_npt1 -nt 6 -pin on -gpu_id 0 -nb gpu -pme gpu -bonded gpu -update gpu\n\n"
                text += "# ==== Step 4: NPT 平衡 2 (2ns) ====\n"
                text += gmx_norm + " grompp -f ydw-npt_02.mdp -c ClFFCl_npt1.gro -p p4PM6-ClFFCl-mix.top -o ClFFCl_npt2.tpr -maxwarn 200\n"
                text += gmx_norm + " mdrun -v -deffnm ClFFCl_npt2 -nt 6 -pin on -gpu_id 0 -nb gpu -pme gpu -bonded gpu -update gpu\n\n"
                text += "echo '所有步骤完成!'\n"
            elif key == "clffcl_sa":
                text = "# ClFFCl SA溶剂蒸发流程模板 (Shell命令)\n"
                text += "# 流程: 逐步删除CF溶剂分子，每轮运行10ps NPT\n"
                text += "# 使用文件: ydw-npt-sa.mdp\n"
                text += "# 输入: ClFFCl_npt2.gro, p4PM6-ClFFCl-mix.top\n\n"
                text += "inputGro=\"ClFFCl_npt2.gro\"\n"
                text += "topFile=\"p4PM6-ClFFCl-mix.top\"\n"
                text += "mdpFile=\"ydw-npt-sa.mdp\"\n"
                text += "prefix=\"ClFFCl_sa\"\n"
                text += "loops=500\n"
                text += "deleteNum=100\n"
                text += "atomsPerSolvent=5\n"
                text += "# 备份原始文件\n"
                text += "cp \"$inputGro\" \"${prefix}_original.gro\"\n"
                text += "cp \"$topFile\" \"${prefix}_original.top\"\n"
                text += "echo \"已备份原始文件\"\n\n"
                text += "workGro=\"${prefix}_work.gro\"\n"
                text += "workTop=\"${prefix}_work.top\"\n"
                text += "currentGro=\"${prefix}_current.gro\"\n"
                text += "currentTop=\"${prefix}_current.top\"\n"
                text += "cp \"$inputGro\" \"$workGro\"\n"
                text += "cp \"$topFile\" \"$workTop\"\n\n"
                text += "for ((i=1; i<=loops; i++)); do\n"
                text += "  echo \"==== SA 第 $i/$loops 轮 ====\"\n"
                text += "  newGro=\"${prefix}_new.gro\"\n"
                text += "  newTop=\"${prefix}_new.top\"\n"
                text += "  echo \"删除 $deleteNum 个CF溶剂分子...\"\n"
                text += "  python delete_solvent.py --solvent CF --delete-num \"$deleteNum\" --atoms-per-mol \"$atomsPerSolvent\" --loop \"$i\" --input \"$workGro\" --output \"$newGro\" --topology \"$workTop\" --topology-output \"$newTop\"\n"
                text += "  if [ $? -ne 0 ]; then echo \"删除溶剂失败\"; exit 1; fi\n"
                text += "  mv \"$newGro\" \"$workGro\"\n"
                text += "  mv \"$newTop\" \"$workTop\"\n"
                text += "  echo \"grompp...\"\n"
                text += "  " + gmx_norm + " grompp -f \"$mdpFile\" -c \"$workGro\" -p \"$workTop\" -o \"${prefix}_$i.tpr\" -maxwarn 200\n"
                text += "  if [ $? -ne 0 ]; then echo \"grompp失败\"; exit 1; fi\n"
                text += "  echo \"mdrun (10ps)...\"\n"
                text += "  " + gmx_norm + " mdrun -v -deffnm \"${prefix}_$i\" -nt 6 -pin on -gpu_id 0 -nb gpu -pme gpu -bonded gpu -update gpu\n"
                text += "  if [ $? -ne 0 ]; then echo \"mdrun失败\"; exit 1; fi\n"
                text += "  cp \"${prefix}_$i.gro\" \"$currentGro\"\n"
                text += "  cp \"$workTop\" \"$currentTop\"\n"
                text += "  echo \"第 $i 轮完成\"\n"
                text += "done\n\n"
                text += "echo 'SA溶剂蒸发完成!'\n"
                text += "echo \"最终结构: $currentGro\"\n"
                text += "echo \"最终拓扑: $currentTop\"\n"
            elif key == "clffcl_evapdio":
                text = "# ClFFCl evapDIO流程模板 (Shell命令)\n"
                text += "# 流程: 删除DIO添加剂 → 运行1ns NPT平衡 → 退火 → MD2\n"
                text += "# 使用文件: ydw-evapDIO.mdp, ydw-ta.mdp, ydw-md_02.mdp\n"
                text += "# 输入: ClFFCl_md.gro, ClFFCl_sa_current.top\n\n"
                text += "inputGro=\"ClFFCl_md.gro\"\n"
                text += "inputTop=\"ClFFCl_sa_current.top\"\n"
                text += "mdpFile=\"ydw-evapDIO.mdp\"\n"
                text += "prefix=\"ClFFCl_evapDIO\"\n\n"
                text += "# ==== Step 1: 删除DIO添加剂 ====\n"
                text += "echo \"==== 删除DIO添加剂 ====\"\n"
                text += "outGro=\"${prefix}_DA.gro\"\n"
                text += "outTop=\"${prefix}.top\"\n"
                text += "python delete_additive_all.py --additive DIO --atoms-per-mol 6 --input \"$inputGro\" --output \"$outGro\" --topology \"$inputTop\" --topology-output \"$outTop\"\n"
                text += "echo 'DIO删除完成'\n\n"
                text += "# ==== Step 2: 1ns NPT平衡 ====\n"
                text += "echo \"==== 运行1ns NPT平衡 ====\"\n"
                text += gmx_norm + " grompp -f \"$mdpFile\" -c \"${prefix}_DA.gro\" -p \"${prefix}.top\" -o \"${prefix}.tpr\" -maxwarn 200\n"
                text += gmx_norm + " mdrun -v -deffnm \"$prefix\" -nt 6 -pin on -gpu_id 0 -nb gpu -pme gpu -bonded gpu -update gpu\n"
                text += "echo 'evapDIO NPT完成'\n\n"
                text += "# ==== Step 3: 退火过程 ====\n"
                text += "echo \"==== 运行退火 ====\"\n"
                text += gmx_norm + " grompp -f ydw-ta.mdp -c \"${prefix}.gro\" -p \"${prefix}.top\" -o \"${prefix}_anneal.tpr\" -maxwarn 200\n"
                text += gmx_norm + " mdrun -v -deffnm \"${prefix}_anneal\" -nt 6 -pin on -gpu_id 0 -nb gpu -pme gpu -bonded gpu -update gpu\n"
                text += "echo '退火完成'\n\n"
                text += "# ==== Step 4: MD2 生产模拟 ====\n"
                text += "echo \"==== 运行MD2 ====\"\n"
                text += gmx_norm + " grompp -f ydw-md_02.mdp -c \"${prefix}_anneal.gro\" -p \"${prefix}.top\" -o \"${prefix}_md2.tpr\" -maxwarn 200\n"
                text += gmx_norm + " mdrun -v -deffnm \"${prefix}_md2\" -nt 6 -pin on -gpu_id 0 -nb gpu -pme gpu -bonded gpu -update gpu\n"
                text += "echo 'MD2完成'\n\n"
                text += "echo 'evapDIO+退火+MD2流程全部完成!'\n"
            elif key == "rmsd":
                text = "# RMSD分析脚本模板 (Shell命令)\n"
                text += "# 一行一条命令，依次执行\n\n"
                text += "# 先做轨迹拟合 (去除平动转动)\n"
                text += "echo 4 | " + gmx_norm + " trjconv -s md.tpr -f md.xtc -o md_fit.xtc -fit rot+trans\n\n"
                text += "# 计算RMSD (骨架原子)\n"
                text += "echo 4 4 | " + gmx_norm + " rms -s md.tpr -f md_fit.xtc -o rmsd.xvg -tu ns\n\n"
                text += "# 计算RMSF\n"
                text += "echo 3 | " + gmx_norm + " rmsf -s md.tpr -f md_fit.xtc -o rmsf.xvg -res\n"
            elif key == "clffcl_md1":
                text = "# ClFFCl MD-1生产模拟流程模板 (Shell命令)\n"
                text += "# 流程: 基于ClFFCl_npt2.gro运行10ns生产模拟\n"
                text += "# 使用文件: ydw-md_01.mdp (10ns)\n"
                text += "# 输入: ClFFCl_npt2.gro, p4PM6-ClFFCl-mix.top\n\n"
                text += "# ==== Step 1: MD-1 生产模拟 (10ns) ====\n"
                text += "echo \"==== 运行 MD-1 (10ns) ====\"\n"
                text += gmx_norm + " grompp -f ydw-md_01.mdp -c ClFFCl_npt2.gro -p p4PM6-ClFFCl-mix.top -o ClFFCl_md.tpr -maxwarn 200\n"
                text += gmx_norm + " mdrun -v -deffnm ClFFCl_md -nt 6 -pin on -gpu_id 0 -nb gpu -pme gpu -bonded gpu -update gpu\n"
                text += "echo 'MD-1 (10ns)完成'\n\n"
                text += "echo 'ClFFCl MD-1生产模拟完成!'\n"
            elif key == "nvt":
                text = "# NVT恒温平衡脚本模板 (Shell命令)\n"
                text += "# 一行一条命令，依次执行\n\n"
                text += "# NVT 恒温平衡\n"
                text += "echo \"==== 运行 NVT 恒温平衡 ====\"\n"
                text += gmx_norm + " grompp -f nvt.mdp -c em.gro -r em.gro -p topol.top -o nvt.tpr -maxwarn 2\n"
                text += gmx_norm + " mdrun -deffnm nvt -v\n"
                text += "echo 'NVT恒温平衡完成!'\n"
            elif key == "npt":
                text = "# NPT恒压平衡脚本模板 (Shell命令)\n"
                text += "# 一行一条命令，依次执行\n\n"
                text += "# NPT 恒压平衡\n"
                text += "echo \"==== 运行 NPT 恒压平衡 ====\"\n"
                text += gmx_norm + " grompp -f npt.mdp -c nvt.gro -r nvt.gro -p topol.top -o npt.tpr -maxwarn 2\n"
                text += gmx_norm + " mdrun -deffnm npt -v\n"
                text += "echo 'NPT恒压平衡完成!'\n"
            elif key == "md":
                text = "# MD生产模拟脚本模板 (Shell命令)\n"
                text += "# 一行一条命令，依次执行\n\n"
                text += "# MD 生产模拟\n"
                text += "echo \"==== 运行 MD 生产模拟 ====\"\n"
                text += gmx_norm + " grompp -f md.mdp -c npt.gro -r npt.gro -p topol.top -o md.tpr -maxwarn 2\n"
                text += gmx_norm + " mdrun -deffnm md -v\n"
                text += "echo 'MD生产模拟完成!'\n"
            elif key == "rdf":
                text = "# RDF径向分布函数分析脚本模板 (Shell命令)\n"
                text += "# 一行一条命令，依次执行\n\n"
                text += "# 计算径向分布函数 (蛋白-溶剂)\n"
                text += "echo 1 11 | " + gmx_norm + " rdf -s md.tpr -f md.xtc -o rdf.xvg -ref 'Protein' -sel 'Water'\n\n"
                text += "# 计算配位数\n"
                text += "echo 1 11 | " + gmx_norm + " rdf -s md.tpr -f md.xtc -o rdf_coord.xvg -ref 'Protein' -sel 'Water' -cn\n\n"
                text += "echo 'RDF分析完成!'\n"
            elif key == "hbond":
                text = "# 氢键分析脚本模板 (Shell命令)\n"
                text += "# 一行一条命令，依次执行\n\n"
                text += "# 计算氢键 (蛋白-蛋白)\n"
                text += "echo 1 1 | " + gmx_norm + " hbond -s md.tpr -f md.xtc -num hbond.xvg\n\n"
                text += "# 计算氢键 (蛋白-溶剂)\n"
                text += "echo 1 11 | " + gmx_norm + " hbond -s md.tpr -f md.xtc -num hbond_solv.xvg\n\n"
                text += "# 氢键寿命分析\n"
                text += "echo 1 1 | " + gmx_norm + " hbond -s md.tpr -f md.xtc -ac hbond_analysis.xvg\n\n"
                text += "echo '氢键分析完成!'\n"
            elif key == "sasa":
                text = "# SASA溶剂可及面积分析脚本模板 (Shell命令)\n"
                text += "# 一行一条命令，依次执行\n\n"
                text += "# 计算整体SASA\n"
                text += "echo 1 | " + gmx_norm + " sasa -s md.tpr -f md.xtc -o sasa.xvg -surface 1 -output 1\n\n"
                text += "# 按残基计算SASA\n"
                text += "echo 3 | " + gmx_norm + " sasa -s md.tpr -f md.xtc -o sasa_res.xvg -surface 1 -output 2\n\n"
                text += "# 计算极性/非极性SASA\n"
                text += "echo 1 | " + gmx_norm + " sasa -s md.tpr -f md.xtc -o sasa_pol.xvg -surface 2 -output 1\n\n"
                text += "echo 'SASA分析完成!'\n"
            elif key == "pca":
                text = "# PCA主成分分析脚本模板 (Shell命令)\n"
                text += "# 注意：需要先做轨迹拟合\n\n"
                text += "# 步骤1: 轨迹拟合 (去除平动转动)\n"
                text += "echo \"==== 轨迹拟合 ====\"\n"
                text += "echo 4 | " + gmx_norm + " trjconv -s md.tpr -f md.xtc -o md_fit.xtc -fit rot+trans\n\n"
                text += "# 步骤2: 计算协方差矩阵\n"
                text += "echo \"==== 计算协方差矩阵 ====\"\n"
                text += "echo 4 | " + gmx_norm + " covar -s md.tpr -f md_fit.xtc -o eigenvectors.trr -xpm covar.xpm\n\n"
                text += "# 步骤3: 对角化协方差矩阵\n"
                text += "echo \"==== 对角化协方差矩阵 ====\"\n"
                text += gmx_norm + " anaeig -s md.tpr -f eigenvectors.trr -o eigenvalues.xvg -v eigenvectors.trr -n 10\n\n"
                text += "# 步骤4: 投影到主成分\n"
                text += "echo \"==== 投影到主成分 ====\"\n"
                text += "echo 4 | " + gmx_norm + " anaeig -s md.tpr -f md_fit.xtc -proj pcaprojection.xvg\n\n"
                text += "# 步骤5: 生成PC1和PC2的结构\n"
                text += "echo \"==== 生成主成分结构 ====\"\n"
                text += "echo 4 | " + gmx_norm + " anaeig -s md.tpr -f md_fit.xtc -first 1 -last 2 -o pca_pc1_pc2.trr\n\n"
                text += "echo 'PCA分析完成!'\n"
            else:
                text = ""
        
        else:
            text = ""
        
        self.script_edit.setPlainText(text)

    def _save_script(self):
        wd = self._get_work_dir() or os.getcwd()
        fname, _ = QFileDialog.getSaveFileName(self, "保存脚本", wd, "脚本文件 (*.ps1 *.bat *.txt);;所有文件 (*.*)")
        if fname:
            with open(fname, "w", encoding="utf-8") as f:
                f.write(self.script_edit.toPlainText())
            self.add_log(f"脚本已保存到: {fname}", "success")

    def _load_script(self):
        wd = self._get_work_dir() or os.getcwd()
        fname, _ = QFileDialog.getOpenFileName(self, "加载脚本", wd, "脚本文件 (*.ps1 *.bat *.txt);;所有文件 (*.*)")
        if fname:
            with open(fname, "r", encoding="utf-8", errors="ignore") as f:
                self.script_edit.setPlainText(f.read())
            self.add_log(f"脚本已加载: {fname}", "info")

    def run_script(self):
        wd = self._get_work_dir()
        if not wd:
            return

        script_text = self.script_edit.toPlainText().strip()
        if not script_text:
            self.add_log("脚本内容为空，请先输入或加载脚本。", "error")
            return

        script_type = self.script_type.currentText()
        step_name = "自定义脚本"
        self.add_log("=" * 60, "cmd")
        self.add_log(f"运行 {script_type}", "cmd")
        self.add_log("=" * 60, "cmd")

        # 创建临时脚本文件
        tmp_dir = wd
        if "PowerShell" in script_type:
            script_file = os.path.join(tmp_dir, "_gmx_gui_script.ps1")
            with open(script_file, "w", encoding="utf-8") as f:
                f.write(script_text)
            cmd = [["powershell", "-ExecutionPolicy", "Bypass", "-File", script_file]]
        elif "Batch" in script_type:
            script_file = os.path.join(tmp_dir, "_gmx_gui_script.bat")
            with open(script_file, "w", encoding="utf-8") as f:
                f.write(f"@echo off\ncd /d \"{wd}\"\nset GMX={self.gmx_path}\n\n{script_text}")
            cmd = [script_file]
        else:
            # 直接作为命令行命令执行
            script_file = None
            cmd = [["cmd", "/c", script_text]]

        self.run_command(cmd, wd, step_name)
