#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WSL GROMACS 更新与状态管理器
负责：
  1. WSL GROMACS 版本检测
  2. 启动脚本/环境脚本更新记录
  3. 环境健康检查
  4. 生成状态报告
"""

import os
import sys
import json
import time
import hashlib
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum

from .error_handler import ErrorHandler, GromacsError, ErrorCategory, ErrorSeverity
from .logger import AppLogger
from .audit_mechanism import AuditMechanism


class WslHealthStatus(Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass
class WslVersionStatus:
    current_version: str = ""
    install_path: str = ""
    cuda_version: str = ""
    supported_arch: List[str] = None
    plumed: bool = False
    simd: str = ""
    gpu: str = ""
    last_check: str = ""

    def __post_init__(self):
        if self.supported_arch is None:
            self.supported_arch = []

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class WslHealthReport:
    status: str = "unknown"
    wsl_available: bool = False
    distro_available: bool = False
    gromacs_installed: bool = False
    cuda_available: bool = False
    gpu_available: bool = False
    path_fixed: bool = False
    errors: List[str] = None
    warnings: List[str] = None
    timestamp: str = ""

    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []

    def to_dict(self) -> Dict:
        return asdict(self)


class WslUpdateManager:
    _instance = None
    _lock = None

    WSL_DISTRO = "Ubuntu"
    GROMACS_ROOT = "/mnt/d/YDW/WSL_Gromacs/install/gromacs-2026.3-AVX512-CUDA"
    ENV_SCRIPT = "/mnt/d/YDW/WSL_Gromacs/setup_gromacs_env.sh"
    LAUNCH_SCRIPT = "/mnt/d/YDW/WSL_Gromacs/launch_gromacs_wsl.sh"
    BAT_FILE = "D:\\YDW\\WSL_Gromacs\\启动WSL_GROMACS.bat"

    def __new__(cls):
        if cls._lock is None:
            cls._lock = __import__('threading').Lock()
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._logger = AppLogger()
        self._error_handler = ErrorHandler()
        self._audit = AuditMechanism()
        self._version_status: Optional[WslVersionStatus] = None
        self._health_report: Optional[WslHealthReport] = None

        self._initialized = True

    def _run_wsl(self, cmd: str, timeout: int = 30) -> Tuple[int, str, str]:
        full_cmd = ["wsl", "-d", self.WSL_DISTRO, "-e", "bash", "-c", cmd]
        try:
            startupinfo = None
            if sys.platform.startswith("win"):
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            result = subprocess.run(
                full_cmd,
                capture_output=True, text=True, timeout=timeout,
                startupinfo=startupinfo
            )
            return result.returncode, result.stdout, result.stderr
        except Exception as e:
            return -1, "", str(e)

    def check_wsl_available(self) -> bool:
        """检测WSL及Ubuntu发行版是否可用（通过实际执行命令验证）"""
        try:
            result = subprocess.run(
                ["wsl", "-d", self.WSL_DISTRO, "-e", "bash", "-c", "echo WSL_OK"],
                capture_output=True, text=True, timeout=10
            )
            return result.returncode == 0 and "wsl_ok" in result.stdout.lower()
        except Exception:
            return False

    def check_gromacs_installed(self) -> bool:
        rc, _, _ = self._run_wsl("test -x /mnt/d/YDW/WSL_Gromacs/install/gromacs-2026.3-AVX512-CUDA/bin/gmx", timeout=10)
        return rc == 0

    def check_cuda_available(self) -> bool:
        rc, _, _ = self._run_wsl("nvcc --version", timeout=10)
        return rc == 0

    def check_gpu_available(self) -> bool:
        rc, out, _ = self._run_wsl(
            "source /mnt/d/YDW/WSL_Gromacs/setup_gromacs_env.sh && gmx --version | grep -i 'gpu support'",
            timeout=15
        )
        if rc == 0 and "cuda" in out.lower():
            return True
        return False

    def check_path_fixed(self) -> bool:
        rc, out, _ = self._run_wsl("which grep && which tail", timeout=10)
        return rc == 0 and "grep" in out and "tail" in out

    def get_version_status(self, force_refresh: bool = False) -> WslVersionStatus:
        if self._version_status is not None and not force_refresh:
            return self._version_status

        status = WslVersionStatus()
        status.last_check = time.strftime("%Y-%m-%d %H:%M:%S")

        if not self.check_gromacs_installed():
            self._version_status = status
            return status

        rc, out, _ = self._run_wsl(
            "source /mnt/d/YDW/WSL_Gromacs/setup_gromacs_env.sh && gmx --version",
            timeout=15
        )
        if rc != 0:
            self._version_status = status
            return status

        for line in out.split("\n"):
            line_lower = line.lower()
            if "gromacs version:" in line_lower:
                status.current_version = line.split(":", 1)[1].strip()
            elif "simd instructions:" in line_lower:
                status.simd = line.split(":", 1)[1].strip()
            elif "gpu support:" in line_lower:
                status.gpu = line.split(":", 1)[1].strip()
            elif "plumed support:" in line_lower:
                status.plumed = "enabled" in line.lower() or "yes" in line.lower()
            elif "cuda runtime:" in line_lower:
                status.cuda_version = line.split(":", 1)[1].strip()
            elif "cuda targets:" in line_lower:
                arch_str = line.split(":", 1)[1].strip()
                status.supported_arch = [a.strip() for a in arch_str.split(";") if a.strip()]

        status.install_path = self.GROMACS_ROOT
        self._version_status = status
        return status

    def check_health(self, force_refresh: bool = False) -> WslHealthReport:
        if self._health_report is not None and not force_refresh:
            return self._health_report

        report = WslHealthReport()
        report.timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

        report.wsl_available = self.check_wsl_available()
        if not report.wsl_available:
            report.status = WslHealthStatus.ERROR.value
            report.errors.append("WSL环境不可用或未安装Ubuntu发行版")
            self._health_report = report
            self._audit.log_wsl_env_check("error", report.to_dict())
            return report

        report.distro_available = True
        report.cuda_available = self.check_cuda_available()
        report.gromacs_installed = self.check_gromacs_installed()
        report.gpu_available = self.check_gpu_available()
        report.path_fixed = self.check_path_fixed()

        if not report.gromacs_installed:
            report.errors.append("GROMACS未安装或安装路径不正确")
        if not report.cuda_available:
            report.warnings.append("CUDA Toolkit不可用，GPU加速可能失败")
        if not report.gpu_available:
            report.warnings.append("GPU支持未启用或无法检测")
        if not report.path_fixed:
            report.warnings.append("PATH环境变量可能需要修复")

        if report.errors:
            report.status = WslHealthStatus.ERROR.value
        elif report.warnings:
            report.status = WslHealthStatus.WARNING.value
        else:
            report.status = WslHealthStatus.HEALTHY.value

        self._health_report = report
        self._audit.log_wsl_env_check(report.status, report.to_dict())
        return report

    def _calc_file_hash(self, filepath: str) -> str:
        try:
            h = hashlib.sha256()
            with open(filepath, "rb") as f:
                while True:
                    chunk = f.read(8192)
                    if not chunk:
                        break
                    h.update(chunk)
            return h.hexdigest()
        except Exception:
            return ""

    def get_script_hashes(self) -> Dict[str, str]:
        """获取关键脚本文件的当前哈希值，用于更新检测"""
        scripts = {
            "launch_gromacs_wsl.sh": self.LAUNCH_SCRIPT,
            "setup_gromacs_env.sh": self.ENV_SCRIPT,
            "启动WSL_GROMACS.bat": self.BAT_FILE,
        }
        result = {}
        for name, path in scripts.items():
            if sys.platform.startswith("win") and path.startswith("/mnt/"):
                win_path = path.replace("/mnt/d", "D:").replace("/", "\\")
            else:
                win_path = path
            result[name] = self._calc_file_hash(win_path)
        return result

    def record_script_update(self, script_name: str, old_hash: str, new_hash: str):
        self._audit.log_wsl_gromacs_update(
            old_version=old_hash[:16] if old_hash else "unknown",
            new_version=new_hash[:16] if new_hash else "unknown",
            details={"script": script_name, "action": "updated"}
        )

    def run_command_with_audit(self, cmd: str, timeout: int = 30,
                               description: str = "") -> Tuple[int, str, str]:
        """执行WSL命令并记录审计日志"""
        rc, stdout, stderr = self._run_wsl(cmd, timeout=timeout)
        self._audit.log_wsl_command(
            command=description or cmd,
            return_code=rc,
            details={"stdout": stdout[:500], "stderr": stderr[:500]}
        )
        return rc, stdout, stderr

    def run_full_workflow_test(self, timeout: int = 120) -> Dict[str, Any]:
        """运行完整工作流测试并返回结果"""
        test_script = "/mnt/d/YDW/WSL_Gromacs/test_full_workflow.sh"
        rc, stdout, stderr = self.run_command_with_audit(
            f"bash {test_script}",
            timeout=timeout,
            description="运行WSL GROMACS完整工作流测试"
        )
        result = {
            "success": rc == 0,
            "return_code": rc,
            "stdout": stdout[-2000:],
            "stderr": stderr[-1000:],
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        if rc != 0:
            self._logger.error(f"WSL完整工作流测试失败: {stderr[:500]}")
            self._audit.log_error("wsl_workflow_test_failed", "完整工作流测试失败", result)
        else:
            self._logger.info("WSL完整工作流测试通过")
        return result

    def check_for_script_updates(self) -> Dict[str, Any]:
        """检查启动脚本/环境脚本是否有更新记录"""
        current_hashes = self.get_script_hashes()
        report = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "scripts": current_hashes,
            "message": "脚本哈希已记录，可用于后续变更比对",
        }
        self._audit.log_wsl_env_check("script_hash_recorded", report)
        return report

    def generate_status_report(self, run_test: bool = False) -> Dict[str, Any]:
        health = self.check_health(force_refresh=True)
        version = self.get_version_status(force_refresh=True)
        script_hashes = self.get_script_hashes()

        report = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "health": health.to_dict(),
            "version": version.to_dict(),
            "script_hashes": script_hashes,
            "paths": {
                "windows_install": "D:\\YDW\\WSL_Gromacs\\install\\gromacs-2026.3-AVX512-CUDA",
                "wsl_install": self.GROMACS_ROOT,
                "env_script": self.ENV_SCRIPT,
                "launch_script": self.LAUNCH_SCRIPT,
                "bat_file": self.BAT_FILE,
            }
        }

        if run_test and health.status == WslHealthStatus.HEALTHY.value:
            report["workflow_test"] = self.run_full_workflow_test()

        # 保存报告到 WSL_Gromacs 目录和 Trae_Gromacs logs 目录
        try:
            report_dirs = [
                Path("D:/YDW/WSL_Gromacs"),
                Path(__file__).parent.parent / "logs" / "wsl_reports",
            ]
            saved_paths = []
            for report_dir in report_dirs:
                report_dir.mkdir(parents=True, exist_ok=True)
                report_file = report_dir / f"wsl_status_report_{time.strftime('%Y%m%d_%H%M%S')}.json"
                with open(report_file, "w", encoding="utf-8") as f:
                    json.dump(report, f, indent=2, ensure_ascii=False)
                saved_paths.append(str(report_file))
            report["saved_to"] = saved_paths
        except Exception as e:
            self._logger.warning(f"保存状态报告失败: {e}")

        return report

    def check_for_gromacs_update(self) -> Dict[str, Any]:
        """检查是否有新的WSL GROMACS版本可用（本地版本记录）"""
        version = self.get_version_status(force_refresh=True)
        result = {
            "current_version": version.current_version,
            "expected_version": "2026.3",
            "update_available": version.current_version != "2026.3" or not version.current_version,
            "message": ""
        }
        if result["update_available"]:
            result["message"] = "建议重新编译或更新GROMACS到2026.3版本"
        else:
            result["message"] = "WSL GROMACS版本已是最新"
        return result
