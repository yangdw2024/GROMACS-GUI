#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GROMACS服务层 - 封装所有gmx命令调用
提供：版本管理、命令执行、结果解析、错误处理、缓存
"""

import os
import sys
import re
import json
import subprocess
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, asdict
from enum import Enum

from .error_handler import ErrorHandler, GromacsError, ErrorCategory, ErrorSeverity
from .logger import AppLogger, LogLevel


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
class VersionInfo:
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

    def to_dict(self) -> Dict:
        return asdict(self)


class GromacsService:
    _instance = None
    _lock = threading.Lock()

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

        self._versions: Dict[str, VersionInfo] = {}
        self._selected_version: Optional[str] = None
        self._cache: Dict[str, Any] = {}
        self._cache_ttl: Dict[str, float] = {}
        self._cache_lock = threading.Lock()
        self._default_ttl = 300.0

        self._logger = AppLogger()
        self._error_handler = ErrorHandler()

        self._initialized = True

    def _validate_plumed(self, bin_dir: Path, gmx_exe: Path = None) -> bool:
        """验证PLUMED运行时库是否有效（支持动态链接和静态链接）"""
        # 1. 动态链接：检查libplumedKernel.dll
        kernel = bin_dir / "libplumedKernel.dll"
        if kernel.exists() and not kernel.is_dir() and kernel.stat().st_size > 0:
            return True

        # 2. 静态链接：libplumedKernel.dll不存在，但gmx.exe可能已静态链接PLUMED
        # 通过运行gmx mdrun -h检查是否支持-plumed参数
        if gmx_exe and gmx_exe.exists():
            try:
                startupinfo = None
                if sys.platform.startswith("win"):
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                result = subprocess.run(
                    [str(gmx_exe), "mdrun", "-h"],
                    capture_output=True, text=True, timeout=10,
                    startupinfo=startupinfo
                )
                output = result.stdout + result.stderr
                if "-plumed" in output or "plumed.dat" in output:
                    return True
            except Exception:
                pass

        return False

    def scan_gromacs_versions(self, base_dir: str = None, prefer_plumed: bool = False) -> Dict[str, VersionInfo]:
        return self.scan_versions(base_dir, prefer_plumed)

    def scan_versions(self, base_dir: str = None, prefer_plumed: bool = False) -> Dict[str, VersionInfo]:
        if base_dir is None:
            base_dir = Path(__file__).parent.parent.parent / "gromacs"

        base_path = Path(base_dir)
        if not base_path.exists():
            return {}

        versions = {}
        for item in sorted(base_path.iterdir()):
            if not item.is_dir():
                continue
            if item.name.startswith("build-"):
                continue

            gmx_exe = item / "bin" / "gmx.exe"
            if not gmx_exe.exists():
                continue

            info = self._get_version_info(str(gmx_exe))
            info.name = item.name
            info.path = str(item)
            info.gmx_exe = str(gmx_exe)
            info.last_modified = time.strftime(
                "%Y-%m-%d %H:%M:%S",
                time.localtime(item.stat().st_mtime)
            )
            info.size_mb = round(self._get_dir_size(item) / (1024 * 1024), 1)

            if info.plumed.lower() in ("yes", "enabled", "是"):
                if not self._validate_plumed(item / "bin", gmx_exe):
                    self._logger.warning(
                        f"版本 {item.name} 声称支持PLUMED但库文件无效，"
                        f"已将PLUMED标记为disabled"
                    )
                    info.plumed = "disabled (broken library)"

            info.score = self._calculate_score(info, prefer_plumed=prefer_plumed)
            versions[item.name] = info

        self._versions = versions
        self._logger.info(f"扫描到 {len(versions)} 个GROMACS版本")
        return versions

    def _get_version_info(self, gmx_exe: str) -> VersionInfo:
        info = VersionInfo()
        try:
            startupinfo = None
            if sys.platform.startswith("win"):
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            result = subprocess.run(
                [gmx_exe, "--version"],
                capture_output=True, text=True, timeout=15,
                startupinfo=startupinfo
            )
            out = result.stdout + result.stderr
            info.valid = result.returncode == 0

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
        except Exception as e:
            info.valid = False
            self._logger.warning(f"获取版本信息失败: {e}")

        return info

    def _get_dir_size(self, path: Path) -> int:
        total = 0
        try:
            for item in path.rglob("*"):
                if item.is_file():
                    try:
                        total += item.stat().st_size
                    except Exception:
                        pass
        except Exception:
            pass
        return total

    def _calculate_score(self, info: VersionInfo, prefer_plumed: bool = False) -> int:
        score = 0
        if info.gpu.lower() in ("cuda", "opencl", "yes", "enabled"):
            score += 1000
        simd = info.simd.lower()
        if "avx_512" in simd or "avx512" in simd:
            score += 500
        elif "avx2" in simd:
            score += 300
        if prefer_plumed and info.plumed.lower() in ("yes", "enabled", "是"):
            score += 100
        try:
            parts = info.version.split(".")
            major = int(parts[0]) if len(parts) > 0 else 0
            minor = int(parts[1]) if len(parts) > 1 else 0
            score += major * 10 + minor
        except Exception:
            pass
        return score

    def select_best_version(self, versions: Dict = None) -> Optional[str]:
        if versions:
            self._versions = versions
        best = self.get_best_version()
        return best[0] if best else None

    def get_best_version(self, prefer_plumed: bool = False) -> Optional[Tuple[str, VersionInfo]]:
        valid_versions = {k: v for k, v in self._versions.items() if v.valid}
        if not valid_versions:
            return None
        if prefer_plumed:
            valid_versions = {
                k: v for k, v in valid_versions.items()
                if v.plumed.lower() in ("yes", "enabled", "是")
            }
            if not valid_versions:
                self._logger.warning("未找到启用了PLUMED的版本，将使用普通版本")
                valid_versions = {k: v for k, v in self._versions.items() if v.valid}
        best = max(valid_versions.items(), key=lambda x: x[1].score)
        return best

    def select_version(self, version_name: str) -> bool:
        if version_name not in self._versions:
            self._logger.error(f"版本不存在: {version_name}")
            return False
        if not self._versions[version_name].valid:
            self._logger.error(f"版本无效: {version_name}")
            return False
        self._selected_version = version_name
        self._logger.info(f"已选择GROMACS版本: {version_name}")
        return True

    def get_selected_version(self) -> Optional[VersionInfo]:
        if self._selected_version and self._selected_version in self._versions:
            return self._versions[self._selected_version]
        best = self.get_best_version()
        if best:
            self._selected_version = best[0]
            return best[1]
        return None

    def get_gmx_exe(self) -> str:
        version = self.get_selected_version()
        if version:
            return version.gmx_exe
        raise GromacsError(
            "未找到可用的GROMACS版本",
            ErrorCategory.GROMACS, ErrorSeverity.CRITICAL,
            suggestion="请检查GROMACS安装路径"
        )

    def run_command(self, cmd_type: CommandType, args: List[str],
                    work_dir: str = None, env: Dict[str, str] = None,
                    timeout: int = 300, input_text: str = None) -> Tuple[int, str, str]:
        gmx_exe = self.get_gmx_exe()
        cmd = [gmx_exe, cmd_type.value] + args

        self._logger.info(f"执行命令: {' '.join(cmd)}")

        try:
            startupinfo = None
            if sys.platform.startswith("win"):
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            process = subprocess.Popen(
                cmd,
                cwd=work_dir,
                stdin=subprocess.PIPE if input_text else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env={**os.environ, **(env or {})},
                startupinfo=startupinfo,
                shell=False
            )

            stdout, stderr = process.communicate(
                input=input_text,
                timeout=timeout
            )

            if process.returncode != 0:
                self._logger.error(
                    f"命令失败 (rc={process.returncode}): {stderr[:500]}"
                )

            return process.returncode, stdout, stderr

        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            raise GromacsError(
                f"命令执行超时 ({timeout}s)",
                ErrorCategory.SUBPROCESS, ErrorSeverity.HIGH,
                recoverable=True,
                suggestion="增加超时时间或简化任务"
            )
        except Exception as e:
            raise self._error_handler.handle(e, {"cmd": cmd, "work_dir": work_dir})

    def run_energy(self, edr_path: str, energy_items: List[str],
                   work_dir: str = None, output_xvg: str = None) -> str:
        args = ["-f", edr_path]
        if output_xvg:
            args += ["-o", output_xvg]

        input_str = "\n".join(energy_items) + "\n\n"

        rc, stdout, stderr = self.run_command(
            CommandType.ENERGY, args,
            work_dir=work_dir, input_text=input_str, timeout=60
        )

        if rc != 0:
            raise GromacsError(
                f"能量分析失败: {stderr[:500]}",
                ErrorCategory.GROMACS, ErrorSeverity.HIGH
            )

        return stdout

    def check_trajectory(self, traj_path: str) -> Dict[str, Any]:
        cache_key = f"traj_check:{traj_path}"
        cached = self._get_cache(cache_key)
        if cached:
            return cached

        args = ["-f", traj_path]
        rc, stdout, stderr = self.run_command(
            CommandType.OTHER, ["check"] + args, timeout=30
        )

        result = {"valid": rc == 0, "details": stdout}
        self._set_cache(cache_key, result)
        return result

    def check_topology(self, tpr_path: str) -> Dict[str, Any]:
        cache_key = f"tpr_check:{tpr_path}"
        cached = self._get_cache(cache_key)
        if cached:
            return cached

        args = ["-s", tpr_path]
        rc, stdout, stderr = self.run_command(
            CommandType.OTHER, ["dump", "-s"] + args, timeout=30
        )

        result = {"valid": rc == 0, "details": stdout}
        self._set_cache(cache_key, result)
        return result

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

    def validate_installation(self, version_name: str = None) -> Tuple[bool, str]:
        if version_name:
            if version_name not in self._versions:
                return False, f"版本 {version_name} 未找到"
            version = self._versions[version_name]
        else:
            version = self.get_selected_version()
            if not version:
                return False, "未选择任何版本"

        if not version.valid:
            return False, f"版本 {version.name} 无效"

        if not Path(version.gmx_exe).exists():
            return False, f"可执行文件不存在: {version.gmx_exe}"

        return True, f"版本 {version.name} 验证通过"
