#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
程序启动引导：使用协议、崩溃处理、单实例锁、主循环
"""

from datetime import datetime
import json
import os
import platform
import sys

from gui.app_context import VERSION_CONFIG


from PyQt5.QtWidgets import (
    QApplication, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, QMessageBox,
    QDialog
)


from PyQt5.QtCore import Qt, QTimer


from PyQt5.QtGui import QColor, QPalette


from gui.main_window import GromacsGUI


def _get_config_path():
    """获取配置文件路径"""
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, 'gromacs_gui_config.json')


def _check_license_agreement():
    """检查用户是否已同意使用协议，未同意则弹出协议窗口"""
    config_path = _get_config_path()
    # 读取配置
    config = {}
    if os.path.isfile(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except Exception:
            config = {}
    if config.get("license_accepted", False):
        return True
    # 弹出协议窗口
    license_text = f"""GROMACS GUI {VERSION_CONFIG['version_string']} 使用协议

版权所有 © 2026 YangDewu (阳德武)

1. 软件用途
   本软件为GROMACS分子动力学模拟的图形化界面工具，旨在简化
   GROMACS命令行操作，提供可视化的模拟流程管理。

2. 免责声明
   本软件按"现状"提供，不提供任何明示或暗示的担保。作者不对
   因使用本软件而产生的任何直接或间接损失承担责任。用户应自行
   验证模拟结果的正确性。

3. 知识产权
   本软件的GUI界面代码版权归YangDewu所有。
   GROMACS本身遵循GNU Lesser General Public License (LGPL)开源协议。
   本软件不修改GROMACS源代码，仅作为其图形化界面工具。

4. 禁止行为
   禁止未经授权将本软件用于商业销售或付费服务。

5. 协议变更
   作者保留随时修改本协议的权利，修改后的协议自发布之日起生效。

点击"我同意"表示您已阅读并同意以上协议内容。"""

    dialog = QDialog()
    dialog.setWindowTitle(f"GROMACS GUI {VERSION_CONFIG['version_string']} - 使用协议")
    dialog.setFixedSize(600, 500)
    layout = QVBoxLayout(dialog)

    text_edit = QTextEdit()
    text_edit.setReadOnly(True)
    text_edit.setPlainText(license_text)
    text_edit.setStyleSheet("font-size: 13px; font-family: 'Microsoft YaHei';")
    layout.addWidget(text_edit)

    btn_layout = QHBoxLayout()
    agree_btn = QPushButton("我同意")
    agree_btn.setMinimumHeight(36)
    agree_btn.setStyleSheet("background-color: #4CAF50; color: white; font-size: 14px; font-weight: bold; border-radius: 4px;")
    refuse_btn = QPushButton("不同意")
    refuse_btn.setMinimumHeight(36)
    refuse_btn.setStyleSheet("background-color: #f44336; color: white; font-size: 14px; border-radius: 4px;")
    btn_layout.addWidget(refuse_btn)
    btn_layout.addWidget(agree_btn)
    layout.addLayout(btn_layout)

    agree_btn.clicked.connect(lambda: dialog.done(1))
    refuse_btn.clicked.connect(lambda: dialog.done(0))

    result = dialog.exec_() == 1
    if result:
        config["license_accepted"] = True
        config["license_accepted_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    return result


def _setup_exception_handler():
    import traceback
    import datetime
    
    def handler(exc_type, exc_value, exc_tb):
        if getattr(sys, 'frozen', False):
            base = os.path.dirname(sys.executable)
        else:
            base = os.path.dirname(os.path.abspath(__file__))
        crash_dir = os.path.join(base, "logs")
        os.makedirs(crash_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        crash_path = os.path.join(crash_dir, f"crash_{timestamp}.log")
        
        try:
            with open(crash_path, "w", encoding="utf-8") as f:
                f.write("=" * 80 + "\n")
                f.write("GROMACS GUI 崩溃日志\n")
                f.write("=" * 80 + "\n")
                f.write(f"崩溃时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Python版本: {sys.version}\n")
                f.write(f"操作系统: {platform.system()} {platform.release()}\n")
                f.write("\n" + "=" * 80 + "\n")
                f.write("异常类型: " + str(exc_type) + "\n")
                f.write("异常值: " + str(exc_value) + "\n")
                f.write("\n堆栈跟踪:\n")
                traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
                f.write("\n" + "=" * 80 + "\n")
            
            print(f"程序崩溃，详细日志已保存到: {crash_path}")
        except Exception as e:
            print(f"无法保存崩溃日志: {e}")
            traceback.print_exception(exc_type, exc_value, exc_tb)
    
    sys.excepthook = handler

_instance_lock = None

def _check_single_instance():
    global _instance_lock
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    lock_file = os.path.join(base, "gromacs_gui.lock")
    
    try:
        if sys.platform == "win32":
            import msvcrt
            _instance_lock = open(lock_file, 'w')
            try:
                msvcrt.locking(_instance_lock.fileno(), msvcrt.LK_LOCK, 1)
            except IOError:
                _instance_lock.close()
                _instance_lock = None
                return False
        else:
            import fcntl
            _instance_lock = open(lock_file, 'w')
            try:
                fcntl.flock(_instance_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except IOError:
                _instance_lock.close()
                _instance_lock = None
                return False
        return True
    except Exception:
        return True


def run_main():
        _setup_exception_handler()
    
        if not _check_single_instance():
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Warning)
            msg.setWindowTitle("程序已运行")
            msg.setText("GROMACS GUI 已经在运行中！\n\n请先关闭已有的实例，再重新启动。")
            msg.exec_()
            sys.exit(0)
    
        app = QApplication(sys.argv)
        app.setStyle("Fusion")

        # 检查使用协议
        if not _check_license_agreement():
            sys.exit(0)

        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(53, 53, 53))
        palette.setColor(QPalette.WindowText, Qt.white)
        palette.setColor(QPalette.Base, QColor(35, 35, 35))
        palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
        palette.setColor(QPalette.ToolTipBase, Qt.white)
        palette.setColor(QPalette.ToolTipText, Qt.white)
        palette.setColor(QPalette.Text, Qt.white)
        palette.setColor(QPalette.Button, QColor(53, 53, 53))
        palette.setColor(QPalette.ButtonText, Qt.white)
        palette.setColor(QPalette.BrightText, Qt.red)
        palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.HighlightedText, Qt.black)
        app.setPalette(palette)

        try:
            window = GromacsGUI()
            QTimer.singleShot(100, window.show)
            sys.exit(app.exec_())
        except Exception as e:
            import traceback
            print(f"程序启动失败: {e}")
            traceback.print_exc()



if __name__ == "__main__":
    run_main()
