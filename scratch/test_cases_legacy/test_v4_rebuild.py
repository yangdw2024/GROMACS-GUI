#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
sys.path.insert(0, "D:\\YDW\\Trae_Gromacs\\source")

from core.version_manager import VersionManager, PlumedStatus, VersionValidity
from core.crash_handler import CrashHandler

print("=== V4.2 重构模块测试 ===")
print()

# 测试VersionManager
print("[1] 测试版本扫描(自动去重+过滤)...")
vm = VersionManager()
versions = vm.scan_versions(filter_invalid=True, deduplicate=True)
print(f"    有效版本数: {len(versions)}")

summary = vm.get_version_summary()
print(f"    总计: {summary['total']} | 有效: {summary['valid']}")
print(f"    重复: {summary['duplicates']} | 无效: {summary['invalid']}")
print(f"    PLUMED支持: {summary['plumed_supported']} | GPU支持: {summary['gpu_supported']}")

print()
print("[2] 版本详情:")
for name, meta in sorted(versions.items()):
    status = "有效"
    if meta.is_duplicate:
        status = f"重复({meta.duplicate_of})"
    print(f"    - {name}")
    print(f"      SIMD={meta.simd}, GPU={meta.gpu}, PLUMED={meta.plumed_status}")
    print(f"      状态: {status}, 大小: {meta.size_mb}MB")

# 测试最佳版本选择
print()
print("[3] 测试最佳版本选择...")
best = vm.select_best_version()
print(f"    最佳版本: {best}")

# 测试CrashHandler
print()
print("[4] 测试崩溃捕获框架...")
ch = CrashHandler()
print("    CrashHandler初始化成功")

# 测试版本清理查询
print()
print("[5] 测试版本清理查询...")
dups = vm.get_duplicate_versions()
invalid = vm.get_invalid_versions()
print(f"    重复版本: {len(dups)}个")
print(f"    无效版本: {len(invalid)}个")

print()
print("=== 所有重构模块测试通过 ===")