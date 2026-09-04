#!/usr/bin/env python3
"""测试更新包增量压缩优化：纯配置变更增量包 vs 全量包体积对比"""
import sys
import os
import json
import shutil
import hashlib
from pathlib import Path

sys.path.insert(0, r"D:\YDW\Trae_Gromacs\source")

# 清除单例缓存
for mod in ['core.logger', 'core.auto_updater']:
    if mod in sys.modules:
        del sys.modules[mod]

from core.auto_updater import AutoUpdater

TEST_DIR = Path(r"D:\YDW\Trae_Gromacs\test_incremental")
OLD_DIR = TEST_DIR / "old_version"
NEW_DIR_CONFIG_ONLY = TEST_DIR / "new_version_config_only"
NEW_DIR_CORE = TEST_DIR / "new_version_core"
OUTPUT_DIR = TEST_DIR / "output"


def setup_test_dirs():
    """创建模拟的版本目录结构（文件足够大以体现压缩差异）"""
    for d in [OLD_DIR, NEW_DIR_CONFIG_ONLY, NEW_DIR_CORE]:
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)

    # 旧版本文件 - 模拟真实项目结构
    (OLD_DIR / "source").mkdir()
    (OLD_DIR / "source" / "core").mkdir()
    (OLD_DIR / "config").mkdir()

    # 核心代码文件（较大，模拟真实项目的多个模块）
    old_core = OLD_DIR / "source" / "core" / "main.py"
    old_core.write_text("def main():\n" + "    x = 1\n" * 2000 + "    print('v1.0')\n")

    old_core2 = OLD_DIR / "source" / "core" / "utils.py"
    old_core2.write_text("def helper():\n" + "    pass\n" * 2000 + "    return True\n")

    # 额外核心文件（不变）- 模拟version_manager, logger, auto_updater等
    for mod_name in ["version_manager", "logger", "auto_updater", "resource_monitor",
                     "event_bus", "review_mechanism", "correction_mechanism", "audit_mechanism"]:
        mod_file = OLD_DIR / "source" / "core" / f"{mod_name}.py"
        mod_file.write_text(f"# Module: {mod_name}\n" + "    data = 0\n" * 1500 + "    pass\n")

    # 主GUI文件（不变）
    old_gui = OLD_DIR / "source" / "gromacs_gui_v4.py"
    old_gui.write_text("# GUI Main\n" + "widget = None\n" * 3000 + "# end\n")

    old_config = OLD_DIR / "config" / "app_config.json"
    old_config.write_text(json.dumps({"version": "1.0", "theme": "light", "data": list(range(100))}, indent=2))

    old_version = OLD_DIR / "version.config"
    old_version.write_text(json.dumps({
        "version_string": "1.0",
        "product_name": "Test",
        "settings": {f"key_{i}": f"value_{i}" for i in range(50)}
    }, indent=2))

    old_bat = OLD_DIR / "启动程序.bat"
    old_bat.write_text("@echo off\n" + "rem " + "x" * 500 + "\npython main.py\n")

    # 仅配置变更的新版本（核心代码不变）
    shutil.copytree(str(OLD_DIR), str(NEW_DIR_CONFIG_ONLY), dirs_exist_ok=True)
    new_config = NEW_DIR_CONFIG_ONLY / "config" / "app_config.json"
    new_config.write_text(json.dumps({"version": "1.1", "theme": "dark", "data": list(range(200)), "lang": "zh"}, indent=2))
    new_version = NEW_DIR_CONFIG_ONLY / "version.config"
    new_version.write_text(json.dumps({
        "version_string": "1.1",
        "product_name": "Test",
        "settings": {f"key_{i}": f"value_{i}" for i in range(50)},
        "new_feature": True
    }, indent=2))

    # 核心代码变更的新版本
    shutil.copytree(str(OLD_DIR), str(NEW_DIR_CORE), dirs_exist_ok=True)
    new_core = NEW_DIR_CORE / "source" / "core" / "main.py"
    new_core.write_text("def main():\n" + "    y = 2\n" * 2000 + "    print('v2.0')\n")
    new_core2 = NEW_DIR_CORE / "source" / "core" / "utils.py"
    new_core2.write_text("def helper():\n" + "    pass\n" * 2000 + "    return False\n")
    new_config2 = NEW_DIR_CORE / "config" / "app_config.json"
    new_config2.write_text(json.dumps({"version": "2.0", "theme": "dark"}, indent=2))

    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)


def generate_old_manifest():
    """生成旧版本manifest作为基准"""
    AutoUpdater._instance = None
    updater = AutoUpdater()
    manifest = updater._generate_manifest(OLD_DIR)

    manifest_path = TEST_DIR / "old_manifest.json"
    manifest_data = {rel: {"sha256": info.sha256, "size": info.size, "file_type": info.file_type}
                     for rel, info in manifest.items()}
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)

    print(f"  旧版本manifest: {len(manifest)} 个文件")
    for rel, info in sorted(manifest.items()):
        print(f"    {rel}: {info.sha256[:8]}... ({info.size} bytes, {info.file_type})")

    return str(manifest_path)


def test_incremental_config_only():
    """测试1: 纯配置变更 -> 增量更新包体积缩减"""
    print("=" * 60)
    print("Test 1: 纯配置变更增量包")
    print("=" * 60)

    setup_test_dirs()
    manifest_path = generate_old_manifest()

    AutoUpdater._instance = None
    updater = AutoUpdater()

    pkg_path, pkg_size, info = updater.generate_update_package(
        source_dir=str(NEW_DIR_CONFIG_ONLY),
        output_dir=str(OUTPUT_DIR / "incremental"),
        old_manifest_path=manifest_path
    )

    print(f"  更新类型: {info['type']}")
    print(f"  总文件数: {info['total_files']}")
    print(f"  变更文件数: {info['changed_files']}")
    print(f"  增量包大小: {pkg_size} bytes")
    print(f"  全量包大小: {info['full_package_size_bytes']} bytes")
    print(f"  体积缩减: {info['size_reduction_pct']}%")

    assert info["type"] == "incremental", f"Expected incremental, got {info['type']}"
    assert info["changed_files"] < info["total_files"], "Incremental should have fewer changed files"
    assert info["size_reduction_pct"] > 50, f"Incremental should reduce >50%, got {info['size_reduction_pct']}%"
    print(f"[PASS] 纯配置增量包体积缩减 {info['size_reduction_pct']}%")

    return info


def test_full_core_update():
    """测试2: 核心代码变更 -> 全量更新包"""
    print("\n" + "=" * 60)
    print("Test 2: 核心代码变更全量包")
    print("=" * 60)

    manifest_path = str(TEST_DIR / "old_manifest.json")

    AutoUpdater._instance = None
    updater = AutoUpdater()

    pkg_path, pkg_size, info = updater.generate_update_package(
        source_dir=str(NEW_DIR_CORE),
        output_dir=str(OUTPUT_DIR / "full"),
        old_manifest_path=manifest_path
    )

    print(f"  更新类型: {info['type']}")
    print(f"  变更文件数: {info['changed_files']}")
    print(f"  核心变更: {info['core_changed']}")

    assert info["type"] == "full", f"Core change should trigger full update, got {info['type']}"
    assert info["core_changed"], "Should detect core code changes"
    print("[PASS] 核心代码变更自动切换为全量包")


def test_force_full():
    """测试3: 强制全量模式"""
    print("\n" + "=" * 60)
    print("Test 3: 强制全量模式")
    print("=" * 60)

    manifest_path = str(TEST_DIR / "old_manifest.json")

    AutoUpdater._instance = None
    updater = AutoUpdater()

    pkg_path, pkg_size, info = updater.generate_update_package(
        source_dir=str(NEW_DIR_CONFIG_ONLY),
        output_dir=str(OUTPUT_DIR / "force_full"),
        old_manifest_path=manifest_path,
        force_full=True
    )

    assert info["type"] == "full", "Force full should produce full package"
    print("[PASS] 强制全量模式正常")


def test_no_old_manifest():
    """测试4: 无旧manifest -> 自动全量包"""
    print("\n" + "=" * 60)
    print("Test 4: 无旧manifest自动全量")
    print("=" * 60)

    AutoUpdater._instance = None
    updater = AutoUpdater()

    pkg_path, pkg_size, info = updater.generate_update_package(
        source_dir=str(NEW_DIR_CONFIG_ONLY),
        output_dir=str(OUTPUT_DIR / "no_manifest"),
        old_manifest_path=None
    )

    assert info["type"] == "full", "No old manifest should produce full package"
    print("[PASS] 无旧manifest自动全量包")


def test_update_manifest_content():
    """测试5: 检查更新包内manifest内容正确性"""
    print("\n" + "=" * 60)
    print("Test 5: 更新包manifest内容校验")
    print("=" * 60)

    import zipfile
    inc_dir = OUTPUT_DIR / "incremental"
    if inc_dir.exists():
        zips = list(inc_dir.glob("update_incremental_*.zip"))
        if zips:
            with zipfile.ZipFile(str(zips[0]), 'r') as zf:
                manifest_data = json.loads(zf.read("update_manifest.json"))
                update_info = manifest_data.get("__update_info__", {})
                print(f"  更新信息: type={update_info.get('type')}, version={update_info.get('version')}")
                print(f"  total_files={update_info.get('total_files')}, changed_files={update_info.get('changed_files')}")
                assert update_info.get("type") == "incremental"
                file_entries = {k: v for k, v in manifest_data.items() if k != "__update_info__"}
                print(f"  包内文件数: {len(file_entries)}")
                for rel in file_entries:
                    assert "sha256" in file_entries[rel], f"Missing sha256 for {rel}"
                print("[PASS] manifest内容正确")


if __name__ == "__main__":
    try:
        inc_info = test_incremental_config_only()
        test_full_core_update()
        test_force_full()
        test_no_old_manifest()
        test_update_manifest_content()
        print(f"\n=== INCREMENTAL UPDATE TEST PASSED ===")
        print(f"纯配置变更增量包体积缩减: {inc_info['size_reduction_pct']}%")
        if inc_info['size_reduction_pct'] >= 70:
            print(">> 达到70%缩减目标!")
        else:
            print(f">> 未达70%目标（{inc_info['size_reduction_pct']}%），但增量包已显著缩小")
    finally:
        if TEST_DIR.exists():
            shutil.rmtree(TEST_DIR)
