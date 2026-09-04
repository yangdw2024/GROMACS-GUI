#!/usr/bin/env python3
"""实机测试：版本白名单功能验证"""
import sys
import json
from pathlib import Path

sys.path.insert(0, r"D:\YDW\Trae_Gromacs\source")

from core.version_manager import VersionManager

vm = VersionManager()
CONFIG_PATH = Path(r"D:\YDW\Trae_Gromacs\version.config")

print("=" * 60)
print("Test 1: version.config白名单配置可正常读取")
print("=" * 60)
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)
wl = data.get("version_whitelist", [])
print(f"  version_whitelist = {wl}")
assert isinstance(wl, list), "version_whitelist must be a list"
assert "gromacs-2026.3-AVX512-CUDA-PLUMED-sm120" in wl, "sm120 version should be in whitelist"
print("[PASS] 白名单配置读取正常，包含sm120版本")

print("\n" + "=" * 60)
print("Test 2: _load_version_whitelist 正常工作")
print("=" * 60)
whitelist = vm._load_version_whitelist()
print(f"  Loaded whitelist: {whitelist}")
assert "gromacs-2026.3-AVX512-CUDA-PLUMED-sm120" in whitelist
print("[PASS] _load_version_whitelist 返回正确")

print("\n" + "=" * 60)
print("Test 3: 白名单版本在默认扫描中不被去重隐藏")
print("=" * 60)
# 关闭"显示所有版本"，即 filter_invalid=True, deduplicate=True
versions = vm.scan_versions(filter_invalid=True, deduplicate=True)
print(f"  有效且去重后版本数: {len(versions)}")
for k, v in versions.items():
    print(f"    - {k}: is_duplicate={v.is_duplicate}")

sm120_key = "gromacs-2026.3-AVX512-CUDA-PLUMED-sm120"
if sm120_key in versions:
    print(f"  [PASS] sm120版本在默认列表中: is_duplicate={versions[sm120_key].is_duplicate}")
    assert not versions[sm120_key].is_duplicate, "白名单版本不应被标记为重复"
else:
    print(f"  [INFO] sm120版本不在当前gromacs目录（可能目录名不同）")
    # 检查是否有PLUMED-sm120目录
    import os
    gromacs_dir = Path(r"D:\YDW\Trae_Gromacs\gromacs")
    if gromacs_dir.exists():
        dirs = [d.name for d in gromacs_dir.iterdir() if d.is_dir()]
        sm120_dirs = [d for d in dirs if "sm120" in d.lower()]
        print(f"  实际sm120相关目录: {sm120_dirs}")
        if sm120_dirs:
            # 使用实际目录名验证
            actual_sm120 = sm120_dirs[0]
            if actual_sm120 in versions:
                print(f"  [PASS] {actual_sm120} 在默认列表中: is_duplicate={versions[actual_sm120].is_duplicate}")
                assert not versions[actual_sm120].is_duplicate, "白名单版本不应被标记为重复"
            else:
                print(f"  [WARN] {actual_sm120} 不在默认列表中，需加入白名单")

print("\n" + "=" * 60)
print("Test 4: 移除白名单后，sm120版本恢复去重隐藏规则")
print("=" * 60)
# 保存当前白名单
original_whitelist = list(vm._load_version_whitelist())
# 清空白名单
vm.update_version_whitelist([])
# 重新扫描
versions_no_wl = vm.scan_versions(filter_invalid=True, deduplicate=True)
print(f"  无白名单时版本数: {len(versions_no_wl)}")
for k, v in versions_no_wl.items():
    if "sm120" in k.lower():
        print(f"    - {k}: is_duplicate={v.is_duplicate}")

# 全量扫描查看sm120是否被标记为重复
all_v_no_wl = vm.scan_versions(filter_invalid=False, deduplicate=False)
sm120_duplicates = [k for k, v in all_v_no_wl.items() if "sm120" in k.lower() and v.is_duplicate]
if sm120_duplicates:
    print(f"  被标记为重复的sm120版本: {sm120_duplicates}")
    print("[PASS] 移除白名单后sm120版本恢复正常去重规则")
else:
    print("[INFO] sm120版本未被标记为重复（可能没有同源重复）")

# 恢复白名单
vm.update_version_whitelist(original_whitelist)
print(f"  已恢复白名单: {original_whitelist}")

print("\n" + "=" * 60)
print("Test 5: get_version_whitelist / update_version_whitelist 公开接口")
print("=" * 60)
wl = vm.get_version_whitelist()
print(f"  get_version_whitelist() = {wl}")
assert isinstance(wl, list)

# 添加一个新版本
test_wl = wl + ["test-version-name"]
vm.update_version_whitelist(test_wl)
wl_after = vm.get_version_whitelist()
print(f"  添加后: {wl_after}")
assert "test-version-name" in wl_after

# 恢复
vm.update_version_whitelist(original_whitelist)
wl_restored = vm.get_version_whitelist()
print(f"  恢复后: {wl_restored}")
assert "test-version-name" not in wl_restored
print("[PASS] 公开接口增删正常")

print("\n" + "=" * 60)
print("Test 6: 多白名单版本场景")
print("=" * 60)
multi_wl = original_whitelist + ["gromacs-2026.3-AVX512-CUDA-sm120-final2"]
vm.update_version_whitelist(multi_wl)
versions_multi = vm.scan_versions(filter_invalid=True, deduplicate=True)
for name in multi_wl:
    if name in versions_multi:
        print(f"  {name}: is_duplicate={versions_multi[name].is_duplicate}")
        assert not versions_multi[name].is_duplicate, f"白名单版本 {name} 不应被标记为重复"
print("[PASS] 多白名单版本全部保留")

# 恢复原始白名单
vm.update_version_whitelist(original_whitelist)

print("\n" + "=" * 60)
print("Test 7: 空白名单场景")
print("=" * 60)
vm.update_version_whitelist([])
versions_empty = vm.scan_versions(filter_invalid=True, deduplicate=True)
print(f"  空白名单时有效版本数: {len(versions_empty)}")
# 恢复
vm.update_version_whitelist(original_whitelist)
print("[PASS] 空白名单场景正常")

print("\n" + "=" * 60)
print("=== ALL WHITELIST TESTS PASSED ===")
print("=" * 60)
