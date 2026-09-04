#!/usr/bin/env python3
"""在真实环境上执行一键清理，计算释放空间"""
import sys
import os
import shutil
from pathlib import Path

sys.path.insert(0, r"D:\YDW\Trae_Gromacs\source")

from gromacs_gui_v4 import _get_app_root

app_root = _get_app_root()
print(f"App root: {app_root}")

cleaned_files = 0
freed_bytes = 0

# 1. 备份配置文件
try:
    config_file = app_root / "config" / "app_config.json"
    if config_file.exists():
        backup_path = app_root / "config" / "app_config.json.backup"
        shutil.copy2(str(config_file), str(backup_path))
        print("[INFO] Config backup created")
except Exception as e:
    print(f"[WARN] Config backup failed: {e}")

# 2. 清理 __pycache__ 和 .pyc
for root, dirs, files in os.walk(str(app_root)):
    dirs[:] = [d for d in dirs if d.lower() not in ("gromacs", "miniconda3", "dist", "release")]
    for d in list(dirs):
        if d == "__pycache__":
            p = Path(root) / d
            try:
                size = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
                shutil.rmtree(str(p))
                cleaned_files += 1
                freed_bytes += size
                print(f"[DEL] __pycache__: {p} ({round(size/1024/1024,2)} MB)")
                dirs.remove(d)
            except Exception as e:
                print(f"[ERR] Failed to delete {p}: {e}")
    for f in files:
        if f.endswith(".pyc"):
            fp = Path(root) / f
            try:
                size = fp.stat().st_size
                fp.unlink()
                cleaned_files += 1
                freed_bytes += size
                print(f"[DEL] .pyc: {fp}")
            except Exception:
                pass

# 3. 清理temp日志
temp_dir = app_root / "temp"
if temp_dir.exists():
    for log_file in temp_dir.glob("*.log"):
        try:
            size = log_file.stat().st_size
            log_file.unlink()
            cleaned_files += 1
            freed_bytes += size
            print(f"[DEL] log: {log_file} ({round(size/1024/1024,2)} MB)")
        except Exception:
            pass

# 4. 清理temp中的spec和旧exe
if temp_dir.exists():
    for pattern in ["*.spec", "*_test.exe"]:
        for f in temp_dir.glob(pattern):
            try:
                size = f.stat().st_size
                f.unlink()
                cleaned_files += 1
                freed_bytes += size
                print(f"[DEL] temp build: {f} ({round(size/1024/1024,2)} MB)")
            except Exception:
                pass

# 5. 清理根目录残留
for residual in ["dl.def", "dl.exp", "dl.lib"]:
    rp = app_root / residual
    if rp.exists():
        try:
            size = rp.stat().st_size
            rp.unlink()
            cleaned_files += 1
            freed_bytes += size
            print(f"[DEL] residual: {rp}")
        except Exception:
            pass

freed_mb = round(freed_bytes / (1024 * 1024), 2)
print(f"\n=== CLEANUP RESULT ===")
print(f"Cleaned items: {cleaned_files}")
print(f"Freed space: {freed_mb} MB")
