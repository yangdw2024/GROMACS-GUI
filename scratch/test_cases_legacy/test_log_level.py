#!/usr/bin/env python3
"""测试日志分级存储与清理功能"""
import sys
import os
import time
import shutil
from pathlib import Path
from datetime import datetime, timedelta

# 重置单例以使用测试目录
TEST_LOG_DIR = Path(r"D:\YDW\Trae_Gromacs\test_log_level")
if TEST_LOG_DIR.exists():
    shutil.rmtree(TEST_LOG_DIR)
TEST_LOG_DIR.mkdir(parents=True)

sys.path.insert(0, r"D:\YDW\Trae_Gromacs\source")

# 清除可能的单例缓存
if 'core.logger' in sys.modules:
    del sys.modules['core.logger']
from core.logger import AppLogger, LogLevel

# 使用测试目录创建logger
logger = AppLogger(name="test", log_dir=str(TEST_LOG_DIR))

print("=" * 60)
print("Test 1: 分级日志文件创建")
print("=" * 60)
logger.info("This is an info message")
logger.debug("This is a debug message")
logger.warning("This is a warning message")
logger.error("This is an error message")

# 刷新
time.sleep(0.5)

log_files = list(TEST_LOG_DIR.glob("*.log"))
print(f"  Created log files: {[f.name for f in log_files]}")
level_files = [f.name for f in log_files if any(f.name.startswith(p) for p in ["info_", "debug_", "warning_", "error_"])]
print(f"  Level-specific files: {level_files}")
assert len(level_files) >= 3, f"Expected at least 3 level files, got {level_files}"

# 检查error日志内容
error_log = [f for f in log_files if f.name.startswith("error_")]
if error_log:
    content = error_log[0].read_text(encoding="utf-8")
    assert "error message" in content, f"Error message not in error log: {content[-200:]}"
    assert "info message" not in content, "Info should not be in error log"
    print("[PASS] error log contains only error messages")

info_log = [f for f in log_files if f.name.startswith("info_")]
if info_log:
    content = info_log[0].read_text(encoding="utf-8")
    assert "info message" in content, "Info message should be in info log"
    print("[PASS] info log contains info messages")
print("[PASS] 分级日志文件创建成功")

print("\n" + "=" * 60)
print("Test 2: 过期日志清理（ERROR永久保留）")
print("=" * 60)

# 创建一个过期的旧日志文件（31天前修改）
old_info = TEST_LOG_DIR / "info_20250601_120000.log"
old_debug = TEST_LOG_DIR / "debug_20250601_120000.log"
old_warning = TEST_LOG_DIR / "warning_20250601_120000.log"
old_error = TEST_LOG_DIR / "error_20250601_120000.log"

for f in [old_info, old_debug, old_warning, old_error]:
    f.write_text("old log content", encoding="utf-8")
    # 修改mtime为31天前
    old_time = (datetime.now() - timedelta(days=31)).timestamp()
    os.utime(str(f), (old_time, old_time))

print(f"  Created old log files with mtime 31 days ago")

# 执行30天过期清理
logger._cleanup_expired_level_logs(days=30)

# 验证：INFO/DEBUG/WARNING过期被删除，ERROR保留
assert not old_info.exists(), "Old info log should be deleted"
assert not old_debug.exists(), "Old debug log should be deleted"
assert not old_warning.exists(), "Old warning log should be deleted"
assert old_error.exists(), "Old error log should be preserved (permanent)"
print("[PASS] 过期INFO/DEBUG/WARNING已删除，ERROR永久保留")

print("\n" + "=" * 60)
print("Test 3: 近期日志不受清理影响")
print("=" * 60)
# 创建5天前的日志
recent_info = TEST_LOG_DIR / "info_20260704_120000.log"
recent_info.write_text("recent log", encoding="utf-8")
recent_time = (datetime.now() - timedelta(days=5)).timestamp()
os.utime(str(recent_info), (recent_time, recent_time))

logger._cleanup_expired_level_logs(days=30)
assert recent_info.exists(), "Recent info log should be preserved"
print("[PASS] 5天内的日志不受30天清理影响")

# 关闭logger
logger.close()

# 清理
shutil.rmtree(TEST_LOG_DIR)

print("\n=== LOG LEVEL TEST PASSED ===")
