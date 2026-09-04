#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GROMACS GUI 内存限制与资源泄漏隐患检测脚本 (test_3_1)
检测范围：
  1. 循环切换全部版本，监控进程内存变化
  2. 测试内存边界阈值：0.5GB、8GB、超硬件内存(999GB)、0GB(关闭限制)
  3. 检测文件/日志句柄残留
  4. 检测临时文件堆积
  5. 检查内存限制校验是否缺失（0GB、负数、超大值）
"""

import sys
import os
import gc
import tempfile
import time
from pathlib import Path

sys.path.insert(0, r"D:\YDW\Trae_Gromacs\source")

from core import VersionManager, ConfigManager, ResourceMonitor

# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def get_process_memory_mb():
    """获取当前进程内存占用(MB)，优先使用psutil，回退到os"""
    try:
        import psutil
        proc = psutil.Process(os.getpid())
        return proc.memory_info().rss / (1024 * 1024)
    except ImportError:
        pass
    # 回退方案：Windows 通过 ctypes 读取
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        PROCESS_QUERY_INFORMATION = 0x0400
        PROCESS_VM_READ = 0x0010
        handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, os.getpid())
        if handle:
            class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
                _fields_ = [
                    ("cb", ctypes.c_uint32),
                    ("PageFaultCount", ctypes.c_uint32),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                    ("PrivateUsage", ctypes.c_size_t),
                ]
            counters = PROCESS_MEMORY_COUNTERS_EX()
            counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS_EX)
            psapi = ctypes.windll.psapi
            if psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                kernel32.CloseHandle(handle)
                return counters.WorkingSetSize / (1024 * 1024)
            kernel32.CloseHandle(handle)
    except Exception:
        pass
    # 最终回退：读取 /proc (Linux) 或返回 0
    try:
        with open(f"/proc/{os.getpid()}/status", "r") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / 1024  # kB -> MB
    except Exception:
        pass
    return 0.0


def get_open_file_handles():
    """统计当前进程打开的文件句柄数，优先psutil，回退到os"""
    try:
        import psutil
        proc = psutil.Process(os.getpid())
        return len(proc.open_files())
    except ImportError:
        pass
    # Windows 回退：使用 ctypes/NtQuerySystemInformation 太复杂，
    # 改用 subprocess 调用 handle.exe 如可用，否则返回 -1 表示无法检测
    try:
        import subprocess
        result = subprocess.run(
            ["handle", "-p", str(os.getpid()), "-nobanner"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return len([l for l in result.stdout.strip().split("\n") if l.strip()])
    except Exception:
        pass
    return -1  # 无法检测


def count_temp_files(temp_dir=None):
    """统计临时目录中的文件数"""
    if temp_dir is None:
        temp_dir = tempfile.gettempdir()
    temp_path = Path(temp_dir)
    if not temp_path.exists():
        return 0
    count = 0
    try:
        for item in temp_path.iterdir():
            # 只统计与 gromacs/gui 相关的临时文件
            name_lower = item.name.lower()
            if any(kw in name_lower for kw in ["gromacs", "gmx", "gui", "mdrun", "grompp", "trr", "xtc", "edr", "log", "tmp"]):
                count += 1
    except Exception:
        pass
    return count


# ---------------------------------------------------------------------------
# 隐患收集器
# ---------------------------------------------------------------------------

class HazardCollector:
    """收集并输出隐患清单"""

    def __init__(self):
        self.hazards = []

    def add(self, description, reproduce_steps, severity):
        """
        severity: HIGH / MEDIUM / LOW
        """
        self.hazards.append({
            "隐患描述": description,
            "复现步骤": reproduce_steps,
            "严重程度": severity,
        })

    def report(self):
        print("\n" + "=" * 80)
        print("  内存限制与资源泄漏隐患清单")
        print("=" * 80)
        if not self.hazards:
            print("  未发现隐患。")
            return

        # 按严重程度排序
        order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        self.hazards.sort(key=lambda h: order.get(h["严重程度"], 9))

        for i, h in enumerate(self.hazards, 1):
            print(f"\n  【隐患 #{i}】")
            print(f"  隐患描述：{h['隐患描述']}")
            print(f"  复现步骤：{h['复现步骤']}")
            print(f"  严重程度：{h['严重程度']}")

        print("\n" + "-" * 80)
        high = sum(1 for h in self.hazards if h["严重程度"] == "HIGH")
        medium = sum(1 for h in self.hazards if h["严重程度"] == "MEDIUM")
        low = sum(1 for h in self.hazards if h["严重程度"] == "LOW")
        print(f"  合计：{len(self.hazards)} 条隐患  (HIGH={high}, MEDIUM={medium}, LOW={low})")
        print("=" * 80)


# ---------------------------------------------------------------------------
# 测试 1: 循环切换全部版本，监控进程内存变化
# ---------------------------------------------------------------------------

def test_version_switch_memory(vm, hazards):
    """循环切换全部GROMACS版本，检测是否存在内存持续增长（泄漏）"""
    print("\n--- 测试1: 循环切换版本，监控内存变化 ---")

    versions = vm.scan_versions(filter_invalid=False, deduplicate=False)
    if not versions:
        print("  未扫描到任何版本，跳过此测试")
        return

    version_names = list(versions.keys())
    print(f"  扫描到 {len(version_names)} 个版本: {version_names}")

    # 记录初始内存
    gc.collect()
    mem_before = get_process_memory_mb()
    print(f"  初始内存: {mem_before:.1f} MB")

    # 多轮切换
    num_rounds = 3
    mem_per_round = []

    for round_idx in range(num_rounds):
        for vname in version_names:
            vm.select_version(vname)
            _ = vm.get_selected_version()
        gc.collect()
        mem_after = get_process_memory_mb()
        mem_per_round.append(mem_after)
        print(f"  第 {round_idx + 1} 轮切换后内存: {mem_after:.1f} MB")

    # 分析内存增长趋势
    if len(mem_per_round) >= 2:
        mem_growth = mem_per_round[-1] - mem_before
        mem_growth_mb = abs(mem_growth)
        print(f"  内存变化: {mem_before:.1f} MB -> {mem_per_round[-1]:.1f} MB (增长 {mem_growth:.1f} MB)")

        if mem_growth_mb > 100:
            hazards.add(
                "循环切换GROMACS版本时进程内存持续增长，可能存在内存泄漏",
                f"连续切换 {len(version_names)} 个版本 {num_rounds} 轮，"
                f"内存从 {mem_before:.1f}MB 增长至 {mem_per_round[-1]:.1f}MB"
                f"（增长 {mem_growth:.1f}MB）",
                "HIGH"
            )
        elif mem_growth_mb > 30:
            hazards.add(
                "循环切换GROMACS版本时进程内存有增长趋势，需关注",
                f"连续切换 {len(version_names)} 个版本 {num_rounds} 轮，"
                f"内存增长 {mem_growth:.1f}MB",
                "MEDIUM"
            )

        # 逐轮增长检测
        for i in range(1, len(mem_per_round)):
            round_growth = mem_per_round[i] - mem_per_round[i - 1]
            if round_growth > 50:
                hazards.add(
                    f"第 {i + 1} 轮版本切换内存突增 {round_growth:.1f}MB，疑似资源未释放",
                    f"第 {i} 轮内存 {mem_per_round[i - 1]:.1f}MB -> "
                    f"第 {i + 1} 轮 {mem_per_round[i]:.1f}MB",
                    "MEDIUM"
                )


# ---------------------------------------------------------------------------
# 测试 2: 内存边界阈值测试
# ---------------------------------------------------------------------------

def test_memory_boundary_thresholds(hazards):
    """测试 ConfigManager 对各类内存边界值的处理"""
    print("\n--- 测试2: 内存边界阈值测试 ---")

    cm = ConfigManager()
    original_mem_limit = cm.get("simulation.mem_limit_gb")
    original_mem_enabled = cm.get("simulation.mem_limit_enabled")
    original_max_mem = cm.get("resources.max_memory_gb")

    boundary_values = [
        (0.5,  "0.5GB（极小值）"),
        (8.0,  "8GB（默认值）"),
        (999.0, "999GB（超硬件内存）"),
        (0,    "0GB（关闭限制）"),
    ]

    for value, desc in boundary_values:
        print(f"  测试阈值: {desc} ({value}GB)")

        # 设置 simulation.mem_limit_gb
        cm.set("simulation.mem_limit_gb", value, auto_save=False)
        actual = cm.get("simulation.mem_limit_gb")

        if actual != value:
            hazards.add(
                f"设置内存限制 {desc} 后值不一致: 期望 {value}, 实际 {actual}",
                f"ConfigManager.set('simulation.mem_limit_gb', {value}) -> "
                f"ConfigManager.get() 返回 {actual}",
                "HIGH"
            )

        # 检查是否有合理性校验
        if value == 999.0:
            # 超大值应该被拦截或告警，但当前代码无校验
            if actual == 999.0:
                hazards.add(
                    "内存限制设为999GB（远超物理内存）未被拦截，缺少上限校验",
                    "设置 simulation.mem_limit_gb=999，ConfigManager 接受该值无报错",
                    "HIGH"
                )

        if value == 0:
            # 0GB 意味着关闭限制，应明确提示
            if actual == 0:
                hazards.add(
                    "内存限制设为0GB（关闭限制）时无任何提示或确认机制",
                    "设置 simulation.mem_limit_gb=0，ConfigManager 静默接受",
                    "MEDIUM"
                )

        # 设置 resources.max_memory_gb
        cm.set("resources.max_memory_gb", value, auto_save=False)
        actual_res = cm.get("resources.max_memory_gb")

        if value == 999.0 and actual_res == 999.0:
            hazards.add(
                "系统资源最大内存设为999GB未被拦截，缺少合理性校验",
                "设置 resources.max_memory_gb=999，ConfigManager 接受该值无报错",
                "MEDIUM"
            )

    # 恢复原值
    cm.set("simulation.mem_limit_gb", original_mem_limit, auto_save=False)
    cm.set("simulation.mem_limit_enabled", original_mem_enabled, auto_save=False)
    cm.set("resources.max_memory_gb", original_max_mem, auto_save=False)

    print("  边界阈值测试完成（已恢复原配置）")


# ---------------------------------------------------------------------------
# 测试 3: 文件/日志句柄残留检测
# ---------------------------------------------------------------------------

def test_file_handle_leak(vm, hazards):
    """检测版本切换后文件/日志句柄是否残留"""
    print("\n--- 测试3: 文件/日志句柄残留检测 ---")

    handles_before = get_open_file_handles()
    if handles_before < 0:
        print("  无法检测文件句柄数（psutil 和 handle.exe 均不可用），使用替代方案")
        # 替代方案：检查日志目录中的文件数量变化
        _test_log_file_accumulation(hazards)
        return

    print(f"  初始文件句柄数: {handles_before}")

    versions = vm.scan_versions(filter_invalid=False, deduplicate=False)
    if not versions:
        print("  未扫描到版本，跳过句柄检测")
        return

    # 多轮扫描 + 切换
    for i in range(3):
        for vname in versions:
            vm.select_version(vname)
            _ = vm.get_selected_version()
        gc.collect()

    handles_after = get_open_file_handles()
    print(f"  操作后文件句柄数: {handles_after}")

    if handles_after >= 0:
        leaked = handles_after - handles_before
        if leaked > 20:
            hazards.add(
                f"版本切换后文件句柄净增 {leaked} 个，疑似句柄泄漏",
                f"3轮版本扫描+切换，文件句柄从 {handles_before} 增至 {handles_after}",
                "HIGH"
            )
        elif leaked > 5:
            hazards.add(
                f"版本切换后文件句柄净增 {leaked} 个，需关注",
                f"文件句柄从 {handles_before} 增至 {handles_after}",
                "MEDIUM"
            )


def _test_log_file_accumulation(hazards):
    """检查日志目录中的文件堆积情况"""
    print("  [替代方案] 检查日志目录文件堆积...")

    log_dir = Path(r"D:\YDW\Trae_Gromacs\source\logs")
    if not log_dir.exists():
        print("  日志目录不存在，跳过")
        return

    log_files = list(log_dir.iterdir())
    crash_dir = log_dir / "crashes"
    crash_count = 0
    if crash_dir.exists():
        crash_count = len(list(crash_dir.iterdir()))

    audit_dir = log_dir / "audit"
    audit_count = 0
    if audit_dir.exists():
        audit_count = len(list(audit_dir.iterdir()))

    print(f"  日志文件数: {len(log_files)}, 崩溃记录数: {crash_count}, 审计记录数: {audit_count}")

    if len(log_files) > 50:
        hazards.add(
            f"日志目录堆积 {len(log_files)} 个文件，可能存在日志未清理问题",
            f"检查 {log_dir}，发现 {len(log_files)} 个日志文件",
            "MEDIUM"
        )

    if crash_count > 10:
        hazards.add(
            f"崩溃日志堆积 {crash_count} 个，可能存在未处理的稳定性问题",
            f"检查 {crash_dir}，发现 {crash_count} 个崩溃记录",
            "LOW"
        )


# ---------------------------------------------------------------------------
# 测试 4: 临时文件堆积检测
# ---------------------------------------------------------------------------

def test_temp_file_accumulation(hazards):
    """检测临时目录中与GROMACS相关的文件是否堆积"""
    print("\n--- 测试4: 临时文件堆积检测 ---")

    # 检查系统临时目录
    sys_temp = tempfile.gettempdir()
    sys_temp_count = count_temp_files(sys_temp)
    print(f"  系统临时目录 ({sys_temp}): {sys_temp_count} 个相关文件")

    if sys_temp_count > 20:
        hazards.add(
            f"系统临时目录堆积 {sys_temp_count} 个GROMACS相关文件",
            f"检查 {sys_temp}，搜索含 gromacs/gmx/gui/mdrun 等关键词的文件",
            "MEDIUM"
        )

    # 检查项目内 temp 目录
    project_temp = Path(r"D:\YDW\Trae_Gromacs\temp")
    if project_temp.exists():
        project_temp_count = len([f for f in project_temp.iterdir() if f.is_file()])
        print(f"  项目temp目录 ({project_temp}): {project_temp_count} 个文件")

        if project_temp_count > 30:
            hazards.add(
                f"项目temp目录堆积 {project_temp_count} 个文件，建议清理",
                f"检查 {project_temp}",
                "LOW"
            )

        # 检查大文件
        large_files = []
        for f in project_temp.iterdir():
            if f.is_file():
                try:
                    size_mb = f.stat().st_size / (1024 * 1024)
                    if size_mb > 100:
                        large_files.append((f.name, size_mb))
                except Exception:
                    pass

        if large_files:
            for fname, size in large_files:
                hazards.add(
                    f"项目temp目录存在大文件 {fname} ({size:.1f}MB)，可能占用磁盘空间",
                    f"检查 {project_temp / fname}",
                    "LOW"
                )

    # 检查 dist 目录中可能遗留的临时文件
    dist_dir = Path(r"D:\YDW\Trae_Gromacs\dist")
    if dist_dir.exists():
        dist_log = dist_dir / "gromacs_gui.log"
        if dist_log.exists():
            try:
                size_mb = dist_log.stat().st_size / (1024 * 1024)
                if size_mb > 50:
                    hazards.add(
                        f"dist目录日志文件过大 ({size_mb:.1f}MB)，可能导致日志写入性能下降",
                        f"检查 {dist_log}",
                        "LOW"
                    )
            except Exception:
                pass


# ---------------------------------------------------------------------------
# 测试 5: 内存限制校验缺失检测
# ---------------------------------------------------------------------------

def test_memory_validation_missing(hazards):
    """检查内存限制校验是否缺失：测试0GB、负数、超大值是否被拦截"""
    print("\n--- 测试5: 内存限制校验缺失检测 ---")

    cm = ConfigManager()
    original_mem_limit = cm.get("simulation.mem_limit_gb")
    original_max_mem = cm.get("resources.max_memory_gb")

    invalid_values = [
        (0,    "0GB"),
        (-1,   "负数(-1GB)"),
        (-0.5, "负小数(-0.5GB)"),
        (9999, "超大值(9999GB)"),
        (1e9,  "极端超大值(1e9GB)"),
    ]

    for value, desc in invalid_values:
        # 测试 simulation.mem_limit_gb
        cm.set("simulation.mem_limit_gb", value, auto_save=False)
        actual = cm.get("simulation.mem_limit_gb")

        if value < 0 and actual == value:
            hazards.add(
                f"内存限制接受{desc}，缺少负数校验",
                f"ConfigManager.set('simulation.mem_limit_gb', {value}) 被静默接受，"
                f"无报错或拒绝",
                "HIGH"
            )
            print(f"  [!] {desc} 被静默接受 (simulation.mem_limit_gb)")

        if value > 1000 and actual == value:
            hazards.add(
                f"内存限制接受{desc}，缺少超大值上限校验",
                f"ConfigManager.set('simulation.mem_limit_gb', {value}) 被静默接受，"
                f"无报错或拒绝",
                "HIGH"
            )
            print(f"  [!] {desc} 被静默接受 (simulation.mem_limit_gb)")

        # 测试 resources.max_memory_gb
        cm.set("resources.max_memory_gb", value, auto_save=False)
        actual_res = cm.get("resources.max_memory_gb")

        if value < 0 and actual_res == value:
            hazards.add(
                f"系统最大内存接受{desc}，缺少负数校验",
                f"ConfigManager.set('resources.max_memory_gb', {value}) 被静默接受",
                "HIGH"
            )
            print(f"  [!] {desc} 被静默接受 (resources.max_memory_gb)")

        if value > 1000 and actual_res == value:
            hazards.add(
                f"系统最大内存接受{desc}，缺少超大值上限校验",
                f"ConfigManager.set('resources.max_memory_gb', {value}) 被静默接受",
                "MEDIUM"
            )

    # 检查 ResourceMonitor 的 can_start_simulation 是否校验内存限制
    rm = ResourceMonitor()
    status = rm.get_status()
    total_mem = status.memory_total_gb
    print(f"  系统物理内存: {total_mem:.1f} GB")

    # 测试超物理内存的需求
    ok, msg = rm.can_start_simulation(required_memory_gb=total_mem + 100)
    if not ok:
        print(f"  [OK] 超物理内存需求被正确拒绝: {msg}")
    else:
        hazards.add(
            "ResourceMonitor.can_start_simulation 允许申请超过物理内存的内存量",
            f"系统内存 {total_mem:.1f}GB，申请 {total_mem + 100:.1f}GB 时返回通过",
            "MEDIUM"
        )

    # 测试0内存需求
    ok, msg = rm.can_start_simulation(required_memory_gb=0)
    if ok:
        print(f"  [INFO] 0GB内存需求通过校验: {msg}")
    else:
        hazards.add(
            "ResourceMonitor 拒绝0GB内存需求，0GB应有明确语义（不限制）",
            f"can_start_simulation(required_memory_gb=0) 返回: {msg}",
            "LOW"
        )

    # 恢复配置
    cm.set("simulation.mem_limit_gb", original_mem_limit, auto_save=False)
    cm.set("resources.max_memory_gb", original_max_mem, auto_save=False)

    print("  内存校验缺失检测完成（已恢复原配置）")


# ---------------------------------------------------------------------------
# 主函数
# ---------------------------------------------------------------------------

def main():
    print("=" * 80)
    print("  GROMACS GUI - 内存限制与资源泄漏隐患检测 (test_3_1)")
    print("=" * 80)

    hazards = HazardCollector()

    # 获取版本列表
    vm = VersionManager()
    versions = vm.scan_versions(filter_invalid=False, deduplicate=False)
    print(f"\n已扫描到 {len(versions)} 个GROMACS版本")
    if versions:
        for name, meta in versions.items():
            valid_mark = "有效" if meta.valid else "无效"
            print(f"  - {name} ({valid_mark}, {meta.size_mb}MB)")

    # 测试1: 循环切换版本，监控内存
    test_version_switch_memory(vm, hazards)

    # 测试2: 内存边界阈值
    test_memory_boundary_thresholds(hazards)

    # 测试3: 文件/日志句柄残留
    test_file_handle_leak(vm, hazards)

    # 测试4: 临时文件堆积
    test_temp_file_accumulation(hazards)

    # 测试5: 内存限制校验缺失
    test_memory_validation_missing(hazards)

    # 输出隐患清单
    hazards.report()


if __name__ == "__main__":
    main()
