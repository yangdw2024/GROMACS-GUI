#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实时模拟监控面板
"""

from datetime import datetime
import os
import time

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QGroupBox,
    QSpinBox, QScrollArea, QFileDialog, QGridLayout, QMessageBox, QPlainTextEdit,
    QDialog
)


from PyQt5.QtGui import QFont, QColor


from gui.widgets.curve_widget import CurveWidget


from gui.workers.data_extractor import DataExtractorThread


# =============================================================================
# 实时模拟监控面板
# =============================================================================
class SimulationMonitorDialog(QDialog):
    def __init__(self, parent=None, work_dir="", gmx_exe=""):
        super().__init__(parent)
        self.setWindowTitle("实时模拟监控面板")
        self.resize(900, 700)
        self._work_dir = work_dir
        self._edr_path = ""
        self._gmx_exe = gmx_exe
        self._extract_thread = None
        self._create_ui()

    def _create_ui(self):
        main_layout = QVBoxLayout(self)

        top_group = QGroupBox("控制设置")
        top_layout = QHBoxLayout(top_group)

        edr_label = QLabel("EDR文件:")
        self.edr_edit = QLineEdit()
        self.edr_edit.setReadOnly(True)
        self.btn_browse = QPushButton("浏览...")
        self.btn_browse.clicked.connect(self._browse_edr)

        interval_label = QLabel("刷新间隔(秒):")
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 60)
        self.interval_spin.setValue(5)

        self.btn_start = QPushButton("开始监控")
        self.btn_start.clicked.connect(self._on_start)
        self.btn_stop = QPushButton("停止监控")
        self.btn_stop.clicked.connect(self._on_stop)
        self.btn_stop.setEnabled(False)
        self.btn_clear = QPushButton("清空数据")
        self.btn_clear.clicked.connect(self._on_clear)

        top_layout.addWidget(edr_label)
        top_layout.addWidget(self.edr_edit, 1)
        top_layout.addWidget(self.btn_browse)
        top_layout.addSpacing(20)
        top_layout.addWidget(interval_label)
        top_layout.addWidget(self.interval_spin)
        top_layout.addSpacing(20)
        top_layout.addWidget(self.btn_start)
        top_layout.addWidget(self.btn_stop)
        top_layout.addWidget(self.btn_clear)

        main_layout.addWidget(top_group)

        curves_group = QGroupBox("能量曲线")
        curves_layout = QVBoxLayout(curves_group)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(10)

        self.curve_temp = CurveWidget(y_label="温度 (Temperature, K)", color=QColor(220, 50, 50))
        self.curve_press = CurveWidget(y_label="压力 (Pressure, bar)", color=QColor(50, 100, 220))
        self.curve_pot = CurveWidget(y_label="势能 (Potential Energy, kJ/mol)", color=QColor(50, 180, 70))
        self.curve_total = CurveWidget(y_label="总能量 (Total Energy, kJ/mol)", color=QColor(150, 50, 200))

        scroll_layout.addWidget(self.curve_temp)
        scroll_layout.addWidget(self.curve_press)
        scroll_layout.addWidget(self.curve_pot)
        scroll_layout.addWidget(self.curve_total)

        scroll_area.setWidget(scroll_content)
        curves_layout.addWidget(scroll_area)

        main_layout.addWidget(curves_group, 1)

        values_group = QGroupBox("当前数值")
        values_layout = QGridLayout(values_group)

        self.lbl_temp = QLabel("温度: -- K")
        self.lbl_temp.setStyleSheet("color: #dc3232; font-weight: bold; font-size: 13px;")
        self.lbl_press = QLabel("压力: -- bar")
        self.lbl_press.setStyleSheet("color: #3264dc; font-weight: bold; font-size: 13px;")
        self.lbl_pot = QLabel("势能: -- kJ/mol")
        self.lbl_pot.setStyleSheet("color: #32b446; font-weight: bold; font-size: 13px;")
        self.lbl_total = QLabel("总能量: -- kJ/mol")
        self.lbl_total.setStyleSheet("color: #9632c8; font-weight: bold; font-size: 13px;")

        values_layout.addWidget(self.lbl_temp, 0, 0)
        values_layout.addWidget(self.lbl_press, 0, 1)
        values_layout.addWidget(self.lbl_pot, 1, 0)
        values_layout.addWidget(self.lbl_total, 1, 1)

        main_layout.addWidget(values_group)

        log_group = QGroupBox("日志输出")
        log_layout = QVBoxLayout(log_group)
        self.log_edit = QPlainTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setMaximumBlockCount(500)
        self.log_edit.setFont(QFont("Consolas", 9))
        log_layout.addWidget(self.log_edit)
        log_group.setMaximumHeight(150)

        main_layout.addWidget(log_group)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_close = QPushButton("关闭")
        self.btn_close.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_close)
        main_layout.addLayout(btn_layout)

    def _browse_edr(self):
        start_dir = self._work_dir if self._work_dir else os.getcwd()
        filepath, _ = QFileDialog.getOpenFileName(
            self, "选择EDR能量文件", start_dir,
            "EDR能量文件 (*.edr);;所有文件 (*.*)"
        )
        if filepath:
            self.load_edr(filepath)

    def load_edr(self, filepath):
        self._edr_path = filepath
        self.edr_edit.setText(filepath)
        self._append_log(f"[INFO] 已加载EDR文件: {filepath}")

    def _on_start(self):
        if not self._edr_path:
            QMessageBox.warning(self, "提示", "请先选择EDR文件！")
            return
        if not os.path.isfile(self._edr_path):
            QMessageBox.warning(self, "提示", "EDR文件不存在！")
            return

        interval = self.interval_spin.value()

        if self._extract_thread is None:
            self._extract_thread = DataExtractorThread(self)
            self._extract_thread.data_signal.connect(self._on_data_received)
            self._extract_thread.error_signal.connect(self._on_error)
            self._extract_thread.log_signal.connect(self._append_log)

        self._extract_thread.set_gmx_exe(self._gmx_exe)
        self._extract_thread.set_edr_path(self._edr_path, self._work_dir)
        self._extract_thread.set_interval(interval)
        self._extract_thread.reset()
        self._extract_thread.start()

        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.btn_browse.setEnabled(False)
        self.interval_spin.setEnabled(False)
        self._append_log(f"[INFO] 开始监控... (GROMACS: {os.path.basename(self._gmx_exe) if self._gmx_exe else '未设置'})")

    def _on_stop(self):
        if self._extract_thread:
            self._extract_thread.stop()
            self._extract_thread.wait(3000)

        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.btn_browse.setEnabled(True)
        self.interval_spin.setEnabled(True)
        self._append_log("[INFO] 已停止监控")

    def _on_clear(self):
        self.curve_temp.clear()
        self.curve_press.clear()
        self.curve_pot.clear()
        self.curve_total.clear()
        self.lbl_temp.setText("温度: -- K")
        self.lbl_press.setText("压力: -- bar")
        self.lbl_pot.setText("势能: -- kJ/mol")
        self.lbl_total.setText("总能量: -- kJ/mol")
        if self._extract_thread:
            self._extract_thread.reset()
        self._append_log("[INFO] 已清空数据")

    def _on_data_received(self, data):
        times = data.get("time", [])
        if not times:
            return

        temp_vals = data.get("Temperature", [])
        press_vals = data.get("Pressure", [])
        pot_vals = data.get("Potential", [])
        total_vals = data.get("Total Energy", [])

        for i, t in enumerate(times):
            if i < len(temp_vals):
                self.curve_temp.add_point(t, temp_vals[i])
            if i < len(press_vals):
                self.curve_press.add_point(t, press_vals[i])
            if i < len(pot_vals):
                self.curve_pot.add_point(t, pot_vals[i])
            if i < len(total_vals):
                self.curve_total.add_point(t, total_vals[i])

        last_temp = self.curve_temp.get_last_value()
        last_press = self.curve_press.get_last_value()
        last_pot = self.curve_pot.get_last_value()
        last_total = self.curve_total.get_last_value()

        if last_temp is not None:
            self.lbl_temp.setText(f"温度: {last_temp:.3f} K")
        if last_press is not None:
            self.lbl_press.setText(f"压力: {last_press:.3f} bar")
        if last_pot is not None:
            self.lbl_pot.setText(f"势能: {last_pot:.3f} kJ/mol")
        if last_total is not None:
            self.lbl_total.setText(f"总能量: {last_total:.3f} kJ/mol")

    def _on_error(self, msg):
        self._append_log(f"[ERROR] {msg}")

    def _append_log(self, msg):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_edit.appendPlainText(f"[{timestamp}] {msg}")
        scrollbar = self.log_edit.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def reject(self):
        if self._extract_thread and self._extract_thread.isRunning():
            self._extract_thread.stop()
            self._extract_thread.wait(3000)
        super().reject()

    def closeEvent(self, event):
        if self._extract_thread and self._extract_thread.isRunning():
            self._extract_thread.stop()
            self._extract_thread.wait(3000)
        super().closeEvent(event)
