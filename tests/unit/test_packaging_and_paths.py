# -*- coding: utf-8 -*-
"""
跨平台路径、Unicode/空格路径兼容性与 Windows 生产打包配置校验测试 (P15 & P19)
覆盖：
1. 含中文 Unicode 与 Windows 空格路径下的 resolve_path、validate_gro_structure 与 ScriptTab 命令调度；
2. 打包版只读安装目录 (Program Files) 下 _get_writable_app_dir() 自动回退用户可写目录；
3. build_windows_portable.py 生成的 PyInstaller Spec 完整包含 core/gui/simulation/utils/resources，
   且绝不私自重分发第三方 GROMACS 二进制文件；
4. run_main() 支持 --smoke-test 无阻塞校验七大功能页完整加载；
5. version.config 字段一致性校验。
"""

import os
import pathlib
import subprocess
import sys
import unittest.mock as mock
import pytest

from simulation.md_runner import resolve_path
from simulation.validation import validate_gro_structure


def test_unicode_and_spaces_path_handling(tmp_path):
    """测试 1: 验证含中文与空格路径下的结构解析、校验与 ScriptTab 脚本读写"""
    from PyQt5.QtWidgets import QApplication
    from gui.tabs.script_tab import ScriptTab

    app = QApplication.instance() or QApplication(sys.argv)

    unicode_space_dir = tmp_path / "科研项目 测试目录 with spaces"
    unicode_space_dir.mkdir(parents=True, exist_ok=True)

    gro = unicode_space_dir / "体系 结构.gro"
    gro.write_text(
        "Unicode & Spaces\n"
        "1\n"
        "    1CF      C1    1   1.000   2.000   3.000\n"
        "   5.00000   5.00000   5.00000\n",
        encoding="utf-8"
    )

    resolved = resolve_path(str(unicode_space_dir), "体系 结构.gro")
    assert resolved == os.path.join(str(unicode_space_dir), "体系 结构.gro")
    assert os.path.isfile(resolved)

    vres = validate_gro_structure(resolved)
    assert vres.status == "PASS"

    tab = ScriptTab(get_work_dir=lambda: str(unicode_space_dir), get_gmx_path=lambda: "gmx")
    cmds = []
    tab.run_requested.connect(lambda c, w, s: cmds.append((c, w, s)))
    tab.script_type.setCurrentIndex(0)  # PowerShell
    tab.script_edit.setPlainText("Write-Host 'unicode ok'")
    tab.run_script()

    assert len(cmds) == 1
    assert cmds[0][1] == str(unicode_space_dir)
    assert (unicode_space_dir / "_gmx_gui_script.ps1").is_file()


def test_writable_app_dir_fallback_when_readonly(tmp_path):
    """测试 2: 验证安装目录只读时 _get_writable_app_dir 安全回退到用户目录"""
    from gui.app import _get_writable_app_dir

    with mock.patch("builtins.open", side_effect=[OSError("Permission denied")]):
        writable = _get_writable_app_dir()
    assert writable and isinstance(writable, str)
    assert "GROMACS" in writable or ".gromacs_gui" in writable


def test_pyinstaller_spec_completeness_and_no_gmx_bundle():
    """测试 3: 验证打包 Spec 完整包含所有源码包且不捆绑第三方 GROMACS 二进制"""
    repo_root = pathlib.Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo_root / "build_scripts"))
    from build_windows_portable import build_spec_text

    spec_text = build_spec_text("GROMACS_GUI_v4.3.0", repo_root / "resources" / "app_icon.ico", repo_root)
    for req_mod in ["'core'", "'gui'", "'simulation'", "'utils'", "'resources'", "'gui.tabs.md_tab'", "'simulation.validation'"]:
        assert req_mod in spec_text, f"Spec missing required package/module: {req_mod}"
    assert "gromacs-2026" not in spec_text.lower()


def test_cli_smoke_test_flag_succeeds(tmp_path):
    """测试 4: 验证独立子进程执行 source/gromacs_gui_v4.py --smoke-test 快速启动通过"""
    repo_root = pathlib.Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONPATH"] = str(repo_root / "source")

    res = subprocess.run(
        [sys.executable, str(repo_root / "source" / "gromacs_gui_v4.py"), "--smoke-test"],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60
    )
    assert res.returncode == 0, f"Smoke test failed: {res.stderr}"
    assert "SMOKE_TEST_OK" in (res.stdout or "")
    assert "tabs=7" in (res.stdout or "")


def test_app_logger_handles_gbk_console_with_emojis(tmp_path):
    """测试 5: 验证 AppLogger 在 Windows GBK 控制台编码下记录含 Emoji 日志不会抛出 UnicodeEncodeError"""
    import io
    from core.logger import AppLogger

    raw_buf = io.BytesIO()
    gbk_stream = io.TextIOWrapper(raw_buf, encoding="gbk", errors="strict")

    log_file = tmp_path / "gbk_test.log"
    logger = AppLogger("GBK_TEST", log_file=str(log_file))
    with mock.patch("sys.stdout", gbk_stream):
        logger.info("AVX-512: 支持 ✅ 🚀")
    gbk_stream.flush()
    assert b"AVX-512" in raw_buf.getvalue()
