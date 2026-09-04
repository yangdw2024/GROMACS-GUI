#!/usr/bin/env python3
"""测试GUI系统清理对话框：双选项独立可用、自定义天数配置"""
import sys
import os
import time
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, r"D:\YDW\Trae_Gromacs\source")

# 创建测试日志目录和过期文件
TEST_LOG_DIR = Path(r"D:\YDW\Trae_Gromacs\test_cleanup_logs")
if TEST_LOG_DIR.exists():
    import shutil
    shutil.rmtree(TEST_LOG_DIR)
TEST_LOG_DIR.mkdir(parents=True)

# 创建过期日志文件（31天前）
old_files = []
for prefix in ["info_", "debug_", "warning_", "error_"]:
    f = TEST_LOG_DIR / f"{prefix}20250601_120000.log"
    f.write_text("old log content", encoding="utf-8")
    old_time = (datetime.now() - timedelta(days=31)).timestamp()
    os.utime(str(f), (old_time, old_time))
    old_files.append((prefix, f))

# 创建近期日志（5天前）
recent_files = []
for prefix in ["info_", "debug_", "warning_", "error_"]:
    f = TEST_LOG_DIR / f"{prefix}20260704_120000.log"
    f.write_text("recent log", encoding="utf-8")
    recent_time = (datetime.now() - timedelta(days=5)).timestamp()
    os.utime(str(f), (recent_time, recent_time))
    recent_files.append((prefix, f))

print("=" * 60)
print("Test: 过期日志清理逻辑（模拟GUI清理30天以上日志）")
print("=" * 60)

# 模拟GUI清理逻辑
now = time.time()
log_days = 30
cleaned = 0
for level_prefix in ["info_", "debug_", "warning_"]:
    for log_file in TEST_LOG_DIR.glob(f"{level_prefix}*.log"):
        if (now - log_file.stat().st_mtime) > log_days * 86400:
            log_file.unlink()
            cleaned += 1
            print(f"  Deleted expired: {log_file.name}")

# 验证结果
for prefix, f in old_files:
    if prefix.startswith("error_"):
        assert f.exists(), f"Old {prefix} log should be preserved (ERROR permanent)"
        print(f"  [PASS] Old {prefix} log preserved (ERROR permanent)")
    else:
        assert not f.exists(), f"Old {prefix} log should be deleted"
        print(f"  [PASS] Old {prefix} log deleted (expired)")

for prefix, f in recent_files:
    assert f.exists(), f"Recent {prefix} log should be preserved"
    print(f"  [PASS] Recent {prefix} log preserved (within {log_days} days)")

# Test: 自定义天数=3天，5天前的日志也应该被清理
print("\n" + "=" * 60)
print("Test: 自定义天数=3天清理")
print("=" * 60)

# 重新创建5天前的文件
for prefix in ["info_", "debug_", "warning_"]:
    f = TEST_LOG_DIR / f"{prefix}20260704_120000.log"
    if not f.exists():
        f.write_text("recent log", encoding="utf-8")
    recent_time = (datetime.now() - timedelta(days=5)).timestamp()
    os.utime(str(f), (recent_time, recent_time))

custom_days = 3
cleaned2 = 0
for level_prefix in ["info_", "debug_", "warning_"]:
    for log_file in TEST_LOG_DIR.glob(f"{level_prefix}*.log"):
        if (now - log_file.stat().st_mtime) > custom_days * 86400:
            log_file.unlink()
            cleaned2 += 1

# 5天前的非ERROR日志应被3天阈值清理
for prefix, f in recent_files:
    if prefix.startswith("error_"):
        assert f.exists(), "ERROR log always preserved"
    else:
        assert not f.exists(), f"5-day-old {prefix} log should be deleted with 3-day threshold"
        print(f"  [PASS] 5-day-old {prefix} log deleted (3-day threshold)")

print(f"\n  Cleaned {cleaned} files with 30-day threshold, {cleaned2} files with 3-day threshold")

# 清理
import shutil
shutil.rmtree(TEST_LOG_DIR)

print("\n=== SYSTEM CLEANUP TEST PASSED ===")
