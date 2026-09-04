#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GROMACS GUI v4.3.0 打包脚本
生成 onedir 模式的可执行文件夹，供 Inno Setup 制作安装包
"""

import os
import sys
import shutil
import subprocess
import json
from pathlib import Path


def main():
    script_dir = Path(__file__).parent.parent.resolve()
    source_dir = script_dir / "source"
    dist_dir = script_dir / "dist"
    release_dir = script_dir / "release"
    icon_path = script_dir / "resources" / "app_icon.ico"
    build_log = script_dir / "build.log"

    # 使用项目自带的 miniconda3 Python 环境
    python_exe = script_dir / "miniconda3" / "python.exe"
    if not python_exe.exists():
        print("[ERROR] 未找到 miniconda3 Python 环境")
        return 1

    print("=" * 60)
    print("GROMACS GUI v4.3.0 打包工具 (onedir 模式)")
    print("=" * 60)
    print()

    # 读取版本配置
    version_config_path = script_dir / "version.config"
    version = "4.3.0"
    if version_config_path.exists():
        with open(version_config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            version = data.get("version_string", "4.3.0")

    print(f"版本号: {version}")
    print(f"Python: {python_exe}")
    print(f"源码目录: {source_dir}")
    print(f"输出目录: {dist_dir}")
    print()

    # 步骤1: 前置校验
    print("[1/6] 前置校验...")
    # 检查主程序文件
    main_file = source_dir / "gromacs_gui_v4.py"
    if not main_file.exists():
        print(f"  [ERROR] 主程序文件不存在: {main_file}")
        return 1
    print("  [OK] 主程序文件存在")

    # 检查 PyInstaller
    result = subprocess.run(
        [str(python_exe), "-m", "PyInstaller", "--version"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print("  [ERROR] PyInstaller 未安装")
        return 1
    print(f"  [OK] PyInstaller {result.stdout.strip()}")

    # 检查依赖库
    for pkg in ["PyQt5", "numpy", "psutil", "matplotlib", "scipy"]:
        result = subprocess.run(
            [str(python_exe), "-c", f"import {pkg}; print({pkg}.__version__)"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"  [WARN] {pkg} 未安装或导入失败")
        else:
            print(f"  [OK] {pkg} {result.stdout.strip()}")

    # 步骤2: 清理旧构建文件
    print()
    print("[2/6] 清理旧构建文件...")
    for path in [dist_dir, source_dir / "build", source_dir / "dist",
                 script_dir / "build"]:
        if path.exists():
            shutil.rmtree(path)
    for spec in source_dir.glob("*.spec"):
        spec.unlink()
    dist_dir.mkdir(exist_ok=True)
    print("  [OK] 清理完成")

    # 步骤3: 生成 version_info.json
    print()
    print("[3/6] 生成版本信息文件...")
    with open(version_config_path, "r", encoding="utf-8") as f:
        vc_data = json.load(f)
    version_info_path = source_dir / "version_info.json"
    with open(version_info_path, "w", encoding="utf-8") as f:
        json.dump(vc_data, f, ensure_ascii=False, indent=2)
    print("  [OK] version_info.json 已生成")

    # 步骤4: 执行 PyInstaller 打包
    print()
    print("[4/6] 正在执行 PyInstaller 打包 (需要3-8分钟)...")
    print(f"  日志文件: {build_log}")
    print()

    # 使用版本号但去掉点号作为内部名称
    version_nodot = version.replace(".", "")
    app_name = f"GROMACS_GUI_v{version_nodot}"

    # 构建 spec 文件内容（避免命令行参数解析问题）
    spec_content = f'''# -*- mode: python ; coding: utf-8 -*-
import sys
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

a = Analysis(
    ['gromacs_gui_v4.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('version_info.json', '.'),
        ('core', 'core'),
        ('gui', 'gui'),
        ('config', 'config'),
        ('../resources', 'resources'),
    ],
    hiddenimports=[
        'PyQt5.QtCore', 'PyQt5.QtGui', 'PyQt5.QtWidgets', 'PyQt5.sip',
        'numpy', 'psutil', 'matplotlib', 'matplotlib.pyplot',
        'matplotlib.backends.backend_qt5agg', 'scipy',
        'cpuinfo', 'ctypes', 'platform',
    ] + collect_submodules('PyQt5') + collect_submodules('matplotlib'),
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='{app_name}',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=r'{icon_path}',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='{app_name}',
)
'''
    spec_file = source_dir / "gromacs_gui_v4.spec"
    with open(spec_file, "w", encoding="utf-8") as f:
        f.write(spec_content)
    print(f"  [OK] spec 文件已生成: {spec_file.name}")

    # 构建 PyInstaller 命令 (使用 spec 文件)
    cmd_parts = [
        str(python_exe), "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--log-level=WARN",
        str(spec_file),
    ]

    cmd_str = " ".join(cmd_parts)
    print(f"  执行命令: {cmd_str}")
    print()

    with open(build_log, "w", encoding="utf-8") as log_f:
        log_f.write(f"Command: {cmd_str}\n")
        log_f.write("=" * 60 + "\n")
        process = subprocess.Popen(
            cmd_parts,
            cwd=str(source_dir),
            stdout=log_f,
            stderr=subprocess.STDOUT,
        )
        process.wait()

        if process.returncode != 0:
            print(f"  [ERROR] 打包失败，返回码: {process.returncode}")
            print(f"  详细日志: {build_log}")
            return 1

    print("  [OK] PyInstaller 打包完成")

    # 步骤5: 整理打包产物
    print()
    print("[5/6] 整理打包产物...")

    # onedir 模式输出在 source/dist/GROMACS_GUI_v430/
    onedir_output = source_dir / "dist" / app_name
    if not onedir_output.exists():
        print(f"  [ERROR] 未找到打包输出目录: {onedir_output}")
        return 1

    # 移动到 dist 目录，重命名为带版本号格式
    final_dist = dist_dir / f"GROMACS_GUI_v{version}"
    if final_dist.exists():
        shutil.rmtree(final_dist)
    shutil.move(str(onedir_output), str(final_dist))
    # 重命名 exe 文件
    old_exe = final_dist / f"{app_name}.exe"
    new_exe = final_dist / f"GROMACS_GUI_v{version}.exe"
    if old_exe.exists():
        old_exe.rename(new_exe)
    print(f"  [OK] 可执行文件目录: {final_dist}")

    # 复制资源文件
    resources_src = script_dir / "resources"
    if resources_src.exists():
        shutil.copytree(
            resources_src, final_dist / "resources",
            dirs_exist_ok=True
        )
        print("  [OK] 资源文件已复制")

    # 复制配置文件
    config_src = script_dir / "source" / "config"
    if config_src.exists():
        shutil.copytree(
            config_src, final_dist / "config",
            dirs_exist_ok=True
        )
        print("  [OK] 配置文件已复制")

    # 复制 version.config
    shutil.copy2(version_config_path, final_dist / "version.config")
    print("  [OK] version.config 已复制")

    # 复制说明书
    manual = script_dir / "说明书.md"
    if manual.exists():
        shutil.copy2(manual, final_dist / "说明书.md")
        print("  [OK] 说明书已复制")

    # 复制 GROMACS 默认版本
    print()
    print("  复制 GROMACS 默认版本 (gromacs-2026.3-AVX512-CUDA-sm120-final2)...")
    gromacs_src = script_dir / "gromacs" / "gromacs-2026.3-AVX512-CUDA-sm120-final2"
    gromacs_dst = final_dist / "gromacs" / "gromacs-2026.3-AVX512-CUDA-sm120-final2"
    if gromacs_src.exists() and (gromacs_src / "bin" / "gmx.exe").exists():
        shutil.copytree(gromacs_src, gromacs_dst, dirs_exist_ok=True)
        print(f"  [OK] GROMACS 已复制到: {gromacs_dst}")
    else:
        print(f"  [WARN] GROMACS 源目录不存在或无效: {gromacs_src}")

    # 创建启动脚本
    bat_content = f'''@echo off
chcp 65001 >nul
set "APP_DIR=%~dp0"
set "PATH=%APP_DIR%gromacs\\gromacs-2026.3-AVX512-CUDA-sm120-final2\\bin;%PATH%"

tasklist /FI "IMAGENAME eq GROMACS_GUI_v{version}.exe" 2>NUL | find /I /N "GROMACS_GUI_v{version}.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo GROMACS GUI 已经在运行中，请先关闭已有的实例！
    pause
    exit /b
)

start "" "%APP_DIR%GROMACS_GUI_v{version}.exe" %*
'''
    bat_path = final_dist / "启动GROMACS_GUI_v4.bat"
    with open(bat_path, "w", encoding="utf-8") as f:
        f.write(bat_content)
    print(f"  [OK] 启动脚本已创建: {bat_path.name}")

    # 步骤6: 清理临时文件
    print()
    print("[6/6] 清理临时文件...")
    for path in [source_dir / "build", source_dir / "dist", script_dir / "build"]:
        if path.exists():
            shutil.rmtree(path)
    for spec in source_dir.glob("*.spec"):
        spec.unlink()
    print("  [OK] 清理完成")

    # 输出结果
    print()
    print("=" * 60)
    print("打包完成！")
    print("=" * 60)
    print()
    print(f"输出目录: {final_dist}")
    print()
    print("目录结构:")
    for item in sorted(final_dist.iterdir()):
        if item.is_dir():
            size = sum(f.stat().st_size for f in item.rglob('*') if f.is_file())
            print(f"  [DIR]  {item.name:40s} ({size / 1024 / 1024:.1f} MB)")
        else:
            size = item.stat().st_size
            print(f"  [FILE] {item.name:40s} ({size / 1024 / 1024:.1f} MB)")

    # 总大小
    total_size = sum(f.stat().st_size for f in final_dist.rglob('*') if f.is_file())
    print()
    print(f"总大小: {total_size / 1024 / 1024 / 1024:.2f} GB")
    print()
    print("下一步: 使用 Inno Setup 7 生成 exe 安装程序")
    return 0


if __name__ == "__main__":
    sys.exit(main())
