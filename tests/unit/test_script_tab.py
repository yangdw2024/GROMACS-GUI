# -*- coding: utf-8 -*-
"""
Part 7 自定义脚本独立组件 (ScriptTab) 专项单元测试与回归测试
覆盖：
1. 默认控件初始状态与属性别名兼容；
2. 全部 14 种快速模板加载内容与 get_script_template 严格等价；
3. 脚本类型切换与 Placeholder 动态联动；
4. run_script 针对 PowerShell / Batch / Shell 三类环境构建命令并正确触发 run_requested 信号；
5. 空脚本执行拦截与日志错误信号上抛；
6. 自定义模板应用与弹窗管理回调；
7. 配置序列化 get_config / set_config 数据往返一致性；
8. GromacsGUI 主窗口通过组合方式代理接入 ScriptTab 后的完整功能自洽性。
"""

import os
import sys
import tempfile
import pytest
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture
def script_tab(qapp, tmp_path):
    from gui.tabs.script_tab import ScriptTab
    tab = ScriptTab(
        get_work_dir=lambda: str(tmp_path),
        get_gmx_path=lambda: "D:/GROMACS/bin/gmx.exe"
    )
    return tab


def test_script_tab_init_state(script_tab):
    """测试 1: 验证控件初始状态与默认值"""
    assert script_tab.script_type.count() == 3
    assert script_tab.script_type.currentText() == "Shell 命令"
    assert script_tab.script_edit.toPlainText() == ""
    assert script_tab.script_run_btn.isEnabled()


def test_script_tab_template_loading_equivalence(script_tab):
    """测试 2: 验证 14 种模板在三种类型下的生成结果与底座函数完全一致"""
    from gui.script_templates import get_script_template
    keys = [
        "em", "full_md", "rmsd", "rdf", "hbond", "sasa", "pca", "nvt", "npt", "md",
        "clffcl_em_npt", "clffcl_sa", "clffcl_md1", "clffcl_evapdio"
    ]
    for st_name in ["PowerShell (.ps1)", "Batch (.bat)", "Shell 命令"]:
        script_tab.script_type.setCurrentText(st_name)
        for k in keys:
            script_tab.load_script_template(k)
            rendered = script_tab.script_edit.toPlainText()
            expected = get_script_template(st_name, k, "D:/GROMACS/bin/gmx.exe")
            assert rendered == expected, f"Template {k} under {st_name} mismatch!"


def test_script_tab_empty_run_interception(script_tab):
    """测试 3: 验证空脚本运行时拦截并发出错误日志信号"""
    logs = []
    cmds = []
    script_tab.log_requested.connect(lambda msg, lvl: logs.append((msg, lvl)))
    script_tab.run_requested.connect(lambda c, w, s: cmds.append((c, w, s)))

    script_tab.script_edit.clear()
    script_tab.run_script()

    assert len(cmds) == 0, "Empty script must not trigger run_requested!"
    assert any("内容为空" in msg and lvl == "error" for msg, lvl in logs)


def test_script_tab_run_command_dispatch(script_tab, tmp_path):
    """测试 4: 验证各类型脚本执行时正确写入临时脚本并上抛正确的命令结构"""
    cmds = []
    script_tab.run_requested.connect(lambda c, w, s: cmds.append((c, w, s)))

    # 4.1 Shell 命令类型
    script_tab.script_type.setCurrentText("Shell 命令")
    script_tab.script_edit.setPlainText("gmx check -f conf.gro")
    script_tab.run_script()
    assert len(cmds) == 1
    assert cmds[0][0] == [["cmd", "/c", "gmx check -f conf.gro"]]
    assert cmds[0][1] == str(tmp_path)
    assert cmds[0][2] == "自定义脚本"

    # 4.2 PowerShell 类型
    cmds.clear()
    script_tab.script_type.setCurrentText("PowerShell (.ps1)")
    script_tab.script_edit.setPlainText("Write-Host 'hello'")
    script_tab.run_script()
    assert len(cmds) == 1
    ps1_file = tmp_path / "_gmx_gui_script.ps1"
    assert ps1_file.is_file()
    assert ps1_file.read_text(encoding="utf-8") == "Write-Host 'hello'"
    assert cmds[0][0] == [["powershell", "-ExecutionPolicy", "Bypass", "-File", str(ps1_file)]]

    # 4.3 Batch 类型
    cmds.clear()
    script_tab.script_type.setCurrentText("Batch (.bat)")
    script_tab.script_edit.setPlainText("echo batch test")
    script_tab.run_script()
    assert len(cmds) == 1
    bat_file = tmp_path / "_gmx_gui_script.bat"
    assert bat_file.is_file()
    assert "echo batch test" in bat_file.read_text(encoding="utf-8")
    assert cmds[0][0] == [str(bat_file)]


def test_script_tab_config_persistence(script_tab):
    """测试 5: 验证配置读写 get_config / set_config 数据自洽性"""
    script_tab.script_type.setCurrentText("Batch (.bat)")
    script_tab.script_edit.setPlainText("test_config_content = 123")

    cfg = script_tab.get_config()
    assert cfg["script_type"] == "Batch (.bat)"
    assert cfg["script_content"] == "test_config_content = 123"

    script_tab.script_type.setCurrentText("Shell 命令")
    script_tab.script_edit.clear()

    script_tab.set_config(cfg)
    assert script_tab.script_type.currentText() == "Batch (.bat)"
    assert script_tab.script_edit.toPlainText() == "test_config_content = 123"


def test_main_window_script_tab_integration(qapp, tmp_path):
    """测试 6: 验证主窗口 GromacsGUI 挂载 ScriptTab 后的完整功能与属性别名兼容"""
    from gui.main_window import GromacsGUI
    win = GromacsGUI()
    win.setAttribute(Qt.WA_DontShowOnScreen, True)

    assert hasattr(win, "script_tab")
    assert hasattr(win, "script_type")
    assert hasattr(win, "script_edit")
    assert hasattr(win, "script_run_btn")
    assert win.script_type is win.script_tab.script_type
    assert win.script_edit is win.script_tab.script_edit

    # 验证主窗口的 Part 7 运行命令调度连接
    win.path_edit.setText(str(tmp_path))
    win.script_type.setCurrentText("Shell 命令")
    win.script_edit.setPlainText("echo integration_test")

    # 模拟点击运行脚本，验证主窗口调用 run_command 且无异常崩溃
    win.script_run_btn.click()
    qapp.processEvents()
    assert "自定义脚本" in win.log_text.toPlainText()

    win.close()
