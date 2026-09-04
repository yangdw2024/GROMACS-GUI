#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自定义模板管理对话框
"""

import json
import os
import sys

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTextEdit, QGroupBox,
    QComboBox, QGridLayout, QMessageBox, QDialog, QDialogButtonBox, QListWidget
)


from PyQt5.QtCore import Qt


from PyQt5.QtGui import QFont


from gui.dialogs.help_dialog import HelpDialog


class CustomTemplateDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("管理自定义模板")
        self.resize(800, 600)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self._templates = []
        self._current_index = -1
        self._create_ui()
        self._load_templates()

    def _create_ui(self):
        main_layout = QVBoxLayout(self)

        header_layout = QHBoxLayout()
        title_label = QLabel("管理自定义模板")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        help_btn = QPushButton("?")
        help_btn.setStyleSheet(
            "QPushButton { background-color: #2196F3; color: white; font-weight: bold; "
            "border-radius: 10px; width: 24px; height: 24px; font-size: 14px; }"
            "QPushButton:hover { background-color: #1976D2; }"
        )
        help_btn.setToolTip("显示帮助文档")
        help_btn.clicked.connect(self._show_help)
        header_layout.addWidget(help_btn)
        main_layout.addLayout(header_layout)

        top_layout = QHBoxLayout()

        list_group = QGroupBox("模板列表")
        list_layout = QVBoxLayout(list_group)
        self.template_list = QListWidget()
        self.template_list.currentRowChanged.connect(self._on_template_selected)
        list_layout.addWidget(self.template_list)

        btn_layout = QVBoxLayout()
        self.btn_add = QPushButton("添加")
        self.btn_add.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 6px 12px; }"
            "QPushButton:hover { background-color: #45a049; }"
        )
        self.btn_add.clicked.connect(self._on_add)

        self.btn_edit = QPushButton("编辑")
        self.btn_edit.setStyleSheet(
            "QPushButton { background-color: #FF9800; color: white; font-weight: bold; padding: 6px 12px; }"
            "QPushButton:hover { background-color: #F57C00; }"
        )
        self.btn_edit.clicked.connect(self._on_edit)
        self.btn_edit.setEnabled(False)

        self.btn_delete = QPushButton("删除")
        self.btn_delete.setStyleSheet(
            "QPushButton { background-color: #f44336; color: white; font-weight: bold; padding: 6px 12px; }"
            "QPushButton:hover { background-color: #da190b; }"
        )
        self.btn_delete.clicked.connect(self._on_delete)
        self.btn_delete.setEnabled(False)

        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_edit)
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addStretch()

        top_layout.addWidget(list_group, stretch=1)
        top_layout.addLayout(btn_layout)
        main_layout.addLayout(top_layout)

        edit_group = QGroupBox("模板编辑")
        edit_layout = QVBoxLayout(edit_group)

        form_layout = QGridLayout()

        form_layout.addWidget(QLabel("模板名称:"), 0, 0)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("输入模板名称")
        form_layout.addWidget(self.name_edit, 0, 1)

        form_layout.addWidget(QLabel("脚本类型:"), 1, 0)
        self.type_combo = QComboBox()
        self.type_combo.addItems(["PowerShell", "Batch", "Shell"])
        form_layout.addWidget(self.type_combo, 1, 1)

        edit_layout.addLayout(form_layout)

        content_label = QLabel("脚本内容:")
        edit_layout.addWidget(content_label)

        self.content_edit = QTextEdit()
        self.content_edit.setFont(QFont("Consolas", 9))
        edit_layout.addWidget(self.content_edit, stretch=1)

        main_layout.addWidget(edit_group, stretch=1)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self._on_save)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

    def _load_templates(self):
        if getattr(sys, 'frozen', False):
            base = os.path.dirname(sys.executable)
        else:
            base = os.path.dirname(os.path.abspath(__file__))
        templates_file = os.path.join(base, "templates.json")
        if os.path.isfile(templates_file):
            try:
                with open(templates_file, "r", encoding="utf-8") as f:
                    self._templates = json.load(f)
            except Exception:
                self._templates = []
        else:
            self._templates = []
        self._update_list()

    def _save_templates(self):
        if getattr(sys, 'frozen', False):
            base = os.path.dirname(sys.executable)
        else:
            base = os.path.dirname(os.path.abspath(__file__))
        templates_file = os.path.join(base, "templates.json")
        try:
            with open(templates_file, "w", encoding="utf-8") as f:
                json.dump(self._templates, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    def _update_list(self):
        self.template_list.clear()
        for template in self._templates:
            self.template_list.addItem(f"{template['name']} ({template['type']})")

    def _on_template_selected(self, index):
        self._current_index = index
        self.btn_edit.setEnabled(index >= 0)
        self.btn_delete.setEnabled(index >= 0)
        if index >= 0:
            template = self._templates[index]
            self.name_edit.setText(template["name"])
            idx = self.type_combo.findText(template["type"])
            if idx >= 0:
                self.type_combo.setCurrentIndex(idx)
            self.content_edit.setPlainText(template["content"])
        else:
            self.name_edit.clear()
            self.type_combo.setCurrentIndex(0)
            self.content_edit.clear()

    def _on_add(self):
        self._current_index = -1
        self.name_edit.clear()
        self.type_combo.setCurrentIndex(0)
        self.content_edit.clear()
        self.name_edit.setFocus()

    def _on_edit(self):
        if self._current_index >= 0:
            self.name_edit.setFocus()

    def _on_delete(self):
        if self._current_index >= 0:
            template = self._templates[self._current_index]
            reply = QMessageBox.question(
                self, "确认删除",
                f"确定要删除模板 '{template['name']}' 吗？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                del self._templates[self._current_index]
            self._save_templates()
            self._update_list()
            self._on_template_selected(-1)

    def _show_help(self):
        dlg = HelpDialog(self)
        dlg.exec_()

    def _on_save(self):
        name = self.name_edit.text().strip()
        content = self.content_edit.toPlainText().strip()
        if not name:
            QMessageBox.warning(self, "提示", "请输入模板名称！")
            return
        if not content:
            QMessageBox.warning(self, "提示", "请输入脚本内容！")
            return

        template = {
            "name": name,
            "type": self.type_combo.currentText(),
            "content": content
        }

        if self._current_index >= 0:
            self._templates[self._current_index] = template
        else:
            self._templates.append(template)

        if self._save_templates():
            QMessageBox.information(self, "成功", "模板已保存！")
            self.accept()
        else:
            QMessageBox.error(self, "失败", "保存模板失败！")

    def get_templates(self):
        return self._templates
