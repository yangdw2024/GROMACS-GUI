#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import subprocess
import time
from pathlib import Path

gromacs_dir = Path("D:/YDW/Trae_Gromacs/gromacs")

print("=== 扫描所有GROMACS版本 ===")
print()

versions = []
for item in sorted(gromacs_dir.iterdir()):
    if item.is_dir() and not item.name.startswith("build-"):
        gmx_exe = item / "bin" / "gmx.exe"
        if gmx_exe.exists():
            versions.append({"name": item.name, "path": str(gmx_exe), "dir": str(item)})

print("发现 {} 个版本:".format(len(versions)))
for i, v in enumerate(versions, 1):
    print("  {}. {}".format(i, v["name"]))

print()
print("=== 测试各版本功能 ===")
print()

test_dir = Path("D:/YDW/Trae_Gromacs/test_output")
test_dir.mkdir(exist_ok=True)

test_results = []

for version in versions:
    print("=" * 60)
    print("测试版本: {}".format(version["name"]))
    print("路径: {}".format(version["path"]))
    
    result = {
        "name": version["name"],
        "path": version["path"],
        "grompp": False,
        "mdrun": False,
        "version_info": "",
        "gpu_support": False,
        "simd": "",
        "errors": []
    }
    
    try:
        print("1. 检测版本信息...")
        proc = subprocess.run(
            [version["path"], "--version"],
            capture_output=True, text=True, timeout=10
        )
        if proc.returncode == 0:
            result["version_info"] = proc.stdout.strip()[:100]
            if "AVX-512" in proc.stdout:
                result["simd"] = "AVX-512"
            elif "AVX2" in proc.stdout:
                result["simd"] = "AVX2"
            elif "SSE" in proc.stdout:
                result["simd"] = "SSE"
            print("   ✓ 版本信息获取成功")
            print("   SIMD: {}".format(result["simd"]))
        else:
            result["errors"].append("版本检测失败: {}".format(proc.stderr[:50]))
            print("   ✗ 版本检测失败")
    except Exception as e:
        result["errors"].append("版本检测异常: {}".format(e))
        print("   ✗ 版本检测异常: {}".format(e))
    
    try:
        print("2. 检测GPU支持...")
        proc = subprocess.run(
            [version["path"], "cuda", "--help"],
            capture_output=True, text=True, timeout=10
        )
        if proc.returncode == 0 or "CUDA" in proc.stderr:
            result["gpu_support"] = True
            print("   ✓ 支持GPU")
        else:
            print("   ✗ 不支持GPU或无CUDA模块")
    except Exception as e:
        print("   - GPU检测异常: {}".format(e))
    
    try:
        print("3. 测试grompp...")
        proc = subprocess.run(
            [version["path"], "grompp", "--help"],
            capture_output=True, text=True, timeout=15
        )
        if proc.returncode == 0:
            result["grompp"] = True
            print("   ✓ grompp正常")
        else:
            result["errors"].append("grompp失败: {}".format(proc.stderr[:50]))
            print("   ✗ grompp失败")
    except Exception as e:
        result["errors"].append("grompp异常: {}".format(e))
        print("   ✗ grompp异常: {}".format(e))
    
    try:
        print("4. 测试mdrun...")
        proc = subprocess.run(
            [version["path"], "mdrun", "--help"],
            capture_output=True, text=True, timeout=15
        )
        if proc.returncode == 0:
            result["mdrun"] = True
            print("   ✓ mdrun正常")
        else:
            result["errors"].append("mdrun失败: {}".format(proc.stderr[:50]))
            print("   ✗ mdrun失败")
    except Exception as e:
        result["errors"].append("mdrun异常: {}".format(e))
        print("   ✗ mdrun异常: {}".format(e))
    
    test_results.append(result)
    print()

print("=" * 60)
print("=== 测试结果汇总 ===")
print()

print("{:<40} | {:<10} | {:<8} | {:<10} | {:<10}".format(
    "版本名称", "grompp", "mdrun", "GPU", "SIMD"))
print("-" * 85)

for r in test_results:
    grompp_status = "✓" if r["grompp"] else "✗"
    mdrun_status = "✓" if r["mdrun"] else "✗"
    gpu_status = "✓" if r["gpu_support"] else "-"
    print("{:<40} | {:<10} | {:<8} | {:<10} | {:<10}".format(
        r["name"], grompp_status, mdrun_status, gpu_status, r["simd"]))

print()
print("详细错误信息:")
for r in test_results:
    if r["errors"]:
        print("  {}:".format(r["name"]))
        for err in r["errors"]:
            print("    - {}".format(err))

print()
print("=== 测试完成 ===")