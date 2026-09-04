#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据提取线程（DataExtractorThread）
"""

import os
import platform
import subprocess
import sys
import time

from PyQt5.QtCore import pyqtSignal, QThread


# =============================================================================
# 数据提取线程
# =============================================================================
class DataExtractorThread(QThread):
    data_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)
    log_signal = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._edr_path = ""
        self._work_dir = ""
        self._interval = 5
        self._running = False
        self._last_time = -1.0
        self._energy_items = ["Temperature", "Pressure", "Potential", "Total-Energy"]
        self._gmx_exe = ""

    def set_gmx_exe(self, gmx_exe):
        self._gmx_exe = gmx_exe

    def set_edr_path(self, path, work_dir=""):
        self._edr_path = path
        self._work_dir = work_dir

    def set_interval(self, seconds):
        self._interval = max(1, int(seconds))

    def stop(self):
        self._running = False

    def reset(self):
        self._last_time = -1.0

    def run(self):
        self._running = True
        self._last_time = -1.0
        self.log_signal.emit("[INFO] 数据提取线程已启动")

        while self._running:
            try:
                if not self._edr_path or not os.path.isfile(self._edr_path):
                    self.error_signal.emit(f"EDR文件不存在: {self._edr_path}")
                    self._sleep_interval()
                    continue

                data = self._extract_data()
                if data and data.get("time"):
                    self.data_signal.emit(data)

            except Exception as e:
                self.error_signal.emit(f"提取数据时出错: {str(e)}")

            self._sleep_interval()

        self.log_signal.emit("[INFO] 数据提取线程已停止")

    def _sleep_interval(self):
        for _ in range(self._interval * 10):
            if not self._running:
                break
            self.msleep(100)

    def _extract_data(self):
        import tempfile

        tmp_dir = tempfile.gettempdir()
        xvg_path = os.path.join(tmp_dir, f"sim_monitor_{int(time.time() * 1000)}.xvg")

        try:
            if not self._gmx_exe or not os.path.isfile(self._gmx_exe):
                raise Exception(f"GROMACS可执行文件无效或未设置: {self._gmx_exe}")

            input_str = "\n".join(self._energy_items) + "\n"

            cmd = [self._gmx_exe, "energy", "-f", self._edr_path, "-o", xvg_path]

            work_dir = self._work_dir if self._work_dir else os.path.dirname(self._edr_path)
            if not work_dir:
                work_dir = os.getcwd()

            if sys.platform.startswith("win"):
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                process = subprocess.Popen(
                    cmd,
                    cwd=work_dir,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    startupinfo=startupinfo,
                    shell=False
                )
            else:
                process = subprocess.Popen(
                    cmd,
                    cwd=work_dir,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    shell=False
                )

            stdout, _ = process.communicate(input=input_str, timeout=30)

            if process.returncode != 0:
                raise Exception(f"gmx energy 命令失败 (returncode={process.returncode}): {stdout[-500:]}")

            if not os.path.isfile(xvg_path):
                raise Exception("xvg输出文件未生成")

            result = self._parse_xvg(xvg_path)
            return result

        except subprocess.TimeoutExpired:
            if process:
                try:
                    process.kill()
                    process.wait()
                except Exception:
                    pass
            raise Exception("gmx energy 命令超时")
        except Exception as e:
            raise Exception(f"数据提取失败: {str(e)}")
        finally:
            if os.path.isfile(xvg_path):
                try:
                    os.remove(xvg_path)
                except Exception:
                    pass

    def _parse_xvg(self, xvg_path):
        result = {"time": []}
        for item in self._energy_items:
            key = item.replace("-", " ")
            result[key] = []

        with open(xvg_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if line.startswith("#") or line.startswith("@"):
                    continue

                parts = line.split()
                if len(parts) < len(self._energy_items) + 1:
                    continue

                try:
                    t = float(parts[0])
                    if t <= self._last_time:
                        continue

                    result["time"].append(t)
                    for i, item in enumerate(self._energy_items):
                        key = item.replace("-", " ")
                        val = float(parts[i + 1])
                        result[key].append(val)

                except (ValueError, IndexError):
                    continue

        if result["time"]:
            self._last_time = result["time"][-1]
            self.log_signal.emit(f"[INFO] 提取 {len(result['time'])} 个新数据点 (最新时间: {self._last_time:.2f} ps)")

        return result
