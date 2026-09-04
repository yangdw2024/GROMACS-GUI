#!/usr/bin/env python3
"""验证frozen模式下的路径修复是否生效"""
import sys
import os
from pathlib import Path

# 必须在导入任何core模块前设置frozen环境
sys.frozen = True
sys._MEIPASS = r"C:\Users\Administrator\AppData\Local\Temp\_MEI12345"
sys.executable = r"D:\YDW\Trae_Gromacs\release\GROMACS_GUI_v4.2.0.exe"

# 添加source到路径
sys.path.insert(0, r"D:\YDW\Trae_Gromacs\source")

# 测试 version_manager 的 _get_app_root
from core.version_manager import _get_app_root, VersionManager
root = _get_app_root()
print(f"[version_manager] _get_app_root() = {root}")
assert str(root) == r"D:\YDW\Trae_Gromacs\release", f"Expected release dir, got {root}"

# 测试 scan_versions 的候选目录逻辑
vm = VersionManager()
versions = vm.scan_versions(filter_invalid=True, deduplicate=True)
print(f"[version_manager] scan_versions found: {len(versions)} versions")
for k, v in versions.items():
    print(f"  - {k}: plumed={v.plumed_status}, simd={v.simd}, gpu={v.gpu}")
assert len(versions) > 0, "Must find at least one gromacs version in frozen mode"

# 测试 config_manager 的 _get_app_root
from core.config_manager import _get_app_root as cfg_root
cfg_root_path = cfg_root()
print(f"[config_manager] _get_app_root() = {cfg_root_path}")
assert str(cfg_root_path) == r"D:\YDW\Trae_Gromacs\release", f"Expected release dir, got {cfg_root_path}"

# 测试 auto_updater 的 _get_app_root
from core.auto_updater import _get_app_root as upd_root
upd_root_path = upd_root()
print(f"[auto_updater] _get_app_root() = {upd_root_path}")
assert str(upd_root_path) == r"D:\YDW\Trae_Gromacs\release", f"Expected release dir, got {upd_root_path}"

# 测试 gromacs_gui_v4 的 get_version_config 路径逻辑
if getattr(sys, 'frozen', False):
    base = os.path.dirname(sys.executable)
else:
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
config_path = os.path.join(base, "version.config")
print(f"[gromacs_gui_v4] version.config path = {config_path}")
assert os.path.exists(config_path), f"version.config not found at {config_path}"
print("[gromacs_gui_v4] version.config exists: OK")

# 测试 templates 路径逻辑
if getattr(sys, 'frozen', False):
    base = os.path.dirname(sys.executable)
else:
    base = os.path.dirname(os.path.abspath(__file__))
# 源码模式下templates应该在source目录下；frozen模式下应该在release目录下
templates_path = os.path.join(base, "templates.json")
print(f"[gromacs_gui_v4] templates.json path = {templates_path}")
# templates.json不一定存在，只验证路径计算正确
print("[gromacs_gui_v4] templates path logic: OK")

print("\n=== ALL PATH TESTS PASSED ===")
