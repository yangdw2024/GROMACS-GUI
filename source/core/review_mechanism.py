#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
审查机制 - 参考NASA/JPL飞行软件审查流程
实现：启动前审查、运行中审查、结果审查三级体系
"""

import os
import json
import time
import threading
from pathlib import Path
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass
from enum import Enum

from .config_manager import ConfigManager
from .resource_monitor import ResourceMonitor
from .gromacs_service import GromacsService, VersionInfo


class ReviewLevel(Enum):
    QUICK = "quick"
    STANDARD = "standard"
    DEEP = "deep"


class ReviewStatus(Enum):
    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ReviewItem:
    name: str
    category: str
    status: ReviewStatus
    message: str
    severity: int = 0
    suggestion: str = ""
    timestamp: float = 0.0

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()


@dataclass
class ReviewReport:
    review_id: str
    level: ReviewLevel
    task_name: str
    items: List[ReviewItem]
    overall_status: ReviewStatus
    timestamp: float = 0.0
    duration_ms: float = 0.0

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    def get_failed_items(self) -> List[ReviewItem]:
        return [i for i in self.items if i.status == ReviewStatus.FAILED]

    def get_warning_items(self) -> List[ReviewItem]:
        return [i for i in self.items if i.status == ReviewStatus.WARNING]

    def has_failures(self) -> bool:
        return any(i.status == ReviewStatus.FAILED for i in self.items)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "review_id": self.review_id,
            "level": self.level.value,
            "task_name": self.task_name,
            "overall_status": self.overall_status.value,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp,
            "items": [{
                "name": i.name,
                "category": i.category,
                "status": i.status.value,
                "message": i.message,
                "severity": i.severity,
                "suggestion": i.suggestion,
            } for i in self.items],
        }


class ReviewMechanism:
    def __init__(self):
        self._config = ConfigManager()
        self._resource_monitor = ResourceMonitor()
        self._gromacs_service = GromacsService()
        self._lock = threading.Lock()
        self._reports: Dict[str, ReviewReport] = {}

    def preflight_check(self, task_name: str, params: Dict[str, Any],
                       work_dir: str, level: ReviewLevel = ReviewLevel.STANDARD) -> ReviewReport:
        start_time = time.time()
        items = []
        review_id = f"preflight_{int(time.time())}"

        if level.value in ("standard", "deep"):
            items.extend(self._check_input_files(params, work_dir))
            items.extend(self._check_parameters(params))
            items.extend(self._check_resources(params))
            items.extend(self._check_version_compatibility(params))

        if level.value == "deep":
            items.extend(self._check_system_environment())

        overall_status = self._determine_overall_status(items)
        duration_ms = (time.time() - start_time) * 1000

        report = ReviewReport(
            review_id=review_id,
            level=level,
            task_name=task_name,
            items=items,
            overall_status=overall_status,
            duration_ms=duration_ms,
        )

        with self._lock:
            self._reports[review_id] = report

        return report

    def _check_input_files(self, params: Dict, work_dir: str) -> List[ReviewItem]:
        items = []
        required_files = ["gro", "top", "mdp"]

        for ftype in required_files:
            path = params.get(f"input_{ftype}")
            if not path:
                items.append(ReviewItem(
                    name=f"输入文件_{ftype}",
                    category="文件检查",
                    status=ReviewStatus.FAILED,
                    message=f"缺少{ftype.upper()}输入文件",
                    severity=10,
                    suggestion="请指定输入文件路径",
                ))
            else:
                full_path = os.path.join(work_dir, path) if not os.path.isabs(path) else path
                if os.path.exists(full_path):
                    items.append(ReviewItem(
                        name=f"输入文件_{ftype}",
                        category="文件检查",
                        status=ReviewStatus.PASSED,
                        message=f"{ftype.upper()}文件存在: {full_path}",
                    ))
                else:
                    items.append(ReviewItem(
                        name=f"输入文件_{ftype}",
                        category="文件检查",
                        status=ReviewStatus.FAILED,
                        message=f"{ftype.upper()}文件不存在: {full_path}",
                        severity=10,
                        suggestion="请检查文件路径是否正确",
                    ))

        return items

    def _check_parameters(self, params: Dict) -> List[ReviewItem]:
        items = []

        nt = params.get("nt", 8)
        max_cores = self._resource_monitor.get_status().cpu_cores
        if nt > max_cores:
            items.append(ReviewItem(
                name="线程数检查",
                category="参数检查",
                status=ReviewStatus.WARNING,
                message=f"线程数{nt}超过可用核心数{max_cores}",
                severity=5,
                suggestion=f"建议设置为{max_cores}或更少",
            ))
        else:
            items.append(ReviewItem(
                name="线程数检查",
                category="参数检查",
                status=ReviewStatus.PASSED,
                message=f"线程数{nt}合理",
            ))

        mem_limit = params.get("mem_limit_gb", 6.0)
        total_mem = self._resource_monitor.get_status().memory_total_gb
        if mem_limit > total_mem * 0.8:
            items.append(ReviewItem(
                name="内存限制检查",
                category="参数检查",
                status=ReviewStatus.WARNING,
                message=f"内存限制{mem_limit}GB接近系统上限{total_mem}GB",
                severity=5,
                suggestion=f"建议降低内存限制",
            ))
        else:
            items.append(ReviewItem(
                name="内存限制检查",
                category="参数检查",
                status=ReviewStatus.PASSED,
                message=f"内存限制{mem_limit}GB合理",
            ))

        return items

    def _check_resources(self, params: Dict) -> List[ReviewItem]:
        items = []
        status = self._resource_monitor.get_status()

        if status.disk_free_gb < 5.0:
            items.append(ReviewItem(
                name="磁盘空间检查",
                category="资源检查",
                status=ReviewStatus.WARNING,
                message=f"磁盘空间不足，剩余{status.disk_free_gb:.1f}GB",
                severity=7,
                suggestion="请清理磁盘空间",
            ))
        else:
            items.append(ReviewItem(
                name="磁盘空间检查",
                category="资源检查",
                status=ReviewStatus.PASSED,
                message=f"磁盘空间充足，剩余{status.disk_free_gb:.1f}GB",
            ))

        if params.get("use_gpu", False) and not status.gpu_available:
            items.append(ReviewItem(
                name="GPU可用性检查",
                category="资源检查",
                status=ReviewStatus.WARNING,
                message="启用GPU但系统无可用NVIDIA GPU",
                severity=8,
                suggestion="将自动降级为CPU模式",
            ))

        return items

    def _check_version_compatibility(self, params: Dict) -> List[ReviewItem]:
        items = []
        version_name = params.get("gromacs_version")

        if version_name:
            versions = self._gromacs_service.scan_versions()
            if version_name in versions:
                info = versions[version_name]
                if info.valid:
                    items.append(ReviewItem(
                        name="版本兼容性检查",
                        category="版本检查",
                        status=ReviewStatus.PASSED,
                        message=f"版本{version_name}有效，支持GPU={info.gpu}, PLUMED={info.plumed}",
                    ))
                else:
                    items.append(ReviewItem(
                        name="版本兼容性检查",
                        category="版本检查",
                        status=ReviewStatus.FAILED,
                        message=f"版本{version_name}无效，请检查安装",
                        severity=10,
                    ))
            else:
                items.append(ReviewItem(
                    name="版本兼容性检查",
                    category="版本检查",
                    status=ReviewStatus.FAILED,
                    message=f"版本{version_name}未找到",
                    severity=10,
                ))

        return items

    def _check_system_environment(self) -> List[ReviewItem]:
        items = []

        env_vars = ["CUDA_PATH", "PATH"]
        for env_var in env_vars:
            if env_var in os.environ:
                items.append(ReviewItem(
                    name=f"环境变量_{env_var}",
                    category="环境检查",
                    status=ReviewStatus.PASSED,
                    message=f"环境变量{env_var}已设置",
                ))
            else:
                items.append(ReviewItem(
                    name=f"环境变量_{env_var}",
                    category="环境检查",
                    status=ReviewStatus.WARNING,
                    message=f"环境变量{env_var}未设置",
                    severity=3,
                ))

        return items

    def _determine_overall_status(self, items: List[ReviewItem]) -> ReviewStatus:
        if any(i.status == ReviewStatus.FAILED for i in items):
            return ReviewStatus.FAILED
        if any(i.status == ReviewStatus.WARNING for i in items):
            return ReviewStatus.WARNING
        return ReviewStatus.PASSED

    def runtime_audit(self, task_name: str, pid: int, work_dir: str,
                      base_name: str) -> ReviewReport:
        start_time = time.time()
        items = []
        review_id = f"audit_{int(time.time())}"

        items.extend(self._check_process_alive(pid))
        items.extend(self._check_output_files(work_dir, base_name))
        items.extend(self._check_resources_during_run())

        overall_status = self._determine_overall_status(items)
        duration_ms = (time.time() - start_time) * 1000

        report = ReviewReport(
            review_id=review_id,
            level=ReviewLevel.QUICK,
            task_name=task_name,
            items=items,
            overall_status=overall_status,
            duration_ms=duration_ms,
        )

        with self._lock:
            self._reports[review_id] = report

        return report

    def _check_process_alive(self, pid: int) -> List[ReviewItem]:
        items = []
        try:
            if os.name == "nt":
                import ctypes
                kernel32 = ctypes.windll.kernel32
                handle = kernel32.OpenProcess(1, False, pid)
                if handle:
                    kernel32.CloseHandle(handle)
                    items.append(ReviewItem(
                        name="进程存活检查",
                        category="运行时检查",
                        status=ReviewStatus.PASSED,
                        message=f"进程{pid}运行中",
                    ))
                else:
                    items.append(ReviewItem(
                        name="进程存活检查",
                        category="运行时检查",
                        status=ReviewStatus.FAILED,
                        message=f"进程{pid}已终止",
                        severity=10,
                    ))
            else:
                try:
                    os.kill(pid, 0)
                    items.append(ReviewItem(
                        name="进程存活检查",
                        category="运行时检查",
                        status=ReviewStatus.PASSED,
                        message=f"进程{pid}运行中",
                    ))
                except OSError:
                    items.append(ReviewItem(
                        name="进程存活检查",
                        category="运行时检查",
                        status=ReviewStatus.FAILED,
                        message=f"进程{pid}已终止",
                        severity=10,
                    ))
        except Exception as e:
            items.append(ReviewItem(
                name="进程存活检查",
                category="运行时检查",
                status=ReviewStatus.WARNING,
                message=f"进程检查失败: {e}",
                severity=5,
            ))

        return items

    def _check_output_files(self, work_dir: str, base_name: str) -> List[ReviewItem]:
        items = []

        for ftype in ["edr", "log", "cpt"]:
            path = os.path.join(work_dir, f"{base_name}.{ftype}")
            if os.path.exists(path):
                size = os.path.getsize(path)
                items.append(ReviewItem(
                    name=f"输出文件_{ftype}",
                    category="运行时检查",
                    status=ReviewStatus.PASSED,
                    message=f"{ftype.upper()}文件存在，大小{size}字节",
                ))
            else:
                items.append(ReviewItem(
                    name=f"输出文件_{ftype}",
                    category="运行时检查",
                    status=ReviewStatus.WARNING,
                    message=f"{ftype.upper()}文件尚未生成",
                    severity=3,
                ))

        return items

    def _check_resources_during_run(self) -> List[ReviewItem]:
        items = []
        status = self._resource_monitor.get_status()

        if status.memory_percent > 90:
            items.append(ReviewItem(
                name="内存使用率检查",
                category="运行时检查",
                status=ReviewStatus.WARNING,
                message=f"内存使用率{status.memory_percent:.1f}%过高",
                severity=7,
                suggestion="注意内存使用情况",
            ))

        return items

    def post_execution_review(self, task_name: str, work_dir: str,
                              base_name: str) -> ReviewReport:
        start_time = time.time()
        items = []
        review_id = f"post_{int(time.time())}"

        items.extend(self._check_output_files(work_dir, base_name))
        items.extend(self._check_result_integrity(work_dir, base_name))
        items.extend(self._check_log_for_errors(work_dir, base_name))

        overall_status = self._determine_overall_status(items)
        duration_ms = (time.time() - start_time) * 1000

        report = ReviewReport(
            review_id=review_id,
            level=ReviewLevel.DEEP,
            task_name=task_name,
            items=items,
            overall_status=overall_status,
            duration_ms=duration_ms,
        )

        with self._lock:
            self._reports[review_id] = report

        return report

    def _check_result_integrity(self, work_dir: str, base_name: str) -> List[ReviewItem]:
        items = []

        essential_files = [f"{base_name}.trr", f"{base_name}.xtc", f"{base_name}.edr"]
        for fname in essential_files:
            path = os.path.join(work_dir, fname)
            if os.path.exists(path):
                size = os.path.getsize(path)
                if size > 0:
                    items.append(ReviewItem(
                        name=f"结果文件_{fname}",
                        category="结果检查",
                        status=ReviewStatus.PASSED,
                        message=f"{fname}文件完整，大小{size}字节",
                    ))
                else:
                    items.append(ReviewItem(
                        name=f"结果文件_{fname}",
                        category="结果检查",
                        status=ReviewStatus.WARNING,
                        message=f"{fname}文件为空",
                        severity=5,
                    ))
            else:
                items.append(ReviewItem(
                    name=f"结果文件_{fname}",
                    category="结果检查",
                    status=ReviewStatus.FAILED,
                    message=f"{fname}文件缺失",
                    severity=8,
                ))

        return items

    def _check_log_for_errors(self, work_dir: str, base_name: str) -> List[ReviewItem]:
        items = []
        log_path = os.path.join(work_dir, f"{base_name}.log")

        if os.path.exists(log_path):
            try:
                with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                if "Fatal error" in content or "Segmentation fault" in content:
                    items.append(ReviewItem(
                        name="日志错误扫描",
                        category="结果检查",
                        status=ReviewStatus.FAILED,
                        message="日志中发现致命错误",
                        severity=10,
                        suggestion="查看日志末尾了解详细错误",
                    ))
                elif "Warning" in content or "warning" in content:
                    items.append(ReviewItem(
                        name="日志错误扫描",
                        category="结果检查",
                        status=ReviewStatus.WARNING,
                        message="日志中包含警告信息",
                        severity=3,
                        suggestion="查看日志了解警告内容",
                    ))
                else:
                    items.append(ReviewItem(
                        name="日志错误扫描",
                        category="结果检查",
                        status=ReviewStatus.PASSED,
                        message="日志无致命错误",
                    ))
            except Exception as e:
                items.append(ReviewItem(
                    name="日志错误扫描",
                    category="结果检查",
                    status=ReviewStatus.WARNING,
                    message=f"读取日志失败: {e}",
                    severity=3,
                ))

        return items

    def get_report(self, review_id: str) -> ReviewReport:
        with self._lock:
            return self._reports.get(review_id)

    def get_recent_reports(self, limit: int = 10) -> List[ReviewReport]:
        with self._lock:
            return list(self._reports.values())[-limit:]
