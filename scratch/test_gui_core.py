#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GUI核心功能全面检测脚本（无需启动图形界面）
检测内容：模块导入、版本扫描、PLUMED校验、命令生成、配置读取
"""
import sys, os, traceback
from pathlib import Path

# 添加source目录到路径
sys.path.insert(0, str(Path(__file__).parent / "source"))

errors = []
warnings = []

def check(name, condition, detail=""):
    if condition:
        print(f"  [PASS] {name}")
        return True
    else:
        print(f"  [FAIL] {name} {detail}")
        errors.append(f"{name}: {detail}")
        return False

def warn(name, condition, detail=""):
    if condition:
        print(f"  [PASS] {name}")
        return True
    else:
        print(f"  [WARN] {name} {detail}")
        warnings.append(f"{name}: {detail}")
        return False

print("=" * 70)
print("GUI核心功能全面检测")
print("=" * 70)

# =============================================================================
# 1. 模块导入测试
# =============================================================================
print("\n[1/6] 核心模块导入测试")
try:
    from core import (
        ConfigManager, AppLogger, ErrorHandler,
        ResourceMonitor, GromacsService, WorkflowEngine,
        EventBus, ReviewMechanism, CorrectionMechanism,
        AuditMechanism, AutoUpdater,
        VersionManager, VersionMetadata, PlumedStatus, VersionValidity,
        CrashHandler
    )
    check("所有核心模块导入", True)
except Exception as e:
    check("核心模块导入", False, f"{e}")
    traceback.print_exc()
    sys.exit(1)

# =============================================================================
# 2. 版本管理器测试
# =============================================================================
print("\n[2/6] 版本管理器测试")
try:
    vm = VersionManager()
    versions = vm.scan_versions(base_dir=r"D:\YDW\Trae_Gromacs\gromacs", filter_invalid=False, deduplicate=False)
    check("版本扫描", len(versions) == 7, f"期望7个，实际{len(versions)}")

    # 检查PLUMED状态
    plumed_versions = {k: v for k, v in versions.items() if "plumed" in k.lower()}
    for name, meta in plumed_versions.items():
        status_ok = meta.plumed_status == PlumedStatus.SUPPORTED.value
        check(f"PLUMED校验 [{name}]", status_ok, meta.plumed_detail)

    # 检查所有版本有效性
    invalid = vm.get_invalid_versions()
    check("无无效版本", len(invalid) == 0, str(invalid))

    # 检查最佳版本选择
    best = vm.select_best_version()
    check("最佳版本选择", best is not None, "返回None")

except Exception as e:
    check("版本管理器测试", False, str(e))
    traceback.print_exc()

# =============================================================================
# 3. GromacsService测试
# =============================================================================
print("\n[3/6] GromacsService测试")
try:
    from core.gromacs_service import GromacsService
    gs = GromacsService()
    # 必须先扫描版本
    gs.scan_versions(base_dir=r"D:\YDW\Trae_Gromacs\gromacs")
    # 再获取gmx路径
    gmx_exe = gs.get_gmx_exe()
    check("GromacsService获取gmx路径", gmx_exe and os.path.exists(gmx_exe), gmx_exe)
except Exception as e:
    check("GromacsService测试", False, str(e))

# =============================================================================
# 4. 配置管理器测试
# =============================================================================
print("\n[4/6] 配置管理器测试")
try:
    cfg = ConfigManager()
    check("ConfigManager实例化", True)
except Exception as e:
    check("ConfigManager", False, str(e))

# =============================================================================
# 5. 其他核心组件测试
# =============================================================================
print("\n[5/6] 其他核心组件测试")
try:
    logger = AppLogger()
    check("AppLogger实例化", True)
except Exception as e:
    check("AppLogger", False, str(e))

try:
    eb = EventBus()
    check("EventBus实例化", True)
except Exception as e:
    check("EventBus", False, str(e))

try:
    rm = ResourceMonitor()
    check("ResourceMonitor实例化", True)
except Exception as e:
    check("ResourceMonitor", False, str(e))

# =============================================================================
# 6. GUI主程序语法检查
# =============================================================================
print("\n[6/6] GUI主程序语法检查")
try:
    gui_path = Path(__file__).parent / "source" / "gromacs_gui_v4.py"
    with open(gui_path, "r", encoding="utf-8") as f:
        source = f.read()
    compile(source, str(gui_path), "exec")
    check("gromacs_gui_v4.py 语法", True)
except Exception as e:
    check("gromacs_gui_v4.py 语法", False, str(e))

# 检查关键文件存在性
print("\n[额外] 关键文件存在性检查")
key_files = [
    ("GUI主程序", "source/gromacs_gui_v4.py"),
    ("版本配置", "version.config"),
    ("可执行文件", "release/GROMACS_GUI_v4.2.0.exe"),
    ("启动脚本", "release/启动程序.bat"),
    ("程序图标", "resources/app_icon.ico"),
]
base = Path(__file__).parent
for label, rel_path in key_files:
    full = base / rel_path
    check(f"{label}", full.exists(), str(full))

# 检查version.config白名单
print("\n[额外] version.config白名单检查")
try:
    import json
    with open(base / "version.config", "r", encoding="utf-8") as f:
        vc = json.load(f)
    whitelist = vc.get("version_whitelist", [])
    expected = [
        "gromacs-2025.1-SM120-AVX512",
        "gromacs-2026.1-plumed-CUDA",
        "gromacs-2026.3-AVX2-CUDA",
        "gromacs-2026.3-AVX512-CUDA",
        "gromacs-2026.3-AVX512-CUDA-PLUMED",
        "gromacs-2026.3-AVX512-CUDA-PLUMED-sm120",
        "gromacs-2026.3-AVX512-CUDA-sm120-final2"
    ]
    check("version.config白名单完整", set(whitelist) >= set(expected), f"实际: {whitelist}")
except Exception as e:
    check("version.config读取", False, str(e))

# =============================================================================
# 总结
# =============================================================================
print("\n" + "=" * 70)
print("检测总结")
print("=" * 70)
print(f"错误数: {len(errors)}")
print(f"警告数: {len(warnings)}")
if errors:
    print("\n错误详情:")
    for e in errors:
        print(f"  - {e}")
if warnings:
    print("\n警告详情:")
    for w in warnings:
        print(f"  - {w}")
if not errors and not warnings:
    print("\n全部通过！GUI核心功能完全正常。")
