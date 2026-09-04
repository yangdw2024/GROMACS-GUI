#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GROMACS GUI 打包脚本
替代.bat批处理，彻底解决中文编码问题
"""

import os
import sys
import shutil
import subprocess
import json
from pathlib import Path


def log(msg, level="INFO"):
    print(f"[{level}] {msg}")


def run_cmd(cmd, cwd=None, capture=True):
    """执行命令并返回结果"""
    log(f"执行: {cmd}")
    try:
        if capture:
            result = subprocess.run(
                cmd, shell=True, cwd=cwd,
                capture_output=True, text=True, encoding="utf-8"
            )
        else:
            result = subprocess.run(cmd, shell=True, cwd=cwd)
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)


def main():
    script_dir = Path(__file__).parent.resolve()
    source_dir = script_dir / "source"
    dist_dir = script_dir / "dist"
    icon_path = script_dir / "resources" / "app_icon.ico"
    build_log = script_dir / "build.log"

    print("=" * 50)
    print("GROMACS GUI v4.2 打包工具")
    print("=" * 50)
    print()

    # 读取版本配置
    version_config = script_dir / "version.config"
    version = "4.2.0"
    if version_config.exists():
        try:
            with open(version_config, "r", encoding="utf-8") as f:
                data = json.load(f)
                version = data.get("version_string", "4.2.0")
        except Exception:
            pass

    log(f"版本号: {version}")

    # 步骤1: 前置校验
    print()
    log("[1/5] 执行前置校验...")

    # 检查Python
    ok, out, err = run_cmd("python --version")
    if not ok:
        log("Python未安装或未添加到PATH", "ERROR")
        input("按回车键退出...")
        return 1
    log(f"  [OK] Python: {out.strip()}")

    # 检查PyInstaller
    ok, out, err = run_cmd("pyinstaller --version")
    if not ok:
        log("PyInstaller未安装，请先执行: pip install pyinstaller", "ERROR")
        input("按回车键退出...")
        return 1
    log(f"  [OK] PyInstaller: {out.strip()}")

    # 检查主程序文件
    main_file = source_dir / "gromacs_gui_v4.py"
    if not main_file.exists():
        log(f"主程序文件不存在: {main_file}", "ERROR")
        input("按回车键退出...")
        return 1
    log("  [OK] 主程序文件存在")

    # 步骤2: 清理旧文件
    print()
    log("[2/5] 清理旧构建文件...")
    for path in [dist_dir, script_dir / "build", source_dir / "build",
                 source_dir / "dist"]:
        if path.exists():
            shutil.rmtree(path)
    for spec in source_dir.glob("*.spec"):
        spec.unlink()
    dist_dir.mkdir(exist_ok=True)
    log("  [OK] 清理完成")

    # 步骤3: 编译打包
    print()
    log("[3/5] 正在编译打包（需要2-5分钟）...")
    log(f"  输出目录: {dist_dir}")
    log(f"  日志文件: {build_log}")
    print()

    cmd_parts = [
        "pyinstaller", "--noconfirm", "--onefile", "--windowed",
        f'--name GROMACS_GUI_v{version.replace(".", "")}',
    ]
    if icon_path.exists():
        cmd_parts.append(f'--icon "{icon_path}"')
    cmd_parts.extend([
        "--hidden-import=PyQt5.QtCore",
        "--hidden-import=PyQt5.QtGui",
        "--hidden-import=PyQt5.QtWidgets",
        "--hidden-import=PyQt5.sip",
        "--hidden-import=numpy",
        "--hidden-import=psutil",
        "--clean",
        "--log-level WARN",
        "gromacs_gui_v4.py"
    ])

    cmd = " ".join(cmd_parts)

    # 执行打包，重定向日志
    with open(build_log, "w", encoding="utf-8") as log_f:
        log_f.write(f"Command: {cmd}\n")
        log_f.write("=" * 50 + "\n")
        try:
            process = subprocess.Popen(
                cmd, shell=True, cwd=str(source_dir),
                stdout=log_f, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8"
            )
            process.wait()
            if process.returncode != 0:
                log(f"打包失败，返回码: {process.returncode}", "ERROR")
                log(f"详细日志: {build_log}", "ERROR")
                input("按回车键退出...")
                return 1
        except Exception as e:
            log(f"打包异常: {e}", "ERROR")
            input("按回车键退出...")
            return 1

    # 步骤4: 整理产物
    print()
    log("[4/5] 整理打包产物...")

    src_exe = source_dir / "dist" / f"GROMACS_GUI_v{version.replace('.', '')}.exe"
    dst_exe = dist_dir / f"GROMACS_GUI_v{version}.exe"

    if not src_exe.exists():
        log(f"未找到打包输出的exe文件: {src_exe}", "ERROR")
        input("按回车键退出...")
        return 1

    shutil.move(str(src_exe), str(dst_exe))
    log(f"  [OK] 可执行文件: {dst_exe.name}")

    # 复制资源文件
    if (script_dir / "resources").exists():
        shutil.copytree(
            script_dir / "resources",
            dist_dir / "resources",
            dirs_exist_ok=True
        )
        log("  [OK] 资源文件已复制")

    if (script_dir / "config").exists():
        shutil.copytree(
            script_dir / "config",
            dist_dir / "config",
            dirs_exist_ok=True
        )
        log("  [OK] 配置文件已复制")

    # 复制GROMACS版本
    gromacs_src = script_dir / "gromacs"
    if gromacs_src.exists():
        gromacs_dst = dist_dir / "gromacs"
        gromacs_dst.mkdir(exist_ok=True)
        for item in gromacs_src.iterdir():
            if item.is_dir() and not item.name.startswith("build-"):
                if (item / "bin" / "gmx.exe").exists():
                    shutil.copytree(
                        item, gromacs_dst / item.name,
                        dirs_exist_ok=True
                    )
        log("  [OK] GROMACS版本已复制")

    # 创建启动脚本
    bat_content = f'''@echo off
chcp 65001 >nul
set "APP_DIR=%~dp0"
set "PATH=%APP_DIR%gromacs\gromacs-2026.3-AVX512-CUDA-sm120-fixed\bin;%PATH%"
start "" "%APP_DIR%GROMACS_GUI_v{version}.exe" %*
'''
    with open(dist_dir / "启动程序.bat", "w", encoding="utf-8") as f:
        f.write(bat_content)
    log("  [OK] 启动脚本已创建")

    # 步骤5: 清理临时文件
    print()
    log("[5/5] 清理临时文件...")
    for path in [source_dir / "build", source_dir / "dist", script_dir / "build"]:
        if path.exists():
            shutil.rmtree(path)
    for spec in source_dir.glob("*.spec"):
        spec.unlink()
    log("  [OK] 清理完成")

    # 创建压缩包
    zip_path = script_dir / f"GROMACS_GUI_v{version}_Release.zip"
    log("  创建发布压缩包...")
    try:
        shutil.make_archive(
            str(script_dir / f"GROMACS_GUI_v{version}_Release"),
            'zip', str(dist_dir)
        )
        log(f"  [OK] 压缩包: {zip_path.name}")
    except Exception as e:
        log(f"压缩包创建失败: {e}", "WARNING")

    # 输出结果
    print()
    print("=" * 50)
    print("打包完成！")
    print("=" * 50)
    print()
    print("输出文件:")
    print(f"  - {dst_exe}")
    print(f"  - {zip_path}")
    print(f"  - {build_log}")
    print()
    input("按回车键退出...")
    return 0


if __name__ == "__main__":
    sys.exit(main())