#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一错误处理器
提供：异常分类、错误诊断、自动恢复、崩溃报告、安全退出
"""

import sys
import os
import json
import traceback
import datetime
import threading
from pathlib import Path
from typing import Dict, List, Callable, Optional, Any
from enum import Enum


class ErrorCategory(Enum):
    UNKNOWN = "unknown"
    CONFIG = "config"
    FILE_IO = "file_io"
    NETWORK = "network"
    GPU = "gpu"
    CPU = "cpu"
    MEMORY = "memory"
    GROMACS = "gromacs"
    PLUMED = "plumed"
    UI = "ui"
    THREAD = "thread"
    SUBPROCESS = "subprocess"


class ErrorSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class GromacsError(Exception):
    def __init__(self, message, category=ErrorCategory.UNKNOWN,
                 severity=ErrorSeverity.MEDIUM, recoverable=False,
                 suggestion="", context=None):
        super().__init__(message)
        self.category = category
        self.severity = severity
        self.recoverable = recoverable
        self.suggestion = suggestion
        self.context = context or {}
        self.timestamp = datetime.datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message": str(self),
            "category": self.category.value,
            "severity": self.severity.value,
            "recoverable": self.recoverable,
            "suggestion": self.suggestion,
            "timestamp": self.timestamp,
            "context": self.context,
        }


class ErrorHandler:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, crash_dir=None):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, crash_dir=None):
        if self._initialized:
            return

        if crash_dir is None:
            base_dir = Path(__file__).parent.parent
            crash_dir = base_dir / "logs" / "crashes"

        self.crash_dir = Path(crash_dir)
        self.crash_dir.mkdir(parents=True, exist_ok=True)

        self._error_history: List[Dict] = []
        self._max_history = 100
        self._listeners: List[Callable] = []
        self._original_excepthook = sys.excepthook
        self._lock = threading.Lock()

        self._setup_global_handler()
        self._initialized = True

    def _setup_global_handler(self):
        sys.excepthook = self._global_exception_handler

    def _global_exception_handler(self, exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            return self._original_excepthook(exc_type, exc_value, exc_tb)

        crash_report = self._generate_crash_report(exc_type, exc_value, exc_tb)
        crash_file = self._save_crash_report(crash_report)

        # 通知监听器
        for listener in self._listeners:
            try:
                listener(crash_report, crash_file)
            except Exception:
                pass

        # 记录到历史
        self._add_to_history({
            "type": "uncaught",
            "message": str(exc_value),
            "traceback": traceback.format_exception(exc_type, exc_value, exc_tb),
            "crash_file": str(crash_file) if crash_file else None,
            "time": datetime.datetime.now().isoformat(),
        })

        # 最后调用原始的异常处理
        self._original_excepthook(exc_type, exc_value, exc_tb)

    def _generate_crash_report(self, exc_type, exc_value, exc_tb) -> Dict[str, Any]:
        return {
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "python_version": sys.version,
            "platform": sys.platform,
            "executable": sys.executable,
            "exception_type": exc_type.__name__ if exc_type else "Unknown",
            "exception_message": str(exc_value) if exc_value else "",
            "traceback": traceback.format_exception(exc_type, exc_value, exc_tb),
            "sys_path": sys.path[:10],
            "environment": {k: v for k, v in os.environ.items()
                          if any(x in k.lower() for x in [
                              "path", "cuda", "gromacs", "python",
                              "gpu", "nvidia", "plumed"
                          ])},
        }

    def _save_crash_report(self, report: Dict) -> Optional[Path]:
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            crash_file = self.crash_dir / f"crash_{timestamp}.json"
            with open(crash_file, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            return crash_file
        except Exception as e:
            print(f"[ErrorHandler] 无法保存崩溃报告: {e}")
            return None

    def _add_to_history(self, error_info: Dict):
        with self._lock:
            self._error_history.append(error_info)
            if len(self._error_history) > self._max_history:
                self._error_history = self._error_history[-self._max_history:]

    def add_listener(self, callback: Callable):
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable):
        if callback in self._listeners:
            self._listeners.remove(callback)

    def handle(self, exception: Exception, context: Dict = None) -> GromacsError:
        if isinstance(exception, GromacsError):
            gerror = exception
        else:
            gerror = self._classify_error(exception, context)

        self._add_to_history({
            "type": "handled",
            **gerror.to_dict(),
            "time": datetime.datetime.now().isoformat(),
        })

        return gerror

    def _classify_error(self, exception: Exception, context: Dict = None) -> GromacsError:
        message = str(exception)
        exc_type = type(exception).__name__
        context = context or {}

        # 根据异常类型和消息内容分类
        if "cuda" in message.lower() or "gpu" in message.lower() or "nvidia" in message.lower():
            return GromacsError(
                message, ErrorCategory.GPU, ErrorSeverity.HIGH,
                recoverable=False,
                suggestion="检查GPU驱动、CUDA版本兼容性，尝试使用CPU模式",
                context=context
            )
        elif "memory" in message.lower() or "alloc" in message.lower():
            return GromacsError(
                message, ErrorCategory.MEMORY, ErrorSeverity.HIGH,
                recoverable=False,
                suggestion="降低模拟规模、减少线程数、增加内存限制",
                context=context
            )
        elif "permission" in message.lower() or "access" in message.lower():
            return GromacsError(
                message, ErrorCategory.FILE_IO, ErrorSeverity.MEDIUM,
                recoverable=True,
                suggestion="检查文件权限、确保工作目录可写",
                context=context
            )
        elif "not found" in message.lower() or "no such file" in message.lower():
            return GromacsError(
                message, ErrorCategory.FILE_IO, ErrorSeverity.MEDIUM,
                recoverable=True,
                suggestion="检查文件路径是否正确、文件是否存在",
                context=context
            )
        elif "gromacs" in message.lower() or "gmx" in message.lower():
            return GromacsError(
                message, ErrorCategory.GROMACS, ErrorSeverity.HIGH,
                recoverable=False,
                suggestion="检查GROMACS版本兼容性、输入文件格式",
                context=context
            )
        elif "plumed" in message.lower():
            return GromacsError(
                message, ErrorCategory.PLUMED, ErrorSeverity.HIGH,
                recoverable=False,
                suggestion="检查PLUMED配置、colvar文件格式",
                context=context
            )
        elif "subprocess" in message.lower() or "timeout" in message.lower():
            return GromacsError(
                message, ErrorCategory.SUBPROCESS, ErrorSeverity.MEDIUM,
                recoverable=True,
                suggestion="检查命令是否正确、增加超时时间",
                context=context
            )
        elif "thread" in message.lower():
            return GromacsError(
                message, ErrorCategory.THREAD, ErrorSeverity.HIGH,
                recoverable=False,
                suggestion="检查线程同步、避免跨线程访问UI",
                context=context
            )
        elif "config" in message.lower():
            return GromacsError(
                message, ErrorCategory.CONFIG, ErrorSeverity.MEDIUM,
                recoverable=True,
                suggestion="检查配置文件格式、重置为默认配置",
                context=context
            )
        else:
            return GromacsError(
                message, ErrorCategory.UNKNOWN, ErrorSeverity.MEDIUM,
                recoverable=False,
                suggestion="查看详细错误日志，尝试重启程序",
                context=context
            )

    def get_error_history(self, category: ErrorCategory = None,
                         severity: ErrorSeverity = None,
                         limit: int = 50) -> List[Dict]:
        with self._lock:
            results = self._error_history.copy()

        if category:
            results = [e for e in results
                      if e.get("category") == category.value]
        if severity:
            results = [e for e in results
                      if e.get("severity") == severity.value]

        return results[-limit:]

    def clear_history(self):
        with self._lock:
            self._error_history.clear()

    def get_crash_files(self) -> List[Path]:
        try:
            return sorted(self.crash_dir.glob("crash_*.json"),
                         key=lambda p: p.stat().st_mtime,
                         reverse=True)
        except Exception:
            return []

    def safe_call(self, func: Callable, *args, **kwargs) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            gerror = self.handle(e, {"func": func.__name__})
            raise gerror

    def cleanup_old_crashes(self, keep_last: int = 20):
        try:
            crash_files = sorted(self.crash_dir.glob("crash_*.json"),
                                key=lambda p: p.stat().st_mtime,
                                reverse=True)
            for old_file in crash_files[keep_last:]:
                try:
                    old_file.unlink()
                except Exception:
                    pass
        except Exception:
            pass
