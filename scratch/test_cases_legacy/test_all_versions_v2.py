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
        "cuda_version": "",
        "plumed": False,
        "errors": []
    }
    
    try:
        print("1. 检测版本信息...")
        proc = subprocess.run(
            [version["path"], "--version"],
            capture_output=True, text=True, timeout=10
        )
        if proc.returncode == 0:
            result["version_info"] = proc.stdout.strip()
            if "AVX-512" in proc.stdout:
                result["simd"] = "AVX-512"
            elif "AVX2" in proc.stdout:
                result["simd"] = "AVX2"
            elif "SSE" in proc.stdout:
                result["simd"] = "SSE"
            print("   ✓ 版本信息获取成功")
            print("   SIMD: {}".format(result["simd"]))
        else:
            result["errors"].append("版本检测失败")
            print("   ✗ 版本检测失败")
    except Exception as e:
        result["errors"].append("版本检测异常: {}".format(e))
        print("   ✗ 版本检测异常: {}".format(e))
    
    try:
        print("2. 检测GPU支持...")
        proc = subprocess.run(
            [version["path"], "mdrun", "-gpu_id", "0", "-h"],
            capture_output=True, text=True, timeout=10
        )
        if "CUDA" in proc.stdout or "GPU" in proc.stdout or "gpu" in proc.stdout.lower():
            result["gpu_support"] = True
            print("   ✓ 支持GPU")
            
            cuda_path = Path(version["dir"]) / "bin" / "cudart64_13.dll"
            if cuda_path.exists():
                result["cuda_version"] = "13.x"
                print("   CUDA: {}".format(result["cuda_version"]))
        else:
            print("   ✗ 不支持GPU")
    except Exception as e:
        print("   - GPU检测异常: {}".format(e))
    
    try:
        print("3. 检测PLUMED支持...")
        proc = subprocess.run(
            [version["path"], "--version"],
            capture_output=True, text=True, timeout=10
        )
        if "PLUMED" in proc.stdout or "plumed" in proc.stdout.lower():
            result["plumed"] = True
            print("   ✓ 支持PLUMED")
        else:
            plumed_dll = Path(version["dir"]) / "bin" / "libplumed.dll"
            if plumed_dll.exists():
                result["plumed"] = True
                print("   ✓ 支持PLUMED")
            else:
                print("   ✗ 不支持PLUMED")
    except Exception as e:
        print("   - PLUMED检测异常: {}".format(e))
    
    try:
        print("4. 测试grompp命令...")
        proc = subprocess.run(
            [version["path"], "grompp"],
            capture_output=True, text=True, timeout=15
        )
        if "GROMACS" in proc.stdout or "GROMACS" in proc.stderr:
            result["grompp"] = True
            print("   ✓ grompp命令可用")
        else:
            result["errors"].append("grompp不可用")
            print("   ✗ grompp不可用")
    except Exception as e:
        result["errors"].append("grompp异常: {}".format(e))
        print("   ✗ grompp异常: {}".format(e))
    
    try:
        print("5. 测试mdrun命令...")
        proc = subprocess.run(
            [version["path"], "mdrun"],
            capture_output=True, text=True, timeout=15
        )
        if "GROMACS" in proc.stdout or "GROMACS" in proc.stderr:
            result["mdrun"] = True
            print("   ✓ mdrun命令可用")
        else:
            result["errors"].append("mdrun不可用")
            print("   ✗ mdrun不可用")
    except Exception as e:
        result["errors"].append("mdrun异常: {}".format(e))
        print("   ✗ mdrun异常: {}".format(e))
    
    test_results.append(result)
    print()

print("=" * 60)
print("=== 测试结果汇总 ===")
print()

print("{:<45} | {:<10} | {:<8} | {:<8} | {:<12} | {:<8}".format(
    "版本名称", "grompp", "mdrun", "GPU", "SIMD", "PLUMED"))
print("-" * 100)

for r in test_results:
    grompp_status = "✓" if r["grompp"] else "✗"
    mdrun_status = "✓" if r["mdrun"] else "✗"
    gpu_status = "✓" if r["gpu_support"] else "-"
    plumed_status = "✓" if r["plumed"] else "-"
    print("{:<45} | {:<10} | {:<8} | {:<8} | {:<12} | {:<8}".format(
        r["name"], grompp_status, mdrun_status, gpu_status, r["simd"], plumed_status))

print()
print("详细错误信息:")
has_errors = False
for r in test_results:
    if r["errors"]:
        has_errors = True
        print("  {}:".format(r["name"]))
        for err in r["errors"]:
            print("    - {}".format(err))

if not has_errors:
    print("  无错误")

print()
print("=== 测试完成 ===")