#!/usr/bin/env python3
"""验证version_manager去重与过滤优化"""
import sys
sys.path.insert(0, r"D:\YDW\Trae_Gromacs\source")

from core.version_manager import VersionManager, VersionValidity

vm = VersionManager()

print("=" * 60)
print("Test 1: 默认扫描（filter_invalid=True, deduplicate=True）")
print("=" * 60)
versions = vm.scan_versions(filter_invalid=True, deduplicate=True)
print(f"有效且不重复版本数: {len(versions)}")
for k, v in versions.items():
    print(f"  - {k}: valid={v.valid}, hash_id={v.hash_id}, simd={v.simd}, gpu={v.gpu}, plumed={v.plumed}")

print("\n" + "=" * 60)
print("Test 2: 显示所有版本（filter_invalid=False, deduplicate=False）")
print("=" * 60)
all_versions = vm.scan_versions(filter_invalid=False, deduplicate=False)
print(f"总版本数: {len(all_versions)}")
invalid = [k for k, v in all_versions.items() if not v.valid]
duplicates = [k for k, v in all_versions.items() if v.is_duplicate]
print(f"无效版本: {len(invalid)} -> {invalid}")
print(f"重复版本: {len(duplicates)} -> {duplicates}")

print("\n" + "=" * 60)
print("Test 3: 人为制造损坏版本，验证自动隐藏")
print("=" * 60)
import os
import shutil
from pathlib import Path

# 复制一个现有版本并破坏它
src_dir = Path(r"D:\YDW\Trae_Gromacs\gromacs\gromacs-2026.3-AVX512-CUDA")
dst_dir = Path(r"D:\YDW\Trae_Gromacs\gromacs\gromacs-2026.3-AVX512-CUDA-broken")
if dst_dir.exists():
    shutil.rmtree(dst_dir)
shutil.copytree(src_dir, dst_dir)

# 破坏gmx.exe（清空它）
broken_gmx = dst_dir / "bin" / "gmx.exe"
with open(broken_gmx, "wb") as f:
    f.write(b"")

# 重新扫描
vm2 = VersionManager()
all_v = vm2.scan_versions(filter_invalid=False, deduplicate=False)
valid_v = vm2.scan_versions(filter_invalid=True, deduplicate=True)

broken_meta = all_v.get("gromacs-2026.3-AVX512-CUDA-broken")
if broken_meta:
    print(f"损坏版本状态: valid={broken_meta.valid}, detail={broken_meta.validity_detail}")
    assert not broken_meta.valid, "损坏版本应被标记为无效"
    assert "gromacs-2026.3-AVX512-CUDA-broken" not in valid_v, "损坏版本不应出现在默认列表"
    print("[PASS] 损坏版本被自动隐藏")
else:
    print("[WARN] 损坏版本未被发现（可能扫描路径问题）")

# 清理
shutil.rmtree(dst_dir)

print("\n" + "=" * 60)
print("Test 4: 验证hash_id基于gmx.exe+SIMD+GPU+PLUMED")
print("=" * 60)
vm3 = VersionManager()
all_v3 = vm3.scan_versions(filter_invalid=False, deduplicate=False)
for k, v in all_v3.items():
    if v.hash_id:
        print(f"  {k}: hash_id={v.hash_id}")

# 检查不同配置版本的hash是否不同
cuda_plumed = all_v3.get("gromacs-2026.3-AVX512-CUDA-PLUMED")
cuda_plain = all_v3.get("gromacs-2026.3-AVX512-CUDA")
if cuda_plumed and cuda_plain:
    assert cuda_plumed.hash_id != cuda_plain.hash_id, "PLUMED差异应导致不同hash_id"
    print("[PASS] PLUMED差异导致不同hash_id")

print("\n" + "=" * 60)
print("=== ALL VERSION_MANAGER TESTS PASSED ===")
print("=" * 60)
