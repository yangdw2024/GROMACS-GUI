#!/usr/bin/env python3
"""验证一键清理逻辑"""
import sys
import os
import shutil
from pathlib import Path

sys.path.insert(0, r"D:\YDW\Trae_Gromacs\source")

# 在frozen模式下测试_get_app_root
sys.frozen = True
sys.executable = r"D:\YDW\Trae_Gromacs\release\GROMACS_GUI_v4.2.0.exe"

from gromacs_gui_v4 import _get_app_root

app_root = _get_app_root()
print(f"[TEST] _get_app_root() = {app_root}")
assert str(app_root) == r"D:\YDW\Trae_Gromacs\release", f"Unexpected root: {app_root}"

# 测试清理逻辑（模拟）
TEST_ROOT = Path(r"D:\YDW\Trae_Gromacs\test_cleanup_env")
if TEST_ROOT.exists():
    shutil.rmtree(TEST_ROOT)
TEST_ROOT.mkdir(parents=True, exist_ok=True)

# 创建测试文件结构
(TEST_ROOT / "config").mkdir(exist_ok=True)
(TEST_ROOT / "source" / "core").mkdir(parents=True, exist_ok=True)
(TEST_ROOT / "source" / "core" / "__pycache__").mkdir(parents=True, exist_ok=True)
(TEST_ROOT / "temp").mkdir(exist_ok=True)
(TEST_ROOT / "gromacs" / "some_version").mkdir(parents=True, exist_ok=True)

# 创建假配置文件
with open(TEST_ROOT / "config" / "app_config.json", "w") as f:
    f.write('{"theme": "dark"}')

# 创建pyc缓存文件
with open(TEST_ROOT / "source" / "core" / "__pycache__" / "module.cpython-313.pyc", "w") as f:
    f.write("x" * 1000)
with open(TEST_ROOT / "source" / "core" / "__pycache__" / "module2.cpython-313.pyc", "w") as f:
    f.write("x" * 2000)

# 创建.pyc文件
with open(TEST_ROOT / "source" / "core" / "module.pyc", "w") as f:
    f.write("x" * 500)

# 创建日志文件
with open(TEST_ROOT / "temp" / "gromacs_gui.log", "w") as f:
    f.write("x" * 5000)
with open(TEST_ROOT / "temp" / "build.log", "w") as f:
    f.write("x" * 3000)

# 创建spec文件
with open(TEST_ROOT / "temp" / "GROMACS_GUI_v4.2.0.spec", "w") as f:
    f.write("x" * 10000)

# 创建根目录残留文件
with open(TEST_ROOT / "dl.def", "w") as f:
    f.write("x" * 100)

# 模拟清理逻辑（复制自_on_system_cleanup）
cleaned_files = 0
freed_bytes = 0

# 备份配置文件
config_file = TEST_ROOT / "config" / "app_config.json"
if config_file.exists():
    backup_path = TEST_ROOT / "config" / "app_config.json.backup"
    shutil.copy2(str(config_file), str(backup_path))
    print("[TEST] Config backup created")

# 清理 __pycache__ 和 .pyc
for root, dirs, files in os.walk(str(TEST_ROOT)):
    dirs[:] = [d for d in dirs if d.lower() not in ("gromacs", "miniconda3", "dist", "release")]
    for d in list(dirs):
        if d == "__pycache__":
            p = Path(root) / d
            try:
                size = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
                shutil.rmtree(str(p))
                cleaned_files += 1
                freed_bytes += size
                dirs.remove(d)
            except Exception:
                pass
    for f in files:
        if f.endswith(".pyc"):
            fp = Path(root) / f
            try:
                size = fp.stat().st_size
                fp.unlink()
                cleaned_files += 1
                freed_bytes += size
            except Exception:
                pass

# 清理temp日志
temp_dir = TEST_ROOT / "temp"
if temp_dir.exists():
    for log_file in temp_dir.glob("*.log"):
        try:
            size = log_file.stat().st_size
            log_file.unlink()
            cleaned_files += 1
            freed_bytes += size
        except Exception:
            pass

# 清理temp中的spec和旧exe
if temp_dir.exists():
    for pattern in ["*.spec", "*_test.exe"]:
        for f in temp_dir.glob(pattern):
            try:
                size = f.stat().st_size
                f.unlink()
                cleaned_files += 1
                freed_bytes += size
            except Exception:
                pass

# 清理根目录残留
for residual in ["dl.def", "dl.exp", "dl.lib"]:
    rp = TEST_ROOT / residual
    if rp.exists():
        try:
            size = rp.stat().st_size
            rp.unlink()
            cleaned_files += 1
            freed_bytes += size
        except Exception:
            pass

freed_mb = round(freed_bytes / (1024 * 1024), 2)
print(f"[TEST] Cleaned {cleaned_files} items, freed {freed_mb} MB")

# 验证结果
assert not (TEST_ROOT / "source" / "core" / "__pycache__").exists(), "__pycache__ should be deleted"
assert not (TEST_ROOT / "source" / "core" / "module.pyc").exists(), ".pyc should be deleted"
assert not (TEST_ROOT / "temp" / "gromacs_gui.log").exists(), "log should be deleted"
assert not (TEST_ROOT / "temp" / "build.log").exists(), "log should be deleted"
assert not (TEST_ROOT / "temp" / "GROMACS_GUI_v4.2.0.spec").exists(), "spec should be deleted"
assert not (TEST_ROOT / "dl.def").exists(), "residual should be deleted"
assert (TEST_ROOT / "config" / "app_config.json.backup").exists(), "backup should exist"
assert (TEST_ROOT / "config" / "app_config.json").exists(), "config should still exist"
assert (TEST_ROOT / "gromacs" / "some_version").exists(), "gromacs dir should be protected"

print("[PASS] All cleanup assertions passed")

# 清理测试环境
shutil.rmtree(TEST_ROOT)

print("\n=== CLEANUP LOGIC TEST PASSED ===")
