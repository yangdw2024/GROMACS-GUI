#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
审计机制 - 参考ISO 27001审计要求、金融系统审计日志
实现：操作留痕、配置变更记录、模拟事件追踪、审计报告生成
"""

import os
import json
import time
import threading
from pathlib import Path
from typing import Dict, List, Any
from dataclasses import dataclass
from enum import Enum
from datetime import datetime


class AuditActionType(Enum):
    CONFIG_CHANGE = "config_change"
    SIMULATION_START = "simulation_start"
    SIMULATION_STOP = "simulation_stop"
    SIMULATION_COMPLETE = "simulation_complete"
    VERSION_CHANGE = "version_change"
    FILE_OPERATION = "file_operation"
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    ERROR_OCCURRED = "error_occurred"
    CORRECTION_APPLIED = "correction_applied"
    REVIEW_PERFORMED = "review_performed"
    WSL_ENV_CHECK = "wsl_env_check"
    WSL_GROMACS_UPDATE = "wsl_gromacs_update"
    WSL_COMMAND_EXECUTED = "wsl_command_executed"


@dataclass
class AuditRecord:
    record_id: str
    action_type: AuditActionType
    timestamp: float
    user: str
    description: str
    details: Dict[str, Any] = None
    ip_address: str = ""
    session_id: str = ""

    def __post_init__(self):
        if self.details is None:
            self.details = {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "action_type": self.action_type.value,
            "timestamp": self.timestamp,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat(),
            "user": self.user,
            "description": self.description,
            "details": self.details,
            "ip_address": self.ip_address,
            "session_id": self.session_id,
        }


class AuditMechanism:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, audit_dir=None):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, audit_dir=None):
        if self._initialized:
            return

        if audit_dir is None:
            base_dir = Path(__file__).parent.parent
            audit_dir = base_dir / "logs" / "audit"

        self.audit_dir = Path(audit_dir)
        self.audit_dir.mkdir(parents=True, exist_ok=True)

        self._records: List[AuditRecord] = []
        self._max_records = 10000
        self._current_session_id = str(id(self))[:8]
        self._lock = threading.Lock()
        self._user = "local_user"

        self._load_records()
        self._initialized = True

    def _load_records(self):
        try:
            recent_files = sorted(
                self.audit_dir.glob("audit_*.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )[:3]
            for f in recent_files:
                with open(f, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                    for record_data in data:
                        record = AuditRecord(
                            record_id=record_data["record_id"],
                            action_type=AuditActionType(record_data["action_type"]),
                            timestamp=record_data["timestamp"],
                            user=record_data["user"],
                            description=record_data["description"],
                            details=record_data.get("details", {}),
                            ip_address=record_data.get("ip_address", ""),
                            session_id=record_data.get("session_id", ""),
                        )
                        self._records.append(record)
            self._records = self._records[-self._max_records:]
        except Exception:
            pass

    def _save_records(self):
        try:
            timestamp = datetime.now().strftime("%Y%m%d")
            filename = self.audit_dir / f"audit_{timestamp}.json"

            records_to_save = [r.to_dict() for r in self._records[-5000:]]
            with open(filename, "w", encoding="utf-8") as fp:
                json.dump(records_to_save, fp, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _generate_id(self) -> str:
        return f"{int(time.time())}_{os.urandom(4).hex()}"

    def log_event(self, category, action, detail=""):
        self.log_action(AuditActionType.CONFIG_CHANGE, f"{category}: {action}", {"detail": detail})

    def log_action(self, action_type: AuditActionType, description: str,
                   details: Dict[str, Any] = None, user: str = None):
        record = AuditRecord(
            record_id=self._generate_id(),
            action_type=action_type,
            timestamp=time.time(),
            user=user or self._user,
            description=description,
            details=details,
            session_id=self._current_session_id,
        )

        with self._lock:
            self._records.append(record)
            if len(self._records) > self._max_records:
                self._records = self._records[-self._max_records:]

        self._save_records()

    def log_config_change(self, old_config: Dict, new_config: Dict, key_path: str, user: str = None):
        self.log_action(
            AuditActionType.CONFIG_CHANGE,
            f"配置变更: {key_path}",
            {
                "key_path": key_path,
                "old_value": old_config,
                "new_value": new_config,
            },
            user=user
        )

    def log_simulation_event(self, event_type: str, task_name: str,
                             details: Dict[str, Any] = None, user: str = None):
        action_map = {
            "start": AuditActionType.SIMULATION_START,
            "stop": AuditActionType.SIMULATION_STOP,
            "complete": AuditActionType.SIMULATION_COMPLETE,
        }

        action_type = action_map.get(event_type, AuditActionType.SIMULATION_START)
        self.log_action(
            action_type,
            f"模拟{event_type}: {task_name}",
            {"task_name": task_name, **(details or {})},
            user=user
        )

    def log_version_change(self, old_version: str, new_version: str, user: str = None):
        self.log_action(
            AuditActionType.VERSION_CHANGE,
            f"版本切换: {old_version} -> {new_version}",
            {"old_version": old_version, "new_version": new_version},
            user=user
        )

    def log_file_operation(self, operation: str, filepath: str, details: Dict[str, Any] = None):
        self.log_action(
            AuditActionType.FILE_OPERATION,
            f"文件操作: {operation} {filepath}",
            {"operation": operation, "filepath": filepath, **(details or {})},
        )

    def log_error(self, error_type: str, message: str, details: Dict[str, Any] = None):
        self.log_action(
            AuditActionType.ERROR_OCCURRED,
            f"错误发生: {error_type}",
            {"error_type": error_type, "message": message, **(details or {})},
        )

    def log_correction(self, correction_type: str, result: str, details: Dict[str, Any] = None):
        self.log_action(
            AuditActionType.CORRECTION_APPLIED,
            f"纠错应用: {correction_type}",
            {"correction_type": correction_type, "result": result, **(details or {})},
        )

    def log_review(self, review_type: str, result: str, details: Dict[str, Any] = None):
        self.log_action(
            AuditActionType.REVIEW_PERFORMED,
            f"审查完成: {review_type}",
            {"review_type": review_type, "result": result, **(details or {})},
        )

    def log_wsl_env_check(self, status: str, details: Dict[str, Any] = None):
        self.log_action(
            AuditActionType.WSL_ENV_CHECK,
            f"WSL环境检查: {status}",
            {"status": status, **(details or {})},
        )

    def log_wsl_gromacs_update(self, old_version: str, new_version: str, details: Dict[str, Any] = None):
        self.log_action(
            AuditActionType.WSL_GROMACS_UPDATE,
            f"WSL GROMACS更新: {old_version} -> {new_version}",
            {"old_version": old_version, "new_version": new_version, **(details or {})},
        )

    def log_wsl_command(self, command: str, return_code: int, details: Dict[str, Any] = None):
        self.log_action(
            AuditActionType.WSL_COMMAND_EXECUTED,
            f"WSL命令执行: {command[:80]}",
            {"command": command, "return_code": return_code, **(details or {})},
        )

    def generate_audit_trail(self, start_time: float = None,
                            end_time: float = None,
                            action_type: AuditActionType = None,
                            limit: int = 100) -> List[AuditRecord]:
        with self._lock:
            records = self._records.copy()

        if start_time:
            records = [r for r in records if r.timestamp >= start_time]
        if end_time:
            records = [r for r in records if r.timestamp <= end_time]
        if action_type:
            records = [r for r in records if r.action_type == action_type]

        records.sort(key=lambda r: r.timestamp, reverse=True)
        return records[:limit]

    def get_statistics(self) -> Dict[str, Any]:
        stats = {t.value: 0 for t in AuditActionType}
        for record in self._records:
            stats[record.action_type.value] += 1

        return {
            "total_records": len(self._records),
            "by_type": stats,
            "oldest_timestamp": min(r.timestamp for r in self._records) if self._records else None,
            "newest_timestamp": max(r.timestamp for r in self._records) if self._records else None,
        }

    def get_recent_actions(self, limit: int = 50) -> List[AuditRecord]:
        return self.generate_audit_trail(limit=limit)

    def export_to_file(self, filepath: str, start_time: float = None,
                       end_time: float = None) -> bool:
        try:
            records = self.generate_audit_trail(start_time, end_time)
            with open(filepath, "w", encoding="utf-8") as fp:
                json.dump([r.to_dict() for r in records], fp, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

    def cleanup_old_records(self, keep_days: int = 30):
        cutoff = time.time() - (keep_days * 24 * 60 * 60)
        try:
            for f in self.audit_dir.glob("audit_*.json"):
                if f.stat().st_mtime < cutoff:
                    f.unlink()
        except Exception:
            pass

        with self._lock:
            self._records = [r for r in self._records if r.timestamp >= cutoff]
