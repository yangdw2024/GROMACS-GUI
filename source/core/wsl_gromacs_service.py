#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WSL GROMACS服务层 - 封装WSL中Linux版GROMACS的调用
支持通过wsl命令调用D盘上的Linux版GROMACS
"""

import os
import sys
import subprocess
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, asdict
from enum import Enum

from .error_handler import ErrorHandler, GromacsError, ErrorCategory, ErrorSeverity
from .logger import AppLogger, LogLevel
from .audit_mechanism import AuditMechanism


class CommandType(Enum):
    GROMPP = "grompp"
    MDRUN = "mdrun"
    EDITCONF = "editconf"
    GENION = "genion"
    SOLVATE = "solvate"
    ENERGY = "energy"
    TRJCONV = "trjconv"
    RMSF = "rmsf"
    RMS = "rms"
    GYRATE = "gyrate"
    HBOND = "hbond"
    SASA = "sasa"
    OTHER = "other"


@dataclass
class WslVersionInfo:
    name: str = ""
    path: str = ""
    gmx_exe: str = ""
    version: str = ""
    precision: str = ""
    simd: str = ""
    gpu: str = ""
    plumed: str = ""
    valid: bool = False
    size_mb: float = 0.0
    last_modified: str = ""
    score: int = 0
    is_wsl: bool = True

    def to_dict(self) -> Dict:
        return asdict(self)


class WslGromacsService:
    _instance = None
    _lock = threading.Lock()

    WSL_DISTRO = "Ubuntu"
    WSL_GROMACS_ROOT = "/mnt/d/YDW/WSL_Gromacs/install/gromacs-2026.3-AVX512-CUDA"
    WSL_ENV_SCRIPT = "/mnt/d/YDW/WSL_Gromacs/setup_gromacs_env.sh"

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._versions: Dict[str, WslVersionInfo] = {}
        self._selected_version: Optional[str] = None
        self._cache: Dict[str, Any] = {}
        self._cache_ttl: Dict[str, float] = {}
        self._cache_lock = threading.Lock()
        self._default_ttl = 300.0

        self._logger = AppLogger()
        self._error_handler = ErrorHandler()
        self._audit = AuditMechanism()

        self._initialized = True

    def _convert_windows_path(self, win_path: str) -> str:
        win_path = win_path.replace("\\", "/")
        if win_path.startswith("D:") or win_path.startswith("d:"):
            return "/mnt/d" + win_path[2:]
        elif win_path.startswith("C:") or win_path.startswith("c:"):
            return "/mnt/c" + win_path[2:]
        elif win_path.startswith("/mnt/"):
            return win_path
        return win_path

    def _build_wsl_command(self, cmd: str, work_dir: str = None) -> List[str]:
        env_setup = f"source {self.WSL_ENV_SCRIPT} && "
        if work_dir:
            wsl_work_dir = self._convert_windows_path(work_dir)
            env_setup += f"cd {wsl_work_dir} && "
        full_cmd = env_setup + cmd
        return ["wsl", "-d", self.WSL_DISTRO, "-e", "bash", "-c", full_cmd]

    def _run_wsl_command(self, cmd: str, work_dir: str = None, timeout: int = 30,
                         input_text: str = None) -> Tuple[int, str, str]:
        full_cmd = self._build_wsl_command(cmd, work_dir)
        self._logger.info(f"WSL命令: {' '.join(full_cmd)}")

        try:
            startupinfo = None
            if sys.platform.startswith("win"):
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            process = subprocess.Popen(
                full_cmd,
                stdin=subprocess.PIPE if input_text else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                startupinfo=startupinfo,
                shell=False
            )

            stdout, stderr = process.communicate(
                input=input_text,
                timeout=timeout
            )

            return process.returncode, stdout, stderr

        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            self._audit.log_wsl_command(cmd, -1, {"error": "timeout", "timeout": timeout})
            raise GromacsError(
                f"WSL命令执行超时 ({timeout}s)",
                ErrorCategory.SUBPROCESS, ErrorSeverity.HIGH,
                recoverable=True,
                suggestion="增加超时时间或简化任务"
            )
        except Exception as e:
            self._audit.log_wsl_command(cmd, -1, {"error": str(e)})
            raise self._error_handler.handle(e, {"cmd": cmd, "work_dir": work_dir})

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
        try:
            rc, stdout, stderr = self._run_wsl_command("gmx --version", timeout=10)
            return rc == 0
        except Exception:
            return False

    def _get_version_info(self) -> WslVersionInfo:
        info = WslVersionInfo()
        info.name = "WSL_gromacs-2026.3-AVX512-CUDA-sm120"
        info.path = self.WSL_GROMACS_ROOT
        info.gmx_exe = f"{self.WSL_GROMACS_ROOT}/bin/gmx"
        info.is_wsl = True

        try:
            rc, out, stderr = self._run_wsl_command("gmx --version", timeout=15)
            info.valid = rc == 0

            if info.valid:
                for line in out.split("\n"):
                    line_lower = line.lower()
                    if "gromacs version:" in line_lower:
                        info.version = line.split(":", 1)[1].strip()
                    elif "precision:" in line_lower:
                        info.precision = line.split(":", 1)[1].strip()
                    elif "simd instructions:" in line_lower:
                        info.simd = line.split(":", 1)[1].strip()
                    elif "gpu support:" in line_lower:
                        info.gpu = line.split(":", 1)[1].strip()
                    elif "plumed support:" in line_lower:
                        info.plumed = line.split(":", 1)[1].strip()

                info.last_modified = time.strftime(
                    "%Y-%m-%d %H:%M:%S",
                    time.localtime()
                )
                info.score = self._calculate_score(info)

        except Exception as e:
            info.valid = False
            self._logger.warning(f"WSL GROMACS获取版本信息失败: {e}")

        return info

    def _calculate_score(self, info: WslVersionInfo) -> int:
        score = 0
        if info.gpu.lower() in ("cuda", "opencl", "yes", "enabled"):
            score += 1000
        simd = info.simd.lower()
        if "avx_512" in simd or "avx512" in simd:
            score += 500
        elif "avx2" in simd:
            score += 300
        if info.plumed.lower() in ("yes", "enabled", "是"):
            score += 100
        try:
            parts = info.version.split(".")
            major = int(parts[0]) if len(parts) > 0 else 0
            minor = int(parts[1]) if len(parts) > 1 else 0
            score += major * 10 + minor
        except Exception:
            pass
        return score

    def scan_versions(self) -> Dict[str, WslVersionInfo]:
        versions = {}
        if self.check_wsl_available() and self.check_gromacs_installed():
            info = self._get_version_info()
            if info.valid:
                versions[info.name] = info
                self._logger.info(f"WSL GROMACS版本扫描完成: {info.name}")
        self._versions = versions
        return versions

    def get_best_version(self) -> Optional[Tuple[str, WslVersionInfo]]:
        valid_versions = {k: v for k, v in self._versions.items() if v.valid}
        if not valid_versions:
            return None
        best = max(valid_versions.items(), key=lambda x: x[1].score)
        return best

    def select_version(self, version_name: str) -> bool:
        if version_name not in self._versions:
            self._logger.error(f"WSL版本不存在: {version_name}")
            return False
        if not self._versions[version_name].valid:
            self._logger.error(f"WSL版本无效: {version_name}")
            return False
        self._selected_version = version_name
        self._logger.info(f"已选择WSL GROMACS版本: {version_name}")
        return True

    def get_selected_version(self) -> Optional[WslVersionInfo]:
        if self._selected_version and self._selected_version in self._versions:
            return self._versions[self._selected_version]
        best = self.get_best_version()
        if best:
            self._selected_version = best[0]
            return best[1]
        return None

    def run_command(self, cmd_type: CommandType, args: List[str],
                    work_dir: str = None, env: Dict[str, str] = None,
                    timeout: int = 300, input_text: str = None) -> Tuple[int, str, str]:
        gmx_cmd = ["gmx", cmd_type.value] + args
        cmd_str = " ".join(gmx_cmd)
        self._logger.info(f"执行WSL GROMACS命令: {cmd_str}")

        rc, stdout, stderr = self._run_wsl_command(cmd_str, work_dir, timeout, input_text)

        self._audit.log_wsl_command(cmd_str, rc, {
            "cmd_type": cmd_type.value,
            "work_dir": work_dir,
            "stderr": stderr[:500] if rc != 0 else ""
        })

        if rc != 0:
            self._logger.error(f"WSL命令失败 (rc={rc}): {stderr[:500]}")

        return rc, stdout, stderr

    def run_energy(self, edr_path: str, energy_items: List[str],
                   work_dir: str = None, output_xvg: str = None) -> str:
        wsl_edr_path = self._convert_windows_path(edr_path)
        args = ["-f", wsl_edr_path]
        if output_xvg:
            wsl_output = self._convert_windows_path(output_xvg)
            args += ["-o", wsl_output]

        input_str = "\n".join(energy_items) + "\n\n"

        rc, stdout, stderr = self.run_command(
            CommandType.ENERGY, args,
            work_dir=work_dir, input_text=input_str, timeout=60
        )

        if rc != 0:
            raise GromacsError(
                f"WSL能量分析失败: {stderr[:500]}",
                ErrorCategory.GROMACS, ErrorSeverity.HIGH
            )

        return stdout

    def validate_installation(self) -> Tuple[bool, str]:
        if not self.check_wsl_available():
            return False, "WSL环境不可用，请检查WSL是否已安装"
        if not self.check_gromacs_installed():
            return False, "WSL中GROMACS未安装或配置错误"
        version = self.get_selected_version()
        if version:
            return True, f"WSL版本 {version.name} 验证通过"
        return False, "未选择任何WSL版本"

    def get_health_report(self) -> Dict[str, Any]:
        """获取WSL环境健康报告（通过WslUpdateManager）"""
        from .wsl_update_manager import WslUpdateManager
        manager = WslUpdateManager()
        return manager.check_health(force_refresh=True).to_dict()

    def get_version_list(self) -> List[Dict[str, Any]]:
        return [v.to_dict() for v in self._versions.values()]

    def _get_cache(self, key: str) -> Any:
        with self._cache_lock:
            if key in self._cache and key in self._cache_ttl:
                if time.time() < self._cache_ttl[key]:
                    return self._cache[key]
                else:
                    del self._cache[key]
                    del self._cache_ttl[key]
            return None

    def _set_cache(self, key: str, value: Any, ttl: float = None):
        if ttl is None:
            ttl = self._default_ttl
        with self._cache_lock:
            self._cache[key] = value
            self._cache_ttl[key] = time.time() + ttl

    def clear_cache(self):
        with self._cache_lock:
            self._cache.clear()
            self._cache_ttl.clear()
