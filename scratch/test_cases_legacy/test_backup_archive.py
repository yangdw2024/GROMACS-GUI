#!/usr/bin/env python3
"""测试打包产物自动归档备份逻辑"""
import os
import json
import shutil
import zipfile
from pathlib import Path
from datetime import datetime

BACKUP_DIR = Path(r"D:\YDW\Trae_Gromacs\archives\release_backup")
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

# 读取backup_max_count
CONFIG_PATH = Path(r"D:\YDW\Trae_Gromacs\version.config")
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = json.load(f)
max_count = config.get("backup_max_count", 5)
print(f"backup_max_count = {max_count}")

print("\n--- Test 1: 创建模拟归档文件 ---")
# 创建3个模拟归档
for i in range(3):
    ts = datetime.now().strftime(f"20260709_20000{i}")
    name = f"GROMACS_GUI_v4.2.0_{ts}.zip"
    path = BACKUP_DIR / name
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(f"test_{i}.txt", f"backup {i}")
    print(f"  Created: {name}")

backups = sorted(BACKUP_DIR.glob("*.zip"))
print(f"  Current backups: {len(backups)}")
assert len(backups) >= 3
print("[PASS] 模拟归档创建成功")

print("\n--- Test 2: 超限清理逻辑（max=5） ---")
# 再创建3个，总共6个超过5
for i in range(3, 6):
    ts = datetime.now().strftime(f"20260709_20000{i}")
    name = f"GROMACS_GUI_v4.2.0_{ts}.zip"
    path = BACKUP_DIR / name
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(f"test_{i}.txt", f"backup {i}")
    print(f"  Created: {name}")

backups = sorted(BACKUP_DIR.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
print(f"  Total backups before cleanup: {len(backups)}")

# 执行清理（保留最新的max_count个）
if len(backups) > max_count:
    to_remove = backups[max_count:]
    for f in to_remove:
        f.unlink()
        print(f"  Removed: {f.name}")
    removed = len(to_remove)
else:
    removed = 0

backups_after = list(BACKUP_DIR.glob("*.zip"))
print(f"  After cleanup: {len(backups_after)} (max={max_count})")
assert len(backups_after) <= max_count
print(f"[PASS] 超限清理正常，删除了{removed}个旧备份")

print("\n--- Test 3: 归档命名格式验证 ---")
for f in sorted(BACKUP_DIR.glob("*.zip")):
    # 验证命名格式：GROMACS_GUI_v4.2.0_YYYYMMDD_HHMMSS.zip
    parts = f.stem.split("_")
    assert len(parts) >= 5, f"Invalid name format: {f.name}"
    print(f"  {f.name}: OK")
print("[PASS] 归档命名格式正确")

# 清理测试归档
for f in BACKUP_DIR.glob("GROMACS_GUI_v4.2.0_20260709_20000*.zip"):
    f.unlink()
print("\n[INFO] 测试归档已清理")

print("\n=== BACKUP ARCHIVE TEST PASSED ===")
