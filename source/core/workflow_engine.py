#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工作流引擎 - 管理模拟任务的生命周期
提供：任务队列、状态跟踪、断点续跑、自动恢复、依赖管理
"""

import os
import json
import time
import uuid
import threading
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime

from .logger import AppLogger
from .error_handler import ErrorHandler, GromacsError
from .gromacs_service import GromacsService, CommandType


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskType(Enum):
    PREPROCESS = "preprocess"
    SIMULATION = "simulation"
    ANALYSIS = "analysis"
    MONITORING = "monitoring"


@dataclass
class Task:
    id: str
    name: str
    type: TaskType
    status: TaskStatus
    command: List[str]
    work_dir: str
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    progress: float = 0.0
    checkpoint_file: Optional[str] = None
    resume_capable: bool = False
    retry_count: int = 0
    max_retries: int = 3
    env: Optional[Dict[str, str]] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["type"] = self.type.value
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, data: Dict) -> "Task":
        data = data.copy()
        data["type"] = TaskType(data["type"])
        data["status"] = TaskStatus(data["status"])
        return cls(**data)


class WorkflowEngine:
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

        self._tasks: Dict[str, Task] = {}
        self._task_order: List[str] = []
        self._current_task: Optional[str] = None
        self._listeners: List[Callable] = []
        self._lock = threading.Lock()
        self._logger = AppLogger()
        self._error_handler = ErrorHandler()
        self._gromacs = GromacsService()

        self._state_file = Path(__file__).parent.parent / "config" / "workflow_state.json"
        self._state_file.parent.mkdir(parents=True, exist_ok=True)

        self._load_state()
        self._initialized = True

    def _load_state(self):
        if self._state_file.exists():
            try:
                with open(self._state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for task_data in data.get("tasks", []):
                    task = Task.from_dict(task_data)
                    self._tasks[task.id] = task
                self._task_order = data.get("order", [])
                self._current_task = data.get("current_task")
            except Exception as e:
                self._logger.warning(f"加载工作流状态失败: {e}")

    def _save_state(self):
        try:
            with self._lock:
                data = {
                    "tasks": [t.to_dict() for t in self._tasks.values()],
                    "order": self._task_order,
                    "current_task": self._current_task,
                    "saved_at": datetime.now().isoformat(),
                }
            with open(self._state_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self._logger.warning(f"保存工作流状态失败: {e}")

    def create_task(self, name: str, task_type: TaskType,
                    command: List[str], work_dir: str,
                    resume_capable: bool = False,
                    metadata: Dict = None) -> Task:
        task = Task(
            id=str(uuid.uuid4())[:8],
            name=name,
            type=task_type,
            status=TaskStatus.PENDING,
            command=command,
            work_dir=work_dir,
            created_at=datetime.now().isoformat(),
            resume_capable=resume_capable,
            metadata=metadata or {},
        )

        with self._lock:
            self._tasks[task.id] = task
            self._task_order.append(task.id)

        self._save_state()
        self._logger.info(f"创建任务: {name} [{task.id}]")
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    def get_all_tasks(self) -> List[Task]:
        return [self._tasks[tid] for tid in self._task_order if tid in self._tasks]

    def update_task_status(self, task_id: str, status: TaskStatus,
                          progress: float = None, error: str = None):
        task = self._tasks.get(task_id)
        if not task:
            return

        task.status = status
        if progress is not None:
            task.progress = progress
        if error:
            task.error_message = error

        if status == TaskStatus.RUNNING and not task.started_at:
            task.started_at = datetime.now().isoformat()
        if status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            task.completed_at = datetime.now().isoformat()

        self._save_state()

        for listener in self._listeners:
            try:
                listener(task)
            except Exception:
                pass

    def can_resume(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if not task or not task.resume_capable:
            return False
        if task.checkpoint_file and os.path.exists(task.checkpoint_file):
            return True
        # 尝试自动发现checkpoint
        if task.work_dir:
            base_name = task.metadata.get("base_name", "")
            if base_name:
                cpt = Path(task.work_dir) / f"{base_name}.cpt"
                if cpt.exists():
                    task.checkpoint_file = str(cpt)
                    return True
        return False

    def get_resume_command(self, task_id: str) -> Optional[List[str]]:
        task = self._tasks.get(task_id)
        if not task:
            return None

        cmd = task.command.copy()
        # 添加续跑参数
        if task.checkpoint_file:
            # mdrun会自动检测cpt文件
            if "-cpi" not in cmd:
                cmd.append("-cpi")
                cmd.append(task.checkpoint_file)
        return cmd

    def add_listener(self, callback: Callable):
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable):
        if callback in self._listeners:
            self._listeners.remove(callback)

    def get_failed_tasks(self) -> List[Task]:
        return [t for t in self._tasks.values() if t.status == TaskStatus.FAILED]

    def get_resumable_tasks(self) -> List[Task]:
        return [t for t in self._tasks.values()
                if t.status in (TaskStatus.FAILED, TaskStatus.CANCELLED)
                and self.can_resume(t.id)]

    def clear_completed(self):
        with self._lock:
            to_remove = [tid for tid, t in self._tasks.items()
                        if t.status == TaskStatus.COMPLETED]
            for tid in to_remove:
                del self._tasks[tid]
                if tid in self._task_order:
                    self._task_order.remove(tid)
        self._save_state()

    def clear_all(self):
        with self._lock:
            self._tasks.clear()
            self._task_order.clear()
            self._current_task = None
        self._save_state()

    def get_statistics(self) -> Dict[str, int]:
        stats = {s.value: 0 for s in TaskStatus}
        for task in self._tasks.values():
            stats[task.status.value] += 1
        return stats
