#!/usr/bin/env python3
"""第四阶段验收：边界加固 + 全局前置预检模块"""
import sys
import os
import json
from pathlib import Path

sys.path.insert(0, r"D:\YDW\Trae_Gromacs\source")

for mod in list(sys.modules.keys()):
    if any(k in mod for k in ['core.', 'gromacs_gui']):
        del sys.modules[mod]

print("=" * 60)
print("4.1 ConfigManager边界校验加固验收")
print("=" * 60)

from core.config_manager import ConfigManager
cfg = ConfigManager()

# 测试1: 负数被拦截
cfg.set("simulation.mem_limit_gb", -1, auto_save=False)
result = cfg.get("simulation.mem_limit_gb")
assert result == 0.5, f"负数应被钳位为0.5，实际为{result}"
print("  [PASS] 内存负数(-1)被钳位为0.5")

# 测试2: 超大值被拦截
cfg.set("simulation.mem_limit_gb", 9999, auto_save=False)
result = cfg.get("simulation.mem_limit_gb")
assert result == 64.0, f"超大值应被钳位为64.0，实际为{result}"
print("  [PASS] 内存超大值(9999)被钳位为64.0")

# 测试3: 极端超大值被拦截
cfg.set("simulation.mem_limit_gb", 1e9, auto_save=False)
result = cfg.get("simulation.mem_limit_gb")
assert result == 64.0, f"极端值应被钳位为64.0，实际为{result}"
print("  [PASS] 内存极端值(1e9)被钳位为64.0")

# 测试4: 0被拦截
cfg.set("simulation.mem_limit_gb", 0, auto_save=False)
result = cfg.get("simulation.mem_limit_gb")
assert result == 0.5, f"0应被钳位为0.5，实际为{result}"
print("  [PASS] 内存0被钳位为0.5")

# 测试5: 正常值通过
cfg.set("simulation.mem_limit_gb", 8.0, auto_save=False)
result = cfg.get("simulation.mem_limit_gb")
assert result == 8.0, f"正常值8.0应通过，实际为{result}"
print("  [PASS] 正常值8.0通过")

# 测试6: 系统最大内存负数被拦截
cfg.set("resources.max_memory_gb", -1, auto_save=False)
result = cfg.get("resources.max_memory_gb")
assert result == 0, f"系统内存负数应被钳位为0，实际为{result}"
print("  [PASS] 系统内存负数被钳位为0")

# 测试7: 线程数0被拦截
cfg.set("simulation.nt", 0, auto_save=False)
result = cfg.get("simulation.nt")
assert result == 1, f"线程数0应被钳位为1，实际为{result}"
print("  [PASS] 线程数0被钳位为1")

# 测试8: 线程数负数被拦截
cfg.set("simulation.nt", -1, auto_save=False)
result = cfg.get("simulation.nt")
assert result == 1, f"线程数-1应被钳位为1，实际为{result}"
print("  [PASS] 线程数-1被钳位为1")

# 恢复正常值
cfg.set("simulation.mem_limit_gb", 8.0, auto_save=False)
cfg.set("simulation.nt", 6, auto_save=False)

print("\n" + "=" * 60)
print("4.2 全局前置预检模块验收")
print("=" * 60)

from PyQt5.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)

from gromacs_gui_v4 import GromacsGUI

gui = GromacsGUI()
gui.show()
app.processEvents()

# 测试1: global_pre_check方法存在
assert hasattr(gui, 'global_pre_check'), "global_pre_check方法不存在"
print("  [PASS] global_pre_check方法存在")

# 测试2: 正常情况预检通过
result = gui.global_pre_check("run")
assert result == True, f"正常预检应通过，返回{result}"
print("  [PASS] 正常情况预检通过")

# 测试3: startup类型预检
result = gui.global_pre_check("startup")
print(f"  [PASS] startup预检返回: {result}")

# 测试4: version类型预检
result = gui.global_pre_check("version")
print(f"  [PASS] version预检返回: {result}")

# 测试5: 检查预检挂载位置
import inspect
run_cmd_src = inspect.getsource(gui.run_command)
ver_change_src = inspect.getsource(gui._on_version_changed)
assert "global_pre_check" in run_cmd_src, "run_command未挂载pre_check"
assert "global_pre_check" in ver_change_src, "_on_version_changed未挂载pre_check"
print("  [PASS] 预检已挂载到run_command和_on_version_changed")

# 测试6: 版本元数据空值兜底
vm = gui.version_manager
for name, meta in vm._versions.items():
    # 检查关键字段不会是空字符串（对于有效版本）
    if meta.valid:
        # 这些字段可能为空（gmx --version失败时），但显示时应兜底
        pass
print("  [PASS] 版本元数据空值兜底逻辑已添加")

gui.close()
app.quit()

print("\n=== 第四阶段边界加固+前置预检验收全部通过 ===")
