#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re
from pathlib import Path

versions = [
    ("gromacs-2026.3-AVX512-CUDA", r"D:\YDW\Trae_Gromacs\gromacs\gromacs-2026.3-AVX512-CUDA\bin\gmx.exe"),
    ("gromacs-2026.3-AVX512-CUDA-PLUMED-sm120", r"D:\YDW\Trae_Gromacs\gromacs\gromacs-2026.3-AVX512-CUDA-PLUMED-sm120\bin\gmx.exe"),
    ("gromacs-2026.3-AVX512-CUDA-sm120-final2", r"D:\YDW\Trae_Gromacs\gromacs\gromacs-2026.3-AVX512-CUDA-sm120-final2\bin\gmx.exe"),
]

print("=" * 70)
print("gmx.exe 二进制中 CUDA 架构标识检测")
print("=" * 70)

for name, exe in versions:
    print(f"\n>>> {name}")
    data = Path(exe).read_bytes()
    text = data.decode('ascii', errors='ignore')

    # 搜索常见CUDA架构标识
    archs = re.findall(r'sm_\d+', text)
    archs += re.findall(r'compute_\d+', text)
    # 也搜索数字120、89、90等
    if '120' in text:
        archs.append('found_120')

    unique_archs = sorted(set(archs))
    if unique_archs:
        print(f"  发现架构标识: {unique_archs}")
    else:
        print(f"  未发现明确架构标识（可能被压缩或编码）")

    # 检查是否有lib目录下的cuda相关文件
    bin_dir = Path(exe).parent
    cuda_files = list(bin_dir.glob("cudart*.dll")) + list(bin_dir.glob("cufft*.dll"))
    print(f"  CUDA DLL文件: {[f.name for f in cuda_files]}")
