#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GROMACS 命令执行线程（GromacsWorker）
"""

import platform
import subprocess
import sys

from PyQt5.QtCore import pyqtSignal, QThread


# =============================================================================
# 工作线程：用于执行 GROMACS 命令
# =============================================================================
class GromacsWorker(QThread):
    log_signal = pyqtSignal(str, str)
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(bool)
    step_finished_signal = pyqtSignal(str, bool)

    def __init__(self, cmd_list, work_dir, step_name="", env=None, mem_limit_gb=None, stdin_input=None):
        super().__init__()
        self.cmd_list = cmd_list if isinstance(cmd_list, list) else [cmd_list]
        self.work_dir = work_dir
        self.step_name = step_name
        self.env = env
        self.mem_limit_gb = mem_limit_gb
        # 修复：支持通过stdin为交互式命令（如 gmx energy/rms/rmsf/gyrate/msd/distance/angle）提供输入
        # 传入 None 时不启用 PIPE，避免部分进程因管道关闭而崩溃
        self.stdin_input = stdin_input
        self.process = None
        self._is_running = True
        self.current_cmd_index = 0
        self._job_handle = None

    def run(self):
        overall_success = True
        for idx, cmd in enumerate(self.cmd_list):
            if not self._is_running:
                overall_success = False
                break
            self.current_cmd_index = idx
            success = self._run_single(cmd)
            if self.step_name:
                self.step_finished_signal.emit(self.step_name, success)
            if not success:
                overall_success = False
                break
        self._close_job()
        self.finished_signal.emit(overall_success)

    def _create_job_with_mem_limit(self):
        if not sys.platform.startswith("win") or self.mem_limit_gb is None:
            return None
        try:
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

            JobObjectExtendedLimitInformation = 9

            class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
                _fields_ = [
                    ("PerProcessUserTimeLimit", ctypes.c_int64),
                    ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", ctypes.c_uint32),
                    ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t),
                    ("ActiveProcessLimit", ctypes.c_uint32),
                    ("Affinity", ctypes.c_size_t),
                    ("PriorityClass", ctypes.c_uint32),
                    ("SchedulingClass", ctypes.c_uint32),
                ]

            class IO_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("ReadOperationCount", ctypes.c_uint64),
                    ("WriteOperationCount", ctypes.c_uint64),
                    ("OtherOperationCount", ctypes.c_uint64),
                    ("ReadTransferCount", ctypes.c_uint64),
                    ("WriteTransferCount", ctypes.c_uint64),
                    ("OtherTransferCount", ctypes.c_uint64),
                ]

            class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
                _fields_ = [
                    ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                    ("IoInfo", IO_COUNTERS),
                    ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t),
                    ("PeakJobMemoryUsed", ctypes.c_size_t),
                ]

            JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100

            job_handle = kernel32.CreateJobObjectW(None, None)
            if not job_handle:
                return None

            mem_bytes = int(self.mem_limit_gb * 1024 * 1024 * 1024)
            info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
            info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_PROCESS_MEMORY
            info.ProcessMemoryLimit = mem_bytes

            result = kernel32.SetInformationJobObject(
                job_handle,
                JobObjectExtendedLimitInformation,
                ctypes.byref(info),
                ctypes.sizeof(info)
            )
            if not result:
                kernel32.CloseHandle(job_handle)
                return None

            return job_handle
        except Exception:
            return None

    def _assign_process_to_job(self, pid):
        if self._job_handle is None or pid is None:
            return False
        try:
            import ctypes
            kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
            process_handle = kernel32.OpenProcess(0x1F0FFF, False, pid)
            if not process_handle:
                return False
            result = kernel32.AssignProcessToJobObject(self._job_handle, process_handle)
            kernel32.CloseHandle(process_handle)
            return bool(result)
        except Exception:
            return False

    def _close_job(self):
        if self._job_handle is not None:
            try:
                import ctypes
                kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
                kernel32.CloseHandle(self._job_handle)
            except Exception:
                pass
            self._job_handle = None

    def _run_single(self, cmd):
        if isinstance(cmd, list):
            cmd_str = " ".join(cmd)
        else:
            cmd_str = cmd
            cmd = cmd.split()

        self.log_signal.emit(f"[CMD] {cmd_str}", "info")

        if self._job_handle is None and self.mem_limit_gb is not None and sys.platform.startswith("win"):
            self._job_handle = self._create_job_with_mem_limit()
            if self._job_handle:
                self.log_signal.emit(f"内存限制已启用: {self.mem_limit_gb} GB", "info")

        # 修复：根据是否提供stdin_input决定stdin参数
        # - 提供了stdin_input：使用PIPE并在启动后写入
        # - 未提供(stdin_input is None)：使用DEVNULL/None，避免某些命令因stdin关闭而退出
        stdin_kw = None
        if self.stdin_input is not None:
            stdin_kw = subprocess.PIPE

        try:
            if sys.platform.startswith("win"):
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                self.process = subprocess.Popen(
                    cmd,
                    cwd=self.work_dir,
                    stdin=stdin_kw,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    bufsize=1,
                    env=self.env,
                    startupinfo=startupinfo,
                    shell=False
                )
                if self._job_handle:
                    self._assign_process_to_job(self.process.pid)
            else:
                self.process = subprocess.Popen(
                    cmd,
                    cwd=self.work_dir,
                    stdin=stdin_kw,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    bufsize=1,
                    env=self.env,
                    shell=False
                )

            # 修复：如果需要stdin输入，立即写入并关闭stdin
            # 必须在process启动后立即写入，避免命令在等待stdin时阻塞
            if self.stdin_input is not None and self.process.stdin is not None:
                try:
                    self.process.stdin.write(self.stdin_input)
                    self.process.stdin.flush()
                except Exception as e:
                    self.log_signal.emit(f"[WARN] 写入stdin失败: {str(e)}", "warning")
                finally:
                    try:
                        self.process.stdin.close()
                    except Exception:
                        pass

            while self._is_running and self.process.poll() is None:
                line = self.process.stdout.readline()
                if line:
                    self._emit_line(line)

            if self.process.stdout:
                for line in self.process.stdout:
                    self._emit_line(line)

            return_code = self.process.returncode
            if return_code == 0:
                self.log_signal.emit(f"[OK] 命令执行成功 (returncode=0)", "success")
                return True
            else:
                self.log_signal.emit(f"[ERROR] 命令执行失败 (returncode={return_code})", "error")
                return False

        except Exception as e:
            self.log_signal.emit(f"[ERROR] 执行异常: {str(e)}", "error")
            return False

    def _emit_line(self, line):
        line = line.rstrip("\n\r")
        if not line:
            return
        low = line.lower()
        if any(x in low for x in ["error", "fatal", "failed", "cannot", "unable", "segmentation"]):
            level = "error"
        elif any(x in low for x in ["warning", "warn", "attention", "note:"]):
            level = "warning"
        elif any(x in low for x in ["success", "finished", "completed", "done", "congratulations"]):
            level = "success"
        else:
            level = "info"
        self.log_signal.emit(line, level)

    def stop(self):
        self._is_running = False
        if self.process:
            try:
                # 优先尝试优雅终止，给GROMACS写入CPT检查点的时间
                self.process.terminate()
                self.process.wait(timeout=10)
            except Exception:
                try:
                    self.process.kill()
                    self.process.wait(timeout=3)
                except Exception:
                    pass
