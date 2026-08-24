#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理器 - 统一管理所有配置项
支持：自动保存/加载、配置验证、默认值、变更通知
"""

import json
import os
import sys
import threading
from pathlib import Path
from typing import Any, Dict, Optional, Callable, List


def _get_app_root() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent.parent


class ConfigManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, config_file=None):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, config_file=None):
        if self._initialized:
            return

        if config_file is None:
            base_dir = _get_app_root()
            config_file = base_dir / "config" / "app_config.json"

        self.config_file = Path(config_file)
        self.config_file.parent.mkdir(parents=True, exist_ok=True)

        self._data: Dict[str, Any] = {}
        self._defaults = self._build_defaults()
        self._listeners: Dict[str, List[Callable]] = {}
        self._lock = threading.RLock()

        self._load()
        self._initialized = True

    def _build_defaults(self) -> Dict[str, Any]:
        return {
            # GROMACS版本配置
            "gromacs": {
                "selected_version": "",
                "versions": {},
                "auto_select_best": True,
                "version_scan_paths": [],
            },
            # 模拟参数默认值
            "simulation": {
                "nt": 8,
                "mem_limit_gb": 8.0,
                "mem_limit_enabled": False,
                "use_gpu": True,
                "gpu_id": 0,
                "pin": "on",
                "dlb": "yes",
                "nb": "gpu",
                "pme": "gpu",
                "auto_mode": True,
            },
            # 系统配置
            "system": {
                "work_dir": "",
                "theme": "dark",
                "language": "zh_CN",
                "log_level": "INFO",
                "auto_save_config": True,
            },
            # 资源限制
            "resources": {
                "max_memory_gb": 0,
                "max_cpu_cores": 0,
                "max_gpu_memory_mb": 0,
                "disk_warning_threshold_gb": 10.0,
            },
            # 监控配置
            "monitor": {
                "interval_seconds": 5,
                "auto_refresh": True,
                "max_history_points": 500,
                "alert_on_high_temp": True,
                "temp_threshold_k": 400.0,
            },
            # 历史记录
            "history": {
                "recent_projects": [],
                "max_recent": 10,
                "command_history": [],
            },
        }

    def _load(self):
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                self._data = self._merge_deep(self._defaults.copy(), loaded)
            except Exception as e:
                print(f"[ConfigManager] 加载配置失败: {e}, 使用默认配置")
                self._data = self._defaults.copy()
        else:
            self._data = self._defaults.copy()
            self._save()

    def _save(self):
        try:
            with self._lock:
                with open(self.config_file, "w", encoding="utf-8") as f:
                    json.dump(self._data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[ConfigManager] 保存配置失败: {e}")

    def _merge_deep(self, base: Dict, override: Dict) -> Dict:
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_deep(result[key], value)
            else:
                result[key] = value
        return result

    def get(self, key_path: str, default=None) -> Any:
        with self._lock:
            keys = key_path.split(".")
            value = self._data
            for key in keys:
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    return default
            return value

    def set(self, key_path: str, value: Any, auto_save: bool = True):
        # 关键参数边界校验：拒绝非法值
        validated_value = self._validate_key_value(key_path, value)

        with self._lock:
            keys = key_path.split(".")
            target = self._data
            for key in keys[:-1]:
                if key not in target:
                    target[key] = {}
                target = target[key]
            old_value = target.get(keys[-1])
            target[keys[-1]] = validated_value

        if old_value != validated_value:
            self._notify(key_path, validated_value)
        else:
            print(f"[ConfigManager] 值未变化，跳过通知: {key_path}")

        if auto_save and self.get("system.auto_save_config", True):
            self._save()

    def _validate_key_value(self, key_path: str, value: Any) -> Any:
        """关键参数边界校验：拒绝非法值，自动钳位到合法范围"""
        # 内存限制：不允许负数，不允许超过64GB
        if key_path == "simulation.mem_limit_gb":
            if isinstance(value, (int, float)):
                if value < 0:
                    print(f"[ConfigManager] 拒绝非法值 {key_path}={value}（负数），已钳位为0.5")
                    return 0.5
                if value > 64:
                    print(f"[ConfigManager] 拒绝非法值 {key_path}={value}（超大值），已钳位为64.0")
                    return 64.0
                if value == 0:
                    print(f"[ConfigManager] {key_path}=0 视为关闭限制，已钳位为0.5")
                    return 0.5
        # 系统最大内存：不允许负数
        if key_path == "resources.max_memory_gb":
            if isinstance(value, (int, float)):
                if value < 0:
                    print(f"[ConfigManager] 拒绝非法值 {key_path}={value}（负数），已钳位为0")
                    return 0
                if value > 128:
                    print(f"[ConfigManager] 拒绝非法值 {key_path}={value}（超大值），已钳位为128.0")
                    return 128.0
        # 线程数：不允许0或负数
        if key_path == "simulation.nt":
            if isinstance(value, int):
                if value < 1:
                    print(f"[ConfigManager] 拒绝非法值 {key_path}={value}（过小），已钳位为1")
                    return 1
                if value > 256:
                    print(f"[ConfigManager] 拒绝非法值 {key_path}={value}（过大），已钳位为256")
                    return 256
        return value

    def add_listener(self, key_path: str, callback: Callable):
        if key_path not in self._listeners:
            self._listeners[key_path] = []
        self._listeners[key_path].append(callback)

    def remove_listener(self, key_path: str, callback: Callable):
        if key_path in self._listeners and callback in self._listeners[key_path]:
            self._listeners[key_path].remove(callback)

    def _notify(self, key_path: str, value: Any):
        for pattern, callbacks in self._listeners.items():
            if key_path == pattern or key_path.startswith(pattern + "."):
                for cb in callbacks:
                    try:
                        cb(key_path, value)
                    except Exception as e:
                        print(f"[ConfigManager] 通知监听器失败: {e}")

    def get_all(self) -> Dict[str, Any]:
        with self._lock:
            return self._data.copy()

    def reset_to_defaults(self):
        with self._lock:
            self._data = self._defaults.copy()
        self._save()

    def export_to_file(self, filepath: str):
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"[ConfigManager] 导出配置失败: {e}")
            return False

    def import_from_file(self, filepath: str) -> bool:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            with self._lock:
                self._data = self._merge_deep(self._defaults.copy(), loaded)
            self._save()
            return True
        except Exception as e:
            print(f"[ConfigManager] 导入配置失败: {e}")
            return False

    def add_recent_project(self, path: str):
        recent = self.get("history.recent_projects", [])
        if path in recent:
            recent.remove(path)
        recent.insert(0, path)
        recent = recent[:self.get("history.max_recent", 10)]
        self.set("history.recent_projects", recent)

    def add_command_history(self, command: str):
        history = self.get("history.command_history", [])
        history.append(command)
        if len(history) > 50:
            history = history[-50:]
        self.set("history.command_history", history)
