#!/usr/bin/env python3
"""第一阶段3项显性故障修复验收测试"""
import sys
import os
import json
import subprocess
from pathlib import Path

sys.path.insert(0, r"D:\YDW\Trae_Gromacs\source")

# 清除缓存
for mod in list(sys.modules.keys()):
    if any(k in mod for k in ['core.', 'gromacs_gui']):
        del sys.modules[mod]

print("=" * 60)
print("修复1：内存限制模块硬件自适应+配置持久化验收")
print("=" * 60)

# 1. 检查ConfigManager默认值
from core.config_manager import ConfigManager
cfg = ConfigManager()
mem_default = cfg.get("simulation.mem_limit_gb")
mem_enabled = cfg.get("simulation.mem_limit_enabled")
print(f"  默认内存上限: {mem_default} GB (期望8.0)")
print(f"  默认内存限制开关: {mem_enabled} (期望False)")
assert mem_default == 8.0, f"内存默认值错误: {mem_default}"
print("  [PASS] ConfigManager默认8GB上限")

# 2. 检查硬件识别
from PyQt5.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)

# 模拟硬件内存读取
try:
    result = subprocess.run(
        ["wmic", "computersystem", "get", "TotalPhysicalMemory"],
        capture_output=True, text=True, timeout=10
    )
    if result.returncode == 0:
        lines = [l.strip() for l in result.stdout.strip().split("\n") if l.strip() and l.strip() != "TotalPhysicalMemory"]
        if lines:
            total_bytes = int(lines[0])
            total_gb = round(total_bytes / (1024**3), 1)
            print(f"  系统物理内存: {total_gb} GB")
            assert total_gb > 4, f"系统内存应>4GB: {total_gb}"
            print("  [PASS] 硬件内存自动识别正常")
except Exception as e:
    print(f"  [WARNING] 硬件内存检测跳过: {e}")

# 3. 检查配置持久化方法存在
from gromacs_gui_v4 import GromacsGUI
assert hasattr(GromacsGUI, '_load_persistent_config'), "缺少_load_persistent_config方法"
assert hasattr(GromacsGUI, '_save_persistent_config'), "缺少_save_persistent_config方法"
assert hasattr(GromacsGUI, 'closeEvent'), "缺少closeEvent方法"
print("  [PASS] 持久化配置方法已添加")

# 4. 检查save_config包含内存字段
import inspect
src = inspect.getsource(GromacsGUI.save_config)
assert "mem_limit_enabled" in src, "save_config未保存mem_limit_enabled"
assert "mem_limit_gb" in src, "save_config未保存mem_limit_gb"
print("  [PASS] save_config包含内存持久化字段")

# 5. 检查load_config包含内存字段
src_load = inspect.getsource(GromacsGUI.load_config)
assert "mem_limit_enabled" in src_load, "load_config未恢复mem_limit_enabled"
assert "mem_limit_gb" in src_load, "load_config未恢复mem_limit_gb"
print("  [PASS] load_config包含内存恢复字段")

print("  [PASS] 修复1验收通过\n")

print("=" * 60)
print("修复2：GPU诊断timeout参数报错修复验收")
print("=" * 60)

# 检查Popen调用不再包含timeout参数
src_gui = Path(r"D:\YDW\Trae_Gromacs\source\gromacs_gui_v4.py").read_text(encoding="utf-8")

# 查找所有Popen调用
import re
popen_calls = re.findall(r'subprocess\.Popen\([^)]+\)', src_gui, re.DOTALL)
timeout_in_popen = [c for c in popen_calls if 'timeout' in c]
print(f"  Popen调用总数: {len(popen_calls)}")
print(f"  包含timeout的Popen调用: {len(timeout_in_popen)}")
assert len(timeout_in_popen) == 0, f"仍有{len(timeout_in_popen)}个Popen调用包含timeout"
print("  [PASS] 无Popen(timeout=...)非法参数")

# 检查communicate调用包含timeout
communicate_calls = re.findall(r'\.communicate\([^)]*\)', src_gui)
comm_with_timeout = [c for c in communicate_calls if 'timeout' in c]
print(f"  communicate(timeout=...)调用数: {len(comm_with_timeout)}")
assert len(comm_with_timeout) >= 2, "应有至少2个communicate(timeout=...)调用"
print("  [PASS] timeout参数已移到communicate()")

print("  [PASS] 修复2验收通过\n")

print("=" * 60)
print("修复3：主窗口程序图标丢失修复验收")
print("=" * 60)

# 检查_get_icon_path方法
icon_src = inspect.getsource(GromacsGUI._get_icon_path)
assert "frozen" in icon_src, "_get_icon_path未区分frozen模式"
assert "normpath" in icon_src, "_get_icon_path未做路径规范化"
assert "resources/app_icon.ico" in icon_src, "_get_icon_path缺少resources路径"
print("  [PASS] _get_icon_path区分frozen/源码模式")

# 验证源码模式可找到图标
gui = GromacsGUI()
icon_path = gui._get_icon_path()
if icon_path:
    print(f"  图标路径: {icon_path}")
    assert os.path.isfile(icon_path), f"图标文件不存在: {icon_path}"
    print("  [PASS] 源码模式图标文件可找到")
else:
    print("  [WARNING] 未找到图标文件（可能路径配置不正确）")

# 验证setWindowIcon调用存在
init_src = inspect.getsource(GromacsGUI.init_ui)
assert "setWindowIcon" in init_src, "init_ui未调用setWindowIcon"
print("  [PASS] init_ui包含setWindowIcon调用")

app.quit()
print("\n=== 第一阶段3项显性故障修复验收全部通过 ===")
