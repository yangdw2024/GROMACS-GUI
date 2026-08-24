#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一日志系统
支持：文件日志、控制台日志、UI回调、日志级别控制、日志轮转
"""

import os
import sys
import datetime
import traceback
import threading
from pathlib import Path
from typing import Callable, List, Optional
from enum import Enum


class LogLevel(Enum):
    DEBUG = 0
    INFO = 1
    SUCCESS = 2
    WARNING = 3
    ERROR = 4
    CRITICAL = 5


LEVEL_NAMES = {
    LogLevel.DEBUG: "DEBUG",
    LogLevel.INFO: "INFO",
    LogLevel.SUCCESS: "SUCCESS",
    LogLevel.WARNING: "WARNING",
    LogLevel.ERROR: "ERROR",
    LogLevel.CRITICAL: "CRITICAL",
}

LEVEL_COLORS = {
    LogLevel.DEBUG: "\033[90m",
    LogLevel.INFO: "\033[36m",
    LogLevel.SUCCESS: "\033[32m",
    LogLevel.WARNING: "\033[33m",
    LogLevel.ERROR: "\033[31m",
    LogLevel.CRITICAL: "\033[35m",
}

RESET_COLOR = "\033[0m"


class AppLogger:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, name=None, log_file=None, log_dir=None, max_files=10):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, name=None, log_file=None, log_dir=None, max_files=10):
        if self._initialized:
            return

        self.name = name or "AppLogger"

        if log_dir is None:
            base_dir = Path(__file__).parent.parent
            log_dir = base_dir / "logs"

        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.max_files = max_files
        self._custom_log_file = log_file

        self._file_handle = None
        self._level_handles = {}  # 分级文件句柄
        self._current_log_file = None
        self._level = LogLevel.INFO
        self._ui_callbacks: List[Callable] = []
        self._lock = threading.Lock()

        self._cleanup_old_logs()
        self._open_new_log_file()
        self._open_level_log_files()
        self._initialized = True

    def _cleanup_old_logs(self):
        try:
            log_files = sorted(self.log_dir.glob("gromacs_gui_*.log"),
                               key=lambda p: p.stat().st_mtime,
                               reverse=True)
            for old_file in log_files[self.max_files:]:
                try:
                    old_file.unlink()
                except Exception:
                    pass
        except Exception:
            pass

    def _open_new_log_file(self):
        if self._custom_log_file:
            self._current_log_file = Path(self._custom_log_file)
        else:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            self._current_log_file = self.log_dir / f"gromacs_gui_{timestamp}.log"

        try:
            if self._file_handle:
                self._file_handle.close()
            self._file_handle = open(self._current_log_file, "w", encoding="utf-8")
            self._write_header()
        except Exception as e:
            print(f"[AppLogger] 无法创建日志文件: {e}")

    def _open_level_log_files(self):
        """为ERROR/WARNING/INFO/DEBUG级别分别创建独立日志文件"""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        level_files = {
            "error": self.log_dir / f"error_{timestamp}.log",
            "warning": self.log_dir / f"warning_{timestamp}.log",
            "info": self.log_dir / f"info_{timestamp}.log",
            "debug": self.log_dir / f"debug_{timestamp}.log",
        }
        for level_name, path in level_files.items():
            try:
                self._level_handles[level_name] = open(path, "w", encoding="utf-8")
                self._level_handles[level_name].write(
                    f"{'=' * 50}\n{level_name.upper()} LOG\n{level_name.upper()} LOG - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n{'=' * 50}\n"
                )
                self._level_handles[level_name].flush()
            except Exception:
                pass

    def _cleanup_expired_level_logs(self, days=30):
        """清理超过指定天数的INFO/DEBUG级别日志，ERROR日志永久保留"""
        try:
            import time
            now = time.time()
            for log_file in self.log_dir.glob("info_*.log"):
                if (now - log_file.stat().st_mtime) > days * 86400:
                    log_file.unlink()
            for log_file in self.log_dir.glob("debug_*.log"):
                if (now - log_file.stat().st_mtime) > days * 86400:
                    log_file.unlink()
            for log_file in self.log_dir.glob("warning_*.log"):
                if (now - log_file.stat().st_mtime) > days * 86400:
                    log_file.unlink()
            # error_*.log 永久保留，不清理
        except Exception:
            pass

    def _write_header(self):
        header = f"""{'=' * 70}
GROMACS GUI 运行日志
{'=' * 70}
启动时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Python版本: {sys.version}
操作系统: {sys.platform}
{'=' * 70}
"""
        if self._file_handle:
            self._file_handle.write(header)
            self._file_handle.flush()

    def set_level(self, level: LogLevel):
        self._level = level

    def add_ui_callback(self, callback: Callable):
        if callback not in self._ui_callbacks:
            self._ui_callbacks.append(callback)

    def remove_ui_callback(self, callback: Callable):
        if callback in self._ui_callbacks:
            self._ui_callbacks.remove(callback)

    def _should_log(self, level: LogLevel) -> bool:
        return level.value >= self._level.value

    def _format_message(self, level: LogLevel, message: str) -> str:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        level_name = LEVEL_NAMES.get(level, "UNKNOWN")
        return f"[{timestamp}] [{level_name:<8}] {message}"

    def log(self, level: LogLevel, message: str, exception: Exception = None):
        if not self._should_log(level):
            return

        formatted = self._format_message(level, message)

        with self._lock:
            # 写入主日志文件
            if self._file_handle:
                try:
                    self._file_handle.write(formatted + "\n")
                    if exception:
                        self._file_handle.write(traceback.format_exc() + "\n")
                    self._file_handle.flush()
                except Exception:
                    pass

            # 写入分级日志文件
            level_map = {
                LogLevel.DEBUG: "debug",
                LogLevel.INFO: "info",
                LogLevel.SUCCESS: "info",
                LogLevel.WARNING: "warning",
                LogLevel.ERROR: "error",
                LogLevel.CRITICAL: "error",
            }
            level_key = level_map.get(level)
            if level_key and level_key in self._level_handles:
                try:
                    self._level_handles[level_key].write(formatted + "\n")
                    if exception:
                        self._level_handles[level_key].write(traceback.format_exc() + "\n")
                    self._level_handles[level_key].flush()
                except Exception:
                    pass

            # 控制台输出（带颜色）
            if sys.platform != "win32" or "ANSICON" in os.environ:
                color = LEVEL_COLORS.get(level, "")
                print(f"{color}{formatted}{RESET_COLOR}")
            else:
                print(formatted)

            # 通知UI回调
            for cb in self._ui_callbacks:
                try:
                    cb(level, formatted, message)
                except Exception:
                    pass

    def debug(self, message: str):
        self.log(LogLevel.DEBUG, message)

    def info(self, message: str):
        self.log(LogLevel.INFO, message)

    def success(self, message: str):
        self.log(LogLevel.SUCCESS, message)

    def warning(self, message: str):
        self.log(LogLevel.WARNING, message)

    def error(self, message: str, exception: Exception = None):
        self.log(LogLevel.ERROR, message, exception)

    def critical(self, message: str, exception: Exception = None):
        self.log(LogLevel.CRITICAL, message, exception)

    def log_exception(self, exc_info=None):
        if exc_info is None:
            exc_info = sys.exc_info()
        exc_type, exc_value, exc_tb = exc_info
        if exc_type and exc_value:
            message = f"{exc_type.__name__}: {exc_value}"
            formatted = traceback.format_exception(exc_type, exc_value, exc_tb)
            with self._lock:
                if self._file_handle:
                    self._file_handle.write(f"{'=' * 50}\nEXCEPTION\n{'=' * 50}\n")
                    self._file_handle.writelines(formatted)
                    self._file_handle.write(f"{'=' * 50}\n")
                    self._file_handle.flush()

    def get_current_log_file(self) -> Optional[Path]:
        return self._current_log_file

    def get_recent_logs(self, lines: int = 100) -> List[str]:
        if not self._current_log_file or not self._current_log_file.exists():
            return []
        try:
            with open(self._current_log_file, "r", encoding="utf-8") as f:
                all_lines = f.readlines()
            return all_lines[-lines:]
        except Exception:
            return []

    def close(self):
        with self._lock:
            if self._file_handle:
                try:
                    self._file_handle.write(
                        f"\n{'=' * 70}\n"
                        f"日志结束: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                        f"{'=' * 70}\n"
                    )
                    self._file_handle.close()
                except Exception:
                    pass
                self._file_handle = None
            for handle in self._level_handles.values():
                try:
                    handle.close()
                except Exception:
                    pass
            self._level_handles.clear()

    def __del__(self):
        self.close()
