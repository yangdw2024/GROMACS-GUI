#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
纠错机制 - 参考NASA故障检测与纠正（FDIR）机制
实现：自动检测、自动修复、降级处理、回滚策略
"""

import os
import time
import threading
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum

from .error_handler import GromacsError, ErrorCategory, ErrorSeverity
from .resource_monitor import ResourceMonitor
from .gromacs_service import GromacsService
from .event_bus import EventBus


class CorrectionAction(Enum):
    AUTO_FIX = "auto_fix"
    DEGRADE = "degrade"
    ROLLBACK = "rollback"
    RETRY = "retry"
    WAIT = "wait"
    MANUAL = "manual"


class CorrectionStatus(Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class CorrectionResult:
    status: CorrectionStatus
    action: CorrectionAction
    message: str
    changes: Dict[str, Any] = None
    retry_count: int = 0
    suggestion: str = ""

    def __post_init__(self):
        if self.changes is None:
            self.changes = {}


class CorrectionMechanism:
    def __init__(self):
        self._event_bus = EventBus()
        self._resource_monitor = ResourceMonitor()
        self._gromacs_service = GromacsService()
        self._lock = threading.Lock()
        self._max_retries = 3
        self._retry_delay = 5.0

    def auto_correct(self, error: GromacsError, context: Dict[str, Any] = None) -> CorrectionResult:
        context = {**error.context, **(context or {})}

        strategies = {
            ErrorCategory.FILE_IO: self._fix_file_issues,
            ErrorCategory.GPU: self._fix_gpu_issues,
            ErrorCategory.MEMORY: self._fix_memory_issues,
            ErrorCategory.GROMACS: self._fix_gromacs_issues,
            ErrorCategory.PLUMED: self._fix_plumed_issues,
            ErrorCategory.CONFIG: self._fix_config_issues,
            ErrorCategory.SUBPROCESS: self._fix_subprocess_issues,
        }

        if error.category in strategies:
            try:
                result = strategies[error.category](error, context)
                if result.status == CorrectionStatus.SUCCESS:
                    self._event_bus.publish(
                        "correction.success",
                        {"error": error.to_dict(), "result": result.__dict__}
                    )
                return result
            except Exception as e:
                return CorrectionResult(
                    status=CorrectionStatus.FAILED,
                    action=CorrectionAction.MANUAL,
                    message=f"自动纠错失败: {e}",
                    suggestion=error.suggestion,
                )
        else:
            return CorrectionResult(
                status=CorrectionStatus.SKIPPED,
                action=CorrectionAction.MANUAL,
                message=f"无法处理的错误类别: {error.category.value}",
                suggestion=error.suggestion,
            )

    def _fix_file_issues(self, error: GromacsError, context: Dict) -> CorrectionResult:
        message = str(error).lower()
        changes = {}

        if "not found" in message or "no such file" in message:
            for key in ["work_dir", "input_dir"]:
                path = context.get(key)
                if path and not os.path.exists(path):
                    try:
                        os.makedirs(path, exist_ok=True)
                        changes[key] = {"action": "create_dir", "path": path}
                        return CorrectionResult(
                            status=CorrectionStatus.SUCCESS,
                            action=CorrectionAction.AUTO_FIX,
                            message=f"创建缺失目录: {path}",
                            changes=changes,
                        )
                    except Exception as e:
                        return CorrectionResult(
                            status=CorrectionStatus.FAILED,
                            action=CorrectionAction.MANUAL,
                            message=f"创建目录失败: {e}",
                            suggestion="请手动创建工作目录",
                        )

        if "permission" in message or "access denied" in message:
            return CorrectionResult(
                status=CorrectionStatus.FAILED,
                action=CorrectionAction.MANUAL,
                message="文件权限不足",
                suggestion="请检查文件权限，确保程序具有读写权限",
            )

        if "file is being used" in message or "in use" in message:
            retry_count = context.get("retry_count", 0)
            if retry_count < self._max_retries:
                time.sleep(self._retry_delay * (2 ** retry_count))
                return CorrectionResult(
                    status=CorrectionStatus.PARTIAL,
                    action=CorrectionAction.RETRY,
                    message=f"文件被占用，等待后重试 ({retry_count + 1}/{self._max_retries})",
                    retry_count=retry_count + 1,
                )
            else:
                return CorrectionResult(
                    status=CorrectionStatus.FAILED,
                    action=CorrectionAction.MANUAL,
                    message="文件持续被占用，请关闭其他程序后重试",
                )

        return CorrectionResult(
            status=CorrectionStatus.SKIPPED,
            action=CorrectionAction.MANUAL,
            message="未知的文件错误",
            suggestion=error.suggestion,
        )

    def _fix_gpu_issues(self, error: GromacsError, context: Dict) -> CorrectionResult:
        changes = {}

        if not self._resource_monitor.get_status().gpu_available:
            if context.get("use_gpu", True):
                changes["use_gpu"] = {"old": True, "new": False}
                return CorrectionResult(
                    status=CorrectionStatus.SUCCESS,
                    action=CorrectionAction.DEGRADE,
                    message="GPU不可用，自动降级为CPU模式",
                    changes=changes,
                    suggestion="如需GPU加速，请检查NVIDIA驱动和CUDA安装",
                )

        if "out of memory" in str(error).lower():
            mem_limit = context.get("mem_limit_gb", 6.0)
            new_limit = mem_limit * 0.8
            changes["mem_limit_gb"] = {"old": mem_limit, "new": new_limit}
            return CorrectionResult(
                status=CorrectionStatus.SUCCESS,
                action=CorrectionAction.AUTO_FIX,
                message=f"GPU显存不足，降低内存限制从{mem_limit}GB到{new_limit}GB",
                changes=changes,
            )

        return CorrectionResult(
            status=CorrectionStatus.SKIPPED,
            action=CorrectionAction.MANUAL,
            message="未知的GPU错误",
            suggestion=error.suggestion,
        )

    def _fix_memory_issues(self, error: GromacsError, context: Dict) -> CorrectionResult:
        changes = {}
        status = self._resource_monitor.get_status()

        if status.memory_percent > 90:
            nt = context.get("nt", 8)
            new_nt = max(1, nt // 2)
            if new_nt != nt:
                changes["nt"] = {"old": nt, "new": new_nt}
                return CorrectionResult(
                    status=CorrectionStatus.SUCCESS,
                    action=CorrectionAction.AUTO_FIX,
                    message=f"内存使用率过高({status.memory_percent:.1f}%)，降低线程数从{nt}到{new_nt}",
                    changes=changes,
                )

        mem_limit = context.get("mem_limit_gb", 6.0)
        available_mem = status.memory_total_gb - status.memory_used_gb
        if mem_limit > available_mem * 0.8:
            new_limit = available_mem * 0.7
            changes["mem_limit_gb"] = {"old": mem_limit, "new": new_limit}
            return CorrectionResult(
                status=CorrectionStatus.SUCCESS,
                action=CorrectionAction.AUTO_FIX,
                message=f"可用内存不足，降低内存限制从{mem_limit}GB到{new_limit:.1f}GB",
                changes=changes,
            )

        return CorrectionResult(
            status=CorrectionStatus.SKIPPED,
            action=CorrectionAction.MANUAL,
            message="内存问题无法自动修复",
            suggestion="请关闭其他程序或增加系统内存",
        )

    def _fix_gromacs_issues(self, error: GromacsError, context: Dict) -> CorrectionResult:
        message = str(error).lower()

        if "version" in message or "compatibility" in message:
            best_version = self._gromacs_service.get_best_version()
            if best_version:
                changes = {"gromacs_version": {"old": context.get("version"), "new": best_version[0]}}
                return CorrectionResult(
                    status=CorrectionStatus.SUCCESS,
                    action=CorrectionAction.AUTO_FIX,
                    message=f"版本不兼容，自动切换到最佳版本: {best_version[0]}",
                    changes=changes,
                )

        if "input file" in message or "format" in message:
            return CorrectionResult(
                status=CorrectionStatus.FAILED,
                action=CorrectionAction.MANUAL,
                message="输入文件格式错误",
                suggestion="请检查输入文件格式是否正确",
            )

        return CorrectionResult(
            status=CorrectionStatus.SKIPPED,
            action=CorrectionAction.MANUAL,
            message="未知的GROMACS错误",
            suggestion=error.suggestion,
        )

    def _fix_plumed_issues(self, error: GromacsError, context: Dict) -> CorrectionResult:
        if "plumed" in str(error).lower() and context.get("use_plumed", False):
            return CorrectionResult(
                status=CorrectionStatus.SUCCESS,
                action=CorrectionAction.DEGRADE,
                message="PLUMED错误，禁用PLUMED继续运行",
                changes={"use_plumed": {"old": True, "new": False}},
                suggestion="如需PLUMED支持，请检查PLUMED配置和安装",
            )

        return CorrectionResult(
            status=CorrectionStatus.SKIPPED,
            action=CorrectionAction.MANUAL,
            message="未知的PLUMED错误",
            suggestion=error.suggestion,
        )

    def _fix_config_issues(self, error: GromacsError, context: Dict) -> CorrectionResult:
        return CorrectionResult(
            status=CorrectionStatus.SUCCESS,
            action=CorrectionAction.ROLLBACK,
            message="配置错误，恢复默认配置",
            changes={"config": {"action": "reset_to_defaults"}},
            suggestion="配置已重置，请重新检查设置",
        )

    def _fix_subprocess_issues(self, error: GromacsError, context: Dict) -> CorrectionResult:
        message = str(error).lower()

        if "timeout" in message:
            timeout = context.get("timeout", 300)
            new_timeout = timeout * 2
            changes = {"timeout": {"old": timeout, "new": new_timeout}}
            return CorrectionResult(
                status=CorrectionStatus.SUCCESS,
                action=CorrectionAction.AUTO_FIX,
                message=f"命令执行超时，增加超时时间从{timeout}s到{new_timeout}s",
                changes=changes,
            )

        retry_count = context.get("retry_count", 0)
        if retry_count < self._max_retries:
            return CorrectionResult(
                status=CorrectionStatus.PARTIAL,
                action=CorrectionAction.RETRY,
                message=f"子进程错误，重试中 ({retry_count + 1}/{self._max_retries})",
                retry_count=retry_count + 1,
            )

        return CorrectionResult(
            status=CorrectionStatus.FAILED,
            action=CorrectionAction.MANUAL,
            message="子进程连续失败",
            suggestion="请检查命令参数或系统环境",
        )

    def retry_operation(self, func, *args, max_retries=3, delay=5.0, **kwargs):
        last_error = None
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    self._event_bus.publish(
                        "correction.retry",
                        {"attempt": attempt + 1, "max_retries": max_retries, "error": str(e)}
                    )
                    time.sleep(delay * (2 ** attempt))

        raise last_error
