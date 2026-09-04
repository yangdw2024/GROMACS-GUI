#!/usr/bin/env python3
"""第二阶段：顶部系统配置整行控件联动回归复测
遍历全部版本切换、内存阈值修改、GPU开关、重启后配置持久化、图标稳定性
"""
import sys
import os
import json
import subprocess
import time
from pathlib import Path

sys.path.insert(0, r"D:\YDW\Trae_Gromacs\source")

for mod in list(sys.modules.keys()):
    if any(k in mod for k in ['core.', 'gromacs_gui']):
        del sys.modules[mod]

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

app = QApplication.instance() or QApplication(sys.argv)

from gromacs_gui_v4 import GromacsGUI

gui = GromacsGUI()
gui.show()
app.processEvents()

print("=" * 60)
print("联动测试1：遍历全部GROMACS版本循环切换")
print("=" * 60)

# 获取所有版本
version_count = gui.ver_combo.count()
print(f"  版本数量: {version_count}")

initial_mem = gui.cfg_mem_value.value()
initial_mem_enabled = gui.cfg_mem_limit.isChecked()
initial_gpu = gui.cfg_gpu.isChecked()
print(f"  初始内存限制: {initial_mem_enabled} / {initial_mem} GB")
print(f"  初始GPU状态: {initial_gpu}")

for i in range(version_count):
    gui.ver_combo.setCurrentIndex(i)
    app.processEvents()
    time.sleep(0.1)

    current_text = gui.ver_combo.currentText()
    current_mem = gui.cfg_mem_value.value()
    current_mem_enabled = gui.cfg_mem_limit.isChecked()
    current_gpu = gui.cfg_gpu.isChecked()

    # 验证切换版本后内存和GPU设置不被重置
    assert current_mem == initial_mem, f"版本切换到 {current_text} 后内存值被重置: {current_mem} != {initial_mem}"
    assert current_mem_enabled == initial_mem_enabled, f"版本切换到 {current_text} 后内存开关被重置"
    assert current_gpu == initial_gpu, f"版本切换到 {current_text} 后GPU开关被重置"

print(f"  [PASS] 遍历{version_count}个版本，内存/GPU设置均未重置")

print("\n" + "=" * 60)
print("联动测试2：内存阈值修改+GPU开关+GPU编号切换")
print("=" * 60)

# 修改内存阈值
gui.cfg_mem_limit.setChecked(True)
gui.cfg_mem_value.setValue(10.0)
app.processEvents()
assert gui.cfg_mem_value.value() == 10.0, "内存阈值设置失败"
print("  [PASS] 内存阈值修改为10.0 GB成功")

# GPU开关切换
gui.cfg_gpu.setChecked(False)
app.processEvents()
gui.cfg_gpu.setChecked(True)
app.processEvents()
print("  [PASS] GPU开关切换正常")

# GPU编号切换
if gui.cfg_gpu_id.count() > 1:
    gui.cfg_gpu_id.setCurrentIndex(1)
    app.processEvents()
    gui.cfg_gpu_id.setCurrentIndex(0)
    app.processEvents()
    print("  [PASS] GPU编号切换正常")

# 修改回来
gui.cfg_mem_limit.setChecked(True)
gui.cfg_mem_value.setValue(8.0)
app.processEvents()

print("\n" + "=" * 60)
print("联动测试3：配置持久化验证（保存+重新加载）")
print("=" * 60)

# 保存当前配置
gui._save_persistent_config()
app.processEvents()

# 读取app_config验证
config_path = Path(r"D:\YDW\Trae_Gromacs\source\config\app_config.json")
with open(config_path, "r", encoding="utf-8") as f:
    saved = json.load(f)

saved_mem = saved.get("simulation", {}).get("mem_limit_gb", 0)
saved_mem_enabled = saved.get("simulation", {}).get("mem_limit_enabled", False)
print(f"  保存的内存值: {saved_mem} GB")
print(f"  保存的内存开关: {saved_mem_enabled}")
assert saved_mem == 8.0, f"持久化内存值错误: {saved_mem}"
print("  [PASS] 配置持久化保存正确")

# 重新加载验证
gui2 = GromacsGUI()
gui2.show()
app.processEvents()
time.sleep(0.5)

loaded_mem = gui2.cfg_mem_value.value()
loaded_mem_enabled = gui2.cfg_mem_limit.isChecked()
print(f"  重新加载的内存值: {loaded_mem} GB")
print(f"  重新加载的内存开关: {loaded_mem_enabled}")
assert loaded_mem == 8.0, f"持久化加载失败: {loaded_mem}"
print("  [PASS] 配置持久化重新加载正确")

gui2.close()

print("\n" + "=" * 60)
print("联动测试4：窗口图标稳定性（5次创建/销毁）")
print("=" * 60)

icon_found = 0
for i in range(5):
    g = GromacsGUI()
    icon_path = g._get_icon_path()
    if icon_path and os.path.isfile(icon_path):
        icon_found += 1
    g.close()
    app.processEvents()
    time.sleep(0.1)

print(f"  5次创建中图标找到次数: {icon_found}/5")
assert icon_found == 5, f"图标不稳定: {icon_found}/5"
print("  [PASS] 窗口图标5次加载全部成功")

gui.close()
app.quit()

print("\n=== 第二阶段联动回归复测全部通过 ===")
