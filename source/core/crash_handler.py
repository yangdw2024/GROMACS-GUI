#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全局崩溃捕获框架
功能：捕获未处理异常、弹出前端提示框、一键导出崩溃日志
"""

import sys
import os
import traceback
import json
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Callable, Optional, Any
from dataclasses import dataclass, asdict

from .logger import AppLogger


@dataclass
class CrashReport:
    timestamp: str
    exception_type: str
    exception_message: str
    traceback: str
    thread_name: str
    system_info: Dict[str, Any]
    context: Dict[str, Any]
    crash_id: str

    def to_dict(self) -> Dict:
        return asdict(self)

    def to_text(self) -> str:
        lines = [
            "=" * 60,
            "GROMACS GUI 崩溃报告",
            "=" * 60,
            f"崩溃ID: {self.crash_id}",
            f"时间: {self.timestamp}",
            f"线程: {self.thread_name}",
            "",
            "--- 异常信息 ---",
            f"类型: {self.exception_type}",
            f"消息: {self.exception_message}",
            "",
            "--- 系统信息 ---",
        ]
        for key, value in self.system_info.items():
            lines.append(f"{key}: {value}")
        lines.extend([
            "",
            "--- 调用堆栈 ---",
            self.traceback,
            "",
            "--- 上下文 ---",
        ])
        for key, value in self.context.items():
            lines.append(f"{key}: {value}")
        lines.append("=" * 60)
        return "\n".join(lines)


class CrashHandler:
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

        self._logger = AppLogger("CrashHandler")
        self._crash_dir = Path(__file__).parent.parent / "logs" / "crashes"
        self._crash_dir.mkdir(parents=True, exist_ok=True)
        self._listeners: List[Callable[[CrashReport], None]] = []
        self._original_excepthook = sys.excepthook
        self._initialized = True

    def install(self):
        """安装全局异常捕获"""
        sys.excepthook = self._handle_exception
        self._logger.info("崩溃捕获框架已安装")

    def uninstall(self):
        """卸载全局异常捕获"""
        sys.excepthook = self._original_excepthook
        self._logger.info("崩溃捕获框架已卸载")

    def add_listener(self, callback: Callable[[CrashReport], None]):
        """添加崩溃监听器（用于前端弹窗）"""
        self._listeners.append(callback)

    def _handle_exception(self, exc_type, exc_value, exc_traceback):
        """处理未捕获异常"""
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        crash_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))

        report = CrashReport(
            timestamp=datetime.now().isoformat(),
            exception_type=exc_type.__name__,
            exception_message=str(exc_value),
            traceback=tb_str,
            thread_name=threading.current_thread().name,
            system_info=self._get_system_info(),
            context=self._get_context(),
            crash_id=crash_id
        )

        # 保存崩溃日志
        self._save_crash_log(report)

        # 打印到控制台
        print(f"\n{'='*60}")
        print(f"程序崩溃: {exc_type.__name__}: {exc_value}")
        print(f"崩溃日志已保存到: {self._crash_dir / f'crash_{crash_id}.log'}")
        print(f"{'='*60}\n")

        # 通知监听器
        for listener in self._listeners:
            try:
                listener(report)
            except Exception:
                pass

        # 调用原始异常处理
        self._original_excepthook(exc_type, exc_value, exc_traceback)

    def _save_crash_log(self, report: CrashReport):
        """保存崩溃日志到文件"""
        try:
            log_file = self._crash_dir / f"crash_{report.crash_id}.log"
            with open(log_file, "w", encoding="utf-8") as f:
                f.write(report.to_text())

            # 同时保存JSON格式
            json_file = self._crash_dir / f"crash_{report.crash_id}.json"
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            self._logger.error(f"保存崩溃日志失败: {e}")

    def _get_system_info(self) -> Dict[str, Any]:
        """获取系统信息"""
        info = {
            "platform": sys.platform,
            "python_version": sys.version,
            "cwd": str(Path.cwd()),
        }
        try:
            import platform
            info["os"] = platform.platform()
            info["processor"] = platform.processor()
        except Exception:
            pass
        return info

    def _get_context(self) -> Dict[str, Any]:
        """获取上下文信息"""
        return {
            "argv": sys.argv,
            "path": [str(p) for p in sys.path[:5]],
        }

    def get_crash_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取崩溃日志列表"""
        logs = []
        try:
            for f in sorted(self._crash_dir.glob("crash_*.json"), reverse=True):
                try:
                    with open(f, "r", encoding="utf-8") as fp:
                        data = json.load(fp)
                        data["file"] = str(f)
                        logs.append(data)
                except Exception:
                    pass
        except Exception:
            pass
        return logs[:limit]

    def export_crash_log(self, crash_id: str, output_path: str = None) -> str:
        """导出指定崩溃日志"""
        log_file = self._crash_dir / f"crash_{crash_id}.log"
        if not log_file.exists():
            return ""

        if output_path is None:
            output_path = str(Path.cwd() / f"GROMACS崩溃报告_{crash_id}.txt")

        try:
            import shutil
            shutil.copy2(str(log_file), output_path)
            return output_path
        except Exception as e:
            self._logger.error(f"导出崩溃日志失败: {e}")
            return ""

    def clear_all_logs(self):
        """清理所有崩溃日志"""
        try:
            for f in self._crash_dir.glob("crash_*"):
                f.unlink()
            self._logger.info("已清理所有崩溃日志")
        except Exception as e:
            self._logger.error(f"清理崩溃日志失败: {e}")