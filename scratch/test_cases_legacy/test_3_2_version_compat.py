#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多版本GROMACS兼容性隐患检测脚本
检测维度：元数据完整性 / 旧版本SIMD与CUDA标识 / SM120特殊版本 / PLUMED状态 / 交叉切换缓存一致性
"""

import sys
sys.path.insert(0, r"D:\YDW\Trae_Gromacs\source")

from core.version_manager import VersionManager, VersionValidity, PlumedStatus
import os
import json


def main():
    # ------------------------------------------------------------------
    # 1. 扫描全部版本（不过滤、不去重），获取每个版本的完整元数据
    # ------------------------------------------------------------------
    vm = VersionManager()
    all_versions = vm.scan_versions(filter_invalid=False, deduplicate=False)

    if not all_versions:
        print("[ERROR] 未扫描到任何版本，请检查 gromacs 目录是否存在。")
        return

    print(f"扫描到 {len(all_versions)} 个版本，开始兼容性隐患检测...\n")

    issues = []  # 每条: (隐患描述, 涉及版本, 严重程度)

    # ------------------------------------------------------------------
    # 2. 检查每个版本的元数据完整性
    # ------------------------------------------------------------------
    for name, meta in all_versions.items():
        # 2a. gmx_exe 是否存在
        if not meta.gmx_exe or not os.path.isfile(meta.gmx_exe):
            issues.append((
                f"gmx_exe 路径不存在或为空: {meta.gmx_exe}",
                name,
                "HIGH"
            ))

        # 2b. size_mb 是否合理（<1 MB 或 >2000 MB 视为异常）
        if meta.size_mb <= 0:
            issues.append((
                f"size_mb 为 0，目录大小可能未正确计算",
                name,
                "MEDIUM"
            ))
        elif meta.size_mb < 1:
            issues.append((
                f"size_mb 仅 {meta.size_mb} MB，安装极不完整",
                name,
                "HIGH"
            ))
        elif meta.size_mb > 2000:
            issues.append((
                f"size_mb 达 {meta.size_mb} MB，可能包含编译垃圾或调试符号",
                name,
                "LOW"
            ))

        # 2c. hash_id 是否有值
        if not meta.hash_id:
            issues.append((
                "hash_id 为空，版本唯一标识计算失败",
                name,
                "MEDIUM"
            ))

        # 2d. valid 状态与 validity_detail 是否一致
        if not meta.valid and meta.validity_status == VersionValidity.VALID.value:
            issues.append((
                "valid=False 但 validity_status 为 VALID，状态不一致",
                name,
                "HIGH"
            ))
        if not meta.valid and not meta.validity_detail:
            issues.append((
                "valid=False 但 validity_detail 为空，缺少失效原因",
                name,
                "MEDIUM"
            ))

    # ------------------------------------------------------------------
    # 3. 检查旧版本（2025系列）是否缺失 SIMD 标识、CUDA 标识
    # ------------------------------------------------------------------
    for name, meta in all_versions.items():
        if "2025" not in name:
            continue

        missing_fields = []
        if not meta.simd:
            missing_fields.append("SIMD")
        if not meta.gpu:
            missing_fields.append("GPU/CUDA")

        if missing_fields:
            issues.append((
                f"2025旧版本缺失标识字段: {', '.join(missing_fields)}，"
                f"可能导致版本选择器无法按SIMD/GPU筛选",
                name,
                "MEDIUM"
            ))

        # 即使名称中有 CUDA 但元数据 gpu 为空也告警
        if "cuda" in name.lower() and not meta.gpu:
            issues.append((
                "名称含CUDA但元数据gpu字段为空，gmx --version可能未正确输出GPU信息",
                name,
                "HIGH"
            ))

        # 即使名称中有 AVX 但元数据 simd 为空也告警
        name_lower = name.lower()
        has_simd_in_name = any(kw in name_lower for kw in ("avx512", "avx2", "sse"))
        if has_simd_in_name and not meta.simd:
            issues.append((
                "名称含SIMD标识但元数据simd字段为空，gmx --version可能未正确输出SIMD信息",
                name,
                "HIGH"
            ))

    # ------------------------------------------------------------------
    # 4. 检查 SM120 特殊版本的元数据是否正常
    # ------------------------------------------------------------------
    for name, meta in all_versions.items():
        if "sm120" not in name.lower():
            continue

        sm120_issues = []

        # 4a. 必须声明 CUDA 支持
        if "cuda" not in meta.gpu.lower():
            sm120_issues.append("gpu字段未声明CUDA（sm120依赖CUDA）")

        # 4b. build_params 中应有 cuda_arch
        if not meta.build_params.get("cuda_arch"):
            sm120_issues.append("build_params缺少cuda_arch=sm_120")

        # 4c. 版本应有效
        if not meta.valid:
            sm120_issues.append(f"版本无效({meta.validity_detail})")

        # 4d. hash_id 应存在
        if not meta.hash_id:
            sm120_issues.append("hash_id为空")

        if sm120_issues:
            issues.append((
                "SM120特殊版本元数据异常: " + "; ".join(sm120_issues),
                name,
                "HIGH"
            ))

    # ------------------------------------------------------------------
    # 5. 检查 PLUMED 版本的 PLUMED 状态是否正确
    # ------------------------------------------------------------------
    for name, meta in all_versions.items():
        name_lower = name.lower()
        if "plumed" not in name_lower:
            continue

        # 5a. 名称含PLUMED但状态非SUPPORTED → 可能文件缺失或损坏
        if meta.plumed_status != PlumedStatus.SUPPORTED.value:
            issues.append((
                f"名称含PLUMED但plumed_status={meta.plumed_status} "
                f"({meta.plumed_detail})，预期应为supported",
                name,
                "HIGH" if meta.plumed_status == PlumedStatus.BROKEN_LIBRARY.value else "MEDIUM"
            ))

        # 5b. 名称含PLUMED但plumed字段非enabled
        if meta.plumed.lower() not in ("yes", "enabled", "是", "true"):
            issues.append((
                f"名称含PLUMED但plumed字段为 '{meta.plumed}'，与名称声明不一致",
                name,
                "MEDIUM"
            ))

        # 5c. 名称含PLUMED但版本无效 → 需要特别关注
        if not meta.valid:
            issues.append((
                f"PLUMED版本无效: {meta.validity_detail}",
                name,
                "HIGH"
            ))

    # 反向检查：名称不含PLUMED但plumed_status为SUPPORTED（可能命名遗漏）
    for name, meta in all_versions.items():
        if "plumed" in name.lower():
            continue
        if meta.plumed_status == PlumedStatus.SUPPORTED.value:
            issues.append((
                "版本实际支持PLUMED但名称未标注，可能造成用户误选",
                name,
                "LOW"
            ))

    # ------------------------------------------------------------------
    # 6. 对每对版本做交叉检查：切换时是否可能导致状态缓存未刷新
    # ------------------------------------------------------------------
    version_names = list(all_versions.keys())
    for i in range(len(version_names)):
        for j in range(i + 1, len(version_names)):
            name_a = version_names[i]
            name_b = version_names[j]
            meta_a = all_versions[name_a]
            meta_b = all_versions[name_b]

            # 6a. hash_id 相同但名称不同 → 切换时用户以为换了版本，
            #     实际二进制完全一致，状态缓存不会刷新
            if (meta_a.hash_id and meta_b.hash_id
                    and meta_a.hash_id == meta_b.hash_id
                    and name_a != name_b):
                issues.append((
                    f"与 {name_b} 的hash_id相同({meta_a.hash_id})，"
                    f"切换版本时状态缓存可能不会刷新（二进制完全一致）",
                    f"{name_a} / {name_b}",
                    "MEDIUM"
                ))

            # 6b. SIMD 不同但 gmx_exe 大小接近 → 可能误用旧缓存
            try:
                size_a = os.path.getsize(meta_a.gmx_exe) if os.path.isfile(meta_a.gmx_exe) else 0
                size_b = os.path.getsize(meta_b.gmx_exe) if os.path.isfile(meta_b.gmx_exe) else 0
                if (size_a > 0 and size_b > 0
                        and meta_a.simd != meta_b.simd
                        and abs(size_a - size_b) < 1024 * 100):  # 差异 <100KB
                    issues.append((
                        f"SIMD不同({meta_a.simd} vs {meta_b.simd})但gmx.exe大小几乎相同"
                        f"({size_a} vs {size_b}字节)，切换时环境变量缓存可能残留",
                        f"{name_a} / {name_b}",
                        "MEDIUM"
                    ))
            except OSError:
                pass

            # 6c. GPU 支持状态不同但路径深度/结构相同 → 运行时DLL搜索路径可能冲突
            if (meta_a.gpu != meta_b.gpu
                    and meta_a.valid and meta_b.valid):
                path_a = os.path.normpath(meta_a.path)
                path_b = os.path.normpath(meta_b.path)
                # 路径深度相同且父目录一致
                if (os.path.dirname(path_a) == os.path.dirname(path_b)):
                    issues.append((
                        f"GPU支持不同({meta_a.gpu} vs {meta_b.gpu})且同目录下，"
                        f"PATH环境变量中DLL搜索顺序可能导致缓存混淆",
                        f"{name_a} / {name_b}",
                        "LOW"
                    ))

    # ------------------------------------------------------------------
    # 输出：版本兼容隐患清单
    # ------------------------------------------------------------------
    severity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    issues.sort(key=lambda x: (severity_order.get(x[2], 99), x[1]))

    print("=" * 80)
    print("  多版本 GROMACS 兼容性隐患清单")
    print("=" * 80)

    if not issues:
        print("\n  未发现兼容性隐患，所有版本元数据完整、状态一致。\n")
    else:
        high_count = sum(1 for _, _, s in issues if s == "HIGH")
        medium_count = sum(1 for _, _, s in issues if s == "MEDIUM")
        low_count = sum(1 for _, _, s in issues if s == "LOW")

        print(f"\n  共发现 {len(issues)} 条隐患  "
              f"[HIGH: {high_count}] [MEDIUM: {medium_count}] [LOW: {low_count}]\n")
        print("-" * 80)

        for idx, (desc, versions, severity) in enumerate(issues, 1):
            severity_tag = f"[{severity}]"
            print(f"\n  {idx:>3}. {severity_tag:<8} 涉及版本: {versions}")
            print(f"       隐患描述: {desc}")

    print("\n" + "=" * 80)
    print("  检测完成")
    print("=" * 80)


if __name__ == "__main__":
    main()
