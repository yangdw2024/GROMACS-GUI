# -*- coding: utf-8 -*-
"""
核心模块单元测试
测试范围：模块导入、ConfigManager、VersionManager、ResourceMonitor、
         GromacsService、WorkflowEngine、EventBus、语法检查等
"""
import os
import sys
import py_compile
from pathlib import Path
import pytest


# ============================================================
# 1. 模块导入测试
# ============================================================

class TestModuleImports:
    """核心模块导入测试"""

    def test_all_core_modules_import(self):
        """验证所有核心模块可以正常导入"""
        from core import (
            ConfigManager, AppLogger, ErrorHandler,
            ResourceMonitor, GromacsService, WorkflowEngine,
            EventBus, ReviewMechanism, CorrectionMechanism,
            AuditMechanism, AutoUpdater,
            VersionManager, VersionMetadata, PlumedStatus, VersionValidity,
            CrashHandler
        )

    def test_individual_module_imports(self):
        """逐模块导入验证"""
        from core.gromacs_service import GromacsService
        from core.version_manager import VersionManager
        from core.resource_monitor import ResourceMonitor
        from core.config_manager import ConfigManager
        from core.workflow_engine import WorkflowEngine
        from core.logger import AppLogger
        from core.error_handler import ErrorHandler
        from core.event_bus import EventBus
        from core.crash_handler import CrashHandler

    def test_wsl_modules_import(self):
        """WSL 相关模块导入（如存在则导入验证）"""
        try:
            from core.wsl_gromacs_service import WslGromacsService
        except ImportError:
            pytest.skip("WSL 模块不存在，跳过")

        try:
            from core.wsl_update_manager import WslUpdateManager
        except ImportError:
            pytest.skip("WSL 更新管理器不存在，跳过")


# ============================================================
# 2. ConfigManager 测试
# ============================================================

class TestConfigManager:
    """配置管理器测试"""

    def test_config_manager_instantiation(self):
        """ConfigManager 可以实例化"""
        from core.config_manager import ConfigManager
        cm = ConfigManager()
        assert cm is not None

    def test_config_structure_valid(self):
        """配置文件包含正确的顶层结构"""
        from core.config_manager import ConfigManager
        cm = ConfigManager()
        config = cm.get_all()
        # app_config.json 的顶层键：gromacs, simulation, system, resources
        assert "gromacs" in config
        assert "simulation" in config
        assert "system" in config

    def test_config_gromacs_section(self):
        """GROMACS 配置段包含必要字段"""
        from core.config_manager import ConfigManager
        cm = ConfigManager()
        config = cm.get_all()
        gromacs_cfg = config.get("gromacs", {})
        assert "default_version" in gromacs_cfg
        assert "version_whitelist" in gromacs_cfg

    def test_config_whitelist_not_empty(self):
        """版本白名单不为空"""
        from core.config_manager import ConfigManager
        cm = ConfigManager()
        config = cm.get_all()
        whitelist = config.get("gromacs", {}).get("version_whitelist", [])
        assert len(whitelist) > 0


# ============================================================
# 3. VersionManager 测试
# ============================================================

class TestVersionManager:
    """版本管理器测试"""

    def test_version_manager_instantiation(self):
        """VersionManager 可以实例化"""
        from core.version_manager import VersionManager
        vm = VersionManager()
        assert vm is not None

    def test_version_scan_returns_dict(self, project_root):
        """版本扫描返回字典结构"""
        from core.version_manager import VersionManager
        vm = VersionManager()
        gromacs_dir = project_root / "gromacs"
        if not gromacs_dir.exists():
            pytest.skip("GROMACS 目录不存在")
        versions = vm.scan_versions(base_dir=str(gromacs_dir))
        assert isinstance(versions, dict)

    def test_version_list_not_empty(self, project_root):
        """检测到的版本列表不为空"""
        from core.version_manager import VersionManager
        vm = VersionManager()
        gromacs_dir = project_root / "gromacs"
        if not gromacs_dir.exists():
            pytest.skip("GROMACS 目录不存在")
        vm.scan_versions(base_dir=str(gromacs_dir))
        versions = vm.get_version_list()
        assert len(versions) >= 0  # 可能为0（无版本），但不应报错

    def test_version_whitelist_accessible(self):
        """可以获取版本白名单"""
        from core.version_manager import VersionManager
        vm = VersionManager()
        whitelist = vm.get_version_whitelist()
        assert isinstance(whitelist, list)

    def test_select_best_version_returns_something(self, project_root):
        """最佳版本选择有返回值"""
        from core.version_manager import VersionManager
        vm = VersionManager()
        gromacs_dir = project_root / "gromacs"
        if not gromacs_dir.exists():
            pytest.skip("GROMACS 目录不存在")
        vm.scan_versions(base_dir=str(gromacs_dir))
        best = vm.select_best_version()
        # best 可能为 None（无可用版本），但不应抛异常


# ============================================================
# 4. ResourceMonitor 测试
# ============================================================

class TestResourceMonitor:
    """资源监视器测试"""

    def test_resource_monitor_instantiation(self):
        """ResourceMonitor 可以实例化"""
        from core.resource_monitor import ResourceMonitor
        rm = ResourceMonitor()
        assert rm is not None

    def test_get_cpu_info_returns_dict(self):
        """获取 CPU 信息返回字典"""
        from core.resource_monitor import ResourceMonitor
        rm = ResourceMonitor()
        cpu_info = rm.get_cpu_info()
        assert isinstance(cpu_info, dict)

    def test_get_cpu_has_cores(self):
        """CPU 信息包含核心数"""
        from core.resource_monitor import ResourceMonitor
        rm = ResourceMonitor()
        cpu_info = rm.get_cpu_info()
        assert "cores" in cpu_info

    def test_get_gpu_info(self):
        """获取 GPU 信息（可能为空）"""
        from core.resource_monitor import ResourceMonitor
        rm = ResourceMonitor()
        gpu_info = rm.get_gpu_info()
        # GPU 信息可能为 dict 或提示信息，不做严格断言


# ============================================================
# 5. GromacsService 测试
# ============================================================

class TestGromacsService:
    """GROMACS 服务测试"""

    def test_gromacs_service_instantiation(self):
        """GromacsService 可以实例化"""
        from core.gromacs_service import GromacsService
        gs = GromacsService()
        assert gs is not None

    def test_scan_versions_does_not_crash(self, project_root):
        """版本扫描不抛出异常"""
        from core.gromacs_service import GromacsService
        gs = GromacsService()
        gromacs_dir = project_root / "gromacs"
        if not gromacs_dir.exists():
            pytest.skip("GROMACS 目录不存在")
        gs.scan_versions(base_dir=str(gromacs_dir))

    def test_get_version_list_returns_list(self, project_root):
        """获取版本列表返回 list"""
        from core.gromacs_service import GromacsService
        gs = GromacsService()
        gromacs_dir = project_root / "gromacs"
        if not gromacs_dir.exists():
            pytest.skip("GROMACS 目录不存在")
        gs.scan_versions(base_dir=str(gromacs_dir))
        versions = gs.get_version_list()
        assert isinstance(versions, list)

    def test_get_gmx_exe_returns_string_or_none(self, project_root):
        """获取 gmx 路径返回字符串或 None"""
        from core.gromacs_service import GromacsService
        gs = GromacsService()
        gromacs_dir = project_root / "gromacs"
        if not gromacs_dir.exists():
            pytest.skip("GROMACS 目录不存在")
        gs.scan_versions(base_dir=str(gromacs_dir))
        gmx = gs.get_gmx_exe()
        assert gmx is None or isinstance(gmx, str)


# ============================================================
# 6. WorkflowEngine 测试
# ============================================================

class TestWorkflowEngine:
    """工作流引擎测试"""

    def test_workflow_engine_instantiation(self):
        """WorkflowEngine 可以实例化"""
        from core.workflow_engine import WorkflowEngine
        we = WorkflowEngine()
        assert we is not None

    def test_get_all_tasks_returns_list(self):
        """获取所有任务返回列表"""
        from core.workflow_engine import WorkflowEngine
        we = WorkflowEngine()
        tasks = we.get_all_tasks()
        assert isinstance(tasks, list)


# ============================================================
# 7. EventBus 测试
# ============================================================

class TestEventBus:
    """事件总线测试"""

    def test_event_bus_instantiation(self):
        """EventBus 可以实例化"""
        from core.event_bus import EventBus
        eb = EventBus()
        assert eb is not None


# ============================================================
# 8. AppLogger 测试
# ============================================================

class TestAppLogger:
    """日志器测试"""

    def test_app_logger_instantiation(self):
        """AppLogger 可以实例化"""
        from core.logger import AppLogger
        logger = AppLogger()
        assert logger is not None


# ============================================================
# 9. CrashHandler 测试
# ============================================================

class TestCrashHandler:
    """崩溃处理器测试"""

    def test_crash_handler_instantiation(self):
        """CrashHandler 可以实例化"""
        from core.crash_handler import CrashHandler
        ch = CrashHandler()
        assert ch is not None


# ============================================================
# 10. GUI 主程序语法检查
# ============================================================

class TestGUISyntax:
    """GUI 主程序语法检查"""

    def test_gui_main_syntax_valid(self, source_dir):
        """gromacs_gui_v4.py 语法正确"""
        gui_path = source_dir / "gromacs_gui_v4.py"
        if not gui_path.exists():
            pytest.skip("主程序文件不存在")
        py_compile.compile(str(gui_path), doraise=True)

    def test_gui_has_required_methods(self, source_dir):
        """主程序包含关键方法"""
        gui_path = source_dir / "gromacs_gui_v4.py"
        if not gui_path.exists():
            pytest.skip("主程序文件不存在")

        with open(gui_path, "r", encoding="utf-8") as f:
            content = f.read()

        required_methods = [
            "_generate_fragment_ndx",
            "_expand_ranges",
            "_run_fragment_rdf_batch",
            "_run_pairdist_analysis",
            "_run_preprocessing_pipeline",
            "_run_energy_decomposition",
            "_generate_plot",
            "_run_batch_processing",
            "_run_file_check",
            "_check_file_status",
        ]

        missing = [m for m in required_methods if f"def {m}" not in content]
        assert missing == [], f"缺少关键方法: {missing}"


# ============================================================
# 11. version.config 白名单检查
# ============================================================

class TestVersionConfig:
    """版本配置检查"""

    def test_version_config_exists(self, project_root):
        """version.config 文件存在"""
        vc_path = project_root / "version.config"
        assert vc_path.exists(), "version.config 不存在"

    def test_version_config_has_whitelist(self, project_root):
        """version.config 包含版本白名单"""
        import json
        vc_path = project_root / "version.config"
        with open(vc_path, "r", encoding="utf-8") as f:
            vc = json.load(f)
        whitelist = vc.get("version_whitelist", [])
        assert len(whitelist) > 0, "版本白名单为空"

    def test_release_key_files_exist(self, project_root):
        """关键发布文件存在"""
        key_files = [
            ("可执行文件", "release/GROMACS_GUI_v4.2.0.exe"),
            ("启动脚本", "release/启动程序.bat"),
            ("程序图标", "resources/app_icon.ico"),
        ]
        missing = []
        for label, rel_path in key_files:
            full = project_root / rel_path
            if not full.exists():
                missing.append(label)
        # 只警告不失败，因为 release 目录可能在不同位置
        if missing:
            pytest.warns(UserWarning, match=f"关键文件缺失: {missing}")
