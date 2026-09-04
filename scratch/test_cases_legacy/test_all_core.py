#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全面测试脚本 - 检测所有核心机制功能是否正常
"""

import os
import sys
import json
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

results = {
    "total_tests": 0,
    "passed": 0,
    "failed": 0,
    "warnings": 0,
    "tests": [],
}


def test(name, func):
    results["total_tests"] += 1
    print(f"\n{'='*60}")
    print(f"测试: {name}")
    print(f"{'='*60}")
    start_time = time.time()
    try:
        result = func()
        elapsed = time.time() - start_time
        if result is False:
            results["failed"] += 1
            print(f"❌ FAILED - {elapsed:.2f}s")
            results["tests"].append({"name": name, "status": "FAILED", "time": elapsed})
        else:
            results["passed"] += 1
            print(f"✅ PASSED - {elapsed:.2f}s")
            results["tests"].append({"name": name, "status": "PASSED", "time": elapsed})
    except Exception as e:
        elapsed = time.time() - start_time
        results["failed"] += 1
        print(f"❌ ERROR - {elapsed:.2f}s")
        print(f"  错误: {e}")
        traceback.print_exc()
        results["tests"].append({"name": name, "status": "ERROR", "time": elapsed, "error": str(e)})


def test_config_manager():
    from core import ConfigManager
    cfg = ConfigManager()
    print("  - 获取配置")
    val = cfg.get("system.theme", "dark")
    assert val in ("dark", "light"), f"主题配置错误: {val}"
    print("  - 设置配置")
    cfg.set("test.key", "test_value")
    assert cfg.get("test.key") == "test_value", "设置配置失败"
    print("  - 变更监听")
    callback_called = []
    def on_change(key, value):
        callback_called.append((key, value))
    cfg.add_listener("test", on_change)
    unique_key = f"test.key_{int(time.time())}"
    cfg.set(unique_key, "unique_value")
    assert len(callback_called) >= 1, f"监听未触发，回调次数: {len(callback_called)}"
    print("  - 导入导出")
    temp_file = Path(__file__).parent / "test_config_export.json"
    cfg.export_to_file(str(temp_file))
    assert temp_file.exists(), "导出失败"
    cfg.set("test.key3", "value3")
    cfg.import_from_file(str(temp_file))
    assert cfg.get("test.key3") is None, "导入后旧值未清除"
    temp_file.unlink()
    print("  - 添加最近项目")
    cfg.add_recent_project("/test/path")
    recent = cfg.get("history.recent_projects")
    assert "/test/path" in recent, "最近项目添加失败"
    print("  ✅ ConfigManager测试通过")


def test_logger():
    from core import AppLogger
    log = AppLogger()
    print("  - 测试各级别日志")
    log.debug("调试测试")
    log.info("信息测试")
    log.success("成功测试")
    log.warning("警告测试")
    log.error("错误测试")
    log.critical("严重错误测试")
    print("  - UI回调")
    received = []
    def ui_handler(level, formatted, message):
        received.append((level, message))
    log.add_ui_callback(ui_handler)
    log.info("回调测试消息")
    assert len(received) >= 1, "UI回调未触发"
    print("  - 获取日志文件")
    log_file = log.get_current_log_file()
    assert log_file is not None and log_file.exists(), "日志文件未创建"
    print("  - 获取最近日志")
    recent = log.get_recent_logs(5)
    assert len(recent) > 0, "未获取到日志"
    print("  ✅ AppLogger测试通过")


def test_error_handler():
    from core import ErrorHandler, GromacsError, ErrorCategory, ErrorSeverity
    err = ErrorHandler()
    print("  - 错误分类")
    gerror = err.handle(ValueError("test error"), {"context": "test"})
    assert isinstance(gerror, GromacsError), "错误分类失败"
    print("  - GPU错误分类")
    gerror = err.handle(Exception("CUDA error out of memory"))
    assert gerror.category == ErrorCategory.GPU, "GPU错误分类错误"
    print("  - 内存错误分类")
    gerror = err.handle(Exception("memory allocation failed"))
    assert gerror.category == ErrorCategory.MEMORY, "内存错误分类错误"
    print("  - 文件错误分类")
    gerror = err.handle(Exception("file not found"))
    assert gerror.category == ErrorCategory.FILE_IO, "文件错误分类错误"
    print("  - 获取错误历史")
    history = err.get_error_history()
    assert len(history) > 0, "错误历史为空"
    print("  - 获取崩溃文件")
    crashes = err.get_crash_files()
    print(f"    崩溃文件数量: {len(crashes)}")
    print("  ✅ ErrorHandler测试通过")


def test_resource_monitor():
    from core import ResourceMonitor
    monitor = ResourceMonitor()
    print("  - 获取资源状态")
    status = monitor.get_status()
    print(f"    CPU核心数: {status.cpu_cores}")
    print(f"    总内存: {status.memory_total_gb:.1f} GB")
    print(f"    可用内存: {status.memory_total_gb - status.memory_used_gb:.1f} GB")
    print(f"    内存使用率: {status.memory_percent:.1f}%")
    print(f"    磁盘可用: {status.disk_free_gb:.1f} GB")
    print(f"    GPU可用: {status.gpu_available}")
    assert status.cpu_cores > 0, "CPU核心数为0"
    assert status.memory_total_gb > 0, "内存为0"
    print("  - 资源检查")
    can_run, reason = monitor.can_start_simulation(0.5, 1.0)
    print(f"    可启动: {can_run}, 原因: {reason}")
    print("  - 获取建议")
    recs = monitor.get_recommendations()
    for rec in recs:
        print(f"    ⚠️ {rec}")
    print("  ✅ ResourceMonitor测试通过")


def test_gromacs_service():
    from core import GromacsService
    gmx = GromacsService()
    print("  - 扫描版本")
    versions = gmx.scan_versions()
    print(f"    发现 {len(versions)} 个版本")
    for name, info in versions.items():
        print(f"    - {name}: v{info.version}, GPU={info.gpu}, SIMD={info.simd}, PLUMED={info.plumed}, 有效={info.valid}, 评分={info.score}")
    assert len(versions) > 0, "未发现任何GROMACS版本"
    print("  - 获取最佳版本")
    best = gmx.get_best_version()
    if best:
        print(f"    最佳版本: {best[0]}")
        gmx.select_version(best[0])
    else:
        print("    警告: 无有效版本")
    print("  - 获取选中版本")
    selected = gmx.get_selected_version()
    if selected:
        print(f"    选中版本: {selected.name}")
    print("  ✅ GromacsService测试通过")


def test_workflow_engine():
    from core import WorkflowEngine, TaskType, TaskStatus
    wf = WorkflowEngine()
    print("  - 创建任务")
    task = wf.create_task(
        name="测试任务",
        task_type=TaskType.SIMULATION,
        command=["mdrun", "-deffnm", "test"],
        work_dir="/tmp",
        resume_capable=True,
        metadata={"base_name": "test"}
    )
    assert task.id, "任务ID为空"
    print(f"    任务ID: {task.id}")
    print("  - 更新任务状态")
    wf.update_task_status(task.id, TaskStatus.RUNNING, progress=30.0)
    updated = wf.get_task(task.id)
    assert updated.status == TaskStatus.RUNNING, "状态更新失败"
    assert updated.progress == 30.0, "进度更新失败"
    print("  - 获取所有任务")
    tasks = wf.get_all_tasks()
    assert len(tasks) >= 1, "任务列表为空"
    print("  - 获取统计")
    stats = wf.get_statistics()
    print(f"    统计: {stats}")
    print("  - 清除任务")
    wf.clear_all()
    tasks = wf.get_all_tasks()
    assert len(tasks) == 0, "清除失败"
    print("  ✅ WorkflowEngine测试通过")


def test_event_bus():
    from core import EventBus, EventPriority
    bus = EventBus()
    print("  - 订阅与发布")
    received = []
    def handler(event):
        received.append((event.event_type, event.data))
    bus.subscribe("test.event", handler)
    bus.publish("test.event", {"key": "value"}, source="test")
    assert len(received) == 1, "事件未收到"
    assert received[0][0] == "test.event", "事件类型错误"
    print("  - 模式匹配")
    pattern_received = []
    def pattern_handler(event):
        pattern_received.append(event.event_type)
    bus.subscribe("test.*", pattern_handler)
    bus.publish("test.subevent", "data")
    bus.publish("test.another", "data2")
    assert len(pattern_received) >= 2, "模式匹配失败"
    print("  - 优先级")
    order = []
    def p1(event):
        order.append("high")
    def p2(event):
        order.append("low")
    bus.subscribe("test.priority", p1, priority=EventPriority.HIGH)
    bus.subscribe("test.priority", p2, priority=EventPriority.LOW)
    bus.publish("test.priority")
    assert order == ["high", "low"], "优先级顺序错误"
    print("  - 全局订阅")
    global_received = []
    def global_handler(event):
        global_received.append(event.event_type)
    bus.subscribe_global(global_handler)
    bus.publish("any.event")
    assert len(global_received) >= 1, "全局订阅失败"
    print("  - 获取订阅者数量")
    count = bus.get_subscriber_count()
    print(f"    订阅者数量: {count}")
    print("  ✅ EventBus测试通过")


def test_review_mechanism():
    from core import ReviewMechanism, ReviewLevel, ReviewStatus
    reviewer = ReviewMechanism()
    print("  - 快速审查")
    report = reviewer.preflight_check(
        "测试任务",
        {"nt": 8, "mem_limit_gb": 4.0},
        str(Path(__file__).parent),
        ReviewLevel.QUICK
    )
    print(f"    审查结果: {report.overall_status.value}")
    print(f"    审查项数: {len(report.items)}")
    print("  - 标准审查")
    report = reviewer.preflight_check(
        "测试任务",
        {"nt": 8, "mem_limit_gb": 4.0, "use_gpu": False},
        str(Path(__file__).parent),
        ReviewLevel.STANDARD
    )
    print(f"    审查结果: {report.overall_status.value}")
    print("  - 查看审查项")
    for item in report.items:
        status_icon = "✅" if item.status == ReviewStatus.PASSED else "⚠️" if item.status == ReviewStatus.WARNING else "❌"
        print(f"    {status_icon} {item.name}: {item.message}")
    print("  ✅ ReviewMechanism测试通过")


def test_correction_mechanism():
    from core import CorrectionMechanism, ErrorHandler, ErrorCategory, CorrectionStatus
    corrector = CorrectionMechanism()
    err_handler = ErrorHandler()
    print("  - 文件错误纠错")
    unique_dir = str(Path(__file__).parent / f"test_dir_{int(time.time())}")
    error = err_handler.handle(Exception("file not found"), {"work_dir": unique_dir})
    result = corrector.auto_correct(error)
    print(f"    纠错结果: {result.status.value}, 动作: {result.action.value}")
    assert result.status in (CorrectionStatus.SUCCESS, CorrectionStatus.PARTIAL), f"文件纠错失败: {result.status.value}"
    print("  - GPU错误纠错")
    error = err_handler.handle(Exception("CUDA error"))
    result = corrector.auto_correct(error, {"use_gpu": True})
    print(f"    纠错结果: {result.status.value}, 动作: {result.action.value}")
    print("  - 内存错误纠错")
    error = err_handler.handle(Exception("memory allocation failed"))
    result = corrector.auto_correct(error, {"nt": 16})
    print(f"    纠错结果: {result.status.value}, 动作: {result.action.value}")
    print("  ✅ CorrectionMechanism测试通过")


def test_audit_mechanism():
    from core import AuditMechanism, AuditActionType
    audit = AuditMechanism()
    print("  - 记录操作")
    audit.log_action(AuditActionType.CONFIG_CHANGE, "测试配置变更", {"key": "value"})
    audit.log_simulation_event("start", "测试模拟")
    audit.log_version_change("old", "new")
    audit.log_file_operation("create", "/test/file")
    audit.log_error("test_error", "测试错误")
    audit.log_correction("auto_fix", "success")
    audit.log_review("preflight", "passed")
    print("  - 获取统计")
    stats = audit.get_statistics()
    print(f"    总记录数: {stats['total_records']}")
    print(f"    按类型统计: {stats['by_type']}")
    assert stats["total_records"] > 0, "审计记录为空"
    print("  - 获取最近操作")
    recent = audit.get_recent_actions(5)
    print(f"    最近操作数: {len(recent)}")
    print("  - 导出审计记录")
    temp_file = Path(__file__).parent / "test_audit_export.json"
    success = audit.export_to_file(str(temp_file))
    assert success, "导出失败"
    temp_file.unlink()
    print("  ✅ AuditMechanism测试通过")


def test_auto_updater():
    from core import AutoUpdater, UpdateChannel
    updater = AutoUpdater()
    print(f"  - 当前版本: {updater.current_version}")
    print(f"  - 更新状态: {updater.update_status.value}")
    print("  - 检查更新")
    result = updater.check_for_update(UpdateChannel.STABLE)
    print(f"    结果: {result.status.value}")
    print(f"    当前版本: {result.current_version}")
    if result.latest_version:
        print(f"    最新版本: {result.latest_version}")
    if result.changelog:
        print("    更新日志:")
        for line in result.changelog[:3]:
            print(f"      - {line}")
    print("  - 更新版本信息")
    updater.update_version_info("4.2.0", ["测试更新日志"])
    print("  ✅ AutoUpdater测试通过")


def test_integration():
    from core import (
        EventBus, ConfigManager, AppLogger,
        ReviewMechanism, AuditMechanism, GromacsService
    )
    print("  - 集成测试: 事件总线 + 配置管理")
    bus = EventBus()
    cfg = ConfigManager()
    changes = []
    def on_config_change(key, value):
        changes.append((key, value))
        bus.publish("config.changed", {"key": key, "value": value})
    cfg.add_listener("simulation", on_config_change)
    unique_sim_key = f"simulation.test_key_{int(time.time())}"
    cfg.set(unique_sim_key, 999)
    assert len(changes) >= 1, f"配置变更未触发，回调次数: {len(changes)}"
    print("  - 集成测试: 审查 + 审计")
    reviewer = ReviewMechanism()
    audit = AuditMechanism()
    report = reviewer.preflight_check("集成测试", {}, str(Path(__file__).parent))
    audit.log_review("preflight", report.overall_status.value)
    print(f"    审查结果: {report.overall_status.value}")
    print("  - 集成测试: GROMACS服务 + 事件总线")
    gmx = GromacsService()
    bus.subscribe("gromacs.version_changed", lambda e: print(f"版本变更: {e.data}"))
    versions = gmx.scan_versions()
    if versions:
        first = list(versions.keys())[0]
        gmx.select_version(first)
    print("  ✅ 集成测试通过")


def main():
    print("="*70)
    print("GROMACS GUI 核心机制全面测试 v4.2.0")
    print("="*70)

    test("ConfigManager", test_config_manager)
    test("AppLogger", test_logger)
    test("ErrorHandler", test_error_handler)
    test("ResourceMonitor", test_resource_monitor)
    test("GromacsService", test_gromacs_service)
    test("WorkflowEngine", test_workflow_engine)
    test("EventBus", test_event_bus)
    test("ReviewMechanism", test_review_mechanism)
    test("CorrectionMechanism", test_correction_mechanism)
    test("AuditMechanism", test_audit_mechanism)
    test("AutoUpdater", test_auto_updater)
    test("Integration", test_integration)

    print("\n" + "="*70)
    print("测试结果汇总")
    print("="*70)
    print(f"总测试数: {results['total_tests']}")
    print(f"✅ 通过: {results['passed']}")
    print(f"❌ 失败: {results['failed']}")
    print(f"⚠️ 警告: {results['warnings']}")
    print(f"成功率: {results['passed']/results['total_tests']*100:.1f}%")

    if results["failed"] > 0:
        print("\n失败的测试:")
        for t in results["tests"]:
            if t["status"] != "PASSED":
                print(f"  ❌ {t['name']}: {t.get('error', '未知错误')}")
        sys.exit(1)
    else:
        print("\n🎉 所有测试通过！")
        sys.exit(0)


if __name__ == "__main__":
    main()
