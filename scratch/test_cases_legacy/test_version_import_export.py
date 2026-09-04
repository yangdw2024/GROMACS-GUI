#!/usr/bin/env python3
"""测试GROMACS版本批量导入/导出功能"""
import sys
import os
import shutil
import zipfile
from pathlib import Path

sys.path.insert(0, r"D:\YDW\Trae_Gromacs\source")

# 清除单例缓存
for mod in ['core.logger', 'core.version_manager']:
    if mod in sys.modules:
        del sys.modules[mod]

from core.version_manager import VersionManager

TEST_DIR = Path(r"D:\YDW\Trae_Gromacs\test_version_io")
EXPORT_DIR = TEST_DIR / "export_output"
MOCK_GROMACS_DIR = TEST_DIR / "gromacs" / "test-version-export"

def setup_mock_version():
    """创建模拟的GROMACS版本目录用于导出测试"""
    if MOCK_GROMACS_DIR.exists():
        shutil.rmtree(MOCK_GROMACS_DIR)
    MOCK_GROMACS_DIR.mkdir(parents=True)

    # 创建核心结构
    bin_dir = MOCK_GROMACS_DIR / "bin"
    bin_dir.mkdir()
    share_top = MOCK_GROMACS_DIR / "share" / "gromacs" / "top"
    share_top.mkdir(parents=True)

    # 创建假gmx.exe（足够大以通过大小检查，但不会真的被执行）
    fake_gmx = bin_dir / "gmx.exe"
    fake_gmx.write_bytes(b"x" * (2 * 1024 * 1024))  # 2MB假exe

    # 创建力场目录
    ff_dir = share_top / "amber99sb-ildn.ff"
    ff_dir.mkdir()
    (ff_dir / "forcefield.itp").write_text("; fake forcefield")

    # 创建临时编译垃圾文件（应被导出过滤）
    (bin_dir / "CMakeCache.txt").write_text("fake cmake cache")
    (bin_dir / "test.pyc").write_bytes(b"fake pyc")
    cache_dir = bin_dir / "__pycache__"
    cache_dir.mkdir()
    (cache_dir / "test.pyc").write_bytes(b"fake cache")

    # 创建正常文件（应保留）
    (bin_dir / "gmxapi.dll").write_bytes(b"x" * 1000)

    return str(MOCK_GROMACS_DIR)


def test_export():
    """测试1: 导出功能 - 垃圾文件过滤、压缩包生成"""
    print("=" * 60)
    print("Test 1: 版本导出（过滤垃圾文件）")
    print("=" * 60)

    # 重置单例
    VersionManager._instance = None
    vm = VersionManager()

    # 手动构造版本元数据
    from core.version_manager import VersionMetadata
    mock_path = setup_mock_version()
    mock_gmx = str(Path(mock_path) / "bin" / "gmx.exe")

    meta = VersionMetadata(
        name="test-version-export",
        path=mock_path,
        gmx_exe=mock_gmx,
        valid=True,
        size_mb=2.1,
    )
    vm._versions["test-version-export"] = meta

    # 执行导出
    if EXPORT_DIR.exists():
        shutil.rmtree(EXPORT_DIR)
    EXPORT_DIR.mkdir(parents=True)

    exported, errors = vm.export_versions(["test-version-export"], str(EXPORT_DIR))

    print(f"  Exported: {exported}, Errors: {errors}")
    assert exported == 1, f"Expected 1 export, got {exported}"
    assert not errors, f"Unexpected errors: {errors}"

    # 检查压缩包存在
    zip_path = EXPORT_DIR / "test-version-export.zip"
    assert zip_path.exists(), "Export zip file not found"

    # 检查垃圾文件被过滤
    with zipfile.ZipFile(str(zip_path), 'r') as zf:
        names = zf.namelist()
        print(f"  Zip contents count: {len(names)}")

        # 垃圾文件不应存在
        has_cmake = any("CMakeCache" in n for n in names)
        has_pyc = any(n.endswith(".pyc") for n in names)
        has_pycache = any("__pycache__" in n for n in names)

        assert not has_cmake, "CMakeCache.txt should be filtered out"
        assert not has_pyc, ".pyc files should be filtered out"
        assert not has_pycache, "__pycache__ should be filtered out"
        print("[PASS] 垃圾文件已被过滤")

        # 正常文件应保留
        has_gmx = any("gmx.exe" in n for n in names)
        has_ff = any("forcefield.itp" in n for n in names)
        has_dll = any("gmxapi.dll" in n for n in names)

        assert has_gmx, "gmx.exe should be in export"
        assert has_ff, "forcefield.itp should be in export"
        assert has_dll, "gmxapi.dll should be in export"
        print("[PASS] 正常文件已保留")

    print("[PASS] 导出测试通过")
    return str(zip_path)


def test_import_valid(zip_path):
    """测试2: 导入有效版本 - 自动校验、版本列表更新"""
    print("\n" + "=" * 60)
    print("Test 2: 版本导入（自动校验）")
    print("=" * 60)

    # 导入到新目录
    import_dir = TEST_DIR / "import_target"
    if import_dir.exists():
        shutil.rmtree(import_dir)
    import_dir.mkdir(parents=True)

    VersionManager._instance = None
    vm = VersionManager()
    # 预填充一些版本（空）
    vm._versions = {}

    imported, conflicts = vm.import_versions([zip_path], str(import_dir))

    print(f"  Imported: {imported}, Conflicts: {conflicts}")
    # 导入可能因gmx.exe无效而报告无效，但文件结构应正确解压
    target_dir = import_dir / "test-version-export"
    assert target_dir.exists(), "Import target directory should exist"

    # 检查bin/gmx.exe被解压
    gmx_in_import = target_dir / "bin" / "gmx.exe"
    assert gmx_in_import.exists(), "gmx.exe should be extracted from import"
    print(f"[PASS] 导入目录结构正确 (gmx.exe exists: {gmx_in_import.exists()})")

    # 版本应加入扫描列表
    assert "test-version-export" in vm._versions, "Version should be in scan list"
    print("[PASS] 导入版本已加入扫描列表")


def test_import_conflict():
    """测试3: 冲突检测 - 同名版本导入提示"""
    print("\n" + "=" * 60)
    print("Test 3: 冲突检测")
    print("=" * 60)

    # 创建一个已存在的目标目录
    import_dir = TEST_DIR / "conflict_target"
    if import_dir.exists():
        shutil.rmtree(import_dir)
    conflict_dir = import_dir / "test-version-export"
    conflict_dir.mkdir(parents=True)
    (conflict_dir / "placeholder.txt").write_text("existing")

    VersionManager._instance = None
    vm = VersionManager()
    vm._versions = {}

    zip_path = EXPORT_DIR / "test-version-export.zip"
    imported, conflicts = vm.import_versions([str(zip_path)], str(import_dir))

    print(f"  Imported: {imported}, Conflicts: {conflicts}")
    assert imported == 0, "Conflicting version should not be imported"
    assert any("已存在" in c for c in conflicts), f"Should report conflict, got: {conflicts}"
    print("[PASS] 冲突版本正确拒绝导入")


def test_import_invalid():
    """测试4: 无效压缩包导入 - 缺少gmx.exe"""
    print("\n" + "=" * 60)
    print("Test 4: 无效压缩包导入")
    print("=" * 60)

    # 创建不含gmx.exe的假ZIP
    invalid_zip = TEST_DIR / "invalid_version.zip"
    if invalid_zip.exists():
        invalid_zip.unlink()
    with zipfile.ZipFile(str(invalid_zip), 'w') as zf:
        zf.writestr("readme.txt", "This is not a GROMACS version")

    import_dir = TEST_DIR / "invalid_target"
    if import_dir.exists():
        shutil.rmtree(import_dir)
    import_dir.mkdir(parents=True)

    VersionManager._instance = None
    vm = VersionManager()

    imported, conflicts = vm.import_versions([str(invalid_zip)], str(import_dir))

    print(f"  Imported: {imported}, Conflicts: {conflicts}")
    assert imported == 0, "Invalid version should not be imported"
    assert any("gmx.exe" in c for c in conflicts), f"Should report missing gmx.exe, got: {conflicts}"
    print("[PASS] 无效压缩包正确拒绝")


if __name__ == "__main__":
    try:
        zip_path = test_export()
        test_import_valid(zip_path)
        test_import_conflict()
        test_import_invalid()
        print("\n=== VERSION IMPORT/EXPORT TEST PASSED ===")
    finally:
        # 清理
        if TEST_DIR.exists():
            shutil.rmtree(TEST_DIR)
