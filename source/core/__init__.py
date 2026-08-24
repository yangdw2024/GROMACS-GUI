"""
GROMACS GUI 核心框架层
提供配置管理、日志、异常处理、资源监控、版本管理等基础服务
"""

from .config_manager import ConfigManager
from .logger import AppLogger
from .error_handler import ErrorHandler, GromacsError, ErrorCategory, ErrorSeverity
from .resource_monitor import ResourceMonitor
from .gromacs_service import GromacsService
from .wsl_gromacs_service import WslGromacsService
from .workflow_engine import WorkflowEngine, TaskType, TaskStatus
from .event_bus import EventBus, EventBusMixin, EventPriority
from .review_mechanism import ReviewMechanism, ReviewLevel, ReviewStatus, ReviewReport
from .correction_mechanism import CorrectionMechanism, CorrectionAction, CorrectionStatus
from .audit_mechanism import AuditMechanism, AuditActionType
from .auto_updater import AutoUpdater, UpdateStatus, UpdateChannel
from .version_manager import VersionManager, VersionMetadata, PlumedStatus, VersionValidity
from .crash_handler import CrashHandler, CrashReport

__all__ = [
    "ConfigManager",
    "AppLogger",
    "ErrorHandler",
    "GromacsError",
    "ErrorCategory",
    "ErrorSeverity",
    "ResourceMonitor",
    "GromacsService",
    "WslGromacsService",
    "WorkflowEngine",
    "TaskType",
    "TaskStatus",
    "EventBus",
    "EventBusMixin",
    "EventPriority",
    "ReviewMechanism",
    "ReviewLevel",
    "ReviewStatus",
    "ReviewReport",
    "CorrectionMechanism",
    "CorrectionAction",
    "CorrectionStatus",
    "AuditMechanism",
    "AuditActionType",
    "AutoUpdater",
    "UpdateStatus",
    "UpdateChannel",
    "VersionManager",
    "VersionMetadata",
    "PlumedStatus",
    "VersionValidity",
    "CrashHandler",
    "CrashReport",
]
