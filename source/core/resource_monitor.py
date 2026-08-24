#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统资源监控器
实时监控：CPU、内存、GPU、磁盘使用率
提供：告警、阈值检查、资源可用性判断
"""

import os
import sys
import time
import threading
import subprocess
from pathlib import Path
from typing import Dict, List, Callable, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class AlertLevel(Enum):
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class ResourceStatus:
    cpu_percent: float = 0.0
    cpu_cores: int = 0
    memory_total_gb: float = 0.0
    memory_used_gb: float = 0.0
    memory_percent: float = 0.0
    disk_total_gb: float = 0.0
    disk_free_gb: float = 0.0
    disk_percent: float = 0.0
    gpu_available: bool = False
    gpu_name: str = ""
    gpu_memory_total_mb: int = 0
    gpu_memory_used_mb: int = 0
    gpu_memory_percent: float = 0.0
    gpu_utilization: float = 0.0
    timestamp: float = 0.0


class ResourceMonitor:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, interval=5.0):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, interval=5.0):
        if self._initialized:
            return

        self.interval = interval
        self._status = ResourceStatus()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._listeners: List[Callable] = []
        self._alert_thresholds = {
            "memory_warning": 80.0,
            "memory_critical": 95.0,
            "disk_warning": 85.0,
            "disk_critical": 95.0,
            "cpu_warning": 90.0,
            "cpu_critical": 98.0,
        }
        self._lock = threading.Lock()

        self._initialized = True

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _monitor_loop(self):
        while self._running:
            try:
                self._update_status()
                self._check_alerts()
                for listener in self._listeners:
                    try:
                        listener(self._status)
                    except Exception:
                        pass
            except Exception:
                pass
            time.sleep(self.interval)

    def _update_status(self):
        status = ResourceStatus()
        status.timestamp = time.time()

        # CPU
        try:
            status.cpu_cores = os.cpu_count() or 0
            if sys.platform == "win32":
                result = subprocess.run(
                    ["wmic", "cpu", "get", "NumberOfCores", "/format:list"],
                    capture_output=True, text=True, timeout=5
                )
                for line in result.stdout.split("\n"):
                    line = line.strip()
                    if "=" in line:
                        key, value = line.split("=", 1)
                        if key.strip() == "NumberOfCores":
                            try:
                                status.cpu_cores = int(value.strip())
                            except ValueError:
                                pass
                            break
                import ctypes
                class FILETIME(ctypes.Structure):
                    _fields_ = [("dwLowDateTime", ctypes.c_uint32),
                               ("dwHighDateTime", ctypes.c_uint32)]
                kernel = ctypes.windll.kernel32
                idle_time = FILETIME()
                kernel_time = FILETIME()
                user_time = FILETIME()
                if kernel.GetSystemTimes(ctypes.byref(idle_time),
                                        ctypes.byref(kernel_time),
                                        ctypes.byref(user_time)):
                    status.cpu_percent = 0.0
        except Exception:
            pass

        # Memory (Windows)
        try:
            if sys.platform == "win32":
                import ctypes
                class MEMORYSTATUSEX(ctypes.Structure):
                    _fields_ = [
                        ("dwLength", ctypes.c_uint32),
                        ("dwMemoryLoad", ctypes.c_uint32),
                        ("ullTotalPhys", ctypes.c_uint64),
                        ("ullAvailPhys", ctypes.c_uint64),
                        ("ullTotalPageFile", ctypes.c_uint64),
                        ("ullAvailPageFile", ctypes.c_uint64),
                        ("ullTotalVirtual", ctypes.c_uint64),
                        ("ullAvailVirtual", ctypes.c_uint64),
                        ("ullAvailExtendedVirtual", ctypes.c_uint64),
                    ]
                mem = MEMORYSTATUSEX()
                mem.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
                ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))
                status.memory_total_gb = mem.ullTotalPhys / (1024 ** 3)
                status.memory_used_gb = (mem.ullTotalPhys - mem.ullAvailPhys) / (1024 ** 3)
                status.memory_percent = mem.dwMemoryLoad
        except Exception:
            try:
                result = subprocess.run(
                    ["wmic", "computersystem", "get", "totalphysicalmemory"],
                    capture_output=True, text=True, timeout=10
                )
                lines = result.stdout.strip().split("\n")
                for line in lines[1:]:
                    line = line.strip()
                    if line.isdigit():
                        status.memory_total_gb = int(line) / (1024 ** 3)
                        break
                result2 = subprocess.run(
                    ["wmic", "os", "get", "freephysicalmemory"],
                    capture_output=True, text=True, timeout=10
                )
                lines2 = result2.stdout.strip().split("\n")
                for line in lines2[1:]:
                    line = line.strip()
                    if line.isdigit():
                        available_mb = int(line)
                        status.memory_used_gb = status.memory_total_gb - (available_mb / 1024)
                        if status.memory_total_gb > 0:
                            status.memory_percent = ((status.memory_total_gb - available_mb / 1024) / status.memory_total_gb) * 100
                        break
            except Exception:
                pass

        # Disk
        try:
            if sys.platform == "win32":
                import ctypes
                free_bytes = ctypes.c_ulonglong(0)
                total_bytes = ctypes.c_ulonglong(0)
                ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                    str(Path.cwd()),
                    ctypes.byref(free_bytes),
                    ctypes.byref(total_bytes),
                    None
                )
                status.disk_total_gb = total_bytes.value / (1024 ** 3)
                status.disk_free_gb = free_bytes.value / (1024 ** 3)
                if status.disk_total_gb > 0:
                    status.disk_percent = (1 - status.disk_free_gb / status.disk_total_gb) * 100
        except Exception:
            pass

        # GPU
        try:
            status.gpu_available = self._detect_gpu()
            if status.gpu_available:
                self._update_gpu_info(status)
        except Exception:
            pass

        with self._lock:
            self._status = status

    def _detect_gpu(self) -> bool:
        try:
            result = subprocess.run(
                ["nvidia-smi", "-L"],
                capture_output=True, text=True, timeout=2
            )
            return result.returncode == 0 and bool(result.stdout.strip())
        except Exception:
            return False

    def _update_gpu_info(self, status: ResourceStatus):
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total,memory.used,utilization.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0:
                parts = result.stdout.strip().split(",")
                if len(parts) >= 4:
                    status.gpu_name = parts[0].strip()
                    status.gpu_memory_total_mb = int(float(parts[1].strip()))
                    status.gpu_memory_used_mb = int(float(parts[2].strip()))
                    status.gpu_utilization = float(parts[3].strip())
                    if status.gpu_memory_total_mb > 0:
                        status.gpu_memory_percent = (
                            status.gpu_memory_used_mb / status.gpu_memory_total_mb * 100
                        )
        except Exception:
            pass

    def _check_alerts(self):
        with self._lock:
            status = self._status

        alerts = []

        if status.memory_percent >= self._alert_thresholds["memory_critical"]:
            alerts.append(("memory", AlertLevel.Critical, f"内存使用率 {status.memory_percent:.1f}%"))
        elif status.memory_percent >= self._alert_thresholds["memory_warning"]:
            alerts.append(("memory", AlertLevel.WARNING, f"内存使用率 {status.memory_percent:.1f}%"))

        if status.disk_percent >= self._alert_thresholds["disk_critical"]:
            alerts.append(("disk", AlertLevel.Critical, f"磁盘使用率 {status.disk_percent:.1f}%"))
        elif status.disk_percent >= self._alert_thresholds["disk_warning"]:
            alerts.append(("disk", AlertLevel.WARNING, f"磁盘使用率 {status.disk_percent:.1f}%"))

        if status.cpu_percent >= self._alert_thresholds["cpu_critical"]:
            alerts.append(("cpu", AlertLevel.Critical, f"CPU使用率 {status.cpu_percent:.1f}%"))
        elif status.cpu_percent >= self._alert_thresholds["cpu_warning"]:
            alerts.append(("cpu", AlertLevel.WARNING, f"CPU使用率 {status.cpu_percent:.1f}%"))

        for resource, level, message in alerts:
            for listener in self._listeners:
                try:
                    listener(status, resource, level, message)
                except Exception:
                    pass

    def get_status(self) -> ResourceStatus:
        self._update_status()
        with self._lock:
            return ResourceStatus(
                cpu_percent=self._status.cpu_percent,
                cpu_cores=self._status.cpu_cores,
                memory_total_gb=self._status.memory_total_gb,
                memory_used_gb=self._status.memory_used_gb,
                memory_percent=self._status.memory_percent,
                disk_total_gb=self._status.disk_total_gb,
                disk_free_gb=self._status.disk_free_gb,
                disk_percent=self._status.disk_percent,
                gpu_available=self._status.gpu_available,
                gpu_name=self._status.gpu_name,
                gpu_memory_total_mb=self._status.gpu_memory_total_mb,
                gpu_memory_used_mb=self._status.gpu_memory_used_mb,
                gpu_memory_percent=self._status.gpu_memory_percent,
                gpu_utilization=self._status.gpu_utilization,
                timestamp=self._status.timestamp,
            )

    def add_listener(self, callback: Callable):
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable):
        if callback in self._listeners:
            self._listeners.remove(callback)

    def set_threshold(self, resource: str, warning: float, critical: float):
        self._alert_thresholds[f"{resource}_warning"] = warning
        self._alert_thresholds[f"{resource}_critical"] = critical

    def can_start_simulation(self, required_memory_gb: float = 0,
                            required_disk_gb: float = 1.0) -> Tuple[bool, str]:
        status = self.get_status()

        if status.memory_percent >= self._alert_thresholds["memory_critical"]:
            return False, f"内存严重不足 ({status.memory_percent:.1f}%)，请关闭其他程序"

        if status.disk_free_gb < required_disk_gb:
            return False, f"磁盘空间不足 (剩余 {status.disk_free_gb:.1f} GB)"

        if status.memory_total_gb - status.memory_used_gb < required_memory_gb:
            return False, f"可用内存不足 (剩余 {status.memory_total_gb - status.memory_used_gb:.1f} GB)"

        return True, "资源充足"

    def get_recommendations(self) -> List[str]:
        status = self.get_status()
        recommendations = []

        if status.memory_percent > 80:
            recommendations.append("内存使用率较高，建议降低线程数或关闭其他程序")

        if status.disk_free_gb < 10:
            recommendations.append(f"磁盘空间紧张 (剩余 {status.disk_free_gb:.1f} GB)，建议清理")

        if status.gpu_available and status.gpu_memory_percent > 90:
            recommendations.append("GPU显存使用率过高，建议检查是否有其他程序占用GPU")

        return recommendations

    def get_cpu_info(self) -> Dict:
        """检测CPU详细信息（型号、核心数、线程数、指令集支持）"""
        cpu_info = {
            "name": "未知CPU",
            "cores": os.cpu_count() or 4,
            "threads": os.cpu_count() or 4,
            "simd_support": [],
            "avx512": False,
            "avx2": False,
            "avx": False,
            "sse4_2": False
        }

        try:
            result = subprocess.run(
                ["wmic", "cpu", "get", "Name,NumberOfCores,NumberOfLogicalProcessors", "/format:list"],
                capture_output=True, text=True, timeout=10
            )
            for line in result.stdout.split("\n"):
                line = line.strip()
                if "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()
                    if key == "Name":
                        cpu_info["name"] = value
                    elif key == "NumberOfCores":
                        try:
                            cpu_info["cores"] = int(value)
                        except ValueError:
                            pass
                    elif key == "NumberOfLogicalProcessors":
                        try:
                            cpu_info["threads"] = int(value)
                        except ValueError:
                            pass
        except Exception:
            pass

        try:
            try:
                from cpuinfo import get_cpu_info
                info = get_cpu_info()
                # 不再用 py-cpuinfo 的 brand_raw 覆盖 wmic 获取的准确名称
                # py-cpuinfo 在部分 AMD 平台上会错误识别 CPU 型号
                if info.get("count"):
                    cpu_info["threads"] = info["count"]
                flags = info.get("flags", [])
                simd_flags = [f for f in [
                    'avx', 'avx2', 'avx512f', 'avx512cd', 'avx512vl',
                    'avx512dq', 'avx512bw', 'sse4_1', 'sse4_2', 'sse2', 'sse3', 'ssse3'
                ] if f in flags]
                cpu_info["simd_support"] = simd_flags
                cpu_info["avx512"] = 'avx512f' in flags
                cpu_info["avx2"] = 'avx2' in flags
                cpu_info["avx"] = 'avx' in flags
                cpu_info["sse4_2"] = 'sse4_2' in flags
            except ImportError:
                cpu_name_lower = cpu_info["name"].lower()
                if "ryzen" in cpu_name_lower and ("9000" in cpu_name_lower or "9700x" in cpu_name_lower or "zen 5" in cpu_name_lower):
                    cpu_info["avx512"] = True
                    cpu_info["avx2"] = True
                    cpu_info["avx"] = True
                    cpu_info["simd_support"] = ['avx', 'avx2', 'avx512f', 'avx512cd', 'avx512vl', 'avx512dq', 'avx512bw']
                elif "ryzen" in cpu_name_lower or "epyc" in cpu_name_lower:
                    cpu_info["avx2"] = True
                    cpu_info["avx"] = True
                    cpu_info["simd_support"] = ['avx', 'avx2']
                elif any(i in cpu_name_lower for i in ["i3", "i5", "i7", "i9", "xeon"]):
                    cpu_info["avx2"] = True
                    cpu_info["avx"] = True
                    cpu_info["simd_support"] = ['avx', 'avx2']
        except Exception:
            pass

        return cpu_info

    def get_total_memory_gb(self) -> float:
        """获取系统总内存（GB）"""
        status = self.get_status()
        return round(status.memory_total_gb, 1)

    def get_gpu_info(self) -> Dict:
        """获取GPU信息"""
        status = self.get_status()
        driver_version = ""
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0:
                driver_version = result.stdout.strip()
        except Exception:
            pass

        return {
            "available": status.gpu_available,
            "name": status.gpu_name,
            "memory_total_mb": status.gpu_memory_total_mb,
            "memory_used_mb": status.gpu_memory_used_mb,
            "memory_percent": status.gpu_memory_percent,
            "utilization": status.gpu_utilization,
            "all_gpus": [{"name": status.gpu_name, "memory": f"{status.gpu_memory_total_mb} MB"}] if status.gpu_available else [],
            "names": [status.gpu_name] if status.gpu_available else [],
            "memories": [f"{status.gpu_memory_total_mb} MB"] if status.gpu_available else [],
            "ids": [0] if status.gpu_available else [],
            "cuda_version": "13.x" if status.gpu_available else "",
            "driver": driver_version
        }
