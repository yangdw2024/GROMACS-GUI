#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import subprocess, sys
from pathlib import Path

versions = [
    ("gromacs-2026.3-AVX512-CUDA", r"D:\YDW\Trae_Gromacs\gromacs\gromacs-2026.3-AVX512-CUDA\bin\gmx.exe"),
    ("gromacs-2026.3-AVX512-CUDA-PLUMED-sm120", r"D:\YDW\Trae_Gromacs\gromacs\gromacs-2026.3-AVX512-CUDA-PLUMED-sm120\bin\gmx.exe"),
    ("gromacs-2026.3-AVX512-CUDA-sm120-final2", r"D:\YDW\Trae_Gromacs\gromacs\gromacs-2026.3-AVX512-CUDA-sm120-final2\bin\gmx.exe"),
]

print("=" * 70)
print("SM120 / AVX-512 编译状态详细检测")
print("=" * 70)

for name, exe in versions:
    print(f"\n>>> {name}")
    exe_path = Path(exe)
    if not exe_path.exists():
        print(f"  [FAIL] gmx.exe 不存在: {exe}")
        continue

    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        r = subprocess.run([str(exe_path), "--version"], capture_output=True, text=True, timeout=15, startupinfo=startupinfo)
        out = r.stdout + r.stderr

        if r.returncode != 0:
            print(f"  [FAIL] gmx.exe 执行失败 (rc={r.returncode})")
            print(f"  stderr: {out[:500]}")
            continue

        # 提取关键信息
        info = {}
        for line in out.split("\n"):
            line_lower = line.lower()
            if "gromacs version:" in line_lower:
                info["version"] = line.split(":", 1)[1].strip()
            elif "precision:" in line_lower:
                info["precision"] = line.split(":", 1)[1].strip()
            elif "simd instructions:" in line_lower:
                info["simd"] = line.split(":", 1)[1].strip()
            elif "gpu support:" in line_lower:
                info["gpu"] = line.split(":", 1)[1].strip()
            elif "cuda driver:" in line_lower:
                info["cuda_driver"] = line.split(":", 1)[1].strip()
            elif "cuda runtime:" in line_lower:
                info["cuda_runtime"] = line.split(":", 1)[1].strip()

        simd_ok = "avx_512" in info.get("simd", "").lower() or "avx512" in info.get("simd", "").lower()
        gpu_ok = "cuda" in info.get("gpu", "").lower()

        print(f"  GROMACS版本: {info.get('version', 'N/A')}")
        print(f"  精度: {info.get('precision', 'N/A')}")
        print(f"  SIMD: {info.get('simd', 'N/A')} {'[OK]' if simd_ok else '[FAIL]'}")
        print(f"  GPU支持: {info.get('gpu', 'N/A')} {'[OK]' if gpu_ok else '[FAIL]'}")
        if "cuda_driver" in info:
            print(f"  CUDA驱动: {info['cuda_driver']}")
        if "cuda_runtime" in info:
            print(f"  CUDA运行时: {info['cuda_runtime']}")

        # 检查gmx mdrun -h中的CUDA相关输出
        r2 = subprocess.run([str(exe_path), "mdrun", "-h"], capture_output=True, text=True, timeout=15, startupinfo=startupinfo)
        mdrun_out = r2.stdout + r2.stderr
        has_gpu_id = "-gpu_id" in mdrun_out
        has_nb = "-nb" in mdrun_out
        has_pme = "-pme" in mdrun_out
        print(f"  mdrun GPU参数: -gpu_id={'支持' if has_gpu_id else '不支持'}, -nb={'支持' if has_nb else '不支持'}, -pme={'支持' if has_pme else '不支持'}")

        # 检查文件大小（静态链接PLUMED会更大）
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"  gmx.exe大小: {size_mb:.1f} MB")

    except Exception as e:
        print(f"  [FAIL] 检测异常: {e}")

print("\n" + "=" * 70)
print("检测完成")
print("=" * 70)
