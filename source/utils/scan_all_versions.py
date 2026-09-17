#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全面检测所有 GROMACS 版本（独立运维脚本，导入不执行）"""
import os, subprocess, sys
from pathlib import Path


def main():
    base = Path("D:/YDW/Trae_Gromacs/gromacs")
    print("=" * 70)
    print("全面检测所有GROMACS版本")
    print("=" * 70)

    # 用户要求保留的版本
    KEEP = {
        "gromacs-2025.1-SM120-AVX512",
        "gromacs-2026.1-plumed-CUDA",
        "gromacs-2026.3-AVX2-CUDA",
        "gromacs-2026.3-AVX512-CUDA",
        "gromacs-2026.3-AVX512-CUDA-PLUMED",
        "gromacs-2026.3-AVX512-CUDA-PLUMED-sm120",
        "gromacs-2026.3-AVX512-CUDA-sm120-final2",
    }

    versions = []

    for d in sorted(base.iterdir()):
        if not d.is_dir():
            continue
        name = d.name
        gmx = d / "bin" / "gmx.exe"
        if not gmx.exists():
            continue

        # 检查gmx.exe可执行性
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            r = subprocess.run([str(gmx), "--version"], capture_output=True, text=True, timeout=15, startupinfo=startupinfo)
            exe_ok = r.returncode == 0
            version_out = r.stdout + r.stderr
        except Exception as e:
            exe_ok = False
            version_out = ""

        # 检查PLUMED支持（运行mdrun -h检测，而非仅检查文件）
        plumed_status = "N/A"
        if "plumed" in name.lower():
            try:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                r2 = subprocess.run([str(gmx), "mdrun", "-h"], capture_output=True, text=True, timeout=15, startupinfo=startupinfo)
                mdrun_out = r2.stdout + r2.stderr
                if "-plumed" in mdrun_out or "plumed.dat" in mdrun_out:
                    # 区分静态链接和动态链接
                    kernel = d / "bin" / "libplumedKernel.dll"
                    if kernel.exists():
                        plumed_status = "SUPPORTED (动态链接)"
                    else:
                        plumed_status = "SUPPORTED (静态链接)"
                else:
                    plumed_status = "BROKEN (不支持-plumed参数)"
            except Exception as e:
                plumed_status = f"BROKEN (检测异常: {e})"

        # 检查CUDA
        bin_dir = d / "bin"
        cudart = bin_dir / "cudart64_13.dll"
        cuda_ok = cudart.exists()

        # 检查力场
        ff = d / "share" / "gromacs" / "top"
        ff_ok = ff.exists() and any(ff.iterdir())

        # 检查gmx.exe大小（过小可能编译失败）
        gmx_size = gmx.stat().st_size
        size_ok = gmx_size > 1024 * 1024

        action = "保留" if name in KEEP else "删除"

        total_mb = round(sum(f.stat().st_size for f in d.rglob("*") if f.is_file()) / (1024*1024), 1)

        versions.append({
            "name": name, "exe_ok": exe_ok, "plumed_status": plumed_status,
            "cuda_ok": cuda_ok, "ff_ok": ff_ok, "size_ok": size_ok, "action": action,
            "size_mb": total_mb, "gmx_size_mb": round(gmx_size/(1024*1024),1)
        })

        print(f"\n[{action}] {name}")
        print(f"  gmx.exe: {'OK' if exe_ok else 'FAIL'} ({versions[-1]['gmx_size_mb']} MB)")
        print(f"  PLUMED: {plumed_status}")
        print(f"  CUDA: {'OK' if cuda_ok else 'MISSING'}")
        print(f"  力场: {'OK' if ff_ok else 'MISSING'}")
        print(f"  大小: {total_mb} MB")

    print("\n" + "=" * 70)
    print("检测完成")
    print("=" * 70)

    # 总结
    ok_versions = [v for v in versions if v['exe_ok'] and v['size_ok']]
    broken_versions = [v for v in versions if not v['exe_ok'] or not v['size_ok']]
    plumed_broken = [v for v in versions if "BROKEN" in v['plumed_status']]

    print(f"\n总版本数: {len(versions)}")
    print(f"完全正常: {len(ok_versions)}")
    print(f"运行异常: {len(broken_versions)}")
    if plumed_broken:
        print(f"PLUMED异常: {len(plumed_broken)}")
        for v in plumed_broken:
            print(f"  - {v['name']}: {v['plumed_status']}")
    else:
        print("PLUMED状态: 全部正常")

    # 检查是否有不在KEEP列表中的版本
    extra = [v for v in versions if v['name'] not in KEEP]
    if extra:
        print(f"\n注意: 以下版本不在保留列表中，建议删除:")
        for v in extra:
            print(f"  - {v['name']}")


if __name__ == "__main__":
    main()
